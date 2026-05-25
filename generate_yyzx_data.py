# -*- coding: utf-8 -*-
"""
运营中心数据流水线

整合以下三个旧脚本的能力：
1. generate_optCost.py
2. generate_optCost_weekly.py
3. generate_bi_tables.py

运行结果：
- 更新月度代运营消耗表
- 更新近四周代运营消耗表
- 生成 BI Excel 文件
- 生成运行日志与核对日志
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


MONTHLY_SOURCE_TABLE = "代运营消耗数据"
CURRENT_MONTH_SOURCE_TABLE = "当月代运营消耗数据"
MONTHLY_TARGET_TABLE = "代运营团队人员消耗"
WEEKLY_TARGET_TABLE = "代运营团队人员消耗_近四周"
HR_SOURCE_TABLE = "月度人力数据源"
PORT_MEDIA_SOURCE_TABLE = "媒体消耗_每日更新"
BI_OUTPUT_FILE_NAME = "运营团队BI报表.xlsx"
LOG_DIR_NAME = "logs"
K_DEPARTMENT_NAMES = ["K2", "K3", "K4", "K5", "K7"]
OPTIMIZER_GRAIN = "优化师"
FIELD_NAME_MAP = {
    "center_name": "所属中心",
    "dept_name": "运营部门",
    "team_name": "组别",
    "opt_name": "姓名",
    "media": "媒体",
    "media_port": "端口",
    "brand": "品牌名称",
    "product": "产品名称",
    "cost_date": "消耗日期",
    "total_cost": "消耗",
    "acct_count": "有消耗账户数",
    "year": "年",
    "month": "月",
}
MONTHLY_OUTPUT_SOURCE_COLUMNS = list(FIELD_NAME_MAP.keys())
DEFAULT_CODE_DIR = Path(r"C:\Users\Lly621\Desktop\py_calc\code")


@dataclass(frozen=True)
class PipelineConfig:
    script_dir: Path
    code_dir: Path
    output_dir: Path
    log_dir: Path
    monthly_start_date: str
    monthly_target_table: str = MONTHLY_TARGET_TABLE
    weekly_target_table: str = WEEKLY_TARGET_TABLE
    monthly_source_table: str = MONTHLY_SOURCE_TABLE
    current_month_source_table: str = CURRENT_MONTH_SOURCE_TABLE
    bi_output_file_name: str = BI_OUTPUT_FILE_NAME

    @property
    def bi_output_path(self) -> Path:
        return self.output_dir / self.bi_output_file_name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成运营中心数据并输出 BI 报表")
    parser.add_argument(
        "--start-date",
        default=None,
        help="月度消耗写库的起始日期；不填写时按当月代运营消耗数据的最新消耗日期所在月 1 号",
    )
    parser.add_argument(
        "--only",
        choices=["all", "monthly", "weekly", "bi"],
        default="all",
        help="只执行某一段流程",
    )
    parser.add_argument(
        "--code-dir",
        default=str(DEFAULT_CODE_DIR),
        help="数据库读写辅助模块所在目录",
    )
    return parser.parse_args()


def build_config(args: argparse.Namespace, monthly_start_date: str | None = None) -> PipelineConfig:
    script_dir = Path(__file__).resolve().parent
    output_dir = script_dir
    log_dir = output_dir / LOG_DIR_NAME
    return PipelineConfig(
        script_dir=script_dir,
        code_dir=Path(args.code_dir),
        output_dir=output_dir,
        log_dir=log_dir,
        monthly_start_date=monthly_start_date or args.start_date or "",
    )


def ensure_code_dir_on_path(code_dir: Path) -> None:
    if not code_dir.exists():
        raise FileNotFoundError(f"未找到数据库辅助模块目录: {code_dir}")
    code_dir_str = str(code_dir)
    if code_dir_str not in sys.path:
        sys.path.insert(0, code_dir_str)


def import_data_helpers(code_dir: Path) -> dict[str, Any]:
    ensure_code_dir_on_path(code_dir)
    from read_my_data import read_my_data  # type: ignore
    from upsert_my_data import truncate_insert, upsert_by_date  # type: ignore

    return {
        "read_my_data": read_my_data,
        "truncate_insert": truncate_insert,
        "upsert_by_date": upsert_by_date,
    }


def resolve_default_monthly_start_date(helpers: dict[str, Any], current_table: str) -> str:
    latest_df = helpers["read_my_data"](f"SELECT MAX(cost_date) AS max_cost_date FROM `{current_table}`")
    latest_value = latest_df.iloc[0, 0] if not latest_df.empty else None
    if latest_value is None or pd.isna(latest_value):
        raise ValueError(f"未能从 {current_table} 获取最新消耗日期，无法自动确定 --start-date。")

    latest_timestamp = pd.to_datetime(latest_value)
    return latest_timestamp.replace(day=1).strftime("%Y-%m-%d")


def setup_logger(log_dir: Path) -> tuple[logging.Logger, Path]:
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"generate_yyzx_data_{timestamp}.log"

    logger = logging.getLogger(f"generate_yyzx_data_{timestamp}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger, log_path


def log_step(logger: logging.Logger, message: str) -> None:
    logger.info(message)


def normalize_strategy_department(df: pd.DataFrame, department_column: str, team_column: str) -> pd.DataFrame:
    if df.empty:
        return df

    is_xiaohongshu = df[department_column] == "品策-小红书"
    is_other_strategy = df[department_column].astype(str).str.startswith("品策-", na=False)

    df[department_column] = np.select(
        [is_xiaohongshu, is_other_strategy],
        ["品策-小红书", "品策-其他"],
        default=df[department_column],
    )
    df[team_column] = np.select(
        [is_xiaohongshu, is_other_strategy],
        ["品策-小红书", "品策-其他"],
        default=df[team_column],
    )
    return df


def build_monthly_cost_sql(start_date: str, history_table: str, current_table: str) -> str:
    return f"""
SELECT
    year,
    month,
    center_name,
    dept_name,
    team_name,
    opt_name,
    media,
    media_port,
    brand,
    product,
    cost_date,
    SUM(total_cost) AS total_cost,
    SUM(acct_count) AS acct_count
FROM (
    SELECT
        YEAR(cost_date) AS year,
        MONTH(cost_date) AS month,
        center_name,
        my_dept_name AS dept_name,
        CASE
            WHEN center_name = "区域中心" THEN my_dept_name
            ELSE team_name
        END AS team_name,
        opt_name,
        media,
        media_port,
        brand,
        product,
        acct_id,
        cost_date,
        SUM(cost) AS total_cost,
        1 AS acct_count
    FROM `{history_table}`
    WHERE cost_date >= '{start_date}'
    GROUP BY center_name, my_dept_name, team_name, opt_name, media, media_port, brand, product, acct_id, cost_date

    UNION ALL

    SELECT
        YEAR(cost_date) AS year,
        MONTH(cost_date) AS month,
        center_name,
        my_dept_name AS dept_name,
        CASE
            WHEN center_name = "区域中心" THEN my_dept_name
            ELSE team_name
        END AS team_name,
        opt_name,
        media,
        media_port,
        brand,
        product,
        acct_id,
        cost_date,
        SUM(cost) AS total_cost,
        1 AS acct_count
    FROM `{current_table}`
    WHERE cost_date >= '{start_date}'
    GROUP BY center_name, my_dept_name, team_name, opt_name, media, media_port, brand, product, acct_id, cost_date
) daily
GROUP BY year, month, center_name, dept_name, team_name, opt_name, media, media_port, brand, product, cost_date
ORDER BY cost_date, center_name, dept_name, team_name, opt_name, media, media_port, brand, product
"""


def transform_monthly_cost_dataframe(raw_df: pd.DataFrame) -> pd.DataFrame:
    transformed_df = raw_df[MONTHLY_OUTPUT_SOURCE_COLUMNS].rename(columns=FIELD_NAME_MAP).copy()
    transformed_df["消耗日期"] = pd.to_datetime(transformed_df["消耗日期"])
    transformed_df = normalize_strategy_department(transformed_df, "运营部门", "组别")
    return transformed_df


def build_summary_dataframe(df: pd.DataFrame, group_column: str, amount_column: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[group_column, "行数", "消耗合计"])
    summary_df = (
        df.groupby(group_column)
        .agg(行数=(group_column, "count"), 消耗合计=(amount_column, "sum"))
        .reset_index()
    )
    return summary_df


def run_monthly_opt_cost_job(
    config: PipelineConfig,
    helpers: dict[str, Any],
    logger: logging.Logger,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    log_step(logger, f"[月度写库] 开始读取 {config.monthly_source_table} + {config.current_month_source_table}")
    query_sql = build_monthly_cost_sql(
        config.monthly_start_date,
        config.monthly_source_table,
        config.current_month_source_table,
    )
    raw_df = helpers["read_my_data"](query_sql)
    if raw_df.empty:
        raise ValueError("月度消耗查询结果为空，终止执行。")

    transformed_df = transform_monthly_cost_dataframe(raw_df)
    helpers["upsert_by_date"](
        transformed_df,
        config.monthly_target_table,
        "消耗日期",
        config.monthly_start_date,
    )

    summary = build_summary_dataframe(transformed_df, "年", "消耗")
    result = {
        "job_name": "monthly_opt_cost",
        "source_rows": len(raw_df),
        "output_rows": len(transformed_df),
        "target_table": config.monthly_target_table,
        "min_date": transformed_df["消耗日期"].min(),
        "max_date": transformed_df["消耗日期"].max(),
        "total_cost": float(transformed_df["消耗"].sum()),
        "summary_df": summary,
    }
    log_step(logger, f"[月度写库] 完成，写入 {len(transformed_df):,} 行 -> {config.monthly_target_table}")
    return transformed_df, result


def query_latest_cost_date(helpers: dict[str, Any], history_table: str, current_table: str) -> date:
    current_df = helpers["read_my_data"](f"SELECT MAX(cost_date) AS max_cost_date FROM `{current_table}`")
    latest_value = current_df.iloc[0, 0]
    if latest_value is None or pd.isna(latest_value):
        history_df = helpers["read_my_data"](f"SELECT MAX(cost_date) AS max_cost_date FROM `{history_table}`")
        latest_value = history_df.iloc[0, 0]

    latest_timestamp = pd.to_datetime(latest_value)
    return latest_timestamp.date()


def build_recent_week_windows(latest_date: date) -> list[dict[str, Any]]:
    monday_of_current_week = latest_date - timedelta(days=latest_date.weekday())
    week_windows: list[dict[str, Any]] = []
    for offset in range(4):
        week_start = monday_of_current_week - timedelta(weeks=offset)
        week_end = latest_date if offset == 0 else week_start + timedelta(days=6)
        week_label = f"W{4 - offset}-[{week_start.strftime('%m%d')}~{week_end.strftime('%m%d')}]"
        week_windows.append({"label": week_label, "start": week_start, "end": week_end})
    return week_windows


def build_weekly_cost_sql(week_windows: list[dict[str, Any]], history_table: str, current_table: str) -> str:
    earliest_date = week_windows[-1]["start"].strftime("%Y-%m-%d")
    return f"""
SELECT
    center_name,
    my_dept_name AS dept_name,
    CASE
        WHEN center_name = "区域中心" THEN my_dept_name
        ELSE team_name
    END AS team_name,
    opt_name,
    media,
    brand,
    product,
    acct_id,
    cost_date,
    cost
FROM `{history_table}`
WHERE cost_date >= '{earliest_date}'

UNION ALL

SELECT
    center_name,
    my_dept_name AS dept_name,
    CASE
        WHEN center_name = "区域中心" THEN my_dept_name
        ELSE team_name
    END AS team_name,
    opt_name,
    media,
    brand,
    product,
    acct_id,
    cost_date,
    cost
FROM `{current_table}`
WHERE cost_date >= '{earliest_date}'
"""


def assign_week_label(cost_date: pd.Timestamp, week_windows: list[dict[str, Any]]) -> str | None:
    row_date = cost_date.date() if isinstance(cost_date, pd.Timestamp) else pd.to_datetime(cost_date).date()
    for week_window in week_windows:
        if week_window["start"] <= row_date <= week_window["end"]:
            return week_window["label"]
    return None


def transform_weekly_cost_dataframe(raw_df: pd.DataFrame, week_windows: list[dict[str, Any]]) -> pd.DataFrame:
    transformed_df = raw_df.copy()
    transformed_df["cost_date"] = pd.to_datetime(transformed_df["cost_date"])
    transformed_df["周标签"] = transformed_df["cost_date"].apply(lambda value: assign_week_label(value, week_windows))
    transformed_df = transformed_df.dropna(subset=["周标签"]).copy()
    transformed_df = normalize_strategy_department(transformed_df, "dept_name", "team_name")

    grouped_df = (
        transformed_df.groupby(
            ["center_name", "dept_name", "team_name", "opt_name", "media", "brand", "product", "周标签"],
            dropna=False,
        )
        .agg(
            消耗=("cost", "sum"),
            有消耗账户数=("acct_id", "nunique"),
            天数=("cost_date", "nunique"),
        )
        .reset_index()
        .rename(
            columns={
                "center_name": "所属中心",
                "dept_name": "运营部门",
                "team_name": "组别",
                "opt_name": "姓名",
                "media": "媒体",
                "brand": "品牌名称",
                "product": "产品名称",
            }
        )
    )
    return grouped_df


def run_weekly_opt_cost_job(
    config: PipelineConfig,
    helpers: dict[str, Any],
    logger: logging.Logger,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    latest_cost_date = query_latest_cost_date(
        helpers,
        config.monthly_source_table,
        config.current_month_source_table,
    )
    week_windows = build_recent_week_windows(latest_cost_date)
    log_step(logger, f"[周度写库] 最新消耗日期: {latest_cost_date}")

    raw_df = helpers["read_my_data"](
        build_weekly_cost_sql(week_windows, config.monthly_source_table, config.current_month_source_table)
    )
    if raw_df.empty:
        raise ValueError("近四周消耗查询结果为空，终止执行。")

    transformed_df = transform_weekly_cost_dataframe(raw_df, week_windows)
    helpers["truncate_insert"](transformed_df, config.weekly_target_table)

    summary = build_summary_dataframe(transformed_df, "周标签", "消耗")
    result = {
        "job_name": "weekly_opt_cost",
        "source_rows": len(raw_df),
        "output_rows": len(transformed_df),
        "target_table": config.weekly_target_table,
        "latest_cost_date": latest_cost_date,
        "week_labels": [window["label"] for window in week_windows],
        "total_cost": float(transformed_df["消耗"].sum()),
        "summary_df": summary,
    }
    log_step(logger, f"[周度写库] 完成，写入 {len(transformed_df):,} 行 -> {config.weekly_target_table}")
    return transformed_df, result


def fetch_bi_source_tables(helpers: dict[str, Any], logger: logging.Logger) -> dict[str, pd.DataFrame]:
    log_step(logger, "[BI 导出] 读取数据库源表")
    latest_cost_date = query_latest_cost_date(helpers, MONTHLY_SOURCE_TABLE, CURRENT_MONTH_SOURCE_TABLE)
    year_start = date(latest_cost_date.year, 1, 1).strftime("%Y-%m-%d")

    cost_sql = f"""
SELECT
    YEAR(cost_date) AS 年,
    center_name AS 所属中心,
    my_dept_name AS 运营部门,
    CASE
        WHEN center_name = "区域中心" THEN my_dept_name
        ELSE team_name
    END AS 组别,
    opt_name AS 姓名,
    media AS 媒体,
    media_port AS 端口,
    brand AS 品牌名称,
    product AS 产品名称,
    acct_id AS 账户ID,
    cost_date AS 消耗日期,
    SUM(cost) AS 消耗
FROM (
    SELECT center_name, my_dept_name, team_name, opt_name, media, media_port, brand, product, acct_id, cost_date, cost
    FROM `{MONTHLY_SOURCE_TABLE}`
    WHERE cost_date >= '{year_start}'

    UNION ALL

    SELECT center_name, my_dept_name, team_name, opt_name, media, media_port, brand, product, acct_id, cost_date, cost
    FROM `{CURRENT_MONTH_SOURCE_TABLE}`
    WHERE cost_date >= '{year_start}'
) raw_cost
GROUP BY center_name, my_dept_name, team_name, opt_name, media, media_port, brand, product, acct_id, cost_date
"""
    weekly_sql = """
SELECT
    所属中心,
    运营部门,
    组别,
    品牌名称,
    有消耗账户数,
    周标签,
    消耗,
    天数
FROM 代运营团队人员消耗_近四周
"""
    hr_sql = """
SELECT
    年,
    月,
    所属中心,
    部门,
    组别,
    运营人效人数,
    运营项目人数
FROM 月度人力数据源
WHERE 用途 = '运营团队用'
"""

    cost_df = helpers["read_my_data"](cost_sql)
    weekly_df = helpers["read_my_data"](weekly_sql)
    hr_df = helpers["read_my_data"](hr_sql)

    cost_df["消耗日期"] = pd.to_datetime(cost_df["消耗日期"])
    cost_df = normalize_strategy_department(cost_df, "运营部门", "组别")
    hr_df = hr_df.rename(columns={"运营人效人数": "人效人数", "运营项目人数": "项目人数"}).copy()

    log_step(
        logger,
        f"[BI 导出] cost={len(cost_df):,} 行, weekly={len(weekly_df):,} 行, hr={len(hr_df):,} 行",
    )
    return {"cost": cost_df, "weekly": weekly_df, "hr": hr_df}


def get_quarter_day_count(year: int, quarter: int, latest_date: pd.Timestamp) -> int:
    quarter_start_month = (quarter - 1) * 3 + 1
    quarter_start = pd.Timestamp(f"{year}-{quarter_start_month:02d}-01")
    quarter_end_month = quarter * 3
    quarter_end = pd.Timestamp(f"{year}-{quarter_end_month:02d}-01") + pd.offsets.MonthEnd(0)
    if quarter_end > latest_date:
        quarter_end = latest_date
    if quarter_start > latest_date:
        return 0
    return (quarter_end - quarter_start).days + 1


def build_hr_rollups(hr_df: pd.DataFrame, current_year: int) -> dict[str, pd.DataFrame]:
    current_year_hr = hr_df[hr_df["年"] == current_year].copy()
    current_year_hr["季度"] = current_year_hr["月"].astype(int).apply(lambda value: (value - 1) // 3 + 1)
    current_year_hr["月份标识"] = current_year_hr["年"].astype(str) + "M" + current_year_hr["月"].astype(str).str.zfill(2)

    def aggregate_headcount(
        source_df: pd.DataFrame,
        measure_column: str,
        extra_group_columns: list[str] | None = None,
    ) -> pd.DataFrame:
        extra_group_columns = extra_group_columns or []
        result_frames: list[pd.DataFrame] = []
        group_specs = [
            (["所属中心"] + extra_group_columns, "所属中心"),
            (["所属中心", "部门"] + extra_group_columns, "部门"),
            (["所属中心", "部门", "组别"] + extra_group_columns, "组别"),
        ]

        for group_columns, team_grain in group_specs:
            aggregated = source_df.groupby(group_columns).agg(
                指标合计=(measure_column, "sum"),
                月份数=("月份标识", "nunique"),
            ).reset_index()
            aggregated = aggregated.rename(columns={"部门": "运营部门"})
            aggregated["团队粒度"] = team_grain
            if team_grain == "所属中心":
                aggregated["运营部门"] = None
                aggregated["组别"] = None
            elif team_grain == "部门":
                aggregated["组别"] = None
            result_frames.append(aggregated)

        return pd.concat(result_frames, ignore_index=True) if result_frames else pd.DataFrame()

    year_rollup = aggregate_headcount(current_year_hr, "人效人数")
    year_rollup["人效人数"] = year_rollup["指标合计"] / year_rollup["月份数"]

    quarter_frames: list[pd.DataFrame] = []
    for quarter in sorted(current_year_hr["季度"].dropna().unique()):
        quarter_df = current_year_hr[current_year_hr["季度"] == quarter]
        aggregated = aggregate_headcount(quarter_df, "人效人数", ["季度"])
        aggregated["人效人数"] = aggregated["指标合计"] / aggregated["月份数"]
        quarter_frames.append(aggregated)
    quarter_rollup = pd.concat(quarter_frames, ignore_index=True) if quarter_frames else pd.DataFrame()

    month_frames: list[pd.DataFrame] = []
    for month_key in current_year_hr["月份标识"].dropna().unique():
        month_df = current_year_hr[current_year_hr["月份标识"] == month_key]
        aggregated = aggregate_headcount(month_df, "人效人数", ["月份标识"])
        aggregated["人效人数"] = aggregated["指标合计"]
        month_frames.append(aggregated)
    month_rollup = pd.concat(month_frames, ignore_index=True) if month_frames else pd.DataFrame()

    latest_month_key = current_year_hr["月份标识"].max()
    latest_month_df = current_year_hr[current_year_hr["月份标识"] == latest_month_key]
    latest_project_rollup = aggregate_headcount(latest_month_df, "项目人数")
    latest_project_rollup["项目人数"] = latest_project_rollup["指标合计"]

    project_year_rollup = aggregate_headcount(current_year_hr, "项目人数")
    project_year_rollup["项目人数"] = project_year_rollup["指标合计"] / project_year_rollup["月份数"]

    project_quarter_frames: list[pd.DataFrame] = []
    for quarter in sorted(current_year_hr["季度"].dropna().unique()):
        quarter_df = current_year_hr[current_year_hr["季度"] == quarter]
        aggregated = aggregate_headcount(quarter_df, "项目人数", ["季度"])
        aggregated["项目人数"] = aggregated["指标合计"] / aggregated["月份数"]
        project_quarter_frames.append(aggregated)
    project_quarter_rollup = pd.concat(project_quarter_frames, ignore_index=True) if project_quarter_frames else pd.DataFrame()

    project_month_frames: list[pd.DataFrame] = []
    for month_key in current_year_hr["月份标识"].dropna().unique():
        month_df = current_year_hr[current_year_hr["月份标识"] == month_key]
        aggregated = aggregate_headcount(month_df, "项目人数", ["月份标识"])
        aggregated["项目人数"] = aggregated["指标合计"]
        project_month_frames.append(aggregated)
    project_month_rollup = pd.concat(project_month_frames, ignore_index=True) if project_month_frames else pd.DataFrame()

    return {
        "current_year_hr": current_year_hr,
        "year": year_rollup,
        "quarter": quarter_rollup,
        "month": month_rollup,
        "project_year": project_year_rollup,
        "project_quarter": project_quarter_rollup,
        "project_month": project_month_rollup,
        "latest_project": latest_project_rollup,
        "latest_month_key": latest_month_key,
    }


def lookup_k_department_total(data_df: pd.DataFrame, center_name: str, value_column: str, extra_filter: dict[str, Any]) -> float:
    total_value = 0.0
    for department_name in K_DEPARTMENT_NAMES:
        mask = (
            (data_df["所属中心"] == center_name)
            & (data_df["运营部门"] == department_name)
            & (data_df["团队粒度"] == "部门")
        )
        for column_name, expected_value in extra_filter.items():
            mask &= data_df[column_name] == expected_value
        matched_values = data_df.loc[mask, value_column]
        if not matched_values.empty:
            total_value += float(matched_values.iloc[0])
    return total_value


def lookup_productive_headcount(row: pd.Series, date_grain: str, hr_rollups: dict[str, pd.DataFrame]) -> float:
    team_grain = row["团队粒度"]
    center_name = row["所属中心"]
    department_name = row["运营部门"]
    team_name = row["组别"]

    if date_grain == "年":
        data_df = hr_rollups["year"]
        extra_filter: dict[str, Any] = {}
    elif date_grain == "季度":
        data_df = hr_rollups["quarter"]
        extra_filter = {"季度": row["季度"]}
    else:
        data_df = hr_rollups["month"]
        month_key = row["月"]
        extra_filter = {"月份标识": month_key[:4] + "M" + month_key[5:7]}

    if center_name == "整体":
        mask = data_df["团队粒度"] == "所属中心"
        for column_name, expected_value in extra_filter.items():
            mask &= data_df[column_name] == expected_value
        return float(data_df.loc[mask, "人效人数"].sum())

    if team_grain == "所属中心":
        mask = (data_df["所属中心"] == center_name) & (data_df["团队粒度"] == "所属中心")
    elif team_grain == "部门":
        if department_name == "K部门":
            return lookup_k_department_total(data_df, center_name, "人效人数", extra_filter)
        mask = (
            (data_df["所属中心"] == center_name)
            & (data_df["运营部门"] == department_name)
            & (data_df["团队粒度"] == "部门")
        )
    elif team_grain == OPTIMIZER_GRAIN:
        return 1.0
    else:
        mask = (
            (data_df["所属中心"] == center_name)
            & (data_df["运营部门"] == department_name)
            & (data_df["组别"] == team_name)
            & (data_df["团队粒度"] == "组别")
        )

    for column_name, expected_value in extra_filter.items():
        mask &= data_df[column_name] == expected_value

    matched_values = data_df.loc[mask, "人效人数"]
    return float(matched_values.iloc[0]) if not matched_values.empty else np.nan


def build_cost_aggregation(cost_df: pd.DataFrame, level_columns: list[str], team_grain: str) -> pd.DataFrame:
    if team_grain == "所属中心":
        aggregated = cost_df.groupby(level_columns + ["所属中心"]).agg(消耗=("消耗", "sum")).reset_index()
        aggregated["运营部门"] = None
        aggregated["组别"] = None
        aggregated["姓名"] = None
    elif team_grain == "部门":
        aggregated = cost_df.groupby(level_columns + ["所属中心", "运营部门"]).agg(消耗=("消耗", "sum")).reset_index()
        aggregated["组别"] = None
        aggregated["姓名"] = None
    elif team_grain == "组别":
        aggregated = cost_df.groupby(level_columns + ["所属中心", "运营部门", "组别"]).agg(消耗=("消耗", "sum")).reset_index()
        aggregated["姓名"] = None
    else:
        aggregated = cost_df.groupby(level_columns + ["所属中心", "运营部门", "组别", "姓名"]).agg(消耗=("消耗", "sum")).reset_index()
    aggregated["团队粒度"] = team_grain
    return aggregated


def iso_week_label(value: pd.Timestamp) -> str:
    iso = value.isocalendar()
    return f"{str(int(iso.year))[-2:]}W{int(iso.week):02d}"


def natural_period_end(start: pd.Timestamp, date_grain: str) -> pd.Timestamp:
    if date_grain == "年":
        return pd.Timestamp(year=start.year, month=12, day=31)
    if date_grain == "季度":
        quarter_end_month = ((start.month - 1) // 3 + 1) * 3
        return pd.Timestamp(year=start.year, month=quarter_end_month, day=1) + pd.offsets.MonthEnd(0)
    if date_grain == "月":
        return start + pd.offsets.MonthEnd(0)
    if date_grain == "周":
        return start + pd.Timedelta(days=6)
    return start


def add_period_columns(source_df: pd.DataFrame, date_grain: str, latest_cost_date: pd.Timestamp) -> pd.DataFrame:
    df = source_df.copy()
    cost_dates = pd.to_datetime(df["消耗日期"])
    df["日期粒度"] = date_grain
    if date_grain == "年":
        df["年"] = cost_dates.dt.year
        df["季度"] = None
        df["月"] = None
        df["周"] = None
        df["开始日期"] = pd.to_datetime(df["年"].astype(str) + "-01-01")
    elif date_grain == "季度":
        df["年"] = cost_dates.dt.year
        df["季度"] = cost_dates.dt.quarter
        df["月"] = None
        df["周"] = None
        start_month = (df["季度"].astype(int) - 1) * 3 + 1
        df["开始日期"] = pd.to_datetime(df["年"].astype(str) + "-" + start_month.astype(str).str.zfill(2) + "-01")
    elif date_grain == "月":
        df["年"] = cost_dates.dt.year
        df["季度"] = None
        df["月"] = cost_dates.dt.to_period("M").astype(str)
        df["周"] = None
        df["开始日期"] = cost_dates.dt.to_period("M").dt.to_timestamp()
    elif date_grain == "周":
        iso_calendar = cost_dates.dt.isocalendar()
        df["年"] = iso_calendar.year.astype(int)
        df["季度"] = None
        df["周"] = cost_dates.apply(iso_week_label)
        df["开始日期"] = cost_dates - pd.to_timedelta(cost_dates.dt.weekday, unit="D")
        df["月"] = df["开始日期"].dt.to_period("M").astype(str)
    elif date_grain == "日":
        df["年"] = cost_dates.dt.year
        df["季度"] = None
        df["月"] = cost_dates.dt.to_period("M").astype(str)
        df["周"] = cost_dates.apply(iso_week_label)
        df["开始日期"] = cost_dates.dt.normalize()
    else:
        raise ValueError(f"不支持的日期粒度: {date_grain}")

    df["结束日期"] = df["开始日期"].apply(lambda value: min(natural_period_end(value, date_grain), latest_cost_date))
    df["天数"] = (df["结束日期"] - df["开始日期"]).dt.days + 1
    return df


def prepare_count_keys(cost_df: pd.DataFrame) -> pd.DataFrame:
    df = cost_df.copy()
    media_key = df["媒体"].fillna("").astype(str).str.strip()
    account_id = df["账户ID"].fillna("").astype(str).str.strip()
    product_name = df["产品名称"].fillna("").astype(str).str.strip()
    brand_name = df["品牌名称"].fillna("").astype(str).str.strip()
    df["_账户唯一键"] = np.where(account_id != "", media_key + "|" + account_id, np.nan)
    df["_产品唯一键"] = np.where(product_name != "", media_key + "|" + product_name, np.nan)
    df["_品牌唯一键"] = np.where(brand_name != "", brand_name, np.nan)
    return df


def effective_month_count(group_df: pd.DataFrame, key_column: str) -> float:
    valid_df = group_df.dropna(subset=[key_column])
    if valid_df.empty:
        return 0.0

    active_days = valid_df.groupby(key_column)["消耗日期"].nunique()

    def weight(day_count: int) -> float:
        if day_count < 7:
            return 0.0
        if day_count < 14:
            return 0.5
        return 1.0

    return float(active_days.map(weight).sum())


def count_group_metrics(source_df: pd.DataFrame, group_columns: list[str], mode: str) -> pd.DataFrame:
    grouped = source_df.groupby(group_columns, dropna=False)
    if mode == "month":
        return grouped.apply(
            lambda frame: pd.Series(
                {
                    "品牌数": effective_month_count(frame, "_品牌唯一键"),
                    "产品数": effective_month_count(frame, "_产品唯一键"),
                    "账户数": effective_month_count(frame, "_账户唯一键"),
                }
            )
        ).reset_index()

    return grouped.agg(
        品牌数=("_品牌唯一键", "nunique"),
        产品数=("_产品唯一键", "nunique"),
        账户数=("_账户唯一键", "nunique"),
    ).reset_index()


def build_team_period_source(
    period_df: pd.DataFrame,
    period_columns: list[str],
    team_grain: str,
    source_label: str = "standard",
) -> tuple[pd.DataFrame, list[str]]:
    if source_label == "overall":
        source_df = period_df.copy()
        org_columns: list[str] = []
    elif source_label == "k_department":
        source_df = period_df[
            (period_df["所属中心"] == "运营中心") & (period_df["运营部门"].isin(K_DEPARTMENT_NAMES))
        ].copy()
        org_columns = ["所属中心"]
    else:
        source_df = period_df.copy()
        if team_grain == "所属中心":
            org_columns = ["所属中心"]
        elif team_grain == "部门":
            org_columns = ["所属中心", "运营部门"]
        elif team_grain == "组别":
            org_columns = ["所属中心", "运营部门", "组别"]
        else:
            org_columns = ["所属中心", "运营部门", "组别", "姓名"]

    return source_df, org_columns


def apply_team_defaults(df: pd.DataFrame, team_grain: str, source_label: str) -> pd.DataFrame:
    result_df = df.copy()
    if source_label == "overall":
        result_df["所属中心"] = "整体"
        result_df["运营部门"] = "整体"
        result_df["组别"] = None
        result_df["姓名"] = None
        result_df["团队粒度"] = "所属中心"
    elif source_label == "k_department":
        result_df["运营部门"] = "K部门"
        result_df["组别"] = None
        result_df["姓名"] = None
        result_df["团队粒度"] = "部门"
    else:
        result_df["团队粒度"] = team_grain
        if team_grain == "所属中心":
            result_df["运营部门"] = None
            result_df["组别"] = None
            result_df["姓名"] = None
        elif team_grain == "部门":
            result_df["组别"] = None
            result_df["姓名"] = None
        elif team_grain == "组别":
            result_df["姓名"] = None
    return result_df


def build_team_rows_for_period(
    period_df: pd.DataFrame,
    period_columns: list[str],
    date_grain: str,
    team_grain: str,
    count_mode: str,
    source_label: str = "standard",
) -> pd.DataFrame:
    source_df, org_columns = build_team_period_source(period_df, period_columns, team_grain, source_label)
    if source_df.empty:
        return pd.DataFrame()
    group_columns = period_columns + org_columns
    cost_df = source_df.groupby(group_columns, dropna=False).agg(
        消耗=("消耗", "sum"),
        开始日期=("开始日期", "first"),
        结束日期=("结束日期", "first"),
        天数=("天数", "first"),
    ).reset_index()
    metric_df = count_group_metrics(source_df, group_columns, count_mode)
    merged_df = cost_df.merge(metric_df, how="left", on=group_columns)
    merged_df["日期粒度"] = date_grain
    return apply_team_defaults(merged_df, team_grain, source_label)


def lookup_project_headcount_for_period(row: pd.Series, date_grain: str, hr_rollups: dict[str, pd.DataFrame]) -> float:
    if row["团队粒度"] == OPTIMIZER_GRAIN:
        return 1.0

    if date_grain == "年":
        data_df = hr_rollups["project_year"]
        extra_filter: dict[str, Any] = {}
    elif date_grain == "季度":
        data_df = hr_rollups["project_quarter"]
        extra_filter = {"季度": row["季度"]}
    else:
        data_df = hr_rollups["project_month"]
        month_key = row["月"]
        extra_filter = {"月份标识": month_key[:4] + "M" + month_key[5:7]} if pd.notna(month_key) else {}

    return lookup_period_headcount(row, data_df, "项目人数", extra_filter)


def lookup_period_headcount(row: pd.Series, data_df: pd.DataFrame, value_column: str, extra_filter: dict[str, Any]) -> float:
    if data_df.empty:
        return np.nan

    team_grain = row["团队粒度"]
    center_name = row["所属中心"]
    department_name = row["运营部门"]
    team_name = row["组别"]

    if center_name == "整体":
        mask = data_df["团队粒度"] == "所属中心"
    elif team_grain == "所属中心":
        mask = (data_df["所属中心"] == center_name) & (data_df["团队粒度"] == "所属中心")
    elif team_grain == "部门":
        if department_name == "K部门":
            return lookup_k_department_total(data_df, center_name, value_column, extra_filter)
        mask = (
            (data_df["所属中心"] == center_name)
            & (data_df["运营部门"] == department_name)
            & (data_df["团队粒度"] == "部门")
        )
    else:
        mask = (
            (data_df["所属中心"] == center_name)
            & (data_df["运营部门"] == department_name)
            & (data_df["组别"] == team_name)
            & (data_df["团队粒度"] == "组别")
        )

    for column_name, expected_value in extra_filter.items():
        mask &= data_df[column_name] == expected_value

    matched_values = data_df.loc[mask, value_column]
    if matched_values.empty:
        return np.nan
    return float(matched_values.sum()) if center_name == "整体" else float(matched_values.iloc[0])


def enrich_team_dimension_metrics(team_df: pd.DataFrame, date_grain: str, hr_rollups: dict[str, pd.DataFrame]) -> pd.DataFrame:
    result_df = team_df.copy()
    result_df["日均消耗"] = result_df["消耗"] / result_df["天数"]
    result_df["人效人数"] = result_df.apply(lambda row: lookup_productive_headcount(row, date_grain, hr_rollups), axis=1)
    result_df["人均日耗"] = np.where(result_df["人效人数"].fillna(0) != 0, result_df["日均消耗"] / result_df["人效人数"], np.nan)
    result_df["项目人数"] = result_df.apply(lambda row: lookup_project_headcount_for_period(row, date_grain, hr_rollups), axis=1)
    result_df["人均品牌"] = np.where(result_df["项目人数"].fillna(0) != 0, result_df["品牌数"] / result_df["项目人数"], np.nan)
    result_df["人均账户"] = np.where(result_df["项目人数"].fillna(0) != 0, result_df["账户数"] / result_df["项目人数"], np.nan)
    result_df["人均项目"] = np.where(result_df["项目人数"].fillna(0) != 0, result_df["产品数"] / result_df["项目人数"], np.nan)
    result_df["户均消耗"] = np.where(result_df["账户数"].fillna(0) != 0, result_df["日均消耗"] / result_df["账户数"], np.nan)
    return result_df


def build_team_dimension_table(cost_df: pd.DataFrame, max_cost_date: pd.Timestamp, hr_rollups: dict[str, pd.DataFrame]) -> pd.DataFrame:
    keyed_cost_df = prepare_count_keys(cost_df)
    period_specs = [
        ("年", ["年"], "distinct"),
        ("季度", ["年", "季度"], "distinct"),
        ("月", ["年", "月"], "month"),
        ("周", ["年", "月", "周"], "distinct"),
    ]
    team_grains = ["所属中心", "部门", "组别", OPTIMIZER_GRAIN]
    rows: list[pd.DataFrame] = []

    month_rows_by_grain: dict[tuple[str, str], pd.DataFrame] = {}
    for date_grain, period_columns, count_mode in period_specs:
        period_df = add_period_columns(keyed_cost_df, date_grain, max_cost_date)
        for team_grain in team_grains:
            if date_grain in ["年", "季度"]:
                continue
            frame = build_team_rows_for_period(period_df, period_columns, date_grain, team_grain, count_mode)
            if not frame.empty:
                month_rows_by_grain[(date_grain, team_grain)] = frame
                rows.append(enrich_team_dimension_metrics(frame, date_grain, hr_rollups))
        for source_label in ["k_department", "overall"]:
            if date_grain in ["年", "季度"]:
                continue
            frame = build_team_rows_for_period(period_df, period_columns, date_grain, "部门", count_mode, source_label)
            if not frame.empty:
                month_rows_by_grain[(date_grain, source_label)] = frame
                rows.append(enrich_team_dimension_metrics(frame, date_grain, hr_rollups))

    month_metric_rows = [frame for (grain, _), frame in month_rows_by_grain.items() if grain == "月"]
    month_metrics_df = pd.concat(month_metric_rows, ignore_index=True) if month_metric_rows else pd.DataFrame()
    if not month_metrics_df.empty:
        month_metrics_df["季度"] = pd.to_datetime(month_metrics_df["月"] + "-01").dt.quarter

    for date_grain, period_columns, _ in [("年", ["年"], "distinct"), ("季度", ["年", "季度"], "distinct")]:
        period_df = add_period_columns(keyed_cost_df, date_grain, max_cost_date)
        for team_grain in team_grains:
            frame = build_team_rows_for_period(period_df, period_columns, date_grain, team_grain, "distinct")
            if not frame.empty and not month_metrics_df.empty:
                org_columns = ["所属中心"] if team_grain == "所属中心" else ["所属中心", "运营部门"] if team_grain == "部门" else ["所属中心", "运营部门", "组别"] if team_grain == "组别" else ["所属中心", "运营部门", "组别", "姓名"]
                metric_columns = period_columns + org_columns
                monthly_avg = month_metrics_df[month_metrics_df["团队粒度"] == team_grain].groupby(metric_columns, dropna=False)[["品牌数", "产品数", "账户数"]].mean().reset_index()
                frame = frame.drop(columns=["品牌数", "产品数", "账户数"]).merge(monthly_avg, how="left", on=metric_columns)
            rows.append(enrich_team_dimension_metrics(frame, date_grain, hr_rollups))
        for source_label in ["k_department", "overall"]:
            frame = build_team_rows_for_period(period_df, period_columns, date_grain, "部门", "distinct", source_label)
            if not frame.empty and not month_metrics_df.empty:
                if source_label == "k_department":
                    monthly_source = month_metrics_df[(month_metrics_df["团队粒度"] == "部门") & (month_metrics_df["运营部门"] == "K部门")]
                    metric_columns = period_columns + ["所属中心", "运营部门"]
                else:
                    monthly_source = month_metrics_df[(month_metrics_df["团队粒度"] == "所属中心") & (month_metrics_df["所属中心"] == "整体")]
                    metric_columns = period_columns + ["所属中心"]
                monthly_avg = monthly_source.groupby(metric_columns, dropna=False)[["品牌数", "产品数", "账户数"]].mean().reset_index()
                frame = frame.drop(columns=["品牌数", "产品数", "账户数"]).merge(monthly_avg, how="left", on=metric_columns)
            rows.append(enrich_team_dimension_metrics(frame, date_grain, hr_rollups))

    output_columns = [
        "日期粒度", "年", "季度", "月", "周", "开始日期", "结束日期", "天数",
        "团队粒度", "所属中心", "运营部门", "组别", "姓名",
        "消耗", "日均消耗", "人效人数", "人均日耗",
        "项目人数", "品牌数", "产品数", "账户数", "人均品牌", "人均账户", "人均项目", "户均消耗",
    ]
    table_df = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=output_columns)
    for column in output_columns:
        if column not in table_df.columns:
            table_df[column] = None
    return table_df[output_columns].sort_values(
        ["日期粒度", "年", "季度", "月", "周", "团队粒度", "所属中心", "运营部门", "组别", "姓名"],
        na_position="last",
    ).reset_index(drop=True)


def build_period_cost_table(cost_df: pd.DataFrame, max_cost_date: pd.Timestamp, hr_rollups: dict[str, pd.DataFrame]) -> pd.DataFrame:
    current_year = max_cost_date.year
    cost_df = cost_df.copy()
    cost_df["季度"] = cost_df["消耗日期"].dt.quarter
    cost_df["月"] = cost_df["消耗日期"].dt.to_period("M").astype(str)
    year_day_count = (max_cost_date - pd.Timestamp(f"{current_year}-01-01")).days + 1
    month_day_count_map = cost_df.groupby(["年", "月"])["消耗日期"].nunique().to_dict()

    year_cost = pd.concat(
        [
            build_cost_aggregation(cost_df, ["年"], "所属中心"),
            build_cost_aggregation(cost_df, ["年"], "部门"),
            build_cost_aggregation(cost_df, ["年"], "组别"),
            build_cost_aggregation(cost_df, ["年"], OPTIMIZER_GRAIN),
        ],
        ignore_index=True,
    )
    year_cost["日期粒度"] = "年"
    year_cost["天数"] = year_day_count
    year_cost["日均消耗"] = year_cost["消耗"] / year_day_count
    year_cost["人效人数"] = year_cost.apply(lambda row: lookup_productive_headcount(row, "年", hr_rollups), axis=1)
    year_cost["人均日耗"] = np.where(year_cost["人效人数"].fillna(0) != 0, year_cost["日均消耗"] / year_cost["人效人数"], np.nan)
    year_cost["季度"] = None
    year_cost["月"] = None

    quarter_cost = pd.concat(
        [
            build_cost_aggregation(cost_df, ["年", "季度"], "所属中心"),
            build_cost_aggregation(cost_df, ["年", "季度"], "部门"),
            build_cost_aggregation(cost_df, ["年", "季度"], "组别"),
            build_cost_aggregation(cost_df, ["年", "季度"], OPTIMIZER_GRAIN),
        ],
        ignore_index=True,
    )
    quarter_cost["日期粒度"] = "季度"
    quarter_cost["天数"] = quarter_cost.apply(
        lambda row: get_quarter_day_count(int(row["年"]), int(row["季度"]), max_cost_date),
        axis=1,
    )
    quarter_cost["日均消耗"] = quarter_cost["消耗"] / quarter_cost["天数"]
    quarter_cost["人效人数"] = quarter_cost.apply(lambda row: lookup_productive_headcount(row, "季度", hr_rollups), axis=1)
    quarter_cost["人均日耗"] = np.where(quarter_cost["人效人数"].fillna(0) != 0, quarter_cost["日均消耗"] / quarter_cost["人效人数"], np.nan)
    quarter_cost["月"] = None

    month_cost = pd.concat(
        [
            build_cost_aggregation(cost_df, ["年", "月"], "所属中心"),
            build_cost_aggregation(cost_df, ["年", "月"], "部门"),
            build_cost_aggregation(cost_df, ["年", "月"], "组别"),
            build_cost_aggregation(cost_df, ["年", "月"], OPTIMIZER_GRAIN),
        ],
        ignore_index=True,
    )
    month_cost["日期粒度"] = "月"
    month_cost["季度"] = None
    month_cost["天数"] = month_cost.apply(
        lambda row: month_day_count_map.get((row["年"], row["月"]), 30),
        axis=1,
    )
    month_cost["日均消耗"] = month_cost["消耗"] / month_cost["天数"]
    month_cost["人效人数"] = month_cost.apply(lambda row: lookup_productive_headcount(row, "月", hr_rollups), axis=1)
    month_cost["人均日耗"] = np.where(month_cost["人效人数"].fillna(0) != 0, month_cost["日均消耗"] / month_cost["人效人数"], np.nan)

    base_table = pd.concat(
        [
            year_cost[["日期粒度", "年", "季度", "月", "所属中心", "运营部门", "组别", "姓名", "团队粒度", "消耗", "日均消耗", "人效人数", "人均日耗"]],
            quarter_cost[["日期粒度", "年", "季度", "月", "所属中心", "运营部门", "组别", "姓名", "团队粒度", "消耗", "日均消耗", "人效人数", "人均日耗"]],
            month_cost[["日期粒度", "年", "季度", "月", "所属中心", "运营部门", "组别", "姓名", "团队粒度", "消耗", "日均消耗", "人效人数", "人均日耗"]],
        ],
        ignore_index=True,
    )

    operation_k_df = cost_df[
        (cost_df["所属中心"] == "运营中心") & (cost_df["运营部门"].isin(K_DEPARTMENT_NAMES))
    ].copy()
    if not operation_k_df.empty:
        k_rows: list[pd.DataFrame] = []
        for date_grain, group_columns in [("年", ["年"]), ("季度", ["年", "季度"]), ("月", ["年", "月"])]:
            grouped = operation_k_df.groupby(group_columns + ["所属中心"]).agg(消耗=("消耗", "sum")).reset_index()
            grouped["运营部门"] = "K部门"
            grouped["组别"] = None
            grouped["姓名"] = None
            grouped["团队粒度"] = "部门"
            grouped["日期粒度"] = date_grain
            if date_grain == "年":
                grouped["季度"] = None
                grouped["月"] = None
                grouped["天数"] = year_day_count
            elif date_grain == "季度":
                grouped["月"] = None
                grouped["天数"] = grouped.apply(
                    lambda row: get_quarter_day_count(int(row["年"]), int(row["季度"]), max_cost_date),
                    axis=1,
                )
            else:
                grouped["季度"] = None
                grouped["天数"] = grouped.apply(
                    lambda row: month_day_count_map.get((row["年"], row["月"]), 30),
                    axis=1,
                )
            grouped["日均消耗"] = grouped["消耗"] / grouped["天数"]
            grouped["人效人数"] = grouped.apply(lambda row: lookup_productive_headcount(row, date_grain, hr_rollups), axis=1)
            grouped["人均日耗"] = np.where(grouped["人效人数"].fillna(0) != 0, grouped["日均消耗"] / grouped["人效人数"], np.nan)
            k_rows.append(
                grouped[["日期粒度", "年", "季度", "月", "所属中心", "运营部门", "组别", "姓名", "团队粒度", "消耗", "日均消耗", "人效人数", "人均日耗"]]
            )
        base_table = pd.concat([base_table] + k_rows, ignore_index=True)

    overall_rows: list[dict[str, Any]] = []
    overall_year_headcount = hr_rollups["year"][hr_rollups["year"]["团队粒度"] == "所属中心"]["人效人数"].sum()
    total_cost = float(cost_df["消耗"].sum())
    overall_rows.append(
        {
            "日期粒度": "年",
            "年": current_year,
            "季度": None,
            "月": None,
            "所属中心": "整体",
            "运营部门": "整体",
            "组别": None,
            "姓名": None,
            "团队粒度": "所属中心",
            "消耗": total_cost,
            "日均消耗": total_cost / year_day_count,
            "人效人数": overall_year_headcount,
            "人均日耗": (total_cost / year_day_count) / overall_year_headcount if overall_year_headcount else np.nan,
        }
    )

    for (year_value, quarter_value), group_df in cost_df.groupby(["年", "季度"]):
        day_count = get_quarter_day_count(int(year_value), int(quarter_value), max_cost_date)
        quarter_headcount = hr_rollups["quarter"][
            (hr_rollups["quarter"]["团队粒度"] == "所属中心")
            & (hr_rollups["quarter"]["季度"] == quarter_value)
        ]["人效人数"].sum()
        period_cost = float(group_df["消耗"].sum())
        overall_rows.append(
            {
                "日期粒度": "季度",
                "年": year_value,
                "季度": quarter_value,
                "月": None,
                "所属中心": "整体",
                "运营部门": "整体",
                "组别": None,
                "姓名": None,
                "团队粒度": "所属中心",
                "消耗": period_cost,
                "日均消耗": period_cost / day_count,
                "人效人数": quarter_headcount,
                "人均日耗": (period_cost / day_count) / quarter_headcount if quarter_headcount else np.nan,
            }
        )

    for (year_value, month_value), group_df in cost_df.groupby(["年", "月"]):
        day_count = month_day_count_map.get((year_value, month_value), 30)
        month_key = month_value[:4] + "M" + month_value[5:7]
        month_headcount = hr_rollups["month"][
            (hr_rollups["month"]["团队粒度"] == "所属中心")
            & (hr_rollups["month"]["月份标识"] == month_key)
        ]["人效人数"].sum()
        period_cost = float(group_df["消耗"].sum())
        overall_rows.append(
            {
                "日期粒度": "月",
                "年": year_value,
                "季度": None,
                "月": month_value,
                "所属中心": "整体",
                "运营部门": "整体",
                "组别": None,
                "姓名": None,
                "团队粒度": "所属中心",
                "消耗": period_cost,
                "日均消耗": period_cost / day_count,
                "人效人数": month_headcount,
                "人均日耗": (period_cost / day_count) / month_headcount if month_headcount else np.nan,
            }
        )

    base_table = pd.concat([base_table, pd.DataFrame(overall_rows)], ignore_index=True)
    base_table = base_table.sort_values(
        ["日期粒度", "年", "季度", "月", "团队粒度", "所属中心", "运营部门", "组别", "姓名"],
        na_position="last",
    ).reset_index(drop=True)
    return base_table


def lookup_project_headcount(row: pd.Series, latest_project_rollup: pd.DataFrame) -> float:
    team_grain = row["团队粒度"]
    center_name = row["所属中心"]
    department_name = row["运营部门"]
    team_name = row["组别"]

    if team_grain == "所属中心":
        mask = (latest_project_rollup["所属中心"] == center_name) & (latest_project_rollup["团队粒度"] == "所属中心")
    elif team_grain == "部门":
        if department_name == "K部门":
            return lookup_k_department_total(latest_project_rollup, center_name, "项目人数", {})
        mask = (
            (latest_project_rollup["所属中心"] == center_name)
            & (latest_project_rollup["运营部门"] == department_name)
            & (latest_project_rollup["团队粒度"] == "部门")
        )
    else:
        mask = (
            (latest_project_rollup["所属中心"] == center_name)
            & (latest_project_rollup["运营部门"] == department_name)
            & (latest_project_rollup["组别"] == team_name)
            & (latest_project_rollup["团队粒度"] == "组别")
        )

    matched_values = latest_project_rollup.loc[mask, "项目人数"]
    return float(matched_values.iloc[0]) if not matched_values.empty else np.nan


def build_brand_account_table(weekly_df: pd.DataFrame, latest_project_rollup: pd.DataFrame) -> pd.DataFrame:
    brand_account_df = pd.concat(
        [
            weekly_df.groupby(["周标签", "所属中心"]).agg(品牌数=("品牌名称", "nunique"), 账户数=("有消耗账户数", "sum"), 消耗=("消耗", "sum"), 天数=("天数", "max")).reset_index().assign(运营部门=None, 组别=None, 团队粒度="所属中心"),
            weekly_df.groupby(["周标签", "所属中心", "运营部门"]).agg(品牌数=("品牌名称", "nunique"), 账户数=("有消耗账户数", "sum"), 消耗=("消耗", "sum"), 天数=("天数", "max")).reset_index().assign(组别=None, 团队粒度="部门"),
            weekly_df.groupby(["周标签", "所属中心", "运营部门", "组别"]).agg(品牌数=("品牌名称", "nunique"), 账户数=("有消耗账户数", "sum"), 消耗=("消耗", "sum"), 天数=("天数", "max")).reset_index().assign(团队粒度="组别"),
        ],
        ignore_index=True,
    )

    project_headcounts = brand_account_df.apply(lambda row: lookup_project_headcount(row, latest_project_rollup), axis=1)
    brand_account_df["人均品牌"] = np.where(project_headcounts.fillna(0) != 0, brand_account_df["品牌数"] / project_headcounts, np.nan)
    brand_account_df["人均账户"] = np.where(project_headcounts.fillna(0) != 0, brand_account_df["账户数"] / project_headcounts, np.nan)
    brand_account_df["户均日耗"] = np.where(
        (brand_account_df["账户数"].fillna(0) != 0) & (brand_account_df["天数"].fillna(0) != 0),
        brand_account_df["消耗"] / brand_account_df["账户数"] / brand_account_df["天数"],
        np.nan,
    )

    k_weekly_df = weekly_df[
        (weekly_df["所属中心"] == "运营中心") & (weekly_df["运营部门"].isin(K_DEPARTMENT_NAMES))
    ].copy()
    if not k_weekly_df.empty:
        k_grouped = (
            k_weekly_df.groupby(["周标签", "所属中心"])
            .agg(品牌数=("品牌名称", "nunique"), 账户数=("有消耗账户数", "sum"), 消耗=("消耗", "sum"), 天数=("天数", "max"))
            .reset_index()
        )
        k_grouped["运营部门"] = "K部门"
        k_grouped["组别"] = None
        k_grouped["团队粒度"] = "部门"
        k_project_headcount = lookup_k_department_total(latest_project_rollup, "运营中心", "项目人数", {})
        k_grouped["人均品牌"] = k_grouped["品牌数"] / k_project_headcount if k_project_headcount else np.nan
        k_grouped["人均账户"] = k_grouped["账户数"] / k_project_headcount if k_project_headcount else np.nan
        k_grouped["户均日耗"] = k_grouped["消耗"] / k_grouped["账户数"] / k_grouped["天数"]
        brand_account_df = pd.concat([brand_account_df, k_grouped], ignore_index=True)

    overall_project_headcount = latest_project_rollup[latest_project_rollup["团队粒度"] == "所属中心"]["项目人数"].sum()
    overall_row = (
        weekly_df.groupby(["周标签"])
        .agg(品牌数=("品牌名称", "nunique"), 账户数=("有消耗账户数", "sum"), 消耗=("消耗", "sum"), 天数=("天数", "max"))
        .reset_index()
    )
    overall_row["所属中心"] = "整体"
    overall_row["运营部门"] = "整体"
    overall_row["组别"] = None
    overall_row["团队粒度"] = "所属中心"
    overall_row["人均品牌"] = overall_row["品牌数"] / overall_project_headcount if overall_project_headcount else np.nan
    overall_row["人均账户"] = overall_row["账户数"] / overall_project_headcount if overall_project_headcount else np.nan
    overall_row["户均日耗"] = np.where(
        (overall_row["账户数"].fillna(0) != 0) & (overall_row["天数"].fillna(0) != 0),
        overall_row["消耗"] / overall_row["账户数"] / overall_row["天数"],
        np.nan,
    )
    brand_account_df = pd.concat([brand_account_df, overall_row], ignore_index=True)

    return brand_account_df.sort_values(["周标签", "团队粒度", "所属中心", "运营部门", "组别"], na_position="last").reset_index(drop=True)


def build_legacy_brand_account_table(team_dimension_df: pd.DataFrame) -> pd.DataFrame:
    weekly_df = team_dimension_df[
        (team_dimension_df["日期粒度"] == "周")
        & (team_dimension_df["团队粒度"].isin(["所属中心", "部门", "组别"]))
    ].copy()
    if weekly_df.empty:
        return pd.DataFrame(
            columns=["周标签", "所属中心", "品牌数", "账户数", "消耗", "天数", "运营部门", "组别", "团队粒度", "人均品牌", "人均账户", "户均日耗"]
        )
    weekly_df["周标签"] = weekly_df["周"]
    return weekly_df[
        ["周标签", "所属中心", "品牌数", "账户数", "消耗", "天数", "运营部门", "组别", "团队粒度", "人均品牌", "人均账户", "户均消耗"]
    ].rename(columns={"户均消耗": "户均日耗"}).sort_values(
        ["周标签", "团队粒度", "所属中心", "运营部门", "组别"],
        na_position="last",
    ).reset_index(drop=True)


def build_media_project_cost_table(cost_df: pd.DataFrame) -> pd.DataFrame:
    media_df = prepare_count_keys(cost_df)
    latest_cost_date = media_df["消耗日期"].max()
    latest_month_period = latest_cost_date.to_period("M")
    recent_month_keys = {
        (latest_month_period - 1).strftime("%Y-%m"),
        latest_month_period.strftime("%Y-%m"),
    }

    def aggregate_project_dimension(source_df: pd.DataFrame, date_grain: str, period_columns: list[str]) -> pd.DataFrame:
        period_df = add_period_columns(source_df, date_grain, latest_cost_date)
        filtered_df = period_df
        if date_grain == "日":
            filtered_df = period_df[
                (period_df["所属中心"] == "运营中心")
                | ((period_df["所属中心"] != "运营中心") & period_df["月"].isin(recent_month_keys))
            ]
        group_columns = period_columns + ["媒体", "端口", "所属中心", "运营部门", "组别", "品牌名称", "产品名称"]
        aggregated = filtered_df.groupby(group_columns, dropna=False).agg(
            消耗=("消耗", "sum"),
            账户数=("_账户唯一键", "nunique"),
            开始日期=("开始日期", "first"),
            结束日期=("结束日期", "first"),
            天数=("天数", "first"),
        ).reset_index()
        aggregated["日期粒度"] = date_grain
        if date_grain != "日":
            aggregated["消耗日期"] = pd.NaT
        return aggregated

    frames = [
        aggregate_project_dimension(media_df, "日", ["年", "月", "周", "消耗日期"]),
        aggregate_project_dimension(media_df, "周", ["年", "月", "周"]),
        aggregate_project_dimension(media_df, "月", ["年", "月"]),
        aggregate_project_dimension(media_df, "季度", ["年", "季度"]),
        aggregate_project_dimension(media_df, "年", ["年"]),
    ]

    k_media_df = media_df[
        (media_df["所属中心"] == "运营中心") & (media_df["运营部门"].isin(K_DEPARTMENT_NAMES))
    ].copy()
    if not k_media_df.empty:
        for date_grain, period_columns in [
            ("日", ["年", "月", "周", "消耗日期"]),
            ("周", ["年", "月", "周"]),
            ("月", ["年", "月"]),
            ("季度", ["年", "季度"]),
            ("年", ["年"]),
        ]:
            aggregated = aggregate_project_dimension(k_media_df, date_grain, period_columns)
            aggregated["运营部门"] = "K部门"
            aggregated["组别"] = None
            frames.append(aggregated)

    table_df = pd.concat(frames, ignore_index=True)
    output_columns = [
        "日期粒度", "年", "季度", "月", "周", "消耗日期", "开始日期", "结束日期", "天数",
        "媒体", "端口", "所属中心", "运营部门", "组别", "品牌名称", "产品名称", "消耗", "账户数",
    ]
    for column in output_columns:
        if column not in table_df.columns:
            table_df[column] = None
    return table_df[output_columns].sort_values(
        ["日期粒度", "年", "季度", "月", "周", "媒体", "端口", "所属中心", "运营部门", "组别", "品牌名称", "产品名称"],
        na_position="last",
    ).reset_index(drop=True)


def normalize_lookup_value(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def load_port_conversion_table(output_path: Path) -> pd.DataFrame:
    if not output_path.exists():
        raise FileNotFoundError(f"未找到 BI 报表文件，无法读取端口转换 sheet: {output_path}")

    conversion_df = pd.read_excel(output_path, sheet_name="端口转换", engine="openpyxl")
    required_columns = {"媒体", "端口", "转换后"}
    missing_columns = required_columns - set(conversion_df.columns)
    if missing_columns:
        raise ValueError(f"端口转换 sheet 缺少必要列: {', '.join(sorted(missing_columns))}")

    conversion_df = conversion_df[["媒体", "端口", "转换后"]].copy()
    conversion_df["_媒体匹配键"] = conversion_df["媒体"].map(normalize_lookup_value)
    conversion_df["_端口匹配键"] = conversion_df["端口"].map(normalize_lookup_value)
    conversion_df = conversion_df[(conversion_df["_媒体匹配键"] != "") & (conversion_df["_端口匹配键"] != "")]
    conversion_df = conversion_df.drop_duplicates(subset=["_媒体匹配键", "_端口匹配键", "转换后"])

    conflict_mask = conversion_df.duplicated(subset=["_媒体匹配键", "_端口匹配键"], keep=False)
    if conflict_mask.any():
        conflict_rows = conversion_df.loc[conflict_mask, ["媒体", "端口", "转换后"]].head(20)
        conflict_text = "；".join(
            f"媒体={row['媒体']}, 端口={row['端口']}, 转换后={row['转换后']}"
            for _, row in conflict_rows.iterrows()
        )
        raise ValueError(f"端口转换 sheet 存在同一媒体+端口对应多个转换后，请先处理: {conflict_text}")

    return conversion_df


def apply_port_conversion(
    source_df: pd.DataFrame,
    conversion_df: pd.DataFrame,
    logger: logging.Logger,
    table_label: str,
) -> pd.DataFrame:
    converted_media = sorted(conversion_df["_媒体匹配键"].dropna().unique())
    log_step(logger, f"[BI 导出][{table_label}] 端口转换媒体: " + (", ".join(converted_media) if converted_media else "无"))

    result_df = source_df.copy()
    result_df["_媒体匹配键"] = result_df["媒体"].map(normalize_lookup_value)
    result_df["_端口匹配键"] = result_df["端口"].map(normalize_lookup_value)
    result_df = result_df.merge(
        conversion_df[["_媒体匹配键", "_端口匹配键", "转换后"]],
        how="left",
        on=["_媒体匹配键", "_端口匹配键"],
    )
    result_df = result_df.rename(columns={"转换后": "归类端口"})

    matched_media = sorted(result_df.loc[result_df["归类端口"].notna(), "_媒体匹配键"].dropna().unique())
    log_step(logger, f"[BI 导出][{table_label}] 已匹配归类端口媒体: " + (", ".join(matched_media) if matched_media else "无"))

    converted_media_set = set(converted_media)
    unmatched_df = result_df[
        result_df["_媒体匹配键"].isin(converted_media_set) & result_df["归类端口"].isna()
    ][["媒体", "端口"]].drop_duplicates()
    if not unmatched_df.empty:
        unmatched_text = "；".join(
            f"媒体={row['媒体']}, 端口={row['端口']}"
            for _, row in unmatched_df.head(50).iterrows()
        )
        more_text = f"；另有 {len(unmatched_df) - 50} 个未展示" if len(unmatched_df) > 50 else ""
        logger.warning(f"[BI 导出][{table_label}][提醒] 以下端口在端口转换表中未匹配到归类端口: {unmatched_text}{more_text}")

    result_df = result_df.drop(columns=["_媒体匹配键", "_端口匹配键"])
    output_columns = list(source_df.columns)
    port_column_index = output_columns.index("端口") + 1
    output_columns.insert(port_column_index, "归类端口")
    return result_df[output_columns]


def build_port_media_cost_table(
    helpers: dict[str, Any],
    logger: logging.Logger,
    conversion_df: pd.DataFrame,
) -> pd.DataFrame:
    log_step(logger, f"[BI 导出] 读取 {PORT_MEDIA_SOURCE_TABLE} 生成分端口媒体消耗")
    port_media_sql = f"""
SELECT
    media AS 媒体,
    media_port AS 端口,
    cost_date AS 消耗日期,
    SUM(cost) AS 消耗
FROM `{PORT_MEDIA_SOURCE_TABLE}`
WHERE cost_date IS NOT NULL
  AND YEAR(cost_date) = (
      SELECT YEAR(MAX(cost_date))
      FROM `{PORT_MEDIA_SOURCE_TABLE}`
      WHERE cost_date IS NOT NULL
  )
GROUP BY media, media_port, cost_date
ORDER BY cost_date, media, media_port
"""
    port_media_df = helpers["read_my_data"](port_media_sql)
    if port_media_df.empty:
        raise ValueError(f"{PORT_MEDIA_SOURCE_TABLE} 当年端口媒体消耗查询结果为空，终止 BI 导出。")

    port_media_df["消耗日期"] = pd.to_datetime(port_media_df["消耗日期"])
    port_media_df["消耗"] = pd.to_numeric(port_media_df["消耗"], errors="coerce").fillna(0)
    log_step(
        logger,
        f"[BI 导出] 分端口媒体消耗={len(port_media_df):,} 行, 日期范围: "
        f"{port_media_df['消耗日期'].min()} ~ {port_media_df['消耗日期'].max()}",
    )
    return apply_port_conversion(
        port_media_df[["媒体", "端口", "消耗日期", "消耗"]],
        conversion_df,
        logger,
        "分端口媒体消耗",
    )


def build_bi_summary_sheet(
    team_cost_df: pd.DataFrame,
    media_cost_df: pd.DataFrame,
    port_media_df: pd.DataFrame,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"表名": "团队维度", "行数": len(team_cost_df), "关键值合计": float(team_cost_df["消耗"].sum())},
            {"表名": "项目维度", "行数": len(media_cost_df), "关键值合计": float(media_cost_df["消耗"].sum())},
            {"表名": "分端口媒体消耗", "行数": len(port_media_df), "关键值合计": float(port_media_df["消耗"].sum())},
        ]
    )


def run_bi_export_job(
    config: PipelineConfig,
    helpers: dict[str, Any],
    logger: logging.Logger,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    source_tables = fetch_bi_source_tables(helpers, logger)
    cost_df = source_tables["cost"]
    weekly_df = source_tables["weekly"]
    hr_df = source_tables["hr"]

    latest_cost_date = cost_df["消耗日期"].max()
    hr_rollups = build_hr_rollups(hr_df, int(latest_cost_date.year))
    team_cost_df = build_team_dimension_table(cost_df, latest_cost_date, hr_rollups)
    media_project_df = build_media_project_cost_table(cost_df)

    config.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = config.bi_output_path
    conversion_df = load_port_conversion_table(output_path)
    media_project_df = apply_port_conversion(media_project_df, conversion_df, logger, "项目维度")
    port_media_df = build_port_media_cost_table(helpers, logger, conversion_df)
    writer_mode = "a" if output_path.exists() else "w"
    writer_kwargs = {"if_sheet_exists": "replace"} if writer_mode == "a" else {}
    with pd.ExcelWriter(output_path, engine="openpyxl", mode=writer_mode, **writer_kwargs) as writer:
        team_cost_df.to_excel(writer, sheet_name="团队维度", index=False)
        media_project_df.to_excel(writer, sheet_name="项目维度", index=False)
        port_media_df.to_excel(writer, sheet_name="分端口媒体消耗", index=False)

    summary_df = build_bi_summary_sheet(team_cost_df, media_project_df, port_media_df)
    log_step(logger, f"[BI 导出] 完成，输出文件: {output_path}")
    return (
        {
            "team_cost": team_cost_df,
            "media_project": media_project_df,
            "port_media": port_media_df,
        },
        {
            "job_name": "bi_export",
            "output_file": str(output_path),
            "cost_source_rows": len(cost_df),
            "weekly_source_rows": len(weekly_df),
            "hr_source_rows": len(hr_df),
            "team_cost_rows": len(team_cost_df),
            "media_project_rows": len(media_project_df),
            "port_media_rows": len(port_media_df),
            "summary_df": summary_df,
        },
    )


def build_check_overview_row(job_result: dict[str, Any]) -> dict[str, Any]:
    notes: list[str] = []
    if job_result.get("min_date") is not None or job_result.get("max_date") is not None:
        notes.append(f"日期范围: {job_result.get('min_date', '')} ~ {job_result.get('max_date', '')}")
    if job_result.get("latest_cost_date") is not None:
        notes.append(f"最新消耗日期: {job_result['latest_cost_date']}")
    if job_result.get("week_labels"):
        notes.append("周标签: " + " | ".join(job_result["week_labels"]))
    if job_result.get("cost_source_rows") is not None:
        notes.append(
            "BI源表行数: "
            f"cost={job_result.get('cost_source_rows', '')}, "
            f"weekly={job_result.get('weekly_source_rows', '')}, "
            f"hr={job_result.get('hr_source_rows', '')}, "
            f"port_media={job_result.get('port_media_rows', '')}"
        )

    total_cost = job_result.get("total_cost")
    total_cost_text = round(float(total_cost), 2) if total_cost is not None else ""

    return {
        "任务": job_result["job_name"],
        "目标": job_result.get("target_table") or job_result.get("output_file"),
        "源数据行数": job_result.get("source_rows", ""),
        "输出行数": job_result.get("output_rows", ""),
        "总消耗": total_cost_text,
        "备注": "；".join(notes),
    }


def write_check_report(
    config: PipelineConfig,
    logger: logging.Logger,
    job_results: list[dict[str, Any]],
    bi_outputs: dict[str, pd.DataFrame] | None = None,
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    check_report_path = config.log_dir / f"check_report_{timestamp}.xlsx"
    config.log_dir.mkdir(parents=True, exist_ok=True)

    overview_rows: list[dict[str, Any]] = []
    with pd.ExcelWriter(check_report_path, engine="openpyxl") as writer:
        for job_result in job_results:
            job_name = job_result["job_name"]
            overview_rows.append(build_check_overview_row(job_result))
            summary_df = job_result.get("summary_df")
            if isinstance(summary_df, pd.DataFrame):
                summary_df.to_excel(writer, sheet_name=job_name[:31], index=False)

        pd.DataFrame(overview_rows).to_excel(writer, sheet_name="运行概览", index=False)

        if bi_outputs:
            for sheet_name, sheet_df in bi_outputs.items():
                preview_df = sheet_df.head(200)
                preview_df.to_excel(writer, sheet_name=f"{sheet_name}_样例"[:31], index=False)

    log_step(logger, f"[核对日志] 已生成: {check_report_path}")
    return check_report_path


def run_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    config = build_config(args)
    logger, log_path = setup_logger(config.log_dir)
    helpers = import_data_helpers(config.code_dir)

    if args.only in {"all", "monthly"} and not config.monthly_start_date:
        monthly_start_date = resolve_default_monthly_start_date(helpers, config.current_month_source_table)
        config = build_config(args, monthly_start_date)
        log_step(
            logger,
            f"未传入 --start-date，按 {config.current_month_source_table} 最新消耗日期所在月自动设置为: {monthly_start_date}",
        )

    log_step(logger, "=" * 72)
    log_step(logger, "开始执行 generate_yyzx_data")
    log_step(logger, f"输出目录: {config.output_dir}")
    log_step(logger, f"代码依赖目录: {config.code_dir}")
    if config.monthly_start_date:
        log_step(logger, f"月度消耗写库起始日期: {config.monthly_start_date}")

    job_results: list[dict[str, Any]] = []
    bi_outputs: dict[str, pd.DataFrame] | None = None

    if args.only in {"all", "monthly"}:
        _, monthly_result = run_monthly_opt_cost_job(config, helpers, logger)
        job_results.append(monthly_result)

    if args.only in {"all", "weekly"}:
        _, weekly_result = run_weekly_opt_cost_job(config, helpers, logger)
        job_results.append(weekly_result)

    if args.only in {"all", "bi"}:
        bi_outputs, bi_result = run_bi_export_job(config, helpers, logger)
        job_results.append(bi_result)

    check_report_path = write_check_report(config, logger, job_results, bi_outputs)
    log_step(logger, f"全部任务完成，运行日志: {log_path}")
    return {
        "log_path": log_path,
        "check_report_path": check_report_path,
        "bi_output_path": config.bi_output_path,
        "job_results": job_results,
    }


def main() -> None:
    args = parse_args()
    run_pipeline(args)


if __name__ == "__main__":
    main()

import argparse
import os
import re
import sys
from pathlib import Path

import pandas as pd, json
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent
SHARED_MODULE_DIR = BASE_DIR.parent
if str(SHARED_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_MODULE_DIR))

from 运营_共享.data_sources import (  # type: ignore
    ADS_PROJECT_TABLE,
    ADS_TEAM_TABLE,
    MANUAL_DATA_FILE_NAME,
    read_ads_table as read_shared_ads_table,
    read_manual_sheet,
    resolve_manual_workbook_path,
)

TEAM_SHEET = '团队维度'
PROJECT_SHEET = '项目维度'
ROI_SHEET = '投入产出'
GOAL_SHEET = '消耗目标'

GOAL_DEPT_MERGE_MAP = {
    '品策-其他-品牌': '品策-其他',
    '品策-其他-效果': '品策-其他',
}

REQUIRED_SHEET_COLUMNS = {
    PROJECT_SHEET: {
        '日期粒度', '年', '季度', '月', '周', '消耗日期', '开始日期', '结束日期', '天数',
        '媒体', '所属中心', '运营部门', '组别', '品牌名称', '产品名称', '消耗', '账户数',
    },
    TEAM_SHEET: {
        '日期粒度', '年', '季度', '月', '周', '开始日期', '结束日期', '天数',
        '团队粒度', '所属中心', '运营部门', '组别', '姓名', '消耗', '日均消耗',
        '人效人数', '人均日耗', '项目人数', '品牌数', '产品数', '账户数',
        '人均品牌', '人均账户', '人均项目', '户均消耗',
    },
    ROI_SHEET: {'年', '月', '运营部门', '收入', '成本'},
    GOAL_SHEET: {'年', '月', '运营部门', '媒体', '消耗目标'},
}


def parse_args():
    parser = argparse.ArgumentParser(description='生成运营周报 data.js')
    parser.add_argument(
        '--excel',
        help='兼容旧参数，当前脚本自动数据已直接读取 ADS 表，不再使用该路径。',
    )
    parser.add_argument(
        '--manual-excel',
        help=f'{MANUAL_DATA_FILE_NAME} 的路径，用于读取投入产出等人工维护 sheet；不传时优先读环境变量 YYZX_MANUAL_EXCEL，再自动查找常见位置。',
    )
    parser.add_argument(
        '--code-dir',
        default=None,
        help='数据库辅助模块目录；用于导入 read_my_data.py。',
    )
    parser.add_argument(
        '--team-table',
        default=ADS_TEAM_TABLE,
        help='团队维度 ADS 表名。',
    )
    parser.add_argument(
        '--project-table',
        default=ADS_PROJECT_TABLE,
        help='项目维度 ADS 表名。',
    )
    return parser.parse_args()


def resolve_sources():
    args = parse_args()

    env_manual_excel = os.environ.get('YYZX_MANUAL_EXCEL')
    manual_path = resolve_manual_workbook_path(
        args.manual_excel or env_manual_excel,
        base_dir=BASE_DIR.parent,
    )
    code_dir = Path(args.code_dir).expanduser() if args.code_dir else None
    return {
        'manual_path': manual_path,
        'code_dir': code_dir,
        'team_table': args.team_table,
        'project_table': args.project_table,
    }


sources = resolve_sources()
manual_xlsx = sources['manual_path']
team_table = sources['team_table']
project_table = sources['project_table']


df = read_shared_ads_table(
    project_table,
    required_columns=REQUIRED_SHEET_COLUMNS[PROJECT_SHEET],
    label=PROJECT_SHEET,
    code_dir=sources['code_dir'],
)
df2 = read_shared_ads_table(
    team_table,
    required_columns=REQUIRED_SHEET_COLUMNS[TEAM_SHEET],
    label=TEAM_SHEET,
    code_dir=sources['code_dir'],
)


def latest_week_label(series):
    labels = sorted_week_labels(series)
    return labels[-1] if labels else None


def sorted_week_labels(series):
    labels = list(series.dropna().astype(str).unique())

    def week_key(label):
        iso = re.search(r'(\d{2})W(\d{1,2})', label)
        if iso:
            return (2000 + int(iso.group(1)), int(iso.group(2)))
        m = re.search(r'W(\d+)', label)
        return (0, int(m.group(1)) if m else -1)

    return sorted(labels, key=week_key)


def normalize_goal_dept(value):
    if pd.isna(value):
        return value
    return GOAL_DEPT_MERGE_MAP.get(str(value), str(value))


TEAM_ORDER = ['K部门', 'K2', 'K3', 'K4', 'K5', 'K7', 'K4-品商', '品策-小红书']
K_DEPT_COMPONENTS = ['K2', 'K3', 'K4', 'K5', 'K7']


def parse_quarter_num(value):
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)) and not pd.isna(value):
        return int(value)
    text = str(value)
    match = re.search(r'Q([1-4])|第?([1-4])季|([1-4])$', text, re.IGNORECASE)
    if match:
        return int(next(g for g in match.groups() if g))
    try:
        return int(pd.Timestamp(value).quarter)
    except Exception:
        return None


daily = df[(df['所属中心'] == '运营中心') & (df['日期粒度'] == '日')].copy()
# 排除"K部门"合计行（是K2/K3/K4/K7的子合计，会导致数据重复）
daily = daily[~daily['运营部门'].isin(['K部门'])]
daily['消耗日期'] = pd.to_datetime(daily['消耗日期']).dt.strftime('%Y-%m-%d')

# 1. RAW_TREND
raw_trend = daily.groupby('消耗日期')['消耗'].sum().reset_index().sort_values('消耗日期')
raw_trend_list = [{'日期': r['消耗日期'], '消耗': round(r['消耗'], 2)} for _, r in raw_trend.iterrows()]
latest_date = pd.to_datetime(raw_trend['消耗日期'].max()) if len(raw_trend) > 0 else pd.Timestamp.today()
current_year = int(latest_date.year)
current_quarter_num = int((latest_date.month - 1) // 3 + 1)
days_in_year = 366 if ((current_year % 4 == 0 and current_year % 100 != 0) or (current_year % 400 == 0)) else 365
year_elapsed_days = int((latest_date - pd.Timestamp(year=current_year, month=1, day=1)).days + 1)
year_remaining_days = max(days_in_year - year_elapsed_days, 0)

# 2. MEDIA_DATA
media_data = {}
for media in daily['媒体'].unique():
    mdf = daily[daily['媒体'] == media].groupby('消耗日期')['消耗'].sum().reset_index().sort_values('消耗日期')
    media_data[media] = [{'日期': r['消耗日期'], '消耗': round(r['消耗'], 2)} for _, r in mdf.iterrows()]

# 3. CENTER_YEAR
cy = df2[(df2['所属中心'] == '运营中心') & (df2['日期粒度'] == '年') & (df2['运营部门'].isna()) & (df2['团队粒度'] == '所属中心')]
center_year = {}
if len(cy) > 0:
    row = cy.iloc[-1]
    center_year = {'消耗': round(row['消耗'], 2), '日均消耗': round(row['日均消耗'], 2), '人效人数': round(row['人效人数'], 4), '人均日耗': round(row['人均日耗'], 6)}

# 4. CENTER_MONTHS
cm = df2[(df2['所属中心'] == '运营中心') & (df2['日期粒度'] == '月') & (df2['运营部门'].isna()) & (df2['团队粒度'] == '所属中心')].sort_values('月')
center_months = [{'月': str(r['月'])[:7] if pd.notna(r['月']) else '', '消耗': round(r['消耗'], 2), '日均消耗': round(r['日均消耗'], 2), '人效人数': round(r['人效人数'], 4), '人均日耗': round(r['人均日耗'], 6)} for _, r in cm.iterrows()]

# 5. TEAM_DATA — 按部门粒度、月度粒度，取每月日均消耗（万）
dept_keys = TEAM_ORDER
team_data = {}
total_days = len(raw_trend_list)
for dept in dept_keys:
    dept_filter = df2['运营部门'].isin(K_DEPT_COMPONENTS) if dept == 'K部门' else (df2['运营部门'] == dept)
    tdf = df2[(df2['所属中心'] == '运营中心') & (df2['日期粒度'] == '月') & dept_filter & (df2['团队粒度'] == '部门')].sort_values('月')
    if len(tdf) == 0:
        continue
    if dept == 'K部门':
        tdf = (
            tdf.groupby('月', as_index=False)
            .agg({'消耗': 'sum', '日均消耗': 'sum', '人均日耗': 'sum'})
            .sort_values('月')
        )
    total = float(tdf['消耗'].sum())
    months = [str(r['月'])[5:7] + '月' if pd.notna(r['月']) else '?' for _, r in tdf.iterrows()]
    month_daily_values = [round(r['日均消耗'] / 10000, 2) for _, r in tdf.iterrows()]
    month_costs = [round(r['消耗'] / 10000, 2) for _, r in tdf.iterrows()]
    month_pcs = [round(r['人均日耗'] / 10000, 2) for _, r in tdf.iterrows()]
    team_data[dept] = {'total': total, 'daily_avg': total / total_days if total_days > 0 else 0, 'months': months, 'month_daily_values': month_daily_values, 'month_costs': month_costs, 'month_pcs': month_pcs}

# 6. BRAND_DATA: 品牌 x 日期 x 媒体 x 运营部门的日消耗
bd = daily.groupby(['消耗日期', '媒体', '运营部门', '品牌名称'])['消耗'].sum().reset_index().sort_values(['消耗日期', '品牌名称'])
brand_daily = [{'日期': r['消耗日期'], '媒体': r['媒体'], '运营部门': r['运营部门'], '品牌名称': r['品牌名称'], '消耗': round(r['消耗'], 2)} for _, r in bd.iterrows()]

# 7. DEPT_PC_DATA: 运营中心各部门年度人均日耗（排除品策-其他，含K部门）
yr_dept = df2[(df2['所属中心'] == '运营中心') & (df2['日期粒度'] == '年') & (df2['团队粒度'] == '部门')]
yr_dept = yr_dept[~yr_dept['运营部门'].isin(['品策-其他'])]
yr_dept = yr_dept.sort_values('人均日耗', ascending=False)
dept_pc_list = [{'dept': r['运营部门'], 'pc': round(r['人均日耗'], 2)} for _, r in yr_dept.iterrows()]

# 8. CENTER_PC_DATA: 各中心年度人均日耗（不含"整体"）
yr_center_all = df2[(df2['日期粒度'] == '年') & (df2['团队粒度'] == '所属中心') & (df2['所属中心'] != '整体')]
yr_center_all = yr_center_all.sort_values('人均日耗', ascending=False)
center_pc_list = [{'center': r['所属中心'], 'pc': round(r['人均日耗'], 2)} for _, r in yr_center_all.iterrows()]

# 9. DEPT_YEAR_COST_DATA: 运营中心各部门年度消耗（排除品策-其他和K部门，按消耗升序）
yr_cost = df2[(df2['所属中心'] == '运营中心') & (df2['日期粒度'] == '年') & (df2['团队粒度'] == '部门')]
yr_cost = yr_cost[~yr_cost['运营部门'].isin(['品策-其他', 'K部门'])]
yr_cost = yr_cost.sort_values('消耗', ascending=True)
dept_cost_list = [{'dept': r['运营部门'], 'cost': round(r['消耗'], 2)} for _, r in yr_cost.iterrows()]

# 10. ROI_DATA: 年度投产比（投入产出sheet）
df_roi = read_manual_sheet(
    ROI_SHEET,
    required_columns=REQUIRED_SHEET_COLUMNS[ROI_SHEET],
    manual_data_path=manual_xlsx,
)
df_goal = read_manual_sheet(
    GOAL_SHEET,
    required_columns=REQUIRED_SHEET_COLUMNS[GOAL_SHEET],
    manual_data_path=manual_xlsx,
)
df_goal = df_goal.copy()
df_goal['运营部门'] = df_goal['运营部门'].apply(normalize_goal_dept)
goal_year_dept_map = (
    df_goal[df_goal['年'] == current_year]
    .groupby('运营部门', as_index=False)['消耗目标']
    .sum()
    .set_index('运营部门')['消耗目标']
    .to_dict()
)
quarter_dept_rows = df2[
    (df2['所属中心'] == '运营中心') &
    (df2['日期粒度'] == '季度') &
    (df2['团队粒度'] == '部门')
].copy()
quarter_dept_daily_map = {}
if len(quarter_dept_rows) > 0:
    quarter_dept_rows['_quarter_num'] = quarter_dept_rows['季度'].apply(parse_quarter_num)
    quarter_dept_rows = quarter_dept_rows[quarter_dept_rows['_quarter_num'] == current_quarter_num]
    quarter_dept_daily_map = (
        quarter_dept_rows.groupby('运营部门')['日均消耗']
        .sum()
        .to_dict()
    )


def _dept_year_target(dept):
    if dept == 'K部门':
        return float(sum(float(goal_year_dept_map.get(d, 0)) for d in K_DEPT_COMPONENTS))
    return float(goal_year_dept_map.get(dept, 0))


def _dept_quarter_daily(dept):
    if dept == 'K部门':
        return float(sum(float(quarter_dept_daily_map.get(d, 0)) for d in K_DEPT_COMPONENTS))
    return float(quarter_dept_daily_map.get(dept, 0))


for dept, values in team_data.items():
    target_val = _dept_year_target(dept)
    has_target = target_val > 0
    quarter_daily = _dept_quarter_daily(dept)
    forecast = float(values['total']) + quarter_daily * year_remaining_days
    values['target'] = round(target_val, 2)
    values['has_target'] = has_target
    values['completion_pct'] = round(values['total'] / target_val * 100, 1) if has_target else None
    values['target_gap'] = round(values['total'] - target_val, 2) if has_target else None
    values['quarter_daily_cost'] = round(quarter_daily, 2)
    values['forecast'] = round(forecast, 2)
    values['forecast_pct'] = round(forecast / target_val * 100, 1) if has_target else None
    values['forecast_gap'] = round(forecast - target_val, 2) if has_target else None
roi_year = df_roi[df_roi['年'] == 2026].copy()
roi_year = roi_year[~roi_year['运营部门'].isin(['品策-其他'])]
roi_year['ROI_CALC'] = roi_year.apply(
    lambda r: float(r['收入']) / float(r['成本']) if pd.notna(r['成本']) and float(r['成本']) else 0,
    axis=1
)
roi_summary = (
    roi_year.groupby('运营部门', as_index=False)
    .agg({'收入': 'sum', '成本': 'sum'})
)
roi_summary['roi'] = roi_summary.apply(
    lambda r: float(r['收入']) / float(r['成本']) if float(r['成本']) else 0,
    axis=1
)
roi_summary = roi_summary.sort_values('roi', ascending=False)
roi_list = [{'dept': r['运营部门'], 'roi': round(r['roi'], 4)} for _, r in roi_summary.iterrows()]

# 10b. DEPT_MONTHLY_ROI: 各部门月度投产比趋势（投入产出sheet）
roi_monthly = roi_year.sort_values(['运营部门', '月'])
dept_monthly_roi = {}
for _, r in roi_monthly.iterrows():
    dept = r['运营部门']
    if dept not in dept_monthly_roi:
        dept_monthly_roi[dept] = []
    dept_monthly_roi[dept].append({
        'month': int(r['月']),
        'roi': round(float(r['ROI_CALC']), 2)
    })

# 11. MONTH_TARGET: 当月指标达成
# 确定当月（取团队维度中最大月份）
max_month = df2[(df2['所属中心'] == '运营中心') & (df2['日期粒度'] == '月') & (df2['团队粒度'] == '部门')]['月'].max()
max_month_num = max_month.month if hasattr(max_month, 'month') else int(str(max_month).split('-')[1])

week_date_map = {}
if {'日期粒度', '周', '开始日期', '结束日期'}.issubset(df2.columns):
    week_periods = df2[(df2['日期粒度'] == '周') & df2['周'].notna()].copy()
    if len(week_periods) > 0:
        week_periods['开始日期'] = pd.to_datetime(week_periods['开始日期'])
        week_periods['结束日期'] = pd.to_datetime(week_periods['结束日期'])
        for week_label, wk in week_periods.groupby(week_periods['周'].astype(str)):
            start = wk['开始日期'].min()
            end = wk['结束日期'].max()
            if pd.notna(start) and pd.notna(end):
                week_date_map[str(week_label)] = {
                    'start': start,
                    'end': end,
                    'display': '[' + start.strftime('%m%d') + '~' + end.strftime('%m%d') + ']'
                }

# 11a. 当月总消耗 + 人效人数（团队维度，月，部门粒度）
mt_cost = df2[(df2['所属中心'] == '运营中心') & (df2['日期粒度'] == '月') & (df2['团队粒度'] == '部门') & (df2['月'] == max_month)]
cost_map = {}
for _, r in mt_cost.iterrows():
    cost_map[r['运营部门']] = {
        'cost': round(r['消耗'], 2),
        'daily_cost': round(r['日均消耗'], 2),
        'staff': round(r['人效人数'], 2),
    }

goal_month = df_goal[(df_goal['年'] == 2026) & (df_goal['月'] == max_month_num)].copy()
goal_dept_map = (
    goal_month.groupby('运营部门', as_index=False)['消耗目标']
    .sum()
    .set_index('运营部门')['消耗目标']
    .to_dict()
)
goal_center_target = float(sum(goal_dept_map.values()))

# 11b. 品牌数 + 账户数（团队维度，周粒度，部门粒度）
df_acct_all = df2[
    (df2['日期粒度'] == '周') &
    (df2['团队粒度'].isin(['所属中心', '部门', '组别']))
].copy()
df_acct_all['周标签'] = df_acct_all['周'].astype(str)
if '户均消耗' in df_acct_all.columns and '户均日耗' not in df_acct_all.columns:
    df_acct_all['户均日耗'] = df_acct_all['户均消耗']
acct_week_labels = sorted_week_labels(df_acct_all['周标签']) if '周标签' in df_acct_all.columns else []
acct_week_label = acct_week_labels[-1] if acct_week_labels else None
df_acct = df_acct_all.copy()
if acct_week_label:
    df_acct = df_acct[df_acct['周标签'].astype(str) == acct_week_label].copy()
acct_dept = df_acct[(df_acct['所属中心'] == '运营中心') & (df_acct['团队粒度'] == '部门')]
acct_map = {}
for _, r in acct_dept.iterrows():
    acct_map[r['运营部门']] = {'brands': int(r['品牌数']), 'accounts': int(r['账户数'])}

# 11c. 各媒体消耗占比（项目维度，月，运营中心，按部门+媒体聚合）
df_media = df

# 11b-1. 近两周人均/户均指标波动分析（不展示K部门）
week_metric_analysis = {'weeks': [], 'week_ranges': {}, 'metrics': []}
if len(acct_week_labels) >= 2:
    prev_week, curr_week = acct_week_labels[-2], acct_week_labels[-1]
    week_metric_analysis['weeks'] = [prev_week, curr_week]
    week_metric_analysis['week_ranges'] = {
        w: {
            'start': week_date_map[w]['start'].strftime('%Y-%m-%d'),
            'end': week_date_map[w]['end'].strftime('%Y-%m-%d'),
            'display': week_date_map[w]['display']
        }
        for w in [prev_week, curr_week]
        if w in week_date_map
    }
    acct_week_base = df_acct_all[
        (df_acct_all['所属中心'] == '运营中心') &
        (df_acct_all['团队粒度'] == '部门') &
        (df_acct_all['周标签'].astype(str).isin([prev_week, curr_week]))
    ].copy()

    def _num(v, default=0):
        return default if pd.isna(v) else float(v)

    def _round(v, nd=2):
        return round(float(v), nd) if v is not None else 0

    def _staff_from(row, value_col, base_col):
        val = _num(row.get(value_col), 0)
        base = _num(row.get(base_col), 0)
        return base / val if val else 0

    def _change_phrase(label, delta, unit=''):
        if abs(delta) < 0.000001:
            return f'{label}无变化'
        verb = '增加' if delta > 0 else '减少'
        val = abs(delta)
        txt = str(int(round(val))) if abs(val - round(val)) < 0.000001 else f'{val:.1f}'
        return f'{label}{verb}{txt}{unit}'

    def _week_date_range(label):
        if str(label) in week_date_map:
            return week_date_map[str(label)]['start'], week_date_map[str(label)]['end']
        m = re.search(r'\[(\d{4})~(\d{4})\]', str(label))
        if not m:
            return None
        year = max_month.year if hasattr(max_month, 'year') else 2026
        start = pd.Timestamp(year=year, month=int(m.group(1)[:2]), day=int(m.group(1)[2:]))
        end = pd.Timestamp(year=year, month=int(m.group(2)[:2]), day=int(m.group(2)[2:]))
        return start, end

    def _brand_set(dept, label):
        date_range = _week_date_range(label)
        if not date_range or '品牌名称' not in df_media.columns:
            return set()
        start, end = date_range
        media_daily = df_media[
            (df_media['所属中心'] == '运营中心') &
            (df_media['日期粒度'] == '日') &
            (df_media['运营部门'] == dept)
        ].copy()
        if len(media_daily) == 0:
            return set()
        media_daily['消耗日期'] = pd.to_datetime(media_daily['消耗日期'])
        media_daily = media_daily[(media_daily['消耗日期'] >= start) & (media_daily['消耗日期'] <= end)]
        return set(media_daily['品牌名称'].dropna().astype(str).unique())

    def _brand_account_map(dept, label):
        if not {'周', '账户数', '品牌名称'}.issubset(df_media.columns):
            return {}
        rows = df_media[
            (df_media['所属中心'] == '运营中心') &
            (df_media['日期粒度'] == '周') &
            (df_media['运营部门'] == dept) &
            (df_media['周'].astype(str) == str(label))
        ].copy()
        if len(rows) == 0:
            return {}
        grouped = rows.groupby('品牌名称')['账户数'].sum()
        return {str(k): float(v) for k, v in grouped.items() if pd.notna(k)}

    def _top_brand_account_changes(dept, prev_label, curr_label, limit=2):
        prev_map = _brand_account_map(dept, prev_label)
        curr_map = _brand_account_map(dept, curr_label)
        names = sorted(set(prev_map) | set(curr_map))
        changes = []
        for name in names:
            delta_val = curr_map.get(name, 0) - prev_map.get(name, 0)
            if abs(delta_val) >= 0.5:
                changes.append({
                    'brand': name,
                    'prev': prev_map.get(name, 0),
                    'curr': curr_map.get(name, 0),
                    'delta': delta_val
                })
        changes = sorted(changes, key=lambda x: abs(x['delta']), reverse=True)
        return changes[:limit]

    def _brand_spend_account_map(dept, label):
        if not {'周', '账户数', '品牌名称', '消耗', '天数'}.issubset(df_media.columns):
            return {}
        rows = df_media[
            (df_media['所属中心'] == '运营中心') &
            (df_media['日期粒度'] == '周') &
            (df_media['运营部门'] == dept) &
            (df_media['周'].astype(str) == str(label))
        ].copy()
        if len(rows) == 0:
            return {}
        grouped = rows.groupby('品牌名称').agg(
            消耗=('消耗', 'sum'),
            账户数=('账户数', 'sum'),
            天数=('天数', 'max')
        )
        result = {}
        for brand, row in grouped.iterrows():
            if pd.isna(brand):
                continue
            accounts = float(row['账户数']) if pd.notna(row['账户数']) else 0
            days = float(row['天数']) if pd.notna(row['天数']) and float(row['天数']) else 0
            daily_spend = float(row['消耗']) / days if days else 0
            acct_daily = daily_spend / accounts if accounts else 0
            result[str(brand)] = {
                'daily_spend': daily_spend,
                'accounts': accounts,
                'acct_daily': acct_daily
            }
        return result

    def _top_brand_acct_daily_change(dept, prev_label, curr_label):
        prev_map = _brand_spend_account_map(dept, prev_label)
        curr_map = _brand_spend_account_map(dept, curr_label)
        changes = []
        for name in sorted(set(prev_map) | set(curr_map)):
            prev_info = prev_map.get(name, {'daily_spend': 0, 'accounts': 0, 'acct_daily': 0})
            curr_info = curr_map.get(name, {'daily_spend': 0, 'accounts': 0, 'acct_daily': 0})
            delta_val = curr_info['acct_daily'] - prev_info['acct_daily']
            if abs(delta_val) >= 1:
                changes.append({
                    'brand': name,
                    'prev': prev_info['acct_daily'],
                    'curr': curr_info['acct_daily'],
                    'delta': delta_val,
                    'spend_prev': prev_info['daily_spend'],
                    'spend_curr': curr_info['daily_spend'],
                    'accounts_prev': prev_info['accounts'],
                    'accounts_curr': curr_info['accounts'],
                })
        if not changes:
            return None
        return sorted(changes, key=lambda x: abs(x['delta']), reverse=True)[0]

    def _top_brand_daily_spend_change(dept, prev_label, curr_label):
        prev_map = _brand_spend_account_map(dept, prev_label)
        curr_map = _brand_spend_account_map(dept, curr_label)
        changes = []
        for name in sorted(set(prev_map) | set(curr_map)):
            prev_info = prev_map.get(name, {'daily_spend': 0, 'accounts': 0, 'acct_daily': 0})
            curr_info = curr_map.get(name, {'daily_spend': 0, 'accounts': 0, 'acct_daily': 0})
            delta_val = curr_info['daily_spend'] - prev_info['daily_spend']
            if abs(delta_val) >= 1:
                changes.append({
                    'brand': name,
                    'prev': prev_info['daily_spend'],
                    'curr': curr_info['daily_spend'],
                    'delta': delta_val,
                })
        if not changes:
            return None
        return sorted(changes, key=lambda x: abs(x['delta']), reverse=True)[0]

    def _fmt_signed(value, unit):
        sign = '+' if value > 0 else ''
        abs_close_int = abs(value - round(value)) < 0.000001
        text = str(int(round(value))) if abs_close_int else f'{value:.1f}'
        return sign + text + unit

    metric_defs = [
        {'key': 'brand_pc', 'label': '人均品牌', 'value_col': '人均品牌', 'base_col': '品牌数', 'base_label': '品牌数', 'unit': '个', 'base_unit': '个', 'decimals': 2},
        {'key': 'acct_pc', 'label': '人均账户', 'value_col': '人均账户', 'base_col': '账户数', 'base_label': '账户数', 'unit': '个', 'base_unit': '个', 'decimals': 1},
        {'key': 'acct_daily', 'label': '户均消耗', 'value_col': '户均日耗', 'base_col': '账户数', 'base_label': '账户数', 'unit': '元', 'base_unit': '个', 'decimals': 0},
    ]

    for metric in metric_defs:
        rows = []
        for dept in dept_keys:
            prev_rows = acct_week_base[(acct_week_base['运营部门'] == dept) & (acct_week_base['周标签'].astype(str) == prev_week)]
            curr_rows = acct_week_base[(acct_week_base['运营部门'] == dept) & (acct_week_base['周标签'].astype(str) == curr_week)]
            if len(prev_rows) == 0 or len(curr_rows) == 0:
                continue
            pr = prev_rows.iloc[0]
            cr = curr_rows.iloc[0]
            prev_val = _num(pr.get(metric['value_col']), 0)
            curr_val = _num(cr.get(metric['value_col']), 0)
            delta = curr_val - prev_val
            prev_base = _num(pr.get(metric['base_col']), 0)
            curr_base = _num(cr.get(metric['base_col']), 0)
            base_delta = curr_base - prev_base
            prev_staff = _staff_from(pr, '人均品牌', '品牌数')
            curr_staff = _staff_from(cr, '人均品牌', '品牌数')
            staff_delta = curr_staff - prev_staff
            prev_daily_cost = _num(pr.get('消耗'), 0) / _num(pr.get('天数'), 1)
            curr_daily_cost = _num(cr.get('消耗'), 0) / _num(cr.get('天数'), 1)
            daily_cost_delta = curr_daily_cost - prev_daily_cost
            parts = []
            details = []
            added_brands = []
            removed_brands = []

            if metric['key'] == 'acct_daily':
                if prev_base and curr_base:
                    spend_effect = 0.5 * ((curr_daily_cost / prev_base - prev_daily_cost / prev_base) + (curr_daily_cost / curr_base - prev_daily_cost / curr_base))
                    account_effect = 0.5 * ((prev_daily_cost / curr_base - prev_daily_cost / prev_base) + (curr_daily_cost / curr_base - curr_daily_cost / prev_base))
                else:
                    spend_effect = 0
                    account_effect = 0
                if abs(delta) < 1:
                    main_cause = '户均消耗无明显变化'
                else:
                    main_cause = '项目消耗变化' if abs(spend_effect) >= abs(account_effect) else '账户数变化'
                parts.append('主因：' + main_cause)
                if main_cause == '项目消耗变化':
                    top_brand_spend = _top_brand_daily_spend_change(dept, prev_week, curr_week)
                    if top_brand_spend:
                        details.append(
                            f"影响最大品牌：{top_brand_spend['brand']} 日均消耗{_fmt_signed(top_brand_spend['delta'], '元')}"
                            + f"（{top_brand_spend['prev']:.0f} -> {top_brand_spend['curr']:.0f}）"
                        )
                elif main_cause == '账户数变化':
                    top_account_changes = _top_brand_account_changes(dept, prev_week, curr_week, 1)
                    if top_account_changes:
                        change = top_account_changes[0]
                        details.append(
                            f"影响最大品牌：{change['brand']} 账户数{_fmt_signed(change['delta'], '个')}"
                            + f"（{change['prev']:.0f} -> {change['curr']:.0f}）"
                        )
                else:
                    top_brand_daily = _top_brand_acct_daily_change(dept, prev_week, curr_week)
                    if top_brand_daily:
                        details.append(
                            f"影响最大品牌：{top_brand_daily['brand']} "
                            + f"{_fmt_signed(top_brand_daily['delta'], '元')}"
                            + f"（{top_brand_daily['prev']:.0f} -> {top_brand_daily['curr']:.0f}）"
                        )
            else:
                if abs(base_delta) >= 0.5:
                    parts.append(_change_phrase(metric['base_label'], base_delta, metric.get('base_unit', '')))
                if abs(staff_delta) >= 0.05:
                    parts.append(_change_phrase('人数', staff_delta, '人'))
                if not parts:
                    parts.append(f"{metric['base_label']}和人员无变化")
                details.append(f"{metric['base_label']}：{prev_base:.0f} -> {curr_base:.0f}")
                if abs(staff_delta) >= 0.05:
                    details.append(f"人数：{prev_staff:.1f} -> {curr_staff:.1f}")
                if metric['key'] == 'brand_pc':
                    prev_brands = _brand_set(dept, prev_week)
                    curr_brands = _brand_set(dept, curr_week)
                    added_brands = sorted(curr_brands - prev_brands)
                    removed_brands = sorted(prev_brands - curr_brands)
                    if added_brands:
                        details.append('新增品牌：' + '、'.join(added_brands[:8]))
                    if removed_brands:
                        details.append('减少品牌：' + '、'.join(removed_brands[:8]))
                if metric['key'] == 'acct_pc':
                    top_account_changes = _top_brand_account_changes(dept, prev_week, curr_week)
                    if top_account_changes:
                        change_texts = []
                        for change in top_account_changes:
                            change_texts.append(
                                f"{change['brand']} {_fmt_signed(change['delta'], '个')}"
                                + f"（{change['prev']:.0f} -> {change['curr']:.0f}）"
                            )
                        details.append('账户变化Top2品牌：' + '；'.join(change_texts))

            rows.append({
                'dept': dept,
                'prev': _round(prev_val, metric['decimals']),
                'curr': _round(curr_val, metric['decimals']),
                'delta': _round(delta, metric['decimals']),
                'base_prev': _round(prev_base, 0),
                'base_curr': _round(curr_base, 0),
                'staff_prev': _round(prev_staff, 1),
                'staff_curr': _round(curr_staff, 1),
                'daily_cost_prev': _round(prev_daily_cost, 0),
                'daily_cost_curr': _round(curr_daily_cost, 0),
                'reason': '；'.join(parts),
                'details': details,
                'added_brands': added_brands,
                'removed_brands': removed_brands,
            })
        rows = sorted(rows, key=lambda x: abs(x['delta']), reverse=True)
        week_metric_analysis['metrics'].append({
            'key': metric['key'],
            'label': metric['label'],
            'unit': metric['unit'],
            'decimals': metric['decimals'],
            'base_label': metric['base_label'],
            'rows': rows
        })

media_month = df_media[(df_media['所属中心'] == '运营中心') & (df_media['日期粒度'] == '月') & (df_media['月'] == max_month)]
# 过滤掉品策-其他和K部门（用于非汇总部门）
media_month_no_k = media_month[~media_month['运营部门'].isin(['品策-其他', 'K部门'])]
# 按部门+媒体聚合（包含K部门）
dept_media_cost = media_month.groupby(['运营部门', '媒体'])['消耗'].sum().reset_index()
# 获取全部媒体列表（去重，不含K部门）
all_media = sorted(media_month_no_k['媒体'].unique())
# 构建部门->媒体占比map
dept_media_map = {}
for dept in dept_keys:
    dept_rows = dept_media_cost[dept_media_cost['运营部门'] == dept]
    dept_total = dept_rows['消耗'].sum()
    ratios = []
    for m in all_media:
        m_row = dept_rows[dept_rows['媒体'] == m]
        val = round(m_row['消耗'].values[0], 2) if len(m_row) > 0 else 0
        pct = round(val / dept_total * 100, 1) if dept_total > 0 else 0
        ratios.append({'media': m, 'cost': val, 'pct': pct})
    dept_media_map[dept] = ratios

month_target_list = []
for dept in TEAM_ORDER:
    cm = cost_map.get(dept, {'cost': 0, 'daily_cost': 0, 'staff': 0})
    ac = acct_map.get(dept, {'brands': 0, 'accounts': 0})
    mr = dept_media_map.get(dept, [])
    target_val = float(sum(float(goal_dept_map.get(d, 0)) for d in K_DEPT_COMPONENTS)) if dept == 'K部门' else float(goal_dept_map.get(dept, 0))
    has_target = target_val > 0
    completion_pct = round(cm['cost'] / target_val * 100, 1) if has_target else None
    target_gap = round(cm['cost'] - target_val, 2) if has_target else None
    # K部门媒体占比：从media_month中单独取
    if dept == 'K部门' and len(mr) == 0:
        k_media_rows = dept_media_cost[dept_media_cost['运营部门'] == 'K部门']
        k_total = k_media_rows['消耗'].sum()
        mr = []
        for m in all_media:
            m_row = k_media_rows[k_media_rows['媒体'] == m]
            val = round(m_row['消耗'].values[0], 2) if len(m_row) > 0 else 0
            pct = round(val / k_total * 100, 1) if k_total > 0 else 0
            mr.append({'media': m, 'cost': val, 'pct': pct})
    month_target_list.append({
        'dept': dept,
        'cost': cm['cost'],
        'daily_cost': cm['daily_cost'],
        'target': round(target_val, 2),
        'has_target': has_target,
        'completion_pct': completion_pct,
        'target_gap': target_gap,
        'staff': cm['staff'],
        'brands': ac['brands'],
        'accounts': ac['accounts'],
        'media_ratios': mr
    })

# 11d. MONTH_MEDIA_TABLE: 当月媒体×部门消耗矩阵（用于当月指标达成顶部表格）
# 数据来源：项目维度，月粒度，运营中心，排除K部门
# 媒体指定顺序（其余媒体追加在后）
media_order = ['腾讯', '小红书', '头条', '快手', '百度', '阿里UDS']
# 统计各子部门消耗：排除K部门，品策-小红书和品策-其他合并为"品牌策略部"
sub_dept_keys = ['K2', 'K3', 'K4', 'K7', 'K4-品商', '品牌策略部']
# 当月项目维度，排除K部门（保留品策-其他用于合并）
mmt = df_media[
    (df_media['所属中心'] == '运营中心') &
    (df_media['日期粒度'] == '月') &
    (df_media['月'] == max_month) &
    (~df_media['运营部门'].isin(['K部门']))
].copy()
# 将品策-小红书和品策-其他合并为"品牌策略部"
mmt['运营部门'] = mmt['运营部门'].replace({'品策-小红书': '品牌策略部', '品策-其他': '品牌策略部'})
# 运营中心总计按媒体
center_media_total = mmt.groupby('媒体')['消耗'].sum()
center_total_all = center_media_total.sum()
# 各部门按媒体消耗
dept_media_matrix = mmt.groupby(['运营部门', '媒体'])['消耗'].sum().unstack(fill_value=0)
# 确定最终媒体顺序
existing_media = list(center_media_total.index)
final_media_order = [m for m in media_order if m in existing_media] + \
                    [m for m in existing_media if m not in media_order]
month_media_table = []
for media in final_media_order:
    mc = center_media_total.get(media, 0)
    if mc <= 0:
        continue
    row = {
        'media': media,
        'center_cost': round(float(mc), 2),
        'center_pct': round(float(mc) / center_total_all * 100, 1) if center_total_all > 0 else 0,
        'dept_pcts': {}
    }
    for dept in sub_dept_keys:
        dept_total = dept_media_matrix.loc[dept].sum() if dept in dept_media_matrix.index else 0
        dept_media_cost = dept_media_matrix.loc[dept, media] if dept in dept_media_matrix.index and media in dept_media_matrix.columns else 0
        row['dept_pcts'][dept] = round(float(dept_media_cost) / dept_total * 100, 1) if dept_total > 0 else 0
    month_media_table.append(row)

# 12. MONTH_DEPT_PC: 当月各部门人均日耗（来源于团队维度，月粒度，部门粒度）
mt_pc = df2[(df2['所属中心'] == '运营中心') & (df2['日期粒度'] == '月') & (df2['团队粒度'] == '部门') & (df2['月'] == max_month)]
# 图表用的部门列表（含K部门汇总）
chart_dept_keys = dept_keys + ['K部门']
month_dept_pc_list = []
for dept in chart_dept_keys:
    row = mt_pc[mt_pc['运营部门'] == dept]
    if len(row) > 0:
        month_dept_pc_list.append({'dept': dept, 'pc': round(row.iloc[0]['人均日耗'], 2)})
    else:
        month_dept_pc_list.append({'dept': dept, 'pc': 0})

# 13. MONTH_DEPT_BRAND_PC / MONTH_DEPT_ACCT_PC: 当月人均品牌数、人均账户数（现成列）
acct_pc_map = {}
for _, r in acct_dept.iterrows():
    acct_pc_map[r['运营部门']] = {'brand_pc': round(r['人均品牌'], 1), 'acct_pc': round(r['人均账户'], 0)}
month_dept_brand_pc_list = []
month_dept_acct_pc_list = []
for dept in chart_dept_keys:
    ap = acct_pc_map.get(dept, {'brand_pc': 0, 'acct_pc': 0})
    month_dept_brand_pc_list.append({'dept': dept, 'val': ap['brand_pc']})
    month_dept_acct_pc_list.append({'dept': dept, 'val': ap['acct_pc']})

# 14. MONTH_ROI: 当月各部门投产比（投入产出sheet）
month_roi = df_roi[df_roi['年'] == 2026].copy()
month_roi['ROI_CALC'] = month_roi.apply(
    lambda r: float(r['收入']) / float(r['成本']) if pd.notna(r['成本']) and float(r['成本']) else 0,
    axis=1
)
month_roi = month_roi[month_roi['月'] == max_month_num]
month_roi = month_roi[~month_roi['运营部门'].isin(['品策-其他'])]
month_roi = month_roi.sort_values('ROI_CALC', ascending=False)
month_roi_list = []
for dept in chart_dept_keys:
    row = month_roi[month_roi['运营部门'] == dept]
    if len(row) > 0:
        month_roi_list.append({'dept': dept, 'val': round(row.iloc[0]['ROI_CALC'], 2)})
    else:
        month_roi_list.append({'dept': dept, 'val': 0})

# 15. MONTH_DEPT_ACCT_DAILY: 当月各部门户均日耗（团队维度，周粒度）
acct2_dept = acct_dept  # 已有：运营中心 + 部门粒度
month_acct_daily_list = []
for dept in chart_dept_keys:
    row = acct2_dept[acct2_dept['运营部门'] == dept]
    if len(row) > 0:
        month_acct_daily_list.append({'dept': dept, 'val': round(row.iloc[0]['户均日耗'], 2)})
    else:
        month_acct_daily_list.append({'dept': dept, 'val': 0})

# 16. DEPT_GROUP_DATA: 各部门组别月度数据（月消耗 + 人均日耗）
dept_group_data = {}
for dept in dept_keys:
    gdf = df2[(df2['所属中心'] == '运营中心') & (df2['日期粒度'] == '月') & (df2['运营部门'] == dept) & (df2['团队粒度'] == '组别')].sort_values('月')
    if len(gdf) == 0:
        continue
    groups = {}
    for grp_name in gdf['组别'].dropna().unique():
        gg = gdf[gdf['组别'] == grp_name]
        months = []
        for _, r in gg.iterrows():
            mo = str(r['月'])[5:7] + '月' if pd.notna(r['月']) else '?'
            months.append({'month': mo, 'cost': round(r['消耗'], 2), 'daily_avg': round(r['日均消耗'] / 10000, 2), 'daily_pc': round(r['人均日耗'] / 10000, 2)})
        groups[grp_name] = months
    dept_group_data[dept] = groups

# 17. CENTER_YEAR_MEDIA: 运营中心年度各媒体消耗占比 + 预计达成
latest_date = pd.to_datetime(raw_trend['消耗日期'].max()) if len(raw_trend) > 0 else pd.Timestamp.today()
current_year = int(latest_date.year)
days_in_year = 366 if ((current_year % 4 == 0 and current_year % 100 != 0) or current_year % 400 == 0) else 365
year_elapsed_days = int((latest_date - pd.Timestamp(year=current_year, month=1, day=1)).days + 1)
year_remaining_days = max(days_in_year - year_elapsed_days, 0)
current_quarter_start_month = ((latest_date.month - 1) // 3) * 3 + 1
current_quarter_start = pd.Timestamp(year=current_year, month=current_quarter_start_month, day=1)
quarter_elapsed_days = int((latest_date - current_quarter_start).days + 1)

daily_for_media_forecast = daily.copy()
daily_for_media_forecast['_date'] = pd.to_datetime(daily_for_media_forecast['消耗日期'])
quarter_media_cost = (
    daily_for_media_forecast[
        (daily_for_media_forecast['_date'] >= current_quarter_start) &
        (daily_for_media_forecast['_date'] <= latest_date)
    ]
    .groupby('媒体')['消耗']
    .sum()
    .to_dict()
)
quarter_media_daily_map = {
    media: (float(cost) / quarter_elapsed_days if quarter_elapsed_days > 0 else 0)
    for media, cost in quarter_media_cost.items()
}

center_year_media = daily.groupby('媒体')['消耗'].sum().reset_index().sort_values('消耗', ascending=False)
cym_total = center_year_media['消耗'].sum()
goal_year_media_map = (
    df_goal[df_goal['年'] == current_year]
    .groupby('媒体')['消耗目标']
    .sum()
    .to_dict()
)
center_year_media_list = []
for _, r in center_year_media.iterrows():
    media = r['媒体']
    cost = float(r['消耗'])
    target = float(goal_year_media_map.get(media, 0))
    quarter_daily = float(quarter_media_daily_map.get(media, 0))
    forecast = cost + quarter_daily * year_remaining_days
    center_year_media_list.append({
        'media': media,
        'cost': round(cost, 2),
        'target': round(target, 2),
        'has_target': target > 0,
        'completion_pct': round(cost / target * 100, 1) if target > 0 else None,
        'target_gap': round(cost - target, 2) if target > 0 else None,
        'quarter_daily_cost': round(quarter_daily, 2),
        'forecast': round(forecast, 2),
        'forecast_pct': round(forecast / target * 100, 1) if target > 0 else None,
        'forecast_gap': round(forecast - target, 2) if target > 0 else None,
        'pct': round(cost / cym_total * 100, 1) if cym_total > 0 else 0
    })

# 18. DEPT_STAFF_DATA: 各部门人员年度数据（年总消耗 + 年均日均消耗）
dept_staff_data = {}
for dept in dept_keys:
    sdf = df2[(df2['所属中心'] == '运营中心') & (df2['日期粒度'] == '年') & (df2['运营部门'] == dept) & (df2['团队粒度'] == '优化师')]
    if len(sdf) == 0:
        continue
    staff_list = []
    for _, r in sdf.iterrows():
        if pd.notna(r['姓名']):
            staff_list.append({
                'name': r['姓名'],
                'group': r['组别'] if pd.notna(r['组别']) else '',
                'total': round(r['消耗'], 2),
                'daily_avg': round(r['日均消耗'], 2),
                'pc': round(r['人均日耗'], 2)
            })
    dept_staff_data[dept] = staff_list

# 18. DEPT_STAFF_MONTHLY_DATA: 各部门人员月度日均消耗（用于人员表格+未达标月份统计）
dept_staff_monthly_data = {}
for dept in dept_keys:
    smdf = df2[(df2['所属中心'] == '运营中心') & (df2['日期粒度'] == '月') & (df2['运营部门'] == dept) & (df2['团队粒度'] == '优化师')].sort_values(['姓名', '月'])
    if len(smdf) == 0:
        continue
    staff_map = {}
    for _, r in smdf.iterrows():
        name = r['姓名'] if pd.notna(r['姓名']) else None
        if not name:
            continue
        if name not in staff_map:
            staff_map[name] = {'group': r['组别'] if pd.notna(r['组别']) else '', 'months': []}
        mo = str(r['月'])[5:7] if pd.notna(r['月']) else '?'
        staff_map[name]['months'].append({
            'month': mo,
            'cost': round(r['消耗'], 2),
            'daily_avg': round(r['日均消耗'], 2),
            'pc': round(r['人均日耗'], 2)
        })
    dept_staff_monthly_data[dept] = staff_map

# 19. WEEKLY_DEPT_AVG: 各部门近四周日均消耗（W1最早~W4最新，W4为当前周）
weekly_dept_keys = ['K2', 'K3', 'K4', 'K7', 'K4-品商', '品策-小红书']
df_weekly = df[(df['所属中心']=='运营中心') & (df['日期粒度']=='日')].copy()
df_weekly = df_weekly[~df_weekly['运营部门'].isin(['品策-其他'])]
df_weekly['消耗日期'] = pd.to_datetime(df_weekly['消耗日期'])
max_dt = df_weekly['消耗日期'].max()
weekday = max_dt.weekday()
current_mon = max_dt - timedelta(days=weekday)
week_defs = [
    {'label': 'W1', 'start': current_mon - timedelta(days=21), 'end': current_mon - timedelta(days=15)},
    {'label': 'W2', 'start': current_mon - timedelta(days=14), 'end': current_mon - timedelta(days=8)},
    {'label': 'W3', 'start': current_mon - timedelta(days=7),  'end': current_mon - timedelta(days=1)},
    {'label': 'W4', 'start': current_mon,                     'end': max_dt},
]
weekly_dept_avg = []
for dept in weekly_dept_keys:
    ddf = df_weekly[df_weekly['运营部门']==dept]
    row = {'dept': dept, 'weeks': []}
    for w in week_defs:
        wdf = ddf[(ddf['消耗日期']>=w['start']) & (ddf['消耗日期']<=w['end'])]
        if len(wdf) > 0:
            total = wdf['消耗'].sum()
        else:
            total = 0
        row['weeks'].append({
            'label': w['label'],
            'range': w['start'].strftime('%m/%d') + '~' + w['end'].strftime('%m/%d'),
            'total_cost': round(total, 2)
        })
    # W4 vs W3 总消耗波动值 = W4总消耗 - W3总消耗
    w4 = row['weeks'][3]['total_cost']
    w3 = row['weeks'][2]['total_cost']
    row['w4_vs_w3_diff'] = round(w4 - w3, 2)
    row['w4_vs_w3_pct'] = round((w4 - w3) / w3 * 100, 1) if w3 > 0 else None
    weekly_dept_avg.append(row)

# 19b. K部门汇总行（从 df_weekly 中筛选 K部门）
ddf_k = df_weekly[df_weekly['运营部门']=='K部门']
kdept_row = {'dept': 'K部门', 'weeks': [], '_is_kdept_sum': True}
for w in week_defs:
    wdf = ddf_k[(ddf_k['消耗日期']>=w['start']) & (ddf_k['消耗日期']<=w['end'])]
    if len(wdf) > 0:
        total = wdf['消耗'].sum()
    else:
        total = 0
    kdept_row['weeks'].append({
        'label': w['label'],
        'range': w['start'].strftime('%m/%d') + '~' + w['end'].strftime('%m/%d'),
        'total_cost': round(total, 2)
    })
w4 = kdept_row['weeks'][3]['total_cost']
w3 = kdept_row['weeks'][2]['total_cost']
kdept_row['w4_vs_w3_diff'] = round(w4 - w3, 2)
kdept_row['w4_vs_w3_pct'] = round((w4 - w3) / w3 * 100, 1) if w3 > 0 else None
weekly_dept_avg.insert(0, kdept_row)

# 20. WEEKLY_PROJ_ALERT: 项目级W4 vs W3日均环比>30%的项目（过滤日均<500元的噪音）
weekly_proj_alert = []
MIN_DAILY_THRESHOLD = 500
for dept in weekly_dept_keys:
    ddf = df_weekly[df_weekly['运营部门']==dept]
    w4df = ddf[(ddf['消耗日期']>=week_defs[3]['start']) & (ddf['消耗日期']<=week_defs[3]['end'])]
    w3df = ddf[(ddf['消耗日期']>=week_defs[2]['start']) & (ddf['消耗日期']<=week_defs[2]['end'])]
    if len(w4df) == 0 and len(w3df) == 0:
        continue
    w4_days = (week_defs[3]['end'] - week_defs[3]['start']).days + 1
    w3_days = 7
    w4_proj = w4df.groupby(['媒体','品牌名称'])['消耗'].sum() / w4_days if len(w4df) > 0 else pd.Series(dtype=float)
    w3_proj = w3df.groupby(['媒体','品牌名称'])['消耗'].sum() / w3_days if len(w3df) > 0 else pd.Series(dtype=float)
    all_proj = set(w4_proj.index) | set(w3_proj.index)
    for proj in all_proj:
        d4 = w4_proj.get(proj, 0)
        d3 = w3_proj.get(proj, 0)
        label = proj[0] + ' · ' + proj[1]  # 媒体 · 品牌名称
        if d3 > 0 and d4 > 0:
            pct = (d4 - d3) / d3 * 100
            if abs(pct) > 30 and (d4 >= MIN_DAILY_THRESHOLD or d3 >= MIN_DAILY_THRESHOLD):
                weekly_proj_alert.append({
                    'dept': dept,
                    'label': label,
                    'w4_daily': round(d4, 2),
                    'w3_daily': round(d3, 2),
                    'pct': round(pct, 1),
                    'type': 'normal'
                })
        elif d3 == 0 and d4 >= MIN_DAILY_THRESHOLD:
            # 新增项目：找到该项目在W4中最早的消耗日期
            proj_w4 = w4df[(w4df['媒体']==proj[0]) & (w4df['品牌名称']==proj[1])]
            first_date = proj_w4['消耗日期'].min().strftime('%m/%d') if len(proj_w4) > 0 else ''
            weekly_proj_alert.append({
                'dept': dept,
                'label': label,
                'w4_daily': round(d4, 2),
                'w3_daily': 0,
                'pct': None,
                'type': 'new',
                'date': first_date
            })
        elif d4 == 0 and d3 >= MIN_DAILY_THRESHOLD:
            # 停投项目：找到该项目在W3中最后的消耗日期
            proj_w3 = w3df[(w3df['媒体']==proj[0]) & (w3df['品牌名称']==proj[1])]
            last_date = proj_w3['消耗日期'].max().strftime('%m/%d') if len(proj_w3) > 0 else ''
            weekly_proj_alert.append({
                'dept': dept,
                'label': label,
                'w4_daily': 0,
                'w3_daily': round(d3, 2),
                'pct': None,
                'type': 'stop',
                'date': last_date
            })
# 排序：新增在上，正常按环比绝对值升序，停投在下
def _alert_sort_key(x):
    if x['type'] == 'new':
        return (0, 0)
    elif x['type'] == 'stop':
        return (2, 0)
    else:
        return (1, abs(x['pct']))
weekly_proj_alert.sort(key=_alert_sort_key)

# 输出统计
print(f'RAW_TREND: {len(raw_trend_list)} days')
print(f'MEDIA_DATA: {len(media_data)} media types: {list(media_data.keys())}')
print(f'CENTER_YEAR: {center_year}')
print(f'CENTER_MONTHS: {len(center_months)} months')
print(f'TEAM_DATA: {list(team_data.keys())}')
print(f'BRAND_DATA: {len(brand_daily)} rows')
print(f'DEPT_PC_DATA: {len(dept_pc_list)} departments')
print(f'CENTER_PC_DATA: {len(center_pc_list)} centers')
print(f'DEPT_YEAR_COST_DATA: {len(dept_cost_list)} departments')
print(f'ROI_DATA: {len(roi_list)} departments')
print(f'MONTH_TARGET: {len(month_target_list)} departments, month={max_month}, media={all_media}')
print(f'ACCOUNT_WEEK: {acct_week_label or "未使用周标签"}')
print(f'WEEK_METRIC_ANALYSIS: {", ".join(week_metric_analysis["weeks"]) if week_metric_analysis["weeks"] else "不足两周"}')
print(f'MONTH_DEPT_PC: {len(month_dept_pc_list)} departments')
print(f'MONTH_DEPT_BRAND_PC: {len(month_dept_brand_pc_list)} departments')
print(f'MONTH_DEPT_ACCT_PC: {len(month_dept_acct_pc_list)} departments')
print(f'MONTH_ROI: {len(month_roi_list)} departments')
print(f'MONTH_DEPT_ACCT_DAILY: {len(month_acct_daily_list)} departments')
print(f'DEPT_GROUP_DATA: {list(dept_group_data.keys())}')
print(f'DEPT_STAFF_DATA: {list(dept_staff_data.keys())}')
for d in dept_staff_data:
    print(f'  {d}: {len(dept_staff_data[d])} staff')
print(f'DEPT_STAFF_MONTHLY_DATA: {list(dept_staff_monthly_data.keys())}')

# 16. MONTH_CENTER: 运营中心当月数据（所属中心粒度）
mc_center = center_months[-1] if len(center_months) > 0 else {}
month_actual_center = mt_cost[
    mt_cost['运营部门'].notna() &
    (~mt_cost['运营部门'].isin(['K部门']))
]['消耗'].sum()
month_center = {
    'cost': round(month_actual_center, 2),
    'staff': mc_center.get('人效人数', 0),
    'target': round(goal_center_target, 2),
    'completion_pct': round(month_actual_center / goal_center_target * 100, 1) if goal_center_target else None,
}

latest_date = pd.to_datetime(raw_trend['消耗日期'].max()) if len(raw_trend) > 0 else pd.Timestamp.today()
current_year = int(latest_date.year)
current_quarter_num = int((latest_date.month - 1) // 3 + 1)
quarter_rows = df2[
    (df2['所属中心'] == '运营中心') &
    (df2['日期粒度'] == '季度') &
    (df2['团队粒度'] == '所属中心') &
    (df2['运营部门'].isna())
].copy()
quarter_daily_cost = 0
if len(quarter_rows) > 0:
    def parse_quarter_num(value):
        if pd.isna(value):
            return None
        if isinstance(value, (int, float)) and not pd.isna(value):
            return int(value)
        text = str(value)
        match = re.search(r'Q([1-4])|第?([1-4])季|([1-4])$', text, re.IGNORECASE)
        if match:
            return int(next(g for g in match.groups() if g))
        try:
            return int(pd.Timestamp(value).quarter)
        except Exception:
            return None

    quarter_rows['_quarter_num'] = quarter_rows['季度'].apply(parse_quarter_num)
    current_quarter_rows = quarter_rows[quarter_rows['_quarter_num'] == current_quarter_num]
    if len(current_quarter_rows) == 0:
        current_quarter_rows = quarter_rows.tail(1)
    quarter_daily_cost = float(current_quarter_rows.iloc[-1]['日均消耗'])

year_target_total = float(df_goal[df_goal['年'] == current_year]['消耗目标'].sum())
year_actual_total = float(center_year.get('消耗', 0))
days_in_year = 366 if ((current_year % 4 == 0 and current_year % 100 != 0) or current_year % 400 == 0) else 365
year_elapsed_days = int((latest_date - pd.Timestamp(year=current_year, month=1, day=1)).days + 1)
year_remaining_days = max(days_in_year - year_elapsed_days, 0)
year_forecast = year_actual_total + quarter_daily_cost * year_remaining_days

month_days = latest_date.days_in_month
month_elapsed_days = int(latest_date.day)
month_remaining_days = max(month_days - month_elapsed_days, 0)
month_daily_cost = float(mc_center.get('日均消耗', 0))
month_pc = float(mc_center.get('人均日耗', 0))
month_forecast = month_actual_center + month_daily_cost * month_remaining_days

report_flow_overview = {
    'date': latest_date.strftime('%Y-%m-%d'),
    'year': {
        'year': current_year,
        'elapsed_days': year_elapsed_days,
        'remaining_days': year_remaining_days,
        'time_pct': round(year_elapsed_days / days_in_year * 100, 1) if days_in_year else 0,
        'cost': round(year_actual_total, 2),
        'daily_cost': round(float(center_year.get('日均消耗', 0)), 2),
        'pc': round(float(center_year.get('人均日耗', 0)), 2),
        'monthly_avg': round(year_actual_total / (max_month_num - 1 + month_elapsed_days / month_days), 2) if month_days else 0,
        'target': round(year_target_total, 2),
        'completion_pct': round(year_actual_total / year_target_total * 100, 1) if year_target_total else None,
        'quarter_daily_cost': round(quarter_daily_cost, 2),
        'forecast': round(year_forecast, 2),
        'forecast_pct': round(year_forecast / year_target_total * 100, 1) if year_target_total else None,
        'forecast_gap': round(year_forecast - year_target_total, 2) if year_target_total else None,
    },
    'month': {
        'month': str(max_month)[:7] if pd.notna(max_month) else '',
        'elapsed_days': month_elapsed_days,
        'remaining_days': month_remaining_days,
        'time_pct': round(month_elapsed_days / month_days * 100, 1) if month_days else 0,
        'cost': round(month_actual_center, 2),
        'daily_cost': round(month_daily_cost, 2),
        'pc': round(month_pc, 2),
        'target': round(goal_center_target, 2),
        'completion_pct': round(month_actual_center / goal_center_target * 100, 1) if goal_center_target else None,
        'forecast': round(month_forecast, 2),
        'forecast_pct': round(month_forecast / goal_center_target * 100, 1) if goal_center_target else None,
        'forecast_gap': round(month_forecast - goal_center_target, 2) if goal_center_target else None,
    },
}

# 确保6个子部门都有key，没有ROI数据的用空数组
dept_monthly_roi_payload = {dept: dept_monthly_roi.get(dept, []) for dept in dept_keys + ['K部门']}

payload = {
    'meta': {
        'source': 'ads',
        'source_team_table': team_table,
        'source_project_table': project_table,
        'source_manual_excel': str(manual_xlsx),
        'sheets': {
            'team': TEAM_SHEET,
            'project': PROJECT_SHEET,
            'roi': ROI_SHEET,
            'goal': GOAL_SHEET,
        },
        'account_week': acct_week_label or '',
        'analysis_weeks': week_metric_analysis['weeks'],
    },
    'RAW_TREND': raw_trend_list,
    'MEDIA_DATA': media_data,
    'CENTER_YEAR': center_year,
    'CENTER_MONTHS': center_months,
    'TEAM_DATA': team_data,
    'BRAND_DATA': brand_daily,
    'DEPT_PC_DATA': dept_pc_list,
    'CENTER_PC_DATA': center_pc_list,
    'DEPT_YEAR_COST_DATA': dept_cost_list,
    'ROI_DATA': roi_list,
    'DEPT_MONTHLY_ROI': dept_monthly_roi_payload,
    'MONTH_CENTER': month_center,
    'REPORT_FLOW_OVERVIEW': report_flow_overview,
    'MONTH_TARGET': month_target_list,
    'MONTH_MEDIA_LIST': all_media,
    'MONTH_DEPT_PC': month_dept_pc_list,
    'MONTH_DEPT_BRAND_PC': month_dept_brand_pc_list,
    'MONTH_DEPT_ACCT_PC': month_dept_acct_pc_list,
    'MONTH_ROI': month_roi_list,
    'MONTH_DEPT_ACCT_DAILY': month_acct_daily_list,
    'WEEK_METRIC_ANALYSIS': week_metric_analysis,
    'MONTH_MEDIA_TABLE': month_media_table,
    'MONTH_MEDIA_SUB_DEPTS': sub_dept_keys,
    'CENTER_YEAR_MEDIA': center_year_media_list,
    'DEPT_GROUP_DATA': dept_group_data,
    'DEPT_STAFF_DATA': dept_staff_data,
    'DEPT_STAFF_MONTHLY_DATA': dept_staff_monthly_data,
    'WEEKLY_DEPT_AVG': weekly_dept_avg,
    'WEEKLY_PROJ_ALERT': weekly_proj_alert,
}

json_text = json.dumps(payload, ensure_ascii=False, indent=2)
json_out = BASE_DIR / 'data' / 'weekly_dashboard_data.json'
json_out.parent.mkdir(parents=True, exist_ok=True)
with open(json_out, 'w', encoding='utf-8') as f:
    f.write(json_text + '\n')

js = '// === 由 gen_data.py 自动生成，请勿手动修改 ===\n'
js += '(function(global){\n'
js += '  global.WEEKLY_DASHBOARD_DATA = ' + json.dumps(payload, ensure_ascii=False) + ';\n'
js += '})(typeof window !== "undefined" ? window : globalThis);\n'

out = BASE_DIR / 'data.js'
with open(out, 'w', encoding='utf-8') as f:
    f.write(js)
print(f'\nweekly_dashboard_data.json generated: {json_out} ({len(json_text)} chars)')
print(f'data.js generated: {out} ({len(js)} chars)')

# 运营团队周报

这是一个静态运营周报看板。自动数据直接读取 ADS 数据库表，人工维护数据读取 Excel，页面使用 HTML、JavaScript 和 ECharts 展示。

运营周报和 `D:\yyzx_data\代运营报表` 共用同一套数据源入口：

```text
D:\yyzx_data\运营_共享\data_sources.py
```

这意味着周报和代运营仪表盘的数据来源保持一致：自动指标来自 ADS 表，人工维护项来自 `运营团队手动维护数据.xlsx`。

## 文件说明

- `index.html`: 周报页面入口，浏览器打开这个文件即可查看看板。
- `data.js`: 自动生成的数据入口，请不要手动修改；它会把结构化数据挂到 `window.WEEKLY_DASHBOARD_DATA`。
- `data/weekly_dashboard_data.json`: 自动生成的结构化数据 payload，供后续复用或排查。
- `dashboard.js`: 页面交互和图表渲染逻辑。
- `gen_data.py`: 从 ADS 表和人工维护 Excel 生成 `data.js` 的脚本。

## 数据源说明

自动指标来自数据库 ADS 表：

```text
ads_team_dimension_metrics
ads_project_dimension_metrics
```

人工维护数据来自：

```text
D:\yyzx_data\运营团队手动维护数据.xlsx
```

周报当前需要人工维护 sheet：

```text
投入产出
消耗目标
```

`运营团队BI报表.xlsx` 现在只是可选导出的线下 Excel 文件，不再作为周报数据源。

## 更新数据

默认情况下，脚本会读取两张 ADS 表：

```text
ads_team_dimension_metrics
ads_project_dimension_metrics
```

人工维护数据文件 `运营团队手动维护数据.xlsx`：

1. 命令行 `--manual-excel` 指定的路径
2. 环境变量 `YYZX_MANUAL_EXCEL`
3. `D:\yyzx_data\运营团队手动维护数据.xlsx`

常用命令：

```powershell
python gen_data.py
```

指定 Excel 路径：

```powershell
python gen_data.py --manual-excel "D:\yyzx_data\运营团队手动维护数据.xlsx"
```

指定 ADS 表名：

```powershell
python gen_data.py --team-table ads_team_dimension_metrics --project-table ads_project_dimension_metrics
```

生成成功后会更新当前目录的 `data.js`。

如果需要先更新 ADS 指标表，请先运行：

```powershell
python D:\yyzx_data\generate_yyzx_data.py
```

如果月底或需要同步线下 Excel：

```powershell
python D:\yyzx_data\generate_yyzx_data.py --update-excel
```

当前脚本使用的主要 sheet：

- `项目维度`: 媒体、品牌、项目、周度波动、账户数等消耗数据。
- `团队维度`: 中心、部门、组别、人员维度的消耗、人效、品牌数、产品数、账户数等数据。
- `投入产出`: 年度、月度 ROI / 投产比数据，来自 `运营团队手动维护数据.xlsx`。
- `消耗目标`: 年度、月度部门目标数据，来自 `运营团队手动维护数据.xlsx`。

## 查看页面

直接打开：

```text
index.html
```

页面需要能访问 ECharts CDN。如果离线使用，后续可以把 ECharts 下载到本地后再改引用。

## 维护约定

- 改数据处理逻辑：修改 `gen_data.py`，再重新运行生成。
- 改页面展示或交互：修改 `dashboard.js`。
- 改页面结构或样式：修改 `index.html`。
- 不要手动改 `data.js`，它会被生成脚本覆盖。
- 不要把人工维护 sheet 放回 `运营团队BI报表.xlsx`，统一维护在 `D:\yyzx_data\运营团队手动维护数据.xlsx`。
- 如果周报和代运营仪表盘的数据源规则要一起调整，优先改 `D:\yyzx_data\运营_共享\data_sources.py`。

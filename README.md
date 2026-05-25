# 运营团队周报

这是一个静态运营周报看板。数据由 Excel 汇总生成，页面使用 HTML、JavaScript 和 ECharts 展示。

## 文件说明

- `index_weekly.html`: 周报页面入口，浏览器打开这个文件即可查看看板。
- `data.js`: 自动生成的数据入口，请不要手动修改；它会把结构化数据挂到 `window.WEEKLY_DASHBOARD_DATA`。
- `data/weekly_dashboard_data.json`: 自动生成的结构化数据 payload，供后续复用或排查。
- `dashboard.js`: 页面交互和图表渲染逻辑。
- `gen_data.py`: 从 Excel 生成 `data.js` 的脚本。
- `index_weekly_standalone.html`: 单文件归档/分享版，目前不会自动随 `data.js` 更新。

## 更新数据

默认情况下，脚本会按顺序查找 Excel 文件：

1. 命令行 `--excel` 指定的路径
2. 环境变量 `YYZX_EXCEL`
3. 当前目录下的 `运营团队BI报表.xlsx`
4. 上级目录下的 `运营团队BI报表.xlsx`

常用命令：

```powershell
python gen_data.py
```

指定 Excel 路径：

```powershell
python gen_data.py --excel "D:\yyzx_data\运营团队BI报表.xlsx"
```

生成成功后会更新当前目录的 `data.js`。

当前脚本使用的主要 sheet：

- `项目维度`: 媒体、品牌、项目、周度波动、账户数等消耗数据。
- `团队维度`: 中心、部门、组别、人员维度的消耗、人效、品牌数、产品数、账户数等数据。
- `投入产出`: 年度、月度 ROI / 投产比数据。

## 查看页面

直接打开：

```text
index_weekly.html
```

页面需要能访问 ECharts CDN。如果离线使用，后续可以把 ECharts 下载到本地后再改引用。

## 维护约定

- 改数据处理逻辑：修改 `gen_data.py`，再重新运行生成。
- 改页面展示或交互：修改 `dashboard.js`。
- 改页面结构或样式：修改 `index_weekly.html`。
- 不要手动改 `data.js`，它会被生成脚本覆盖。

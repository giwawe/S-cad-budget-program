# 项目状态与 GUI 前置收口

更新时间：2026-07-02

## 当前结论

项目已经具备进入图形界面第一版设计的基础。CAD 导入、算量、商品房整装报价、全局单价表、真实模板回归和一键验收入口都已落地。GUI 前还需要做的是产品边界确认和界面服务接口整理，不再需要补一大块核心算量能力。

## 已完成能力

- DXF/DWG 导入路径已建立：DXF 直接导入，DWG 通过外部转换器先转 DXF。
- `QUOTE_*` 图层规范已覆盖空间、文字、窗、门、墙、开放边界、外墙、建筑面积、拆改、新砌墙、过梁、管道、局部墙砖、背景墙、淋浴房、蹲坑、全屋定制和橱柜。
- `ProjectInput` 到 `QuantityResult` 的算量主流程已稳定，Excel 算量表可导出和回读。
- 商品房整装报价可从 `QuantityResult` 和真实模板生成报价 Excel。
- 全局单价表按 `项目名称 + 单位` 去重维护，重复项目只改一次，后续方案复用同一套单价。
- `priced-quote` 可一键生成正式报价包：`quote-priced.xlsx`、`quote-priced-review.md`、`quote-priced-review.json`、`quote-priced-review-checklist.xlsx`。
- 真实模板关键业务数值已固化，当前一键验收入口为：

```powershell
$env:PYTHONPATH='src'; py -3.14 scripts\run_real_acceptance.py
```

- 当前全量测试基线：`281 passed, 80 warnings`。

## 当前真实模板验收口径

默认输入：

- DXF：`D:\Desktop\10.dxf`
- 模板：`D:\Desktop\清单式报价表（商品房）-修正版.xlsx`
- 单价表：`scratch\cad-import-10-real-template-current\quote-unit-prices.xlsx`

默认输出：

- 回归输出：`scratch\cad-import-10-real-template-current`
- 正式报价包：`scratch\cad-import-10-real-template-priced-command`

`quote-priced.xlsx` 已使用当前报价草稿外壳：顶部包含地址、客户、装修面积、日期栏，装修面积来自 `QuantityResult.building_area`；表尾包含 `编制说明` 和客户、设计师、报价员签名栏。

当前验收统计：

| 指标 | 当前值 |
| --- | ---: |
| 自动算量 | 53 |
| 自动汇总 | 46 |
| 模板默认 | 0 |
| 自动生成-默认推断 | 38 |
| 自动生成-异常提示 | 0 |
| 按模板生成 | 0 |
| high 复核行动 | 3 |
| medium 复核行动 | 3 |
| low 复核行动 | 0 |
| 正式报价单价匹配行 | 99 |

已业务确认的关键数量包括：暗窗帘箱只进普通干区有窗空间、主卧 L 形窗合并宽度 3.467m、厨房墙砖 14.954467㎡、室内门 3、厨房推拉门面积 3.843228㎡、厨房推拉门双包套 6.146922m、建筑面积 136.237652㎡、地面砖现场维护费使用室内地面面积 116.615998㎡。

## 必须保持

- 修改 `LayerName`、`dxf_adapter.py`、`quantity.py`、Excel/报价对 CAD 结果的使用口径，或新增/变更 CAD 图层、块属性、单位规则、几何推断规则、异常口径时，必须同步更新 `docs/cad-lightweight-drawing-standard-zh.md`。
- 修改 CAD/算量/报价规则后，至少运行：

```powershell
$env:PYTHONPATH='src'; py -3.14 scripts\run_real_acceptance.py
$env:PYTHONPATH='src'; py -3.14 -m pytest -q
```

- `scripts\run_real_acceptance.py` 只做真实业务验收；全量 pytest 保持独立运行，避免验收入口变慢且职责混杂。
- 真实业务单价不提交仓库；`config/quote-unit-prices.xlsx` 已在 `.gitignore` 中。

## 必须做

- GUI v1 需求边界已记录在 `docs/gui-v1-scope-zh.md`。
- GUI 前置服务接口清单已记录在 `docs/gui-v1-service-interface-zh.md`。
- GUI v1 视觉设计 brief 已记录在 `docs/gui-v1-visual-design-brief-zh.md`。
- GUI 技术选型结论：预算员/设计师使用场景优先 `PySide6`；如果只做开发者内部工具才考虑 `Textual`。

## GUI 前必须做

- `src/cad_budget/gui_services.py` 已新增，当前封装真实验收入口为 GUI 友好的请求/响应接口。
- GUI 服务层已补单元测试，覆盖成功摘要、输入文件缺失、pipeline 失败和正式报价包校验失败。
- `PySide6` 已加入可选依赖：`pip install -e ".[gui]"`。
- GUI 骨架入口已新增：`cad-budget-gui`。

## GUI 实现建议

- 第一轮实现 `PySide6` 桌面操作台。
- 主界面已具备运行、结果、设置三页骨架；下一步接入文件选择、运行按钮、摘要统计、复核行动列表、输出路径和打开目录。
- 核心业务通过 GUI 服务层调用，不在界面层拼长命令。
- 开发阶段可以调用设计类 skill 辅助视觉方案和设计评审；交付后的 GUI 运行时不依赖 Codex skill。

## 进入 GUI 的建议范围

GUI v1 应保持轻量：选择 DXF、模板、单价表和输出目录，点击运行，展示验收统计、复核行动、输出文件路径，并提供打开输出目录按钮。第一版不要做 CAD 编辑器、报价 Excel 编辑器或复杂主材库管理。

## GUI 当前状态：可试用

- `src/cad_budget/gui_controller.py` 已新增，用于把 GUI 选择的 DXF、模板、单价表和输出根目录转换成真实验收请求，并格式化运行摘要。
- `cad-budget-gui` 主窗口已接入文件选择、后台线程运行真实验收、结果摘要刷新和打开输出目录按钮。
- GUI 运行时会把用户选择的输出根目录映射为 `cad-import-10-real-template-current` 和 `cad-import-10-real-template-priced-command` 两个子目录，保持与现有验收路径一致。
- GUI 结果页已新增关键输出文件列表，窗口已加入第一版基础 QSS 样式。
- GUI 已预填真实验收默认路径，并支持把默认路径保存到本地 `gui-settings.json`。
- GUI 输出文件表已支持双击用系统文件管理器打开文件；运行失败会显示中文阶段名。
- 已安装 `PySide6` 并用 Windows Qt 平台做过 GUI 截图验收：默认路径页和真实验收结果页中文正常、无明显布局重叠。
- GUI v1 使用说明已记录在 `docs/gui-v1-user-guide-zh.md`。
- GUI v1 主按钮口径已确认：当前使用“运行真实验收”作为主按钮；单独“生成正式报价”按钮放入 v1.1 范围。

## 后续增强

- GUI 内部报价编辑器。
- CAD 图纸可视化预览或图层检查。
- 从 Excel 回读后闭环写回项目源数据或 CAD 标注。
- 更细的多项目单价库、客户方案管理、历史报价对比。

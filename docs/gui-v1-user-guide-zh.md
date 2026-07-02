# GUI v1 使用说明

## 安装

在项目根目录安装 GUI 可选依赖：

```powershell
pip install -e ".[gui]"
```

## 启动

```powershell
cad-budget-gui
```

## 默认路径

首次打开会预填当前真实验收路径：

- DXF：`D:\Desktop\10.dxf`
- 报价模板：`D:\Desktop\清单式报价表（商品房）-修正版.xlsx`
- 单价表：`scratch\cad-import-10-real-template-current\quote-unit-prices.xlsx`
- 输出目录：`scratch`

可以在“设置”页修改默认路径，并点击“保存默认路径”。保存后再次打开 GUI 会自动读回本地 `gui-settings.json`。

## 运行真实验收

在“运行”页确认 DXF、报价模板、单价表和输出目录后，点击“运行真实验收”。

当前 v1 主按钮会执行完整真实验收流程，并生成正式报价包。普通用户不需要单独运行命令行。

输出目录会自动分成两个子目录：

- `cad-import-10-real-template-current`
- `cad-import-10-real-template-priced-command`

## 查看与打开输出

运行完成后 GUI 会切到“结果”页，显示自动算量、自动汇总、默认推断、复核行动和单价匹配统计。

“输出文件”表列出正式报价表、复核报告、复核数据、复核清单和运行摘要。双击文件行可以用系统文件管理器打开对应文件；也可以点击“打开输出目录”打开最近一次正式报价包目录。

## 按钮口径

GUI v1 以“运行真实验收”作为主按钮，因为它已经会生成正式报价包并校验关键业务结果。

“生成正式报价”单独按钮暂定为 v1.1 范围，用于后续支持不跑真实模板断言的普通项目报价生成。

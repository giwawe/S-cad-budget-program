# 商品房报价全局单价表维护流程

全局单价表用于维护所有报价共用的单价。它按精确 `项目名称 + 单位` 去重，重复空间项目只需要改一次，后续新增方案也会使用同一套主材、辅材、人工单价。

## 默认位置

项目默认单价表路径：

```powershell
config\quote-unit-prices.xlsx
```

`cad-budget quote` 在没有传 `--unit-prices` 时，如果当前工作目录存在这个文件，会自动使用它覆盖模板单价。

真实业务价格不提交到仓库。根目录 `.gitignore` 已忽略 `config/quote-unit-prices.xlsx`，当前真实样例使用的单价表仍保留在：

```powershell
scratch\cad-import-10-real-template-current\quote-unit-prices.xlsx
```

## 初始化

从模板或已生成报价导出默认单价表：

```powershell
cad-budget init-prices "D:\Desktop\清单式报价表（商品房）-修正版.xlsx"
```

如果要写到自定义位置：

```powershell
cad-budget init-prices "D:\Desktop\清单式报价表（商品房）-修正版.xlsx" --output scratch\cad-import-10-real-template-current\quote-unit-prices.xlsx
```

`init-prices` 不覆盖已有文件，避免误改预算员维护过的价格。

## 修改与校验

预算员只维护三列：

- `主材单价`
- `辅材单价`
- `人工单价`

修改后运行：

```powershell
cad-budget check-prices config\quote-unit-prices.xlsx
```

校验会拦截空单价、非数字单价，以及同一 `项目名称 + 单位` 出现冲突价格。

## 生成正式报价

使用默认单价表：

```powershell
cad-budget priced-quote result.json --template "D:\Desktop\清单式报价表（商品房）-修正版.xlsx" --output-dir scratch\cad-import-10-real-template-priced-command
```

使用显式单价表：

```powershell
cad-budget priced-quote result.json --template "D:\Desktop\清单式报价表（商品房）-修正版.xlsx" --unit-prices scratch\cad-import-10-real-template-current\quote-unit-prices.xlsx --output-dir scratch\cad-import-10-real-template-priced-command
```

正式报价会输出：

- `quote-priced.xlsx`
- `quote-priced-review.md`
- `quote-priced-review.json`
- `quote-priced-review-checklist.xlsx`

## 输出校验

生成正式报价后运行：

```powershell
$env:PYTHONPATH='src'; py -3.14 scripts\check_priced_quote_outputs.py --output-dir scratch\cad-import-10-real-template-priced-command --unit-prices scratch\cad-import-10-real-template-current\quote-unit-prices.xlsx
```

该脚本会检查四个正式输出文件是否存在、右侧自动化统计是否符合真实模板当前预期、复核状态统计是否符合当前预期，并确认报价行已套用单价表中匹配的单价。

也可以在真实模板回归时一次生成并校验正式报价包：

```powershell
$env:PYTHONPATH='src'; py -3.14 scripts\run_real_template_quote_review.py --unit-prices scratch\cad-import-10-real-template-current\quote-unit-prices.xlsx --priced-output-dir scratch\cad-import-10-real-template-priced-command --check-priced-output
```

该命令会继续写 `scratch\cad-import-10-real-template-current` 下的算量和普通报价回归文件，同时写 `scratch\cad-import-10-real-template-priced-command` 下的正式报价四件套，并把正式报价包校验结果记录到 `summary.json`。

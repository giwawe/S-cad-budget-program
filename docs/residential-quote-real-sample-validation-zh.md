# 商品房真实样例报价自动化验收记录

本文记录当前真实商品房样例与 `marker-rich` 对照样例的自动化覆盖差距，用于指导下一轮 CAD 补标识和回归验收。

## 样例来源

- 真实样例报价：`scratch/cad-import-test/quote-ext-repair.xlsx`
- 真实样例算量：`scratch/cad-import-test/result-building-area.json`
- 对照样例生成命令：

```powershell
$env:PYTHONPATH='src'; py -3.14 scripts\generate_marker_rich_quote_sample.py --output-dir scratch\marker-rich-quote-sample
```

## 当前统计

| 样例 | 自动算量 | 自动汇总 | 模板默认 |
| --- | ---: | ---: | ---: |
| 真实样例 | 47 | 28 | 17 |
| marker-rich 对照样例 | 0 | 12 | 1 |

真实样例当前关键缺口：

- `building_area=None`
- `exterior_rows=0`
- `construction_details=0`
- `custom_details=0`
- `cabinet_details=0`
- 无匹配的阳台/露台宽门洞

marker-rich 对照样例证明以下数据源接通后可稳定生成：

- `building_area=36.0`
- `exterior_rows=1`
- `construction_details=6`
- `custom_details=1`
- `cabinet_details=1`
- 阳台推拉门与双包套行可自动汇总

## 真实样例仍为模板默认的 17 项

### 补 CAD 标识后可自动汇总

| 报价项 | 当前模板数量 | 需要补齐的数据源 | 补齐后口径 |
| --- | ---: | --- | --- |
| 拆改及拆墙 | 93 | `QUOTE_DEMO_WALL`，建议写 `HEIGHT` | 拆改墙线长度乘高度汇总 |
| 砌120厚砖墙 | 44.8 | `QUOTE_NEW_WALL`，`THICKNESS=120`，建议写 `HEIGHT` | 新砌 120mm 墙面积汇总 |
| 砌240厚砖墙 | 64.56 | `QUOTE_NEW_WALL`，`THICKNESS=240`，建议写 `HEIGHT` | 新砌 240mm 墙面积汇总 |
| 外墙批嵌 | 235 | `QUOTE_EXT_WALL`、`QUOTE_EXT_OPENING`，相邻户外墙用 `QUOTE_INCLUDE=false` 排除 | 选定外墙净面积汇总，扣除外墙洞口 |
| 外墙批嵌以及修补 | 25.3 | `QUOTE_EXT_REPAIR` | 明确修补范围面积汇总 |
| 打混凝土过梁孔 | 108 | 闭合 `QUOTE_EXT_WALL` 或闭合 `QUOTE_BUILDING_AREA` | 建筑面积的 10% 取整 |
| 厨房、卫生间排污管包隔音棉 | 50 | `QUOTE_PIPE_INSULATION`，建议写 `HEIGHT` | 排污管隔音棉立管长度汇总 |
| 包上/下水管道(单管) | 36 | `QUOTE_PIPE_WRAP`，建议写 `HEIGHT` | 包管立管长度汇总 |
| 全屋定制 | 66 | `QUOTE_CUSTOM` | 投影面积汇总，缺高默认 2.6m；低于 1m 的柜体提示按长度复核 |
| 橱柜 | 22 | `QUOTE_BASE_CABINET` / `QUOTE_WALL_CABINET`，旧图可用 `QUOTE_CABINET + TYPE` | 橱柜长度汇总；地柜、吊柜可重叠画线，不自动去重 |
| 阳台推拉门 | 4.6 | 阳台/露台空间内宽度大于等于 1.4m 的 `QUOTE_DOOR` | 宽门洞面积汇总，缺高默认 2.1m |
| 阳台推拉门双包套 | 6 | 与阳台推拉门同源的宽门洞 | 门洞宽度加两侧有效门高汇总 |

### 继续保留人工/模板默认

| 报价项 | 当前模板数量 | 保留原因 |
| --- | ---: | --- |
| 砖墙门窗洞过梁 | 15 | 只有新增门洞需要过梁，当前仍由设计师人工填写 |
| 背景墙 | 60 | 背景墙范围和造型口径待定，不能从普通墙面面积硬推 |
| 入户门 | 1 | 是否更换属于主材/套餐选择，不是 CAD 算量结果 |
| 蹲坑 | 1 | 卫生间数量不能判断坐便/蹲坑配置 |
| 玻璃淋浴房 | 6 | 已有 `淋浴隔断` 按卫生间数量自动汇总，玻璃淋浴房默认保留以避免重复报价 |

## 验收步骤

1. 设计师按 `docs/residential-quote-sample-cad-marker-checklist-zh.md` 补齐上述 CAD 标识。
2. 重新导入 CAD，生成 `project.json`。
3. 重新计算算量，检查：
   - `building_area` 有值。
   - `exterior_rows` 包含外墙行。
   - `construction_details` 包含拆改、新砌墙、管道、外墙修补明细。
   - 房间行包含 `custom_details`、`cabinet_details` 和阳台/露台宽门洞明细。
4. 重新生成报价 Excel。
5. 期望 `模板默认` 至少减少 12 行；如果补齐所有上述标识，剩余模板默认应主要是 5 个人工项。
6. 抽查每个自动汇总行的 `数量来源`、`计量口径`、`复核状态` 和 `复核备注`。

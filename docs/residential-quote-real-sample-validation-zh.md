# 商品房真实样例报价自动化验收记录

本文记录当前真实商品房样例与 `marker-rich` 对照样例的自动化覆盖差距，用于指导下一轮 CAD 补标识和回归验收。

## 样例来源

- 真实样例报价：`scratch/cad-import-10-cabinet-footprint/quote.xlsx`
- 真实样例算量：`scratch/cad-import-10-cabinet-footprint/result.json`
- 对照样例生成命令：

```powershell
$env:PYTHONPATH='src'; py -3.14 scripts\generate_marker_rich_quote_sample.py --output-dir scratch\marker-rich-quote-sample
```

## 当前统计

| 样例 | 自动算量 | 自动汇总 | 模板默认 |
| --- | ---: | ---: | ---: |
| 真实样例 | 47 | 41 | 5 |
| marker-rich 对照样例 | 0 | 16 | 1 |

真实样例当前关键缺口：

- `building_area=136.237652`
- `exterior_rows=1`
- `construction_details=4`，包含新砌墙和 `QUOTE_WALL_TILE`，暂无 `QUOTE_LINTEL`、拆墙、管道或外墙修补标识
- `custom_details=10`
- `cabinet_details=4`
- 无匹配的阳台/露台宽门洞

marker-rich 对照样例证明以下数据源接通后可稳定生成：

- `building_area=36.0`
- `exterior_rows=1`
- `construction_details=7`
- `custom_details=1`
- `cabinet_details=1`
- `QUOTE_WALL_TILE` 非湿区局部墙砖面积进入墙面瓷砖片数和美缝面积
- 阳台推拉门与双包套行可自动汇总

## 真实样例仍为模板默认的 5 项

### 最新样例已自动汇总的能力

| 报价项 | 数据源 | 当前口径 |
| --- | --- | --- |
| 砌120厚砖墙 / 砌240厚砖墙 | `QUOTE_NEW_WALL`，`THICKNESS=120/240` | 新砌墙面积按厚度归类汇总，未填厚度按 240mm |
| 外墙批嵌 | `QUOTE_EXT_WALL`、`QUOTE_EXT_OPENING` | 选定外墙净面积汇总，扣除外墙洞口 |
| 打混凝土过梁孔 | 闭合 `QUOTE_EXT_WALL` 或闭合 `QUOTE_BUILDING_AREA` | 建筑面积的 10% 取整 |
| 全屋定制 | `QUOTE_CUSTOM` | 投影面积汇总，缺高默认 2.6m；低于 1m 的柜体提示按长度复核 |
| 地柜 / 吊柜 | `QUOTE_BASE_CABINET` / `QUOTE_WALL_CABINET`，旧图可用 `QUOTE_CABINET + TYPE` | 按地柜、吊柜分别汇总长度；闭合轮廓按占地面积除以推断柜深折算 |
| 非湿区局部墙砖 | `QUOTE_WALL_TILE` | 局部墙砖面积并入 `墙面瓷砖` 片数和 `美缝` 面积；湿区不重复叠加 |

### 补 CAD 标识后可自动汇总

| 报价项 | 当前模板数量 | 需要补齐的数据源 | 补齐后口径 |
| --- | ---: | --- | --- |
| 砖墙门窗洞过梁 | 15 | `QUOTE_LINTEL` | 每个新增门窗洞过梁标识按 1 支过梁计；未标识时保持模板默认 |

### 继续保留人工/模板默认

| 报价项 | 当前模板数量 | 保留原因 |
| --- | ---: | --- |
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
5. 最新样例 `模板默认` 为 5 行；如果补齐 `QUOTE_LINTEL`，剩余模板默认应主要是背景墙、入户门、蹲坑、玻璃淋浴房等人工项。
6. 抽查每个自动汇总行的 `数量来源`、`计量口径`、`复核状态` 和 `复核备注`。

# 商品房整装报价剩余模板默认项审计

审计基于真实样例 `scratch/cad-import-test/quote-ext-repair.xlsx`。当前样例统计为：

- 自动算量：47 行
- 自动汇总：28 行
- 模板默认：17 行

本文件只记录“现有算量结果是否足以继续自动化”。原则是：没有可靠 CAD / 算量来源的项目继续保留模板默认，不为了降低默认行数而硬推断。

## 当前样例仍为模板默认，但能力已具备

这些项目已经有自动化规则；当前真实样例保持模板默认，是因为 `scratch/cad-import-test/result-building-area.json` 中没有对应 CAD 标识、外墙行、建筑面积或匹配门洞。后续设计师按规范补图层后即可自动汇总。

| 项目 | 当前样例状态 | 已支持的数据来源 | 当前样例默认原因 |
| --- | --- | --- | --- |
| 外墙批嵌 | 模板默认 | `exterior_rows.net_area`，`QUOTE_EXT_WALL` 可用 `CAD_BUDGET` XDATA `QUOTE_INCLUDE=false` / `INCLUDE=false` 排除 | 当前样例 `exterior_rows=0`，没有可汇总外墙面 |
| 外墙批嵌以及修补 | 模板默认 | `QUOTE_EXT_REPAIR` 生成的 `construction_details.exterior_repair` 面积 | 当前样例无 `QUOTE_EXT_REPAIR` 修补范围 |
| 拆改及拆墙 | 模板默认 | `QUOTE_DEMO_WALL` 面积 | 当前样例无拆墙标识 |
| 砌120厚砖墙 | 模板默认 | `QUOTE_NEW_WALL` 面积，且 `THICKNESS=120mm/0.12m` | 当前样例无新砌墙标识 |
| 砌240厚砖墙 | 模板默认 | `QUOTE_NEW_WALL` 面积，且 `THICKNESS=240mm/0.24m` | 当前样例无新砌墙标识 |
| 打混凝土过梁孔 | 模板默认 | `QuantityResult.building_area` 的 10% 取整数 | 当前样例 `building_area=None`，没有闭合 `QUOTE_EXT_WALL` 或闭合 `QUOTE_BUILDING_AREA` |
| 厨房、卫生间排污管包隔音棉 | 模板默认 | `QUOTE_PIPE_INSULATION` 立管长度 | 当前样例无管道隔音棉标识 |
| 包上/下水管道(单管) | 模板默认 | `QUOTE_PIPE_WRAP` 立管长度 | 当前样例无包管标识 |
| 全屋定制 | 模板默认 | `QUOTE_CUSTOM` 投影面积；缺高默认 2.6m；低于 1m 的柜体按长度复核 | 当前样例无全屋定制标识 |
| 橱柜 | 模板默认 | `QUOTE_CABINET` 长度 | 当前样例无橱柜标识 |
| 阳台推拉门 | 模板默认 | 阳台/露台空间中宽度大于等于 1.4m 的唯一门洞面积 | 当前样例无匹配阳台/露台宽门洞 |
| 阳台推拉门双包套 | 模板默认 | 与阳台推拉门同源门洞，按门洞宽度加两侧有效门高 | 当前样例无匹配阳台/露台宽门洞 |

## 继续保留人工/模板默认

这些项目不建议从现有算量结果硬推，需要业务选择、主材方案或后续新增更明确的范围标识。

| 项目 | 当前状态 | 原因 |
| --- | --- | --- |
| 背景墙 | 模板默认 | 用户已确认待定；需要背景墙范围或墙面装饰标识，不能从普通墙面面积推断 |
| 入户门 | 模板默认 | 是否更换入户门属于套餐/主材选择，不是 CAD 算量结果 |
| 蹲坑 | 模板默认 | 卫生间数量不能判断坐便/蹲坑配置，需洁具方案确认 |
| 玻璃淋浴房 | 模板默认 | 已有 `淋浴隔断` 按卫生间数量自动汇总；玻璃淋浴房继续默认可避免重复报价 |
| 砖墙门窗洞过梁 | 模板默认 | 只有新增加的门洞需要过梁，当前由设计师人工填写 |

## 已具备标识后自动化能力

| 项目 | 自动化条件 | 数据来源 | 说明 |
| --- | --- | --- | --- |
| 外墙批嵌 | 有 `QUOTE_EXT_WALL` 且参与报价的外墙行时自动汇总；没有外墙行或全部排除时仍按模板默认 | `exterior_rows.net_area` | 按选定外墙净面积汇总，已扣除外墙洞口；复核备注提示确认外墙批嵌施工面 |
| 外墙批嵌以及修补 | 有 `QUOTE_EXT_REPAIR` 时自动汇总；没有修补标识时仍按模板默认 | `construction_details` 中 `exterior_repair` 面积 | 闭合修补轮廓按实际面积；开放修补线按长度乘 `HEIGHT` 或默认高度，缺高时标记默认推断 |
| 拆改及拆墙 | 有 `QUOTE_DEMO_WALL` 时自动汇总；没有标识时仍按模板默认 | `construction_details` 中 `demo_wall` 面积 | 按拆墙线长度乘标识高度/默认高度汇总，缺高时标记默认推断 |
| 砌120厚砖墙 | 有 `QUOTE_NEW_WALL` 且 `THICKNESS=120mm/0.12m` 时自动汇总；没有匹配标识时仍按模板默认 | `construction_details` 中 `new_wall` 面积和厚度 | 按新砌墙线长度乘标识高度/默认高度汇总 |
| 砌240厚砖墙 | 有 `QUOTE_NEW_WALL` 且 `THICKNESS=240mm/0.24m` 时自动汇总；没有匹配标识时仍按模板默认 | `construction_details` 中 `new_wall` 面积和厚度 | 按新砌墙线长度乘标识高度/默认高度汇总 |
| 打混凝土过梁孔 | 按 `QuantityResult.building_area` 的 10% 取整数自动汇总；没有闭合外墙轮廓或 `QUOTE_BUILDING_AREA` 时仍按模板默认 | 闭合 `QUOTE_EXT_WALL` 面积汇总；没有闭合外墙轮廓时使用闭合 `QUOTE_BUILDING_AREA` 备用轮廓 | 不再使用室内空间面积相加作为建筑面积代理值；复核备注提示设计师确认建筑面积来源 |
| 厨房、卫生间排污管包隔音棉 | 有 `QUOTE_PIPE_INSULATION` 时自动汇总；没有标识时仍按模板默认 | `construction_details` 中 `pipe_insulation` 立管长度 | 按标识 `HEIGHT` 汇总；缺高时按楼层/项目默认高度推断并提示复核 |
| 包上/下水管道(单管) | 有 `QUOTE_PIPE_WRAP` 时自动汇总；没有标识时仍按模板默认 | `construction_details` 中 `pipe_wrap` 立管长度 | 按标识 `HEIGHT` 汇总；缺高时按楼层/项目默认高度推断并提示复核 |
| 阳台推拉门 | 有阳台/露台空间宽门洞时自动汇总；没有匹配门洞时仍按模板默认 | 阳台/露台 `QuantityRow.door_details` 宽度大于等于 1.4m 的唯一门洞 | 按门洞面积汇总，使用独立空间关键词，不影响厨房推拉门 |
| 阳台推拉门双包套 | 有阳台/露台空间宽门洞时自动汇总；没有匹配门洞时仍按模板默认 | 与阳台推拉门同源门洞 | 按门洞宽度加两侧有效门高汇总，门高缺失时使用默认门高并提示复核 |
| 全屋定制 | 有 `QUOTE_CUSTOM` 时自动汇总；样例未画标识时仍按模板默认 | `QUOTE_CUSTOM` 线/闭合轮廓、`HEIGHT`/`高`、`TYPE`/`类型`、`ROOM`/`空间` | 按投影面积汇总；缺高默认 2.6m；高度低于 1m 的柜体不计投影面积，复核备注提示按长度确认 |
| 橱柜 | 有 `QUOTE_CABINET` 时自动汇总；样例未画标识时仍按模板默认 | `QUOTE_CABINET` 线/闭合轮廓、`TYPE`/`类型`、`ROOM`/`空间` | 按长度汇总；地柜和吊柜可重叠画线，不自动去重，复核备注提示确认 |

## 下一阶段推荐

1. 若目标是继续降低真实样例的 17 行模板默认，优先补 CAD 标识：`QUOTE_EXT_WALL` / `QUOTE_BUILDING_AREA`、`QUOTE_DEMO_WALL`、`QUOTE_NEW_WALL`、`QUOTE_PIPE_INSULATION`、`QUOTE_PIPE_WRAP`、`QUOTE_CUSTOM`、`QUOTE_CABINET`、`QUOTE_EXT_REPAIR`。
2. 背景墙仍需要业务口径或范围标识，不应从现有面积硬推。
3. 入户门、蹲坑、玻璃淋浴房、砖墙门窗洞过梁继续作为人工/模板默认项处理。

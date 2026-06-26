# 商品房整装报价剩余模板默认项审计

审计基于真实样例 `scratch/cad-import-10-zero-optional-defaults/quote.xlsx`。当前样例统计为：

- 自动算量：47 行
- 自动汇总：46 行
- 模板默认：0 行

本文件只记录“现有算量结果是否足以继续自动化”。原则是：没有可靠 CAD / 算量来源的项目不硬推断；已确认为按需选择的项目按 0 自动汇总，由设计师手工填写。

针对当前样例的补图操作清单见 `docs/residential-quote-sample-cad-marker-checklist-zh.md`。
真实样例与 marker-rich 对照样例的验收记录见 `docs/residential-quote-real-sample-validation-zh.md`。

## 当前样例按 0 自动汇总的按需项目

这些项目已经有自动化规则；当前真实样例 `scratch/cad-import-10-zero-optional-defaults/result.json` 中没有对应 CAD 标识，因此按 0 自动汇总并提示设计师按需填写。后续设计师按规范补图层后即可自动汇总实际数量。

| 项目 | 当前样例状态 | 已支持的数据来源 | 当前样例默认原因 |
| --- | --- | --- | --- |
| 砖墙门窗洞过梁 | 自动汇总为 0 | `QUOTE_LINTEL` 数量 | 当前样例无过梁标识；只有新增门窗洞需要标识，未标识时由设计师手工填写 |
| 背景墙 | 自动汇总为 0 | `QUOTE_BACKGROUND_WALL` 面积 | 当前样例无背景墙范围标识；不从普通墙面面积硬推，未标识时由设计师按客户方案填写 |
| 玻璃淋浴房 | 自动汇总为 0 | `QUOTE_SHOWER_GLASS` 数量 | 当前样例无玻璃淋浴房标识；未标识时按 0，避免和淋浴隔断重复报价 |
| 蹲坑 | 自动汇总为 0 | `QUOTE_SQUAT_TOILET` 数量 | 当前样例无蹲坑标识；未标识时按 0，避免和马桶重复报价 |

| 入户门 | 自动汇总为 0 | 规则默认 0 | 是否更换入户门属于套餐/主材选择，且经常不在报价范围；如客户要求更换由设计师手工填写 |

## 已具备标识后自动化能力

| 项目 | 自动化条件 | 数据来源 | 说明 |
| --- | --- | --- | --- |
| 外墙批嵌 | 有 `QUOTE_EXT_WALL` 且参与报价的外墙行时自动汇总；没有外墙行或全部排除时仍按模板默认 | `exterior_rows.net_area` | 按选定外墙净面积汇总，已扣除外墙洞口；复核备注提示确认外墙批嵌施工面 |
| 外墙批嵌以及修补 | 有 `QUOTE_EXT_REPAIR` 时自动汇总；没有修补标识时按 0 | `construction_details` 中 `exterior_repair` 面积 | 闭合修补轮廓按实际面积；开放修补线按长度乘 `HEIGHT` 或默认高度，缺高时标记默认推断；无标识提示设计师手工输入 |
| 拆改及拆墙 | 有 `QUOTE_DEMO_WALL` 时自动汇总；没有标识时按 0 | `construction_details` 中 `demo_wall` 面积 | 按拆墙线长度乘标识高度/默认高度汇总，缺高时标记默认推断；无标识表示没有要拆的墙 |
| 砌120厚砖墙 | 有 `QUOTE_NEW_WALL` 且 `THICKNESS=120mm/0.12m` 时自动汇总；有新砌墙但没有 120 标识时按 0 并提示确认厚度 | `construction_details` 中 `new_wall` 面积和厚度 | 按新砌墙线长度乘标识高度/默认高度汇总 |
| 砌240厚砖墙 | 有 `QUOTE_NEW_WALL` 且 `THICKNESS=240mm/0.24m` 时自动汇总；未填 `THICKNESS` 的新砌墙默认按 240mm | `construction_details` 中 `new_wall` 面积和厚度 | 按新砌墙线长度乘标识高度/默认高度汇总 |
| 砖墙门窗洞过梁 | 有 `QUOTE_LINTEL` 时自动汇总；没有标识时按 0 | `construction_details` 中 `lintel` 数量 | 每个标识按 1 支过梁计；仅标新增门窗洞，避免把既有普通门洞误计入 |
| 背景墙 | 有 `QUOTE_BACKGROUND_WALL` 时自动汇总；没有标识时按 0 | `construction_details` 中 `background_wall` 面积 | 按背景墙线长乘 `HEIGHT` 或默认高度汇总；缺高时提示复核；没有客户方案时不硬推 |
| 玻璃淋浴房 | 有 `QUOTE_SHOWER_GLASS` 时按标识个数汇总；没有标识时按 0 | `construction_details` 中 `shower_glass` 数量 | 每个点、块、线或折线实体按 1 个计；不从卫生间数量推断，避免和 `淋浴隔断` 重复报价 |
| 蹲坑 | 有 `QUOTE_SQUAT_TOILET` 时按标识个数汇总；没有标识时按 0 | `construction_details` 中 `squat_toilet` 数量 | 每个点、块、线或折线实体按 1 个计；不从卫生间数量推断，避免和 `马桶` 重复报价 |
| 打混凝土过梁孔 | 按 `QuantityResult.building_area` 的 10% 取整数自动汇总；没有闭合外墙轮廓或 `QUOTE_BUILDING_AREA` 时仍按模板默认 | 闭合 `QUOTE_EXT_WALL` 面积汇总；没有闭合外墙轮廓时使用闭合 `QUOTE_BUILDING_AREA` 备用轮廓 | 不再使用室内空间面积相加作为建筑面积代理值；复核备注提示设计师确认建筑面积来源 |
| 厨房、卫生间排污管包隔音棉 | 有 `QUOTE_PIPE_INSULATION` 时自动汇总；没有标识时按 0 | `construction_details` 中 `pipe_insulation` 立管长度 | 按标识 `HEIGHT` 汇总；缺高时按楼层/项目默认高度推断并提示复核；无标识提示设计师手工输入 |
| 包上/下水管道(单管) | 有 `QUOTE_PIPE_WRAP` 时自动汇总；没有标识时按 0 | `construction_details` 中 `pipe_wrap` 立管长度 | 按标识 `HEIGHT` 汇总；缺高时按楼层/项目默认高度推断并提示复核；无标识提示设计师手工输入 |
| 阳台推拉门 | 有阳台/露台空间宽门洞时自动汇总；没有匹配门洞时按 0 | 阳台/露台 `QuantityRow.door_details` 宽度大于等于 1.4m 的唯一门洞 | 按门洞面积汇总，使用独立空间关键词，不影响厨房推拉门 |
| 阳台推拉门双包套 | 有阳台/露台空间宽门洞时自动汇总；没有匹配门洞时按 0 | 与阳台推拉门同源门洞 | 按门洞宽度加两侧有效门高汇总，门高缺失时使用默认门高并提示复核 |
| 全屋定制 | 有 `QUOTE_CUSTOM` 时自动汇总；样例未画标识时仍按模板默认 | `QUOTE_CUSTOM` 线/闭合轮廓、`HEIGHT`/`高`、`TYPE`/`类型`、`ROOM`/`空间` | 按投影面积汇总；缺高默认 2.6m；高度低于 1m 的柜体不计投影面积，复核备注提示按长度确认 |
| 地柜 / 吊柜 | 有橱柜标识时自动汇总；样例未画标识时仍按模板默认 | 新图优先用 `QUOTE_BASE_CABINET` / `QUOTE_WALL_CABINET`，旧图可用 `QUOTE_CABINET` 线/闭合轮廓加 `TYPE`/`类型`、`ROOM`/`空间` | `地柜` / `吊柜` 按类型分别汇总长度；闭合轮廓按占地面积除以推断柜深折算，避免转角漏算；模板只有通用橱柜行时自动拆成两行；地柜和吊柜可重叠画线，不自动去重 |

## 下一阶段推荐

1. 当前真实样例模板默认已清零；后续若客户需要过梁或背景墙，补 `QUOTE_LINTEL` 和 `QUOTE_BACKGROUND_WALL` 后可从 0 自动汇总为实际数量。
2. 背景墙必须有明确范围标识，不应从现有墙面面积硬推。
3. 玻璃淋浴房可用 `QUOTE_SHOWER_GLASS` 显式标识；没有标识时系统按 0，不保留模板默认数量。
4. 蹲坑可用 `QUOTE_SQUAT_TOILET` 显式标识；没有标识时系统按 0，不保留模板默认数量。
5. 入户门按 0 自动汇总，继续由设计师按客户是否更换手工填写。

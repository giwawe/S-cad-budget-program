# AGENTS.md

## 项目一句话

这是一个面向装修报价前置算量的 Python 项目。系统读取符合 `QUOTE_*` 图层规范的 CAD 平面方案，先转换成标准 `ProjectInput` JSON，再计算各空间的地面面积、墙面计量周长、墙面面积、窗面积、门洞数据等，最后导出 JSON 和可修改 Excel，供后续报价使用。

第一版重点是“准确算量表”，不是最终报价单、材料清单或单价系统。

## 技术栈

- Python 包名：`cad-budget`
- 源码目录：`src/cad_budget`
- 测试目录：`tests`
- 主要依赖：
  - `pydantic`：数据模型与 JSON 校验
  - `shapely`：几何面积、周长、点面关系、线段相交
  - `ezdxf`：DXF 读取和测试 DXF 生成
  - `openpyxl`：Excel 导出
  - `typer`：CLI
  - `pytest`：测试

## 常用命令

安装开发依赖：

```powershell
pip install -e ".[dev]"
```

运行全量测试：

```powershell
$env:PYTHONPATH='src'; py -3.14 -m pytest -q
```

从标准 JSON 计算算量：

```powershell
$env:PYTHONPATH='src'; cad-budget calculate tests\fixtures\simple_apartment.json --json-output build\result.json --excel-output build\result.xlsx
```

如果没有安装 entry point，可以直接调用 Typer app：

```powershell
$env:PYTHONPATH='src'; py -3.14 -c "from cad_budget.cli import app; app()" calculate tests\fixtures\simple_apartment.json --json-output build\result.json --excel-output build\result.xlsx
```

导入 DXF：

```powershell
$env:PYTHONPATH='src'; py -3.14 -c "from cad_budget.cli import app; app()" import-cad plan.dxf --json-output project.json --unit mm
```

## 当前架构

核心数据流：

```text
DWG / DXF
  -> CAD Adapter
  -> ProjectInput JSON
  -> Quantity Engine
  -> QuantityResult JSON / editable Excel
```

模块边界要保持清楚：

- `dxf_adapter.py` 只负责把 DXF 中的 `QUOTE_*` 对象翻译成 `ProjectInput`。
- `dwg_converter.py` 只负责调用外部 DWG 转 DXF 工具；项目不直接解析 DWG。
- `quantity.py` 只负责基于 `ProjectInput` 算量和异常判断。
- `export_excel.py` 只负责把 `QuantityResult` 导出成可修改 Excel。
- `models.py` 是稳定的公共数据模型，修改前要确认 JSON、Excel、测试和设计文档的影响。

## CAD 图层规范

已建模的图层在 `LayerName` 中：

- `QUOTE_ROOM`：空间闭合边界，用于地面面积和地面周长。
- `QUOTE_TEXT`：空间名称文字。DXF 导入会把落在房间内的文字匹配到空间。
- `QUOTE_WINDOW`：窗。支持窗块 `INSERT` 属性读取，也支持封闭窗洞轮廓。
- `QUOTE_DOOR`：门洞。支持门块缩放宽度，也支持线段或闭合轮廓几何推断宽度。
- `QUOTE_WALL`：墙体或可施工墙面线，用于推断墙面计量周长。
- `QUOTE_OPENING`：开放边界，开放客餐厅等空间不要把这段计入墙面乳胶漆面积。
- `QUOTE_FLOOR`：楼层文字，主要用于别墅和多楼层项目；商品房样例可以没有。
- `QUOTE_HEIGHT`：层高文字，优先级高于楼层默认层高和项目默认层高。
- `QUOTE_VOID`：挑空区域或楼板洞口辅助标记。
- `QUOTE_EXT_WALL` / `QUOTE_EXT_OPENING`：外墙和外墙洞口，已能导入，完整外墙表仍是后续范围。

## 业务规则

### 空间、楼层、层高

- 商品房默认可以只有统一项目层高，通常不需要 `QUOTE_FLOOR`。
- 别墅或多层项目应使用 `QUOTE_FLOOR`，并通过 `floor_heights` 设置每层默认层高。
- 层高优先级：
  1. `RoomBoundary.attributes["height"]`
  2. 挑空空间的 `QUOTE_VOID` / 关联楼层高度规则
  3. `QUOTE_HEIGHT`
  4. `floor_heights`
  5. `project.default_height`
- `RoomBoundary` 必须是闭合多边形，首尾点一致。

### 开放空间

- `QUOTE_ROOM` 始终用于地面面积和地面周长，不能直接等同于墙面计量周长。
- 墙面计量周长优先由 `QUOTE_WALL` 与房间边界匹配得到。
- `QUOTE_OPENING` 标记的开放边界要从墙面计量周长中扣除。
- 如果没有 `QUOTE_WALL`，则退回为 `floor_perimeter - open_boundary_length`。

### 窗

- 窗块 `INSERT` 位于 `QUOTE_WINDOW` 时，会优先读取属性：
  - 宽度：`WIDTH`、`width`、`窗宽`、`宽`
  - 高度：`HEIGHT`、`height`、`窗高`、`高`
- 属性数值规则：大于 `20` 按毫米转米，小于等于 `20` 按米处理；也支持 `mm` / `m` 后缀。
- 窗块没有可解析宽度时不生成窗，并给 `WINDOW_WIDTH_ATTRIBUTE_INVALID` warning。
- 封闭窗洞轮廓支持矩形、多边形和带 bulge 弧线的闭合 `LWPOLYLINE`；宽度来自最小旋转矩形的主尺寸，高度保持 `None`。
- 窗高缺失时算量引擎使用 `default_window_height`，并产生 `window_height_defaulted`，行状态通常为 `default_inferred`。
- 窗面积会从墙面毛面积中扣除；如果窗面积大于墙面毛面积，净墙面面积置 0，并标记 `window_area_exceeds_wall_area`。

### 门

- 门洞数据会保存门洞数量和门洞面积。
- 门块 `INSERT` 位于 `QUOTE_DOOR` 时，会优先读取属性：
  - 宽度：`WIDTH`、`width`、`门宽`、`宽`
  - 高度：`HEIGHT`、`height`、`门高`、`高`
- 门块属性缺失时继续使用 block scale 兜底，线段或闭合轮廓门继续走几何推断。
- 第一版默认不从墙面净面积中扣除门洞面积，这是已确认业务口径。
- 共享边界上的门会计入相邻空间；共享边界上的窗会判定为歧义并不计入。

### 特殊空间

- `void`：挑空空间。地面面积只按所在层空间计算，墙面面积使用实际挑空高度。
- `void_opening`：上层楼板洞口，默认排除面积和墙面量。
- `stair` / `stair_hall`：可作为空间类型；`stair` 会保留基础空间算量并标记 `stair_special_quantity_manual`，提示人工补录踏步、踢面、斜板、扶手等专项工程量。
- `balcony` / `terrace`：通过 `is_outdoor` 和是否计入室内地面、室内墙面乳胶漆字段控制。
- `elevator_shaft`：默认排除在装修算量之外。
- 外墙工程量与室内空间行分开；当前 `result.json` 输出 `exterior_rows`，Excel 在存在外墙行时输出独立 `外墙表`。

## Excel 导出

目标是可修改算量表，而不是只读报表。

- 主工作表是算量表。
- 第 1 行为项目名称，第 3 行为表头，第 4 行起每个空间一行。
- 冻结窗格：`A4`。
- 自动筛选覆盖表头到数据区。
- 人工可编辑字段和公式字段用不同底色区分。
- 公式字段：
  - 墙面毛面积：`墙面计量周长 * 层高`
  - 墙面净面积：`墙面毛面积 - 窗面积`
- JSON 输出仍是静态计算结果；Excel 的公式服务人工复核和报价前修改。
- `算量表` 末尾有隐藏列 `空间ID`，用于保留 `room_id`。
- 已提供 `import-excel` 命令，可把修改后的 Excel 回读成 `QuantityResult` JSON，并按表格中的层高、墙面计量周长、窗面积等重新计算墙面毛面积和净面积。
- Excel 回读不会修改 CAD，也不会反向更新原始 `ProjectInput` JSON。

## 真实样例和当前回归口径

本地曾用 `D:\Desktop\test-case 2.dxf` 做商品房样例回归。当前预期：

- `QUOTE_ROOM` 识别后有效空间：8 个。
- `QUOTE_TEXT`：8 个。
- `QUOTE_WINDOW`：8 个，都是封闭轮廓窗，窗高为 `None`，后续默认推断。
- 门：7 个。
- 墙线：82 个。
- 楼层：全部 `None`，因为这是商品房样例，不是别墅。
- 算量异常中会有 8 个 `window_height_defaulted`。

这个样例还会产生一些 `ROOM_BOUNDARY_WITHOUT_TEXT_IGNORED` warning，用于过滤视觉上不是最终空间的多余闭合边界。

## 已知注意事项

- `scratch/` 是本地生成输出目录，已在 `.gitignore` 中，不要提交。
- 终端里读取部分中文文件时可能出现乱码显示；修改中文内容前要确认是终端编码问题还是文件内容问题。不要只因为 PowerShell 输出显示异常就大范围重写文件。
- 当前 `python -m cad_budget.cli ...` 不一定会触发 Typer app；优先使用已安装的 `cad-budget` 命令，或使用 `py -3.14 -c "from cad_budget.cli import app; app()" ...`。
- `ProjectInput` / `QuantityRow` 是重要接口。除非用户明确要求接口升级，否则优先保持模型兼容。
- DWG 需要外部转换器命令，项目只负责调用转换器并读取生成的 DXF。
- 单位冲突会被视为 blocker，避免整张图比例错误。
- 修改 CAD adapter 时一定要覆盖 DXF 单元测试，尤其是单位、闭合边界、窗/门/墙/开放边界、楼层继承。
- 修改算量规则时要补充 `tests/test_quantity.py`，因为业务口径主要在这里固化。
- 修改 Excel 时要补充 `tests/test_export_excel.py`，并用 `openpyxl` 读取 workbook 验证公式、表头、冻结窗格、筛选和样式。

## 推荐开发流程

1. 先读设计文档：
   - `docs/superpowers/specs/2026-06-18-cad-quantity-takeoff-design-zh.md`
   - `docs/superpowers/specs/2026-06-18-cad-quantity-takeoff-design.md`
2. 再读相关源码和测试，优先相信测试中已经固化的业务规则。
3. 对新功能先加失败测试，再实现，再跑定向测试。
4. 最后跑全量测试：

```powershell
$env:PYTHONPATH='src'; py -3.14 -m pytest -q
```

5. 如果改动影响真实 CAD 导入，重新用 DXF 样例生成 `scratch/cad-import-test/project.json`、`result.json`、`result.xlsx` 并核对数量。

## 后续可能的工作

- 修复或统一中文显示/编码问题，确保 README、Excel 表头和测试断言都是真实中文。
- 楼梯专项工程量后续可增加专门字段或专门规则，目前只做人工补录提示。
- Excel 修改后的数据已经可以回读成 `QuantityResult` JSON；后续如果需要闭环到项目源数据，还要另行定义回写 `ProjectInput` 或图纸标注的接口。

## 商品房整装报价清单

- 已新增 `quote` 命令：`cad-budget quote result.json --template 清单式报价表（商品房）.xlsx --excel-output quote.xlsx`。
- 第一版只读取模板里的 `整装` 工作表，`半包` 直接忽略，不提供选择。
- 报价输出是独立 Excel，不追加到算量表。
- 输出会按真实 `QuantityResult.rows` 生成实际空间分组，例如 `客厅工程`、`厨房工程`、`主卫工程`。
- 干区空间用地面面积生成顶面/地面项目，用墙面净面积生成墙面项目。
- 厨房、卫生间、主卫、公卫等湿区空间用地面面积生成地面项目，用墙面净面积生成墙砖项目；卫生间类防水数量为 `地面面积 + 墙面净面积`，厨房防水数量为 `地面面积`。
- 主材、全屋定制、室内门、卫浴、水电、其他等当前 CAD 无法准确判断的项目保留模板默认数量和单价，供预算员复核修改。

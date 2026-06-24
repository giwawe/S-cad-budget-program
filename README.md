# CAD Budget Program

First-version CAD renovation quantity takeoff core.

The system accepts normalized CAD-derived JSON using the `QUOTE_*` standard, calculates room quantities, reports exceptions, and exports Excel for later quotation work.

## Local Usage

Install development dependencies:

```bash
pip install -e ".[dev]"
```

Run tests:

```bash
pytest -q
```

Calculate a sample apartment:

```bash
cad-budget calculate tests/fixtures/simple_apartment.json --json-output build/simple-result.json --excel-output build/simple-result.xlsx
```

## First-Version CAD Standard

Designer-facing CAD drawing requirements live in [docs/cad-lightweight-drawing-standard-zh.md](docs/cad-lightweight-drawing-standard-zh.md). Keep that document updated whenever CAD import layers, block attributes, unit handling, geometry inference, or quantity rules change.

Core layers:

```text
QUOTE_ROOM
QUOTE_TEXT
QUOTE_WINDOW
QUOTE_DOOR
QUOTE_WALL
QUOTE_OPENING
QUOTE_FLOOR
QUOTE_HEIGHT
QUOTE_VOID
QUOTE_EXT_WALL
QUOTE_EXT_OPENING
```

The current implementation starts from normalized JSON. DWG/DXF conversion should produce the same structure used by the fixtures.

## CAD Import Workflow

The first CAD import path is:

```text
DXF / DWG -> CAD Adapter -> ProjectInput JSON -> Quantity calculation -> JSON / Excel result
```

Import a DXF file directly into normalized project JSON:

```bash
cad-budget import-cad plan.dxf --json-output project.json --unit mm
```

Then run quantity calculation from that JSON:

```bash
cad-budget calculate project.json --json-output result.json --excel-output result.xlsx
```

DWG direct parsing is not implemented. DWG files must first be converted to DXF through a configured converter command that includes both `{input}` and `{output}` placeholders. The adapter runs the converter, reads the generated DXF, and then follows the same ProjectInput JSON and calculation path. If DWG conversion fails, ask the designer to save the drawing as DXF and upload the DXF file.

For example, pass the converter command as repeated `--dwg-converter` parts. The actual converter executable is environment-specific:

```bash
cad-budget import-cad plan.dwg --json-output project.json --unit mm --dwg-converter "converter" --dwg-converter "{input}" --dwg-converter "{output}"
```

Current import-supported layers:

```text
QUOTE_ROOM
QUOTE_TEXT
QUOTE_WINDOW
QUOTE_DOOR
QUOTE_WALL
QUOTE_OPENING
QUOTE_FLOOR
QUOTE_HEIGHT
QUOTE_VOID
QUOTE_EXT_WALL
QUOTE_EXT_OPENING
```

`QUOTE_FLOOR` text markers are optional. Commodity apartment drawings can omit them and use the project default height. Villa or multi-floor drawings can add `QUOTE_FLOOR` text markers inside room boundaries; imported windows, doors, walls, openings, height markers, voids, and exterior linework inherit the matched room floor when the match is unambiguous, so per-floor default heights can be used during quantity calculation.

The import adapter recognizes `QUOTE_WINDOW` window blocks and closed LWPOLYLINE outlines. Window blocks read width and height from common attributes such as `WIDTH`, `HEIGHT`, `窗宽`, and `窗高`; numeric values greater than 20 are treated as millimeters, while smaller values are treated as meters. Closed outlines may be rectangular, polygonal, or arc-based; they infer width from the outline and keep `height=None`, so the quantity engine applies the default window height and marks it inferred.

Room names prefer `QUOTE_TEXT`. If a drawing has no `QUOTE_TEXT` at all, the importer falls back to ordinary `TEXT` / `MTEXT` on non-`QUOTE_*` layers inside room boundaries.

Door recognition reads width and height from common block attributes such as `WIDTH`, `HEIGHT`, `门宽`, and `门高` when available, and falls back to block scale or geometry. Door count and door opening area are recorded when width and height are available. Door area is not deducted from wall area by default.

Exterior wall quantities are kept separate from room rows. `QUOTE_EXT_WALL` and matching `QUOTE_EXT_OPENING` linework produce `exterior_rows` in the calculated JSON result, with measure length, opening length, gross area, and net area. Exterior wall rows default to `include_in_quote=true`; a `QUOTE_EXT_WALL` can opt out of quote aggregates with `CAD_BUDGET` XDATA `QUOTE_INCLUDE=false` or `INCLUDE=false`. When exterior rows exist, Excel export includes a separate `外墙表` worksheet.

Stair spaces keep their basic room quantities, but `space_type=stair` is marked with `stair_special_quantity_manual` because stair treads, risers, sloped slabs, handrails, and other stair-specific quantities are manual in the first version.

The main Excel quantity sheet keeps hidden `空间ID` and quote-detail metadata columns. They are not part of the visible review table, but they give a stable key and preserve detail rows used by quote automation, such as window wall segments, door openings, custom cabinetry, and cabinets.

Edited Excel workbooks can be imported back into a `QuantityResult` JSON:

```powershell
cad-budget import-excel result.xlsx --json-output edited-result.json
```

The importer reads the editable quantity fields, preserves the hidden room id and quote-detail metadata, and recalculates gross/net wall areas from the edited row values. It does not modify the original CAD file or the original `ProjectInput` JSON.

## Residential Quote Export

Generate a commodity-apartment fitout quote workbook from a `QuantityResult` JSON:

```powershell
cad-budget quote result.json --template "D:\Desktop\清单式报价表（商品房）.xlsx" --excel-output quote.xlsx
```

The quote exporter reads only the `整装` worksheet from the template and ignores `半包`. It creates actual room sections from the quantity result, fills quantities that can be derived from room floor/wall areas, supported opening details, and optional `QUOTE_CUSTOM` / `QUOTE_CABINET` markers, and preserves template quantities for manual/non-CAD items such as background walls, sanitary ware, and package lines without reliable CAD data. The generated workbook also includes visible review columns for quantity source, source room, room id, measurement basis, review status, and notes.

Quote generation is automation-first: `confirmed` and `manually_edited` room quantities are marked `自动生成`; `default_inferred` rows are still generated and marked `自动生成-默认推断`; `needs_review` rows are still generated and marked `自动生成-异常提示`; template-default items are marked `按模板生成`. These statuses are review hints and do not block quote generation.

Several non-room quote lines are auto-filled from whole-house aggregates when their template item names match the built-in rules. Cleanup, material handling, tile protection, wiring, water-pipe routing, wall chasing, and similar area-based items use the summed included indoor floor area. `美缝` uses generated tile work area: floor tile area plus wet-area wall tile area. `窗帘` uses the summed wall-segment length for windows and de-duplicates multiple windows on the same room wall. `地面瓷砖` and `墙面瓷砖` parse tile specs such as `750X1500` or `600x1200` from the template text and convert generated tile area to piece counts with the configured loss rate. `瓷砖加工费` uses the summed included indoor floor area as the house-area proxy and is marked for designer confirmation. `室内门` is counted by unique ordinary door openings; wide openings are excluded. `厨房推拉门` uses unique wide door-opening area for matched room names, and `厨房推拉门双包套` uses the matching opening trim length. `阳台推拉门` and `阳台推拉门双包套` use item-specific balcony/terrace room keywords so they do not broaden kitchen sliding-door matching. `外墙批嵌` uses selected exterior net area and deducts exterior openings; `外墙批嵌以及修补` remains template-default. `全屋定制` uses projected area from `QUOTE_CUSTOM`; missing custom height defaults to 2.6m, and custom fixtures lower than 1m are excluded from projected-area totals with a review note for length pricing. `橱柜` uses summed `QUOTE_CABINET` length and keeps a review note for overlapping base/wall cabinet confirmation. `淋浴隔断` is filled by bathroom count, while `玻璃淋浴房` remains template-default unless the rules are customized. Rule files can also opt template items into room-count, wet-room-count, kitchen-count, bathroom-count, window-count, window-area, door-count, door-area, fixed-quantity, curtain wall-length, tile-piece, tile-processing-area, interior-door-count, sliding-door-area, sliding-door-trim-length, exterior-net-area, custom projected-area, and cabinet-length aggregates. Fixed-quantity aggregates are for whole-house one-off lines such as cleaning, switch packages, and lighting packages.

Wet-room quote quantities use dedicated height rules instead of full wall net area: kitchen waterproofing is floor area plus wall length below 0.3m; bathroom waterproofing is floor area plus wall length below 1.8m; wall tile area is wall length below 2.5m minus known window area.

Default residential quote rules live in `src/cad_budget/config/residential_quote_rules.json`. The CLI automatically uses this packaged rule file. To customize wet-room heights, whole-house aggregate item names, tile loss rate, wide-door threshold, default door height, custom-cabinet height defaults, low custom-cabinet height threshold, exterior net-area aggregate items, or sliding-door room keywords and item-specific keyword mappings, export an editable copy first. Older rule files with only the original area aggregate fields remain valid; omitted optional aggregate lists and maps default to empty and omitted optional numbers use built-in defaults.

```powershell
cad-budget init-rules --output my-rules.json
```

Then pass the edited file to `quote`:

```powershell
cad-budget quote result.json --template "D:\Desktop\清单式报价表（商品房）.xlsx" --rules my-rules.json --excel-output quote.xlsx
```

The generated quote workbook records the rule source in the automation summary area. Invalid rule JSON, missing required fields, non-numeric rule numbers, and unparseable tile specifications fail with clear CLI errors.

The quote workbook writes a small automation summary in columns `Q:S`, counting `自动算量`, `自动汇总`, and `模板默认` lines and showing their percentages. The main quote table remains in columns `A:O`.

Remaining template-default items from the real commodity-apartment sample are tracked in `docs/residential-quote-remaining-defaults-audit-zh.md`, grouped by whether they need new CAD marker layers or should stay manual.

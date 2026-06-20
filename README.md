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

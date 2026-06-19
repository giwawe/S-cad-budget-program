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
QUOTE_HEIGHT
QUOTE_VOID
QUOTE_EXT_WALL
QUOTE_EXT_OPENING
```

`QUOTE_FLOOR` remains reserved in the CAD standard and is planned for floor assignment in a later CAD adapter increment; the current importer does not parse it.

The first import adapter recognizes closed `QUOTE_WINDOW` LWPOLYLINE outlines; the outline may be rectangular, polygonal, or arc-based. Window height is not imported yet: imported windows keep `height=None`, then the quantity engine applies the default window height and marks it inferred. Window block attributes and tags remain part of the CAD standard and are planned for a future importer increment.

Door recognition records door count and door opening area when width and height are available. Door area is not deducted from wall area by default.

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

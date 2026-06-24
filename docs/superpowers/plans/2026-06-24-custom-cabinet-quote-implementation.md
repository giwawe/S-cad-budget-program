# Custom Cabinet Quote Markers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add lightweight `QUOTE_CUSTOM` and `QUOTE_CABINET` CAD markers so residential quote export can auto-fill `全屋定制` and `橱柜` from CAD-backed quantities.

**Architecture:** Extend the stable JSON models with a reusable fixture marker/detail shape, import `LINE` and `LWPOLYLINE` entities from the two new CAD layers, assign fixture details to rooms during quantity calculation, and let residential quote rules opt template rows into custom projected-area and cabinet length aggregates. Keep old JSON/rules compatible and keep template defaults when no markers exist.

**Tech Stack:** Python, Pydantic, Shapely, ezdxf, openpyxl, pytest, Typer CLI.

---

## Files

- Modify: `src/cad_budget/models.py`
  - Add `LayerName.QUOTE_CUSTOM`, `LayerName.QUOTE_CABINET`.
  - Add `FixtureKind`, `FixturePricingMode`, `FixtureMarker`, `FixtureQuantityDetail`.
  - Add `ProjectInput.custom_items`, `ProjectInput.cabinet_items`.
  - Add `QuantityRow.custom_details`, `QuantityRow.cabinet_details`.
- Modify: `src/cad_budget/dxf_adapter.py`
  - Parse `QUOTE_CUSTOM` / `QUOTE_CABINET` `LINE` and `LWPOLYLINE`.
  - Read optional attributes from XDATA / extension dictionaries only if existing helpers support them; otherwise only geometry now and leave block/advanced attributes out.
  - Use normal DXF entity layer dispatch and existing unit scaling.
- Modify: `src/cad_budget/quantity.py`
  - Assign fixtures to rooms by `ROOM` attribute, midpoint containment, then boundary tolerance.
  - Calculate default custom height `2.6m`.
  - Set `pricing_mode` to `length` when explicit effective height is less than `1.0m`, otherwise `projected_area`.
- Modify: `src/cad_budget/quote_excel.py`
  - Add rule fields for custom projected-area items and cabinet length items.
  - Auto-fill `全屋定制` and `橱柜` when details exist.
  - Keep template default when details are absent.
- Modify: `src/cad_budget/config/residential_quote_rules.json`
  - Add `custom_projected_area_items: ["全屋定制"]`.
  - Add `cabinet_length_items: ["橱柜"]`.
  - Add `default_custom_height: 2.6`.
  - Add `low_custom_height_threshold: 1.0`.
- Modify: `docs/cad-lightweight-drawing-standard-zh.md`
  - Document the two new layers and attributes.
- Modify: `docs/residential-quote-remaining-defaults-audit-zh.md`
  - Move `全屋定制` and `橱柜` out of “needs new layer” once implemented.
- Tests:
  - `tests/test_models.py`
  - `tests/test_dxf_adapter.py`
  - `tests/test_quantity.py`
  - `tests/test_quote_excel.py`

## Task 1: Model Fields And Compatibility

**Files:**
- Modify: `src/cad_budget/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write failing model compatibility tests**

Add tests:

```python
def test_project_input_accepts_custom_and_cabinet_fixture_markers():
    project = ProjectInput(
        project_name="Fixtures",
        custom_items=[
            FixtureMarker(
                id="custom-1",
                layer=LayerName.QUOTE_CUSTOM,
                kind=FixtureKind.CUSTOM,
                points=[Point(x=0, y=0), Point(x=2, y=0)],
                length=2.0,
                height=2.6,
                fixture_type="衣柜",
            )
        ],
        cabinet_items=[
            FixtureMarker(
                id="cabinet-1",
                layer=LayerName.QUOTE_CABINET,
                kind=FixtureKind.CABINET,
                points=[Point(x=0, y=1), Point(x=3, y=1)],
                length=3.0,
                fixture_type="地柜",
            )
        ],
    )
    assert project.custom_items[0].kind is FixtureKind.CUSTOM
    assert project.cabinet_items[0].fixture_type == "地柜"


def test_quantity_row_fixture_details_default_to_empty_lists():
    row = QuantityRow(
        room_id="r1",
        floor=None,
        room_name="卧室",
        space_type=SpaceType.NORMAL,
        height=2.8,
        height_mode=HeightMode.PROJECT_DEFAULT,
        floor_area=10,
        floor_perimeter=12,
        wall_measure_perimeter=12,
        open_boundary_length=0,
        gross_wall_area=33.6,
        window_count=0,
        window_area=0,
        door_opening_count=0,
        door_opening_area=0,
        net_wall_area=33.6,
        is_outdoor=False,
        include_in_floor_quantity=True,
        include_in_wall_paint_quantity=True,
        status=DataStatus.CONFIRMED,
    )
    assert row.custom_details == []
    assert row.cabinet_details == []
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
py -3.14 -m pytest tests\test_models.py::test_project_input_accepts_custom_and_cabinet_fixture_markers tests\test_models.py::test_quantity_row_fixture_details_default_to_empty_lists -q
```

Expected: fail because `FixtureMarker`, `FixtureKind`, fixture layers, or row fields are missing.

- [ ] **Step 3: Implement model types**

In `src/cad_budget/models.py`:

```python
class LayerName(str, Enum):
    QUOTE_ROOM = "QUOTE_ROOM"
    QUOTE_TEXT = "QUOTE_TEXT"
    QUOTE_WINDOW = "QUOTE_WINDOW"
    QUOTE_DOOR = "QUOTE_DOOR"
    QUOTE_WALL = "QUOTE_WALL"
    QUOTE_OPENING = "QUOTE_OPENING"
    QUOTE_FLOOR = "QUOTE_FLOOR"
    QUOTE_HEIGHT = "QUOTE_HEIGHT"
    QUOTE_VOID = "QUOTE_VOID"
    QUOTE_EXT_WALL = "QUOTE_EXT_WALL"
    QUOTE_EXT_OPENING = "QUOTE_EXT_OPENING"
    QUOTE_CUSTOM = "QUOTE_CUSTOM"
    QUOTE_CABINET = "QUOTE_CABINET"


class FixtureKind(str, Enum):
    CUSTOM = "custom"
    CABINET = "cabinet"


class FixturePricingMode(str, Enum):
    PROJECTED_AREA = "projected_area"
    LENGTH = "length"


class FixtureMarker(BaseModel):
    id: str
    layer: LayerName
    kind: FixtureKind
    points: list[Point]
    length: float
    height: float | None = None
    fixture_type: str | None = None
    floor: str | None = None
    room_id: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class FixtureQuantityDetail(BaseModel):
    id: str
    room_id: str | None = None
    room_name: str | None = None
    kind: FixtureKind
    length: float
    height: float | None = None
    effective_height: float | None = None
    height_defaulted: bool = False
    projected_area: float = 0.0
    pricing_mode: FixturePricingMode
    fixture_type: str | None = None
```

Add `ProjectInput.custom_items`, `ProjectInput.cabinet_items`, `QuantityRow.custom_details`, and `QuantityRow.cabinet_details` with `Field(default_factory=list)`.

- [ ] **Step 4: Run tests and verify GREEN**

Run the two model tests again. Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src\cad_budget\models.py tests\test_models.py
git commit -m "feat: add fixture marker models"
```

## Task 2: DXF Adapter Imports Fixture Layers

**Files:**
- Modify: `src/cad_budget/dxf_adapter.py`
- Test: `tests/test_dxf_adapter.py`

- [ ] **Step 1: Write failing DXF adapter tests**

Add tests that create rooms plus fixture lines:

```python
def test_imports_quote_custom_and_cabinet_lines(tmp_path: Path):
    doc = ezdxf.new()
    modelspace = doc.modelspace()
    for layer in ["QUOTE_ROOM", "QUOTE_TEXT", "QUOTE_CUSTOM", "QUOTE_CABINET"]:
        doc.layers.add(layer)
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_text("主卧", dxfattribs={"layer": "QUOTE_TEXT", "height": 250}).set_placement((1500, 1200))
    modelspace.add_line((500, 500), (2500, 500), dxfattribs={"layer": "QUOTE_CUSTOM"})
    modelspace.add_line((500, 900), (3500, 900), dxfattribs={"layer": "QUOTE_CABINET"})
    path = tmp_path / "fixtures.dxf"
    doc.saveas(path)

    result = import_dxf(path, CadImportOptions(confirmed_unit=CadUnit.MILLIMETER))

    assert len(result.project.custom_items) == 1
    assert result.project.custom_items[0].length == 2.0
    assert result.project.custom_items[0].kind is FixtureKind.CUSTOM
    assert len(result.project.cabinet_items) == 1
    assert result.project.cabinet_items[0].length == 3.0
    assert result.project.cabinet_items[0].kind is FixtureKind.CABINET
```

Add a second test for closed `LWPOLYLINE`:

```python
def test_imports_closed_custom_outline_using_longest_rectangle_edge(tmp_path: Path):
    doc = ezdxf.new()
    modelspace = doc.modelspace()
    for layer in ["QUOTE_ROOM", "QUOTE_TEXT", "QUOTE_CUSTOM"]:
        doc.layers.add(layer)
    modelspace.add_lwpolyline(
        [(0, 0), (5000, 0), (5000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_text("客厅", dxfattribs={"layer": "QUOTE_TEXT", "height": 250}).set_placement((1500, 1200))
    modelspace.add_lwpolyline(
        [(500, 500), (2500, 500), (2500, 1100), (500, 1100), (500, 500)],
        dxfattribs={"layer": "QUOTE_CUSTOM", "closed": True},
    )
    path = tmp_path / "custom-outline.dxf"
    doc.saveas(path)

    result = import_dxf(path, CadImportOptions(confirmed_unit=CadUnit.MILLIMETER))

    assert result.project.custom_items[0].length == 2.0
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
py -3.14 -m pytest tests\test_dxf_adapter.py::test_imports_quote_custom_and_cabinet_lines tests\test_dxf_adapter.py::test_imports_closed_custom_outline_using_longest_rectangle_edge -q
```

Expected: fail because adapter does not populate fixture lists.

- [ ] **Step 3: Implement import logic**

In `src/cad_budget/dxf_adapter.py`:

- Import `FixtureKind` and `FixtureMarker`.
- Add fixture lists near `windows` / `doors`:

```python
custom_items: list[FixtureMarker] = []
cabinet_items: list[FixtureMarker] = []
```

- Add helper:

```python
def _fixture_marker_from_points(entity, points: list[Point], layer: LayerName, kind: FixtureKind) -> FixtureMarker | None:
    if len(points) < 2:
        return None
    if len(points) >= 4 and points[0] == points[-1]:
        polygon = _outline_polygon(points)
        length = _outline_width(polygon) if polygon is not None else 0.0
    else:
        length = _polyline_length(points)
    if length <= 0:
        return None
    return FixtureMarker(id=_entity_id(entity), layer=layer, kind=kind, points=points, length=length)
```

- Dispatch `LINE` and `LWPOLYLINE` on `QUOTE_CUSTOM` and `QUOTE_CABINET`.
- Pass `custom_items=custom_items`, `cabinet_items=cabinet_items` into `ProjectInput`.

- [ ] **Step 4: Run tests and verify GREEN**

Run the two adapter tests again. Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src\cad_budget\dxf_adapter.py tests\test_dxf_adapter.py
git commit -m "feat: import custom and cabinet CAD markers"
```

## Task 3: Quantity Fixture Details

**Files:**
- Modify: `src/cad_budget/quantity.py`
- Test: `tests/test_quantity.py`

- [ ] **Step 1: Write failing quantity tests**

Add tests:

```python
def test_custom_fixture_details_default_height_and_low_height_pricing():
    project = ProjectInput(
        project_name="Custom Fixtures",
        rooms=[RoomBoundary(id="bed", points=rect(0, 0, 4, 3), name="主卧")],
        custom_items=[
            FixtureMarker(
                id="wardrobe",
                layer=LayerName.QUOTE_CUSTOM,
                kind=FixtureKind.CUSTOM,
                points=[Point(x=0.5, y=0.5), Point(x=2.5, y=0.5)],
                length=2.0,
                fixture_type="衣柜",
            ),
            FixtureMarker(
                id="low",
                layer=LayerName.QUOTE_CUSTOM,
                kind=FixtureKind.CUSTOM,
                points=[Point(x=0.5, y=1.0), Point(x=1.5, y=1.0)],
                length=1.0,
                height=0.8,
                fixture_type="矮柜",
            ),
        ],
    )

    result = calculate_quantities(project)
    row = result.rows[0]

    assert row.custom_details[0].effective_height == 2.6
    assert row.custom_details[0].height_defaulted is True
    assert row.custom_details[0].projected_area == 5.2
    assert row.custom_details[0].pricing_mode == FixturePricingMode.PROJECTED_AREA
    assert row.custom_details[1].effective_height == 0.8
    assert row.custom_details[1].projected_area == 0.0
    assert row.custom_details[1].pricing_mode == FixturePricingMode.LENGTH
```

Add overlapping cabinet test:

```python
def test_cabinet_fixture_details_keep_overlapping_base_and_wall_cabinets():
    project = ProjectInput(
        project_name="Cabinet Fixtures",
        rooms=[RoomBoundary(id="kitchen", points=rect(0, 0, 4, 3), name="厨房")],
        cabinet_items=[
            FixtureMarker(
                id="base",
                layer=LayerName.QUOTE_CABINET,
                kind=FixtureKind.CABINET,
                points=[Point(x=0.5, y=0.5), Point(x=3.5, y=0.5)],
                length=3.0,
                fixture_type="地柜",
            ),
            FixtureMarker(
                id="wall",
                layer=LayerName.QUOTE_CABINET,
                kind=FixtureKind.CABINET,
                points=[Point(x=0.5, y=0.5), Point(x=3.5, y=0.5)],
                length=3.0,
                fixture_type="吊柜",
            ),
        ],
    )

    result = calculate_quantities(project)
    row = result.rows[0]

    assert [detail.id for detail in row.cabinet_details] == ["base", "wall"]
    assert sum(detail.length for detail in row.cabinet_details) == 6.0
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
py -3.14 -m pytest tests\test_quantity.py::test_custom_fixture_details_default_height_and_low_height_pricing tests\test_quantity.py::test_cabinet_fixture_details_keep_overlapping_base_and_wall_cabinets -q
```

Expected: fail because calculation does not populate fixture details.

- [ ] **Step 3: Implement detail assignment**

In `src/cad_budget/quantity.py`:

- Import `FixtureKind`, `FixturePricingMode`, `FixtureMarker`, `FixtureQuantityDetail`.
- Add constants:

```python
_DEFAULT_CUSTOM_HEIGHT_METERS = 2.6
_LOW_CUSTOM_HEIGHT_THRESHOLD_METERS = 1.0
```

- Add `_fixture_midpoint(fixture)` using the first and last point midpoint.
- Add `_assign_fixtures_to_rooms(project, rooms, fixtures)` with this algorithm:
  - Create `assigned: dict[str, list[FixtureMarker]] = defaultdict(list)`.
  - For each fixture, first check `fixture.room_id`; if it matches a room id, assign to that room.
  - If `fixture.attributes.get("room")` or `fixture.attributes.get("ROOM")` matches a room id or room name, assign to that room.
  - Otherwise compute midpoint from first and last point; assign to every room whose polygon contains or touches the midpoint.
  - If no room contains the midpoint, assign to the nearest room whose boundary distance is within the existing marker-room tolerance.
  - Do not dedupe fixtures by geometry; overlapping cabinet lines must both survive.
- During row construction, build:

```python
custom_details = _custom_details_for_room(room, room_custom_items, room_name)
cabinet_details = _cabinet_details_for_room(room, room_cabinet_items, room_name)
```

- For custom details:
  - Effective height is marker height or `2.6`.
  - `pricing_mode=LENGTH` if marker height is not `None` and effective height `< 1.0`.
  - `projected_area=0` for length-priced low cabinets.
  - Otherwise `projected_area=length * effective_height`.

- Excluded rooms get empty fixture details.

- [ ] **Step 4: Run tests and verify GREEN**

Run the two quantity tests again. Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src\cad_budget\quantity.py tests\test_quantity.py
git commit -m "feat: calculate custom and cabinet fixture details"
```

## Task 4: Residential Quote Aggregates

**Files:**
- Modify: `src/cad_budget/quote_excel.py`
- Modify: `src/cad_budget/config/residential_quote_rules.json`
- Test: `tests/test_quote_excel.py`

- [ ] **Step 1: Write failing quote tests**

Add default rule assertions:

```python
assert "全屋定制" in rules.custom_projected_area_items
assert "橱柜" in rules.cabinet_length_items
assert rules.default_custom_height == 2.6
assert rules.low_custom_height_threshold == 1.0
```

Add export test:

```python
def test_export_residential_quote_auto_fills_custom_and_cabinet_items(tmp_path: Path):
    template_path = tmp_path / "template.xlsx"
    output_path = tmp_path / "quote.xlsx"
    _create_quote_template(template_path, include_custom_cabinet_items=True)
    result = QuantityResult(
        project_name="Custom Cabinet Quote Demo",
        rows=[
            _quantity_row(
                "bed",
                "主卧",
                floor_area=12.0,
                net_wall_area=30.0,
                custom_details=[
                    FixtureQuantityDetail(
                        id="wardrobe",
                        room_id="bed",
                        room_name="主卧",
                        kind=FixtureKind.CUSTOM,
                        length=2.0,
                        height=None,
                        effective_height=2.6,
                        height_defaulted=True,
                        projected_area=5.2,
                        pricing_mode=FixturePricingMode.PROJECTED_AREA,
                        fixture_type="衣柜",
                    ),
                    FixtureQuantityDetail(
                        id="low",
                        room_id="bed",
                        room_name="主卧",
                        kind=FixtureKind.CUSTOM,
                        length=1.0,
                        height=0.8,
                        effective_height=0.8,
                        height_defaulted=False,
                        projected_area=0.0,
                        pricing_mode=FixturePricingMode.LENGTH,
                        fixture_type="矮柜",
                    ),
                ],
            ),
            _quantity_row(
                "kitchen",
                "厨房",
                floor_area=6.0,
                net_wall_area=18.0,
                cabinet_details=[
                    FixtureQuantityDetail(
                        id="base",
                        room_id="kitchen",
                        room_name="厨房",
                        kind=FixtureKind.CABINET,
                        length=3.0,
                        pricing_mode=FixturePricingMode.LENGTH,
                        fixture_type="地柜",
                    ),
                    FixtureQuantityDetail(
                        id="wall",
                        room_id="kitchen",
                        room_name="厨房",
                        kind=FixtureKind.CABINET,
                        length=3.0,
                        pricing_mode=FixturePricingMode.LENGTH,
                        fixture_type=None,
                    ),
                ],
            ),
        ],
        exceptions=[],
    )

    export_residential_quote(result, template_path, output_path)

    workbook = load_workbook(output_path, data_only=False)
    rows = list(workbook.active.iter_rows(values_only=True))
    custom = _item_row_named(rows, "全屋定制")
    cabinet = _item_row_named(rows, "橱柜")
    assert custom[3] == 5.2
    assert custom[12] == "全屋定制投影面积汇总"
    assert custom[13] == "自动生成-默认推断"
    assert "默认2.6m" in custom[14]
    assert "高度小于1m" in custom[14]
    assert cabinet[3] == 6.0
    assert cabinet[12] == "橱柜长度汇总"
    assert "地柜/吊柜需确认" in cabinet[14]
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
py -3.14 -m pytest tests\test_quote_excel.py::test_load_default_quote_rules_reads_packaged_rule_file tests\test_quote_excel.py::test_export_residential_quote_auto_fills_custom_and_cabinet_items -q
```

Expected: fail because rules and aggregates are missing.

- [ ] **Step 3: Implement rules and aggregates**

In `ResidentialQuoteRules`, add:

```python
custom_projected_area_items: set[str]
cabinet_length_items: set[str]
default_custom_height: float
low_custom_height_threshold: float
```

Load them with `_optional_item_set` and `_optional_float`.

In `_aggregate_quantity_for_item`:

- If item in `custom_projected_area_items`:
  - Collect rows with `custom_details`.
  - Quantity is sum of `detail.projected_area` where `pricing_mode == PROJECTED_AREA`.
  - If no custom details, return `None` to preserve template default.
  - Review note includes default height, low-height length total, missing type, and missing room if applicable.
- If item in `cabinet_length_items`:
  - Quantity is sum of all `cabinet_details.length`.
  - If no cabinet details, return `None`.
  - Review note includes missing type if any.

Update `src/cad_budget/config/residential_quote_rules.json`.

- [ ] **Step 4: Run tests and verify GREEN**

Run the two quote tests again. Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src\cad_budget\quote_excel.py src\cad_budget\config\residential_quote_rules.json tests\test_quote_excel.py
git commit -m "feat: quote custom and cabinet fixture aggregates"
```

## Task 5: Documentation And Real Sample Verification

**Files:**
- Modify: `docs/cad-lightweight-drawing-standard-zh.md`
- Modify: `docs/residential-quote-remaining-defaults-audit-zh.md`
- Modify: `README.md`

- [ ] **Step 1: Update CAD drawing standard**

Document:

- `QUOTE_CUSTOM`
- `QUOTE_CABINET`
- Supported entities: `LINE`, `LWPOLYLINE`
- Attributes: `HEIGHT/高`, `TYPE/类型`, `ROOM/空间`
- Full custom default height `2.6m`
- Custom height `<1m` length pricing
- Cabinet `TYPE=地柜/吊柜` because plan geometry can overlap

- [ ] **Step 2: Update remaining defaults audit**

Move `全屋定制` and `橱柜` from “needs new layer” to “automated when markers exist; template default when markers are absent.” Leave background wall and pipe items unchanged.

- [ ] **Step 3: Run focused tests**

Run:

```powershell
py -3.14 -m pytest tests\test_models.py tests\test_dxf_adapter.py tests\test_quantity.py tests\test_quote_excel.py -q
```

Expected: pass.

- [ ] **Step 4: Run full tests**

Run:

```powershell
$env:PYTHONPATH='src'; py -3.14 -m pytest -q
```

Expected: pass.

- [ ] **Step 5: Real sample verification**

Run:

```powershell
$env:PYTHONPATH='src'; py -3.14 -c "from cad_budget.cli import app; app()" quote scratch\cad-import-test\result.json --template "D:\Desktop\清单式报价表（商品房）.xlsx" --excel-output scratch\cad-import-test\quote-coverage-enhanced.xlsx
```

Expected for current real sample without new markers:

- `全屋定制` remains `模板默认`.
- `橱柜` remains `模板默认`.
- No regression in automation summary for existing automated rows.

- [ ] **Step 6: Commit**

```powershell
git add docs\cad-lightweight-drawing-standard-zh.md docs\residential-quote-remaining-defaults-audit-zh.md README.md
git commit -m "docs: document custom and cabinet CAD quote markers"
```

## Task 6: Final Verification

**Files:**
- No code changes unless verification reveals a defect.

- [ ] **Step 1: Run diff check**

Run:

```powershell
git diff --check
```

Expected: no output.

- [ ] **Step 2: Run full test suite**

Run:

```powershell
$env:PYTHONPATH='src'; py -3.14 -m pytest -q
```

Expected: pass.

- [ ] **Step 3: Inspect git status**

Run:

```powershell
git status --short
```

Expected: clean worktree after commits.

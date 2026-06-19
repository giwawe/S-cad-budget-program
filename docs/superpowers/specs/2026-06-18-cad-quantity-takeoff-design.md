# CAD Quantity Takeoff Design

Date: 2026-06-18

## Goal

Build the first version of a CAD-based renovation quantity takeoff tool.

The input is a DWG floor plan. The output is an editable quantity table that is accurate enough to become the basis for later renovation pricing. The first version focuses on quantity takeoff, not final quotation generation.

Accuracy is more important than full automation. Designers can make small CAD drawing adjustments to improve system recognition.

## Product Direction

Use a lightweight CAD drawing standard plus automatic recognition.

The system should automatically read standard layers, generate an initial takeoff table, and only ask users to handle exceptions or uncertain data. The expected workflow is:

1. Designer prepares the DWG or DXF with the required `QUOTE_*` layers.
2. User uploads the DWG or DXF.
3. DXF is parsed directly; DWG is automatically converted to DXF first. If conversion fails, the designer is asked to save the drawing as DXF and upload again.
4. System parses room boundaries, room names, walls, windows, openings, doors, floors, and heights.
5. System generates an editable takeoff table.
6. User reviews only exceptions or default-inferred values.
7. Confirmed takeoff data is exported and used later as pricing input.

## CAD Adapter Input Strategy

The first version uses `direct DXF parsing + automatic DWG-to-DXF conversion + fallback guidance when conversion fails`.

The system boundary should stay explicit:

```text
DWG / DXF file -> CAD Adapter -> ProjectInput JSON -> Quantity Engine -> Editable Excel / JSON table
```

The CAD Adapter only translates CAD files into the standard `ProjectInput` data contract. It should not own quotation formulas or final pricing logic. This keeps CAD parsing, quantity formulas, and future quotation modules independently evolvable.

File handling rules:

```text
DXF
- Read directly with a DXF parser.
- Convert parsed entities into ProjectInput JSON.

DWG
- Convert to DXF through a backend conversion tool.
- Reuse the same DXF parsing logic after conversion.
- If conversion fails, block parsing and ask the designer to save as DXF from CAD and upload again.
```

The system should retain these traceability artifacts:

```text
Original uploaded file
Converted DXF file
CAD Adapter parse log
Generated ProjectInput JSON
Exception list
```

CAD unit handling uses double validation:

1. Read the unit from the DXF/DWG file.
2. Ask the user to confirm the project unit during upload.
3. If the file unit conflicts with the user-confirmed unit, block or raise a severe exception to avoid global scale errors.

## CAD Layer Standard

### Required Core Layers

`QUOTE_ROOM`

Space boundary. Each room or space should have one closed polyline. This is the main source for floor area, room ownership, and floor perimeter.

`QUOTE_WINDOW`

Window marker. The system reads width and height from block attributes when available. If height is missing, the system uses a default window height and marks the value as default-inferred.

The first version also supports the current window drawing convention: a closed window opening outline on the `QUOTE_WINDOW` layer. The outline may be a rectangle, polygon, or closed shape with arcs, and may contain internal line segments as window-symbol features. The system should recognize the closed outline, prefer block attributes or tags for width, and otherwise infer width from the outline's principal-direction projection length or the boundary length that overlaps or follows the wall. It then combines the inferred width with window height to calculate window area.

### Optional Core Layers

`QUOTE_TEXT`

Room name text. If this layer is present, it is the preferred room name source. If absent, the system should try to read existing CAD text inside the `QUOTE_ROOM` boundary.

Room name priority:

1. Block attributes or standard tags.
2. `QUOTE_TEXT`.
3. Ordinary CAD text inside the `QUOTE_ROOM` boundary.
4. Manual table entry.

`QUOTE_DOOR`

Door opening marker. The first version reads and stores door opening data, but door opening area is not deducted from wall area by default. Doors may use the existing model or block library; the system should prefer block name, insertion point, rotation, scale, and attributes, and fall back to geometric door-width inference when attributes are missing.

### Recommended Accuracy Layers

`QUOTE_WALL`

Actual wall or paintable wall geometry. This is used to calculate wall-measure perimeter and to avoid counting open room boundaries as wall surface.

`QUOTE_OPENING`

Open boundary or non-wall boundary. This is used for spaces such as open living/dining areas, where the `QUOTE_ROOM` boundary is closed for floor calculation but part of the boundary is not an actual wall and should not be included in paint area.

### Multistory Layers

`QUOTE_FLOOR`

Floor marker for villas and multistory projects.

`QUOTE_HEIGHT`

Optional height marker. If present, it overrides floor default height and project default height.

## Height Rules

Height priority:

1. Manually edited room height.
2. `QUOTE_HEIGHT` marker.
3. Floor default height.
4. Project default height.

Commercial apartment projects can usually use one project default height. Villa projects should support one default height per floor, with room-level overrides when needed.

## Open Space Wall Measurement

Floor boundary and wall-measure boundary are separate concepts.

`QUOTE_ROOM` is always used for floor area and floor perimeter. It must not be blindly used as wall-measure perimeter.

For open spaces such as living rooms and dining rooms:

```text
Floor area = QUOTE_ROOM closed boundary area
Floor perimeter = QUOTE_ROOM closed boundary perimeter
Wall-measure perimeter = only the parts of the room boundary that are actual wall or paintable wall
```

Wall area formulas:

```text
Gross wall area = wall-measure perimeter * height
Net wall area = gross wall area - window area
```

Door opening area is recorded but not deducted by default in the first version.

Wall-measure perimeter recognition priority:

1. If a boundary segment is marked by `QUOTE_OPENING`, it is not counted as wall.
2. If a `QUOTE_ROOM` boundary segment is near or overlaps `QUOTE_WALL`, it is counted as wall.
3. If there is neither wall match nor opening marker, the segment is marked as uncertain.
4. Users can edit wall-measure perimeter in the table or later in a drawing review UI.

The quantity table must expose both floor perimeter and wall-measure perimeter to avoid confusion.

## Special Space Rules

The first version should support special spaces through lightweight CAD standards and explicit space types. It should not try to infer complex building semantics from arbitrary geometry.

Recommended space types:

```text
normal
void
void_opening
stair
stair_hall
balcony
terrace
elevator_shaft
```

The space type can come from a CAD object attribute, a room text convention, a table edit, or a dedicated marker layer when needed.

### Void / Double-Height Spaces

Villa projects often include double-height living rooms or other void spaces.

Recommended CAD support:

```text
QUOTE_VOID
```

`QUOTE_VOID` marks a double-height region or a slab opening. It can be associated with a `QUOTE_ROOM` boundary.

Calculation rules:

```text
Floor area = first-floor QUOTE_ROOM boundary area
Floor perimeter = first-floor QUOTE_ROOM boundary perimeter
Wall-measure perimeter = QUOTE_WALL / QUOTE_OPENING based perimeter
Gross wall area = wall-measure perimeter * void actual height
Net wall area = gross wall area - window area
```

Void height priority:

1. Manually edited room height.
2. `QUOTE_HEIGHT` marker.
3. `QUOTE_VOID` height attribute.
4. Sum of related floor default heights.
5. Project default height.

If an upper floor contains the same void as a slab opening, that upper-floor void should not be treated as a normal room and should not create floor area. It can be shown as an auxiliary `void_opening` row for review.

### Stair and Stair Hall Spaces

Stair-related spaces should be marked explicitly:

```text
space_type = stair
space_type = stair_hall
```

Rules:

```text
Stair space
- Record floor area as a special area.
- Calculate wall area using QUOTE_WALL / QUOTE_OPENING and the relevant height.
- Do not automatically calculate stair tread, riser, sloped slab, handrail, or detailed stair finish quantities in the first version.
- Provide manual-entry fields for stair-specific quantities later.

Stair hall
- If it is a normal flat circulation space, calculate like a normal room.
- If it connects to a void or stairwell, allow opening boundaries and uncertain wall segments.
```

### Balcony and Terrace Spaces

Balconies and terraces should be explicitly marked:

```text
space_type = balcony
space_type = terrace
```

Rules:

```text
Balcony
- Calculate floor area.
- Calculate wall area only for actual wall segments.
- Do not count railing or open edges as interior wall area.
- If enclosed by windows, use QUOTE_WINDOW and deduct window area.

Terrace
- Calculate floor area.
- Usually count only adjacent building walls or parapet walls where relevant.
- Do not count open edges as interior wall paint area.
- Use table fields to decide whether the space is included in interior renovation quantities.
```

The table should expose:

```text
Is outdoor space
Include in interior floor quantity
Include in interior wall paint quantity
```

### Elevator Shaft

Elevator shafts should be marked explicitly:

```text
space_type = elevator_shaft
```

Rules:

```text
- Default to excluded from renovation quantity takeoff.
- Do not count floor area.
- Do not count wall area.
- Keep as an auxiliary row or validation object so it is not mistaken for a normal room.
```

### Exterior Wall Area

Interior wall quantity and exterior facade quantity should be separate.

The first version may support exterior wall area through lightweight dedicated layers:

```text
QUOTE_EXT_WALL
QUOTE_EXT_OPENING
```

Rules:

```text
Exterior gross wall area = exterior wall measure length * exterior wall height
Exterior net wall area = exterior gross wall area - exterior opening area
```

Exterior wall quantities should be shown in a separate exterior/facade table, not mixed into room rows. The first version should not attempt to automatically handle complex facade modeling, insulation systems, stone/paint assemblies, or decorative exterior shapes.

## Quantity Table

The generated table has one row per space.

Recommended fields:

```text
Floor
Room name
Height
Floor area
Floor perimeter
Wall-measure perimeter
Open boundary length
Gross wall area
Window count
Window area
Door opening count
Door opening area
Net wall area
Space type
Height mode
Calculation height
Related floors
Is outdoor space
Include in interior floor quantity
Include in interior wall paint quantity
Recognition status
Exception notes
```

Editable fields should include:

```text
Room name
Floor
Height
Window height
Window area
Wall-measure perimeter
Open boundary length
Space type
Calculation height
Include/exclude flags
Status / confirmation
```

When editable inputs change, dependent values must recalculate automatically.

## Data Status

Every important value should have a source/status so the table is auditable.

Statuses:

`confirmed`

Read from standard CAD layers with complete data or manually confirmed.

`default_inferred`

The system used a default value, such as default window height.

`needs_review`

The system detected missing, conflicting, or uncertain data.

`manually_edited`

The user changed the generated value.

Later quotation generation should use only confirmed or manually accepted data.

## Exception Severity

Parse results use severity levels so the system does not silently produce wrong quantities.

Severe issues block formal table generation:

```text
DWG-to-DXF conversion failed
CAD unit cannot be confirmed or conflicts with the user-confirmed unit
Required layers are missing
Room boundary is not closed
Room area is zero or clearly abnormal
Required floor information is missing in a multistory project
```

Minor issues still generate the table, but the relevant row and the exception summary must mark them as needing confirmation:

```text
Window height is missing and default height was used
Room name came from ordinary CAD text with low confidence
Door model has no attributes and geometric width inference was used
Window closed outline has a slight wall matching offset
Wall-measure boundary has uncertain segments
Special space type was inferred from name instead of explicit attributes
```

The quantity table should include value source, confidence, review flag, and issue notes. Later quotation should use only `confirmed`, `manually_edited`, or user-accepted values by default.

## Recognition and Calculation Rules

Room recognition:

1. Read closed polylines from `QUOTE_ROOM`.
2. Validate that each room boundary is closed.
3. Calculate floor area and floor perimeter from the closed boundary.
4. Match room name from `QUOTE_TEXT`, or fallback to ordinary CAD text inside the boundary.
5. Detect missing names, duplicate names, overlapping rooms, and invalid boundaries.

Window recognition:

1. Read `QUOTE_WINDOW`.
2. Prefer block attributes for width and height.
3. If the window is not represented by block attributes, recognize a closed window opening outline on `QUOTE_WINDOW`; the outline may be a rectangle, polygon, or closed shape with arcs, and internal line segments may be used as auxiliary symbol features.
4. For rectangular windows, infer width from the long side. For polygonal or arc-based windows, infer width from the principal-direction projection length or from the boundary length that overlaps or follows the wall.
5. If height is missing, use default window height and mark as `default_inferred`.
6. Match windows to room boundaries or wall segments.
7. Calculate window area and deduct it from wall area.

Door recognition:

1. Read `QUOTE_DOOR`.
2. Prefer block name, insertion point, rotation, scale, and attributes from the existing door model or block.
3. If attributes are missing, infer door width from door-end distance or model geometry.
4. Store door count and door opening area if available.
5. Do not deduct door area from wall area by default in the first version.

Wall recognition:

1. Read `QUOTE_WALL`.
2. Compare `QUOTE_ROOM` boundary segments with nearby `QUOTE_WALL`.
3. Exclude `QUOTE_OPENING` segments.
4. Generate wall-measure perimeter.
5. Mark uncertain wall segments as exceptions.

## Exception List

The system should report these exceptions:

```text
Room boundary is not closed
Room boundary overlaps another room
Room has no name
Multiple names are inside one room
Window cannot be assigned to a room or wall
Window height is missing and default height was used
Door cannot be assigned to a room or wall
Wall-measure boundary is uncertain
QUOTE_OPENING conflicts with QUOTE_WALL
Void height is missing or uncertain
Upper-floor void opening is mistaken for normal room
Stair space requires manual stair-specific quantities
Balcony or terrace open edge is uncertain
Elevator shaft is not marked as excluded
Exterior wall height or opening data is missing
Floor is missing in a multistory project
Height is missing and default height was used
CAD unit or scale is unclear
```

Exceptions should appear both in the table row and in a separate exception summary.

## System Modules

### DWG Import Module

Uploads DWG files and converts them to a parseable intermediate format, likely DXF or JSON. DWG is a closed format, so the implementation should avoid depending on hand-written DWG parsing.

### CAD Standard Recognition Module

Reads the `QUOTE_*` layers and converts CAD objects into structured entities:

```text
RoomBoundary
RoomText
WindowMarker
DoorMarker
WallGeometry
OpeningGeometry
FloorMarker
HeightMarker
VoidMarker
ExteriorWallGeometry
ExteriorOpeningGeometry
```

### Geometry Matching Module

Assigns text, windows, doors, walls, openings, floors, and heights to rooms.

It also validates geometry and produces exceptions.

### Quantity Engine

Computes floor area, floor perimeter, wall-measure perimeter, gross wall area, window area, door opening area, and net wall area.

The engine should be formula-driven and separate from CAD parsing.

### Editable Table Module

Shows the generated takeoff table, value sources, statuses, and exceptions.

It allows users to edit values and recalculates dependent fields.

### Export Module

Exports the confirmed takeoff table to Excel for use as pricing input.

## First Version Scope

Included:

```text
DWG import and conversion
QUOTE_ROOM parsing
QUOTE_TEXT and fallback CAD text parsing
QUOTE_WINDOW parsing
QUOTE_DOOR parsing, stored but not deducted
QUOTE_WALL parsing
QUOTE_OPENING parsing
QUOTE_VOID parsing for double-height spaces and slab openings
Special space type support for stair, stair hall, balcony, terrace, and elevator shaft
Optional QUOTE_EXT_WALL and QUOTE_EXT_OPENING parsing for exterior wall quantities
Project default height
Floor default height
Room-level height override
Editable quantity table
Exception summary
Excel export
```

Not included:

```text
Final renovation quotation generation
Machine-learning recognition of arbitrary unstandardized DWG files
Automatic room boundary inference without QUOTE_ROOM
Door opening deduction by default
Automatic stair tread/riser/sloped slab quantity calculation
Automatic complex facade modeling or exterior finish system calculation
Full support for every possible CAD drawing style
```

## Success Criteria

The first version is successful if:

1. A DWG following the `QUOTE_*` standard produces one editable row per room.
2. Floor area is calculated from `QUOTE_ROOM`.
3. Wall area for open spaces does not incorrectly count open boundaries.
4. Window area is deducted, using block height when available and default height otherwise.
5. Door data is retained but does not affect wall area by default.
6. Double-height spaces can use explicit height and do not create duplicate upper-floor room quantities.
7. Stair, balcony, terrace, and elevator shaft spaces can be marked and handled by their first-version rules.
8. Exterior wall quantities, if enabled, are kept separate from room quantities.
9. Users can identify and resolve uncertain data before exporting.
10. The exported Excel table is suitable as the input for a later quotation module.

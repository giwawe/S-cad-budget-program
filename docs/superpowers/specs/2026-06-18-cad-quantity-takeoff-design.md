# CAD Quantity Takeoff Design

Date: 2026-06-18

## Goal

Build the first version of a CAD-based renovation quantity takeoff tool.

The input is a DWG floor plan. The output is an editable quantity table that is accurate enough to become the basis for later renovation pricing. The first version focuses on quantity takeoff, not final quotation generation.

Accuracy is more important than full automation. Designers can make small CAD drawing adjustments to improve system recognition.

## Product Direction

Use a lightweight CAD drawing standard plus automatic recognition.

The system should automatically read standard layers, generate an initial takeoff table, and only ask users to handle exceptions or uncertain data. The expected workflow is:

1. Designer prepares the DWG with the required `QUOTE_*` layers.
2. User uploads the DWG.
3. System parses room boundaries, room names, walls, windows, openings, doors, floors, and heights.
4. System generates an editable takeoff table.
5. User reviews only exceptions or default-inferred values.
6. Confirmed takeoff data is exported and used later as pricing input.

## CAD Layer Standard

### Required Core Layers

`QUOTE_ROOM`

Space boundary. Each room or space should have one closed polyline. This is the main source for floor area, room ownership, and floor perimeter.

`QUOTE_WINDOW`

Window marker. The system reads width and height from block attributes when available. If height is missing, the system uses a default window height and marks the value as default-inferred.

### Optional Core Layers

`QUOTE_TEXT`

Room name text. If this layer is present, it is the preferred room name source. If absent, the system should try to read existing CAD text inside the `QUOTE_ROOM` boundary.

`QUOTE_DOOR`

Door opening marker. The first version reads and stores door opening data, but door opening area is not deducted from wall area by default.

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
3. If height is missing, use default window height and mark as `default_inferred`.
4. Match windows to room boundaries or wall segments.
5. Calculate window area and deduct it from wall area.

Door recognition:

1. Read `QUOTE_DOOR`.
2. Store door count and door opening area if available.
3. Do not deduct door area from wall area by default in the first version.

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
Full support for every possible CAD drawing style
```

## Success Criteria

The first version is successful if:

1. A DWG following the `QUOTE_*` standard produces one editable row per room.
2. Floor area is calculated from `QUOTE_ROOM`.
3. Wall area for open spaces does not incorrectly count open boundaries.
4. Window area is deducted, using block height when available and default height otherwise.
5. Door data is retained but does not affect wall area by default.
6. Users can identify and resolve uncertain data before exporting.
7. The exported Excel table is suitable as the input for a later quotation module.

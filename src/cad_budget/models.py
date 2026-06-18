from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


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


class SpaceType(str, Enum):
    NORMAL = "normal"
    VOID = "void"
    VOID_OPENING = "void_opening"
    STAIR = "stair"
    STAIR_HALL = "stair_hall"
    BALCONY = "balcony"
    TERRACE = "terrace"
    ELEVATOR_SHAFT = "elevator_shaft"


class DataStatus(str, Enum):
    CONFIRMED = "confirmed"
    DEFAULT_INFERRED = "default_inferred"
    NEEDS_REVIEW = "needs_review"
    MANUALLY_EDITED = "manually_edited"
    EXCLUDED = "excluded"


class HeightMode(str, Enum):
    PROJECT_DEFAULT = "project_default"
    FLOOR_DEFAULT = "floor_default"
    QUOTE_HEIGHT = "quote_height"
    QUOTE_VOID = "quote_void"
    MANUAL = "manual"
    RELATED_FLOORS_SUM = "related_floors_sum"


class Point(BaseModel):
    x: float
    y: float


class RoomBoundary(BaseModel):
    id: str
    layer: LayerName = LayerName.QUOTE_ROOM
    points: list[Point]
    floor: str | None = None
    name: str | None = None
    space_type: SpaceType = SpaceType.NORMAL
    include_in_floor_quantity: bool = True
    include_in_wall_paint_quantity: bool = True
    is_outdoor: bool = False
    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("points")
    @classmethod
    def validate_points(cls, points: list[Point]) -> list[Point]:
        if len(points) < 4:
            raise ValueError("room boundary must include at least 4 points including closure")
        if points[0].x != points[-1].x or points[0].y != points[-1].y:
            raise ValueError("room boundary must be closed (first point equals last point)")
        return points


class TextMarker(BaseModel):
    id: str
    layer: LayerName = LayerName.QUOTE_TEXT
    text: str
    point: Point
    floor: str | None = None


class WindowMarker(BaseModel):
    id: str
    layer: LayerName = LayerName.QUOTE_WINDOW
    point: Point
    width: float
    height: float | None = None
    floor: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class DoorMarker(BaseModel):
    id: str
    layer: LayerName = LayerName.QUOTE_DOOR
    point: Point
    width: float | None = None
    height: float | None = None
    floor: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class PolylineMarker(BaseModel):
    id: str
    layer: LayerName
    points: list[Point]
    floor: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("points")
    @classmethod
    def validate_points(cls, points: list[Point]) -> list[Point]:
        if len(points) < 2:
            raise ValueError("polyline must include at least 2 points")
        return points


class HeightMarker(BaseModel):
    id: str
    layer: LayerName = LayerName.QUOTE_HEIGHT
    point: Point
    height: float
    floor: str | None = None
    room_id: str | None = None


class VoidMarker(BaseModel):
    id: str
    layer: LayerName = LayerName.QUOTE_VOID
    points: list[Point]
    height: float | None = None
    related_floors: list[str] = Field(default_factory=list)
    floor: str | None = None


class ProjectInput(BaseModel):
    project_name: str = "Untitled"
    default_height: float = 2.8
    default_window_height: float = 1.5
    floor_heights: dict[str, float] = Field(default_factory=dict)
    rooms: list[RoomBoundary] = Field(default_factory=list)
    texts: list[TextMarker] = Field(default_factory=list)
    windows: list[WindowMarker] = Field(default_factory=list)
    doors: list[DoorMarker] = Field(default_factory=list)
    walls: list[PolylineMarker] = Field(default_factory=list)
    openings: list[PolylineMarker] = Field(default_factory=list)
    heights: list[HeightMarker] = Field(default_factory=list)
    voids: list[VoidMarker] = Field(default_factory=list)
    exterior_walls: list[PolylineMarker] = Field(default_factory=list)
    exterior_openings: list[PolylineMarker] = Field(default_factory=list)


class QuantityException(BaseModel):
    code: str
    message: str
    room_id: str | None = None
    severity: str = "warning"


class QuantityRow(BaseModel):
    room_id: str
    floor: str | None
    room_name: str
    space_type: SpaceType
    height: float
    height_mode: HeightMode
    floor_area: float
    floor_perimeter: float
    wall_measure_perimeter: float
    open_boundary_length: float
    gross_wall_area: float
    window_count: int
    window_area: float
    door_opening_count: int
    door_opening_area: float
    net_wall_area: float
    is_outdoor: bool
    include_in_floor_quantity: bool
    include_in_wall_paint_quantity: bool
    status: DataStatus
    exception_notes: list[str] = Field(default_factory=list)


class QuantityResult(BaseModel):
    project_name: str
    rows: list[QuantityRow]
    exceptions: list[QuantityException]

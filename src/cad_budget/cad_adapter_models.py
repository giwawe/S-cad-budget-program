from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, computed_field

from cad_budget.models import ProjectInput


class AdapterSeverity(str, Enum):
    BLOCKER = "blocker"
    WARNING = "warning"


class CadUnit(str, Enum):
    MILLIMETER = "mm"
    CENTIMETER = "cm"
    METER = "m"


class AdapterIssue(BaseModel):
    code: str
    message: str
    severity: AdapterSeverity = AdapterSeverity.WARNING
    entity_id: str | None = None
    layer: str | None = None


class CadImportOptions(BaseModel):
    source_path: Path
    confirmed_unit: CadUnit = CadUnit.MILLIMETER
    project_name_override: str | None = None
    default_height: float = 2.8
    default_window_height: float = 1.5
    floor_heights: dict[str, float] = Field(default_factory=dict)
    dwg_converter_command: list[str] | None = None

    @computed_field
    @property
    def project_name(self) -> str:
        if self.project_name_override:
            return self.project_name_override
        return self.source_path.stem


class CadImportResult(BaseModel):
    project: ProjectInput | None = None
    issues: list[AdapterIssue] = Field(default_factory=list)
    source_path: Path
    dxf_path: Path | None = None

    @property
    def has_blockers(self) -> bool:
        return any(issue.severity == AdapterSeverity.BLOCKER for issue in self.issues)

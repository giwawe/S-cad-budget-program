from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_DXF_PATH = Path("D:/Desktop/10.dxf")
DEFAULT_TEMPLATE_PATH = Path("D:/Desktop/\u6e05\u5355\u5f0f\u62a5\u4ef7\u8868\uff08\u5546\u54c1\u623f\uff09-\u4fee\u6b63\u7248.xlsx")
DEFAULT_UNIT_PRICES_PATH = Path("scratch/cad-import-10-real-template-current/quote-unit-prices.xlsx")
DEFAULT_OUTPUT_ROOT = Path("scratch")


@dataclass(frozen=True)
class GuiSettings:
    dxf_path: Path
    template_path: Path
    unit_prices_path: Path
    output_root: Path

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "GuiSettings":
        defaults = default_gui_settings()
        return cls(
            dxf_path=Path(data.get("dxf_path") or defaults.dxf_path),
            template_path=Path(data.get("template_path") or defaults.template_path),
            unit_prices_path=Path(data.get("unit_prices_path") or defaults.unit_prices_path),
            output_root=Path(data.get("output_root") or defaults.output_root),
        )

    def to_json(self) -> dict[str, str]:
        return {key: str(value) for key, value in asdict(self).items()}


def default_gui_settings() -> GuiSettings:
    return GuiSettings(
        dxf_path=DEFAULT_DXF_PATH,
        template_path=DEFAULT_TEMPLATE_PATH,
        unit_prices_path=DEFAULT_UNIT_PRICES_PATH,
        output_root=DEFAULT_OUTPUT_ROOT,
    )


def default_gui_settings_path() -> Path:
    appdata = os.environ.get("APPDATA")
    root = Path(appdata) if appdata else Path.home() / ".cad-budget"
    return root / "cad-budget" / "gui-settings.json"


def load_gui_settings(config_path: Path | None = None) -> GuiSettings:
    path = config_path or default_gui_settings_path()
    if not path.exists():
        return default_gui_settings()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return default_gui_settings()
    return GuiSettings.from_json(data)


def save_gui_settings(settings: GuiSettings, config_path: Path | None = None) -> None:
    path = config_path or default_gui_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")

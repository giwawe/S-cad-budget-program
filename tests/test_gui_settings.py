from __future__ import annotations

from pathlib import Path

from cad_budget.gui_settings import GuiSettings, default_gui_settings, load_gui_settings, save_gui_settings


def test_default_gui_settings_prefill_real_acceptance_paths() -> None:
    settings = default_gui_settings()

    assert settings.dxf_path == Path("D:/Desktop/10.dxf")
    assert settings.template_path == Path("D:/Desktop/\u6e05\u5355\u5f0f\u62a5\u4ef7\u8868\uff08\u5546\u54c1\u623f\uff09-\u4fee\u6b63\u7248.xlsx")
    assert settings.unit_prices_path == Path("scratch/cad-import-10-real-template-current/quote-unit-prices.xlsx")
    assert settings.output_root == Path("scratch")


def test_gui_settings_round_trip_json(tmp_path: Path) -> None:
    config_path = tmp_path / "gui-settings.json"
    settings = GuiSettings(
        dxf_path=tmp_path / "plan.dxf",
        template_path=tmp_path / "template.xlsx",
        unit_prices_path=tmp_path / "prices.xlsx",
        output_root=tmp_path / "out",
    )

    save_gui_settings(settings, config_path)
    loaded = load_gui_settings(config_path)

    assert loaded == settings

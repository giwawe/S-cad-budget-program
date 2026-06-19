from pathlib import Path

from cad_budget.cad_adapter_models import (
    AdapterIssue,
    AdapterSeverity,
    CadImportOptions,
    CadUnit,
)


def test_adapter_issue_defaults_to_warning():
    issue = AdapterIssue(code="WINDOW_HEIGHT_DEFAULTED", message="Window height used default")

    assert issue.severity == AdapterSeverity.WARNING
    assert issue.entity_id is None
    assert issue.layer is None


def test_cad_import_options_defaults_for_millimeter_project():
    options = CadImportOptions(source_path=Path("sample.dxf"))

    assert options.project_name == "sample"
    assert options.confirmed_unit == CadUnit.MILLIMETER
    assert options.default_height == 2.8
    assert options.default_window_height == 1.5

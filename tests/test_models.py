from cad_budget.models import ProjectInput


def test_project_input_can_be_imported():
    assert ProjectInput.__name__ == "ProjectInput"


def test_project_input_has_default_name():
    assert ProjectInput().project_name == "Untitled"


def test_project_input_accepts_custom_name():
    assert ProjectInput(project_name="Demo Condo").project_name == "Demo Condo"

from cad_budget.models import ProjectInput


def test_project_input_can_be_imported():
    assert ProjectInput.__name__ == "ProjectInput"

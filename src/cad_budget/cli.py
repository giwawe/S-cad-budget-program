import json
from pathlib import Path

import typer

from cad_budget.models import ProjectInput
from cad_budget.quantity import calculate_quantities

app = typer.Typer(help="CAD renovation quantity takeoff tools.")


@app.callback()
def main() -> None:
    """Entry point for the CLI."""
    return


@app.command()
def calculate(
    input_json: Path,
    json_output: Path = typer.Option(..., "--json-output", help="Path for calculated JSON output."),
) -> None:
    project = ProjectInput.model_validate_json(input_json.read_text(encoding="utf-8"))
    result = calculate_quantities(project)
    json_output.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    typer.echo(f"Wrote {json_output}")

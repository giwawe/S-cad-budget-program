import json
from pathlib import Path

import typer
from pydantic import ValidationError

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
    try:
        raw_json = input_json.read_text(encoding="utf-8")
    except OSError as exc:
        typer.echo(f"Failed to read input JSON '{input_json}': {exc}", err=True)
        raise typer.Exit(code=1)

    try:
        project = ProjectInput.model_validate_json(raw_json)
    except (json.JSONDecodeError, ValidationError) as exc:
        error_message = str(exc).splitlines()[0] if str(exc).splitlines() else str(exc)
        typer.echo(f"Invalid project JSON in '{input_json}': {error_message}", err=True)
        raise typer.Exit(code=1)

    result = calculate_quantities(project)
    try:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    except OSError as exc:
        typer.echo(f"Failed to write JSON output '{json_output}': {exc}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Wrote {json_output}")

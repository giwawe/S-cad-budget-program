import json
from pathlib import Path

import typer
from pydantic import ValidationError

from cad_budget.models import ProjectInput
from cad_budget.export_excel import export_quantity_result
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
    excel_output: Path | None = typer.Option(None, "--excel-output", help="Optional Excel output path."),
) -> None:
    try:
        raw_json = input_json.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        typer.echo(f"Failed to read input JSON '{input_json}': {exc}", err=True)
        raise typer.Exit(code=1)

    try:
        project = ProjectInput.model_validate_json(raw_json)
    except (json.JSONDecodeError, ValidationError) as exc:
        error_message = str(exc).splitlines()[0] if str(exc).splitlines() else str(exc)
        typer.echo(f"Invalid project JSON in '{input_json}': {error_message}", err=True)
        raise typer.Exit(code=1)

    try:
        result = calculate_quantities(project)
    except ValueError as exc:
        typer.echo(f"Failed to calculate quantities: {exc}", err=True)
        raise typer.Exit(code=1)
    wrote_outputs: list[str] = []

    try:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        wrote_outputs.append(f"Wrote {json_output}")
    except OSError as exc:
        typer.echo(f"Failed to write JSON output '{json_output}': {exc}", err=True)
        raise typer.Exit(code=1)

    if excel_output is not None:
        try:
            excel_output.parent.mkdir(parents=True, exist_ok=True)
            export_quantity_result(result, excel_output)
            wrote_outputs.append(f"Wrote {excel_output}")
        except OSError as exc:
            typer.echo(f"Failed to write Excel output '{excel_output}': {exc}", err=True)
            raise typer.Exit(code=1)

    for message in wrote_outputs:
        typer.echo(message)

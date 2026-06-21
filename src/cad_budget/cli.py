import json
from pathlib import Path

import typer
from pydantic import ValidationError

from cad_budget.cad_adapter_models import CadImportOptions, CadUnit
from cad_budget.dwg_converter import convert_dwg_to_dxf
from cad_budget.dxf_adapter import import_dxf
from cad_budget.models import ProjectInput, QuantityResult
from cad_budget.export_excel import export_quantity_result
from cad_budget.import_excel import import_quantity_result
from cad_budget.quote_excel import default_quote_rules_text, export_residential_quote
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


@app.command("import-cad")
def import_cad(
    input_cad: Path,
    json_output: Path = typer.Option(..., "--json-output", help="Path for generated ProjectInput JSON."),
    unit: CadUnit = typer.Option(CadUnit.MILLIMETER, "--unit", help="Confirmed project CAD unit."),
    project_name: str | None = typer.Option(None, "--project-name", help="Optional project name override."),
    dwg_converter: list[str] | None = typer.Option(
        None,
        "--dwg-converter",
        help="DWG converter command parts; use {input} and {output} placeholders.",
    ),
) -> None:
    extension = input_cad.suffix.lower()
    dxf_path = input_cad
    import_project_name = project_name

    if extension == ".dwg":
        conversion_output_dir = json_output.parent / "_converted"
        try:
            conversion = convert_dwg_to_dxf(input_cad, conversion_output_dir, dwg_converter)
        except OSError as exc:
            typer.echo(
                f"Failed to prepare DWG conversion output '{conversion_output_dir}': {exc}",
                err=True,
            )
            raise typer.Exit(code=1)
        if conversion.issue is not None:
            typer.echo(conversion.issue.message, err=True)
            raise typer.Exit(code=1)
        if conversion.dxf_path is None:
            typer.echo("DWG conversion did not return a DXF path.", err=True)
            raise typer.Exit(code=1)
        dxf_path = conversion.dxf_path
        import_project_name = project_name or input_cad.stem
    elif extension != ".dxf":
        typer.echo(f"Unsupported CAD file extension '{input_cad.suffix}'. Expected .dxf or .dwg.", err=True)
        raise typer.Exit(code=1)

    result = import_dxf(
        CadImportOptions(
            source_path=dxf_path,
            confirmed_unit=unit,
            project_name_override=import_project_name,
            dwg_converter_command=dwg_converter,
        )
    )

    for issue in result.issues:
        typer.echo(f"{issue.severity.value}: {issue.code}: {issue.message}", err=True)

    if result.has_blockers or result.project is None:
        if result.project is None and not result.has_blockers:
            typer.echo("CAD import did not produce a project.", err=True)
        raise typer.Exit(code=1)

    try:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(result.project.model_dump_json(indent=2), encoding="utf-8")
    except OSError as exc:
        typer.echo(f"Failed to write JSON output '{json_output}': {exc}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Wrote {json_output}")


@app.command("import-excel")
def import_excel(
    input_excel: Path,
    json_output: Path = typer.Option(..., "--json-output", help="Path for generated QuantityResult JSON."),
) -> None:
    try:
        result = import_quantity_result(input_excel)
    except (OSError, ValueError) as exc:
        typer.echo(f"Failed to import Excel workbook '{input_excel}': {exc}", err=True)
        raise typer.Exit(code=1)

    try:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    except OSError as exc:
        typer.echo(f"Failed to write JSON output '{json_output}': {exc}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Wrote {json_output}")


@app.command("quote")
def quote(
    input_json: Path,
    template: Path = typer.Option(..., "--template", help="Residential fitout quote template workbook."),
    rules: Path | None = typer.Option(None, "--rules", help="Optional residential quote rules JSON."),
    excel_output: Path = typer.Option(..., "--excel-output", help="Path for generated quote Excel output."),
) -> None:
    try:
        raw_json = input_json.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        typer.echo(f"Failed to read quantity result JSON '{input_json}': {exc}", err=True)
        raise typer.Exit(code=1)

    try:
        result = QuantityResult.model_validate_json(raw_json)
    except (json.JSONDecodeError, ValidationError) as exc:
        error_message = str(exc).splitlines()[0] if str(exc).splitlines() else str(exc)
        typer.echo(f"Invalid quantity result JSON in '{input_json}': {error_message}", err=True)
        raise typer.Exit(code=1)

    try:
        export_residential_quote(result, template, excel_output, rules_path=rules)
    except (OSError, ValueError) as exc:
        typer.echo(f"Failed to generate quote Excel '{excel_output}': {exc}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Wrote {excel_output}")


@app.command("init-rules")
def init_rules(
    output: Path = typer.Option(..., "--output", help="Path for generated residential quote rules JSON."),
) -> None:
    if output.exists():
        typer.echo(f"Rules output already exists '{output}'. Delete it first or choose another path.", err=True)
        raise typer.Exit(code=1)

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(default_quote_rules_text(), encoding="utf-8")
    except OSError as exc:
        typer.echo(f"Failed to write quote rules '{output}': {exc}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Wrote {output}")

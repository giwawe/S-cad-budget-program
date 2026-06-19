from pathlib import Path
import subprocess

from pydantic import BaseModel

from cad_budget.cad_adapter_models import AdapterIssue, AdapterSeverity


class DwgConversionResult(BaseModel):
    dxf_path: Path | None = None
    issue: AdapterIssue | None = None


def convert_dwg_to_dxf(
    dwg_path: Path,
    output_dir: Path,
    converter_command: list[str] | None,
) -> DwgConversionResult:
    if converter_command is None:
        return DwgConversionResult(
            issue=AdapterIssue(
                code="DWG_CONVERTER_NOT_CONFIGURED",
                message="DWG input requires a configured DWG-to-DXF converter.",
                severity=AdapterSeverity.BLOCKER,
            )
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    dxf_path = output_dir / f"{dwg_path.stem}.dxf"
    command = [
        part.replace("{input}", str(dwg_path)).replace("{output}", str(dxf_path))
        for part in converter_command
    ]

    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        return DwgConversionResult(
            issue=AdapterIssue(
                code="DWG_CONVERSION_FAILED",
                message=(
                    f"DWG conversion failed with exit code {completed.returncode}: "
                    f"{completed.stderr.strip()}"
                ),
                severity=AdapterSeverity.BLOCKER,
            )
        )

    if not dxf_path.exists():
        return DwgConversionResult(
            issue=AdapterIssue(
                code="DWG_CONVERSION_OUTPUT_MISSING",
                message=f"DWG converter succeeded but did not create {dxf_path}.",
                severity=AdapterSeverity.BLOCKER,
            )
        )

    return DwgConversionResult(dxf_path=dxf_path)

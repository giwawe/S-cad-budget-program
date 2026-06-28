from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


_HEADER_ROW = 3
_FIRST_DATA_ROW = 4
_REVIEW_STATUSES = [
    "自动生成-默认推断",
    "自动生成-异常提示",
    "按模板生成",
]


@dataclass(frozen=True)
class QuoteReviewRow:
    excel_row: int
    number: int
    item_name: str
    quantity: Any
    quantity_source: str | None
    source_room: str | None
    basis: str | None
    review_status: str
    review_note: str | None


def generate_quote_review_report(input_excel: Path, markdown_output: Path) -> str:
    report_text = build_quote_review_report(input_excel)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(report_text, encoding="utf-8")
    return report_text


def build_quote_review_report(input_excel: Path) -> str:
    workbook = load_workbook(input_excel, data_only=False)
    sheet = workbook.active
    headers = _header_columns(sheet)
    rows = _review_rows(sheet, headers)
    lines = ["# 报价复核报告", ""]
    lines.extend(_status_summary(rows))
    lines.append("")
    lines.extend(_source_summary(rows))
    for status in _REVIEW_STATUSES:
        status_rows = [row for row in rows if row.review_status == status]
        if not status_rows:
            continue
        lines.append("")
        lines.append(f"## {status}")
        lines.append("")
        lines.append("| Excel行 | 编号 | 项目名称 | 数量 | 计量口径 | 复核状态 | 复核备注 |")
        lines.append("| ---: | --- | --- | ---: | --- | --- | --- |")
        for row in status_rows:
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row.excel_row),
                        str(row.number),
                        _markdown_cell(row.item_name),
                        _markdown_cell(_format_quantity(row.quantity)),
                        _markdown_cell(row.basis),
                        _markdown_cell(row.review_status),
                        _markdown_cell(row.review_note),
                    ]
                )
                + " |"
            )
    lines.append("")
    return "\n".join(lines)


def _header_columns(sheet) -> dict[str, int]:
    headers: dict[str, int] = {}
    for column in range(1, sheet.max_column + 1):
        value = sheet.cell(row=_HEADER_ROW, column=column).value
        if isinstance(value, str) and value:
            headers[value] = column
    required = ["项目名称", "数量", "数量来源", "计量口径", "复核状态", "复核备注"]
    missing = [header for header in required if header not in headers]
    if missing:
        raise ValueError(f"Quote workbook is missing review column(s): {', '.join(missing)}")
    return headers


def _review_rows(sheet, headers: dict[str, int]) -> list[QuoteReviewRow]:
    rows: list[QuoteReviewRow] = []
    for row_index in range(_FIRST_DATA_ROW, sheet.max_row + 1):
        number = sheet.cell(row=row_index, column=1).value
        item_name = _text(sheet.cell(row=row_index, column=headers["项目名称"]).value)
        review_status = _text(sheet.cell(row=row_index, column=headers["复核状态"]).value)
        if not isinstance(number, int) or item_name is None or review_status in {None, "自动生成"}:
            continue
        rows.append(
            QuoteReviewRow(
                excel_row=row_index,
                number=number,
                item_name=item_name,
                quantity=sheet.cell(row=row_index, column=headers["数量"]).value,
                quantity_source=_text(sheet.cell(row=row_index, column=headers["数量来源"]).value),
                source_room=_text(sheet.cell(row=row_index, column=headers.get("来源空间", 0)).value)
                if "来源空间" in headers
                else None,
                basis=_text(sheet.cell(row=row_index, column=headers["计量口径"]).value),
                review_status=review_status,
                review_note=_text(sheet.cell(row=row_index, column=headers["复核备注"]).value),
            )
        )
    return rows


def _status_summary(rows: list[QuoteReviewRow]) -> list[str]:
    lines = ["## 复核状态统计", ""]
    for status in _REVIEW_STATUSES:
        count = sum(1 for row in rows if row.review_status == status)
        lines.append(f"- {status}：{count} 行")
    return lines


def _source_summary(rows: list[QuoteReviewRow]) -> list[str]:
    counts: dict[str, int] = {}
    for row in rows:
        source = row.quantity_source or "未标注"
        counts[source] = counts.get(source, 0) + 1
    lines = ["## 数量来源统计", ""]
    if not counts:
        lines.append("- 无需要复核的报价行")
        return lines
    for source in sorted(counts):
        lines.append(f"- {source}：{counts[source]} 行")
    return lines


def _format_quantity(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", "<br>")

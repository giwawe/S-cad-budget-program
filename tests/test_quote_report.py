from pathlib import Path

from openpyxl import Workbook

from cad_budget.quote_report import generate_quote_review_report


def test_generate_quote_review_report_groups_review_rows(tmp_path: Path):
    quote_path = tmp_path / "quote.xlsx"
    report_path = tmp_path / "report.md"
    _write_quote_workbook(quote_path)

    report_text = generate_quote_review_report(quote_path, report_path)

    assert report_path.read_text(encoding="utf-8") == report_text
    assert "# 报价复核报告" in report_text
    assert "- 自动生成-默认推断：3 行" in report_text
    assert "- 自动生成-异常提示：1 行" in report_text
    assert "- 按模板生成：1 行" in report_text
    assert "## 复核行动建议" in report_text
    assert "- 补窗高：影响 2 个报价行，涉及项目：卧室墙面项目、墙面乳胶漆；Excel 行 5、6" in report_text
    assert "- 补新砌墙高度/厚度：影响 1 个报价行，涉及项目：砌240厚砖墙；Excel 行 7" in report_text
    assert "- 复核外墙修补范围：影响 1 个报价行，涉及项目：外墙修补；Excel 行 8" in report_text
    assert "| 5 | 101 | 卧室墙面项目 | 31.5 | 墙面净面积 | 自动生成-默认推断 | 窗高缺失 1 个 |" in report_text
    assert "| 6 | 102 | 墙面乳胶漆 | 31.5 | 墙面净面积 | 自动生成-默认推断 | 窗高缺失 1 个 |" in report_text
    assert "| 7 | 103 | 砌240厚砖墙 | 6 | 新砌240mm砖墙面积汇总 | 自动生成-默认推断 | 墙体标识缺少高度 |" in report_text
    assert "| 8 | 104 | 外墙修补 | 0 | 外墙修补范围面积汇总 | 自动生成-异常提示 | 需要确认修补范围 |" in report_text
    assert "| 9 | 105 | 主材包 | 1 |  | 按模板生成 |  |" in report_text
    assert "普通自动行" not in report_text


def _write_quote_workbook(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "商品房整装报价"
    headers = [
        "编号",
        "项目名称",
        "单位",
        "数量",
        "主材单价",
        "辅材单价",
        "人工单价",
        "合价",
        "工艺说明",
        "数量来源",
        "来源空间",
        "空间ID",
        "计量口径",
        "复核状态",
        "复核备注",
    ]
    for column, header in enumerate(headers, start=1):
        sheet.cell(row=3, column=column).value = header
    rows = [
        [1, "普通自动行", "m2", 10, None, None, None, None, None, "自动算量", "客厅", "living", "地面面积", "自动生成", None],
        [101, "卧室墙面项目", "m2", 31.5, None, None, None, None, None, "自动算量", "卧室", "bed", "墙面净面积", "自动生成-默认推断", "窗高缺失 1 个"],
        [102, "墙面乳胶漆", "m2", 31.5, None, None, None, None, None, "自动算量", "卧室", "bed", "墙面净面积", "自动生成-默认推断", "窗高缺失 1 个"],
        [103, "砌240厚砖墙", "m2", 6, None, None, None, None, None, "自动汇总", "全屋", None, "新砌240mm砖墙面积汇总", "自动生成-默认推断", "墙体标识缺少高度"],
        [104, "外墙修补", "m2", 0, None, None, None, None, None, "自动汇总", "全屋", None, "外墙修补范围面积汇总", "自动生成-异常提示", "需要确认修补范围"],
        [105, "主材包", "项", 1, None, None, None, None, None, "模板默认", None, None, None, "按模板生成", None],
    ]
    for row_index, values in enumerate(rows, start=4):
        for column, value in enumerate(values, start=1):
            sheet.cell(row=row_index, column=column).value = value
    workbook.save(path)

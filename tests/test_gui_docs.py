from __future__ import annotations

from pathlib import Path


def test_gui_user_guide_documents_v1_workflow() -> None:
    guide = Path("docs/gui-v1-user-guide-zh.md")

    text = guide.read_text(encoding="utf-8")

    assert "pip install -e \".[gui]\"" in text
    assert "cad-budget-gui" in text
    assert "运行真实验收" in text
    assert "打开输出目录" in text
    assert "双击" in text
    assert "生成正式报价" in text

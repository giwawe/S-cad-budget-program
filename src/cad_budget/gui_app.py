from __future__ import annotations

import sys


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ModuleNotFoundError as exc:
        raise SystemExit("PySide6 is required for the GUI. Install it with: pip install -e \".[gui]\"") from exc

    from cad_budget.gui_main_window import CadBudgetMainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    window = CadBudgetMainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

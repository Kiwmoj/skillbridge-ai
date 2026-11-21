"""Start the SkillBridge AI native desktop application."""
import logging
import sys
from PyQt6.QtWidgets import QApplication, QMessageBox

from ui.main_window import MainWindow


def main() -> int:
    logging.basicConfig(filename="skillbridge.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    app = QApplication(sys.argv)
    app.setApplicationName("SkillBridge AI")
    app.setOrganizationName("SkillBridge")
    app.setStyle("Fusion")
    try:
        window = MainWindow()
    except Exception as exc:
        logging.exception("Application startup failed")
        QMessageBox.critical(None, "SkillBridge AI could not start", f"{exc}\n\nSee skillbridge.log for details.")
        return 1
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

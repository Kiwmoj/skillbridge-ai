from PyQt6.QtWidgets import QProgressBar


class SkillProgress(QProgressBar):
    def __init__(self, value: int = 0, parent=None):
        super().__init__(parent)
        self.setRange(0, 100)
        self.setValue(value)
        self.setTextVisible(False)
        self.setFixedHeight(8)
        self.setObjectName("skillProgress")


def roadmap_progress(value: int) -> QProgressBar:
    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setValue(max(0, min(100, value)))
    bar.setFormat(f"{value}%")
    bar.setFixedHeight(18)
    return bar

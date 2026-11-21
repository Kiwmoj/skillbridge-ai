from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget


def nav_icon(kind: str) -> QIcon:
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#78b8ff"), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if kind == "overview":
        painter.drawRoundedRect(3, 3, 8, 8, 2, 2); painter.drawRoundedRect(13, 3, 8, 8, 2, 2)
        painter.drawRoundedRect(3, 13, 8, 8, 2, 2); painter.drawRoundedRect(13, 13, 8, 8, 2, 2)
    elif kind == "career":
        painter.drawEllipse(4, 4, 16, 16); painter.drawEllipse(9, 9, 6, 6); painter.drawLine(14, 10, 21, 3)
    elif kind == "skills":
        painter.drawLine(4, 20, 4, 4); painter.drawLine(4, 20, 21, 20)
        painter.drawRoundedRect(7, 12, 3, 8, 1, 1); painter.drawRoundedRect(12, 8, 3, 12, 1, 1); painter.drawRoundedRect(17, 4, 3, 16, 1, 1)
    elif kind == "portfolio":
        painter.drawRoundedRect(3, 4, 18, 16, 2, 2); painter.drawEllipse(7, 8, 3, 3)
        painter.drawLine(5, 18, 11, 12); painter.drawLine(11, 12, 14, 15); painter.drawLine(14, 15, 18, 10); painter.drawLine(18, 10, 20, 13)
    elif kind == "roadmap":
        painter.drawLine(5, 18, 9, 7); painter.drawLine(9, 7, 15, 13); painter.drawLine(15, 13, 20, 4)
        painter.drawEllipse(3, 16, 4, 4); painter.drawEllipse(7, 5, 4, 4); painter.drawEllipse(13, 11, 4, 4); painter.drawEllipse(18, 2, 4, 4)
    elif kind == "projects":
        painter.drawRoundedRect(3, 3, 8, 8, 2, 2); painter.drawRoundedRect(13, 3, 8, 8, 2, 2)
        painter.drawRoundedRect(3, 13, 8, 8, 2, 2); painter.drawRoundedRect(13, 13, 8, 8, 2, 2)
    elif kind == "explorer":
        painter.drawEllipse(3, 3, 13, 13); painter.drawLine(13, 13, 21, 21)
    elif kind == "analytics":
        painter.drawLine(3, 20, 3, 4); painter.drawLine(3, 20, 21, 20)
        painter.drawLine(6, 16, 10, 12); painter.drawLine(10, 12, 14, 15); painter.drawLine(14, 15, 20, 7)
    else:
        painter.drawEllipse(8, 3, 8, 8); painter.drawArc(3, 12, 18, 12, 0, 180*16)
    painter.end()
    return QIcon(pixmap)


class Sidebar(QFrame):
    navigate = pyqtSignal(str)

    ITEMS = [
        ("Overview", "overview"),
        ("Career reality check", "career"),
        ("Skill gap", "skills"),
        ("Portfolio review", "portfolio"),
        ("Learning roadmap", "roadmap"),
        ("Project studio", "projects"),
        ("Career explorer", "explorer"),
        ("Opportunities & Colleges", "career"),
        ("Progress analytics", "analytics"),
        ("My profile", "profile"),
        ("Service & account", "profile"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(238)
        box = QVBoxLayout(self)
        box.setContentsMargins(16, 20, 16, 18)
        box.setSpacing(6)
        brand = QWidget()
        brand_box = QVBoxLayout(brand)
        brand_box.setContentsMargins(6, 2, 6, 18)
        brand_box.setSpacing(2)
        logo = QLabel("SB")
        logo.setObjectName("brandMark")
        logo.setFixedSize(40, 40)
        name = QLabel("SkillBridge AI")
        name.setObjectName("brandName")
        line = QLabel("CAREER DEVELOPMENT STUDIO")
        line.setObjectName("eyebrow")
        brand_box.addWidget(logo)
        brand_box.addSpacing(9)
        brand_box.addWidget(name)
        brand_box.addWidget(line)
        box.addWidget(brand)
        self.buttons = {}
        for label, icon in self.ITEMS:
            key = label
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setIcon(nav_icon(icon))
            button.setIconSize(QSize(18, 18))
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, item=key: self.navigate.emit(item))
            box.addWidget(button)
            self.buttons[label] = button
        box.addStretch(1)
        self.set_active("Overview")

    def set_active(self, label: str):
        for name, button in self.buttons.items():
            button.setChecked(name == label)

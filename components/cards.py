from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class Card(QFrame):
    def __init__(self, parent=None, accent=False):
        super().__init__(parent)
        self.setObjectName("accentCard" if accent else "card")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.layout_box = QVBoxLayout(self)
        self.layout_box.setContentsMargins(20, 18, 20, 18)
        self.layout_box.setSpacing(10)


def heading(text: str, level: str = "body") -> QLabel:
    label = QLabel(text)
    label.setObjectName({"title":"pageTitle", "heading":"cardTitle", "muted":"muted", "eyebrow":"eyebrow"}.get(level,"body"))
    label.setWordWrap(True)
    return label


def badge(text: str, tone: str = "blue") -> QLabel:
    label = QLabel(text)
    label.setObjectName(f"badge_{tone}")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setContentsMargins(9, 4, 9, 4)
    return label


def add_title(card: Card, title: str, subtitle: str = "") -> None:
    card.layout_box.addWidget(heading(title, "heading"))
    if subtitle:
        card.layout_box.addWidget(heading(subtitle, "muted"))


def wrap_widget(widget: QWidget) -> Card:
    card = Card()
    card.layout_box.addWidget(widget)
    return card

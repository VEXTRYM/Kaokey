from PySide6.QtCore import (
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QMouseEvent,
)
from PySide6.QtWidgets import (
    QPushButton,
)


class KaomojiButton(QPushButton):
    right_clicked = Signal()

    def mousePressEvent(
        self,
        event: QMouseEvent,
    ) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseReleaseEvent(
        self,
        event: QMouseEvent,
    ) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            event.accept()

            self.right_clicked.emit()

            return

        super().mouseReleaseEvent(event)

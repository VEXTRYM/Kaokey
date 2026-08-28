from PySide6.QtCore import (
    QEvent,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QFont,
    QMouseEvent,
)
from PySide6.QtWidgets import (
    QPushButton,
    QToolTip,
    QWidget,
)

from unicode_fonts import font_for_text


class KaomojiButton(QPushButton):
    right_clicked = Signal()

    def __init__(
        self,
        text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            text,
            parent,
        )

        # QToolTip has one application-wide font. Store the ordinary tooltip
        # font before any hover changes it, then derive the right exact font
        # from this stable base for every kaomoji tooltip.
        self._tooltip_base_font = QFont(
            QToolTip.font()
        )

    def event(
        self,
        event: QEvent,
    ) -> bool:
        if (
            event.type()
            == QEvent.Type.ToolTip
            and self.toolTip()
        ):
            QToolTip.setFont(
                font_for_text(
                    self._tooltip_base_font,
                    self.toolTip(),
                )
            )

        return super().event(
            event
        )

    def mousePressEvent(
        self,
        event: QMouseEvent,
    ) -> None:
        if (
            event.button()
            == Qt.MouseButton.RightButton
        ):
            self.right_clicked.emit()
            return

        super().mousePressEvent(
            event
        )

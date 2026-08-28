from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QStatusBar,
    QWidget,
)

from unicode_fonts import font_for_text


class UnicodeStatusBar(QStatusBar):
    """QStatusBar that chooses a font capable of rendering each message."""

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        # Keep the normal UI font as the reference. Otherwise, after one
        # Canadian-Syllabics message, the next ordinary message could inherit
        # Gadugi simply because it happened to be the last selected font.
        self._base_font = QFont(
            self.font()
        )

    def showMessage(
        self,
        message: str,
        timeout: int = 0,
    ) -> None:
        self.setFont(
            font_for_text(
                self._base_font,
                message,
            )
        )

        super().showMessage(
            message,
            timeout,
        )

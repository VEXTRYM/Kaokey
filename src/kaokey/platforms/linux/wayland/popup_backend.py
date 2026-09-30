from PySide6.QtCore import QObject
from PySide6.QtGui import QGuiApplication

from kaokey.platforms.popup_backend import UnavailablePopupBackend


class WaylandPopupBackend(UnavailablePopupBackend):
    """Wayland backend placeholder.

    GlobalShortcuts portal and Linux AT-SPI integration are added separately.
    """

    def __init__(
        self,
        app: QGuiApplication,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self.app = app

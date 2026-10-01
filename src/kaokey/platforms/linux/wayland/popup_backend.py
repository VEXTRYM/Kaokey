from PySide6.QtCore import QObject
from PySide6.QtGui import QGuiApplication

from kaokey.platforms.linux.common_popup_backend import (
    LinuxPopupBackendBase,
)


class WaylandPopupBackend(LinuxPopupBackendBase):
    """Wayland popup backend with shared Linux accessibility services.

    GlobalShortcuts portal integration is added separately.
    """

    def __init__(
        self,
        app: QGuiApplication,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(
            app,
            parent,
        )

from PySide6.QtCore import QObject
from PySide6.QtGui import QGuiApplication

from kaokey.platforms.linux.common_popup_backend import (
    LinuxPopupBackendBase,
)


class X11PopupBackend(LinuxPopupBackendBase):
    """X11 popup backend with shared Linux accessibility services.

    Native X11 global hotkeys are added separately.
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

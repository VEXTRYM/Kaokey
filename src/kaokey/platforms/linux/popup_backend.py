import logging

from PySide6.QtCore import QObject
from PySide6.QtGui import QGuiApplication

from kaokey.platforms.linux.session import (
    display_backend_from_qt_platform,
)
from kaokey.platforms.popup_backend import (
    PopupBackend,
    UnavailablePopupBackend,
)

_LOG = logging.getLogger(__name__)


def create_linux_popup_backend(
    app: QGuiApplication,
    parent: QObject | None = None,
) -> PopupBackend:
    """Create a backend for the display server Qt is actually using."""
    display_backend = display_backend_from_qt_platform(
        app.platformName()
    )

    if display_backend == "x11":
        from kaokey.platforms.linux.x11.popup_backend import (
            X11PopupBackend,
        )

        return X11PopupBackend(
            app,
            parent,
        )

    if display_backend == "wayland":
        try:
            from kaokey.platforms.linux.wayland.popup_backend import (
                WaylandPopupBackend,
            )
        except ModuleNotFoundError as error:
            if (error.name or "").partition(".")[0] != "dbus_next":
                raise
            _LOG.warning(
                "Wayland global shortcuts require dbus-next. The main window remains available."
            )
            return UnavailablePopupBackend(parent)

        return WaylandPopupBackend(
            app,
            parent,
        )

    return UnavailablePopupBackend(parent)

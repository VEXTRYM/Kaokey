from collections.abc import (
    Callable,
    Sequence,
)

from PySide6.QtCore import (
    QObject,
    QPoint,
)
from PySide6.QtGui import (
    QGuiApplication,
    QScreen,
)

from kaokey.platforms.linux.accessibility import (
    LinuxAccessibility,
    LinuxAccessibleTarget,
)
from kaokey.platforms.popup_backend import (
    PopupCapabilities,
    PopupContext,
    PopupInsertionResult,
    UnavailablePopupBackend,
)
from kaokey.ui.popup.popup_positioning import Rect


class LinuxPopupBackendBase(UnavailablePopupBackend):
    """Popup services shared by X11 and Wayland backends."""

    def __init__(
        self,
        app: QGuiApplication,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self.app = app
        self.accessibility = LinuxAccessibility()

    @property
    def capabilities(
        self,
    ) -> PopupCapabilities:
        accessibility_available = self.accessibility.available

        return PopupCapabilities(
            hotkey=False,
            target_capture=accessibility_available,
            caret_positioning=accessibility_available,
            text_insertion=accessibility_available,
        )

    def capture_context(
        self,
        screens: Sequence[QScreen],
    ) -> PopupContext:
        target = self.accessibility.capture_target()

        if target is None:
            return PopupContext(target=None)

        caret_rect = self.accessibility.caret_rect(
            target
        )

        return PopupContext(
            target=target,
            caret_rect=caret_rect,
            fallback_screen=_screen_for_rect(
                caret_rect,
                screens,
            ),
        )

    def insert_text(
        self,
        target: object,
        text: str,
        *,
        before_focus_transfer: Callable[[], None],
    ) -> PopupInsertionResult:
        del before_focus_transfer

        if not isinstance(
            target,
            LinuxAccessibleTarget,
        ):
            return PopupInsertionResult(
                inserted=False
            )

        return PopupInsertionResult(
            inserted=self.accessibility.insert_text(
                target,
                text,
            ),
            focus_transferred=False,
        )


def _screen_for_rect(
    rect: Rect | None,
    screens: Sequence[QScreen],
) -> QScreen | None:
    if rect is None:
        return None

    point = QPoint(
        rect.x,
        rect.y,
    )

    for screen in screens:
        if screen.geometry().contains(point):
            return screen

    return None

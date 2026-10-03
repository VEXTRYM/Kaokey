import threading

from collections.abc import (
    Callable,
    Sequence,
)

from PySide6.QtCore import (
    QObject,
    QPoint,
    Signal,
    Slot,
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
    PopupContextCallback,
    PopupInsertionResult,
    UnavailablePopupBackend,
)
from kaokey.ui.popup.popup_positioning import Rect


class LinuxPopupBackendBase(UnavailablePopupBackend):
    """Popup services shared by X11 and Wayland backends."""

    _context_captured = Signal(int, object, object)

    def __init__(
        self,
        app: QGuiApplication,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self.app = app
        self.accessibility = LinuxAccessibility()
        self._accessibility_available = self.accessibility.available
        self._context_capture_serial = 0
        self._context_capture_in_progress = False
        self._context_capture_request: tuple[
            int,
            tuple[QScreen, ...],
            PopupContextCallback,
        ] | None = None
        self._context_captured.connect(self._finish_context_capture)

    @property
    def capabilities(
        self,
    ) -> PopupCapabilities:
        accessibility_available = self._accessibility_available

        return PopupCapabilities(
            hotkey=False,
            target_capture=accessibility_available,
            caret_positioning=accessibility_available,
            window_positioning=True,
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

    def capture_context_async(
        self,
        screens: Sequence[QScreen],
        callback: PopupContextCallback,
    ) -> None:
        # A single hung AT-SPI provider must not create an unbounded number of
        # blocked worker threads if the user presses the hotkey repeatedly.
        if self._context_capture_in_progress:
            callback(PopupContext(target=None))
            return

        self._context_capture_serial += 1
        serial = self._context_capture_serial

        self._context_capture_in_progress = True
        self._context_capture_request = (
            serial,
            tuple(screens),
            callback,
        )

        threading.Thread(
            target=self._capture_context_worker,
            args=(serial,),
            name=f"kaokey-atspi-capture-{serial}",
            daemon=True,
        ).start()

    def _capture_context_worker(
        self,
        serial: int,
    ) -> None:
        accessibility = LinuxAccessibility()
        target: LinuxAccessibleTarget | None = None
        caret_rect: Rect | None = None

        try:
            target = accessibility.capture_target()

            if target is not None:
                caret_rect = accessibility.caret_rect(target)
        except Exception:
            # The UI has a bounded timeout and a clipboard fallback. Treat a
            # broken accessibility provider the same as unavailable AT-SPI.
            target = None
            caret_rect = None
        finally:
            accessibility.close()

        self._context_captured.emit(
            serial,
            target,
            caret_rect,
        )

    @Slot(int, object, object)
    def _finish_context_capture(
        self,
        serial: int,
        target: LinuxAccessibleTarget | None,
        caret_rect: Rect | None,
    ) -> None:
        request = self._context_capture_request

        if request is None or request[0] != serial:
            return

        _, screens, callback = request
        self._context_capture_request = None
        self._context_capture_in_progress = False

        callback(
            PopupContext(
                target=target,
                caret_rect=caret_rect,
                fallback_screen=_screen_for_rect(
                    caret_rect,
                    screens,
                ),
            )
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

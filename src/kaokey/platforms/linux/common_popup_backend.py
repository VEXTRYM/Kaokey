import logging
import threading
import time
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

from kaokey.platforms.linux.native_accessibility import (
    LinuxAccessibility,
    LinuxAccessibleTarget,
)
from kaokey.platforms.linux.dbus import ensure_accessibility_enabled
from kaokey.platforms.popup_backend import (
    PopupCapabilities,
    PopupContext,
    PopupContextCallback,
    PopupInsertionResult,
    UnavailablePopupBackend,
)
from kaokey.geometry import Rect

_LOG = logging.getLogger(__name__)


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
        self._accessibility_requested = False
        self._context_capture_serial = 0
        self._context_capture_in_progress = False
        self._context_capture_request: tuple[
            int,
            tuple[QScreen, ...],
            PopupContextCallback,
        ] | None = None
        self._context_captured.connect(self._finish_context_capture)

    def prepare_accessibility(self) -> bool:
        """Activate toolkit accessibility when the user enables the picker."""
        if self._accessibility_requested:
            return True
        if not self._accessibility_available:
            return False
        self._accessibility_requested = ensure_accessibility_enabled()
        _LOG.debug("Toolkit accessibility enabled: %s", self._accessibility_requested)
        return self._accessibility_requested

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
        *,
        process_id: int | None = None,
    ) -> PopupContext:
        target = self.accessibility.capture_target(process_id=process_id)

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
        *,
        process_id: int | None = None,
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
            args=(serial, process_id),
            name=f"kaokey-atspi-capture-{serial}",
            daemon=True,
        ).start()

    def _capture_context_worker(
        self,
        serial: int,
        process_id: int | None = None,
    ) -> None:
        accessibility = LinuxAccessibility()
        target: LinuxAccessibleTarget | None = None
        caret_rect: Rect | None = None
        started = time.monotonic()

        try:
            target = accessibility.capture_target(process_id=process_id)

            if target is not None:
                caret_rect = accessibility.caret_rect(target)
        except Exception:  # noqa: BLE001 - external provider may fail unpredictably
            _LOG.debug("Caret capture failed", exc_info=True)
            # The UI has a bounded timeout and a clipboard fallback. Treat a
            # broken accessibility provider the same as unavailable AT-SPI.
            target = None
            caret_rect = None
        finally:
            accessibility.close()
            _LOG.debug("Caret capture took %.0f ms; rect=%s", (time.monotonic() - started) * 1000, caret_rect)

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

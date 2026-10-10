import threading
from collections.abc import Sequence

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

from kaokey.platforms.linux.x11.hotkey import (
    X11GlobalHotkey,
    X11HotkeyError,
    x11_hotkeys_available,
)
from kaokey.platforms.popup_backend import (
    PopupCapabilities,
    PopupContext,
    PopupContextCallback,
    PopupHotkey,
    PopupHotkeyActivation,
    PopupHotkeyActivationCallback,
    PopupHotkeyRegistrationCallback,
    PopupHotkeyRegistrationError,
    PopupHotkeyRegistrationErrorCallback,
    UnavailablePopupBackend,
)
from kaokey.ui.popup.popup_positioning import Rect


class X11PopupBackend(UnavailablePopupBackend):
    """X11 popup hotkey and optional asynchronous AT-SPI caret positioning.

    Capturing the caret must never block the GUI or enable text insertion.
    The coordinator has a timeout and opens at the saved/centered position
    when AT-SPI is unavailable or unresponsive.
    """

    _caret_captured = Signal(int, object)

    def __init__(
        self,
        app: QGuiApplication,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        del app

        self._hotkey_available = x11_hotkeys_available()
        self._hotkey: X11GlobalHotkey | None = None
        self._caret_serial = 0
        self._caret_in_progress = False
        self._caret_request: tuple[
            int,
            tuple[QScreen, ...],
            PopupContextCallback,
        ] | None = None
        self._caret_captured.connect(self._finish_caret_capture)

    @property
    def capabilities(
        self,
    ) -> PopupCapabilities:
        return PopupCapabilities(
            hotkey=self._hotkey_available,
            caret_positioning=True,
            window_positioning=True,
            # Text selection still copies to the clipboard; native insertion
            # remains disabled until it is explicitly implemented and tested.
            text_insertion=False,
        )

    def capture_context_async(
        self,
        screens: Sequence[QScreen],
        callback: PopupContextCallback,
    ) -> None:
        # A blocked AT-SPI provider must not spawn an unlimited number of
        # worker threads. Further activations use the normal popup fallback.
        if self._caret_in_progress:
            callback(PopupContext(target=None))
            return

        self._caret_serial += 1
        serial = self._caret_serial
        self._caret_request = (serial, tuple(screens), callback)
        self._caret_in_progress = True

        try:
            threading.Thread(
                target=self._capture_caret_worker,
                args=(serial,),
                name=f"kaokey-x11-caret-{serial}",
                daemon=True,
            ).start()
        except RuntimeError:
            self._caret_request = None
            self._caret_in_progress = False
            callback(PopupContext(target=None))

    def _capture_caret_worker(
        self,
        serial: int,
    ) -> None:
        # Initialize libatspi in the worker as well: even the first AT-SPI
        # connection can block when the desktop accessibility bus is starting.
        caret_rect: Rect | None = None

        try:
            from kaokey.platforms.linux.native_accessibility import (
                LinuxAccessibility,
            )

            accessibility = LinuxAccessibility()

            try:
                target = accessibility.capture_target()

                if target is not None:
                    try:
                        caret_rect = accessibility.caret_rect(target)
                    finally:
                        target.close()
            finally:
                accessibility.close()
        except Exception:
            # An inaccessible app or unavailable AT-SPI bus must not prevent
            # opening the popup or affect the hotkey registration.
            pass

        try:
            self._caret_captured.emit(serial, caret_rect)
        except RuntimeError:
            # The QObject might have been deleted during application shutdown.
            pass

    @Slot(int, object)
    def _finish_caret_capture(
        self,
        serial: int,
        caret_rect: Rect | None,
    ) -> None:
        request = self._caret_request

        if request is None or request[0] != serial:
            return

        _, screens, callback = request
        self._caret_request = None
        self._caret_in_progress = False

        screen = None

        if caret_rect is not None:
            point = QPoint(
                caret_rect.x + caret_rect.width // 2,
                caret_rect.y + caret_rect.height // 2,
            )
            screen = next(
                (item for item in screens if item.geometry().contains(point)),
                None,
            )

            # Some providers return coordinates outside every active screen.
            # Use the saved/centered popup position rather than a screen edge.
            if screen is None:
                caret_rect = None

        callback(
            PopupContext(
                target=None,
                caret_rect=caret_rect,
                fallback_screen=screen,
            )
        )

    @property
    def active_hotkey(
        self,
    ) -> PopupHotkey | None:
        hotkey = self._hotkey

        if hotkey is None:
            return None

        return PopupHotkey(
            modifier=hotkey.modifier,
            key=hotkey.key,
            label=hotkey.label,
        )

    def set_hotkey(
        self,
        modifier: str,
        key: str,
        callback: PopupHotkeyActivationCallback,
        on_registered: PopupHotkeyRegistrationCallback,
        on_error: PopupHotkeyRegistrationErrorCallback,
    ) -> None:
        previous_hotkey = self._hotkey

        if previous_hotkey is not None and (
            previous_hotkey.modifier,
            previous_hotkey.key,
        ) == (
            modifier,
            key,
        ):
            on_registered(
                PopupHotkey(
                    modifier=previous_hotkey.modifier,
                    key=previous_hotkey.key,
                    label=previous_hotkey.label,
                )
            )
            return

        try:
            candidate = X11GlobalHotkey(
                modifier,
                key,
                lambda timestamp: callback(
                    PopupHotkeyActivation(
                        x11_timestamp=timestamp,
                    )
                ),
                self,
            )
        except X11HotkeyError as error:
            on_error(
                PopupHotkeyRegistrationError(
                    str(error),
                    previous_hotkey_restored=previous_hotkey is not None,
                )
            )
            return

        if previous_hotkey is not None:
            previous_hotkey.unregister()

        try:
            candidate.register()
        except X11HotkeyError as error:
            candidate.close()
            candidate.deleteLater()

            restored = False

            if previous_hotkey is not None:
                try:
                    previous_hotkey.register()
                    restored = True
                except X11HotkeyError:
                    previous_hotkey.close()
                    previous_hotkey.deleteLater()
                    self._hotkey = None

            on_error(
                PopupHotkeyRegistrationError(
                    str(error),
                    previous_hotkey_restored=restored,
                )
            )
            return

        self._hotkey = candidate

        if previous_hotkey is not None:
            previous_hotkey.close()
            previous_hotkey.deleteLater()

        on_registered(
            PopupHotkey(
                modifier=candidate.modifier,
                key=candidate.key,
                label=candidate.label,
            )
        )

    def clear_hotkey(
        self,
    ) -> None:
        hotkey = self._hotkey

        if hotkey is None:
            return

        hotkey.close()
        hotkey.deleteLater()
        self._hotkey = None

    def hotkey_keys_released(
        self,
    ) -> bool:
        hotkey = self._hotkey

        if hotkey is None:
            return True

        return hotkey.keys_released()

    def request_popup_activation(
        self,
        window_id: int,
        activation: PopupHotkeyActivation,
    ) -> bool:
        hotkey = self._hotkey
        timestamp = activation.x11_timestamp

        if (
            hotkey is None
            or timestamp is None
            or timestamp <= 0
        ):
            return False

        try:
            hotkey.request_window_activation(
                window_id,
                timestamp,
            )
        except OSError:
            return False

        return True

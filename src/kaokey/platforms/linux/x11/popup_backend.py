import logging
from collections.abc import Callable, Sequence

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QGuiApplication, QScreen

from kaokey.config.popup_constants import POPUP_CONTEXT_CAPTURE_TIMEOUT_MS
from kaokey.platforms.linux.common_popup_backend import (
    LinuxPopupBackendBase,
)
from kaokey.platforms.linux.native_accessibility import LinuxAccessibleTarget
from kaokey.platforms.linux.x11.coordinates import native_rect_to_qt
from kaokey.platforms.linux.x11.desktop import X11Desktop, X11Target
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
    PopupInsertionResult,
)
from kaokey.ui.popup.popup_positioning import Rect

_LOG = logging.getLogger(__name__)


class X11PopupBackend(LinuxPopupBackendBase):
    """X11 hotkeys, caret positioning, and foreground-window paste."""

    def __init__(
        self,
        app: QGuiApplication,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(
            app,
            parent,
        )

        self._hotkey_available = x11_hotkeys_available()
        self._hotkey: X11GlobalHotkey | None = None
        try:
            self._desktop: X11Desktop | None = X11Desktop()
        except OSError:
            self._desktop = None

    @property
    def capabilities(
        self,
    ) -> PopupCapabilities:
        common = super().capabilities

        return PopupCapabilities(
            hotkey=self._hotkey_available,
            target_capture=self._desktop is not None or common.target_capture,
            caret_positioning=self._desktop is not None or common.caret_positioning,
            window_positioning=common.window_positioning,
            text_insertion=(
                self._desktop is not None and self._desktop.xtest is not None
            ) or common.text_insertion,
        )

    def _native_context(self) -> tuple[int | None, Rect | None, int | None]:
        if self._desktop is None:
            return None, None, None
        try:
            window = self._desktop.active_window()
            process_id = self._desktop.window_process_id(window) if window else None
            return window, self._desktop.pointer_rect(), process_id
        except OSError:
            return None, None, None

    def _merge_context(
        self,
        context: PopupContext,
        window: int | None,
        pointer: Rect | None,
        screens: Sequence[QScreen],
    ) -> PopupContext:
        rect = context.caret_rect or pointer
        screen = context.fallback_screen
        if rect is not None:
            rect, screen = native_rect_to_qt(rect, screens)
        _LOG.debug(
            "Popup anchor source=%s native caret=%s Qt anchor=%s",
            "caret" if context.caret_rect is not None else "pointer fallback",
            context.caret_rect,
            rect,
        )
        target = context.target
        if window is not None:
            target = X11Target(
                window,
                target if isinstance(target, LinuxAccessibleTarget) else None,
            )
        return PopupContext(target=target, caret_rect=rect, fallback_screen=screen)

    def capture_context(
        self,
        screens: Sequence[QScreen],
        *,
        process_id: int | None = None,
    ) -> PopupContext:
        window, pointer, native_process_id = self._native_context()
        context = super().capture_context(screens, process_id=native_process_id or process_id)
        return self._merge_context(context, window, pointer, screens)

    def capture_context_async(
        self,
        screens: Sequence[QScreen],
        callback: PopupContextCallback,
        *,
        process_id: int | None = None,
    ) -> None:
        # Capture the native target BEFORE a worker or the popup can change
        # focus. Even a hung AT-SPI provider must leave insertion usable.
        window, pointer, native_process_id = self._native_context()
        completed = False

        def finish(context: PopupContext) -> None:
            nonlocal completed
            if completed:
                return
            completed = True
            callback(self._merge_context(context, window, pointer, screens))

        QTimer.singleShot(
            max(0, POPUP_CONTEXT_CAPTURE_TIMEOUT_MS - 100),
            lambda: finish(PopupContext(target=None)),
        )
        super().capture_context_async(screens, finish, process_id=native_process_id or process_id)

    def insert_text(
        self,
        target: object,
        text: str,
        *,
        before_focus_transfer: Callable[[], None],
    ) -> PopupInsertionResult:
        if isinstance(target, X11Target):
            desktop = self._desktop
            if desktop is not None and desktop.xtest is not None:
                inserted = desktop.paste_text(target.window_id, text, before_focus_transfer)
                return PopupInsertionResult(inserted=inserted, focus_transferred=inserted)
            target = target.accessible
        return super().insert_text(target, text, before_focus_transfer=before_focus_transfer)

    def target_still_active(self, target: object) -> bool:
        if isinstance(target, X11Target):
            return self._desktop is not None and self._desktop.target_still_active(target.window_id)
        return super().target_still_active(target)

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

            restored = False

            if previous_hotkey is not None:
                try:
                    previous_hotkey.register()
                    restored = True
                except X11HotkeyError:
                    previous_hotkey.close()
                    self._hotkey = None

            on_error(
                PopupHotkeyRegistrationError(
                    str(error),
                    previous_hotkey_restored=restored,
                )
            )
            return

        self._hotkey = candidate
        self.prepare_accessibility()

        if previous_hotkey is not None:
            previous_hotkey.close()

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

        if self._desktop is not None:
            self._desktop.close()
            self._desktop = None

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

        try:
            if self._desktop is not None:
                self._desktop.request_window_activation(window_id, timestamp)
            elif hotkey is not None and timestamp is not None and timestamp > 0:
                hotkey.request_window_activation(window_id, timestamp)
            else:
                return False
        except OSError:
            return False

        return True

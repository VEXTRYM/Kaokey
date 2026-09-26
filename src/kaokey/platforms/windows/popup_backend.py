from collections.abc import Callable, Sequence
from dataclasses import dataclass

from PySide6.QtCore import (
    QCoreApplication,
    QObject,
)
from PySide6.QtGui import QScreen

from kaokey.platforms.popup_backend import (
    PopupContext,
    PopupHotkey,
    PopupHotkeyRegistrationError,
    PopupInsertionResult,
)
from kaokey.platforms.windows.coordinates import (
    convert_native_rect,
    screen_for_native_rect,
)
from kaokey.platforms.windows.foreground import (
    capture_foreground_context,
)
from kaokey.platforms.windows.hotkey import (
    HotkeyRegistrationError,
    WindowsGlobalHotkey,
)
from kaokey.platforms.windows.insertion import (
    get_foreground_window_handle,
    global_hotkey_keys_released,
    insert_text_into_native_edit,
    insert_unicode_text,
)


@dataclass(frozen=True)
class WindowsPopupTarget:
    """Native Windows target captured before the popup takes focus."""

    window_handle: int | None
    focus_handle: int | None


class WindowsPopupBackend(QObject):
    """Windows implementation of the services used by PopupCoordinator."""

    def __init__(
        self,
        app: QCoreApplication,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self.app = app
        self._hotkey: WindowsGlobalHotkey | None = None

    @property
    def available(
        self,
    ) -> bool:
        return True

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

    def capture_context(
        self,
        screens: Sequence[QScreen],
    ) -> PopupContext:
        native_context = capture_foreground_context()

        target = WindowsPopupTarget(
            window_handle=native_context.window_handle,
            focus_handle=native_context.focus_window_handle,
        )

        fallback_screen: QScreen | None = None

        if native_context.window_rect is not None:
            fallback_screen = screen_for_native_rect(
                native_context.window_rect,
                screens,
            )

        caret_rect = None

        if native_context.caret_rect is not None:
            converted = convert_native_rect(
                native_context.caret_rect,
                screens,
            )

            if converted is not None:
                caret_rect, caret_screen = converted
                fallback_screen = caret_screen

        return PopupContext(
            target=target,
            caret_rect=caret_rect,
            fallback_screen=fallback_screen,
        )

    def set_hotkey(
        self,
        modifier: str,
        key: str,
        callback: Callable[[], None],
    ) -> PopupHotkey:
        previous_hotkey = self._hotkey

        if previous_hotkey is not None and (
            previous_hotkey.modifier,
            previous_hotkey.key,
        ) == (
            modifier,
            key,
        ):
            return PopupHotkey(
                modifier=previous_hotkey.modifier,
                key=previous_hotkey.key,
                label=previous_hotkey.label,
            )

        if previous_hotkey is not None:
            previous_hotkey.unregister()

        candidate = WindowsGlobalHotkey(
            self.app,
            modifier,
            key,
            self,
        )

        candidate.activated.connect(callback)

        try:
            candidate.register()

        except HotkeyRegistrationError as error:
            candidate.deleteLater()

            restored = False

            if previous_hotkey is not None:
                try:
                    previous_hotkey.register()
                    restored = True
                except HotkeyRegistrationError:
                    self._hotkey = None

            raise PopupHotkeyRegistrationError(
                str(error),
                previous_hotkey_restored=restored,
            ) from error

        self._hotkey = candidate

        if previous_hotkey is not None:
            previous_hotkey.deleteLater()

        return PopupHotkey(
            modifier=candidate.modifier,
            key=candidate.key,
            label=candidate.label,
        )

    def clear_hotkey(
        self,
    ) -> None:
        hotkey = self._hotkey

        if hotkey is None:
            return

        hotkey.unregister()
        hotkey.deleteLater()

        self._hotkey = None

    def hotkey_keys_released(
        self,
    ) -> bool:
        hotkey = self._hotkey

        if hotkey is None:
            return True

        return global_hotkey_keys_released(
            hotkey.release_virtual_keys,
        )

    def insert_text(
        self,
        target: object,
        text: str,
        *,
        before_focus_transfer: Callable[[], None],
    ) -> PopupInsertionResult:
        if not isinstance(
            target,
            WindowsPopupTarget,
        ):
            return PopupInsertionResult(inserted=False)

        direct_inserted = insert_text_into_native_edit(
            target.focus_handle,
            text,
        )

        if direct_inserted:
            return PopupInsertionResult(
                inserted=True,
                focus_transferred=False,
            )

        if target.window_handle is None:
            return PopupInsertionResult(inserted=False)

        before_focus_transfer()

        inserted = insert_unicode_text(
            target.window_handle,
            text,
        )

        return PopupInsertionResult(
            inserted=inserted,
            focus_transferred=inserted,
        )

    def target_still_active(
        self,
        target: object,
    ) -> bool:
        if not isinstance(
            target,
            WindowsPopupTarget,
        ):
            return True

        if target.window_handle is None:
            return True

        foreground_handle = get_foreground_window_handle()

        if foreground_handle is None:
            return True

        return foreground_handle == target.window_handle

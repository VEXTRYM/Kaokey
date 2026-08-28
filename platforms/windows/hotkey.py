import ctypes
import ctypes.wintypes
import sys

from typing import Any

from PySide6.QtCore import (
    QAbstractNativeEventFilter,
    QCoreApplication,
    QObject,
    Signal,
)

from platforms.windows.constants import (
    GLOBAL_HOTKEY_ID,
    WM_HOTKEY,
)
from platforms.windows.hotkey_config import (
    hotkey_label,
    hotkey_modifier_flags,
    hotkey_release_virtual_keys,
    hotkey_virtual_key,
)


class HotkeyRegistrationError(
    RuntimeError
):
    pass


class _WindowsHotkeyEventFilter(
    QAbstractNativeEventFilter
):
    def __init__(
        self,
        hotkey_id: int,
        callback: object,
    ) -> None:
        super().__init__()

        self.hotkey_id = hotkey_id
        self.callback = callback

    def nativeEventFilter(
        self,
        event_type: object,
        message: object,
    ) -> tuple[bool, int]:
        del event_type

        try:
            address = int(
                message
            )
        except (
            TypeError,
            ValueError,
        ):
            return (False, 0)

        if address == 0:
            return (False, 0)

        native_message = (
            ctypes.wintypes.MSG.from_address(
                address
            )
        )

        if (
            native_message.message
            != WM_HOTKEY
        ):
            return (False, 0)

        if (
            int(native_message.wParam)
            != self.hotkey_id
        ):
            return (False, 0)

        callback = self.callback

        if callable(callback):
            callback()

        return (True, 0)


class WindowsGlobalHotkey(QObject):
    activated = Signal()

    def __init__(
        self,
        app: QCoreApplication,
        modifier: str,
        key: str,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.app = app
        self.modifier = modifier
        self.key = key
        self.registered = False

        self.modifier_flags = (
            hotkey_modifier_flags(
                modifier
            )
        )

        self.virtual_key = (
            hotkey_virtual_key(
                key
            )
        )

        self.release_virtual_keys = (
            hotkey_release_virtual_keys(
                modifier,
                key,
            )
        )

        self.label = hotkey_label(
            modifier,
            key,
        )

        self.event_filter = (
            _WindowsHotkeyEventFilter(
                GLOBAL_HOTKEY_ID,
                self.activated.emit,
            )
        )

    def register(
        self,
    ) -> None:
        if self.registered:
            return

        user32 = _load_user32()

        _configure_user32(
            user32
        )

        self.app.installNativeEventFilter(
            self.event_filter
        )

        result = user32.RegisterHotKey(
            None,
            GLOBAL_HOTKEY_ID,
            self.modifier_flags,
            self.virtual_key,
        )

        if not result:
            self.app.removeNativeEventFilter(
                self.event_filter
            )

            error_code = (
                ctypes.get_last_error()
            )

            raise HotkeyRegistrationError(
                "Could not register the "
                "Windows global hotkey. "
                f"Win32 error: {error_code}"
            )

        self.registered = True

    def unregister(
        self,
    ) -> None:
        if not self.registered:
            return

        user32 = _load_user32()

        _configure_user32(
            user32
        )

        user32.UnregisterHotKey(
            None,
            GLOBAL_HOTKEY_ID,
        )

        self.app.removeNativeEventFilter(
            self.event_filter
        )

        self.registered = False


def _load_user32() -> Any:
    if sys.platform != "win32":
        raise RuntimeError(
            "WindowsGlobalHotkey can only "
            "be used on Windows."
        )

    win_dll = getattr(
        ctypes,
        "WinDLL",
        None,
    )

    if win_dll is None:
        raise RuntimeError(
            "ctypes.WinDLL is unavailable."
        )

    return win_dll(
        "user32",
        use_last_error=True,
    )


def _configure_user32(
    user32: Any,
) -> None:
    user32.RegisterHotKey.argtypes = [
        ctypes.wintypes.HWND,
        ctypes.c_int,
        ctypes.wintypes.UINT,
        ctypes.wintypes.UINT,
    ]

    user32.RegisterHotKey.restype = (
        ctypes.wintypes.BOOL
    )

    user32.UnregisterHotKey.argtypes = [
        ctypes.wintypes.HWND,
        ctypes.c_int,
    ]

    user32.UnregisterHotKey.restype = (
        ctypes.wintypes.BOOL
    )

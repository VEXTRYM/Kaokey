import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import QObject
from PySide6.QtGui import (
    QGuiApplication,
    QScreen,
)

from kaokey.ui.popup.popup_positioning import Rect


@dataclass(frozen=True)
class PopupCapabilities:
    """Native popup features provided by a platform backend."""

    hotkey: bool = False
    target_capture: bool = False
    caret_positioning: bool = False
    window_positioning: bool = False
    text_insertion: bool = False


@dataclass(frozen=True)
class PopupContext:
    """Platform context captured before the popup takes focus."""

    target: object | None
    caret_rect: Rect | None = None
    fallback_screen: QScreen | None = None


@dataclass(frozen=True)
class PopupInsertionResult:
    """Result of an attempt to insert text into the captured target."""

    inserted: bool
    focus_transferred: bool = False


@dataclass(frozen=True)
class PopupHotkey:
    """Platform-independent description of the active popup hotkey.

    On portal-managed desktops, modifier/key are the application's preferred
    trigger while label describes the binding the desktop actually accepted.
    """

    modifier: str
    key: str
    label: str
    system_managed: bool = False


@dataclass(frozen=True)
class PopupHotkeyActivation:
    """Information supplied when a global hotkey activates."""

    activation_token: str | None = None


class PopupHotkeyRegistrationError(RuntimeError):
    """Describes a failure to register the popup hotkey."""

    def __init__(
        self,
        message: str,
        *,
        previous_hotkey_restored: bool,
    ) -> None:
        super().__init__(message)

        self.previous_hotkey_restored = previous_hotkey_restored


PopupHotkeyActivationCallback = Callable[[PopupHotkeyActivation], None]
PopupContextCallback = Callable[[PopupContext], None]
PopupHotkeyRegistrationCallback = Callable[[PopupHotkey], None]
PopupHotkeyRegistrationErrorCallback = Callable[
    [PopupHotkeyRegistrationError], None
]


class PopupBackend(Protocol):
    """Platform services required by the popup feature."""

    @property
    def capabilities(
        self,
    ) -> PopupCapabilities: ...

    @property
    def active_hotkey(
        self,
    ) -> PopupHotkey | None: ...

    def capture_context(
        self,
        screens: Sequence[QScreen],
    ) -> PopupContext: ...

    def capture_context_async(
        self,
        screens: Sequence[QScreen],
        callback: PopupContextCallback,
    ) -> None: ...

    def set_hotkey(
        self,
        modifier: str,
        key: str,
        callback: PopupHotkeyActivationCallback,
        on_registered: PopupHotkeyRegistrationCallback,
        on_error: PopupHotkeyRegistrationErrorCallback,
    ) -> None: ...

    def clear_hotkey(
        self,
    ) -> None: ...

    def hotkey_keys_released(
        self,
    ) -> bool: ...

    def insert_text(
        self,
        target: object,
        text: str,
        *,
        before_focus_transfer: Callable[[], None],
    ) -> PopupInsertionResult: ...

    def target_still_active(
        self,
        target: object,
    ) -> bool: ...


class UnavailablePopupBackend(QObject):
    """Fallback backend for platforms without native popup integration."""

    @property
    def capabilities(
        self,
    ) -> PopupCapabilities:
        return PopupCapabilities()

    @property
    def active_hotkey(
        self,
    ) -> PopupHotkey | None:
        return None

    def capture_context(
        self,
        screens: Sequence[QScreen],
    ) -> PopupContext:
        del screens

        return PopupContext(target=None)

    def capture_context_async(
        self,
        screens: Sequence[QScreen],
        callback: PopupContextCallback,
    ) -> None:
        callback(self.capture_context(screens))

    def set_hotkey(
        self,
        modifier: str,
        key: str,
        callback: PopupHotkeyActivationCallback,
        on_registered: PopupHotkeyRegistrationCallback,
        on_error: PopupHotkeyRegistrationErrorCallback,
    ) -> None:
        del modifier, key, callback, on_registered

        on_error(
            PopupHotkeyRegistrationError(
                "Native popup hotkeys are unavailable on this platform.",
                previous_hotkey_restored=False,
            )
        )

    def clear_hotkey(
        self,
    ) -> None:
        return

    def hotkey_keys_released(
        self,
    ) -> bool:
        return True

    def insert_text(
        self,
        target: object,
        text: str,
        *,
        before_focus_transfer: Callable[[], None],
    ) -> PopupInsertionResult:
        del target, text, before_focus_transfer

        return PopupInsertionResult(inserted=False)

    def target_still_active(
        self,
        target: object,
    ) -> bool:
        del target

        return True


def create_popup_backend(
    app: QGuiApplication,
    parent: QObject | None = None,
) -> PopupBackend:
    """Create the native popup backend for the current platform."""
    if sys.platform == "win32":
        from kaokey.platforms.windows.popup_backend import (
            WindowsPopupBackend,
        )

        return WindowsPopupBackend(
            app,
            parent,
        )

    if sys.platform.startswith("linux"):
        from kaokey.platforms.linux.popup_backend import (
            create_linux_popup_backend,
        )

        return create_linux_popup_backend(
            app,
            parent,
        )

    return UnavailablePopupBackend(parent)

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import (
    QCoreApplication,
    QObject,
)
from PySide6.QtGui import QScreen

from kaokey.ui.popup.popup_positioning import Rect


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
    """Platform-independent description of the active popup hotkey."""

    modifier: str
    key: str
    label: str


class PopupHotkeyRegistrationError(RuntimeError):
    """Raised when the popup hotkey cannot be registered."""

    def __init__(
        self,
        message: str,
        *,
        previous_hotkey_restored: bool,
    ) -> None:
        super().__init__(message)

        self.previous_hotkey_restored = previous_hotkey_restored


class PopupBackend(Protocol):
    """Platform services required by the popup feature."""

    @property
    def available(
        self,
    ) -> bool: ...

    @property
    def active_hotkey(
        self,
    ) -> PopupHotkey | None: ...

    def capture_context(
        self,
        screens: Sequence[QScreen],
    ) -> PopupContext: ...

    def set_hotkey(
        self,
        modifier: str,
        key: str,
        callback: Callable[[], None],
    ) -> PopupHotkey: ...

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
    def available(
        self,
    ) -> bool:
        return False

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

    def set_hotkey(
        self,
        modifier: str,
        key: str,
        callback: Callable[[], None],
    ) -> PopupHotkey:
        del modifier, key, callback

        raise PopupHotkeyRegistrationError(
            "Native popup hotkeys are unavailable on this platform.",
            previous_hotkey_restored=False,
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
    app: QCoreApplication,
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

    return UnavailablePopupBackend(parent)

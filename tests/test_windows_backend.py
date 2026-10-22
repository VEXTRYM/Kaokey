from collections.abc import Callable
from typing import ClassVar

import pytest
from PySide6.QtWidgets import QApplication

from kaokey.platforms.popup_backend import (
    PopupHotkey,
    PopupHotkeyActivation,
    PopupHotkeyRegistrationError,
)
from kaokey.platforms.windows import popup_backend as windows_backend


def test_windows_insertion_uses_direct_target_then_keyboard_fallback(
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = windows_backend.WindowsPopupBackend(qapp)
    focus_transfers: list[str] = []
    keyboard_calls: list[tuple[int, str]] = []
    target = windows_backend.WindowsPopupTarget(100, 200)

    monkeypatch.setattr(
        windows_backend, "insert_text_into_native_edit", lambda handle, text: True
    )
    result = backend.insert_text(
        target, "(^_^)", before_focus_transfer=lambda: focus_transfers.append("focus")
    )
    assert result.inserted and not result.focus_transferred
    assert focus_transfers == []

    monkeypatch.setattr(
        windows_backend, "insert_text_into_native_edit", lambda handle, text: False
    )

    def insert_keyboard(handle: int, text: str) -> bool:
        keyboard_calls.append((handle, text))
        return True

    monkeypatch.setattr(windows_backend, "insert_unicode_text", insert_keyboard)
    result = backend.insert_text(
        target, "(o_o)", before_focus_transfer=lambda: focus_transfers.append("focus")
    )
    assert result.inserted and result.focus_transferred
    assert keyboard_calls == [(100, "(o_o)")]
    assert focus_transfers == ["focus"]

    assert not backend.insert_text(
        object(), "ignored", before_focus_transfer=lambda: focus_transfers.append("bad")
    ).inserted
    assert focus_transfers == ["focus"]

    monkeypatch.setattr(windows_backend, "get_foreground_window_handle", lambda: 100)
    assert backend.target_still_active(target)
    monkeypatch.setattr(windows_backend, "get_foreground_window_handle", lambda: 999)
    assert not backend.target_still_active(target)


def test_windows_failed_hotkey_change_restores_previous_registration(
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSignal:
        def __init__(self) -> None:
            self.callback: Callable[[], None] | None = None

        def connect(self, callback: Callable[[], None]) -> None:
            self.callback = callback

        def emit(self) -> None:
            assert self.callback is not None
            self.callback()

    class FakeHotkey:
        instances: ClassVar[list["FakeHotkey"]] = []

        def __init__(
            self, app: object, modifier: str, key: str, parent: object
        ) -> None:
            del app, parent
            self.modifier = modifier
            self.key = key
            self.label = f"{modifier}+{key}"
            self.activated = FakeSignal()
            self.registered = False
            self.deleted = False
            self.instances.append(self)

        def register(self) -> None:
            if self.key == "J":
                raise windows_backend.HotkeyRegistrationError("already used")
            self.registered = True

        def unregister(self) -> None:
            self.registered = False

        def deleteLater(self) -> None:
            self.deleted = True

    monkeypatch.setattr(windows_backend, "WindowsGlobalHotkey", FakeHotkey)
    backend = windows_backend.WindowsPopupBackend(qapp)
    registered: list[PopupHotkey] = []
    errors: list[PopupHotkeyRegistrationError] = []
    activations: list[PopupHotkeyActivation] = []

    backend.set_hotkey("Alt", "K", activations.append, registered.append, errors.append)
    first = FakeHotkey.instances[0]
    first.activated.emit()
    assert activations == [PopupHotkeyActivation()]

    backend.set_hotkey("Alt", "J", activations.append, registered.append, errors.append)
    assert backend.active_hotkey == PopupHotkey("Alt", "K", "Alt+K")
    assert first.registered and not first.deleted
    assert FakeHotkey.instances[1].deleted
    assert len(errors) == 1 and errors[0].previous_hotkey_restored
    backend.clear_hotkey()
    assert first.deleted
    assert backend.active_hotkey is None

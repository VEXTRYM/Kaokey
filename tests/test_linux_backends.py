"""Backend registration tests using native-service fakes.

These exercise the switching behavior without requiring an X server or portal.
"""

from collections.abc import Callable
from typing import ClassVar

import pytest
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from kaokey.platforms.linux import common_popup_backend
from kaokey.platforms.linux.x11 import popup_backend as x11_backend
from kaokey.platforms.popup_backend import (
    PopupHotkey,
    PopupHotkeyActivation,
    PopupHotkeyRegistrationError,
)


@pytest.fixture(scope="module")
def gui_app(qapp: QApplication) -> QGuiApplication:
    return qapp


@pytest.fixture
def no_accessibility(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAccessibility:
        available = False

    monkeypatch.setattr(
        common_popup_backend, "LinuxAccessibility", FakeAccessibility
    )


def test_x11_failed_rebinding_restores_previous_grab(
    gui_app: QGuiApplication,
    no_accessibility: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del no_accessibility

    class FakeHotkey:
        instances: ClassVar[list["FakeHotkey"]] = []

        def __init__(
            self,
            modifier: str,
            key: str,
            callback: Callable[[int], None],
            parent: object,
        ) -> None:
            del parent
            self.modifier = modifier
            self.key = key
            self.label = f"{modifier}+{key}"
            self.callback = callback
            self.registered = False
            self.closed = False
            self.instances.append(self)

        def register(self) -> None:
            if self.key == "J":
                raise x11_backend.X11HotkeyError("grab rejected")
            self.registered = True

        def unregister(self) -> None:
            self.registered = False

        def close(self) -> None:
            self.unregister()
            self.closed = True

        def deleteLater(self) -> None:
            pass

    monkeypatch.setattr(x11_backend, "X11GlobalHotkey", FakeHotkey)
    monkeypatch.setattr(x11_backend, "x11_hotkeys_available", lambda: True)
    backend = x11_backend.X11PopupBackend(gui_app)
    registered: list[PopupHotkey] = []
    errors: list[PopupHotkeyRegistrationError] = []
    activations: list[PopupHotkeyActivation] = []

    backend.set_hotkey("Alt", "K", activations.append, registered.append, errors.append)
    first = FakeHotkey.instances[0]
    assert first.registered
    first.callback(123)
    assert activations == [PopupHotkeyActivation(x11_timestamp=123)]

    backend.set_hotkey("Alt", "J", activations.append, registered.append, errors.append)
    assert backend.active_hotkey == PopupHotkey("Alt", "K", "Alt+K")
    assert first.registered and not first.closed
    assert FakeHotkey.instances[1].closed
    assert len(registered) == 1
    assert len(errors) == 1
    assert errors[0].previous_hotkey_restored

    backend.clear_hotkey()
    assert first.closed
    assert backend.active_hotkey is None


def test_wayland_rebinding_keeps_active_shortcut_until_portal_accepts(
    gui_app: QGuiApplication,
    no_accessibility: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del no_accessibility
    pytest.importorskip("dbus_next")
    from kaokey.platforms.linux.wayland import popup_backend as wayland_backend

    class FakeShortcut:
        instances: ClassVar[list["FakeShortcut"]] = []

        def __init__(
            self,
            modifier: str,
            key: str,
            callback: Callable[[str | None], None],
            parent: object,
        ) -> None:
            del parent
            self.modifier = modifier
            self.key = key
            self.label = f"{modifier}+{key}"
            self.callback = callback
            self.registered = False
            self.closed = False
            self.on_registered: Callable[[PopupHotkey], None] | None = None
            self.on_error: Callable[[str], None] | None = None
            self.instances.append(self)

        def register(
            self,
            on_registered: Callable[[PopupHotkey], None],
            on_error: Callable[[str], None],
        ) -> None:
            self.on_registered = on_registered
            self.on_error = on_error

        def accept(self, label: str) -> None:
            self.label = label
            self.registered = True
            assert self.on_registered is not None
            self.on_registered(PopupHotkey(self.modifier, self.key, label))

        def fail(self, message: str) -> None:
            assert self.on_error is not None
            self.on_error(message)

        def close(self) -> None:
            self.registered = False
            self.closed = True

        def deleteLater(self) -> None:
            pass

    monkeypatch.setattr(wayland_backend, "WaylandGlobalShortcut", FakeShortcut)
    monkeypatch.setattr(
        wayland_backend, "wayland_global_shortcuts_available", lambda: True
    )
    backend = wayland_backend.WaylandPopupBackend(gui_app)
    registered: list[PopupHotkey] = []
    errors: list[PopupHotkeyRegistrationError] = []
    activations: list[PopupHotkeyActivation] = []

    backend.set_hotkey("Alt", "K", activations.append, registered.append, errors.append)
    first = FakeShortcut.instances[0]
    assert backend.active_hotkey is None
    first.accept("Super+K")
    assert backend.active_hotkey == PopupHotkey("Alt", "K", "Super+K", True)
    first.callback("portal-token")
    assert activations == [PopupHotkeyActivation(activation_token="portal-token")]

    backend.set_hotkey("Alt", "J", activations.append, registered.append, errors.append)
    second = FakeShortcut.instances[1]
    assert backend.active_hotkey == PopupHotkey("Alt", "K", "Super+K", True)
    second.fail("portal rejected shortcut")
    assert second.closed
    assert not first.closed
    assert errors[0].previous_hotkey_restored
    second.accept("Alt+J")  # a late portal reply must not replace the live shortcut
    assert backend.active_hotkey == PopupHotkey("Alt", "K", "Super+K", True)

    backend.set_hotkey("Ctrl", "L", activations.append, registered.append, errors.append)
    third = FakeShortcut.instances[2]
    third.accept("Ctrl+L")
    assert first.closed
    assert backend.active_hotkey == PopupHotkey("Ctrl", "L", "Ctrl+L", True)
    assert len(registered) == 2
    backend.clear_hotkey()
    assert third.closed
    assert backend.active_hotkey is None

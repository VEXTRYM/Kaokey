import asyncio
from typing import cast

import pytest

pytest.importorskip("dbus_next")

from dbus_next.aio.message_bus import MessageBus
from dbus_next.constants import MessageType
from dbus_next.message import Message
from dbus_next.signature import Variant

from kaokey.platforms.linux import native_accessibility
from kaokey.platforms.linux.session import display_backend_from_qt_platform
from kaokey.platforms.linux.wayland.portal_shortcut import (
    GLOBAL_SHORTCUTS_INTERFACE,
    REQUEST_INTERFACE,
    SHORTCUT_ID,
    WaylandGlobalShortcut,
    WaylandPortalError,
    _bound_trigger_description,
    _preferred_trigger,
    _register_host_app,
    _request_path,
)


def test_linux_backend_follows_qt_display_plugin():
    assert display_backend_from_qt_platform("xcb") == "x11"
    assert display_backend_from_qt_platform("wayland") == "wayland"
    assert display_backend_from_qt_platform("wayland-egl") == "wayland"
    assert display_backend_from_qt_platform("offscreen") is None


def test_wayland_shortcut_requires_a_bound_result():
    assert _preferred_trigger("Alt", "K") == "ALT+k"
    assert _bound_trigger_description({"shortcuts": []}, "Alt+K") is None
    assert _bound_trigger_description(
        {"shortcuts": [["another-shortcut", {}]]}, "Alt+K"
    ) is None
    assert _bound_trigger_description(
        {"shortcuts": [[SHORTCUT_ID, {
            "trigger_description": Variant("s", "Super+K")
        }]]},
        "Alt+K",
    ) == "Super+K"


def test_wayland_bind_shortcuts_has_portal_signature():
    shortcut = WaylandGlobalShortcut("Alt", "K", lambda _: None)

    class FakeBus:
        unique_name = ":1.42"

        def __init__(self):
            self.messages: list[Message] = []

        async def call(self, message: Message) -> Message:
            self.messages.append(message)
            assert message.interface == GLOBAL_SHORTCUTS_INTERFACE
            assert message.member == "BindShortcuts"
            assert message.signature == "oa(sa{sv})sa{sv}"
            assert message.body[1][0][0] == SHORTCUT_ID
            # A valid Message object alone does not prove D-Bus transport can
            # serialize its nested struct and variant map.
            assert message._marshall()

            token = message.body[-1]["handle_token"].value
            path = _request_path(self.unique_name, token)
            response = Message.new_signal(
                path,
                REQUEST_INTERFACE,
                "Response",
                "ua{sv}",
                [0, {"shortcuts": Variant("a(sa{sv})", [[
                    SHORTCUT_ID,
                    {"trigger_description": Variant("s", "Alt+K")},
                ]])}],
            )
            asyncio.get_running_loop().call_soon(
                shortcut._handle_message, response
            )
            return Message(
                message_type=MessageType.METHOD_RETURN,
                reply_serial=1,
                signature="o",
                body=[path],
            )

    bus = FakeBus()
    results = asyncio.run(shortcut._request(
        cast(MessageBus, bus),
        "BindShortcuts",
        "oa(sa{sv})sa{sv}",
        [
            "/org/freedesktop/portal/desktop/session/1",
            [[SHORTCUT_ID, {
                "description": Variant("s", "Open Kaokey popup"),
                "preferred_trigger": Variant("s", "ALT+k"),
            }]],
            "",
            {},
        ],
    ))
    assert _bound_trigger_description(results, "Alt+K") == "Alt+K"
    assert shortcut._responses == {}


def test_wayland_create_session_decodes_portal_response():
    shortcut = WaylandGlobalShortcut("Alt", "K", lambda _: None)
    session_path = "/org/freedesktop/portal/desktop/session/1_42/kaokey"

    class FakeBus:
        unique_name = ":1.42"

        async def call(self, message: Message) -> Message:
            assert message.member == "CreateSession"
            assert message.signature == "a{sv}"
            assert "session_handle_token" in message.body[0]
            assert message._marshall()
            token = message.body[0]["handle_token"].value
            path = _request_path(self.unique_name, token)
            asyncio.get_running_loop().call_soon(
                shortcut._handle_message,
                Message.new_signal(
                    path,
                    REQUEST_INTERFACE,
                    "Response",
                    "ua{sv}",
                    [0, {"session_handle": Variant("s", session_path)}],
                ),
            )
            return Message(
                message_type=MessageType.METHOD_RETURN,
                reply_serial=1,
                signature="o",
                body=[path],
            )

    results = asyncio.run(shortcut._request(
        cast(MessageBus, FakeBus()), "CreateSession", "a{sv}",
        [{"session_handle_token": Variant("s", "kaokey_session")}],
    ))
    assert cast(Variant, results["session_handle"]).value == session_path


def test_wayland_portal_error_cleans_up_pending_request():
    shortcut = WaylandGlobalShortcut("Alt", "K", lambda _: None)

    class FakeBus:
        unique_name = ":1.42"

        async def call(self, message: Message) -> Message:
            assert message.member == "CreateSession"
            return Message(
                message_type=MessageType.ERROR,
                error_name="org.freedesktop.portal.Error.Failed",
                reply_serial=1,
                signature="s",
                body=["permission denied"],
            )

    with pytest.raises(WaylandPortalError, match="permission denied"):
        asyncio.run(shortcut._request(
            cast(MessageBus, FakeBus()),
            "CreateSession",
            "a{sv}",
            [{"session_handle_token": Variant("s", "kaokey_session")}],
        ))
    assert shortcut._responses == {}


def test_wayland_activation_token_reaches_callback():
    activated: list[str | None] = []
    shortcut = WaylandGlobalShortcut("Alt", "K", activated.append)
    shortcut._session_path = "/org/freedesktop/portal/desktop/session/1_42/kaokey"
    shortcut._registered = True

    shortcut._handle_message(Message.new_signal(
        "/org/freedesktop/portal/desktop",
        GLOBAL_SHORTCUTS_INTERFACE,
        "Activated",
        "osta{sv}",
        [shortcut._session_path, SHORTCUT_ID, 1, {
            "activation_token": Variant("s", "one-time-token"),
        }],
    ))
    assert activated == ["one-time-token"]


def test_wayland_registers_native_app_before_shortcuts(monkeypatch):
    monkeypatch.delenv("FLATPAK_ID", raising=False)
    monkeypatch.delenv("SNAP", raising=False)

    class FakeBus:
        async def call(self, message: Message) -> Message:
            assert message.member == "Register"
            assert message.signature == "sa{sv}"
            assert message.body == ["io.github.VEXTRYM.Kaokey", {}]
            assert message._marshall()
            return Message(
                message_type=MessageType.METHOD_RETURN,
                reply_serial=1,
            )

    asyncio.run(_register_host_app(cast(MessageBus, FakeBus())))


def test_atspi_focus_scan_stops_before_popup_timeout(monkeypatch):
    class SlowLibrary:
        def __init__(self):
            self.visited: list[int] = []
            self.released: list[int] = []

        def desktop(self):
            return 1

        def state_enabled(self, pointer, state):
            self.visited.append(pointer)
            return False

        def child_count(self, pointer):
            return 100 if pointer == 1 else 0

        def child_at(self, pointer, index):
            return index + 2

        def unref(self, pointer):
            self.released.append(pointer)

    clock = iter(index / 100 for index in range(1000))
    monkeypatch.setattr(native_accessibility.time, "monotonic", lambda: next(clock))
    library = SlowLibrary()
    accessibility = native_accessibility.LinuxAccessibility.__new__(
        native_accessibility.LinuxAccessibility
    )
    monkeypatch.setattr(accessibility, "library", library, raising=False)

    assert accessibility.capture_target() is None
    assert len(library.visited) < 100
    assert 1 in library.released
    assert set(library.visited) <= set(library.released)
    assert len(library.released) == len(set(library.released))

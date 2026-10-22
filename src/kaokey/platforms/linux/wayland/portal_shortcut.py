"""Wayland global shortcut via the XDG Desktop Portal.

The portal's nested a(sa{sv}) argument needs an explicit D-Bus signature.
An asyncio worker owns the bus; Qt signals deliver events to the UI thread.
"""

import asyncio
import os
import secrets
import threading
from collections.abc import Callable, Mapping, Sequence

from dbus_next.aio.message_bus import MessageBus
from dbus_next.constants import MessageType
from dbus_next.message import Message
from dbus_next.signature import Variant
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtDBus import QDBusConnection, QDBusInterface

from kaokey.config.constants import APPLICATION_ID
from kaokey.platforms.linux.dbus import dbus_int, read_dbus_property
from kaokey.platforms.popup_backend import PopupHotkey

PORTAL_SERVICE = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
GLOBAL_SHORTCUTS_INTERFACE = "org.freedesktop.portal.GlobalShortcuts"
REQUEST_INTERFACE = "org.freedesktop.portal.Request"
HOST_REGISTRY_INTERFACE = "org.freedesktop.host.portal.Registry"
SHORTCUT_ID = "show-popup"
SHORTCUT_DESCRIPTION = "Open Kaokey popup"
REQUEST_TIMEOUT_SECONDS = 120

MODIFIER_NAMES = {"Alt": "ALT", "Ctrl": "CTRL", "Shift": "SHIFT"}


class WaylandPortalError(RuntimeError):
    """The desktop portal could not register a shortcut."""


class WaylandGlobalShortcut(QObject):
    """One desktop portal session containing the Kaokey shortcut."""

    _registered_signal = Signal(str)
    _error_signal = Signal(str)
    _activated_signal = Signal(object)

    def __init__(
        self,
        modifier: str,
        key: str,
        callback: Callable[[str | None], None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.modifier = modifier
        self.key = key
        self.label = f"{modifier}+{key}"
        self.callback = callback
        self.preferred_trigger = _preferred_trigger(modifier, key)

        self._closed = threading.Event()
        self._registered = False
        self._worker: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task[None] | None = None
        self._responses: dict[str, asyncio.Future[tuple[int, object]]] = {}
        self._session_path: str | None = None
        self._on_registered: Callable[[PopupHotkey], None] | None = None
        self._on_error: Callable[[str], None] | None = None

        self._registered_signal.connect(self._notify_registered)
        self._error_signal.connect(self._notify_error)
        self._activated_signal.connect(self._notify_activated)

    def register(
        self,
        on_registered: Callable[[PopupHotkey], None],
        on_error: Callable[[str], None],
    ) -> None:
        if self._closed.is_set():
            on_error("The GlobalShortcuts session is already closed.")
            return
        if self._registered:
            on_registered(self._popup_hotkey())
            return
        if self._worker is not None:
            on_error("The GlobalShortcuts session is already registering.")
            return

        self._on_registered = on_registered
        self._on_error = on_error
        self._worker = threading.Thread(
            target=self._run,
            name="kaokey-wayland-shortcut",
            daemon=True,
        )
        self._worker.start()

    @property
    def registered(self) -> bool:
        return self._registered and not self._closed.is_set()

    def close(self) -> None:
        if self._closed.is_set():
            return
        self._closed.set()
        self._registered = False
        loop = self._loop
        task = self._task
        if loop is not None and task is not None and loop.is_running():
            loop.call_soon_threadsafe(task.cancel)

    def _run(self) -> None:
        try:
            asyncio.run(self._run_session())
        except Exception as error:  # noqa: BLE001 - worker failure reaches the UI
            if not self._closed.is_set():
                self._error_signal.emit(f"GlobalShortcuts portal failed: {error}")

    async def _run_session(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._task = asyncio.current_task()
        if self._closed.is_set():
            return

        bus = await MessageBus().connect()
        try:
            if self._closed.is_set():
                return
            await _register_host_app(bus)
            bus.add_message_handler(self._handle_message)
            await _subscribe(bus, REQUEST_INTERFACE, "Response")
            await _subscribe(bus, GLOBAL_SHORTCUTS_INTERFACE, "Activated")

            create_results = await self._request(
                bus,
                "CreateSession",
                "a{sv}",
                [{"session_handle_token": Variant(
                    "s", _portal_token("session")
                )}],
            )
            session_path = _value(create_results.get("session_handle"))
            if not isinstance(session_path, str) or not session_path.startswith("/"):
                raise WaylandPortalError(
                    "The portal returned no GlobalShortcuts session handle."
                )
            self._session_path = session_path

            shortcuts = [[SHORTCUT_ID, {
                "description": Variant("s", SHORTCUT_DESCRIPTION),
                "preferred_trigger": Variant("s", self.preferred_trigger),
            }]]
            bind_results = await self._request(
                bus,
                "BindShortcuts",
                "oa(sa{sv})sa{sv}",
                [session_path, shortcuts, "", {}],
            )
            label = _bound_trigger_description(bind_results, self.label)
            if label is None:
                raise WaylandPortalError(
                    "The desktop did not bind the Kaokey shortcut."
                )

            if not self._closed.is_set():
                self._registered_signal.emit(label)
                await bus.wait_for_disconnect()
        except asyncio.CancelledError:
            pass
        finally:
            self._registered = False
            bus.disconnect()
            self._session_path = None
            self._responses.clear()
            self._loop = None
            self._task = None

    async def _request(
        self,
        bus: MessageBus,
        member: str,
        signature: str,
        body: list[object],
    ) -> Mapping[str, object]:
        token = _portal_token(member.lower())
        if not bus.unique_name:
            raise WaylandPortalError("The D-Bus session has no unique name.")
        request_path = _request_path(bus.unique_name, token)
        future: asyncio.Future[tuple[int, object]] = (
            asyncio.get_running_loop().create_future()
        )
        self._responses[request_path] = future

        options = {"handle_token": Variant("s", token)}
        if member == "CreateSession":
            create_options = body[0]
            if not isinstance(create_options, dict):
                raise TypeError("CreateSession options must be a dictionary.")
            create_options.update(options)
        else:
            body[-1] = options

        actual_path: str | None = None
        try:
            reply = await _call(
                bus,
                PORTAL_SERVICE,
                PORTAL_PATH,
                GLOBAL_SHORTCUTS_INTERFACE,
                member,
                signature,
                body,
            )
            value = reply.body[0] if reply.body else None
            if not isinstance(value, str) or not value.startswith("/"):
                raise WaylandPortalError(
                    f"The portal returned no {member} request handle."
                )
            actual_path = value
            self._responses[actual_path] = future
            response, results = await asyncio.wait_for(
                future, REQUEST_TIMEOUT_SECONDS
            )
            if response != 0:
                raise WaylandPortalError(
                    f"{member} was cancelled or failed (response {response})."
                )
            if not isinstance(results, Mapping):
                raise WaylandPortalError(
                    f"The portal returned invalid {member} results."
                )
            return results
        except TimeoutError as error:
            raise WaylandPortalError(
                f"The portal did not answer {member}."
            ) from error
        finally:
            self._responses.pop(request_path, None)
            if actual_path is not None:
                self._responses.pop(actual_path, None)

    def _handle_message(self, message: Message) -> None:
        if message.message_type != MessageType.SIGNAL:
            return
        if (
            message.interface == REQUEST_INTERFACE
            and message.member == "Response"
        ):
            future = self._responses.get(message.path)
            if future is not None and not future.done() and len(message.body) >= 2:
                future.set_result((message.body[0], message.body[1]))
            return
        if (
            message.interface == GLOBAL_SHORTCUTS_INTERFACE
            and message.member == "Activated"
            and message.path == PORTAL_PATH
            and len(message.body) >= 4
            and message.body[0] == self._session_path
            and message.body[1] == SHORTCUT_ID
            and self._registered
            and not self._closed.is_set()
        ):
            options = message.body[3]
            token = _value(options.get("activation_token")) if isinstance(
                options, Mapping
            ) else None
            self._activated_signal.emit(token if isinstance(token, str) else None)

    @Slot(str)
    def _notify_registered(self, label: str) -> None:
        if self._closed.is_set() or self._loop is None:
            return
        self.label = label
        self._registered = True
        if self._on_registered is not None:
            self._on_registered(self._popup_hotkey())

    @Slot(str)
    def _notify_error(self, message: str) -> None:
        if not self._closed.is_set() and self._on_error is not None:
            self._on_error(message)

    @Slot(object)
    def _notify_activated(self, token: object) -> None:
        if not self._closed.is_set():
            self.callback(token if isinstance(token, str) else None)

    def _popup_hotkey(self) -> PopupHotkey:
        return PopupHotkey(self.modifier, self.key, self.label)


async def _call(
    bus: MessageBus,
    destination: str,
    path: str,
    interface: str,
    member: str,
    signature: str,
    body: list[object],
) -> Message:
    reply = await bus.call(Message(
        destination=destination,
        path=path,
        interface=interface,
        member=member,
        signature=signature,
        body=body,
    ))
    if reply is None or reply.message_type == MessageType.ERROR:
        detail = reply.body[0] if reply is not None and reply.body else ""
        raise WaylandPortalError(f"{member} failed: {detail}")
    return reply


async def _subscribe(bus: MessageBus, interface: str, member: str) -> None:
    rule = (
        f"type='signal',sender='{PORTAL_SERVICE}',"
        f"interface='{interface}',member='{member}'"
    )
    await _call(
        bus,
        "org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus",
        "AddMatch",
        "s",
        [rule],
    )


async def _register_host_app(bus: MessageBus) -> None:
    """Associate a native app's bus connection with its desktop file ID."""
    if os.environ.get("FLATPAK_ID") or os.environ.get("SNAP"):
        return

    reply = await bus.call(Message(
        destination=PORTAL_SERVICE,
        path=PORTAL_PATH,
        interface=HOST_REGISTRY_INTERFACE,
        member="Register",
        signature="sa{sv}",
        body=[APPLICATION_ID, {}],
    ))
    if reply is None:
        raise WaylandPortalError("The host app registry did not respond.")
    if reply.message_type != MessageType.ERROR:
        return
    if reply.error_name in {
        "org.freedesktop.DBus.Error.UnknownInterface",
        "org.freedesktop.DBus.Error.UnknownMethod",
    }:
        # Older portal versions infer the app ID from the process.
        return
    detail = reply.body[0] if reply.body else reply.error_name
    raise WaylandPortalError(
        "Could not register Kaokey with the desktop portal. Install "
        f"{APPLICATION_ID}.desktop, then restart Kaokey: {detail}"
    )


def wayland_global_shortcuts_available() -> bool:
    """Return whether the desktop exposes the GlobalShortcuts portal."""
    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        return False
    portal = QDBusInterface(
        PORTAL_SERVICE, PORTAL_PATH, GLOBAL_SHORTCUTS_INTERFACE, bus
    )
    if not portal.isValid():
        return False
    version = dbus_int(read_dbus_property(portal, "version"))
    return version is not None and version >= 1


def _preferred_trigger(modifier: str, key: str) -> str:
    modifier_name = MODIFIER_NAMES.get(modifier)
    if modifier_name is None:
        raise WaylandPortalError(
            f"Unsupported Wayland hotkey modifier: {modifier}."
        )
    normalized_key = key.upper()
    if len(normalized_key) == 1 and (
        "A" <= normalized_key <= "Z" or "0" <= normalized_key <= "9"
    ):
        key_name = normalized_key.lower()
    elif (
        normalized_key.startswith("F")
        and normalized_key[1:].isdigit()
        and 1 <= int(normalized_key[1:]) <= 12
    ):
        key_name = normalized_key
    else:
        raise WaylandPortalError(f"Unsupported Wayland hotkey key: {key}.")
    return f"{modifier_name}+{key_name}"


def _portal_token(prefix: str) -> str:
    return f"kaokey_{prefix}_{secrets.token_hex(8)}"


def _request_path(sender: str, token: str) -> str:
    return (
        "/org/freedesktop/portal/desktop/request/"
        f"{sender.removeprefix(':').replace('.', '_')}/{token}"
    )


def _value(value: object) -> object:
    return value.value if isinstance(value, Variant) else value


def _bound_trigger_description(
    results: Mapping[str, object], fallback: str
) -> str | None:
    shortcuts = _value(results.get("shortcuts"))
    if not isinstance(shortcuts, Sequence) or isinstance(
        shortcuts, (str, bytes, bytearray)
    ):
        return None
    for shortcut in shortcuts:
        if not isinstance(shortcut, Sequence) or len(shortcut) < 2:
            continue
        if _value(shortcut[0]) != SHORTCUT_ID:
            continue
        details = _value(shortcut[1])
        if not isinstance(details, Mapping):
            return fallback
        description = _value(details.get("trigger_description"))
        return description if isinstance(description, str) and description else fallback
    return None

import secrets
from collections.abc import Callable, Mapping, Sequence

from PySide6.QtCore import (
    QObject,
    SLOT,
    Slot,
)
from PySide6.QtDBus import (
    QDBusConnection,
    QDBusInterface,
    QDBusMessage,
    QDBusObjectPath,
)

from kaokey.platforms.linux.dbus import (
    dbus_int,
    read_dbus_property,
    unwrap_dbus_value,
)
from kaokey.platforms.popup_backend import PopupHotkey

PORTAL_SERVICE = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
GLOBAL_SHORTCUTS_INTERFACE = "org.freedesktop.portal.GlobalShortcuts"
REQUEST_INTERFACE = "org.freedesktop.portal.Request"
SESSION_INTERFACE = "org.freedesktop.portal.Session"

SHORTCUT_ID = "show-popup"
SHORTCUT_DESCRIPTION = "Open Kaokey popup"

PORTAL_RESPONSE_SUCCESS = 0

MODIFIER_NAMES = {
    "Alt": "ALT",
    "Ctrl": "CTRL",
    "Shift": "SHIFT",
}

def _dbus_slot(
    signature: str,
) -> bytes:
    return SLOT(signature).encode("utf-8")

class WaylandPortalError(RuntimeError):
    """Raised when the GlobalShortcuts portal cannot be used."""


class WaylandGlobalShortcut(QObject):
    """One GlobalShortcuts portal session containing the Kaokey hotkey."""

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
        self.preferred_trigger = _preferred_trigger(
            modifier,
            key,
        )

        self.bus = QDBusConnection.sessionBus()

        if not self.bus.isConnected():
            raise WaylandPortalError(
                "The D-Bus session bus is unavailable."
            )

        self.portal = QDBusInterface(
            PORTAL_SERVICE,
            PORTAL_PATH,
            GLOBAL_SHORTCUTS_INTERFACE,
            self.bus,
            self,
        )

        if not self.portal.isValid():
            raise WaylandPortalError(
                "The GlobalShortcuts portal is unavailable."
            )

        version = dbus_int(
            read_dbus_property(
                self.portal,
                "version",
            )
        )

        if version is None or version < 1:
            raise WaylandPortalError(
                "The GlobalShortcuts portal is unsupported."
            )

        self.session_path: str | None = None
        self._create_request_path: str | None = None
        self._bind_request_path: str | None = None
        self._registered = False
        self._closed = False

        self._on_registered: Callable[[PopupHotkey], None] | None = None
        self._on_error: Callable[[str], None] | None = None

        self._activation_connected = self.bus.connect(
            PORTAL_SERVICE,
            PORTAL_PATH,
            GLOBAL_SHORTCUTS_INTERFACE,
            "Activated",
            self,
            _dbus_slot(
                "_on_activated("
                "QDBusObjectPath,QString,qulonglong,QVariantMap)"
            ),
        )

        if not self._activation_connected:
            raise WaylandPortalError(
                "Could not subscribe to GlobalShortcuts activation events."
            )

    def register(
        self,
        on_registered: Callable[[PopupHotkey], None],
        on_error: Callable[[str], None],
    ) -> None:
        if self._closed:
            on_error("The GlobalShortcuts session is already closed.")
            return

        if self._registered:
            on_registered(
                PopupHotkey(
                    modifier=self.modifier,
                    key=self.key,
                    label=self.label,
                )
            )
            return

        self._on_registered = on_registered
        self._on_error = on_error

        handle_token = _portal_token("kaokey_create")
        session_token = _portal_token("kaokey_session")

        request_path = _request_path(
            self.bus,
            handle_token,
        )
        self._create_request_path = request_path

        if not self.bus.connect(
            PORTAL_SERVICE,
            request_path,
            REQUEST_INTERFACE,
            "Response",
            self,
            _dbus_slot("_on_create_response(uint,QVariantMap)"),
        ):
            self._fail(
                "Could not subscribe to the portal session response."
            )
            return

        reply = self.portal.call(
            "CreateSession",
            {
                "handle_token": handle_token,
                "session_handle_token": session_token,
            },
        )

        actual_path = _reply_object_path(reply)

        if actual_path is None:
            self._fail(
                _reply_error(
                    reply,
                    "Could not create a GlobalShortcuts session.",
                )
            )
            return

        self._move_request_subscription(
            request_path,
            actual_path,
            "_on_create_response(uint,QVariantMap)",
            create_request=True,
        )

    def close(
        self,
    ) -> None:
        if self._closed:
            return

        self._closed = True
        self._registered = False

        self._close_request(
            self._create_request_path
        )
        self._disconnect_request(
            self._create_request_path,
            "_on_create_response(uint,QVariantMap)",
        )
        self._create_request_path = None

        self._close_request(
            self._bind_request_path
        )
        self._disconnect_request(
            self._bind_request_path,
            "_on_bind_response(uint,QVariantMap)",
        )
        self._bind_request_path = None

        if self._activation_connected:
            self.bus.disconnect(
                PORTAL_SERVICE,
                PORTAL_PATH,
                GLOBAL_SHORTCUTS_INTERFACE,
                "Activated",
                self,
                _dbus_slot(
                    "_on_activated("
                    "QDBusObjectPath,QString,qulonglong,QVariantMap)"
                ),
            )
            self._activation_connected = False

        session_path = self.session_path
        self.session_path = None

        if session_path is not None:
            session = QDBusInterface(
                PORTAL_SERVICE,
                session_path,
                SESSION_INTERFACE,
                self.bus,
            )

            if session.isValid():
                session.call("Close")

    @Slot("uint", "QVariantMap")
    def _on_create_response(
        self,
        response: int,
        results: dict[str, object],
    ) -> None:
        request_path = self._create_request_path
        self._create_request_path = None

        self._disconnect_request(
            request_path,
            "_on_create_response(uint,QVariantMap)",
        )

        if self._closed:
            return

        if response != PORTAL_RESPONSE_SUCCESS:
            self._fail(
                _portal_response_error(
                    response,
                    "GlobalShortcuts session creation",
                )
            )
            return

        session_path = _mapping_string(
            results,
            "session_handle",
        )

        if session_path is None:
            self._fail(
                "The GlobalShortcuts portal returned no session handle."
            )
            return

        self.session_path = session_path
        self._bind_shortcut()

    @Slot("uint", "QVariantMap")
    def _on_bind_response(
        self,
        response: int,
        results: dict[str, object],
    ) -> None:
        request_path = self._bind_request_path
        self._bind_request_path = None

        self._disconnect_request(
            request_path,
            "_on_bind_response(uint,QVariantMap)",
        )

        if self._closed:
            return

        if response != PORTAL_RESPONSE_SUCCESS:
            self._fail(
                _portal_response_error(
                    response,
                    "Global shortcut binding",
                )
            )
            return

        self.label = _bound_trigger_description(
            results,
            self.label,
        )
        self._registered = True

        callback = self._on_registered

        if callback is not None:
            callback(
                PopupHotkey(
                    modifier=self.modifier,
                    key=self.key,
                    label=self.label,
                )
            )

    @Slot(
        "QDBusObjectPath",
        "QString",
        "qulonglong",
        "QVariantMap",
    )
    def _on_activated(
        self,
        session_handle: QDBusObjectPath,
        shortcut_id: str,
        _timestamp: int,
        options: dict[str, object],
    ) -> None:
        if self._closed or not self._registered:
            return

        session_path = unwrap_dbus_value(
            session_handle
        )

        if (
            session_path != self.session_path
            or shortcut_id != SHORTCUT_ID
        ):
            return

        self.callback(
            _mapping_string(
                options,
                "activation_token",
            )
        )

    def _bind_shortcut(
        self,
    ) -> None:
        session_path = self.session_path

        if session_path is None:
            self._fail(
                "The GlobalShortcuts session was not created."
            )
            return

        handle_token = _portal_token("kaokey_bind")
        request_path = _request_path(
            self.bus,
            handle_token,
        )
        self._bind_request_path = request_path

        if not self.bus.connect(
            PORTAL_SERVICE,
            request_path,
            REQUEST_INTERFACE,
            "Response",
            self,
            _dbus_slot("_on_bind_response(uint,QVariantMap)"),
        ):
            self._fail(
                "Could not subscribe to the shortcut binding response."
            )
            return

        shortcuts = [
            (
                SHORTCUT_ID,
                {
                    "description": SHORTCUT_DESCRIPTION,
                    "preferred_trigger": self.preferred_trigger,
                },
            )
        ]

        reply = self.portal.call(
            "BindShortcuts",
            QDBusObjectPath(session_path),
            shortcuts,
            "",
            {
                "handle_token": handle_token,
            },
        )

        actual_path = _reply_object_path(reply)

        if actual_path is None:
            self._fail(
                _reply_error(
                    reply,
                    "Could not request the global shortcut binding.",
                )
            )
            return

        self._move_request_subscription(
            request_path,
            actual_path,
            "_on_bind_response(uint,QVariantMap)",
            create_request=False,
        )

    def _move_request_subscription(
        self,
        expected_path: str,
        actual_path: str,
        slot: str,
        *,
        create_request: bool,
    ) -> None:
        if expected_path == actual_path:
            return

        self._disconnect_request(
            expected_path,
            slot,
        )

        if not self.bus.connect(
            PORTAL_SERVICE,
            actual_path,
            REQUEST_INTERFACE,
            "Response",
            self,
            _dbus_slot(slot),
        ):
            self._fail(
                "Could not subscribe to the portal request response."
            )
            return

        if create_request:
            self._create_request_path = actual_path
        else:
            self._bind_request_path = actual_path

    def _close_request(
        self,
        path: str | None,
    ) -> None:
        if path is None:
            return

        request = QDBusInterface(
            PORTAL_SERVICE,
            path,
            REQUEST_INTERFACE,
            self.bus,
        )

        if request.isValid():
            request.call("Close")

    def _disconnect_request(
        self,
        path: str | None,
        slot: str,
    ) -> None:
        if path is None:
            return

        self.bus.disconnect(
            PORTAL_SERVICE,
            path,
            REQUEST_INTERFACE,
            "Response",
            self,
            _dbus_slot(slot),
        )

    def _fail(
        self,
        message: str,
    ) -> None:
        callback = self._on_error

        if callback is not None:
            callback(message)


def wayland_global_shortcuts_available() -> bool:
    """Return whether the desktop exposes the GlobalShortcuts portal."""
    bus = QDBusConnection.sessionBus()

    if not bus.isConnected():
        return False

    portal = QDBusInterface(
        PORTAL_SERVICE,
        PORTAL_PATH,
        GLOBAL_SHORTCUTS_INTERFACE,
        bus,
    )

    if not portal.isValid():
        return False

    version = dbus_int(
        read_dbus_property(
            portal,
            "version",
        )
    )

    return version is not None and version >= 1


def _preferred_trigger(
    modifier: str,
    key: str,
) -> str:
    modifier_name = MODIFIER_NAMES.get(modifier)

    if modifier_name is None:
        raise WaylandPortalError(
            f"Unsupported Wayland hotkey modifier: {modifier}."
        )

    normalized_key = key.upper()

    if len(normalized_key) == 1 and "A" <= normalized_key <= "Z":
        key_name = normalized_key.lower()
    elif len(normalized_key) == 1 and "0" <= normalized_key <= "9":
        key_name = normalized_key
    elif (
        normalized_key.startswith("F")
        and normalized_key[1:].isdigit()
        and 1 <= int(normalized_key[1:]) <= 12
    ):
        key_name = normalized_key
    else:
        raise WaylandPortalError(
            f"Unsupported Wayland hotkey key: {key}."
        )

    return f"{modifier_name}+{key_name}"


def _portal_token(
    prefix: str,
) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def _request_path(
    bus: QDBusConnection,
    token: str,
) -> str:
    sender = bus.baseService()

    if sender.startswith(":"):
        sender = sender[1:]

    sender = sender.replace(
        ".",
        "_",
    )

    return (
        "/org/freedesktop/portal/desktop/request/"
        f"{sender}/{token}"
    )


def _reply_object_path(
    reply: QDBusMessage,
) -> str | None:
    if reply.type() == QDBusMessage.MessageType.ErrorMessage:
        return None

    arguments = reply.arguments()

    if not arguments:
        return None

    value = unwrap_dbus_value(
        arguments[0]
    )

    if not isinstance(value, str) or not value.startswith("/"):
        return None

    return value


def _reply_error(
    reply: QDBusMessage,
    fallback: str,
) -> str:
    if reply.type() != QDBusMessage.MessageType.ErrorMessage:
        return fallback

    message = reply.errorMessage().strip()

    if not message:
        return fallback

    return f"{fallback} {message}"


def _mapping_string(
    mapping: Mapping[str, object],
    key: str,
) -> str | None:
    value = unwrap_dbus_value(
        mapping.get(key)
    )

    if not isinstance(value, str) or not value:
        return None

    return value


def _bound_trigger_description(
    results: Mapping[str, object],
    fallback: str,
) -> str:
    shortcuts = unwrap_dbus_value(
        results.get("shortcuts")
    )

    if not isinstance(
        shortcuts,
        Sequence,
    ) or isinstance(
        shortcuts,
        (str, bytes, bytearray),
    ):
        return fallback

    for shortcut in shortcuts:
        if not isinstance(
            shortcut,
            Sequence,
        ) or isinstance(
            shortcut,
            (str, bytes, bytearray),
        ) or len(shortcut) < 2:
            continue

        shortcut_id = unwrap_dbus_value(
            shortcut[0]
        )

        if shortcut_id != SHORTCUT_ID:
            continue

        details = unwrap_dbus_value(
            shortcut[1]
        )

        if not isinstance(
            details,
            Mapping,
        ):
            return fallback

        description = _mapping_string(
            details,
            "trigger_description",
        )

        return description or fallback

    return fallback


def _portal_response_error(
    response: int,
    operation: str,
) -> str:
    if response == 1:
        return f"{operation} was cancelled."

    return f"{operation} failed (portal response {response})."

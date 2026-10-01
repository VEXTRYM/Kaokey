from collections.abc import Sequence

from PySide6.QtDBus import (
    QDBusArgument,
    QDBusConnection,
    QDBusInterface,
    QDBusMessage,
    QDBusObjectPath,
    QDBusVariant,
)

A11Y_BUS_SERVICE = "org.a11y.Bus"
A11Y_BUS_PATH = "/org/a11y/bus"
A11Y_BUS_INTERFACE = "org.a11y.Bus"


def connect_accessibility_bus(
    connection_name: str,
) -> QDBusConnection | None:
    """Connect to the private AT-SPI accessibility bus."""
    session_bus = QDBusConnection.sessionBus()

    if not session_bus.isConnected():
        return None

    bus_interface = QDBusInterface(
        A11Y_BUS_SERVICE,
        A11Y_BUS_PATH,
        A11Y_BUS_INTERFACE,
        session_bus,
    )

    arguments = call_dbus(
        bus_interface,
        "GetAddress",
    )

    if not arguments:
        return None

    address = unwrap_dbus_value(arguments[0])

    if not isinstance(address, str) or not address:
        return None

    connection = QDBusConnection.connectToBus(
        address,
        connection_name,
    )

    if not connection.isConnected():
        return None

    return connection


def call_dbus(
    interface: QDBusInterface,
    method: str,
    *arguments: object,
) -> tuple[object, ...] | None:
    """Call a D-Bus method and return decoded top-level arguments."""
    if not interface.isValid():
        return None

    reply = interface.call(
        method,
        *arguments,
    )

    if reply.type() == QDBusMessage.MessageType.ErrorMessage:
        return None

    return tuple(
        unwrap_dbus_value(value)
        for value in reply.arguments()
    )


def read_dbus_property(
    interface: QDBusInterface,
    name: str,
) -> object | None:
    """Read a property exposed by a dynamic D-Bus interface."""
    if not interface.isValid():
        return None

    return unwrap_dbus_value(
        interface.property(name)
    )


def unwrap_dbus_value(
    value: object,
) -> object:
    """Remove Qt wrappers around primitive D-Bus values."""
    while isinstance(
        value,
        QDBusVariant,
    ):
        value = value.variant()

    if isinstance(
        value,
        QDBusObjectPath,
    ):
        return value.path()

    return value

def dbus_int(
    value: object,
) -> int | None:
    """Return a D-Bus integer after unwrapping Qt wrappers."""
    value = unwrap_dbus_value(value)

    if isinstance(
        value,
        int,
    ):
        return value

    return None


def decode_object_references(
    value: object,
) -> tuple[tuple[str, str], ...]:
    """Decode an AT-SPI a(so) value into service/path pairs."""
    if isinstance(
        value,
        QDBusArgument,
    ):
        return _decode_object_reference_argument(value)

    if not isinstance(
        value,
        Sequence,
    ) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return ()

    references: list[tuple[str, str]] = []

    for item in value:
        reference = _decode_object_reference(item)

        if reference is not None:
            references.append(reference)

    return tuple(references)


def decode_int_array(
    value: object,
) -> tuple[int, ...]:
    """Decode a D-Bus integer array."""
    if isinstance(
        value,
        QDBusArgument,
    ):
        argument = QDBusArgument(value)
        result: list[int] = []

        argument.beginArray()

        while not argument.atEnd():
            item = unwrap_dbus_value(
                argument.asVariant()
            )

            number = dbus_int(item)

            if number is not None:
                result.append(number)

        argument.endArray()

        return tuple(result)

    if isinstance(
        value,
        Sequence,
    ) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        result = []

        for item in value:
            number = dbus_int(item)

            if number is not None:
                result.append(number)

        return tuple(result)

    return ()


def decode_string_array(
    value: object,
) -> tuple[str, ...]:
    """Decode a D-Bus string array."""
    if isinstance(
        value,
        QDBusArgument,
    ):
        argument = QDBusArgument(value)
        result: list[str] = []

        argument.beginArray()

        while not argument.atEnd():
            item = unwrap_dbus_value(
                argument.asVariant()
            )

            if isinstance(item, str):
                result.append(item)

        argument.endArray()

        return tuple(result)

    if isinstance(
        value,
        Sequence,
    ) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return tuple(
            item
            for item in (
                unwrap_dbus_value(value_item)
                for value_item in value
            )
            if isinstance(item, str)
        )

    return ()


def _decode_object_reference_argument(
    value: QDBusArgument,
) -> tuple[tuple[str, str], ...]:
    argument = QDBusArgument(value)
    references: list[tuple[str, str]] = []

    argument.beginArray()

    while not argument.atEnd():
        argument.beginStructure()

        service = unwrap_dbus_value(
            argument.asVariant()
        )
        object_path = unwrap_dbus_value(
            argument.asVariant()
        )

        argument.endStructure()

        reference = _normalize_object_reference(
            service,
            object_path,
        )

        if reference is not None:
            references.append(reference)

    argument.endArray()

    return tuple(references)


def _decode_object_reference(
    value: object,
) -> tuple[str, str] | None:
    if isinstance(
        value,
        QDBusArgument,
    ):
        argument = QDBusArgument(value)

        argument.beginStructure()

        service = unwrap_dbus_value(
            argument.asVariant()
        )
        object_path = unwrap_dbus_value(
            argument.asVariant()
        )

        argument.endStructure()

        return _normalize_object_reference(
            service,
            object_path,
        )

    if isinstance(
        value,
        Sequence,
    ) and not isinstance(
        value,
        (str, bytes, bytearray),
    ) and len(value) >= 2:
        return _normalize_object_reference(
            unwrap_dbus_value(value[0]),
            unwrap_dbus_value(value[1]),
        )

    return None


def _normalize_object_reference(
    service: object,
    object_path: object,
) -> tuple[str, str] | None:
    if not isinstance(service, str):
        return None

    if isinstance(
        object_path,
        QDBusObjectPath,
    ):
        object_path = object_path.path()

    if not isinstance(object_path, str):
        return None

    if not service or not object_path:
        return None

    return (
        service,
        object_path,
    )

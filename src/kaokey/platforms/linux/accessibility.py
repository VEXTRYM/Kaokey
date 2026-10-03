from collections import deque
from dataclasses import dataclass

from PySide6.QtDBus import (
    QDBusConnection,
    QDBusInterface,
)

from kaokey.platforms.linux.dbus import (
    call_dbus,
    connect_accessibility_bus,
    dbus_int,
    decode_int_array,
    decode_object_references,
    decode_string_array,
    read_dbus_property,
)
from kaokey.ui.popup.popup_positioning import Rect

ATSPI_REGISTRY_SERVICE = "org.a11y.atspi.Registry"
ATSPI_ROOT_PATH = "/org/a11y/atspi/accessible/root"
ATSPI_NULL_PATH = "/org/a11y/atspi/null"

ATSPI_ACCESSIBLE_INTERFACE = "org.a11y.atspi.Accessible"
ATSPI_TEXT_INTERFACE = "org.a11y.atspi.Text"
ATSPI_EDITABLE_TEXT_INTERFACE = "org.a11y.atspi.EditableText"

ATSPI_STATE_ACTIVE = 1
ATSPI_STATE_FOCUSED = 12

ATSPI_COORD_TYPE_SCREEN = 0

MAX_FOCUS_SEARCH_NODES = 512
MAX_FALLBACK_SEARCH_NODES = 256


@dataclass(frozen=True)
class LinuxAccessibleTarget:
    """Stable D-Bus reference to an AT-SPI accessible object."""

    service: str
    object_path: str


class LinuxAccessibility:
    """Shared AT-SPI services for Linux popup backends."""

    def __init__(
        self,
    ) -> None:
        self.connection_name = f"kaokey-atspi-{id(self):x}"
        self.connection = connect_accessibility_bus(
            self.connection_name
        )

    def close(
        self,
    ) -> None:
        if self.connection is None:
            return

        self.connection = None
        QDBusConnection.disconnectFromBus(self.connection_name)

    @property
    def available(
        self,
    ) -> bool:
        connection = self.connection

        if connection is None or not connection.isConnected():
            return False

        root = self._interface(
            LinuxAccessibleTarget(
                ATSPI_REGISTRY_SERVICE,
                ATSPI_ROOT_PATH,
            ),
            ATSPI_ACCESSIBLE_INTERFACE,
        )

        return root is not None and root.isValid()

    def capture_target(
        self,
    ) -> LinuxAccessibleTarget | None:
        """Find the accessible object that currently owns keyboard focus."""
        if not self.available:
            return None

        root = LinuxAccessibleTarget(
            ATSPI_REGISTRY_SERVICE,
            ATSPI_ROOT_PATH,
        )

        applications = self._children(root)

        if not applications:
            return None

        active_roots: list[LinuxAccessibleTarget] = []
        fallback_roots: list[LinuxAccessibleTarget] = []

        for application in applications:
            application_states = self._state_words(application)

            if _state_enabled(
                application_states,
                ATSPI_STATE_FOCUSED,
            ):
                return application

            top_levels = self._children(application)

            if not top_levels:
                fallback_roots.append(application)
                continue

            fallback_roots.extend(top_levels)

            for top_level in top_levels:
                states = self._state_words(top_level)

                if _state_enabled(
                    states,
                    ATSPI_STATE_FOCUSED,
                ):
                    return top_level

                if _state_enabled(
                    states,
                    ATSPI_STATE_ACTIVE,
                ):
                    active_roots.append(top_level)

        if active_roots:
            target = self._find_focused(
                active_roots,
                MAX_FOCUS_SEARCH_NODES,
            )

            if target is not None:
                return target

        return self._find_focused(
            fallback_roots or list(applications),
            MAX_FALLBACK_SEARCH_NODES,
        )

    def caret_rect(
        self,
        target: LinuxAccessibleTarget,
    ) -> Rect | None:
        """Return the text caret in AT-SPI screen coordinates."""
        interfaces = self._interfaces(target)

        if not _supports_interface(
            interfaces,
            ATSPI_TEXT_INTERFACE,
        ):
            return None

        text_interface = self._interface(
            target,
            ATSPI_TEXT_INTERFACE,
        )

        if text_interface is None:
            return None

        caret_offset = self._caret_offset(
            text_interface
        )

        if caret_offset is None:
            return None

        current_rect = self._text_extents(
            text_interface,
            "GetCharacterExtents",
            caret_offset,
        )

        if current_rect is not None:
            return Rect(
                current_rect.x,
                current_rect.y,
                1,
                max(
                    current_rect.height,
                    1,
                ),
            )

        if caret_offset > 0:
            previous_rect = self._text_extents(
                text_interface,
                "GetCharacterExtents",
                caret_offset - 1,
            )

            if previous_rect is not None:
                return Rect(
                    previous_rect.right,
                    previous_rect.y,
                    1,
                    max(
                        previous_rect.height,
                        1,
                    ),
                )

        range_rect = self._text_extents(
            text_interface,
            "GetRangeExtents",
            caret_offset,
            caret_offset,
        )

        if range_rect is None:
            return None

        return Rect(
            range_rect.x,
            range_rect.y,
            max(
                range_rect.width,
                1,
            ),
            max(
                range_rect.height,
                1,
            ),
        )

    def insert_text(
        self,
        target: LinuxAccessibleTarget,
        text: str,
    ) -> bool:
        """Insert text through AT-SPI EditableText without moving focus."""
        if not text:
            return True

        interfaces = self._interfaces(target)

        if not _supports_interface(
            interfaces,
            ATSPI_TEXT_INTERFACE,
        ) or not _supports_interface(
            interfaces,
            ATSPI_EDITABLE_TEXT_INTERFACE,
        ):
            return False

        text_interface = self._interface(
            target,
            ATSPI_TEXT_INTERFACE,
        )
        editable_interface = self._interface(
            target,
            ATSPI_EDITABLE_TEXT_INTERFACE,
        )

        if text_interface is None or editable_interface is None:
            return False

        caret_offset = self._caret_offset(
            text_interface
        )

        if caret_offset is None:
            return False

        result = call_dbus(
            editable_interface,
            "InsertText",
            caret_offset,
            text,
            len(
                text.encode("utf-8")
            ),
        )

        if not result or not bool(result[0]):
            return False

        call_dbus(
            text_interface,
            "SetCaretOffset",
            caret_offset + len(text),
        )

        return True

    def _find_focused(
        self,
        roots: list[LinuxAccessibleTarget],
        max_nodes: int,
    ) -> LinuxAccessibleTarget | None:
        queue = deque(roots)
        visited: set[LinuxAccessibleTarget] = set()
        visited_count = 0

        while queue and visited_count < max_nodes:
            target = queue.popleft()

            if target in visited:
                continue

            visited.add(target)
            visited_count += 1

            if _state_enabled(
                self._state_words(target),
                ATSPI_STATE_FOCUSED,
            ):
                return target

            queue.extend(
                child
                for child in self._children(target)
                if child not in visited
            )

        return None

    def _children(
        self,
        target: LinuxAccessibleTarget,
    ) -> tuple[LinuxAccessibleTarget, ...]:
        interface = self._interface(
            target,
            ATSPI_ACCESSIBLE_INTERFACE,
        )

        if interface is None:
            return ()

        result = call_dbus(
            interface,
            "GetChildren",
        )

        if not result:
            return ()

        return tuple(
            LinuxAccessibleTarget(
                service,
                object_path,
            )
            for service, object_path in decode_object_references(
                result[0]
            )
            if object_path != ATSPI_NULL_PATH
        )

    def _state_words(
        self,
        target: LinuxAccessibleTarget,
    ) -> tuple[int, ...]:
        interface = self._interface(
            target,
            ATSPI_ACCESSIBLE_INTERFACE,
        )

        if interface is None:
            return ()

        result = call_dbus(
            interface,
            "GetState",
        )

        if not result:
            return ()

        return decode_int_array(
            result[0]
        )

    def _interfaces(
        self,
        target: LinuxAccessibleTarget,
    ) -> tuple[str, ...]:
        interface = self._interface(
            target,
            ATSPI_ACCESSIBLE_INTERFACE,
        )

        if interface is None:
            return ()

        result = call_dbus(
            interface,
            "GetInterfaces",
        )

        if not result:
            return ()

        return decode_string_array(
            result[0]
        )

    def _interface(
        self,
        target: LinuxAccessibleTarget,
        interface_name: str,
    ) -> QDBusInterface | None:
        connection = self.connection

        if connection is None or not connection.isConnected():
            return None

        return QDBusInterface(
            target.service,
            target.object_path,
            interface_name,
            connection,
        )

    @staticmethod
    def _caret_offset(
        text_interface: QDBusInterface,
    ) -> int | None:
        value = read_dbus_property(
            text_interface,
            "CaretOffset",
        )

        offset = dbus_int(value)

        if offset is None:
            return None

        if offset < 0:
            return None

        return offset

    @staticmethod
    def _text_extents(
        text_interface: QDBusInterface,
        method: str,
        start_offset: int,
        end_offset: int | None = None,
    ) -> Rect | None:
        arguments: tuple[object, ...]

        if end_offset is None:
            arguments = (
                start_offset,
                ATSPI_COORD_TYPE_SCREEN,
            )
        else:
            arguments = (
                start_offset,
                end_offset,
                ATSPI_COORD_TYPE_SCREEN,
            )

        result = call_dbus(
            text_interface,
            method,
            *arguments,
        )

        if result is None or len(result) < 4:
            return None

        x = dbus_int(result[0])
        y = dbus_int(result[1])
        width = dbus_int(result[2])
        height = dbus_int(result[3])

        if (
            x is None
            or y is None
            or width is None
            or height is None
        ):
            return None

        if x < 0 or y < 0 or width < 0 or height < 0:
            return None

        return Rect(
            x,
            y,
            width,
            height,
        )


def _state_enabled(
    state_words: tuple[int, ...],
    state: int,
) -> bool:
    word_index = state // 32
    bit_index = state % 32

    if word_index >= len(state_words):
        return False

    return bool(
        state_words[word_index]
        & (1 << bit_index)
    )


def _supports_interface(
    interfaces: tuple[str, ...],
    interface_name: str,
) -> bool:
    short_name = interface_name.rsplit(
        ".",
        1,
    )[-1]

    return any(
        name == interface_name
        or name.rsplit(
            ".",
            1,
        )[-1]
        == short_name
        for name in interfaces
    )

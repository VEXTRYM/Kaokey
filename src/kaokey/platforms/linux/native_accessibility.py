import ctypes
import ctypes.util
import os
import threading
from collections import deque

from PySide6.QtDBus import (
    QDBusConnection,
    QDBusInterface,
)

from kaokey.platforms.linux.dbus import (
    A11Y_BUS_INTERFACE,
    A11Y_BUS_PATH,
    A11Y_BUS_SERVICE,
    call_dbus,
    unwrap_dbus_value,
)
from kaokey.ui.popup.popup_positioning import Rect

ATSPI_STATE_FOCUSED = 12
ATSPI_COORD_TYPE_SCREEN = 0

MAX_FOCUS_SEARCH_NODES = 768
MAX_CHILDREN_PER_NODE = 512
ATSPI_METHOD_TIMEOUT_MS = 350
ATSPI_STARTUP_TIMEOUT_MS = 1000


class _AtspiRect(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("width", ctypes.c_int),
        ("height", ctypes.c_int),
    ]


class _AtspiLibrary:
    """Small ctypes wrapper around libatspi used by the Linux popup backend."""

    def __init__(self, bus_address: str) -> None:
        atspi_name = ctypes.util.find_library("atspi") or "libatspi.so.0"
        gobject_name = (
            ctypes.util.find_library("gobject-2.0") or "libgobject-2.0.so.0"
        )
        glib_name = ctypes.util.find_library("glib-2.0") or "libglib-2.0.so.0"

        self.atspi = ctypes.CDLL(atspi_name)
        self.gobject = ctypes.CDLL(gobject_name)
        self.glib = ctypes.CDLL(glib_name)

        self._configure_signatures()

        # Kaokey only performs bounded, on-demand accessibility reads. Avoid
        # libatspi's process-wide cache because not every provider exports the
        # optional /org/a11y/atspi/cache object. Without this, libatspi/dbind
        # emits a GetItems warning whenever such an application appears.
        os.environ["ATSPI_NO_CACHE"] = "1"

        # Newer libatspi releases can also skip optional per-application P2P
        # probing. Older releases ignore this environment variable.
        os.environ["ATSPI_DISABLE_P2P"] = "1"

        # The session bus already returned the authoritative AT-SPI address.
        os.environ["AT_SPI_BUS_ADDRESS"] = bus_address
        self.atspi.atspi_init()

        is_initialized = getattr(self.atspi, "atspi_is_initialized", None)

        if is_initialized is not None and not bool(is_initialized()):
            raise OSError("AT-SPI could not be initialized.")

        set_timeout = getattr(self.atspi, "atspi_set_timeout", None)

        if set_timeout is not None:
            set_timeout(
                ATSPI_METHOD_TIMEOUT_MS,
                ATSPI_STARTUP_TIMEOUT_MS,
            )

    def _configure_signatures(self) -> None:
        atspi = self.atspi

        atspi.atspi_init.argtypes = []
        atspi.atspi_init.restype = ctypes.c_int

        is_initialized = getattr(atspi, "atspi_is_initialized", None)

        if is_initialized is not None:
            is_initialized.argtypes = []
            is_initialized.restype = ctypes.c_int

        set_timeout = getattr(atspi, "atspi_set_timeout", None)

        if set_timeout is not None:
            set_timeout.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
            ]
            set_timeout.restype = None

        atspi.atspi_get_desktop.argtypes = [ctypes.c_int]
        atspi.atspi_get_desktop.restype = ctypes.c_void_p

        atspi.atspi_accessible_get_child_count.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        atspi.atspi_accessible_get_child_count.restype = ctypes.c_int

        atspi.atspi_accessible_get_child_at_index.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
        ]
        atspi.atspi_accessible_get_child_at_index.restype = ctypes.c_void_p

        atspi.atspi_accessible_get_state_set.argtypes = [ctypes.c_void_p]
        atspi.atspi_accessible_get_state_set.restype = ctypes.c_void_p

        atspi.atspi_state_set_contains.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        atspi.atspi_state_set_contains.restype = ctypes.c_int

        atspi.atspi_accessible_get_text_iface.argtypes = [ctypes.c_void_p]
        atspi.atspi_accessible_get_text_iface.restype = ctypes.c_void_p

        atspi.atspi_accessible_get_editable_text_iface.argtypes = [
            ctypes.c_void_p
        ]
        atspi.atspi_accessible_get_editable_text_iface.restype = ctypes.c_void_p

        atspi.atspi_text_get_caret_offset.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        atspi.atspi_text_get_caret_offset.restype = ctypes.c_int

        atspi.atspi_text_get_character_extents.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_void_p,
        ]
        atspi.atspi_text_get_character_extents.restype = ctypes.POINTER(
            _AtspiRect
        )

        atspi.atspi_text_get_range_extents.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_void_p,
        ]
        atspi.atspi_text_get_range_extents.restype = ctypes.POINTER(
            _AtspiRect
        )

        atspi.atspi_editable_text_insert_text.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_void_p,
        ]
        atspi.atspi_editable_text_insert_text.restype = ctypes.c_int

        atspi.atspi_text_set_caret_offset.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
        ]
        atspi.atspi_text_set_caret_offset.restype = ctypes.c_int

        self.gobject.g_object_unref.argtypes = [ctypes.c_void_p]
        self.gobject.g_object_unref.restype = None

        self.glib.g_free.argtypes = [ctypes.c_void_p]
        self.glib.g_free.restype = None

    def unref(self, pointer: int | None) -> None:
        if pointer:
            self.gobject.g_object_unref(ctypes.c_void_p(pointer))

    def free(self, pointer: object) -> None:
        if pointer:
            self.glib.g_free(ctypes.cast(pointer, ctypes.c_void_p))

    def desktop(self) -> int | None:
        pointer = self.atspi.atspi_get_desktop(0)
        return int(pointer) if pointer else None

    def child_count(self, pointer: int) -> int:
        return int(
            self.atspi.atspi_accessible_get_child_count(
                ctypes.c_void_p(pointer),
                None,
            )
        )

    def child_at(self, pointer: int, index: int) -> int | None:
        child = self.atspi.atspi_accessible_get_child_at_index(
            ctypes.c_void_p(pointer),
            index,
            None,
        )
        return int(child) if child else None

    def state_enabled(self, pointer: int, state: int) -> bool:
        state_set = self.atspi.atspi_accessible_get_state_set(
            ctypes.c_void_p(pointer)
        )

        if not state_set:
            return False

        try:
            return bool(
                self.atspi.atspi_state_set_contains(
                    state_set,
                    state,
                )
            )
        finally:
            self.unref(int(state_set))

    def text_interface(self, pointer: int) -> int | None:
        interface = self.atspi.atspi_accessible_get_text_iface(
            ctypes.c_void_p(pointer)
        )
        return int(interface) if interface else None

    def editable_text_interface(self, pointer: int) -> int | None:
        interface = self.atspi.atspi_accessible_get_editable_text_iface(
            ctypes.c_void_p(pointer)
        )
        return int(interface) if interface else None

    def caret_offset(self, text_interface: int) -> int | None:
        offset = int(
            self.atspi.atspi_text_get_caret_offset(
                ctypes.c_void_p(text_interface),
                None,
            )
        )
        return offset if offset >= 0 else None

    def character_extents(
        self,
        text_interface: int,
        offset: int,
    ) -> Rect | None:
        result = self.atspi.atspi_text_get_character_extents(
            ctypes.c_void_p(text_interface),
            offset,
            ATSPI_COORD_TYPE_SCREEN,
            None,
        )
        return self._consume_rect(result)

    def range_extents(
        self,
        text_interface: int,
        start_offset: int,
        end_offset: int,
    ) -> Rect | None:
        result = self.atspi.atspi_text_get_range_extents(
            ctypes.c_void_p(text_interface),
            start_offset,
            end_offset,
            ATSPI_COORD_TYPE_SCREEN,
            None,
        )
        return self._consume_rect(result)

    def insert_text(
        self,
        editable_interface: int,
        position: int,
        text: str,
    ) -> bool:
        encoded = text.encode("utf-8")

        return bool(
            self.atspi.atspi_editable_text_insert_text(
                ctypes.c_void_p(editable_interface),
                position,
                encoded,
                len(encoded),
                None,
            )
        )

    def set_caret_offset(
        self,
        text_interface: int,
        offset: int,
    ) -> bool:
        return bool(
            self.atspi.atspi_text_set_caret_offset(
                ctypes.c_void_p(text_interface),
                offset,
                None,
            )
        )

    def _consume_rect(
        self,
        result: ctypes.POINTER(_AtspiRect),
    ) -> Rect | None:
        if not result:
            return None

        try:
            value = result.contents
            rect = Rect(
                value.x,
                value.y,
                value.width,
                value.height,
            )
        finally:
            self.free(result)

        if (
            rect.x < 0
            or rect.y < 0
            or rect.width < 0
            or rect.height < 0
        ):
            return None

        return rect



def _accessibility_bus_address() -> str | None:
    """Resolve the private AT-SPI bus without decoding compound D-Bus types."""
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

    return address

_ATSPI_LIBRARY: _AtspiLibrary | None = None
_ATSPI_LOAD_ATTEMPTED = False
_ATSPI_LOAD_LOCK = threading.Lock()
_ATSPI_CALL_LOCK = threading.RLock()


def _load_atspi() -> _AtspiLibrary | None:
    global _ATSPI_LIBRARY, _ATSPI_LOAD_ATTEMPTED

    if _ATSPI_LOAD_ATTEMPTED:
        return _ATSPI_LIBRARY

    with _ATSPI_LOAD_LOCK:
        if _ATSPI_LOAD_ATTEMPTED:
            return _ATSPI_LIBRARY

        bus_address = _accessibility_bus_address()

        if bus_address is None:
            _ATSPI_LOAD_ATTEMPTED = True
            return None

        try:
            _ATSPI_LIBRARY = _AtspiLibrary(bus_address)
        except (OSError, AttributeError):
            _ATSPI_LIBRARY = None

        _ATSPI_LOAD_ATTEMPTED = True
        return _ATSPI_LIBRARY


class LinuxAccessibleTarget:
    """Owned libatspi reference to the accessible that held keyboard focus."""

    __slots__ = ("pointer", "_library")

    def __init__(
        self,
        pointer: int,
        library: _AtspiLibrary,
    ) -> None:
        self.pointer = pointer
        self._library = library

    def close(self) -> None:
        pointer = self.pointer

        if pointer <= 0:
            return

        self.pointer = 0

        try:
            with _ATSPI_CALL_LOCK:
                self._library.unref(pointer)
        except Exception:
            # Interpreter shutdown can tear down ctypes objects out of order.
            pass

    def __del__(self) -> None:
        self.close()


class LinuxAccessibility:
    """AT-SPI services implemented through libatspi rather than QtDBus."""

    def __init__(self) -> None:
        self.library = _load_atspi()

    def close(self) -> None:
        # libatspi owns one process-wide connection. It is intentionally kept
        # initialized for the lifetime of Kaokey and shared by worker objects.
        return

    @property
    def available(self) -> bool:
        return self.library is not None

    def capture_target(self) -> LinuxAccessibleTarget | None:
        """Find the focused accessible without demarshalling QDBusArgument."""
        library = self.library

        if library is None:
            return None

        with _ATSPI_CALL_LOCK:
            desktop = library.desktop()

            if desktop is None:
                return None

            queue = deque([desktop])
            owned = {desktop}
            focused_fallback: int | None = None
            selected: int | None = None
            visited_count = 0

            try:
                while queue and visited_count < MAX_FOCUS_SEARCH_NODES:
                    pointer = queue.popleft()
                    visited_count += 1

                    if library.state_enabled(
                        pointer,
                        ATSPI_STATE_FOCUSED,
                    ):
                        text_interface = library.text_interface(pointer)

                        if text_interface is not None:
                            library.unref(text_interface)
                            selected = pointer
                            break

                        if focused_fallback is None:
                            focused_fallback = pointer

                    child_count = library.child_count(pointer)

                    if child_count <= 0:
                        continue

                    child_count = min(
                        child_count,
                        MAX_CHILDREN_PER_NODE,
                    )

                    for index in range(child_count):
                        child = library.child_at(pointer, index)

                        if child is None:
                            continue

                        if child in owned:
                            library.unref(child)
                            continue

                        owned.add(child)
                        queue.append(child)

                if selected is None:
                    selected = focused_fallback

                if selected is None:
                    return None

                owned.remove(selected)
                return LinuxAccessibleTarget(
                    selected,
                    library,
                )
            finally:
                for pointer in owned:
                    library.unref(pointer)

    def caret_rect(
        self,
        target: LinuxAccessibleTarget,
    ) -> Rect | None:
        library = self.library

        if library is None or target.pointer <= 0:
            return None

        with _ATSPI_CALL_LOCK:
            text_interface = library.text_interface(target.pointer)

            if text_interface is None:
                return None

            try:
                caret_offset = library.caret_offset(text_interface)

                if caret_offset is None:
                    return None

                current_rect = library.character_extents(
                    text_interface,
                    caret_offset,
                )

                if current_rect is not None:
                    return Rect(
                        current_rect.x,
                        current_rect.y,
                        1,
                        max(current_rect.height, 1),
                    )

                if caret_offset > 0:
                    previous_rect = library.character_extents(
                        text_interface,
                        caret_offset - 1,
                    )

                    if previous_rect is not None:
                        return Rect(
                            previous_rect.right,
                            previous_rect.y,
                            1,
                            max(previous_rect.height, 1),
                        )

                range_rect = library.range_extents(
                    text_interface,
                    caret_offset,
                    caret_offset,
                )

                if range_rect is None:
                    return None

                return Rect(
                    range_rect.x,
                    range_rect.y,
                    max(range_rect.width, 1),
                    max(range_rect.height, 1),
                )
            finally:
                library.unref(text_interface)

    def insert_text(
        self,
        target: LinuxAccessibleTarget,
        text: str,
    ) -> bool:
        """Insert text through libatspi's EditableText interface."""
        if not text:
            return True

        library = self.library

        if library is None or target.pointer <= 0:
            return False

        with _ATSPI_CALL_LOCK:
            text_interface = library.text_interface(target.pointer)
            editable_interface = library.editable_text_interface(target.pointer)

            if text_interface is None or editable_interface is None:
                library.unref(text_interface)
                library.unref(editable_interface)
                return False

            try:
                caret_offset = library.caret_offset(text_interface)

                if caret_offset is None:
                    return False

                if not library.insert_text(
                    editable_interface,
                    caret_offset,
                    text,
                ):
                    return False

                library.set_caret_offset(
                    text_interface,
                    caret_offset + len(text),
                )
                return True
            finally:
                library.unref(text_interface)
                library.unref(editable_interface)

import ctypes
import ctypes.util
import os
import threading
import time
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

ATSPI_STATE_ACTIVE = 1
ATSPI_STATE_EDITABLE = 7
ATSPI_STATE_FOCUSED = 12
ATSPI_STATE_SHOWING = 25
ATSPI_COORD_TYPE_SCREEN = 0

# Mousepad has a small accessibility tree. Do not scan the entire desktop;
# a 500ms popup timeout makes large AT-SPI traversals counterproductive.
MAX_FOCUS_SEARCH_NODES = 96
MAX_CARET_SEARCH_SECONDS = 0.35
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

        atspi.atspi_accessible_get_name.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p,
        ]
        atspi.atspi_accessible_get_name.restype = ctypes.c_void_p

        atspi.atspi_accessible_get_process_id.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p,
        ]
        atspi.atspi_accessible_get_process_id.restype = ctypes.c_uint

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

        atspi.atspi_text_get_character_count.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        atspi.atspi_text_get_character_count.restype = ctypes.c_int

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

    def accessible_name(self, pointer: int) -> str:
        """Application name for opt-in troubleshooting only."""
        result = self.atspi.atspi_accessible_get_name(
            ctypes.c_void_p(pointer), None
        )

        if not result:
            return "?"

        try:
            return ctypes.string_at(result).decode("utf-8", errors="replace")
        finally:
            self.glib.g_free(ctypes.c_void_p(result))

    def process_id(self, pointer: int) -> int | None:
        value = int(self.atspi.atspi_accessible_get_process_id(
            ctypes.c_void_p(pointer), None
        ))
        return value if 0 < value < 0xFFFFFFFF else None

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

    def character_count(self, text_interface: int) -> int:
        return int(
            self.atspi.atspi_text_get_character_count(
                ctypes.c_void_p(text_interface),
                None,
            )
        )

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

        # X11 monitors can have negative desktop coordinates when arranged
        # left of or above the primary display.
        if rect.width < 0 or rect.height < 0:
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
        self.capture_diagnostics = "not started"

    def close(self) -> None:
        # libatspi owns one process-wide connection. It is intentionally kept
        # initialized for the lifetime of Kaokey and shared by worker objects.
        return

    @property
    def available(self) -> bool:
        return self.library is not None

    def capture_target(
        self,
        preferred_pid: int | None = None,
    ) -> LinuxAccessibleTarget | None:
        """Search only the active X11 application's AT-SPI subtree.

        A global breadth-first desktop search regularly exceeds the popup
        timeout on XFCE. Restrict the search to the application matching the
        X11 window's PID; use an ACTIVE-window fallback if PID is missing.
        """
        library = self.library

        if library is None:
            self.capture_diagnostics = "AT-SPI library unavailable"
            return None

        with _ATSPI_CALL_LOCK:
            started = time.monotonic()
            deadline = started + MAX_CARET_SEARCH_SECONDS
            desktop = library.desktop()

            if desktop is None:
                self.capture_diagnostics = "AT-SPI desktop unavailable"
                return None

            owned = {desktop}
            child_cache: dict[int, tuple[int, ...]] = {}
            visited: set[int] = set()
            applications: tuple[int, ...] = ()
            matched_apps: list[int] = []
            active_windows: list[int] = []
            focused_without_text = 0
            editable_candidates: list[int] = []
            selected_name = "none"
            status = "no focused text"

            def children(pointer: int) -> tuple[int, ...]:
                cached = child_cache.get(pointer)

                if cached is not None:
                    return cached

                count = min(
                    max(library.child_count(pointer), 0),
                    MAX_CHILDREN_PER_NODE,
                )
                result: list[int] = []
                seen: set[int] = set()

                for index in range(count):
                    child = library.child_at(pointer, index)

                    if child is None:
                        continue

                    if child in owned:
                        library.unref(child)
                    else:
                        owned.add(child)

                    if child not in seen:
                        seen.add(child)
                        result.append(child)

                child_cache[pointer] = tuple(result)
                return child_cache[pointer]

            try:
                applications = children(desktop)

                if preferred_pid:
                    for application in applications:
                        if time.monotonic() >= deadline:
                            status = "PID lookup timed out"
                            break

                        if library.process_id(application) == preferred_pid:
                            matched_apps.append(application)

                if matched_apps:
                    roots = tuple(matched_apps)
                    selected_name = (
                        library.accessible_name(matched_apps[0])
                        if os.environ.get("KAOKEY_CARET_DEBUG") == "1"
                        else "matched PID"
                    )
                else:
                    # When the window doesn't advertise a PID, use ACTIVE
                    # windows instead of recursively walking 18+ apps.
                    for application in applications:
                        if time.monotonic() >= deadline:
                            break

                        for window in children(application):
                            if library.state_enabled(
                                window, ATSPI_STATE_ACTIVE
                            ):
                                active_windows.append(window)

                    roots = tuple(active_windows)

                queue = deque(roots)

                while (
                    queue
                    and len(visited) < MAX_FOCUS_SEARCH_NODES
                    and time.monotonic() < deadline
                ):
                    pointer = queue.popleft()

                    if pointer in visited:
                        continue

                    visited.add(pointer)
                    focused = library.state_enabled(
                        pointer, ATSPI_STATE_FOCUSED
                    )
                    editable = library.state_enabled(
                        pointer, ATSPI_STATE_EDITABLE
                    )

                    if not focused and not editable:
                        queue.extend(children(pointer))
                        continue

                    text_interface = library.text_interface(pointer)

                    if text_interface is not None:
                        library.unref(text_interface)

                        if focused:
                            status = "focused text found"
                            owned.remove(pointer)
                            return LinuxAccessibleTarget(pointer, library)

                        if (
                            editable
                            and library.state_enabled(
                                pointer, ATSPI_STATE_SHOWING
                            )
                        ):
                            editable_candidates.append(pointer)
                    elif focused:
                        focused_without_text += 1

                    queue.extend(children(pointer))

                if len(editable_candidates) == 1:
                    # GtkSourceView can expose the caret on its unique
                    # editable text area without setting FOCUSED on that node.
                    pointer = editable_candidates[0]
                    status = "unique editable text fallback"
                    owned.remove(pointer)
                    return LinuxAccessibleTarget(pointer, library)

                status = (
                    "search deadline" if time.monotonic() >= deadline
                    else "no unambiguous focused text"
                )
                return None
            finally:
                self.capture_diagnostics = (
                    f"target_pid={preferred_pid}, app={selected_name}, "
                    f"apps={len(applications)}, pid_matches={len(matched_apps)}, "
                    f"active_windows={len(active_windows)}, "
                    f"visited={len(visited)}, "
                    f"focused_without_text={focused_without_text}, "
                    f"editable_candidates={len(editable_candidates)}, "
                    f"search_status={status}"
                )
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

                # GTK editors may expose a caret at character_count, where
                # GetCharacterExtents(caret_offset) is out of range. Try the
                # empty-range caret rectangle, then a neighboring glyph.
                caret_rect = library.range_extents(
                    text_interface, caret_offset, caret_offset
                )

                if caret_rect is not None and caret_rect.height > 0:
                    return Rect(
                        caret_rect.x,
                        caret_rect.y,
                        1,
                        caret_rect.height,
                    )

                count = library.character_count(text_interface)

                if 0 <= caret_offset < count:
                    current_rect = library.character_extents(
                        text_interface, caret_offset
                    )

                    if current_rect is not None and current_rect.height > 0:
                        return Rect(
                            current_rect.x,
                            current_rect.y,
                            1,
                            current_rect.height,
                        )

                if caret_offset > 0:
                    previous_rect = library.character_extents(
                        text_interface, caret_offset - 1
                    )

                    if previous_rect is not None and previous_rect.height > 0:
                        return Rect(
                            previous_rect.right,
                            previous_rect.y,
                            1,
                            previous_rect.height,
                        )

                return None
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

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
LINE_BREAKS = ("\n", "\r", "\u2028", "\u2029")

ATSPI_ROLE_MENU = 33
ATSPI_ROLE_MENU_BAR = 34
ATSPI_ROLE_POPUP_MENU = 41
ATSPI_ROLE_TEXT = 61
ATSPI_ROLE_TOOL_BAR = 63
ATSPI_ROLE_ENTRY = 79

# Exclude unrelated menu trees from the search while Mousepad is editing.
SKIP_CLOSED_MENU_ROLES = {
    ATSPI_ROLE_MENU,
    ATSPI_ROLE_MENU_BAR,
    ATSPI_ROLE_POPUP_MENU,
    ATSPI_ROLE_TOOL_BAR,
}
ATSPI_COORD_TYPE_SCREEN = 0

# Mousepad has a small accessibility tree. Do not scan the entire desktop;
# a 500ms popup timeout makes large AT-SPI traversals counterproductive.
MAX_FOCUS_SEARCH_NODES = 256
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

        atspi.atspi_accessible_get_role.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p,
        ]
        atspi.atspi_accessible_get_role.restype = ctypes.c_int

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

        atspi.atspi_accessible_get_component_iface.argtypes = [
            ctypes.c_void_p,
        ]
        atspi.atspi_accessible_get_component_iface.restype = ctypes.c_void_p

        atspi.atspi_component_get_extents.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
        ]
        atspi.atspi_component_get_extents.restype = ctypes.POINTER(_AtspiRect)

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

        atspi.atspi_text_get_character_at_offset.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
        ]
        atspi.atspi_text_get_character_at_offset.restype = ctypes.c_uint

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

    def role(self, pointer: int) -> int:
        return int(self.atspi.atspi_accessible_get_role(
            ctypes.c_void_p(pointer), None
        ))

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

    def states(self, pointer: int, *states: int) -> tuple[bool, ...]:
        """Read one AT-SPI state snapshot for several local checks.

        Chromium accessibility trees can be large. Calling
        atspi_accessible_get_state_set separately for FOCUSED, EDITABLE and
        SHOWING costs three round trips per visited object.
        """
        state_set = self.atspi.atspi_accessible_get_state_set(
            ctypes.c_void_p(pointer)
        )

        if not state_set:
            return (False,) * len(states)

        try:
            return tuple(
                bool(self.atspi.atspi_state_set_contains(state_set, state))
                for state in states
            )
        finally:
            self.unref(int(state_set))

    def text_interface(self, pointer: int) -> int | None:
        interface = self.atspi.atspi_accessible_get_text_iface(
            ctypes.c_void_p(pointer)
        )
        return int(interface) if interface else None

    def component_extents(self, pointer: int) -> Rect | None:
        """Return the text widget's bounds (not its caret location)."""
        component = self.atspi.atspi_accessible_get_component_iface(
            ctypes.c_void_p(pointer)
        )

        if not component:
            return None

        try:
            rectangle = self.atspi.atspi_component_get_extents(
                ctypes.c_void_p(component),
                ATSPI_COORD_TYPE_SCREEN,
                None,
            )
            return self._consume_rect(rectangle)
        finally:
            self.unref(int(component))

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

    def character_at(self, text_interface: int, offset: int) -> str | None:
        """Read only one Unicode codepoint, not the user's text."""
        if offset < 0:
            return None

        value = int(
            self.atspi.atspi_text_get_character_at_offset(
                ctypes.c_void_p(text_interface),
                offset,
                None,
            )
        )

        if value > 0x10FFFF or 0xD800 <= value <= 0xDFFF:
            return None

        return chr(value)

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

# Remember only an index, never a foreign AT-SPI pointer. On every call the
# index is checked against the application's current PID before use.
_LAST_APP_HINT: tuple[int, int] | None = None


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
        self.caret_diagnostics = "not started"

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
        global _LAST_APP_HINT
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
            focused_invalid_caret = 0
            name_matches = 0
            process_name = ""
            editable_candidates: list[int] = []
            editor_candidates: list[int] = []
            skipped_menus = 0
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
                    hint = _LAST_APP_HINT
                    hint_index = None

                    if hint is not None and hint[0] == preferred_pid:
                        hint_index = hint[1]

                        if 0 <= hint_index < len(applications):
                            candidate = applications[hint_index]

                            if library.process_id(candidate) == preferred_pid:
                                matched_apps.append(candidate)
                                status = "cached PID match"

                    if not matched_apps:
                        for index, application in enumerate(applications):
                            if time.monotonic() >= deadline:
                                status = "PID lookup timed out"
                                break

                            if library.process_id(application) == preferred_pid:
                                matched_apps.append(application)
                                _LAST_APP_HINT = (preferred_pid, index)
                                break

                # Some browsers expose a different AT-SPI process PID than
                # _NET_WM_PID. Use a strict browser-family name match only
                # when the exact PID lookup has failed.
                if not matched_apps and preferred_pid is not None:
                    try:
                        with open(
                            f"/proc/{preferred_pid}/comm",
                            "r",
                            encoding="utf-8",
                        ) as process_file:
                            process_name = process_file.read(128).strip().lower()
                    except OSError:
                        process_name = ""

                    browser_family = None

                    if "firefox" in process_name:
                        browser_family = "firefox"
                    elif "chrome" in process_name:
                        browser_family = "chrome"
                    elif "chromium" in process_name:
                        browser_family = "chromium"
                    elif "discord" in process_name:
                        browser_family = "discord"

                    if browser_family is not None:
                        for app in applications:
                            if time.monotonic() >= deadline:
                                break

                            app_name = library.accessible_name(app).lower()
                            is_match = (
                                browser_family in app_name
                                or (
                                    browser_family in ("chrome", "chromium")
                                    and (
                                        "google chrome" in app_name
                                        or "chromium" in app_name
                                    )
                                )
                            )

                            if is_match:
                                matched_apps.append(app)
                                name_matches += 1

                if matched_apps:
                    roots = tuple(matched_apps)
                    selected_name = (
                        library.accessible_name(matched_apps[0])
                        if os.environ.get("KAOKEY_CARET_DEBUG") == "1"
                        else "matched PID"
                    )
                elif preferred_pid is None:
                    # With no usable X11 PID, the active AT-SPI window is the
                    # best available fallback. Never substitute a different
                    # ACTIVE application when an explicit PID did not match.
                    for application in applications:
                        if time.monotonic() >= deadline:
                            break

                        for window in children(application):
                            if library.state_enabled(
                                window, ATSPI_STATE_ACTIVE
                            ):
                                active_windows.append(window)

                    roots = tuple(active_windows)
                else:
                    roots = ()
                    status = "no matching AT-SPI app for X11 PID"

                # A broad breadth-first walk visited GTK's menus, buttons,
                # and decorations before the nested GtkSourceView text area.
                # With a 500ms popup timeout, explore document branches first.
                stack = list(reversed(roots))

                while (
                    stack
                    and len(visited) < MAX_FOCUS_SEARCH_NODES
                    and time.monotonic() < deadline
                ):
                    pointer = stack.pop()

                    if pointer in visited:
                        continue

                    visited.add(pointer)
                    focused, editable, showing = library.states(
                        pointer,
                        ATSPI_STATE_FOCUSED,
                        ATSPI_STATE_EDITABLE,
                        ATSPI_STATE_SHOWING,
                    )
                    role = library.role(pointer)
                    editor_role = role in (
                        ATSPI_ROLE_TEXT, ATSPI_ROLE_ENTRY
                    )

                    if focused or editable or editor_role:
                        text_interface = library.text_interface(pointer)

                        if text_interface is not None:
                            try:
                                # Chromium may expose a focused document with
                                # Text but without a caret. Do not accept it;
                                # inspect nested inputs/contenteditable instead.
                                offset = library.caret_offset(text_interface)
                            finally:
                                library.unref(text_interface)

                            if offset is None:
                                if focused:
                                    focused_invalid_caret += 1
                            else:
                                if focused:
                                    status = "focused text with valid caret"
                                    owned.remove(pointer)
                                    return LinuxAccessibleTarget(pointer, library)

                                if showing:
                                    if editable:
                                        editable_candidates.append(pointer)
                                    if role == ATSPI_ROLE_TEXT:
                                        editor_candidates.append(pointer)
                        elif focused:
                            focused_without_text += 1

                    # Mousepad's normal text area does not live inside an
                    # open menu or toolbar. Ignore such trees unless they
                    # contain focus, so their many action labels do not use
                    # the entire traversal budget.
                    if role in SKIP_CLOSED_MENU_ROLES and not focused:
                        skipped_menus += 1
                        continue

                    # Depth-first. GTK typically places document content
                    # in the later children of the main window; LIFO visits
                    # those before expanding every toolbar sibling.
                    stack.extend(children(pointer))

                candidate: int | None = None

                if len(editable_candidates) == 1:
                    candidate = editable_candidates[0]
                    status = "unique editable text fallback"
                elif len(editor_candidates) == 1:
                    # GTK's editable state is not consistently exposed by
                    # GtkSourceView; prefer an unambiguous TEXT role.
                    candidate = editor_candidates[0]
                    status = "unique visible text editor fallback"

                if candidate is not None:
                    owned.remove(candidate)
                    return LinuxAccessibleTarget(candidate, library)

                status = (
                    "search deadline" if time.monotonic() >= deadline
                    else "node budget exhausted"
                    if len(visited) >= MAX_FOCUS_SEARCH_NODES
                    else "no unambiguous focused text"
                )
                return None
            finally:
                self.capture_diagnostics = (
                    f"target_pid={preferred_pid}, app={selected_name}, "
                    f"apps={len(applications)}, pid_matches={len(matched_apps) - name_matches}, "
                    f"name_matches={name_matches}, process_name={process_name}, "
                    f"active_windows={len(active_windows)}, "
                    f"visited={len(visited)}, "
                    f"focused_without_text={focused_without_text}, "
                    f"focused_invalid_caret={focused_invalid_caret}, "
                    f"editable_candidates={len(editable_candidates)}, "
                    f"text_roles={len(editor_candidates)}, "
                    f"skipped_menus={skipped_menus}, "
                    f"search_status={status}"
                )
                for pointer in owned:
                    library.unref(pointer)

    def caret_rect(
        self,
        target: LinuxAccessibleTarget,
    ) -> Rect | None:
        """Read caret geometry, treating explicit line breaks separately."""
        library = self.library
        self.caret_diagnostics = "not started"

        if library is None or target.pointer <= 0:
            self.caret_diagnostics = "AT-SPI target unavailable"
            return None

        with _ATSPI_CALL_LOCK:
            text_interface = library.text_interface(target.pointer)

            if text_interface is None:
                self.caret_diagnostics = "target has no Text interface"
                return None

            details: list[str] = []

            def accept(
                rect: Rect | None,
                *,
                at_end: bool = False,
            ) -> Rect | None:
                if (
                    rect is None
                    or rect.height <= 0
                    or (rect.x == 0 and rect.y == 0)
                ):
                    return None

                return Rect(
                    rect.right if at_end else rect.left,
                    rect.top,
                    1,
                    rect.height,
                )

            try:
                caret_offset = library.caret_offset(text_interface)
                details.append(f"offset={caret_offset}")

                if caret_offset is None:
                    details.append("invalid caret offset (-1)")
                    return None

                count = library.character_count(text_interface)
                details.append(f"characters={count}")
                role = library.role(target.pointer)
                editable = library.state_enabled(
                    target.pointer, ATSPI_STATE_EDITABLE
                )
                showing = library.state_enabled(
                    target.pointer, ATSPI_STATE_SHOWING
                )
                focused = library.state_enabled(
                    target.pointer, ATSPI_STATE_FOCUSED
                )
                details.append(
                    f"role={role}, editable={editable}, "
                    f"showing={showing}, focused={focused}"
                )

                if count < 0 or caret_offset > count:
                    details.append("offset outside text length")
                    return None

                # Only read newline markers, never the document's contents.
                previous_char = (
                    library.character_at(text_interface, caret_offset - 1)
                    if caret_offset > 0 else None
                )
                current_char = (
                    library.character_at(text_interface, caret_offset)
                    if caret_offset < count else None
                )
                after_break = previous_char in LINE_BREAKS
                before_break = current_char in LINE_BREAKS
                details.append(
                    f"after_line_break={after_break}, "
                    f"before_line_break={before_break}"
                )

                empty_rect = library.range_extents(
                    text_interface, caret_offset, caret_offset
                )
                details.append(f"empty_range={empty_rect}")
                result = accept(empty_rect)

                if result is not None:
                    details.append("used=empty_range")
                    return result

                # At the start of a line the character provider may return
                # the *previous line's* end geometry (often the newline glyph
                # itself). Do not accept that as the current caret location.
                if after_break:
                    previous_rect = library.character_extents(
                        text_interface, caret_offset - 1
                    )
                    details.append(f"newline_rect={previous_rect}")

                    current_rect = (
                        library.character_extents(
                            text_interface, caret_offset
                        )
                        if caret_offset < count and not before_break
                        else None
                    )
                    details.append(f"new_line_char={current_rect}")

                    if previous_rect is not None and current_rect is not None:
                        if (
                            current_rect.y
                            > previous_rect.y + previous_rect.height // 2
                        ):
                            result = accept(current_rect)

                            if result is not None:
                                details.append("used=new_line_char")
                                return result

                    component = library.component_extents(target.pointer)
                    details.append(f"editor_bounds={component}")

                    if (
                        component is not None
                        and component.width >= 24
                        and component.height >= 24
                        and previous_rect is not None
                        and previous_rect.height > 0
                    ):
                        # An empty line has no glyph. The previous newline's
                        # screen y plus one line-height gives the next row.
                        # The widget's left edge provides an approximate x.
                        next_y = previous_rect.bottom

                        if (
                            component.top <= next_y
                            and next_y + previous_rect.height
                            <= component.bottom + previous_rect.height
                        ):
                            details.append("used=approximate_line_start")
                            return Rect(
                                component.left + 12,
                                next_y,
                                1,
                                previous_rect.height,
                            )

                    details.append("no reliable next-line geometry")
                    return None

                # At the end of the line immediately before an explicit
                # newline, use the preceding printable glyph's right edge,
                # not the newline character's often misleading bounds.
                if before_break and caret_offset > 0:
                    prev_rect = library.character_extents(
                        text_interface, caret_offset - 1
                    )
                    details.append(f"before_newline_previous={prev_rect}")
                    result = accept(prev_rect, at_end=True)

                    if result is not None:
                        details.append("used=before_newline_previous")
                        return result

                if caret_offset < count and not before_break:
                    current = library.character_extents(
                        text_interface, caret_offset
                    )
                    details.append(f"current_char={current}")
                    result = accept(current)

                    if result is not None:
                        details.append("used=current_char")
                        return result

                if caret_offset > 0:
                    previous = library.character_extents(
                        text_interface, caret_offset - 1
                    )
                    details.append(f"previous_char={previous}")
                    result = accept(previous, at_end=True)

                    if result is not None:
                        details.append("used=previous_char")
                        return result

                if caret_offset < count and not before_break:
                    range_rect = library.range_extents(
                        text_interface, caret_offset, caret_offset + 1
                    )
                    details.append(f"next_range={range_rect}")
                    result = accept(range_rect)

                    if result is not None:
                        details.append("used=next_range")
                        return result

                # A genuinely empty editor has no glyphs. Its visible
                # component bounds are a safe approximate first-line anchor.
                if (
                    count == 0
                    and caret_offset == 0
                    and role == ATSPI_ROLE_TEXT
                    and editable
                    and showing
                ):
                    component = library.component_extents(target.pointer)
                    details.append(f"empty_editor_bounds={component}")

                    if (
                        component is not None
                        and component.width >= 24
                        and component.height >= 24
                    ):
                        details.append("used=approximate_empty_editor")
                        return Rect(
                            component.left + 12,
                            component.top + 12,
                            1,
                            16,
                        )

                details.append("no usable text geometry")
                return None
            finally:
                self.caret_diagnostics = "; ".join(details)
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

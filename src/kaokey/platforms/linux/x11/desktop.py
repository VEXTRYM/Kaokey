"""X11 window tracking and Unicode clipboard paste without external commands."""

import ctypes
import ctypes.util
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from PySide6.QtCore import QEventLoop
from PySide6.QtGui import QClipboard, QGuiApplication

from kaokey.platforms.linux.native_accessibility import LinuxAccessibleTarget
from kaokey.platforms.linux.x11.xlib import (
    ATOM,
    DISPLAY,
    PROPERTY_CHANGE_MASK,
    PROP_MODE_REPLACE,
    WINDOW,
    X11Connection,
    XEvent,
    XErrorEvent,
    XErrorHandler,
)
from kaokey.geometry import Rect


@dataclass(frozen=True)
class X11Target:
    window_id: int
    accessible: LinuxAccessibleTarget | None = None


class X11Desktop:
    def __init__(self) -> None:
        self.connection = X11Connection()
        connection = self.connection
        # An unmapped private window supplies PropertyNotify server timestamps
        # for EWMH activation. Wall-clock time is not an X server timestamp.
        self._time_window = int(connection.x11.lib.XCreateSimpleWindow(
            connection.display, connection.root_window, 0, 0, 1, 1, 0, 0, 0,
        ))
        connection.x11.lib.XSelectInput(
            connection.display, self._time_window, PROPERTY_CHANGE_MASK,
        )
        self.xtest = None
        try:
            library = ctypes.util.find_library("Xtst") or "libXtst.so.6"
            xtest = ctypes.CDLL(library)
            xtest.XTestQueryExtension.argtypes = [
                DISPLAY, *([ctypes.POINTER(ctypes.c_int)] * 4),
            ]
            xtest.XTestQueryExtension.restype = ctypes.c_int
            xtest.XTestFakeKeyEvent.argtypes = [
                DISPLAY, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong,
            ]
            xtest.XTestFakeKeyEvent.restype = ctypes.c_int
            values = [ctypes.c_int() for _ in range(4)]
            if xtest.XTestQueryExtension(
                self.connection.display, *(ctypes.byref(value) for value in values)
            ):
                self.xtest = xtest
        except (OSError, AttributeError):
            pass

    def close(self) -> None:
        if self.connection.display and self._time_window:
            self.connection.x11.lib.XDestroyWindow(
                self.connection.display, self._time_window,
            )
            self._time_window = 0
        self.connection.close()

    def server_timestamp(self) -> int:
        connection = self.connection
        value = ctypes.c_ubyte(0)
        connection.x11.lib.XChangeProperty(
            connection.display, self._time_window,
            connection._atom("_KAOKEY_TIMESTAMP"), connection._atom("INTEGER"),
            8, PROP_MODE_REPLACE, ctypes.byref(value), 1,
        )
        event = XEvent()
        connection.x11.lib.XWindowEvent(
            connection.display, self._time_window,
            PROPERTY_CHANGE_MASK, ctypes.byref(event),
        )
        return int(event.xproperty.time)

    @contextmanager
    def _checked(self) -> Iterator[None]:
        """A target can close between capture and insertion; don't let Xlib exit."""
        lib = self.connection.x11.lib
        errors: list[int] = []

        @XErrorHandler
        def handler(_display: DISPLAY, error: ctypes.c_void_p) -> int:
            event = ctypes.cast(error, ctypes.POINTER(XErrorEvent)).contents
            errors.append(int(event.error_code))
            return 0

        previous = lib.XSetErrorHandler(ctypes.cast(handler, ctypes.c_void_p))
        try:
            yield
        finally:
            lib.XSync(self.connection.display, 0)
            lib.XSetErrorHandler(previous)
        if errors:
            raise OSError(f"X11 window is no longer available (error {errors[0]}).")

    def _property(self, window: int, name: str) -> int | None:
        connection = self.connection
        value = ctypes.POINTER(ctypes.c_ubyte)()
        actual_type = ATOM()
        actual_format = ctypes.c_int()
        count = ctypes.c_ulong()
        remaining = ctypes.c_ulong()
        status = connection.x11.lib.XGetWindowProperty(
            connection.display, window, connection._atom(name), 0, 1, 0, 0,
            ctypes.byref(actual_type), ctypes.byref(actual_format),
            ctypes.byref(count), ctypes.byref(remaining), ctypes.byref(value),
        )
        try:
            if status != 0 or actual_format.value != 32 or count.value != 1 or not value:
                return None
            return int(ctypes.cast(value, ctypes.POINTER(ctypes.c_ulong))[0])
        finally:
            if value:
                connection.x11.lib.XFree(value)

    def active_window(self) -> int | None:
        with self._checked():
            window = self._property(self.connection.root_window, "_NET_ACTIVE_WINDOW")
        return window if window and window > 1 else None

    def window_process_id(self, window: int) -> int | None:
        with self._checked():
            return self._property(window, "_NET_WM_PID") or None

    def request_window_activation(self, window: int, timestamp: int | None = None) -> None:
        with self._checked():
            self.connection.request_window_activation(window, timestamp or self.server_timestamp())

    def pointer_rect(self) -> Rect | None:
        connection = self.connection
        root, child = WINDOW(), WINDOW()
        root_x, root_y = ctypes.c_int(), ctypes.c_int()
        win_x, win_y = ctypes.c_int(), ctypes.c_int()
        mask = ctypes.c_uint()
        with self._checked():
            found = connection.x11.lib.XQueryPointer(
                connection.display, connection.root_window,
                ctypes.byref(root), ctypes.byref(child),
                ctypes.byref(root_x), ctypes.byref(root_y),
                ctypes.byref(win_x), ctypes.byref(win_y), ctypes.byref(mask),
            )
        return Rect(root_x.value, root_y.value, 1, 1) if found else None

    def _focus_belongs_to(self, window: int) -> bool:
        connection = self.connection
        focus, revert = WINDOW(), ctypes.c_int()
        connection.x11.lib.XGetInputFocus(
            connection.display, ctypes.byref(focus), ctypes.byref(revert)
        )
        current = int(focus.value)
        # A text widget can own focus in a child X window. Never send paste
        # to an unrelated window just because activation was requested.
        for _ in range(64):
            if current == window:
                return True
            if current <= 1 or current == connection.root_window:
                return False
            root, parent = WINDOW(), WINDOW()
            children = ctypes.POINTER(WINDOW)()
            count = ctypes.c_uint()
            found = connection.x11.lib.XQueryTree(
                connection.display, current, ctypes.byref(root),
                ctypes.byref(parent), ctypes.byref(children), ctypes.byref(count),
            )
            if children:
                connection.x11.lib.XFree(children)
            if not found or parent.value == current:
                return False
            current = int(parent.value)
        return False

    def target_still_active(self, window: int) -> bool:
        try:
            with self._checked():
                return (
                    self._property(self.connection.root_window, "_NET_ACTIVE_WINDOW") == window
                    and self._focus_belongs_to(window)
                )
        except OSError:
            return False

    def paste_text(
        self,
        window: int,
        text: str,
        before_focus_transfer: Callable[[], None],
    ) -> bool:
        if self.xtest is None:
            return False

        connection = self.connection
        shift = connection.keysym_keycode("Shift_L")
        insert = connection.keysym_keycode("Insert")
        if not shift or not insert:
            return False

        # Do not release physical keys on the user's behalf. A held modifier
        # would change Shift+Insert into a different command in the target.
        modifiers = tuple(
            connection.keysym_keycode(name)
            for name in (
                "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R",
                "Super_L", "Super_R", "ISO_Level3_Shift", "Return", "KP_Enter",
            )
        )
        app = QGuiApplication.instance()
        if not isinstance(app, QGuiApplication):
            return False

        # Keep focus in the picker until the activation key is up. Otherwise
        # a held Enter can repeat in the editor, or Alt release can open a menu.
        deadline = time.monotonic() + 0.3
        while any(connection.key_is_pressed(key) for key in modifiers if key):
            if time.monotonic() >= deadline:
                return False
            app.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
            time.sleep(0.005)

        before_focus_transfer()
        try:
            with self._checked():
                connection.request_window_activation(window, self.server_timestamp())
            deadline = time.monotonic() + 0.3
            while True:
                released = not any(connection.key_is_pressed(key) for key in modifiers if key)
                if released and self.target_still_active(window):
                    break
                if time.monotonic() >= deadline:
                    return False
                app.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
                time.sleep(0.005)

            clipboard = app.clipboard()
            # Shift+Insert uses CLIPBOARD in some toolkits and PRIMARY in
            # others, including terminals. Keep both alive for async requests.
            clipboard.setText(text, QClipboard.Mode.Clipboard)
            if clipboard.supportsSelection():
                clipboard.setText(text, QClipboard.Mode.Selection)

            with self._checked():
                if not self._focus_belongs_to(window):
                    return False
                pressed: list[int] = []
                try:
                    for key in (shift, insert):
                        if not self.xtest.XTestFakeKeyEvent(connection.display, key, 1, 0):
                            return False
                        pressed.append(key)
                finally:
                    for key in reversed(pressed):
                        self.xtest.XTestFakeKeyEvent(connection.display, key, 0, 0)
            # Qt serves selection requests once the coordinator returns to
            # the event loop, before it restores focus to the popup.
            return True
        except OSError:
            return False

import ctypes
import ctypes.util
from collections.abc import Iterable

DISPLAY = ctypes.c_void_p
WINDOW = ctypes.c_ulong
KEYSYM = ctypes.c_ulong
KEYCODE = ctypes.c_ubyte

KEY_PRESS = 2
KEY_RELEASE = 3
BAD_ACCESS = 10

GRAB_MODE_ASYNC = 1

SHIFT_MASK = 1 << 0
LOCK_MASK = 1 << 1
CONTROL_MASK = 1 << 2
MOD1_MASK = 1 << 3


class XKeyEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", DISPLAY),
        ("window", WINDOW),
        ("root", WINDOW),
        ("subwindow", WINDOW),
        ("time", ctypes.c_ulong),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("x_root", ctypes.c_int),
        ("y_root", ctypes.c_int),
        ("state", ctypes.c_uint),
        ("keycode", ctypes.c_uint),
        ("same_screen", ctypes.c_int),
    ]


class XEvent(ctypes.Union):
    _fields_ = [
        ("type", ctypes.c_int),
        ("xkey", XKeyEvent),
        ("pad", ctypes.c_long * 24),
    ]


class XModifierKeymap(ctypes.Structure):
    _fields_ = [
        ("max_keypermod", ctypes.c_int),
        ("modifiermap", ctypes.POINTER(KEYCODE)),
    ]


class XErrorEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("display", DISPLAY),
        ("resourceid", ctypes.c_ulong),
        ("serial", ctypes.c_ulong),
        ("error_code", ctypes.c_ubyte),
        ("request_code", ctypes.c_ubyte),
        ("minor_code", ctypes.c_ubyte),
    ]


XErrorHandler = ctypes.CFUNCTYPE(
    ctypes.c_int,
    DISPLAY,
    ctypes.POINTER(XErrorEvent),
)


class X11Library:
    """Small ctypes wrapper around the Xlib calls used by Kaokey."""

    def __init__(
        self,
    ) -> None:
        library_name = ctypes.util.find_library("X11")

        if not library_name:
            raise OSError("libX11 is unavailable.")

        self.lib = ctypes.CDLL(library_name)
        self._configure_signatures()

    def _configure_signatures(
        self,
    ) -> None:
        lib = self.lib

        lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
        lib.XOpenDisplay.restype = DISPLAY

        lib.XCloseDisplay.argtypes = [DISPLAY]
        lib.XCloseDisplay.restype = ctypes.c_int

        lib.XDefaultRootWindow.argtypes = [DISPLAY]
        lib.XDefaultRootWindow.restype = WINDOW

        lib.XConnectionNumber.argtypes = [DISPLAY]
        lib.XConnectionNumber.restype = ctypes.c_int

        lib.XStringToKeysym.argtypes = [ctypes.c_char_p]
        lib.XStringToKeysym.restype = KEYSYM

        lib.XKeysymToKeycode.argtypes = [
            DISPLAY,
            KEYSYM,
        ]
        lib.XKeysymToKeycode.restype = KEYCODE

        lib.XGrabKey.argtypes = [
            DISPLAY,
            ctypes.c_int,
            ctypes.c_uint,
            WINDOW,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
        ]
        lib.XGrabKey.restype = ctypes.c_int

        lib.XUngrabKey.argtypes = [
            DISPLAY,
            ctypes.c_int,
            ctypes.c_uint,
            WINDOW,
        ]
        lib.XUngrabKey.restype = ctypes.c_int

        lib.XSync.argtypes = [
            DISPLAY,
            ctypes.c_int,
        ]
        lib.XSync.restype = ctypes.c_int

        lib.XPending.argtypes = [DISPLAY]
        lib.XPending.restype = ctypes.c_int

        lib.XNextEvent.argtypes = [
            DISPLAY,
            ctypes.POINTER(XEvent),
        ]
        lib.XNextEvent.restype = ctypes.c_int

        lib.XQueryKeymap.argtypes = [
            DISPLAY,
            ctypes.POINTER(ctypes.c_char),
        ]
        lib.XQueryKeymap.restype = ctypes.c_int

        lib.XGetModifierMapping.argtypes = [DISPLAY]
        lib.XGetModifierMapping.restype = ctypes.POINTER(
            XModifierKeymap
        )

        lib.XFreeModifiermap.argtypes = [
            ctypes.POINTER(XModifierKeymap)
        ]
        lib.XFreeModifiermap.restype = ctypes.c_int

        lib.XSetErrorHandler.argtypes = [ctypes.c_void_p]
        lib.XSetErrorHandler.restype = ctypes.c_void_p

        lib.XkbSetDetectableAutoRepeat.argtypes = [
            DISPLAY,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
        ]
        lib.XkbSetDetectableAutoRepeat.restype = ctypes.c_int


class X11Connection:
    """Owned Xlib display connection for one global hotkey."""

    def __init__(
        self,
    ) -> None:
        self.x11 = X11Library()
        self.display = self.x11.lib.XOpenDisplay(None)

        if not self.display:
            raise OSError("Could not open the X11 display.")

        self.root_window = int(
            self.x11.lib.XDefaultRootWindow(
                self.display
            )
        )
        self.file_descriptor = int(
            self.x11.lib.XConnectionNumber(
                self.display
            )
        )

        supported = ctypes.c_int()
        self.x11.lib.XkbSetDetectableAutoRepeat(
            self.display,
            1,
            ctypes.byref(supported),
        )

    def close(
        self,
    ) -> None:
        display = self.display

        if not display:
            return

        self.x11.lib.XCloseDisplay(display)
        self.display = DISPLAY()

    def keysym_keycode(
        self,
        name: str,
    ) -> int:
        keysym = self.x11.lib.XStringToKeysym(
            name.encode("ascii")
        )

        if not keysym:
            return 0

        return int(
            self.x11.lib.XKeysymToKeycode(
                self.display,
                keysym,
            )
        )

    def modifier_mask_for_keysyms(
        self,
        names: Iterable[str],
    ) -> int:
        keycodes = {
            self.keysym_keycode(name)
            for name in names
        }
        keycodes.discard(0)

        if not keycodes:
            return 0

        mapping = self.x11.lib.XGetModifierMapping(
            self.display
        )

        if not mapping:
            return 0

        try:
            max_per_modifier = mapping.contents.max_keypermod
            modifier_map = mapping.contents.modifiermap

            for modifier_index in range(8):
                for item_index in range(max_per_modifier):
                    index = (
                        modifier_index * max_per_modifier
                        + item_index
                    )

                    if int(modifier_map[index]) in keycodes:
                        return 1 << modifier_index
        finally:
            self.x11.lib.XFreeModifiermap(mapping)

        return 0

    def lock_modifier_variants(
        self,
    ) -> tuple[int, ...]:
        lock_masks = {
            self.modifier_mask_for_keysyms(("Caps_Lock",)),
            self.modifier_mask_for_keysyms(("Num_Lock",)),
            self.modifier_mask_for_keysyms(("Scroll_Lock",)),
        }
        lock_masks.discard(0)

        variants = {0}

        for mask in lock_masks:
            variants.update(
                value | mask
                for value in tuple(variants)
            )

        return tuple(sorted(variants))

    def grab_key(
        self,
        keycode: int,
        modifier_mask: int,
        lock_variants: tuple[int, ...],
    ) -> None:
        errors: list[int] = []

        @XErrorHandler
        def error_handler(
            _display: DISPLAY,
            event: ctypes.c_void_p,
        ) -> int:
            error_event = ctypes.cast(
                event,
                ctypes.POINTER(XErrorEvent),
            ).contents

            errors.append(
                int(error_event.error_code)
            )

            return 0

        callback_pointer = ctypes.cast(
            error_handler,
            ctypes.c_void_p,
        )
        previous_handler = self.x11.lib.XSetErrorHandler(
            callback_pointer
        )

        try:
            for lock_mask in lock_variants:
                self.x11.lib.XGrabKey(
                    self.display,
                    keycode,
                    modifier_mask | lock_mask,
                    self.root_window,
                    0,
                    GRAB_MODE_ASYNC,
                    GRAB_MODE_ASYNC,
                )

            self.x11.lib.XSync(
                self.display,
                0,
            )
        finally:
            self.x11.lib.XSetErrorHandler(
                previous_handler
            )

        if errors:
            self.ungrab_key(
                keycode,
                modifier_mask,
                lock_variants,
            )

            if BAD_ACCESS in errors:
                raise OSError(
                    "The global hotkey is already in use."
                )

            raise OSError(
                f"X11 rejected the global hotkey (error {errors[0]})."
            )

    def ungrab_key(
        self,
        keycode: int,
        modifier_mask: int,
        lock_variants: tuple[int, ...],
    ) -> None:
        if not self.display:
            return

        for lock_mask in lock_variants:
            self.x11.lib.XUngrabKey(
                self.display,
                keycode,
                modifier_mask | lock_mask,
                self.root_window,
            )

        self.x11.lib.XSync(
            self.display,
            0,
        )

    def pending_events(
        self,
    ) -> int:
        if not self.display:
            return 0

        return int(
            self.x11.lib.XPending(
                self.display
            )
        )

    def next_event(
        self,
    ) -> XEvent:
        event = XEvent()
        self.x11.lib.XNextEvent(
            self.display,
            ctypes.byref(event),
        )
        return event

    def key_is_pressed(
        self,
        keycode: int,
    ) -> bool:
        if not self.display or keycode <= 0:
            return False

        keymap = ctypes.create_string_buffer(32)
        self.x11.lib.XQueryKeymap(
            self.display,
            keymap,
        )

        byte_index = keycode // 8
        bit_index = keycode % 8

        if byte_index >= 32:
            return False

        return bool(
            keymap.raw[byte_index]
            & (1 << bit_index)
        )

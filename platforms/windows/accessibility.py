import ctypes
import ctypes.wintypes
import sys

from typing import Any

from popup_positioning import Rect


# Microsoft Active Accessibility object IDs.
OBJID_CLIENT = -4
OBJID_CARET = -8
CHILDID_SELF = 0

# VARIANT type used by IAccessible::accLocation.
VT_I4 = 3

# COM apartment setup.
COINIT_APARTMENTTHREADED = 0x2
S_OK = 0
S_FALSE = 1
RPC_E_CHANGED_MODE = -2147417850

# IAccessible inherits IDispatch. accLocation is method #22 in the
# COM vtable (IUnknown: 0-2, IDispatch: 3-6, IAccessible: 7+).
IACCESSIBLE_ACC_LOCATION_INDEX = 22
IUNKNOWN_RELEASE_INDEX = 2


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.wintypes.DWORD),
        ("Data2", ctypes.wintypes.WORD),
        ("Data3", ctypes.wintypes.WORD),
        ("Data4", ctypes.wintypes.BYTE * 8),
    ]


class _VariantValue(ctypes.Union):
    _fields_ = [
        ("lVal", ctypes.wintypes.LONG),
        ("llVal", ctypes.c_longlong),
        ("dblVal", ctypes.c_double),
        ("ptr", ctypes.c_void_p),
    ]


class Variant(ctypes.Structure):
    _anonymous_ = ("value",)
    _fields_ = [
        ("vt", ctypes.wintypes.WORD),
        ("wReserved1", ctypes.wintypes.WORD),
        ("wReserved2", ctypes.wintypes.WORD),
        ("wReserved3", ctypes.wintypes.WORD),
        ("value", _VariantValue),
    ]


IID_IACCESSIBLE = GUID(
    0x618736E0,
    0x3C3D,
    0x11CF,
    (ctypes.wintypes.BYTE * 8)(
        0x81,
        0x0C,
        0x00,
        0xAA,
        0x00,
        0x38,
        0x9B,
        0x71,
    ),
)


def get_accessible_caret_rect(
    focus_hwnd: int | None,
    foreground_hwnd: int | None,
) -> Rect | None:
    """Return the current MSAA caret rectangle in screen coordinates."""
    if sys.platform != "win32":
        return None

    ole32 = _load_dll("ole32")
    oleacc = _load_dll("oleacc")

    _configure_ole32(ole32)
    _configure_oleacc(oleacc)

    com_result = ole32.CoInitializeEx(
        None,
        COINIT_APARTMENTTHREADED,
    )

    should_uninitialize = com_result in {
        S_OK,
        S_FALSE,
    }

    if (
        com_result < 0
        and com_result != RPC_E_CHANGED_MODE
    ):
        return None

    try:
        targets = _unique_handles(
            focus_hwnd,
            foreground_hwnd,
        )

        # Some browser/Electron providers are lazy. Touching OBJID_CLIENT
        # asks the application to initialise its accessibility tree.
        for hwnd in targets:
            _activate_accessibility(
                oleacc,
                hwnd,
            )

        # Windows documentation recommends requesting OBJID_CARET from the
        # focused window for custom carets. Keep the global caret as a useful
        # fallback for applications which expose it that way instead.
        for hwnd in targets:
            rect = _caret_rect_from_window(
                oleacc,
                hwnd,
            )
            if rect is not None:
                return rect

        return _caret_rect_from_window(
            oleacc,
            None,
        )
    finally:
        if should_uninitialize:
            ole32.CoUninitialize()


def get_accessible_caret_rect_from_event(
    hwnd: int | None,
    object_id: int,
    child_id: int,
) -> Rect | None:
    """Resolve the caret object that generated a WinEvent notification.

    This is the important difference from polling AccessibleObjectFromWindow:
    the event identifies the accessibility object *after* the provider reports
    that its location changed, so browser layout changes are not guessed from a
    possibly stale snapshot.
    """
    if (
        sys.platform != "win32"
        or object_id != OBJID_CARET
    ):
        return None

    ole32 = _load_dll("ole32")
    oleacc = _load_dll("oleacc")

    _configure_ole32(ole32)
    _configure_oleacc(oleacc)

    com_result = ole32.CoInitializeEx(
        None,
        COINIT_APARTMENTTHREADED,
    )

    should_uninitialize = com_result in {
        S_OK,
        S_FALSE,
    }

    if (
        com_result < 0
        and com_result != RPC_E_CHANGED_MODE
    ):
        return None

    try:
        accessible = ctypes.c_void_p()
        child = Variant()

        result = oleacc.AccessibleObjectFromEvent(
            hwnd,
            object_id & 0xFFFFFFFF,
            child_id & 0xFFFFFFFF,
            ctypes.byref(accessible),
            ctypes.byref(child),
        )

        if (
            result != S_OK
            or not accessible.value
        ):
            return None

        try:
            return _call_acc_location(
                accessible,
                child,
            )
        finally:
            _release_interface(
                accessible
            )
    finally:
        if should_uninitialize:
            ole32.CoUninitialize()


def _unique_handles(
    *handles: int | None,
) -> list[int]:
    result: list[int] = []

    for handle in handles:
        if not handle:
            continue

        value = int(handle)
        if value not in result:
            result.append(value)

    return result


def _activate_accessibility(
    oleacc: Any,
    hwnd: int,
) -> None:
    accessible = _accessible_object_from_window(
        oleacc,
        hwnd,
        OBJID_CLIENT,
    )

    if accessible is not None:
        _release_interface(
            accessible
        )


def _caret_rect_from_window(
    oleacc: Any,
    hwnd: int | None,
) -> Rect | None:
    accessible = _accessible_object_from_window(
        oleacc,
        hwnd,
        OBJID_CARET,
    )

    if accessible is None:
        return None

    try:
        return _call_acc_location(
            accessible
        )
    finally:
        _release_interface(
            accessible
        )


def _accessible_object_from_window(
    oleacc: Any,
    hwnd: int | None,
    object_id: int,
) -> ctypes.c_void_p | None:
    interface_pointer = ctypes.c_void_p()

    result = oleacc.AccessibleObjectFromWindow(
        hwnd,
        object_id & 0xFFFFFFFF,
        ctypes.byref(
            IID_IACCESSIBLE
        ),
        ctypes.byref(
            interface_pointer
        ),
    )

    if (
        result != S_OK
        or not interface_pointer.value
    ):
        return None

    return interface_pointer


def _call_acc_location(
    accessible: ctypes.c_void_p,
    child: Variant | None = None,
) -> Rect | None:
    winfunctype = getattr(
        ctypes,
        "WINFUNCTYPE",
        None,
    )

    if winfunctype is None:
        return None

    vtable = _get_vtable(
        accessible
    )

    method_address = vtable[
        IACCESSIBLE_ACC_LOCATION_INDEX
    ]

    if not method_address:
        return None

    acc_location_type = winfunctype(
        ctypes.wintypes.LONG,
        ctypes.c_void_p,
        ctypes.POINTER(
            ctypes.wintypes.LONG
        ),
        ctypes.POINTER(
            ctypes.wintypes.LONG
        ),
        ctypes.POINTER(
            ctypes.wintypes.LONG
        ),
        ctypes.POINTER(
            ctypes.wintypes.LONG
        ),
        Variant,
    )

    acc_location = acc_location_type(
        method_address
    )

    left = ctypes.wintypes.LONG()
    top = ctypes.wintypes.LONG()
    width = ctypes.wintypes.LONG()
    height = ctypes.wintypes.LONG()

    if child is None:
        child = Variant()
        child.vt = VT_I4
        child.lVal = CHILDID_SELF

    result = acc_location(
        accessible,
        ctypes.byref(left),
        ctypes.byref(top),
        ctypes.byref(width),
        ctypes.byref(height),
        child,
    )

    if result != S_OK:
        return None

    caret_width = max(
        1,
        int(width.value),
    )
    caret_height = max(
        1,
        int(height.value),
    )

    return Rect(
        x=int(left.value),
        y=int(top.value),
        width=caret_width,
        height=caret_height,
    )


def _release_interface(
    accessible: ctypes.c_void_p,
) -> None:
    winfunctype = getattr(
        ctypes,
        "WINFUNCTYPE",
        None,
    )

    if winfunctype is None:
        return

    vtable = _get_vtable(
        accessible
    )

    method_address = vtable[
        IUNKNOWN_RELEASE_INDEX
    ]

    if not method_address:
        return

    release_type = winfunctype(
        ctypes.wintypes.ULONG,
        ctypes.c_void_p,
    )

    release = release_type(
        method_address
    )

    release(
        accessible
    )


def _get_vtable(
    interface_pointer: ctypes.c_void_p,
) -> ctypes.POINTER(ctypes.c_void_p):
    pointer_to_vtable = ctypes.cast(
        interface_pointer,
        ctypes.POINTER(
            ctypes.POINTER(
                ctypes.c_void_p
            )
        ),
    )

    return pointer_to_vtable.contents


def _load_dll(
    name: str,
) -> Any:
    win_dll = getattr(
        ctypes,
        "WinDLL",
        None,
    )

    if win_dll is None:
        raise RuntimeError(
            "Windows DLL loading is unavailable."
        )

    return win_dll(
        name,
        use_last_error=True,
    )


def _configure_ole32(
    ole32: Any,
) -> None:
    ole32.CoInitializeEx.argtypes = [
        ctypes.c_void_p,
        ctypes.wintypes.DWORD,
    ]
    ole32.CoInitializeEx.restype = (
        ctypes.wintypes.LONG
    )

    ole32.CoUninitialize.argtypes = []
    ole32.CoUninitialize.restype = None


def _configure_oleacc(
    oleacc: Any,
) -> None:
    oleacc.AccessibleObjectFromWindow.argtypes = [
        ctypes.wintypes.HWND,
        ctypes.wintypes.DWORD,
        ctypes.POINTER(GUID),
        ctypes.POINTER(
            ctypes.c_void_p
        ),
    ]
    oleacc.AccessibleObjectFromWindow.restype = (
        ctypes.wintypes.LONG
    )

    oleacc.AccessibleObjectFromEvent.argtypes = [
        ctypes.wintypes.HWND,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.DWORD,
        ctypes.POINTER(
            ctypes.c_void_p
        ),
        ctypes.POINTER(Variant),
    ]
    oleacc.AccessibleObjectFromEvent.restype = (
        ctypes.wintypes.LONG
    )

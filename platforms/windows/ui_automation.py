import ctypes
import ctypes.wintypes
import sys

from dataclasses import dataclass
from typing import Any

from platforms.windows.constants import (
    CARET_DIAGNOSTICS_ENABLED,
    CARET_STALE_POSITION_TOLERANCE,
)
from popup_positioning import Rect


# UI Automation is the preferred Windows accessibility API for a caret that is
# owned by a modern text control. Chromium/Electron and other applications may
# expose a caret through TextPattern2 even when there is no Win32 system caret.
UIA_TEXT_PATTERN2_ID = 10024

CLSCTX_INPROC_SERVER = 0x1
COINIT_APARTMENTTHREADED = 0x2

S_OK = 0
S_FALSE = 1
RPC_E_CHANGED_MODE = -2147417850

# COM vtable indexes. The first three entries are IUnknown.
IUNKNOWN_RELEASE_INDEX = 2
IUIAUTOMATION_GET_FOCUSED_ELEMENT_INDEX = 8
IUIAUTOMATION_ELEMENT_GET_RUNTIME_ID_INDEX = 4
IUIAUTOMATION_ELEMENT_GET_CURRENT_PATTERN_AS_INDEX = 14
IUIAUTOMATION_ELEMENT_GET_CURRENT_BOUNDING_RECTANGLE_INDEX = 43
IUIAUTOMATION_TEXT_PATTERN2_GET_CARET_RANGE_INDEX = 10
IUIAUTOMATION_TEXT_RANGE_GET_BOUNDING_RECTANGLES_INDEX = 10


def _debug_uia(
    message: str,
) -> None:
    if not CARET_DIAGNOSTICS_ENABLED:
        return

    print(
        f"[Kaokey UIA] {message}",
        flush=True,
    )


class GUID(ctypes.Structure):
    _fields_ = [
        (
            "Data1",
            ctypes.wintypes.DWORD,
        ),
        (
            "Data2",
            ctypes.wintypes.WORD,
        ),
        (
            "Data3",
            ctypes.wintypes.WORD,
        ),
        (
            "Data4",
            ctypes.wintypes.BYTE * 8,
        ),
    ]


def _guid(
    data1: int,
    data2: int,
    data3: int,
    *data4: int,
) -> GUID:
    return GUID(
        data1,
        data2,
        data3,
        (ctypes.wintypes.BYTE * 8)(
            *data4
        ),
    )


CLSID_CUIAUTOMATION: GUID = _guid(
    0xFF48DBA4,
    0x60EF,
    0x4201,
    0xAA,
    0x87,
    0x54,
    0x10,
    0x3E,
    0xEF,
    0x59,
    0x4E,
)

IID_IUIAUTOMATION: GUID = _guid(
    0x30CBE57D,
    0xD9D0,
    0x452A,
    0xAB,
    0x13,
    0x7A,
    0xC5,
    0xAC,
    0x48,
    0x25,
    0xEE,
)

IID_IUIAUTOMATION_TEXT_PATTERN2: GUID = _guid(
    0x506A921A,
    0xFCC9,
    0x409F,
    0xB2,
    0x3B,
    0x37,
    0xEB,
    0x74,
    0x10,
    0x68,
    0x72,
)


@dataclass(frozen=True)
class UiaCaretSnapshot:
    # caret_rect is the best current position. raw_caret_rect is the
    # rectangle returned directly by TextPattern2 before compensation.
    caret_rect: Rect | None
    raw_caret_rect: Rect | None
    element_rect: Rect | None
    runtime_id: tuple[int, ...] | None
    previous_element_rect: Rect | None
    previous_caret_rect: Rect | None
    element_delta: tuple[int, int] | None
    same_element_as_previous: bool
    correction_applied: bool


_previous_runtime_id: tuple[int, ...] | None = None
_previous_element_rect: Rect | None = None
_previous_caret_rect: Rect | None = None


def get_uia_caret_rect() -> Rect | None:
    """Return the active UIA TextPattern2 caret in physical screen pixels."""
    return get_uia_caret_snapshot().caret_rect


def get_uia_caret_snapshot() -> UiaCaretSnapshot:
    """Return caret + focused-element geometry for Stage 6.7 diagnostics."""
    if sys.platform != "win32":
        _debug_uia("not running on Windows")
        return _empty_snapshot()

    ole32 = _load_dll(
        "ole32"
    )
    oleaut32 = _load_dll(
        "oleaut32"
    )

    _configure_ole32(
        ole32
    )
    _configure_oleaut32(
        oleaut32
    )

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
        and com_result
        != RPC_E_CHANGED_MODE
    ):
        _debug_uia(
            f"CoInitializeEx failed: {com_result}"
        )
        return _empty_snapshot()

    automation = ctypes.c_void_p()
    element = ctypes.c_void_p()
    pattern = ctypes.c_void_p()
    caret_range = ctypes.c_void_p()

    try:
        result = ole32.CoCreateInstance(
            ctypes.byref(
                CLSID_CUIAUTOMATION
            ),
            None,
            CLSCTX_INPROC_SERVER,
            ctypes.byref(
                IID_IUIAUTOMATION
            ),
            ctypes.byref(
                automation
            ),
        )

        if result < 0 or not automation:
            _debug_uia(
                f"CoCreateInstance failed: {result}"
            )
            return _empty_snapshot()

        get_focused_element = _com_method(
            automation,
            IUIAUTOMATION_GET_FOCUSED_ELEMENT_INDEX,
            ctypes.POINTER(
                ctypes.c_void_p
            ),
        )

        result = get_focused_element(
            automation,
            ctypes.byref(
                element
            ),
        )

        if result < 0 or not element:
            _debug_uia(
                f"GetFocusedElement failed: {result}"
            )
            return _empty_snapshot()

        element_rect = _get_element_rect(
            element
        )
        runtime_id = _get_runtime_id(
            element,
            oleaut32,
        )

        get_pattern = _com_method(
            element,
            IUIAUTOMATION_ELEMENT_GET_CURRENT_PATTERN_AS_INDEX,
            ctypes.c_int,
            ctypes.POINTER(
                GUID
            ),
            ctypes.POINTER(
                ctypes.c_void_p
            ),
        )

        result = get_pattern(
            element,
            UIA_TEXT_PATTERN2_ID,
            ctypes.byref(
                IID_IUIAUTOMATION_TEXT_PATTERN2
            ),
            ctypes.byref(
                pattern
            ),
        )

        if result < 0 or not pattern:
            _debug_uia(
                f"TextPattern2 unavailable: {result}"
            )
            return _build_snapshot(
                runtime_id,
                element_rect,
                None,
            )

        is_active = (
            ctypes.wintypes.BOOL()
        )

        get_caret_range = _com_method(
            pattern,
            IUIAUTOMATION_TEXT_PATTERN2_GET_CARET_RANGE_INDEX,
            ctypes.POINTER(
                ctypes.wintypes.BOOL
            ),
            ctypes.POINTER(
                ctypes.c_void_p
            ),
        )

        result = get_caret_range(
            pattern,
            ctypes.byref(
                is_active
            ),
            ctypes.byref(
                caret_range
            ),
        )

        if (
            result < 0
            or not caret_range
            or not bool(
                is_active.value
            )
        ):
            _debug_uia(
                "GetCaretRange failed/inactive: "
                f"result={result}, "
                f"range={bool(caret_range)}, "
                f"active={bool(is_active.value)}"
            )
            return _build_snapshot(
                runtime_id,
                element_rect,
                None,
            )

        raw_caret_rect = _get_range_rect(
            caret_range,
            oleaut32,
        )

        return _build_snapshot(
            runtime_id,
            element_rect,
            raw_caret_rect,
        )
    finally:
        _release(
            caret_range
        )
        _release(
            pattern
        )
        _release(
            element
        )
        _release(
            automation
        )

        if should_uninitialize:
            ole32.CoUninitialize()


def _empty_snapshot() -> UiaCaretSnapshot:
    return UiaCaretSnapshot(
        caret_rect=None,
        raw_caret_rect=None,
        element_rect=None,
        runtime_id=None,
        previous_element_rect=None,
        previous_caret_rect=None,
        element_delta=None,
        same_element_as_previous=False,
        correction_applied=False,
    )


def correct_stale_caret_for_element_move(
    raw_caret_rect: Rect | None,
    previous_caret_rect: Rect | None,
    element_delta: tuple[int, int] | None,
    same_element_as_previous: bool,
    tolerance: int = CARET_STALE_POSITION_TOLERANCE,
) -> tuple[Rect | None, bool]:
    """Compensate Firefox's one-invocation-late accessibility caret.

    We only compensate when all of these are true:
    - it is the same focused UIA element;
    - that element moved;
    - the newly queried caret is still at the previous absolute position.

    This deliberately avoids guessing when the user actually moved the caret
    inside the text field.
    """
    if (
        raw_caret_rect is None
        or previous_caret_rect is None
        or element_delta is None
        or not same_element_as_previous
    ):
        return raw_caret_rect, False

    delta_x, delta_y = element_delta

    if delta_x == 0 and delta_y == 0:
        return raw_caret_rect, False

    if (
        abs(
            raw_caret_rect.x
            - previous_caret_rect.x
        ) > tolerance
        or abs(
            raw_caret_rect.y
            - previous_caret_rect.y
        ) > tolerance
    ):
        return raw_caret_rect, False

    return (
        Rect(
            x=raw_caret_rect.x + delta_x,
            y=raw_caret_rect.y + delta_y,
            width=raw_caret_rect.width,
            height=raw_caret_rect.height,
        ),
        True,
    )


def _build_snapshot(
    runtime_id: tuple[int, ...] | None,
    element_rect: Rect | None,
    raw_caret_rect: Rect | None,
) -> UiaCaretSnapshot:
    global _previous_runtime_id
    global _previous_element_rect
    global _previous_caret_rect

    same_element = (
        runtime_id is not None
        and runtime_id == _previous_runtime_id
    )

    previous_element_rect = (
        _previous_element_rect
        if same_element
        else None
    )
    previous_caret_rect = (
        _previous_caret_rect
        if same_element
        else None
    )

    element_delta: tuple[int, int] | None = None

    if (
        same_element
        and previous_element_rect is not None
        and element_rect is not None
    ):
        element_delta = (
            element_rect.x
            - previous_element_rect.x,
            element_rect.y
            - previous_element_rect.y,
        )

    (
        caret_rect,
        correction_applied,
    ) = correct_stale_caret_for_element_move(
        raw_caret_rect,
        previous_caret_rect,
        element_delta,
        same_element,
    )

    _debug_uia(
        f"focused element runtime id: {runtime_id}"
    )
    _debug_uia(
        f"focused element rect: {element_rect}"
    )
    _debug_uia(
        "focused element previous: "
        f"{previous_element_rect}; "
        f"same={same_element}; "
        f"delta={element_delta}"
    )
    _debug_uia(
        "caret raw/resolved: "
        f"{raw_caret_rect} -> {caret_rect}; "
        f"corrected={correction_applied}"
    )

    _previous_runtime_id = runtime_id
    _previous_element_rect = element_rect

    # Store the best known actual position, not the stale provider value.
    # This also lets consecutive scrolls be corrected correctly.
    _previous_caret_rect = caret_rect

    return UiaCaretSnapshot(
        caret_rect=caret_rect,
        raw_caret_rect=raw_caret_rect,
        element_rect=element_rect,
        runtime_id=runtime_id,
        previous_element_rect=previous_element_rect,
        previous_caret_rect=previous_caret_rect,
        element_delta=element_delta,
        same_element_as_previous=same_element,
        correction_applied=correction_applied,
    )


def _get_element_rect(
    element: ctypes.c_void_p,
) -> Rect | None:
    native_rect = ctypes.wintypes.RECT()

    get_bounding_rect = _com_method(
        element,
        IUIAUTOMATION_ELEMENT_GET_CURRENT_BOUNDING_RECTANGLE_INDEX,
        ctypes.POINTER(
            ctypes.wintypes.RECT
        ),
    )

    result = get_bounding_rect(
        element,
        ctypes.byref(
            native_rect
        ),
    )

    if result < 0:
        _debug_uia(
            f"CurrentBoundingRectangle failed: {result}"
        )
        return None

    width = (
        int(native_rect.right)
        - int(native_rect.left)
    )
    height = (
        int(native_rect.bottom)
        - int(native_rect.top)
    )

    if width <= 0 or height <= 0:
        return None

    return Rect(
        x=int(native_rect.left),
        y=int(native_rect.top),
        width=width,
        height=height,
    )


def _get_runtime_id(
    element: ctypes.c_void_p,
    oleaut32: Any,
) -> tuple[int, ...] | None:
    safe_array = ctypes.c_void_p()

    get_runtime_id = _com_method(
        element,
        IUIAUTOMATION_ELEMENT_GET_RUNTIME_ID_INDEX,
        ctypes.POINTER(
            ctypes.c_void_p
        ),
    )

    result = get_runtime_id(
        element,
        ctypes.byref(
            safe_array
        ),
    )

    if result < 0 or not safe_array:
        _debug_uia(
            f"GetRuntimeId failed: {result}"
        )
        return None

    try:
        values = _safe_array_ints(
            oleaut32,
            safe_array,
        )
    finally:
        oleaut32.SafeArrayDestroy(
            safe_array
        )

    if not values:
        return None

    return tuple(values)

def _get_range_rect(
    text_range: ctypes.c_void_p,
    oleaut32: Any,
) -> Rect | None:
    safe_array = ctypes.c_void_p()

    get_rectangles = _com_method(
        text_range,
        IUIAUTOMATION_TEXT_RANGE_GET_BOUNDING_RECTANGLES_INDEX,
        ctypes.POINTER(
            ctypes.c_void_p
        ),
    )

    result = get_rectangles(
        text_range,
        ctypes.byref(
            safe_array
        ),
    )

    if result < 0 or not safe_array:
        _debug_uia(
            "GetBoundingRectangles returned no array: "
            f"result={result}"
        )
        return None

    try:
        values = _safe_array_doubles(
            oleaut32,
            safe_array,
        )
    finally:
        oleaut32.SafeArrayDestroy(
            safe_array
        )

    if len(values) < 4:
        _debug_uia(
            "GetBoundingRectangles returned "
            f"{len(values)} values: {values}"
        )
        return None

    x, y, width, height = values[
        :4
    ]

    _debug_uia(
        "caret bounding rectangle: "
        f"x={x}, y={y}, "
        f"width={width}, height={height}"
    )

    return Rect(
        x=round(x),
        y=round(y),
        width=max(
            1,
            round(width),
        ),
        height=max(
            1,
            round(height),
        ),
    )


def _safe_array_doubles(
    oleaut32: Any,
    safe_array: ctypes.c_void_p,
) -> list[float]:
    if oleaut32.SafeArrayGetDim(
        safe_array
    ) != 1:
        return []

    lower = ctypes.c_long()
    upper = ctypes.c_long()

    if oleaut32.SafeArrayGetLBound(
        safe_array,
        1,
        ctypes.byref(
            lower
        ),
    ) < 0:
        return []

    if oleaut32.SafeArrayGetUBound(
        safe_array,
        1,
        ctypes.byref(
            upper
        ),
    ) < 0:
        return []

    count = (
        upper.value
        - lower.value
        + 1
    )

    if count <= 0:
        return []

    data = ctypes.c_void_p()

    if oleaut32.SafeArrayAccessData(
        safe_array,
        ctypes.byref(
            data
        ),
    ) < 0:
        return []

    try:
        values = ctypes.cast(
            data,
            ctypes.POINTER(
                ctypes.c_double
            ),
        )

        return [
            float(values[index])
            for index in range(
                count
            )
        ]
    finally:
        oleaut32.SafeArrayUnaccessData(
            safe_array
        )



def _safe_array_ints(
    oleaut32: Any,
    safe_array: ctypes.c_void_p,
) -> list[int]:
    if oleaut32.SafeArrayGetDim(
        safe_array
    ) != 1:
        return []

    lower = ctypes.c_long()
    upper = ctypes.c_long()

    if oleaut32.SafeArrayGetLBound(
        safe_array,
        1,
        ctypes.byref(
            lower
        ),
    ) < 0:
        return []

    if oleaut32.SafeArrayGetUBound(
        safe_array,
        1,
        ctypes.byref(
            upper
        ),
    ) < 0:
        return []

    count = (
        upper.value
        - lower.value
        + 1
    )

    if count <= 0:
        return []

    data = ctypes.c_void_p()

    if oleaut32.SafeArrayAccessData(
        safe_array,
        ctypes.byref(
            data
        ),
    ) < 0:
        return []

    try:
        values = ctypes.cast(
            data,
            ctypes.POINTER(
                ctypes.c_int
            ),
        )

        return [
            int(values[index])
            for index in range(
                count
            )
        ]
    finally:
        oleaut32.SafeArrayUnaccessData(
            safe_array
        )

def _com_method(
    pointer: ctypes.c_void_p,
    index: int,
    *argtypes: object,
) -> Any:
    winfunctype = getattr(
        ctypes,
        "WINFUNCTYPE",
        None,
    )

    if winfunctype is None:
        raise RuntimeError(
            "ctypes.WINFUNCTYPE is unavailable."
        )

    vtable = ctypes.cast(
        pointer,
        ctypes.POINTER(
            ctypes.POINTER(
                ctypes.c_void_p
            )
        ),
    ).contents

    address = vtable[
        index
    ]

    prototype = winfunctype(
        ctypes.c_long,
        ctypes.c_void_p,
        *argtypes,
    )

    return prototype(
        address
    )


def _release(
    pointer: ctypes.c_void_p,
) -> None:
    if not pointer:
        return

    release = _com_method(
        pointer,
        IUNKNOWN_RELEASE_INDEX,
    )

    release(
        pointer
    )


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
        ctypes.c_long
    )

    ole32.CoUninitialize.argtypes = []
    ole32.CoUninitialize.restype = None

    ole32.CoCreateInstance.argtypes = [
        ctypes.POINTER(
            GUID
        ),
        ctypes.c_void_p,
        ctypes.wintypes.DWORD,
        ctypes.POINTER(
            GUID
        ),
        ctypes.POINTER(
            ctypes.c_void_p
        ),
    ]
    ole32.CoCreateInstance.restype = (
        ctypes.c_long
    )


def _configure_oleaut32(
    oleaut32: Any,
) -> None:
    oleaut32.SafeArrayGetDim.argtypes = [
        ctypes.c_void_p,
    ]
    oleaut32.SafeArrayGetDim.restype = (
        ctypes.wintypes.UINT
    )

    oleaut32.SafeArrayGetLBound.argtypes = [
        ctypes.c_void_p,
        ctypes.wintypes.UINT,
        ctypes.POINTER(
            ctypes.c_long
        ),
    ]
    oleaut32.SafeArrayGetLBound.restype = (
        ctypes.c_long
    )

    oleaut32.SafeArrayGetUBound.argtypes = [
        ctypes.c_void_p,
        ctypes.wintypes.UINT,
        ctypes.POINTER(
            ctypes.c_long
        ),
    ]
    oleaut32.SafeArrayGetUBound.restype = (
        ctypes.c_long
    )

    oleaut32.SafeArrayAccessData.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(
            ctypes.c_void_p
        ),
    ]
    oleaut32.SafeArrayAccessData.restype = (
        ctypes.c_long
    )

    oleaut32.SafeArrayUnaccessData.argtypes = [
        ctypes.c_void_p,
    ]
    oleaut32.SafeArrayUnaccessData.restype = (
        ctypes.c_long
    )

    oleaut32.SafeArrayDestroy.argtypes = [
        ctypes.c_void_p,
    ]
    oleaut32.SafeArrayDestroy.restype = (
        ctypes.c_long
    )

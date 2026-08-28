import ctypes
import ctypes.wintypes
import sys

from dataclasses import dataclass
from typing import Any

from platforms.windows.accessibility import (
    get_accessible_caret_rect,
)
from platforms.windows.constants import (
    CARET_DIAGNOSTICS_ENABLED,
    CARET_STALE_POSITION_TOLERANCE,
)
from platforms.windows.ui_automation import (
    UiaCaretSnapshot,
    get_uia_caret_snapshot,
)
from popup_positioning import Rect


GUI_CARETBLINKING = 0x00000001


class GUIThreadInfo(ctypes.Structure):
    _fields_ = [
        (
            "cbSize",
            ctypes.wintypes.DWORD,
        ),
        (
            "flags",
            ctypes.wintypes.DWORD,
        ),
        (
            "hwndActive",
            ctypes.wintypes.HWND,
        ),
        (
            "hwndFocus",
            ctypes.wintypes.HWND,
        ),
        (
            "hwndCapture",
            ctypes.wintypes.HWND,
        ),
        (
            "hwndMenuOwner",
            ctypes.wintypes.HWND,
        ),
        (
            "hwndMoveSize",
            ctypes.wintypes.HWND,
        ),
        (
            "hwndCaret",
            ctypes.wintypes.HWND,
        ),
        (
            "rcCaret",
            ctypes.wintypes.RECT,
        ),
    ]


@dataclass(frozen=True)
class WindowsForegroundContext:
    window_handle: int | None
    focus_window_handle: int | None
    caret_rect: Rect | None
    window_rect: Rect | None


def capture_foreground_context() -> WindowsForegroundContext:
    user32 = _load_user32()

    _configure_user32(
        user32
    )

    hwnd = user32.GetForegroundWindow()

    if not hwnd:
        if CARET_DIAGNOSTICS_ENABLED:
            print(
                "\n[Kaokey caret diagnostics]\n"
                "foreground hwnd: None\n"
                "No foreground window.",
                flush=True,
            )

        return WindowsForegroundContext(
            window_handle=None,
            focus_window_handle=None,
            caret_rect=None,
            window_rect=None,
        )

    window_handle = int(
        hwnd
    )

    thread_info = _get_gui_thread_info(
        user32
    )

    focus_handle: int | None = None
    caret_handle: int | None = None

    if thread_info is not None:
        if thread_info.hwndFocus:
            focus_handle = int(
                thread_info.hwndFocus
            )

        if thread_info.hwndCaret:
            caret_handle = int(
                thread_info.hwndCaret
            )

    native_rect = None

    if (
        thread_info is not None
        and (
            thread_info.flags
            & GUI_CARETBLINKING
        )
    ):
        native_rect = _get_native_caret_rect(
            user32,
            thread_info,
        )

    # Query UI Automation on every invocation, even when a Win32 caret exists.
    # Firefox exposes a synthetic system caret that can lag one invocation
    # behind the focused element after scrolling. UIA element geometry lets us
    # detect that exact case and compensate it safely.
    uia_snapshot, uia_error = (
        _try_uia_snapshot()
    )
    uia_rect = (
        uia_snapshot.caret_rect
        if uia_snapshot is not None
        else None
    )

    if CARET_DIAGNOSTICS_ENABLED:
        msaa_rect, msaa_error = _try_msaa_caret(
            focus_handle,
            window_handle,
        )
    else:
        msaa_rect = None
        msaa_error = None

        if native_rect is None and uia_rect is None:
            msaa_rect = get_accessible_caret_rect(
                focus_handle,
                window_handle,
            )

    raw_uia_rect = (
        uia_snapshot.raw_caret_rect
        if uia_snapshot is not None
        else None
    )

    use_adjusted_uia = (
        uia_snapshot is not None
        and uia_snapshot.correction_applied
        and uia_rect is not None
        and (
            native_rect is None
            or _same_caret_position(
                native_rect,
                raw_uia_rect,
            )
        )
    )

    if use_adjusted_uia:
        caret_rect = uia_rect
        caret_source = "uia-adjusted"
    elif native_rect is not None:
        caret_rect = native_rect
        caret_source = "native"
    elif uia_rect is not None:
        caret_rect = uia_rect
        caret_source = "uia"
    elif msaa_rect is not None:
        caret_rect = msaa_rect
        caret_source = "msaa"
    else:
        caret_rect = None
        caret_source = "none"

    window_rect = _get_window_rect(
        user32,
        hwnd,
    )

    if CARET_DIAGNOSTICS_ENABLED:
        _print_caret_diagnostics(
            window_handle=window_handle,
            focus_handle=focus_handle,
            caret_handle=caret_handle,
            thread_info=thread_info,
            native_rect=native_rect,
            uia_rect=uia_rect,
            uia_snapshot=uia_snapshot,
            uia_error=uia_error,
            msaa_rect=msaa_rect,
            msaa_error=msaa_error,
            selected_source=caret_source,
            selected_rect=caret_rect,
            window_rect=window_rect,
        )

    return WindowsForegroundContext(
        window_handle=window_handle,
        focus_window_handle=focus_handle,
        caret_rect=caret_rect,
        window_rect=window_rect,
    )


def _same_caret_position(
    first: Rect | None,
    second: Rect | None,
) -> bool:
    if first is None or second is None:
        return False

    return (
        abs(
            first.x
            - second.x
        ) <= CARET_STALE_POSITION_TOLERANCE
        and abs(
            first.y
            - second.y
        ) <= CARET_STALE_POSITION_TOLERANCE
    )


def _try_uia_snapshot(
) -> tuple[UiaCaretSnapshot | None, str | None]:
    try:
        return (
            get_uia_caret_snapshot(),
            None,
        )
    except Exception as error:
        return (
            None,
            repr(error),
        )

def _try_msaa_caret(
    focus_handle: int | None,
    window_handle: int | None,
) -> tuple[Rect | None, str | None]:
    try:
        return (
            get_accessible_caret_rect(
                focus_handle,
                window_handle,
            ),
            None,
        )
    except Exception as error:
        return (
            None,
            repr(error),
        )


def _format_handle(
    handle: int | None,
) -> str:
    if handle is None:
        return "None"

    return f"0x{handle:X}"


def _print_caret_diagnostics(
    *,
    window_handle: int,
    focus_handle: int | None,
    caret_handle: int | None,
    thread_info: GUIThreadInfo | None,
    native_rect: Rect | None,
    uia_rect: Rect | None,
    uia_snapshot: UiaCaretSnapshot | None,
    uia_error: str | None,
    msaa_rect: Rect | None,
    msaa_error: str | None,
    selected_source: str,
    selected_rect: Rect | None,
    window_rect: Rect | None,
) -> None:
    if thread_info is None:
        flags_text = "None"
        raw_caret_text = "None"
    else:
        flags_text = f"0x{int(thread_info.flags):X}"
        raw_caret_text = (
            f"({thread_info.rcCaret.left}, "
            f"{thread_info.rcCaret.top}, "
            f"{thread_info.rcCaret.right}, "
            f"{thread_info.rcCaret.bottom})"
        )

    lines = [
        "",
        "[Kaokey caret diagnostics]",
        f"foreground hwnd: {_format_handle(window_handle)}",
        f"focus hwnd:      {_format_handle(focus_handle)}",
        f"caret hwnd:      {_format_handle(caret_handle)}",
        f"GUI flags:       {flags_text}",
        f"raw rcCaret:     {raw_caret_text}",
        f"native:          {native_rect}",
        f"UIA:             {uia_rect}",
        f"MSAA:            {msaa_rect}",
        f"selected:        {selected_source} -> {selected_rect}",
        f"window:          {window_rect}",
    ]

    if uia_snapshot is not None:
        lines.extend(
            [
                (
                    "UIA element:      "
                    f"{uia_snapshot.element_rect}"
                ),
                (
                    "UIA runtime id:   "
                    f"{uia_snapshot.runtime_id}"
                ),
                (
                    "UIA previous:     "
                    f"{uia_snapshot.previous_element_rect}"
                ),
                (
                    "UIA same element: "
                    f"{uia_snapshot.same_element_as_previous}"
                ),
                (
                    "UIA element delta:"
                    f" {uia_snapshot.element_delta}"
                ),
            ]
        )

    if uia_error is not None:
        lines.append(
            f"UIA error:       {uia_error}"
        )

    if msaa_error is not None:
        lines.append(
            f"MSAA error:      {msaa_error}"
        )

    print(
        "\n".join(lines),
        flush=True,
    )


def _get_gui_thread_info(
    user32: Any,
) -> GUIThreadInfo | None:
    info = GUIThreadInfo()
    info.cbSize = ctypes.sizeof(
        GUIThreadInfo
    )

    if not user32.GetGUIThreadInfo(
        0,
        ctypes.byref(
            info
        ),
    ):
        return None

    return info


def _get_native_caret_rect(
    user32: Any,
    info: GUIThreadInfo,
) -> Rect | None:
    if not info.hwndCaret:
        return None

    top_left = ctypes.wintypes.POINT(
        info.rcCaret.left,
        info.rcCaret.top,
    )

    bottom_right = (
        ctypes.wintypes.POINT(
            info.rcCaret.right,
            info.rcCaret.bottom,
        )
    )

    if not user32.ClientToScreen(
        info.hwndCaret,
        ctypes.byref(
            top_left
        ),
    ):
        return None

    if not user32.ClientToScreen(
        info.hwndCaret,
        ctypes.byref(
            bottom_right
        ),
    ):
        return None

    insertion_x = max(
        top_left.x,
        bottom_right.x - 1,
    )

    height = max(
        1,
        bottom_right.y
        - top_left.y,
    )

    return Rect(
        x=insertion_x,
        y=top_left.y,
        width=1,
        height=height,
    )


def _get_window_rect(
    user32: Any,
    hwnd: object,
) -> Rect | None:
    native_rect = (
        ctypes.wintypes.RECT()
    )

    if not user32.GetWindowRect(
        hwnd,
        ctypes.byref(
            native_rect
        ),
    ):
        return None

    return Rect(
        x=native_rect.left,
        y=native_rect.top,
        width=max(
            1,
            native_rect.right
            - native_rect.left,
        ),
        height=max(
            1,
            native_rect.bottom
            - native_rect.top,
        ),
    )


def _load_user32() -> Any:
    if sys.platform != "win32":
        raise RuntimeError(
            "Windows foreground context can "
            "only be captured on Windows."
        )

    win_dll = getattr(
        ctypes,
        "WinDLL",
        None,
    )

    if win_dll is None:
        raise RuntimeError(
            "ctypes.WinDLL is unavailable."
        )

    return win_dll(
        "user32",
        use_last_error=True,
    )


def _configure_user32(
    user32: Any,
) -> None:
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = (
        ctypes.wintypes.HWND
    )

    user32.GetGUIThreadInfo.argtypes = [
        ctypes.wintypes.DWORD,
        ctypes.POINTER(
            GUIThreadInfo
        ),
    ]

    user32.GetGUIThreadInfo.restype = (
        ctypes.wintypes.BOOL
    )

    user32.ClientToScreen.argtypes = [
        ctypes.wintypes.HWND,
        ctypes.POINTER(
            ctypes.wintypes.POINT
        ),
    ]

    user32.ClientToScreen.restype = (
        ctypes.wintypes.BOOL
    )

    user32.GetWindowRect.argtypes = [
        ctypes.wintypes.HWND,
        ctypes.POINTER(
            ctypes.wintypes.RECT
        ),
    ]

    user32.GetWindowRect.restype = (
        ctypes.wintypes.BOOL
    )

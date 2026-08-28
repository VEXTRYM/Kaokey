import ctypes
import sys

from typing import Any

# SendInput constants.
INPUT_KEYBOARD = 1

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

EM_GETSEL = 0x00B0
EM_REPLACESEL = 0x00C2
WINDOW_CLASS_BUFFER_SIZE = 256


# Use fixed-width Win32 integer types instead of
# ctypes.wintypes so this module can still be imported
# safely by tests on non-Windows systems.
DWORD = ctypes.c_uint32
WORD = ctypes.c_uint16
LONG = ctypes.c_int32
UINT = ctypes.c_uint32
HWND = ctypes.c_void_p
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
LRESULT = ctypes.c_ssize_t

ULONG_PTR = (
    ctypes.c_uint64
    if ctypes.sizeof(
        ctypes.c_void_p
    ) == 8
    else ctypes.c_uint32
)


class MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", LONG),
        ("dy", LONG),
        ("mouseData", DWORD),
        ("dwFlags", DWORD),
        ("time", DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KeyboardInput(ctypes.Structure):
    _fields_ = [
        ("wVk", WORD),
        ("wScan", WORD),
        ("dwFlags", DWORD),
        ("time", DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HardwareInput(ctypes.Structure):
    _fields_ = [
        ("uMsg", DWORD),
        ("wParamL", WORD),
        ("wParamH", WORD),
    ]


class InputValue(ctypes.Union):
    _fields_ = [
        ("mi", MouseInput),
        ("ki", KeyboardInput),
        ("hi", HardwareInput),
    ]


class Input(ctypes.Structure):
    _anonymous_ = (
        "value",
    )

    _fields_ = [
        ("type", DWORD),
        ("value", InputValue),
    ]



def global_hotkey_keys_released(
    virtual_keys: tuple[int, ...],
) -> bool:
    """Return True when every key used by the active hotkey is released."""
    if sys.platform != "win32":
        return True

    user32 = _load_user32()

    _configure_user32(
        user32
    )

    return all(
        not _async_key_is_down(
            user32.GetAsyncKeyState(
                virtual_key
            )
        )
        for virtual_key in virtual_keys
    )


def _async_key_is_down(
    state: int,
) -> bool:
    # GetAsyncKeyState uses the high-order bit to indicate that the
    # key is physically down at the time of the call.
    return bool(
        int(state)
        & 0x8000
    )


def insert_text_into_native_edit(
    focus_window_handle: int | None,
    text: str,
) -> bool:
    """Insert directly into a standard Windows Edit/RichEdit control."""
    if sys.platform != "win32":
        return False

    if not focus_window_handle:
        return False

    if not text:
        return True

    user32 = _load_user32()
    _configure_user32(user32)

    hwnd = HWND(focus_window_handle)

    if not user32.IsWindow(hwnd):
        return False

    class_name = _get_window_class_name(
        user32,
        hwnd,
    )

    if not is_native_text_control_class(
        class_name
    ):
        return False

    before_selection = _get_edit_selection(
        user32,
        hwnd,
    )

    if before_selection is None:
        return False

    start, _end = before_selection

    text_buffer = ctypes.create_unicode_buffer(
        text
    )

    user32.SendMessageW(
        hwnd,
        EM_REPLACESEL,
        WPARAM(1),
        LPARAM(
            ctypes.addressof(
                text_buffer
            )
        ),
    )

    after_selection = _get_edit_selection(
        user32,
        hwnd,
    )

    if after_selection is None:
        return False

    after_start, after_end = after_selection

    expected_position = (
        start
        + len(
            utf16_code_units(
                text
            )
        )
    )

    return (
        after_start
        == expected_position
        and after_end
        == expected_position
    )


def is_native_text_control_class(
    class_name: str | None,
) -> bool:
    if not class_name:
        return False

    normalized = class_name.casefold()

    return (
        normalized == "edit"
        or normalized.startswith(
            "richedit"
        )
    )


def _get_window_class_name(
    user32: Any,
    hwnd: HWND,
) -> str | None:
    buffer = ctypes.create_unicode_buffer(
        WINDOW_CLASS_BUFFER_SIZE
    )

    length = user32.GetClassNameW(
        hwnd,
        buffer,
        WINDOW_CLASS_BUFFER_SIZE,
    )

    if length <= 0:
        return None

    return buffer.value


def _get_edit_selection(
    user32: Any,
    hwnd: HWND,
) -> tuple[int, int] | None:
    start = DWORD()
    end = DWORD()

    user32.SendMessageW(
        hwnd,
        EM_GETSEL,
        WPARAM(
            ctypes.addressof(
                start
            )
        ),
        LPARAM(
            ctypes.addressof(
                end
            )
        ),
    )

    return (
        int(start.value),
        int(end.value),
    )


def get_foreground_window_handle(
) -> int | None:
    """Return the current Windows foreground HWND without touching focus."""
    if sys.platform != "win32":
        return None

    user32 = _load_user32()

    _configure_user32(
        user32
    )

    hwnd = user32.GetForegroundWindow()

    if not hwnd:
        return None

    return int(
        hwnd
    )

def insert_unicode_text(
    window_handle: int,
    text: str,
) -> bool:
    """Insert text into a previously active Windows window.

    The clipboard is never touched here. False means Windows could not
    activate the target window or did not accept every SendInput event.
    """
    if sys.platform != "win32":
        return False

    if not text:
        return True

    user32 = _load_user32()

    _configure_user32(
        user32
    )

    hwnd = HWND(
        window_handle
    )

    if not user32.IsWindow(
        hwnd
    ):
        return False

    if not user32.SetForegroundWindow(
        hwnd
    ):
        return False

    foreground = (
        user32.GetForegroundWindow()
    )

    if (
        not foreground
        or int(
            foreground
        )
        != window_handle
    ):
        return False

    inputs = build_unicode_inputs(
        text
    )

    if not inputs:
        return True

    input_array_type = (
        Input * len(
            inputs
        )
    )

    input_array = input_array_type(
        *inputs
    )

    sent = user32.SendInput(
        len(
            inputs
        ),
        input_array,
        ctypes.sizeof(
            Input
        ),
    )

    return int(
        sent
    ) == len(
        inputs
    )


def build_unicode_inputs(
    text: str,
) -> list[Input]:
    inputs: list[Input] = []

    for code_unit in utf16_code_units(
        text
    ):
        inputs.append(
            _keyboard_input(
                code_unit,
                KEYEVENTF_UNICODE,
            )
        )

        inputs.append(
            _keyboard_input(
                code_unit,
                (
                    KEYEVENTF_UNICODE
                    | KEYEVENTF_KEYUP
                ),
            )
        )

    return inputs


def utf16_code_units(
    text: str,
) -> list[int]:
    """Return UTF-16 code units required by KEYEVENTF_UNICODE.

    Characters outside the BMP are intentionally returned as surrogate
    pairs because SendInput consumes UTF-16 units rather than Python
    Unicode code points.
    """
    encoded = text.encode(
        "utf-16-le",
        errors="surrogatepass",
    )

    return [
        int.from_bytes(
            encoded[
                index:index + 2
            ],
            "little",
        )
        for index in range(
            0,
            len(
                encoded
            ),
            2,
        )
    ]


def _keyboard_input(
    code_unit: int,
    flags: int,
) -> Input:
    keyboard = KeyboardInput(
        wVk=0,
        wScan=code_unit,
        dwFlags=flags,
        time=0,
        dwExtraInfo=0,
    )

    return Input(
        type=INPUT_KEYBOARD,
        value=InputValue(
            ki=keyboard
        ),
    )


def _load_user32(
) -> Any:
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
    user32.IsWindow.argtypes = [
        HWND,
    ]

    user32.IsWindow.restype = (
        ctypes.c_int
    )

    user32.SetForegroundWindow.argtypes = [
        HWND,
    ]

    user32.SetForegroundWindow.restype = (
        ctypes.c_int
    )

    user32.GetForegroundWindow.argtypes = []

    user32.GetForegroundWindow.restype = (
        HWND
    )

    user32.SendInput.argtypes = [
        UINT,
        ctypes.POINTER(
            Input
        ),
        ctypes.c_int,
    ]

    user32.SendInput.restype = UINT

    user32.GetClassNameW.argtypes = [
        HWND,
        ctypes.POINTER(ctypes.c_wchar),
        ctypes.c_int,
    ]
    user32.GetClassNameW.restype = ctypes.c_int

    user32.SendMessageW.argtypes = [
        HWND,
        UINT,
        WPARAM,
        LPARAM,
    ]
    user32.SendMessageW.restype = LRESULT

    user32.GetAsyncKeyState.argtypes = [
        ctypes.c_int,
    ]

    user32.GetAsyncKeyState.restype = (
        ctypes.c_short
    )

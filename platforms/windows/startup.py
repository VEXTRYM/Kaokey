from pathlib import Path
import ctypes
import os
import subprocess
import sys

from typing import Any


STARTUP_REGISTRY_PATH = (
    r"Software\Microsoft\Windows\CurrentVersion\Run"
)

STARTUP_FOLDER_PARTS = (
    "Microsoft",
    "Windows",
    "Start Menu",
    "Programs",
    "Startup",
)

STARTUP_LAUNCH_ARGUMENT = "--startup"

# COM
COINIT_APARTMENTTHREADED = 0x2
CLSCTX_INPROC_SERVER = 0x1

S_OK = 0
S_FALSE = 1
RPC_E_CHANGED_MODE = -2147417850

# IUnknown vtable
IUNKNOWN_QUERY_INTERFACE_INDEX = 0
IUNKNOWN_RELEASE_INDEX = 2

# IShellLinkW vtable
ISHELLLINK_SET_DESCRIPTION_INDEX = 7
ISHELLLINK_SET_WORKING_DIRECTORY_INDEX = 9
ISHELLLINK_SET_ARGUMENTS_INDEX = 11
ISHELLLINK_SET_ICON_LOCATION_INDEX = 17
ISHELLLINK_SET_PATH_INDEX = 20

# IPersistFile vtable
IPERSISTFILE_SAVE_INDEX = 6


class GUID(
    ctypes.Structure
):
    _fields_ = [
        (
            "Data1",
            ctypes.c_uint32,
        ),
        (
            "Data2",
            ctypes.c_uint16,
        ),
        (
            "Data3",
            ctypes.c_uint16,
        ),
        (
            "Data4",
            ctypes.c_ubyte * 8,
        ),
    ]


CLSID_SHELL_LINK = GUID(
    0x00021401,
    0x0000,
    0x0000,
    (
        ctypes.c_ubyte
        * 8
    )(
        0xC0,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x46,
    ),
)

IID_ISHELL_LINK_W = GUID(
    0x000214F9,
    0x0000,
    0x0000,
    (
        ctypes.c_ubyte
        * 8
    )(
        0xC0,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x46,
    ),
)

IID_IPERSIST_FILE = GUID(
    0x0000010B,
    0x0000,
    0x0000,
    (
        ctypes.c_ubyte
        * 8
    )(
        0xC0,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x46,
    ),
)


def startup_target(
) -> tuple[
    Path,
    str,
    Path,
]:
    """Return target executable, arguments and working directory."""
    if getattr(
        sys,
        "frozen",
        False,
    ):
        executable = Path(
            sys.executable
        )

        return (
            executable,
            STARTUP_LAUNCH_ARGUMENT,
            executable.parent,
        )

    executable = _source_python_executable(
        Path(
            sys.executable
        )
    )

    main_path = (
        Path(
            __file__
        )
        .resolve()
        .parents[2]
        / "main.py"
    )

    return (
        executable,
        subprocess.list2cmdline(
            [
                str(
                    main_path
                ),
                STARTUP_LAUNCH_ARGUMENT,
            ]
        ),
        main_path.parent,
    )


def startup_folder(
) -> Path:
    appdata = os.environ.get(
        "APPDATA"
    )

    if not appdata:
        raise OSError(
            "APPDATA is unavailable."
        )

    return Path(
        appdata
    ).joinpath(
        *STARTUP_FOLDER_PARTS
    )


def startup_shortcut_path(
    app_name: str,
) -> Path:
    return (
        startup_folder()
        / f"{app_name}.lnk"
    )


def is_startup_enabled(
    app_name: str,
) -> bool:
    if sys.platform != "win32":
        return False

    if startup_shortcut_path(
        app_name
    ).exists():
        return True

    return _legacy_registry_entry_exists(
        app_name
    )


def migrate_legacy_startup_entry(
    app_name: str,
    icon_path: Path,
) -> None:
    """Move the old Run-registry startup entry to a named .lnk shortcut."""
    if sys.platform != "win32":
        return

    shortcut_path = startup_shortcut_path(
        app_name
    )

    if shortcut_path.exists():
        # Refresh an existing shortcut too. During development the startup
        # command can evolve between stages (for example adding --startup).
        _create_startup_shortcut(
            app_name,
            icon_path,
        )

        _delete_legacy_registry_entry(
            app_name
        )
        return

    if not _legacy_registry_entry_exists(
        app_name
    ):
        return

    _create_startup_shortcut(
        app_name,
        icon_path,
    )

    _delete_legacy_registry_entry(
        app_name
    )


def set_startup_enabled(
    app_name: str,
    enabled: bool,
    icon_path: Path,
) -> None:
    if sys.platform != "win32":
        raise RuntimeError(
            "Windows startup integration "
            "is only available on Windows."
        )

    shortcut_path = startup_shortcut_path(
        app_name
    )

    if enabled:
        _create_startup_shortcut(
            app_name,
            icon_path,
        )

        _delete_legacy_registry_entry(
            app_name
        )

        return

    try:
        shortcut_path.unlink()

    except FileNotFoundError:
        pass

    _delete_legacy_registry_entry(
        app_name
    )


def _create_startup_shortcut(
    app_name: str,
    icon_path: Path,
) -> None:
    """Create a Windows .lnk directly through IShellLinkW."""
    shortcut_path = startup_shortcut_path(
        app_name
    )

    shortcut_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    executable, arguments, working_directory = (
        startup_target()
    )

    ole32 = _load_ole32()

    initialized = ole32.CoInitializeEx(
        None,
        COINIT_APARTMENTTHREADED,
    )

    if (
        initialized < 0
        and initialized
        != RPC_E_CHANGED_MODE
    ):
        raise OSError(
            "Could not initialize Windows COM "
            f"(HRESULT 0x{initialized & 0xFFFFFFFF:08X})."
        )

    should_uninitialize = (
        initialized
        in {
            S_OK,
            S_FALSE,
        }
    )

    shell_link = ctypes.c_void_p()
    persist_file = ctypes.c_void_p()

    try:
        result = ole32.CoCreateInstance(
            ctypes.byref(
                CLSID_SHELL_LINK
            ),
            None,
            CLSCTX_INPROC_SERVER,
            ctypes.byref(
                IID_ISHELL_LINK_W
            ),
            ctypes.byref(
                shell_link
            ),
        )

        _check_hresult(
            result,
            "Could not create IShellLinkW",
        )

        _shell_link_set_string(
            shell_link,
            ISHELLLINK_SET_PATH_INDEX,
            str(
                executable
            ),
            "Could not set startup target",
        )

        _shell_link_set_string(
            shell_link,
            ISHELLLINK_SET_ARGUMENTS_INDEX,
            arguments,
            "Could not set startup arguments",
        )

        _shell_link_set_string(
            shell_link,
            ISHELLLINK_SET_WORKING_DIRECTORY_INDEX,
            str(
                working_directory
            ),
            "Could not set startup working directory",
        )

        _shell_link_set_string(
            shell_link,
            ISHELLLINK_SET_DESCRIPTION_INDEX,
            app_name,
            "Could not set startup description",
        )

        set_icon_location = _com_method(
            shell_link,
            ISHELLLINK_SET_ICON_LOCATION_INDEX,
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            ctypes.c_int,
        )

        result = set_icon_location(
            shell_link,
            str(
                startup_icon_path(
                    icon_path
                )
            ),
            0,
        )

        _check_hresult(
            result,
            "Could not set startup icon",
        )

        query_interface = _com_method(
            shell_link,
            IUNKNOWN_QUERY_INTERFACE_INDEX,
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.POINTER(
                GUID
            ),
            ctypes.POINTER(
                ctypes.c_void_p
            ),
        )

        result = query_interface(
            shell_link,
            ctypes.byref(
                IID_IPERSIST_FILE
            ),
            ctypes.byref(
                persist_file
            ),
        )

        _check_hresult(
            result,
            "Could not get IPersistFile",
        )

        save = _com_method(
            persist_file,
            IPERSISTFILE_SAVE_INDEX,
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            ctypes.c_int,
        )

        result = save(
            persist_file,
            str(
                shortcut_path
            ),
            1,
        )

        _check_hresult(
            result,
            "Could not save startup shortcut",
        )

    finally:
        if persist_file.value:
            _release_com_object(
                persist_file
            )

        if shell_link.value:
            _release_com_object(
                shell_link
            )

        if should_uninitialize:
            ole32.CoUninitialize()

    if not shortcut_path.exists():
        raise OSError(
            "Windows startup shortcut was not created."
        )



def startup_icon_path(
    bundled_icon_path: Path,
) -> Path:
    """Return an icon path that remains valid after the process exits."""
    if getattr(
        sys,
        "frozen",
        False,
    ):
        # In a one-file build bundled resources live in PyInstaller's
        # temporary extraction directory. A persistent .lnk must therefore
        # use the executable itself, whose Windows icon is permanent.
        return Path(
            sys.executable
        )

    return bundled_icon_path

def _shell_link_set_string(
    shell_link: ctypes.c_void_p,
    method_index: int,
    value: str,
    error_message: str,
) -> None:
    method = _com_method(
        shell_link,
        method_index,
        ctypes.c_long,
        ctypes.c_void_p,
        ctypes.c_wchar_p,
    )

    result = method(
        shell_link,
        value,
    )

    _check_hresult(
        result,
        error_message,
    )


def _com_method(
    interface: ctypes.c_void_p,
    index: int,
    restype: Any,
    *argtypes: Any,
) -> Any:
    if not interface.value:
        raise OSError(
            "COM interface is null."
        )

    vtable_pointer = ctypes.cast(
        interface,
        ctypes.POINTER(
            ctypes.POINTER(
                ctypes.c_void_p
            )
        ),
    )

    address = (
        vtable_pointer.contents[
            index
        ]
    )

    prototype = ctypes.WINFUNCTYPE(
        restype,
        *argtypes,
    )

    return prototype(
        address
    )


def _release_com_object(
    interface: ctypes.c_void_p,
) -> None:
    release = _com_method(
        interface,
        IUNKNOWN_RELEASE_INDEX,
        ctypes.c_ulong,
        ctypes.c_void_p,
    )

    release(
        interface
    )


def _check_hresult(
    result: int,
    message: str,
) -> None:
    if result >= 0:
        return

    raise OSError(
        (
            f"{message}: "
            f"HRESULT 0x{result & 0xFFFFFFFF:08X}"
        )
    )


def _load_ole32() -> Any:
    win_dll = getattr(
        ctypes,
        "WinDLL",
        None,
    )

    if win_dll is None:
        raise RuntimeError(
            "ctypes.WinDLL is unavailable."
        )

    ole32 = win_dll(
        "ole32",
        use_last_error=True,
    )

    ole32.CoInitializeEx.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
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
        ctypes.c_uint32,
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

    return ole32


def _legacy_registry_entry_exists(
    app_name: str,
) -> bool:
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            STARTUP_REGISTRY_PATH,
            0,
            winreg.KEY_READ,
        ) as key:
            value, _value_type = (
                winreg.QueryValueEx(
                    key,
                    app_name,
                )
            )

    except FileNotFoundError:
        return False

    return isinstance(
        value,
        str,
    )


def _delete_legacy_registry_entry(
    app_name: str,
) -> None:
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            STARTUP_REGISTRY_PATH,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.DeleteValue(
                key,
                app_name,
            )

    except FileNotFoundError:
        return


def _source_python_executable(
    executable: Path,
) -> Path:
    """Prefer pythonw.exe for source-mode autostart to avoid a console."""
    if (
        sys.platform == "win32"
        and executable.name.casefold()
        == "python.exe"
    ):
        pythonw = executable.with_name(
            "pythonw.exe"
        )

        if pythonw.exists():
            return pythonw

    return executable

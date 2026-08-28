from pathlib import Path

from platforms.windows.startup import (
    STARTUP_FOLDER_PARTS,
    _source_python_executable,
)


def test_startup_folder_is_windows_startup_folder():
    assert STARTUP_FOLDER_PARTS == (
        "Microsoft",
        "Windows",
        "Start Menu",
        "Programs",
        "Startup",
    )


def test_non_python_executable_is_kept():
    executable = Path(
        "C:/Apps/Kaokey/Kaokey.exe"
    )

    assert _source_python_executable(
        executable
    ) == executable

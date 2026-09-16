from pathlib import Path

from kaokey.platforms.windows.startup import (
    _source_python_executable,
)


def test_non_python_executable_is_kept():
    executable = Path("C:/Apps/Kaokey/Kaokey.exe")

    assert _source_python_executable(executable) == executable

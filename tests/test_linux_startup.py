from pathlib import Path

import pytest

from kaokey.config.constants import APPLICATION_ID
from kaokey.platforms.linux import startup
from kaokey.platforms.startup import STARTUP_LAUNCH_ARGUMENT


def test_xdg_autostart_enable_refresh_and_disable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    executable = tmp_path / "My App%" / "kaokey"
    working_directory = tmp_path / "working directory"
    monkeypatch.setattr(
        startup,
        "_startup_target",
        lambda: (executable, (STARTUP_LAUNCH_ARGUMENT,), working_directory),
    )
    backend = startup.LinuxStartupBackend()
    entry = tmp_path / "autostart" / f"{APPLICATION_ID}.desktop"

    backend.initialize("Kaokey", tmp_path / "unused.png")
    assert not entry.exists()

    backend.set_enabled("Kaokey", True, tmp_path / "unused.png")
    contents = entry.read_text(encoding="utf-8")
    assert contents.startswith("[Desktop Entry]\nType=Application\nName=Kaokey\n")
    assert f"Path={working_directory}\n" in contents
    assert STARTUP_LAUNCH_ARGUMENT in contents
    assert "%%" in next(line for line in contents.splitlines() if line.startswith("Exec="))
    assert backend.is_enabled("Kaokey")

    backend.initialize("Kaokey Updated", tmp_path / "unused.png")
    assert "Name=Kaokey Updated\n" in entry.read_text(encoding="utf-8")

    backend.set_enabled("Kaokey", False, tmp_path / "unused.png")
    assert not entry.exists()
    assert not backend.is_enabled("Kaokey")

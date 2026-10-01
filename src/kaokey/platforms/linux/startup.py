import os
import sys
from pathlib import Path

from kaokey.config.constants import (
    APPLICATION_ID,
    LINUX_DESKTOP_ICON_NAME,
)
from kaokey.platforms.startup import (
    STARTUP_LAUNCH_ARGUMENT,
)

AUTOSTART_DIRECTORY_NAME = "autostart"


class LinuxStartupBackend:
    """XDG Autostart implementation shared by X11 and Wayland."""

    @property
    def available(
        self,
    ) -> bool:
        return True

    def initialize(
        self,
        app_name: str,
        icon_path: Path,
    ) -> None:
        del icon_path

        # Refresh an existing entry without enabling autostart by itself.
        if self._entry_path().exists():
            self._write_entry(app_name)

    def is_enabled(
        self,
        app_name: str,
    ) -> bool:
        del app_name
        return self._entry_path().is_file()

    def set_enabled(
        self,
        app_name: str,
        enabled: bool,
        icon_path: Path,
    ) -> None:
        del icon_path
        entry_path = self._entry_path()

        if enabled:
            self._write_entry(app_name)
            return

        try:
            entry_path.unlink()
        except FileNotFoundError:
            pass

    def _write_entry(
        self,
        app_name: str,
    ) -> None:
        entry_path = self._entry_path()
        entry_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        executable, arguments, working_directory = _startup_target()
        entry_path.write_text(
            _desktop_entry(
                app_name,
                executable,
                arguments,
                working_directory,
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _entry_path() -> Path:
        return (
            _xdg_config_home()
            / AUTOSTART_DIRECTORY_NAME
            / f"{APPLICATION_ID}.desktop"
        )


def _xdg_config_home() -> Path:
    configured = os.environ.get("XDG_CONFIG_HOME")

    if configured:
        return Path(configured).expanduser()

    return Path.home() / ".config"


def _startup_target() -> tuple[
    Path,
    tuple[str, ...],
    Path,
]:
    """Return executable, arguments and working directory for autostart."""
    if getattr(
        sys,
        "frozen",
        False,
    ):
        executable = Path(sys.executable)
        return (
            executable,
            (STARTUP_LAUNCH_ARGUMENT,),
            executable.parent,
        )

    source_root = Path(__file__).resolve().parents[3]

    return (
        Path(sys.executable),
        (
            "-m",
            "kaokey.main",
            STARTUP_LAUNCH_ARGUMENT,
        ),
        source_root,
    )


def _desktop_entry(
    app_name: str,
    executable: Path,
    arguments: tuple[str, ...],
    working_directory: Path,
) -> str:
    exec_line = " ".join(
        _quote_exec_token(token)
        for token in (
            str(executable),
            *arguments,
        )
    )

    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={app_name}\n"
        f"Exec={exec_line}\n"
        f"Path={working_directory}\n"
        f"Icon={LINUX_DESKTOP_ICON_NAME}\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


def _quote_exec_token(
    value: str,
) -> str:
    """Quote one token according to Desktop Entry Exec field rules."""
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("`", "\\`")
        .replace("$", "\\$")
        .replace("%", "%%")
    )

    return f'"{escaped}"'

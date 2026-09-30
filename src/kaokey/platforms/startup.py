import sys
from pathlib import Path
from typing import Protocol

STARTUP_LAUNCH_ARGUMENT = "--startup"


class StartupBackend(Protocol):
    """Platform services used by the Start with system setting."""

    @property
    def available(
        self,
    ) -> bool: ...

    def initialize(
        self,
        app_name: str,
        icon_path: Path,
    ) -> None: ...

    def is_enabled(
        self,
        app_name: str,
    ) -> bool: ...

    def set_enabled(
        self,
        app_name: str,
        enabled: bool,
        icon_path: Path,
    ) -> None: ...


class UnavailableStartupBackend:
    """Fallback for platforms without startup integration."""

    @property
    def available(
        self,
    ) -> bool:
        return False

    def initialize(
        self,
        app_name: str,
        icon_path: Path,
    ) -> None:
        del app_name, icon_path

    def is_enabled(
        self,
        app_name: str,
    ) -> bool:
        del app_name
        return False

    def set_enabled(
        self,
        app_name: str,
        enabled: bool,
        icon_path: Path,
    ) -> None:
        del app_name, enabled, icon_path
        raise RuntimeError(
            "Startup integration is unavailable on this platform."
        )


def create_startup_backend() -> StartupBackend:
    """Create the startup integration for the current platform."""
    if sys.platform == "win32":
        from kaokey.platforms.windows.startup import (
            WindowsStartupBackend,
        )

        return WindowsStartupBackend()

    return UnavailableStartupBackend()

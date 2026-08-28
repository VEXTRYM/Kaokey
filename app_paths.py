from collections.abc import Mapping
from pathlib import Path
import os
import sys


USER_DATA_OVERRIDE_ENV = "KAOKEY_USER_DATA_DIR"


def resource_root(
) -> Path:
    """Return the directory containing bundled read-only resources."""
    bundled_root = getattr(
        sys,
        "_MEIPASS",
        None,
    )

    if bundled_root:
        return Path(
            bundled_root
        )

    return Path(
        __file__
    ).resolve().parent


def user_data_dir(
    app_name: str,
) -> Path:
    """Return a writable per-user data directory for the current OS."""
    override = os.environ.get(
        USER_DATA_OVERRIDE_ENV
    )

    if override:
        return Path(
            override
        ).expanduser()

    return resolve_user_data_dir(
        app_name=app_name,
        platform=sys.platform,
        environ=os.environ,
        home=Path.home(),
    )


def resolve_user_data_dir(
    app_name: str,
    platform: str,
    environ: Mapping[str, str],
    home: Path,
) -> Path:
    """Pure platform path resolver used by user_data_dir() and tests."""
    if platform == "win32":
        appdata = environ.get(
            "APPDATA"
        )

        if appdata:
            return (
                Path(
                    appdata
                )
                / app_name
            )

        return (
            home
            / "AppData"
            / "Roaming"
            / app_name
        )

    if platform == "darwin":
        return (
            home
            / "Library"
            / "Application Support"
            / app_name
        )

    xdg_data_home = environ.get(
        "XDG_DATA_HOME"
    )

    if xdg_data_home:
        return (
            Path(
                xdg_data_home
            )
            / app_name
        )

    return (
        home
        / ".local"
        / "share"
        / app_name
    )

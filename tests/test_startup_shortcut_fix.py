from pathlib import Path

from platforms.windows.startup import (
    STARTUP_FOLDER_PARTS,
    startup_shortcut_path,
)


def test_startup_folder_components():
    assert STARTUP_FOLDER_PARTS == (
        "Microsoft",
        "Windows",
        "Start Menu",
        "Programs",
        "Startup",
    )


def test_shortcut_name_uses_application_name(
    monkeypatch,
):
    monkeypatch.setenv(
        "APPDATA",
        "C:/Users/Test/AppData/Roaming",
    )

    path = startup_shortcut_path(
        "Kaokey"
    )

    assert path.name == "Kaokey.lnk"

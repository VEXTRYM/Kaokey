from pathlib import Path

from app_paths import resolve_user_data_dir


def test_windows_user_data_path_uses_appdata():
    path = resolve_user_data_dir(
        app_name="Kaokey",
        platform="win32",
        environ={
            "APPDATA": "C:/Users/Test/AppData/Roaming",
        },
        home=Path("C:/Users/Test"),
    )

    assert path == Path(
        "C:/Users/Test/AppData/Roaming/Kaokey"
    )


def test_linux_user_data_path_uses_xdg_data_home():
    path = resolve_user_data_dir(
        app_name="Kaokey",
        platform="linux",
        environ={
            "XDG_DATA_HOME": "/tmp/user-data",
        },
        home=Path("/home/test"),
    )

    assert path == Path(
        "/tmp/user-data/Kaokey"
    )


def test_linux_user_data_path_has_standard_fallback():
    path = resolve_user_data_dir(
        app_name="Kaokey",
        platform="linux",
        environ={},
        home=Path("/home/test"),
    )

    assert path == Path(
        "/home/test/.local/share/Kaokey"
    )

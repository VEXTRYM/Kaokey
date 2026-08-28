from pathlib import Path

from platforms.windows.startup import startup_icon_path


def test_source_mode_uses_bundled_icon_path():
    icon = Path("C:/Project/resources/icons/kaokey.ico")
    assert startup_icon_path(icon) == icon

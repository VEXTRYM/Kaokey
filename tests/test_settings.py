from typing import Any

import pytest

from kaokey.config.constants import (
    SETTINGS_ADD_SPACE_AFTER_INSERT_KEY,
    SETTINGS_HOTKEY_KEY,
    SETTINGS_HOTKEY_MODIFIER_KEY,
    SETTINGS_LANGUAGE_KEY,
    SETTINGS_POPUP_X_KEY,
    SETTINGS_POPUP_Y_KEY,
    SETTINGS_SHOW_HINTS_KEY,
    SETTINGS_WINDOW_HEIGHT_KEY,
    SETTINGS_WINDOW_WIDTH_KEY,
)
from kaokey.config.settings import SettingsManager
from kaokey.ui.styling.style_constants import (
    WINDOW_MAX_WIDTH,
    WINDOW_MIN_HEIGHT,
)


class MemorySettings:
    def __init__(self) -> None:
        self.values: dict[str, Any] = {}
        self.sync_count = 0

    def value(
        self, key: str, defaultValue: Any = None, type: Any = None, /
    ) -> Any:
        del type
        return self.values.get(key, defaultValue)

    def setValue(self, key: str, value: Any, /) -> None:
        self.values[key] = value

    def remove(self, key: str, /) -> None:
        self.values.pop(key, None)

    def sync(self) -> None:
        self.sync_count += 1


def test_settings_parse_saved_strings_and_clamp_window_size() -> None:
    store = MemorySettings()
    store.values.update({
        SETTINGS_SHOW_HINTS_KEY: " off ",
        SETTINGS_ADD_SPACE_AFTER_INSERT_KEY: "YES",
        SETTINGS_WINDOW_WIDTH_KEY: "999999",
        SETTINGS_WINDOW_HEIGHT_KEY: "-50",
        SETTINGS_LANGUAGE_KEY: " ru ",
        SETTINGS_POPUP_X_KEY: "120",
        SETTINGS_POPUP_Y_KEY: "-20",
    })
    settings = SettingsManager(store)

    assert settings.show_hints is False
    assert settings.add_space_after_insert is True
    assert settings.window_size == (WINDOW_MAX_WIDTH, WINDOW_MIN_HEIGHT)
    assert settings.language == "ru"
    assert settings.popup_position == (120, -20)

    store.values[SETTINGS_WINDOW_WIDTH_KEY] = True
    store.values[SETTINGS_POPUP_Y_KEY] = "invalid"
    assert settings.window_size[0] != 1  # bool is not accepted as a width
    assert settings.popup_position is None


def test_invalid_hotkey_does_not_partially_write_settings() -> None:
    store = MemorySettings()
    settings = SettingsManager(store)
    original = settings.hotkey

    with pytest.raises(ValueError, match="modifier"):
        settings.set_hotkey("Meta", "K")
    with pytest.raises(ValueError, match="key"):
        settings.set_hotkey("Ctrl", "Emoji")
    assert settings.hotkey == original
    assert SETTINGS_HOTKEY_MODIFIER_KEY not in store.values
    assert SETTINGS_HOTKEY_KEY not in store.values
    assert store.sync_count == 0

    settings.set_hotkey("Ctrl", "F12")
    assert settings.hotkey == ("Ctrl", "F12")
    assert store.sync_count == 1


def test_settings_setters_persist_normalized_values() -> None:
    store = MemorySettings()
    settings = SettingsManager(store)
    settings.language = "  ja  "
    settings.show_hints = False
    settings.set_popup_position(48, -12)

    assert store.values[SETTINGS_LANGUAGE_KEY] == "ja"
    assert store.values[SETTINGS_SHOW_HINTS_KEY] is False
    assert settings.popup_position == (48, -12)
    assert store.sync_count == 3

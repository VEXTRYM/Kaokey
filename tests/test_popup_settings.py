from constants import (
    SETTINGS_POPUP_X_KEY,
    SETTINGS_POPUP_Y_KEY,
)
from settings import SettingsManager


class MemorySettingsStore:
    def __init__(self) -> None:
        self.data: dict[str, object] = {}
        self.synced = 0

    def value(
        self,
        key: str,
        defaultValue: object = None,
        type: object = None,
    ) -> object:
        return self.data.get(
            key,
            defaultValue,
        )

    def setValue(
        self,
        key: str,
        value: object,
    ) -> None:
        self.data[key] = value

    def sync(self) -> None:
        self.synced += 1


def test_popup_position_defaults_to_none() -> None:
    settings = SettingsManager(
        MemorySettingsStore()
    )

    assert settings.popup_position is None


def test_popup_position_round_trip() -> None:
    store = MemorySettingsStore()
    settings = SettingsManager(store)

    settings.set_popup_position(
        -500,
        240,
    )

    assert settings.popup_position == (
        -500,
        240,
    )

    assert store.data[
        SETTINGS_POPUP_X_KEY
    ] == -500

    assert store.data[
        SETTINGS_POPUP_Y_KEY
    ] == 240

    assert store.synced == 1


def test_popup_position_accepts_qsettings_string_values() -> None:
    store = MemorySettingsStore()
    store.data[
        SETTINGS_POPUP_X_KEY
    ] = "120"
    store.data[
        SETTINGS_POPUP_Y_KEY
    ] = "340"

    settings = SettingsManager(store)

    assert settings.popup_position == (
        120,
        340,
    )


def test_popup_position_requires_both_coordinates() -> None:
    store = MemorySettingsStore()
    store.data[
        SETTINGS_POPUP_X_KEY
    ] = 120

    settings = SettingsManager(store)

    assert settings.popup_position is None

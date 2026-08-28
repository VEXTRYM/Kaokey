from pathlib import Path

from constants import (
    SETTINGS_LANGUAGE_KEY,
    SETTINGS_SHOW_HINTS_KEY,
    SYSTEM_LANGUAGE,
)
from i18n import (
    discover_translation_languages,
    language_code,
    resolve_language_preference,
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


def test_settings_defaults() -> None:
    store = MemorySettingsStore()
    settings = SettingsManager(store)

    assert settings.language == SYSTEM_LANGUAGE
    assert settings.show_hints is True


def test_settings_language_round_trip() -> None:
    store = MemorySettingsStore()
    settings = SettingsManager(store)

    settings.language = "ru"

    assert settings.language == "ru"
    assert store.data[
        SETTINGS_LANGUAGE_KEY
    ] == "ru"
    assert store.synced == 1


def test_blank_language_becomes_system() -> None:
    store = MemorySettingsStore()
    settings = SettingsManager(store)

    settings.language = "   "

    assert settings.language == SYSTEM_LANGUAGE


def test_show_hints_accepts_saved_string_false() -> None:
    store = MemorySettingsStore()
    store.data[
        SETTINGS_SHOW_HINTS_KEY
    ] = "false"

    settings = SettingsManager(store)

    assert settings.show_hints is False


def test_show_hints_round_trip() -> None:
    store = MemorySettingsStore()
    settings = SettingsManager(store)

    settings.show_hints = False

    assert settings.show_hints is False
    assert store.synced == 1


def test_language_code_uses_language_part() -> None:
    assert language_code("ru_RU") == "ru"
    assert language_code("pt-BR") == "pt"
    assert language_code("JA_jp") == "ja"


def test_system_language_uses_system_locale() -> None:
    assert (
        resolve_language_preference(
            "system",
            "ru_RU",
        )
        == "ru"
    )


def test_explicit_language_ignores_system_locale() -> None:
    assert (
        resolve_language_preference(
            "ja",
            "ru_RU",
        )
        == "ja"
    )


def test_discover_translation_languages(
    tmp_path: Path,
) -> None:
    (
        tmp_path / "kaokey_ru.qm"
    ).touch()
    (
        tmp_path / "kaokey_ja.qm"
    ).touch()
    (
        tmp_path / "something_else.qm"
    ).touch()

    assert discover_translation_languages(
        tmp_path
    ) == [
        "en",
        "ja",
        "ru",
    ]

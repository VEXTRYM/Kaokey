import json
from pathlib import Path

import pytest

from kaokey.config.app_paths import resolve_user_data_dir
from kaokey.config.i18n import (
    discover_translation_languages,
    language_code,
    resolve_language_preference,
)
from kaokey.core import constructor_symbols
from kaokey.ui.layout.responsive_layout import columns_for_width


def test_data_path_resolves_for_each_desktop_platform(tmp_path: Path) -> None:
    assert resolve_user_data_dir(
        "Kaokey", "win32", {"APPDATA": str(tmp_path / "roaming")}, tmp_path
    ) == tmp_path / "roaming" / "Kaokey"
    assert resolve_user_data_dir(
        "Kaokey", "linux", {"XDG_DATA_HOME": str(tmp_path / "data")}, tmp_path
    ) == tmp_path / "data" / "Kaokey"
    assert resolve_user_data_dir("Kaokey", "darwin", {}, tmp_path) == (
        tmp_path / "Library" / "Application Support" / "Kaokey"
    )
    assert resolve_user_data_dir("Kaokey", "linux", {}, tmp_path) == (
        tmp_path / ".local" / "share" / "Kaokey"
    )


def test_language_resolution_and_translation_discovery(tmp_path: Path) -> None:
    (tmp_path / "kaokey_ru_RU.qm").touch()
    (tmp_path / "kaokey_ja.qm").touch()
    (tmp_path / "unrelated_fr.qm").touch()

    assert language_code(" PT-BR ") == "pt"
    assert resolve_language_preference("system", "ru_RU") == "ru"
    assert resolve_language_preference("JA-jp", "ru_RU") == "ja"
    assert discover_translation_languages(tmp_path) == ["en", "ja", "ru"]


def test_constructor_symbols_deduplicates_and_rejects_malformed_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "symbols.json"
    monkeypatch.setattr(constructor_symbols, "CONSTRUCTOR_SYMBOLS_PATH", path)
    path.write_text(json.dumps({"Eyes": ["•", "•", "◕"]}), encoding="utf-8")
    assert constructor_symbols.load_constructor_symbols() == {"Eyes": ["•", "◕"]}

    path.write_text(json.dumps({"Eyes": ["•", ""]}), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid constructor symbol"):
        constructor_symbols.load_constructor_symbols()


def test_grid_column_count_handles_narrow_width_and_spacing() -> None:
    assert columns_for_width(0, 100, 10) == 1
    assert columns_for_width(210, 100, 10) == 2
    assert columns_for_width(320, 100, 10) == 3
    with pytest.raises(ValueError, match="positive"):
        columns_for_width(300, 0, 10)

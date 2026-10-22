import json
from pathlib import Path

import pytest

from kaokey.config.constants import DATA_FORMAT_VERSION, DEFAULT_LIST_NAME
from kaokey.core.models import KaomojiList
from kaokey.persistence import storage
from kaokey.persistence.list_io import export_kaomoji_list, import_kaomoji_list


@pytest.fixture
def user_data_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "profile" / "kaomoji.json"
    seed = tmp_path / "seed.json"
    ensure = storage.ensure_user_data_file
    monkeypatch.setattr(storage, "DATA_PATH", path)
    monkeypatch.setattr(storage, "ensure_user_data_file", lambda: ensure(path, seed))
    return path


@pytest.mark.parametrize(
    "legacy_data",
    [
        [{"name": "Wave", "text": "(^_^)", "tags": ["happy"]}],
        {"main_tags": ["happy"], "kaomoji": [
            {"name": "Wave", "text": "(^_^)", "tags": ["happy"]}
        ]},
    ],
)
def test_legacy_library_is_migrated_and_persisted(
    user_data_file: Path,
    legacy_data: object,
) -> None:
    user_data_file.parent.mkdir(parents=True)
    user_data_file.write_text(json.dumps(legacy_data), encoding="utf-8")

    data = storage.load_data()
    assert data["format_version"] == DATA_FORMAT_VERSION
    assert data["active_list"] == DEFAULT_LIST_NAME
    assert data["lists"][0]["kaomoji"][0]["text"] == "(^_^)"
    assert json.loads(user_data_file.read_text(encoding="utf-8")) == data


def test_library_repairs_invalid_active_list_without_losing_items(
    user_data_file: Path,
) -> None:
    data = storage.create_default_data()
    data["active_list"] = "Missing"
    data["lists"][0]["kaomoji"].append(
        {"name": "Saved", "text": "(o_o)", "tags": []}
    )
    user_data_file.parent.mkdir(parents=True)
    user_data_file.write_text(json.dumps(data), encoding="utf-8")

    loaded = storage.load_data()
    assert loaded["active_list"] == DEFAULT_LIST_NAME
    assert loaded["lists"][0]["kaomoji"][0]["name"] == "Saved"
    assert json.loads(user_data_file.read_text(encoding="utf-8")) == loaded


def test_atomic_save_keeps_previous_library_if_replace_fails(
    user_data_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_data_file.parent.mkdir(parents=True)
    user_data_file.write_text("previous library", encoding="utf-8")

    def fail_replace(source: object, target: object) -> None:
        del source, target
        raise OSError("disk error")

    monkeypatch.setattr(storage.os, "replace", fail_replace)
    with pytest.raises(OSError, match="disk error"):
        storage.save_data(storage.create_default_data())
    assert user_data_file.read_text(encoding="utf-8") == "previous library"
    assert not user_data_file.with_name("kaomoji.json.tmp").exists()


def test_export_import_roundtrip_resets_favorites(tmp_path: Path) -> None:
    source: KaomojiList = {
        "name": "Faces",
        "main_tags": ["cute"],
        "kaomoji": [{
            "name": "Wave", "text": "(ﾉ◕ヮ◕)ﾉ", "tags": ["cute"],
            "favorite": True, "favorite_order": 8,
        }],
    }
    path = export_kaomoji_list(str(tmp_path / "faces"), source)
    imported = import_kaomoji_list(str(path))

    assert path.suffix == ".json"
    assert imported["name"] == "Faces"
    assert imported["kaomoji"][0]["text"] == "(ﾉ◕ヮ◕)ﾉ"
    assert imported["kaomoji"][0].get("favorite") is False
    assert "favorite_order" not in imported["kaomoji"][0]
    assert source["kaomoji"][0].get("favorite") is True


def test_import_rejects_ambiguous_and_duplicate_data(tmp_path: Path) -> None:
    path = tmp_path / "import.json"
    one_list = {
        "name": "Faces", "main_tags": [],
        "kaomoji": [{"name": "Wave", "text": "(^_^)", "tags": []}],
    }
    path.write_text(json.dumps({
        "format_version": DATA_FORMAT_VERSION,
        "lists": [one_list, one_list],
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="only one list"):
        import_kaomoji_list(str(path))

    duplicate_items = dict(one_list)
    duplicate_items["kaomoji"] = [
        one_list["kaomoji"][0],
        {"name": "wave", "text": "(o_o)", "tags": []},
    ]
    path.write_text(json.dumps({
        "format_version": DATA_FORMAT_VERSION,
        "type": "kaokey_list",
        "list": duplicate_items,
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate kaomoji name"):
        import_kaomoji_list(str(path))

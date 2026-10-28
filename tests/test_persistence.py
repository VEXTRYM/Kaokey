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
    "unsupported_data",
    [
        [{"name": "Wave", "text": "(^_^)", "tags": ["happy"]}],
        {"main_tags": ["happy"], "kaomoji": [
            {"name": "Wave", "text": "(^_^)", "tags": ["happy"]}
        ]},
        {"format_version": DATA_FORMAT_VERSION + 1,
         "active_list": DEFAULT_LIST_NAME, "lists": []},
        {"format_version": DATA_FORMAT_VERSION,
         "active_list": DEFAULT_LIST_NAME},
        {"format_version": DATA_FORMAT_VERSION,
         "active_list": DEFAULT_LIST_NAME, "lists": {}},
        {"format_version": DATA_FORMAT_VERSION,
         "active_list": DEFAULT_LIST_NAME,
         "lists": [{"name": DEFAULT_LIST_NAME, "main_tags": [], "kaomoji": [
             {"text": "(^_^)", "tags": []}
         ]}]},
    ],
)
def test_unsupported_library_formats_are_rejected_without_rewriting(
    user_data_file: Path,
    unsupported_data: object,
) -> None:
    user_data_file.parent.mkdir(parents=True)
    original = json.dumps(unsupported_data)
    user_data_file.write_text(original, encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid Kaokey library format"):
        storage.load_data()

    assert user_data_file.read_text(encoding="utf-8") == original


def test_current_library_loads_without_rewriting(user_data_file: Path) -> None:
    data = storage.create_default_data()
    data["lists"][0]["kaomoji"].append(
        {"name": "Wave", "text": "(^_^)", "tags": ["happy"]}
    )
    user_data_file.parent.mkdir(parents=True)
    original = json.dumps(data)
    user_data_file.write_text(original, encoding="utf-8")

    assert storage.load_data() == data
    assert user_data_file.read_text(encoding="utf-8") == original

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
    exported_data = json.loads(path.read_text(encoding="utf-8"))

    assert exported_data["format_version"] == DATA_FORMAT_VERSION
    assert exported_data["active_list"] == "Faces"
    assert exported_data["lists"] == [{
        "name": "Faces",
        "main_tags": ["cute"],
        "kaomoji": [{
            "name": "Wave", "text": "(ﾉ◕ヮ◕)ﾉ",
            "tags": ["cute"], "favorite": False,
        }],
    }]
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
        "active_list": "Faces",
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
        "active_list": "Faces",
        "lists": [duplicate_items],
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate kaomoji name"):
        import_kaomoji_list(str(path))

@pytest.mark.parametrize(
    "invalid_export",
    [
        {"format_version": DATA_FORMAT_VERSION, "type": "kaokey_list",
         "list": {"name": "Old", "main_tags": [], "kaomoji": []}},
        {"name": "Old", "main_tags": [], "kaomoji": []},
    ],
)
def test_import_rejects_legacy_list_exports(
    tmp_path: Path,
    invalid_export: object,
) -> None:
    path = tmp_path / "old.json"
    path.write_text(json.dumps(invalid_export), encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid Kaokey library format"):
        import_kaomoji_list(str(path))

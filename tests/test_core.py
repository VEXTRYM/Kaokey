import json
from pathlib import Path

from library import (
    add_imported_list,
    create_empty_list,
    create_kaomoji_list,
    delete_kaomoji_list,
    merge_kaomoji_lists,
    rename_kaomoji_list,
)
from list_io import import_kaomoji_list
from models import KaokeyData, KaomojiList


def write_import_file(path: Path, kaomoji_list: KaomojiList) -> None:
    payload = {
        "format_version": 1,
        "type": "kaokey_list",
        "list": kaomoji_list,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def make_data() -> KaokeyData:
    return {
        "format_version": 1,
        "active_list": "Default",
        "lists": [create_empty_list("Default")],
    }


def test_import_keeps_all_kaomoji(tmp_path: Path) -> None:
    imported: KaomojiList = {
        "name": "Animals",
        "main_tags": ["cat"],
        "kaomoji": [
            {"name": "one", "text": "(=^･ω･^=)", "tags": ["cat"]},
            {"name": "two", "text": "ฅ^•ﻌ•^ฅ", "tags": ["cat"]},
            {"name": "three", "text": "(=①ω①=)", "tags": ["cat"]},
        ],
    }
    path = tmp_path / "animals.json"
    write_import_file(path, imported)

    result = import_kaomoji_list(str(path))

    assert len(result["kaomoji"]) == 3
    assert [item["name"] for item in result["kaomoji"]] == [
        "one",
        "two",
        "three",
    ]


def test_import_resets_favorites(tmp_path: Path) -> None:
    imported: KaomojiList = {
        "name": "Animals",
        "main_tags": [],
        "kaomoji": [
            {
                "name": "cat",
                "text": "ฅ^•ﻌ•^ฅ",
                "tags": [],
                "favorite": True,
                "favorite_order": 99,
            }
        ],
    }
    path = tmp_path / "favorites.json"
    write_import_file(path, imported)

    result = import_kaomoji_list(str(path))
    item = result["kaomoji"][0]

    assert item["favorite"] is False
    assert "favorite_order" not in item


def test_add_imported_list_renames_conflicting_list() -> None:
    data = make_data()
    imported: KaomojiList = {
        "name": "Default",
        "main_tags": [],
        "kaomoji": [],
    }

    new_list = add_imported_list(data, imported)

    assert new_list["name"] == "Default(1)"
    assert len(data["lists"]) == 2


def test_merge_skips_duplicate_text_and_renames_name_conflict() -> None:
    current: KaomojiList = {
        "name": "Current",
        "main_tags": ["cute"],
        "kaomoji": [
            {"name": "cat", "text": "same", "tags": [], "favorite": False}
        ],
    }
    imported: KaomojiList = {
        "name": "Imported",
        "main_tags": ["cute", "happy"],
        "kaomoji": [
            {"name": "ignored", "text": "same", "tags": []},
            {"name": "cat", "text": "new", "tags": [], "favorite": True},
        ],
    }

    report = merge_kaomoji_lists(current, imported)

    assert report == {"added": 1, "main_tags_added": 1}
    assert len(current["kaomoji"]) == 2
    added = current["kaomoji"][1]
    assert added["name"] == "cat(1)"
    assert added["favorite"] is False
    assert current["main_tags"] == ["cute", "happy"]


def test_list_names_are_case_insensitive() -> None:
    data = make_data()

    create_kaomoji_list(data, "Animals")
    rename_kaomoji_list(data, "Animals", "animals")

    assert data["lists"][1]["name"] == "animals"


def test_delete_last_list_creates_new_list() -> None:
    data = make_data()

    delete_kaomoji_list(data, "Default")

    assert len(data["lists"]) == 1
    assert data["lists"][0]["name"] == "New List"
    assert data["active_list"] == "New List"

from copy import deepcopy

import pytest

from kaokey.application.app_state import AppState
from kaokey.config.constants import MAX_MAIN_TAGS
from kaokey.core.kaomoji_search import matches_kaomoji_search
from kaokey.core.library import (
    add_imported_list,
    create_kaomoji_list,
    delete_kaomoji_list,
    get_active_list,
    get_list_names,
    merge_kaomoji_lists,
    rename_kaomoji_list,
    set_active_list,
)
from kaokey.core.models import KaokeyData, Kaomoji, KaomojiList
from kaokey.persistence.storage import create_default_data


def test_list_lifecycle_preserves_a_valid_active_list() -> None:
    data = create_default_data()
    animals = create_kaomoji_list(data, " Animals ")
    assert animals["name"] == "Animals"
    with pytest.raises(ValueError, match="already exists"):
        create_kaomoji_list(data, "animals")

    set_active_list(data, "ANIMALS")
    assert get_active_list(data) is animals
    assert get_list_names(data) == ["Animals", "Default"]

    rename_kaomoji_list(data, "animals", "animals")
    assert data["active_list"] == "animals"
    delete_kaomoji_list(data, "animals")
    assert data["active_list"] == "Default"
    delete_kaomoji_list(data, "Default")
    assert len(data["lists"]) == 1
    assert get_active_list(data) is data["lists"][0]


def test_merge_deduplicates_text_and_copies_imported_items() -> None:
    current: KaomojiList = {
        "name": "Current",
        "main_tags": ["cute"],
        "kaomoji": [{"name": "Wave", "text": "(^_^)", "tags": []}],
    }
    imported: KaomojiList = {
        "name": "Imported",
        "main_tags": ["cute", "happy"],
        "kaomoji": [
            {"name": "Duplicate", "text": "(^_^)", "tags": []},
            {
                "name": "wave",
                "text": "(o_o)",
                "tags": ["happy"],
                "favorite": True,
                "favorite_order": 9,
            },
        ],
    }
    original = deepcopy(imported)

    assert merge_kaomoji_lists(current, imported) == {
        "added": 1,
        "main_tags_added": 1,
    }
    assert [item["text"] for item in current["kaomoji"]] == ["(^_^)", "(o_o)"]
    added = current["kaomoji"][1]
    assert added["name"] == "wave(1)"
    assert added.get("favorite") is False
    assert "favorite_order" not in added
    assert current["main_tags"] == ["cute", "happy"]
    assert imported == original


def test_imported_list_is_independent_and_gets_a_unique_name() -> None:
    data = create_default_data()
    incoming: KaomojiList = {
        "name": "default",
        "main_tags": [],
        "kaomoji": [{
            "name": "Favorite",
            "text": "(^_^)",
            "tags": [],
            "favorite": True,
            "favorite_order": 2,
        }],
    }
    imported = add_imported_list(data, incoming)
    assert imported["name"] == "default(1)"
    assert imported["kaomoji"][0].get("favorite") is False
    assert "favorite_order" not in imported["kaomoji"][0]
    assert incoming["kaomoji"][0].get("favorite") is True
    assert imported["kaomoji"][0] is not incoming["kaomoji"][0]


def test_app_state_migrates_favorite_order_and_preserves_it_on_edit() -> None:
    first: Kaomoji = {"name": "First", "text": "(a)", "tags": [], "favorite": True}
    second: Kaomoji = {
        "name": "Second", "text": "(b)", "tags": [],
        "favorite": True, "favorite_order": 4,
    }
    data = create_default_data(kaomoji=[first, second])
    saved: list[KaokeyData] = []
    state = AppState(data, lambda current: saved.append(deepcopy(current)))
    assert first.get("favorite_order") == 5
    assert state.next_favorite_order == 6
    assert len(saved) == 1

    assert state.toggle_favorite(second) is False
    assert "favorite_order" not in second
    assert state.toggle_favorite(second) is True
    assert second["favorite_order"] == 6

    tags = ["one"]
    added = state.add_kaomoji({"name": "Third", "text": "(c)", "tags": tags})
    tags.append("later")
    assert added["tags"] == ["one"]

    state.update_kaomoji(first, {"name": "Renamed", "text": "(new)", "tags": []})
    assert first["favorite"] is True
    assert first["favorite_order"] == 5
    assert first["name"] == "Renamed"
    state.delete_kaomoji(added)
    assert added not in state.kaomoji
    assert len(saved) == 6


def test_app_state_deletes_the_selected_duplicate_by_identity() -> None:
    first: Kaomoji = {"name": "", "text": "(same)", "tags": []}
    second: Kaomoji = {"name": "", "text": "(same)", "tags": []}
    state = AppState(create_default_data(kaomoji=[first, second]), lambda _: None)

    state.delete_kaomoji(second)
    assert len(state.kaomoji) == 1
    assert state.kaomoji[0] is first

    with pytest.raises(ValueError, match="active list"):
        state.delete_kaomoji(second)


def test_search_matches_name_text_and_tags_with_normalized_query() -> None:
    item: Kaomoji = {"name": "Sleepy", "text": "(￣o￣) z Z", "tags": ["Night Owl"]}
    assert matches_kaomoji_search(item, "  sleepy  ")
    assert matches_kaomoji_search(item, "NIGHT OWL")
    assert matches_kaomoji_search(item, "￣o￣")
    assert not matches_kaomoji_search(item, "morning")


def test_app_state_main_tags_apply_changes_and_enforce_limit() -> None:
    data = create_default_data()
    saved: list[KaokeyData] = []
    state = AppState(data, lambda current: saved.append(deepcopy(current)))
    assert state.add_main_tag("cute") is True
    assert state.add_main_tag("cute") is False
    assert state.add_main_tag("happy") is True
    assert state.move_main_tag("happy", -10) is True
    assert state.main_tags == ["happy", "cute"]
    assert state.remove_main_tag("missing") is False
    assert state.remove_main_tag("cute") is True
    assert len(saved) == 4

    state.main_tags[:] = [f"tag{index}" for index in range(MAX_MAIN_TAGS)]
    with pytest.raises(ValueError, match="Maximum number"):
        state.add_main_tag("extra")


def test_app_state_switch_import_merge_and_reset() -> None:
    saved: list[KaokeyData] = []
    state = AppState(create_default_data(), lambda data: saved.append(deepcopy(data)))
    state.create_list("Work")
    assert state.active_list_name == "Work"
    assert state.switch_list("Work") is False
    assert state.switch_list("Default") is True
    assert state.active_list_name == "Default"

    incoming: KaomojiList = {
        "name": "Default", "main_tags": ["happy"],
        "kaomoji": [{"name": "A", "text": "(^_^)", "tags": [], "favorite": True}],
    }
    imported = state.import_as_new_list(incoming)
    assert imported["name"] == "Default(1)"
    assert state.current_list is imported
    assert imported["kaomoji"][0].get("favorite") is False
    assert incoming["kaomoji"][0].get("favorite") is True

    report = state.merge_into_current_list({
        "name": "Extra", "main_tags": ["new"],
        "kaomoji": [{"name": "B", "text": "(o_o)", "tags": []}],
    })
    assert report == {"added": 1, "main_tags_added": 1}
    assert len(state.kaomoji) == 2

    replacement: KaomojiList = {
        "name": "Fresh", "main_tags": [], "kaomoji": [],
    }
    state.reset_all_lists(replacement)
    assert state.list_names == ["Fresh"]
    assert state.kaomoji == []
    assert saved[-1]["active_list"] == "Fresh"

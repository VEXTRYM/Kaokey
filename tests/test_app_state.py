from app_state import AppState
from library import create_empty_list
from models import KaokeyData, KaomojiInput, KaomojiList


def make_data() -> KaokeyData:
    return {
        "format_version": 1,
        "active_list": "Default",
        "lists": [create_empty_list("Default")],
    }


def make_state(data: KaokeyData | None = None) -> AppState:
    if data is None:
        data = make_data()

    return AppState(
        data,
        save_callback=lambda _data: None,
    )


def test_state_creates_and_switches_active_list() -> None:
    state = make_state()

    new_list = state.create_list("Animals")

    assert new_list["name"] == "Animals"
    assert state.active_list_name == "Animals"
    assert state.current_list is new_list

    assert state.switch_list("Default") is True
    assert state.active_list_name == "Default"


def test_state_adds_updates_and_deletes_kaomoji() -> None:
    state = make_state()

    input_data: KaomojiInput = {
        "name": "cat",
        "text": "ฅ^•ﻌ•^ฅ",
        "tags": ["cute"],
    }

    kaomoji = state.add_kaomoji(
        input_data
    )

    assert state.kaomoji == [kaomoji]
    assert kaomoji["favorite"] is False

    state.toggle_favorite(
        kaomoji
    )

    edited_data: KaomojiInput = {
        "name": "happy cat",
        "text": "(=^･ω･^=)",
        "tags": ["cat"],
    }

    state.update_kaomoji(
        kaomoji,
        edited_data,
    )

    assert kaomoji["name"] == "happy cat"
    assert kaomoji["favorite"] is True
    assert kaomoji["favorite_order"] == 1

    state.delete_kaomoji(
        kaomoji
    )

    assert state.kaomoji == []


def test_state_favorite_order_is_sequential() -> None:
    state = make_state()

    first = state.add_kaomoji(
        {
            "name": "one",
            "text": "one",
            "tags": [],
        }
    )

    second = state.add_kaomoji(
        {
            "name": "two",
            "text": "two",
            "tags": [],
        }
    )

    state.toggle_favorite(first)
    state.toggle_favorite(second)

    assert first["favorite_order"] == 1
    assert second["favorite_order"] == 2

    state.toggle_favorite(first)

    assert "favorite_order" not in first


def test_state_imports_new_list_and_makes_it_active() -> None:
    state = make_state()

    imported: KaomojiList = {
        "name": "Animals",
        "main_tags": ["cat"],
        "kaomoji": [
            {
                "name": "cat",
                "text": "ฅ^•ﻌ•^ฅ",
                "tags": ["cat"],
                "favorite": True,
                "favorite_order": 10,
            }
        ],
    }

    new_list = state.import_as_new_list(
        imported
    )

    assert state.current_list is new_list
    assert state.active_list_name == "Animals"
    assert state.kaomoji[0]["favorite"] is False
    assert "favorite_order" not in state.kaomoji[0]


def test_state_delete_active_list_refreshes_active_state() -> None:
    data = make_data()
    animals = create_empty_list("Animals")
    data["lists"].append(animals)
    data["active_list"] = "Animals"

    state = make_state(data)

    was_active = state.delete_list(
        "Animals"
    )

    assert was_active is True
    assert state.active_list_name == "Default"
    assert state.current_list["name"] == "Default"

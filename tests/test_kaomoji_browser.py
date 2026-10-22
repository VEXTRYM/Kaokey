from PySide6.QtWidgets import QApplication

from kaokey.core.models import Kaomoji
from kaokey.ui.widgets.kaomoji_browser import KaomojiBrowser


def test_browser_groups_favorites_and_main_tags_in_display_order(
    qapp: QApplication,
) -> None:
    del qapp
    items: list[Kaomoji] = [
        {"name": "Later", "text": "(1)", "tags": ["cute"],
         "favorite": True, "favorite_order": 5},
        {"name": "Earlier", "text": "(2)", "tags": [],
         "favorite": True, "favorite_order": 2},
        {"name": "Two tags", "text": "(3)", "tags": ["happy", "cute"]},
        {"name": "Cute", "text": "(4)", "tags": ["cute"]},
        {"name": "Other", "text": "(5)", "tags": ["night"]},
        {"name": "Bare", "text": "(6)", "tags": []},
    ]
    browser = KaomojiBrowser(["cute", "happy"], items)
    sections = browser.group_kaomoji(items)
    assert [(kind, tag, [item["name"] for item in group]) for kind, tag, group in sections] == [
        ("favorites", None, ["Earlier", "Later"]),
        ("tag", "cute", ["Cute"]),
        ("tag", "happy", ["Two tags"]),
        ("tag", "night", ["Other"]),
        ("untagged", None, ["Bare"]),
    ]
    browser.deleteLater()


def test_browser_search_reuses_kaomoji_buttons(qapp: QApplication) -> None:
    del qapp
    items: list[Kaomoji] = [
        {"name": "Sun", "text": "(sun)", "tags": ["day"]},
        {"name": "Moon", "text": "(moon)", "tags": ["night"]},
    ]
    browser = KaomojiBrowser([], items)
    original = dict(browser.kaomoji_button_cache)
    assert len(original) == 2

    browser.search_input.setText("night")
    browser.refresh_timer.stop()
    browser.apply_filters()
    assert len(browser.kaomoji_buttons) == 1
    assert browser.kaomoji_button_cache[id(items[1])] is original[id(items[1])]

    browser.search_input.clear()
    browser.refresh_timer.stop()
    browser.apply_filters()
    assert browser.kaomoji_button_cache == original
    browser.deleteLater()

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QPushButton

from kaokey.core.models import Kaomoji
from kaokey.ui.widgets import kaomoji_browser as browser_module
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


def test_browser_updates_search_index_and_rebuilds_once_for_list_switch(
    qapp: QApplication,
) -> None:
    del qapp

    class CountingBrowser(KaomojiBrowser):
        rebuilds = 0

        def fill_kaomoji_grid(
            self,
            sections: list[tuple[str, str | None, list[Kaomoji]]],
        ) -> None:
            self.rebuilds += 1
            super().fill_kaomoji_grid(sections)

    old: Kaomoji = {"name": "Old", "text": "(old)", "tags": []}
    new: Kaomoji = {"name": "New", "text": "(new)", "tags": ["fresh"]}
    browser = CountingBrowser(["old"], [old])
    initial_rebuilds = browser.rebuilds

    browser.refresh_timer.start()
    browser.set_data(["fresh"], [new])
    assert browser.rebuilds == initial_rebuilds + 1
    assert not browser.refresh_timer.isActive()
    assert id(old) not in browser.kaomoji_button_cache
    assert id(new) in browser.kaomoji_button_cache

    browser.search_input.setText("fresh")
    browser.refresh_timer.stop()
    browser.apply_filters()
    assert len(browser.kaomoji_buttons) == 1

    new["tags"] = ["changed"]
    browser.set_kaomoji([new])
    assert browser.kaomoji_buttons == []
    browser.deleteLater()


def test_browser_styles_buttons_only_when_content_or_favorite_changes(
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del qapp
    item: Kaomoji = {"name": "One", "text": "(one)", "tags": []}
    browser = KaomojiBrowser([], [item])
    styled: list[bool] = []
    original_style = browser_module.style_kaomoji_button

    def record_style(button: QPushButton, favorite: bool) -> None:
        styled.append(favorite)
        original_style(button, favorite)

    monkeypatch.setattr(browser_module, "style_kaomoji_button", record_style)
    browser.apply_filters()
    assert styled == []

    item["favorite"] = True
    browser.apply_filters()
    assert styled == [True]
    browser.apply_filters()
    assert styled == [True]

    item["text"] = "(changed)"
    browser.set_kaomoji([item])
    assert styled == [True, True]
    assert browser.kaomoji_button_cache[id(item)].text() == "(changed)"
    browser.deleteLater()


def test_browser_flushes_pending_search_before_keyboard_selection(
    qapp: QApplication,
) -> None:
    del qapp
    items: list[Kaomoji] = [
        {"name": "Sun", "text": "(sun)", "tags": []},
        {"name": "Moon", "text": "(moon)", "tags": []},
    ]
    browser = KaomojiBrowser([], items)
    browser.search_input.setText("moon")
    assert browser.refresh_timer.isActive()

    browser.handle_key_press(
        QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Return,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    assert not browser.refresh_timer.isActive()
    assert len(browser.kaomoji_buttons) == 1
    assert browser.kaomoji_buttons[0] is browser.kaomoji_button_cache[id(items[1])]
    browser.deleteLater()

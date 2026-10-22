from PySide6.QtWidgets import QApplication, QPushButton

from kaokey.core.models import KaomojiInput
from kaokey.ui.tabs.constructor_tab import ConstructorTab
from kaokey.ui.tabs.lists_tab import ListsTab


def test_constructor_builds_and_submits_normalized_kaomoji(
    qapp: QApplication,
) -> None:
    del qapp
    tab = ConstructorTab({"Eyes": ["◕", "•"]})
    tab.symbol_grids[0][1][0].click()
    tab.name_input.setText("  Happy  ")
    tab.tags_input.setText(" cute, happy, cute, ")

    submitted: list[KaomojiInput] = []
    tab.submit_requested.connect(submitted.append)
    tab.submit_button.click()
    assert submitted == [{
        "name": "Happy", "text": "◕", "tags": ["cute", "happy"],
    }]

    tab.clear_button.click()
    assert tab.kaomoji_input.toPlainText() == ""
    tab.deleteLater()


def test_constructor_cancel_edit_keeps_form_until_coordinator_resets_it(
    qapp: QApplication,
) -> None:
    del qapp
    tab = ConstructorTab({})
    tab.load_for_edit({"name": "Old", "text": "(o_o)", "tags": ["calm"]})
    assert tab.edit_mode
    assert tab.submit_button.text() == "Edit"

    cancelled: list[bool] = []
    tab.cancel_edit_requested.connect(lambda: cancelled.append(True))
    tab.clear_button.click()
    assert cancelled == [True]
    assert tab.kaomoji_input.toPlainText() == "(o_o)"

    tab.reset_form()
    assert not tab.edit_mode
    assert tab.submit_button.text() == "Add"
    assert tab.name_input.text() == ""
    assert tab.kaomoji_input.toPlainText() == ""
    tab.deleteLater()


def test_lists_tab_emits_only_requested_changes(qapp: QApplication) -> None:
    del qapp
    tab = ListsTab(["Default", "Work"], "Default")
    created: list[str] = []
    selected: list[str] = []
    exported: list[str] = []
    tab.create_list_requested.connect(created.append)
    tab.use_list_requested.connect(selected.append)
    tab.export_list_requested.connect(exported.append)

    tab.create_list_button.click()
    assert created == []
    tab.new_list_input.setText("  New  ")
    tab.create_list_button.click()
    assert created == ["New"]

    first_item = tab.list_layout.itemAt(0)
    second_item = tab.list_layout.itemAt(1)
    assert first_item is not None and second_item is not None
    first = first_item.widget()
    second = second_item.widget()
    assert first is not None and second is not None
    first.findChildren(QPushButton)[0].click()
    second.findChildren(QPushButton)[0].click()
    assert selected == ["Work"]
    tab.export_list_button.click()
    assert exported == ["Default"]
    tab.deleteLater()

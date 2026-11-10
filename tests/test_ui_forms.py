from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QInputMethodEvent, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from kaokey.core.models import KaomojiInput
from kaokey.ui.tabs.constructor_tab import ConstructorTab, KaomojiTextEdit
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


def test_constructor_palette_appends_rtl_symbols_in_click_order(
    qapp: QApplication,
) -> None:
    del qapp
    tab = ConstructorTab({"Letters": ["ا", "ب", "א"]})
    for button in tab.symbol_grids[0][1]:
        button.click()
    assert tab.kaomoji_input.toPlainText() == "ابא"
    _, line = tab.kaomoji_input._visual_layout()
    positions = tab.kaomoji_input._boundaries()
    x_positions = [tab.kaomoji_input._caret_x(line, p) for p in positions]
    assert x_positions == sorted(x_positions)
    tab.deleteLater()


def test_constructor_displays_mixed_scripts_in_insertion_order(
    qapp: QApplication,
) -> None:
    edit = KaomojiTextEdit()
    edit.resize(400, 40)
    edit.show()
    edit.setFocus()
    for symbol in ("A", "ا", "ب", "ג", "😀", "👩‍👩‍👧‍👧", "Z"):
        edit.insertPlainText(symbol)

    assert edit.toPlainText() == "Aابג😀👩‍👩‍👧‍👧Z"
    _, line = edit._visual_layout()
    positions = edit._boundaries()
    x_positions = [edit._caret_x(line, position) for position in positions]
    assert all(left < right for left, right in zip(x_positions, x_positions[1:]))
    assert edit.textCursor().position() == positions[-1]

    QTest.keyClick(edit, Qt.Key.Key_Left)
    assert edit.textCursor().position() == positions[-2]
    QTest.keyClick(edit, Qt.Key.Key_Left)
    assert edit.textCursor().position() == positions[-3]
    QTest.keyClick(edit, Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier)
    assert edit.textCursor().selectedText() == "😀"
    assert not edit.grab().isNull()

    edit.deleteLater()


def test_constructor_rtl_editing_keeps_raw_unicode(qapp: QApplication) -> None:
    edit = KaomojiTextEdit()
    edit.resize(300, 40)
    edit.show()
    edit.setFocus()
    edit.setPlainText("אבג")
    _, line = edit._visual_layout()
    x = edit._caret_x(line, 1)
    QTest.mouseClick(
        edit.viewport(),
        Qt.MouseButton.LeftButton,
        pos=QPoint(round(x), edit.viewport().height() // 2),
    )
    assert edit.textCursor().position() == 1
    cursor = edit.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    edit.setTextCursor(cursor)
    QTest.keyClick(edit, Qt.Key.Key_Left)
    QTest.keyClicks(edit, "X")
    assert edit.toPlainText() == "אבXג"
    QTest.keyClick(edit, Qt.Key.Key_Home)
    assert edit.textCursor().position() == 0
    QTest.keyClick(edit, Qt.Key.Key_Right)
    assert edit.textCursor().position() == 1
    edit.insertPlainText("ا\nב")
    assert edit.toPlainText().startswith("אا ב")
    edit.deleteLater()


def test_constructor_shows_ime_preedit_without_storing_it(
    qapp: QApplication,
) -> None:
    edit = KaomojiTextEdit()
    edit.show()
    edit.setFocus()
    edit.inputMethodEvent(QInputMethodEvent("あ", []))
    assert edit.toPlainText() == ""
    assert "あ" in edit._visual_layout()[0].text()
    assert not edit.grab().isNull()
    committed = QInputMethodEvent()
    committed.setCommitString("あ")
    edit.inputMethodEvent(committed)
    assert edit.toPlainText() == "あ"
    assert edit._preedit_text == ""
    edit.deleteLater()


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

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from kaokey.core.models import Kaomoji
from kaokey.ui.tabs.edit_tab import EditTab


def test_edit_search_reuses_rows_and_keeps_actions_connected(
    qapp: QApplication,
) -> None:
    del qapp
    items: list[Kaomoji] = [
        {"name": f"Name {index}", "text": f"face {index}", "tags": ["common"]}
        for index in range(120)
    ]
    tab = EditTab([], items)
    initial_rows = [row for row, _ in tab._edit_rows]
    assert tab.edit_list_layout.count() == len(items)

    tab.search_input.setText("name 11")
    assert tab.search_timer.isActive()
    assert [row for row, _ in tab._edit_rows] == initial_rows
    assert tab.edit_list_layout.count() == len(items)

    QTest.qWait(120)
    assert not tab.search_timer.isActive()
    visible_indices = [
        index for index, (row, _) in enumerate(tab._edit_rows) if not row.isHidden()
    ]
    assert visible_indices == list(range(11, 12)) + list(range(110, 120))

    requested: list[Kaomoji] = []
    tab.edit_kaomoji_requested.connect(requested.append)
    initial_rows[11].findChildren(QPushButton)[0].click()
    assert requested == [items[11]]
    assert requested[0] is items[11]

    tab.search_input.clear()
    tab.search_timer.stop()
    tab.apply_search_filter()
    assert all(not row.isHidden() for row in initial_rows)
    assert [row for row, _ in tab._edit_rows] == initial_rows


def test_edit_search_refreshes_cached_text_when_library_changes(
    qapp: QApplication,
) -> None:
    del qapp
    tab = EditTab([], [{"name": "Old", "text": "old", "tags": []}])
    tab.search_input.setText("new-tag")
    tab.set_kaomoji([
        {"name": "New", "text": "new", "tags": ["new-tag"]},
        {"name": "Other", "text": "other", "tags": []},
    ])

    assert not tab.search_timer.isActive()
    assert [not row.isHidden() for row, _ in tab._edit_rows] == [True, False]
    assert len(tab._edit_rows) == 2

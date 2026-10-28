from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QLabel

from kaokey.application.app_state import AppState
from kaokey.config.i18n import TranslationManager
from kaokey.config.settings import SettingsManager
from kaokey.persistence.storage import create_default_data
from kaokey.platforms.popup_backend import UnavailablePopupBackend
from kaokey.platforms.startup import UnavailableStartupBackend
from kaokey.ui.coordinators import popup_coordinator, settings_coordinator
from kaokey.ui.main_window import MainWindow
from kaokey.ui.tabs.text_ench_tab import TextEnchTab
from kaokey.ui.tray import TrayController


def test_text_ench_tab_generates_plain_text_and_copies_selected_variant(
    qapp: QApplication,
) -> None:
    tab = TextEnchTab()
    copied: list[str] = []
    tab.copy_requested.connect(copied.append)

    assert not tab.enchance_button.isEnabled()
    line_height = tab.text_input.fontMetrics().lineSpacing()
    assert 2 * line_height <= tab.text_input.height() < 3 * line_height
    assert tab.text_input.minimumHeight() == tab.text_input.maximumHeight()
    tab.text_input.setPlainText("<Hi>&\nYo")
    assert tab.enchance_button.isEnabled()
    tab.enchance_button.click()
    assert len(tab.variants) >= 20
    assert tab.results_layout.count() == len(tab.variants)

    row = tab.results_layout.itemAt(0)
    assert row is not None
    row_widget = row.widget()
    assert row_widget is not None
    row_labels = row_widget.findChildren(QLabel)
    assert len(row_labels) == 1
    sample = row_labels[0]
    assert sample.textFormat() == Qt.TextFormat.PlainText
    assert not sample.wordWrap()
    assert "<" in sample.text()
    assert "\n" not in sample.text()
    assert "↵" in sample.text()

    first_variant, copy_button = tab._result_controls[0]
    copy_button.click()
    assert copied == [first_variant.text]

    tab.text_input.setPlainText("new")
    assert tab.variants == []
    assert tab.results_layout.count() == 0
    tab.text_input.clear()
    assert not tab.enchance_button.isEnabled()
    tab.deleteLater()
    qapp.processEvents()


def test_text_ench_tab_sits_left_of_settings_and_copies_in_main_window(
    qapp: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = AppState(create_default_data(), lambda _: None)
    monkeypatch.setattr(AppState, "load", lambda: state)
    monkeypatch.setattr(
        popup_coordinator,
        "create_popup_backend",
        lambda app, parent: UnavailablePopupBackend(parent),
    )
    monkeypatch.setattr(
        settings_coordinator,
        "create_startup_backend",
        UnavailableStartupBackend,
    )
    monkeypatch.setattr(TrayController, "is_available", lambda: False)

    settings = SettingsManager(
        QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )
    window = MainWindow(settings, TranslationManager(qapp))
    assert window.tabs.indexOf(window.text_ench_tab) + 1 == window.tabs.indexOf(
        window.settings_tab
    )
    assert window.tabs.tabText(window.tabs.indexOf(window.text_ench_tab)) == "Text ench"
    assert window.text_ench_tab.enchance_button.text() == "Enchance"

    window.text_ench_tab.text_input.setPlainText("Hello")
    window.text_ench_tab.enchance_button.click()
    variant, copy_button = window.text_ench_tab._result_controls[0]
    copy_button.click()
    assert qapp.clipboard().text() == variant.text
    assert window.status_bar.currentMessage() == f"Copied: {variant.text}"

    window.text_ench_tab.text_input.setPlainText("Hi\nthere")
    window.text_ench_tab.enchance_button.click()
    multiline, copy_button = window.text_ench_tab._result_controls[0]
    multiline_row = window.text_ench_tab.results_layout.itemAt(0)
    assert multiline_row is not None
    multiline_widget = multiline_row.widget()
    assert multiline_widget is not None
    multiline_preview = multiline_widget.findChild(QLabel)
    assert multiline_preview is not None
    assert "\n" not in multiline_preview.text()
    assert "↵" in multiline_preview.text()
    copy_button.click()
    assert qapp.clipboard().text() == multiline.text
    assert window.status_bar.currentMessage() == (
        f"Copied: {multiline.text.replace(chr(10), ' ↵ ')}"
    )
    window.close()
    window.deleteLater()

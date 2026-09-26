from PySide6.QtCore import QEvent
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabWidget,
)

from kaokey.application.app_state import AppState
from kaokey.config.constants import WINDOW_TITLE
from kaokey.config.i18n import TranslationManager
from kaokey.config.settings import SettingsManager
from kaokey.core.constructor_symbols import load_constructor_symbols
from kaokey.ui.controllers.status_hints import StatusHintsController
from kaokey.ui.coordinators.library_coordinator import LibraryCoordinator
from kaokey.ui.coordinators.lists_coordinator import ListsCoordinator
from kaokey.ui.coordinators.popup_coordinator import PopupCoordinator
from kaokey.ui.coordinators.settings_coordinator import SettingsCoordinator
from kaokey.ui.popup.popup_window import PopupWindow
from kaokey.ui.styling.style_constants import STATUS_BAR_DURATION
from kaokey.ui.tabs.constructor_tab import ConstructorTab
from kaokey.ui.tabs.edit_tab import EditTab
from kaokey.ui.tabs.kaomoji_tab import KaomojiTab
from kaokey.ui.tabs.lists_tab import ListsTab
from kaokey.ui.tray import TrayController
from kaokey.ui.widgets.unicode_status_bar import UnicodeStatusBar


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: SettingsManager,
        translations: TranslationManager,
    ) -> None:
        super().__init__()

        self.settings = settings
        self.translations = translations
        self.state = AppState.load()

        self.tray_controller: TrayController | None = None
        self.exit_requested = False

        self.setWindowTitle(WINDOW_TITLE)
        self.resize(*self.settings.window_size)

        self._build_ui()
        self._build_coordinators()
        self._connect_cross_feature_signals()

        self.setup_tray()
        self.popup_coordinator.setup_hotkey(*self.settings.hotkey)

        self.retranslate_ui()
        self.status_hints.set_enabled(self.settings.show_hints)

    def _build_ui(
        self,
    ) -> None:
        self.tabs = QTabWidget()

        self.kaomoji_tab = KaomojiTab(
            self.state.main_tags,
            self.state.kaomoji,
        )
        self.edit_tab = EditTab(
            self.state.main_tags,
            self.state.kaomoji,
        )
        self.lists_tab = ListsTab(
            self.state.list_names,
            self.state.active_list_name,
        )
        self.constructor_tab = ConstructorTab(load_constructor_symbols())

        self.popup_window = PopupWindow(
            self.state.main_tags,
            self.state.kaomoji,
            self.settings,
        )

        self.status_bar = UnicodeStatusBar()
        self.status_bar.setSizeGripEnabled(False)
        self.setStatusBar(self.status_bar)

    def _build_coordinators(
        self,
    ) -> None:
        self.popup_coordinator = PopupCoordinator(
            host_window=self,
            popup_window=self.popup_window,
            settings=self.settings,
            status_bar=self.status_bar,
            copy_text=self.copy_text_to_clipboard,
            parent=self,
        )

        self.status_hints = StatusHintsController(
            tabs=self.tabs,
            kaomoji_tab=self.kaomoji_tab,
            status_bar=self.status_bar,
            parent=self,
        )

        self.settings_coordinator = SettingsCoordinator(
            settings=self.settings,
            translations=self.translations,
            window=self,
            popup_window=self.popup_window,
            popup_coordinator=self.popup_coordinator,
            status_hints=self.status_hints,
            status_bar=self.status_bar,
            parent=self,
        )
        self.settings_tab = self.settings_coordinator.tab

        self.tabs.addTab(self.kaomoji_tab, "")
        self.tabs.addTab(self.edit_tab, "")
        self.tabs.addTab(self.lists_tab, "")
        self.tabs.addTab(self.constructor_tab, "")
        self.tabs.addTab(self.settings_tab, "")

        self.setCentralWidget(self.tabs)

        self.library_coordinator = LibraryCoordinator(
            state=self.state,
            tabs=self.tabs,
            kaomoji_tab=self.kaomoji_tab,
            edit_tab=self.edit_tab,
            constructor_tab=self.constructor_tab,
            popup_window=self.popup_window,
            status_bar=self.status_bar,
            dialog_parent=self,
            copy_text=self.copy_text_to_clipboard,
            parent=self,
        )

        self.lists_coordinator = ListsCoordinator(
            state=self.state,
            lists_tab=self.lists_tab,
            settings_tab=self.settings_tab,
            status_bar=self.status_bar,
            dialog_parent=self,
            parent=self,
        )

    def _connect_cross_feature_signals(
        self,
    ) -> None:
        self.lists_coordinator.active_list_changed.connect(
            self.library_coordinator.handle_active_list_changed
        )
        self.lists_coordinator.current_list_updated.connect(
            self.library_coordinator.refresh_active_list_views
        )

    def retranslate_ui(
        self,
    ) -> None:
        self.tabs.setTabText(
            self.tabs.indexOf(self.kaomoji_tab),
            self.tr("Kaomoji"),
        )
        self.tabs.setTabText(
            self.tabs.indexOf(self.edit_tab),
            self.tr("Edit"),
        )
        self.tabs.setTabText(
            self.tabs.indexOf(self.lists_tab),
            self.tr("Lists"),
        )
        self.tabs.setTabText(
            self.tabs.indexOf(self.constructor_tab),
            self.tr("Constructor"),
        )
        self.tabs.setTabText(
            self.tabs.indexOf(self.settings_tab),
            self.tr("Settings"),
        )

        self.kaomoji_tab.retranslate_ui()
        self.settings_tab.retranslate_ui()

        if self.tray_controller is not None:
            self.tray_controller.retranslate_ui()

        self.status_hints.retranslate()

    def changeEvent(
        self,
        event: QEvent,
    ) -> None:
        super().changeEvent(event)

        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()

    def setup_tray(
        self,
    ) -> None:
        if not TrayController.is_available():
            return

        tray = TrayController(self)

        tray.open_requested.connect(self.show_main_window)
        tray.settings_requested.connect(self.show_settings_window)
        tray.close_requested.connect(self.quit_application)

        self.tray_controller = tray

        app = QApplication.instance()

        if isinstance(
            app,
            QApplication,
        ):
            app.setQuitOnLastWindowClosed(False)

        tray.show()

    def show_main_window(
        self,
    ) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def show_settings_window(
        self,
    ) -> None:
        self.tabs.setCurrentWidget(self.settings_tab)
        self.show_main_window()

    def quit_application(
        self,
    ) -> None:
        self.exit_requested = True

        self.popup_window.close()
        self.popup_coordinator.shutdown()

        if self.tray_controller is not None:
            self.tray_controller.hide()

        app = QApplication.instance()

        if app is not None:
            app.quit()

    def copy_text_to_clipboard(
        self,
        text: str,
    ) -> None:
        clipboard = QApplication.clipboard()
        clipboard.setText(text)

        self.status_bar.showMessage(
            f"Copied: {text.rstrip()}",
            STATUS_BAR_DURATION,
        )

    def closeEvent(
        self,
        event: QCloseEvent,
    ) -> None:
        if (
            self.tray_controller is not None
            and not self.exit_requested
            and self.settings.minimize_to_tray_on_close
        ):
            self.popup_window.close()
            self.hide()
            event.ignore()
            return

        self.popup_coordinator.shutdown()
        self.popup_window.close()

        if self.tray_controller is not None:
            self.tray_controller.hide()

        super().closeEvent(event)

        if self.tray_controller is not None and not self.exit_requested:
            app = QApplication.instance()

            if app is not None:
                app.quit()

from PySide6.QtCore import (
    QCoreApplication,
    QObject,
    Signal,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QMessageBox,
    QStatusBar,
    QWidget,
)

from kaokey.application.app_state import AppState
from kaokey.config.constants import (
    DEFAULT_DATA_PATH,
    LIST_FILE_FILTER,
)
from kaokey.core.models import KaomojiList
from kaokey.persistence.list_io import (
    export_kaomoji_list,
    import_kaomoji_list,
)
from kaokey.ui.styling.style_constants import STATUS_BAR_DURATION
from kaokey.ui.tabs.lists_tab import ListsTab
from kaokey.ui.tabs.settings_tab import SettingsTab


class ListsCoordinator(QObject):
    """Coordinates list management, import, export, and reset operations."""

    active_list_changed = Signal()
    current_list_updated = Signal()

    def __init__(
        self,
        state: AppState,
        lists_tab: ListsTab,
        settings_tab: SettingsTab,
        status_bar: QStatusBar,
        dialog_parent: QWidget,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self.state = state
        self.lists_tab = lists_tab
        self.settings_tab = settings_tab
        self.status_bar = status_bar
        self.dialog_parent = dialog_parent

        self.lists_tab.use_list_requested.connect(self.switch_list)
        self.lists_tab.create_list_requested.connect(self.create_list)
        self.lists_tab.rename_list_requested.connect(self.rename_list)
        self.lists_tab.delete_list_requested.connect(self.delete_list)
        self.lists_tab.export_list_requested.connect(self.export_list)
        self.lists_tab.import_list_requested.connect(self.import_list)

        self.settings_tab.import_default_list_requested.connect(
            self.import_default_list
        )
        self.settings_tab.reset_all_lists_requested.connect(self.reset_all_lists)

    @staticmethod
    def _tr(
        text: str,
    ) -> str:
        return QCoreApplication.translate(
            "MainWindow",
            text,
        )

    def refresh_lists_view(
        self,
    ) -> None:
        self.lists_tab.set_lists(
            self.state.list_names,
            self.state.active_list_name,
        )

    def switch_list(
        self,
        name: str,
    ) -> None:
        try:
            changed = self.state.switch_list(name)
        except ValueError as error:
            self.status_bar.showMessage(
                str(error),
                STATUS_BAR_DURATION,
            )
            return

        if not changed:
            return

        self.active_list_changed.emit()
        self.refresh_lists_view()

        self.status_bar.showMessage(
            f"Active list: {self.state.active_list_name}",
            STATUS_BAR_DURATION,
        )

    def create_list(
        self,
        name: str,
    ) -> None:
        try:
            new_list = self.state.create_list(name)
        except ValueError as error:
            self.status_bar.showMessage(
                str(error),
                STATUS_BAR_DURATION,
            )
            return

        self.active_list_changed.emit()
        self.refresh_lists_view()
        self.lists_tab.clear_new_list_name()

        self.status_bar.showMessage(
            f"List created: {new_list['name']}",
            STATUS_BAR_DURATION,
        )

    def rename_list(
        self,
        name: str,
    ) -> None:
        new_name, accepted = QInputDialog.getText(
            self.dialog_parent,
            "Rename list",
            "List name:",
            text=name,
        )

        if not accepted:
            return

        new_name = new_name.strip()

        if new_name == name:
            return

        try:
            renamed_list = self.state.rename_list(
                name,
                new_name,
            )
        except ValueError as error:
            self.status_bar.showMessage(
                str(error),
                STATUS_BAR_DURATION,
            )
            return

        self.refresh_lists_view()

        self.status_bar.showMessage(
            f"List renamed: {renamed_list['name']}",
            STATUS_BAR_DURATION,
        )

    def delete_list(
        self,
        name: str,
    ) -> None:
        answer = QMessageBox.question(
            self.dialog_parent,
            "Delete list",
            f'Delete list "{name}"?\n\nAll kaomoji in this list will be deleted.',
            (QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No),
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            was_active = self.state.delete_list(name)
        except ValueError as error:
            self.status_bar.showMessage(
                str(error),
                STATUS_BAR_DURATION,
            )
            return

        if was_active:
            self.active_list_changed.emit()

        self.refresh_lists_view()

        self.status_bar.showMessage(
            f"List deleted: {name}",
            STATUS_BAR_DURATION,
        )

    def export_list(
        self,
        name: str,
    ) -> None:
        kaomoji_list = self.state.find_list(name)

        if kaomoji_list is None:
            self.status_bar.showMessage(
                f"List does not exist: {name}",
                STATUS_BAR_DURATION,
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self.dialog_parent,
            "Export Kaokey list",
            "",
            LIST_FILE_FILTER,
        )

        if not file_path:
            return

        try:
            saved_path = export_kaomoji_list(
                file_path,
                kaomoji_list,
            )
        except ValueError as error:
            QMessageBox.warning(
                self.dialog_parent,
                "Export failed",
                str(error),
            )
            return

        self.status_bar.showMessage(
            f"List exported: {saved_path.name}",
            STATUS_BAR_DURATION,
        )

    def import_list(
        self,
    ) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self.dialog_parent,
            "Import Kaokey list",
            "",
            LIST_FILE_FILTER,
        )

        if not file_path:
            return

        try:
            imported_list = import_kaomoji_list(file_path)
        except ValueError as error:
            QMessageBox.warning(
                self.dialog_parent,
                "Import failed",
                str(error),
            )
            return

        mode = self.choose_import_mode(imported_list["name"])

        if mode == "new":
            self.import_as_new_list(imported_list)
        elif mode == "merge":
            self.merge_into_current_list(imported_list)

    def choose_import_mode(
        self,
        imported_name: str,
    ) -> str | None:
        message_box = QMessageBox(self.dialog_parent)
        message_box.setWindowTitle("Import list")
        message_box.setText(
            f'Import "{imported_name}"\n\nHow should it be imported?'
        )

        add_button = message_box.addButton(
            "Add as new list",
            QMessageBox.ButtonRole.AcceptRole,
        )
        merge_button = message_box.addButton(
            "Merge into current",
            QMessageBox.ButtonRole.ActionRole,
        )
        message_box.addButton(QMessageBox.StandardButton.Cancel)

        message_box.exec()
        clicked_button = message_box.clickedButton()

        if clicked_button is add_button:
            return "new"

        if clicked_button is merge_button:
            return "merge"

        return None

    def import_as_new_list(
        self,
        imported_list: KaomojiList,
    ) -> None:
        new_list = self.state.import_as_new_list(imported_list)

        self.active_list_changed.emit()
        self.refresh_lists_view()

        self.status_bar.showMessage(
            f"List imported: {new_list['name']}",
            STATUS_BAR_DURATION,
        )

    def merge_into_current_list(
        self,
        imported_list: KaomojiList,
    ) -> None:
        report = self.state.merge_into_current_list(imported_list)

        self.current_list_updated.emit()

        self.status_bar.showMessage(
            (
                f"Added: {report['added']} | "
                f"Main tags added: {report['main_tags_added']}"
            ),
            STATUS_BAR_DURATION,
        )

    def load_default_list(
        self,
    ) -> KaomojiList | None:
        try:
            return import_kaomoji_list(str(DEFAULT_DATA_PATH))
        except ValueError as error:
            QMessageBox.warning(
                self.dialog_parent,
                self._tr("Default list unavailable"),
                str(error),
            )
            return None

    def import_default_list(
        self,
    ) -> None:
        default_list = self.load_default_list()

        if default_list is None:
            return

        self.import_as_new_list(default_list)

    def reset_all_lists(
        self,
    ) -> None:
        default_list = self.load_default_list()

        if default_list is None:
            return

        answer = QMessageBox.question(
            self.dialog_parent,
            self._tr("Reset all lists"),
            self._tr(
                "Reset all lists to the default list?\n\n"
                "All current lists and their changes will be deleted."
            ),
            (QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No),
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.state.reset_all_lists(default_list)

        self.active_list_changed.emit()
        self.refresh_lists_view()

        self.status_bar.showMessage(
            self._tr("All lists were reset to the default list."),
            STATUS_BAR_DURATION,
        )

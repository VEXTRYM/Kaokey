from collections.abc import Callable

from PySide6.QtCore import QObject
from PySide6.QtWidgets import (
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QWidget,
)

from kaokey.application.app_state import AppState
from kaokey.core.models import (
    Kaomoji,
    KaomojiInput,
)
from kaokey.core.validators import (
    validate_kaomoji_content,
    validate_name,
)
from kaokey.ui.popup.popup_window import PopupWindow
from kaokey.ui.styling.style_constants import STATUS_BAR_DURATION
from kaokey.ui.tabs.constructor_tab import ConstructorTab
from kaokey.ui.tabs.edit_tab import EditTab
from kaokey.ui.tabs.kaomoji_tab import KaomojiTab


class LibraryCoordinator(QObject):
    """Coordinates kaomoji, favorites, tags, and constructor editing."""

    def __init__(
        self,
        state: AppState,
        tabs: QTabWidget,
        kaomoji_tab: KaomojiTab,
        edit_tab: EditTab,
        constructor_tab: ConstructorTab,
        popup_window: PopupWindow,
        status_bar: QStatusBar,
        dialog_parent: QWidget,
        copy_text: Callable[[str], None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self.state = state
        self.tabs = tabs
        self.kaomoji_tab = kaomoji_tab
        self.edit_tab = edit_tab
        self.constructor_tab = constructor_tab
        self.popup_window = popup_window
        self.status_bar = status_bar
        self.dialog_parent = dialog_parent
        self.copy_text = copy_text

        self.editing_kaomoji: Kaomoji | None = None

        self.kaomoji_tab.copy_requested.connect(self.copy_kaomoji)
        self.kaomoji_tab.favorite_toggle_requested.connect(self.toggle_favorite)
        self.popup_window.favorite_toggle_requested.connect(self.toggle_favorite)

        self.edit_tab.edit_kaomoji_requested.connect(self.start_edit_kaomoji)
        self.edit_tab.delete_kaomoji_requested.connect(self.delete_kaomoji)
        self.edit_tab.add_main_tag_requested.connect(self.add_main_tag)
        self.edit_tab.remove_main_tag_requested.connect(self.remove_main_tag)

        self.constructor_tab.submit_requested.connect(self.submit_constructor)
        self.constructor_tab.cancel_edit_requested.connect(
            self.cancel_constructor_edit
        )

    def copy_kaomoji(
        self,
        kaomoji: Kaomoji,
    ) -> None:
        self.copy_text(kaomoji["text"])

    def toggle_favorite(
        self,
        kaomoji: Kaomoji,
    ) -> None:
        is_favorite = self.state.toggle_favorite(kaomoji)

        if is_favorite:
            message = f"Added to favorites: {kaomoji['text']}"
        else:
            message = f"Removed from favorites: {kaomoji['text']}"

        self.status_bar.showMessage(
            message,
            STATUS_BAR_DURATION,
        )

        self.kaomoji_tab.refresh()
        self.popup_window.refresh()

    def refresh_kaomoji_views(
        self,
    ) -> None:
        self.kaomoji_tab.set_kaomoji(self.state.kaomoji)
        self.edit_tab.set_kaomoji(self.state.kaomoji)
        self.popup_window.set_kaomoji(self.state.kaomoji)

    def refresh_main_tag_views(
        self,
    ) -> None:
        self.kaomoji_tab.set_main_tags(self.state.main_tags)
        self.edit_tab.set_main_tags(self.state.main_tags)
        self.popup_window.set_main_tags(self.state.main_tags)

    def refresh_active_list_views(
        self,
    ) -> None:
        self.kaomoji_tab.set_main_tags(self.state.main_tags)
        self.kaomoji_tab.set_kaomoji(self.state.kaomoji)

        self.edit_tab.set_main_tags(self.state.main_tags)
        self.edit_tab.set_kaomoji(self.state.kaomoji)

        self.popup_window.set_main_tags(self.state.main_tags)
        self.popup_window.set_kaomoji(self.state.kaomoji)

    def handle_active_list_changed(
        self,
    ) -> None:
        self.cancel_constructor_edit()
        self.refresh_active_list_views()

    def cancel_constructor_edit(
        self,
    ) -> None:
        self.editing_kaomoji = None
        self.constructor_tab.reset_form()

    def start_edit_kaomoji(
        self,
        kaomoji: Kaomoji,
    ) -> None:
        self.editing_kaomoji = kaomoji

        data: KaomojiInput = {
            "name": kaomoji["name"],
            "text": kaomoji["text"],
            "tags": list(kaomoji["tags"]),
        }

        self.constructor_tab.load_for_edit(data)
        self.tabs.setCurrentWidget(self.constructor_tab)

    def submit_constructor(
        self,
        input_data: KaomojiInput,
    ) -> None:
        content_error = validate_kaomoji_content(
            input_data["text"],
            input_data["tags"],
        )

        if content_error is not None:
            self.status_bar.showMessage(
                content_error,
                STATUS_BAR_DURATION,
            )
            return

        existing_names = self.state.existing_kaomoji_names(
            exclude=self.editing_kaomoji
        )

        name_error = validate_name(
            input_data["name"],
            existing_names,
        )

        if name_error is not None:
            self.status_bar.showMessage(
                name_error,
                STATUS_BAR_DURATION,
            )
            return

        if self.editing_kaomoji is None:
            self.add_constructor_kaomoji(input_data)
        else:
            self.update_constructor_kaomoji(input_data)

    def add_constructor_kaomoji(
        self,
        input_data: KaomojiInput,
    ) -> None:
        new_kaomoji = self.state.add_kaomoji(input_data)

        self.refresh_kaomoji_views()
        self.constructor_tab.reset_form()

        self.status_bar.showMessage(
            f"Added: {new_kaomoji['text']}",
            STATUS_BAR_DURATION,
        )

    def update_constructor_kaomoji(
        self,
        input_data: KaomojiInput,
    ) -> None:
        if self.editing_kaomoji is None:
            return

        edited_kaomoji = self.editing_kaomoji

        self.state.update_kaomoji(
            edited_kaomoji,
            input_data,
        )

        self.refresh_kaomoji_views()

        self.editing_kaomoji = None
        self.constructor_tab.reset_form()

        self.status_bar.showMessage(
            f"Updated: {edited_kaomoji['text']}",
            STATUS_BAR_DURATION,
        )

    def delete_kaomoji(
        self,
        kaomoji: Kaomoji,
    ) -> None:
        name = kaomoji["name"]
        description = name if name else kaomoji["text"]

        answer = QMessageBox.question(
            self.dialog_parent,
            "Delete kaomoji",
            f'Delete "{description}"?\n\nAre you sure?',
            (QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No),
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        if kaomoji is self.editing_kaomoji:
            self.cancel_constructor_edit()

        self.state.delete_kaomoji(kaomoji)
        self.refresh_kaomoji_views()

        self.status_bar.showMessage(
            f"Deleted: {kaomoji['text']}",
            STATUS_BAR_DURATION,
        )

    def add_main_tag(
        self,
        tag: str,
    ) -> None:
        try:
            added = self.state.add_main_tag(tag)
        except ValueError as error:
            self.status_bar.showMessage(
                str(error),
                STATUS_BAR_DURATION,
            )
            return

        if not added:
            return

        self.refresh_main_tag_views()

        self.status_bar.showMessage(
            f"Main tag added: {tag}",
            STATUS_BAR_DURATION,
        )

    def remove_main_tag(
        self,
        tag: str,
    ) -> None:
        if not self.state.remove_main_tag(tag):
            return

        self.refresh_main_tag_views()

        self.status_bar.showMessage(
            f"Main tag removed: {tag}",
            STATUS_BAR_DURATION,
        )

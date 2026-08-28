import sys

from PySide6.QtCore import (
    QEvent,
    QTimer,
)

from PySide6.QtGui import (
    QCloseEvent,
)

from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QTabWidget,
)

from constants import (
    APPLICATION_NAME,
    ICON_PATH,
    LIST_FILE_FILTER,
    WINDOW_TITLE,
)

from constructor_symbols import (
    load_constructor_symbols,
)

from app_state import AppState
from i18n import TranslationManager

from list_io import (
    export_kaomoji_list,
    import_kaomoji_list,
)

from models import (
    Kaomoji,
    KaomojiInput,
    KaomojiList,
)

from popup_window import PopupWindow
from settings import SettingsManager
from tray import TrayController

from platforms.windows.constants import (
    INSERTION_KEY_RELEASE_MAX_ATTEMPTS,
    INSERTION_KEY_RELEASE_POLL_INTERVAL_MS,
    INSERTION_POPUP_REFOCUS_DELAY_MS,
)
from platforms.windows.coordinates import (
    convert_native_rect,
    screen_for_native_rect,
)
from platforms.windows.foreground import (
    capture_foreground_context,
)
from platforms.windows.hotkey import (
    HotkeyRegistrationError,
    WindowsGlobalHotkey,
)
from platforms.windows.insertion import (
    get_foreground_window_handle,
    global_hotkey_keys_released,
    insert_text_into_native_edit,
    insert_unicode_text,
)
from platforms.windows.startup import (
    is_startup_enabled,
    migrate_legacy_startup_entry,
    set_startup_enabled as set_windows_startup_enabled,
)

from style_constants import (
    STATUS_BAR_DURATION,
    STATUS_HINT_INTERVAL,
)


from tabs.constructor_tab import (
    ConstructorTab,
)

from tabs.edit_tab import EditTab
from tabs.kaomoji_tab import KaomojiTab
from tabs.lists_tab import ListsTab
from tabs.settings_tab import SettingsTab

from validators import (
    validate_kaomoji_content,
    validate_name,
)

from widgets.unicode_status_bar import (
    UnicodeStatusBar,
)


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: SettingsManager,
        translations: TranslationManager,
    ) -> None:
        super().__init__()

        self.settings = settings
        self.translations = translations

        # =========================
        # Window
        # =========================

        self.setWindowTitle(
            WINDOW_TITLE
        )

        self.resize(
            *self.settings.window_size
        )

        # =========================
        # Windows startup
        # =========================

        self.startup_available = (
            sys.platform == "win32"
        )

        self.startup_enabled = False

        if self.startup_available:
            try:
                migrate_legacy_startup_entry(
                    APPLICATION_NAME,
                    ICON_PATH,
                )

            except OSError:
                pass

            self.startup_enabled = (
                is_startup_enabled(
                    APPLICATION_NAME
                )
            )

        # =========================
        # Data
        # =========================

        self.state = AppState.load()

        # None means Constructor is
        # currently in Add mode.
        self.editing_kaomoji: Kaomoji | None = None

        # =========================
        # Tabs
        # =========================

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

        self.constructor_tab = ConstructorTab(
            load_constructor_symbols()
        )

        self.settings_tab = SettingsTab(
            self.translations.available_languages,
            self.settings.language,
            self.settings.show_hints,
            self.settings.add_space_after_insert,
            self.startup_enabled,
            self.startup_available,
            self.settings.hotkey,
            sys.platform == "win32",
            self.settings.window_size,
            self.settings.popup_size,
        )

        self.tabs.addTab(
            self.kaomoji_tab,
            "",
        )

        self.tabs.addTab(
            self.edit_tab,
            "",
        )

        self.tabs.addTab(
            self.lists_tab,
            "",
        )

        self.tabs.addTab(
            self.constructor_tab,
            "",
        )

        self.tabs.addTab(
            self.settings_tab,
            "",
        )

        self.setCentralWidget(
            self.tabs
        )

        # =========================
        # Popup MVP
        # =========================

        self.popup_window = PopupWindow(
            self.state.main_tags,
            self.state.kaomoji,
            self.settings,
        )

        self.popup_window.copy_requested.connect(
            self.insert_kaomoji_from_popup
        )

        self.popup_window.favorite_toggle_requested.connect(
            self.toggle_favorite
        )

        self.popup_window.closed.connect(
            self.clear_popup_target
        )

        self.global_hotkey: (
            WindowsGlobalHotkey | None
        ) = None

        self.tray_controller: (
            TrayController | None
        ) = None

        self.exit_requested = False

        # The external window from which the
        # current popup session was invoked.
        self.popup_target_window_handle: (
            int | None
        ) = None

        self.popup_target_focus_handle: (
            int | None
        ) = None

        # Incremented for every new popup session and again when a popup
        # closes. Delayed refocus callbacks carry the session they belong
        # to, so an old callback can never reactivate a newer popup.
        self.popup_session_id = 0


        # =========================
        # Status bar
        # =========================

        self.status_bar = UnicodeStatusBar()

        self.status_bar.setSizeGripEnabled(
            False
        )

        self.setStatusBar(
            self.status_bar
        )

        self.setup_windows_integration()
        self.setup_tray()

        # =========================
        # Status hints
        # =========================

        self.status_hints: tuple[str, ...] = ()

        self.status_hint_index = 0
        self.status_hints_dismissed = (
            not self.settings.show_hints
        )

        self.status_hint_timer = QTimer(
            self
        )

        self.status_hint_timer.setInterval(
            STATUS_HINT_INTERVAL
        )

        self.status_hint_timer.timeout.connect(
            self.show_next_status_hint
        )

        # =========================
        # Kaomoji tab signals
        # =========================

        self.kaomoji_tab.copy_requested.connect(
            self.copy_kaomoji
        )

        self.kaomoji_tab.favorite_toggle_requested.connect(
            self.toggle_favorite
        )

        self.kaomoji_tab.interaction_started.connect(
            self.dismiss_status_hints
        )

        self.tabs.currentChanged.connect(
            self.on_tab_changed
        )

        # =========================
        # Edit tab signals
        # =========================

        self.edit_tab.edit_kaomoji_requested.connect(
            self.start_edit_kaomoji
        )

        self.edit_tab.delete_kaomoji_requested.connect(
            self.delete_kaomoji
        )

        self.edit_tab.add_main_tag_requested.connect(
            self.add_main_tag
        )

        self.edit_tab.remove_main_tag_requested.connect(
            self.remove_main_tag
        )

        # =========================
        # Lists tab signals
        # =========================

        self.lists_tab.use_list_requested.connect(
            self.switch_list
        )

        self.lists_tab.create_list_requested.connect(
            self.create_list
        )

        self.lists_tab.rename_list_requested.connect(
            self.rename_list
        )

        self.lists_tab.delete_list_requested.connect(
            self.delete_list
        )

        self.lists_tab.export_list_requested.connect(
            self.export_list
        )

        self.lists_tab.import_list_requested.connect(
            self.import_list
        )

        # =========================
        # Constructor signals
        # =========================

        self.constructor_tab.submit_requested.connect(
            self.submit_constructor
        )

        self.constructor_tab.cancel_edit_requested.connect(
            self.cancel_constructor_edit
        )

        # =========================
        # Settings signals
        # =========================

        self.settings_tab.language_changed.connect(
            self.apply_language
        )

        self.settings_tab.show_hints_changed.connect(
            self.set_show_hints
        )

        self.settings_tab.add_space_after_insert_changed.connect(
            self.set_add_space_after_insert
        )

        self.settings_tab.startup_changed.connect(
            self.set_startup_enabled
        )

        self.settings_tab.hotkey_changed.connect(
            self.set_hotkey
        )

        self.settings_tab.window_size_changed.connect(
            self.set_window_size
        )

        self.settings_tab.popup_size_changed.connect(
            self.set_popup_size
        )

        # =========================
        # Translation / hints
        # =========================

        self.retranslate_ui()

        if self.settings.show_hints:
            self.show_next_status_hint()
            self.status_hint_timer.start()

    # =============================
    # Settings / translation
    # =============================

    def build_status_hints(
        self,
    ) -> tuple[str, ...]:
        return (
            self.tr(
                "Mouse: Left = Copy · "
                "Right = Favorite"
            ),
            self.tr(
                "Keyboard: Tab = Section · "
                "Arrows = Navigate · "
                "Enter = Select · "
                "Type to search"
            ),
        )

    def retranslate_ui(
        self,
    ) -> None:
        old_hints = self.status_hints

        current_message = (
            self.status_bar.currentMessage()
        )

        was_showing_hint = (
            current_message in old_hints
        )

        self.tabs.setTabText(
            self.tabs.indexOf(
                self.kaomoji_tab
            ),
            self.tr("Kaomoji"),
        )

        self.tabs.setTabText(
            self.tabs.indexOf(
                self.edit_tab
            ),
            self.tr("Edit"),
        )

        self.tabs.setTabText(
            self.tabs.indexOf(
                self.lists_tab
            ),
            self.tr("Lists"),
        )

        self.tabs.setTabText(
            self.tabs.indexOf(
                self.constructor_tab
            ),
            self.tr("Constructor"),
        )

        self.tabs.setTabText(
            self.tabs.indexOf(
                self.settings_tab
            ),
            self.tr("Settings"),
        )

        self.kaomoji_tab.retranslate_ui()
        self.settings_tab.retranslate_ui()

        if self.tray_controller is not None:
            self.tray_controller.retranslate_ui()

        self.status_hints = (
            self.build_status_hints()
        )

        if (
            was_showing_hint
            and not self.status_hints_dismissed
        ):
            self.status_hint_index = 0
            self.status_bar.clearMessage()
            self.show_next_status_hint()

    def changeEvent(
        self,
        event: QEvent,
    ) -> None:
        super().changeEvent(
            event
        )

        if (
            event.type()
            == QEvent.Type.LanguageChange
        ):
            self.retranslate_ui()

    def apply_language(
        self,
        preference: str,
    ) -> str:
        self.settings.language = preference

        return self.translations.apply_language(
            preference
        )

    def set_show_hints(
        self,
        enabled: bool,
    ) -> None:
        self.settings.show_hints = enabled

        if enabled:
            self.status_hints_dismissed = False
            self.status_hint_index = 0
            self.show_next_status_hint()
            self.status_hint_timer.start()
            return

        self.dismiss_status_hints()

    def set_add_space_after_insert(
        self,
        enabled: bool,
    ) -> None:
        self.settings.add_space_after_insert = enabled

    def set_startup_enabled(
        self,
        enabled: bool,
    ) -> None:
        if not self.startup_available:
            return

        try:
            set_windows_startup_enabled(
                APPLICATION_NAME,
                enabled,
                ICON_PATH,
            )

        except OSError as error:
            current = is_startup_enabled(
                APPLICATION_NAME
            )

            self.sync_startup_controls(
                current
            )

            self.status_bar.showMessage(
                (
                    "Could not change Windows "
                    f"startup setting: {error}"
                ),
                STATUS_BAR_DURATION,
            )

            return

        self.startup_enabled = enabled

        self.sync_startup_controls(
            enabled
        )

    def sync_startup_controls(
        self,
        enabled: bool,
    ) -> None:
        self.settings_tab.set_startup_enabled(
            enabled
        )

    def set_hotkey(
        self,
        modifier: str,
        key: str,
    ) -> None:
        if sys.platform != "win32":
            return

        app = QApplication.instance()

        if app is None:
            return

        current_config = self.settings.hotkey

        if (
            self.global_hotkey is not None
            and (
                self.global_hotkey.modifier,
                self.global_hotkey.key,
            )
            == (
                modifier,
                key,
            )
        ):
            return

        previous_hotkey = self.global_hotkey

        if previous_hotkey is not None:
            previous_hotkey.unregister()

        candidate = WindowsGlobalHotkey(
            app,
            modifier,
            key,
            self,
        )

        candidate.activated.connect(
            self.show_popup
        )

        try:
            candidate.register()

        except HotkeyRegistrationError:
            candidate.deleteLater()

            restored = False

            if previous_hotkey is not None:
                try:
                    previous_hotkey.register()
                    restored = True
                except HotkeyRegistrationError:
                    self.global_hotkey = None

            self.settings_tab.set_hotkey(
                *current_config
            )

            requested_label = (
                f"{modifier}+{key}"
            )

            if restored:
                previous_label = (
                    f"{current_config[0]}+"
                    f"{current_config[1]}"
                )

                message = (
                    f"Could not register {requested_label}. "
                    f"{previous_label} is still active."
                )
            else:
                message = (
                    f"Could not register {requested_label}."
                )

            self.status_bar.showMessage(
                message,
                STATUS_BAR_DURATION,
            )

            return

        self.global_hotkey = candidate

        if previous_hotkey is not None:
            previous_hotkey.deleteLater()

        self.settings.set_hotkey(
            modifier,
            key,
        )

        self.settings_tab.set_hotkey(
            modifier,
            key,
        )

        self.status_bar.showMessage(
            (
                "Popup hotkey changed to "
                f"{candidate.label}."
            ),
            STATUS_BAR_DURATION,
        )

    def set_window_size(
        self,
        width: int,
        height: int,
    ) -> None:
        self.settings.set_window_size(
            width,
            height,
        )

        self.resize(
            width,
            height,
        )

    def set_popup_size(
        self,
        width: int,
        height: int,
    ) -> None:
        self.settings.set_popup_size(
            width,
            height,
        )

        self.popup_window.set_popup_size(
            width,
            height,
        )

    # =============================
    # Favorites
    # =============================

    def toggle_favorite(
        self,
        kaomoji: Kaomoji,
    ) -> None:
        is_favorite = (
            self.state.toggle_favorite(
                kaomoji
            )
        )

        if is_favorite:
            message = (
                "Added to favorites: "
                f"{kaomoji['text']}"
            )

        else:
            message = (
                "Removed from favorites: "
                f"{kaomoji['text']}"
            )

        self.status_bar.showMessage(
            message,
            STATUS_BAR_DURATION,
        )

        self.kaomoji_tab.refresh()
        self.popup_window.refresh()

    # =============================
    # View refresh
    # =============================

    def refresh_kaomoji_views(
        self,
    ) -> None:
        self.kaomoji_tab.set_kaomoji(
            self.state.kaomoji
        )

        self.edit_tab.set_kaomoji(
            self.state.kaomoji
        )

        self.popup_window.set_kaomoji(
            self.state.kaomoji
        )

    def refresh_main_tag_views(
        self,
    ) -> None:
        self.kaomoji_tab.set_main_tags(
            self.state.main_tags
        )

        self.edit_tab.set_main_tags(
            self.state.main_tags
        )

        self.popup_window.set_main_tags(
            self.state.main_tags
        )

    def refresh_active_list_views(
        self,
    ) -> None:
        self.kaomoji_tab.set_main_tags(
            self.state.main_tags
        )

        self.kaomoji_tab.set_kaomoji(
            self.state.kaomoji
        )

        self.edit_tab.set_main_tags(
            self.state.main_tags
        )

        self.edit_tab.set_kaomoji(
            self.state.kaomoji
        )

        self.popup_window.set_main_tags(
            self.state.main_tags
        )

        self.popup_window.set_kaomoji(
            self.state.kaomoji
        )

    def refresh_lists_view(
        self,
    ) -> None:
        self.lists_tab.set_lists(
            self.state.list_names,
            self.state.active_list_name,
        )

    # =============================
    # Constructor mode
    # =============================

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
            "tags": list(
                kaomoji["tags"]
            ),
        }

        self.constructor_tab.load_for_edit(
            data
        )

        self.tabs.setCurrentWidget(
            self.constructor_tab
        )

    def submit_constructor(
        self,
        input_data: KaomojiInput,
    ) -> None:
        content_error = (
            validate_kaomoji_content(
                input_data["text"],
                input_data["tags"],
            )
        )

        if content_error is not None:
            self.status_bar.showMessage(
                content_error,
                STATUS_BAR_DURATION,
            )
            return

        existing_names = (
            self.state.existing_kaomoji_names(
                exclude=self.editing_kaomoji
            )
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
            self.add_constructor_kaomoji(
                input_data
            )
        else:
            self.update_constructor_kaomoji(
                input_data
            )

    def add_constructor_kaomoji(
        self,
        input_data: KaomojiInput,
    ) -> None:
        new_kaomoji = (
            self.state.add_kaomoji(
                input_data
            )
        )

        self.refresh_kaomoji_views()
        self.constructor_tab.reset_form()

        self.status_bar.showMessage(
            (
                "Added: "
                f"{new_kaomoji['text']}"
            ),
            STATUS_BAR_DURATION,
        )

    def update_constructor_kaomoji(
        self,
        input_data: KaomojiInput,
    ) -> None:
        if self.editing_kaomoji is None:
            return

        edited_kaomoji = (
            self.editing_kaomoji
        )

        self.state.update_kaomoji(
            edited_kaomoji,
            input_data,
        )

        self.refresh_kaomoji_views()

        self.editing_kaomoji = None
        self.constructor_tab.reset_form()

        self.status_bar.showMessage(
            (
                "Updated: "
                f"{edited_kaomoji['text']}"
            ),
            STATUS_BAR_DURATION,
        )

    # =============================
    # Delete kaomoji
    # =============================

    def delete_kaomoji(
        self,
        kaomoji: Kaomoji,
    ) -> None:
        name = kaomoji["name"]
        description = (
            name if name else kaomoji["text"]
        )

        answer = QMessageBox.question(
            self,
            "Delete kaomoji",
            (
                f'Delete "{description}"?\n\n'
                "Are you sure?"
            ),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.No,
        )

        if (
            answer
            != QMessageBox.StandardButton.Yes
        ):
            return

        if kaomoji is self.editing_kaomoji:
            self.cancel_constructor_edit()

        self.state.delete_kaomoji(
            kaomoji
        )

        self.refresh_kaomoji_views()

        self.status_bar.showMessage(
            (
                "Deleted: "
                f"{kaomoji['text']}"
            ),
            STATUS_BAR_DURATION,
        )

    # =============================
    # Main tags
    # =============================

    def add_main_tag(
        self,
        tag: str,
    ) -> None:
        try:
            added = self.state.add_main_tag(
                tag
            )
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
            (
                "Main tag added: "
                f"{tag}"
            ),
            STATUS_BAR_DURATION,
        )

    def remove_main_tag(
        self,
        tag: str,
    ) -> None:
        if not self.state.remove_main_tag(
            tag
        ):
            return

        self.refresh_main_tag_views()

        self.status_bar.showMessage(
            (
                "Main tag removed: "
                f"{tag}"
            ),
            STATUS_BAR_DURATION,
        )

    # =============================
    # Switch list
    # =============================

    def switch_list(
        self,
        name: str,
    ) -> None:
        try:
            changed = self.state.switch_list(
                name
            )
        except ValueError as error:
            self.status_bar.showMessage(
                str(error),
                STATUS_BAR_DURATION,
            )
            return

        if not changed:
            return

        self.cancel_constructor_edit()
        self.refresh_active_list_views()
        self.refresh_lists_view()

        self.status_bar.showMessage(
            (
                "Active list: "
                f"{self.state.active_list_name}"
            ),
            STATUS_BAR_DURATION,
        )

    # =============================
    # Create list
    # =============================

    def create_list(
        self,
        name: str,
    ) -> None:
        try:
            new_list = self.state.create_list(
                name
            )
        except ValueError as error:
            self.status_bar.showMessage(
                str(error),
                STATUS_BAR_DURATION,
            )
            return

        self.cancel_constructor_edit()
        self.refresh_active_list_views()
        self.refresh_lists_view()
        self.lists_tab.clear_new_list_name()

        self.status_bar.showMessage(
            (
                "List created: "
                f"{new_list['name']}"
            ),
            STATUS_BAR_DURATION,
        )

    # =============================
    # Rename list
    # =============================

    def rename_list(
        self,
        name: str,
    ) -> None:
        new_name, accepted = (
            QInputDialog.getText(
                self,
                "Rename list",
                "List name:",
                text=name,
            )
        )

        if not accepted:
            return

        new_name = new_name.strip()

        if new_name == name:
            return

        try:
            renamed_list = (
                self.state.rename_list(
                    name,
                    new_name,
                )
            )
        except ValueError as error:
            self.status_bar.showMessage(
                str(error),
                STATUS_BAR_DURATION,
            )
            return

        self.refresh_lists_view()

        self.status_bar.showMessage(
            (
                "List renamed: "
                f"{renamed_list['name']}"
            ),
            STATUS_BAR_DURATION,
        )

    # =============================
    # Delete list
    # =============================

    def delete_list(
        self,
        name: str,
    ) -> None:
        answer = QMessageBox.question(
            self,
            "Delete list",
            (
                f'Delete list "{name}"?\n\n'
                "All kaomoji in this list "
                "will be deleted."
            ),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.No,
        )

        if (
            answer
            != QMessageBox.StandardButton.Yes
        ):
            return

        try:
            was_active = self.state.delete_list(
                name
            )
        except ValueError as error:
            self.status_bar.showMessage(
                str(error),
                STATUS_BAR_DURATION,
            )
            return

        if was_active:
            self.cancel_constructor_edit()
            self.refresh_active_list_views()

        self.refresh_lists_view()

        self.status_bar.showMessage(
            (
                "List deleted: "
                f"{name}"
            ),
            STATUS_BAR_DURATION,
        )

    # =============================
    # Export list
    # =============================

    def export_list(
        self,
        name: str,
    ) -> None:
        kaomoji_list = self.state.find_list(
            name
        )

        if kaomoji_list is None:
            self.status_bar.showMessage(
                (
                    "List does not exist: "
                    f"{name}"
                ),
                STATUS_BAR_DURATION,
            )

            return

        file_path, _ = (
            QFileDialog.getSaveFileName(
                self,
                "Export Kaokey list",
                "",
                LIST_FILE_FILTER,
            )
        )

        if not file_path:
            return

        try:
            saved_path = (
                export_kaomoji_list(
                    file_path,
                    kaomoji_list,
                )
            )

        except ValueError as error:
            QMessageBox.warning(
                self,
                "Export failed",
                str(error),
            )

            return

        self.status_bar.showMessage(
            (
                "List exported: "
                f"{saved_path.name}"
            ),
            STATUS_BAR_DURATION,
        )

    # =============================
    # Import list
    # =============================

    def import_list(
        self,
    ) -> None:
        file_path, _ = (
            QFileDialog.getOpenFileName(
                self,
                "Import Kaokey list",
                "",
                LIST_FILE_FILTER,
            )
        )

        if not file_path:
            return

        try:
            imported_list = (
                import_kaomoji_list(
                    file_path
                )
            )

        except ValueError as error:
            QMessageBox.warning(
                self,
                "Import failed",
                str(error),
            )

            return

        mode = self.choose_import_mode(
            imported_list["name"]
        )

        if mode is None:
            return

        if mode == "new":
            self.import_as_new_list(
                imported_list
            )

        elif mode == "merge":
            self.merge_into_current_list(
                imported_list
            )

    def choose_import_mode(
        self,
        imported_name: str,
    ) -> str | None:
        message_box = QMessageBox(
            self
        )

        message_box.setWindowTitle(
            "Import list"
        )

        message_box.setText(
            (
                f'Import "{imported_name}"\n\n'
                "How should it be imported?"
            )
        )

        add_button = (
            message_box.addButton(
                "Add as new list",
                QMessageBox.ButtonRole.AcceptRole,
            )
        )

        merge_button = (
            message_box.addButton(
                "Merge into current",
                QMessageBox.ButtonRole.ActionRole,
            )
        )

        message_box.addButton(
            QMessageBox.StandardButton.Cancel
        )

        message_box.exec()

        clicked_button = (
            message_box.clickedButton()
        )

        if clicked_button is add_button:
            return "new"

        if clicked_button is merge_button:
            return "merge"

        return None

    # =============================
    # Import as new list
    # =============================

    def import_as_new_list(
        self,
        imported_list: KaomojiList,
    ) -> None:
        new_list = (
            self.state.import_as_new_list(
                imported_list
            )
        )

        self.cancel_constructor_edit()
        self.refresh_active_list_views()
        self.refresh_lists_view()

        self.status_bar.showMessage(
            (
                "List imported: "
                f"{new_list['name']}"
            ),
            STATUS_BAR_DURATION,
        )

    # =============================
    # Merge into current list
    # =============================

    def merge_into_current_list(
        self,
        imported_list: KaomojiList,
    ) -> None:
        report = (
            self.state.merge_into_current_list(
                imported_list
            )
        )

        self.refresh_active_list_views()

        self.status_bar.showMessage(
            (
                f"Added: {report['added']} | "
                "Main tags added: "
                f"{report['main_tags_added']}"
            ),
            STATUS_BAR_DURATION,
        )

    # =============================
    # System tray
    # =============================

    def setup_tray(
        self,
    ) -> None:
        if not TrayController.is_available():
            return

        tray = TrayController(
            self
        )

        tray.open_requested.connect(
            self.show_main_window
        )

        tray.settings_requested.connect(
            self.show_settings_window
        )

        tray.close_requested.connect(
            self.quit_application
        )

        self.tray_controller = tray

        app = QApplication.instance()

        if app is not None:
            app.setQuitOnLastWindowClosed(
                False
            )

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
        self.tabs.setCurrentWidget(
            self.settings_tab
        )

        self.show_main_window()

    def quit_application(
        self,
    ) -> None:
        self.exit_requested = True

        self.popup_window.close()

        if self.global_hotkey is not None:
            self.global_hotkey.unregister()
            self.global_hotkey = None

        if self.tray_controller is not None:
            self.tray_controller.hide()

        app = QApplication.instance()

        if app is not None:
            app.quit()

    # =============================
    # Popup / Windows hotkey
    # =============================

    def setup_windows_integration(
        self,
    ) -> None:
        if sys.platform != "win32":
            return

        app = QApplication.instance()

        if app is None:
            return

        modifier, key = self.settings.hotkey

        hotkey = WindowsGlobalHotkey(
            app,
            modifier,
            key,
            self,
        )

        hotkey.activated.connect(
            self.show_popup
        )

        try:
            hotkey.register()
        except HotkeyRegistrationError:
            self.status_bar.showMessage(
                (
                    "Could not register global "
                    f"hotkey {hotkey.label}."
                ),
                STATUS_BAR_DURATION,
            )
            return

        self.global_hotkey = hotkey

    def show_popup(
        self,
    ) -> None:
        # If the popup itself already owns focus,
        # there is no external caret to recapture.
        # Treat another hotkey press as a fresh
        # popup invocation without moving the window.
        if (
            self.popup_window.isVisible()
            and self.popup_window.isActiveWindow()
        ):
            self.popup_window.reset_search()
            self.popup_window.raise_()
            self.popup_window.activateWindow()
            self.popup_window.focus_search()
            return

        self.popup_session_id += 1

        caret_rect = None
        fallback_screen = self.screen()

        if sys.platform == "win32":
            context = (
                capture_foreground_context()
            )

            # Only an external application is a
            # valid automatic-insertion target.
            # Invoking the popup from Kaokey itself
            # intentionally clears the target so a
            # stale application cannot receive text.
            if self.isActiveWindow():
                self.popup_target_window_handle = None
                self.popup_target_focus_handle = None
            else:
                self.popup_target_window_handle = (
                    context.window_handle
                )
                self.popup_target_focus_handle = (
                    context.focus_window_handle
                )

            screens = QApplication.screens()

            if context.window_rect is not None:
                screen = screen_for_native_rect(
                    context.window_rect,
                    screens,
                )

                if screen is not None:
                    fallback_screen = screen

            if context.caret_rect is not None:
                converted = convert_native_rect(
                    context.caret_rect,
                    screens,
                )

                if converted is not None:
                    caret_rect, caret_screen = converted
                    fallback_screen = caret_screen

        # Qt widgets expose their caret more
        # reliably through Qt than through
        # GetGUIThreadInfo(). Only use this
        # fallback while Kaokey itself is the
        # active application so stale Qt focus
        # is never used for another app.
        if (
            caret_rect is None
            and self.isActiveWindow()
        ):
            caret_rect = (
                self.popup_window.current_qt_caret_rect()
            )

        self.popup_window.show_popup(
            caret_rect,
            fallback_screen,
        )

    # =============================
    # Popup insertion
    # =============================

    def insert_kaomoji_from_popup(
        self,
        kaomoji: Kaomoji,
    ) -> None:
        self.try_popup_insertion(
            kaomoji,
            INSERTION_KEY_RELEASE_MAX_ATTEMPTS,
        )

    def try_popup_insertion(
        self,
        kaomoji: Kaomoji,
        attempts_left: int,
    ) -> None:
        # Windows keeps the physical keyboard state when SendInput runs,
        # so insertion must wait until the currently configured global
        # hotkey keys are actually released.
        if (
            sys.platform == "win32"
            and self.global_hotkey is not None
            and not global_hotkey_keys_released(
                self.global_hotkey.release_virtual_keys
            )
            and attempts_left > 0
        ):
            QTimer.singleShot(
                INSERTION_KEY_RELEASE_POLL_INTERVAL_MS,
                lambda: self.try_popup_insertion(
                    kaomoji,
                    attempts_left - 1,
                ),
            )
            return

        base_text = kaomoji[
            "text"
        ]

        text = base_text

        if self.settings.add_space_after_insert:
            text += " "

        inserted = False
        direct_native_insert = False

        if sys.platform == "win32":
            direct_native_insert = (
                insert_text_into_native_edit(
                    self.popup_target_focus_handle,
                    text,
                )
            )

            inserted = direct_native_insert

            if (
                not inserted
                and self.popup_target_window_handle
                is not None
            ):
                self.popup_window.suspend_auto_close()

                inserted = insert_unicode_text(
                    self.popup_target_window_handle,
                    text,
                )

        if not inserted:
            # Clipboard remains a fallback only. A successful automatic
            # insertion never reads or modifies the user's clipboard.
            self.copy_text_to_clipboard(
                text
            )

            if self.popup_window.auto_close_suspended:
                self.popup_window.restore_after_external_action()

            return

        self.status_bar.showMessage(
            (
                "Inserted: "
                f"{base_text}"
            ),
            STATUS_BAR_DURATION,
        )

        if not direct_native_insert:
            session_id = self.popup_session_id

            QTimer.singleShot(
                INSERTION_POPUP_REFOCUS_DELAY_MS,
                lambda: self.restore_popup_after_insertion(
                    session_id
                ),
            )

    def restore_popup_after_insertion(
        self,
        session_id: int,
    ) -> None:
        # A delayed callback from an old/closed popup must never reactivate a
        # new popup session.
        if (
            session_id
            != self.popup_session_id
            or not self.popup_window.isVisible()
        ):
            return

        if (
            sys.platform == "win32"
            and self.popup_target_window_handle
            is not None
        ):
            foreground_handle = (
                get_foreground_window_handle()
            )

            # After successful SendInput the target app should still own the
            # foreground until Kaokey deliberately takes it back. If another
            # app owns it now, the user switched away during the handoff:
            # end this popup session instead of stealing focus back.
            if (
                foreground_handle is not None
                and foreground_handle
                != self.popup_target_window_handle
            ):
                self.popup_window.close()
                return

        self.popup_window.restore_after_external_action()

    def clear_popup_target(
        self,
    ) -> None:
        # Closing/deactivating the popup ends the insertion session. A later
        # global-hotkey invocation must capture the foreground app again.
        self.popup_target_window_handle = None
        self.popup_target_focus_handle = None
        self.popup_session_id += 1

    # =============================
    # Clipboard
    # =============================

    def copy_kaomoji(
        self,
        kaomoji: Kaomoji,
    ) -> None:
        self.copy_text_to_clipboard(
            kaomoji[
                "text"
            ]
        )

    def copy_text_to_clipboard(
        self,
        text: str,
    ) -> None:
        clipboard = (
            QApplication.clipboard()
        )

        clipboard.setText(
            text
        )

        self.status_bar.showMessage(
            (
                "Copied: "
                f"{text.rstrip()}"
            ),
            STATUS_BAR_DURATION,
        )


    # =============================
    # Window lifecycle
    # =============================

    def closeEvent(
        self,
        event: QCloseEvent,
    ) -> None:
        if (
            self.tray_controller is not None
            and not self.exit_requested
        ):
            self.popup_window.close()
            self.hide()
            event.ignore()
            return

        if self.global_hotkey is not None:
            self.global_hotkey.unregister()
            self.global_hotkey = None

        self.popup_window.close()

        if self.tray_controller is not None:
            self.tray_controller.hide()

        super().closeEvent(
            event
        )


    # =============================
    # Status hints
    # =============================

    def show_next_status_hint(
        self,
    ) -> None:
        if self.status_hints_dismissed:
            return

        if (
            self.tabs.currentWidget()
            is not self.kaomoji_tab
        ):
            return

        current_message = (
            self.status_bar.currentMessage()
        )

        # Do not overwrite a real status
        # message such as "Added" or
        # "List imported".
        if (
            current_message
            and current_message
            not in self.status_hints
        ):
            return

        message = self.status_hints[
            self.status_hint_index
        ]

        self.status_bar.showMessage(
            message
        )

        self.status_hint_index = (
            self.status_hint_index + 1
        ) % len(
            self.status_hints
        )


    def dismiss_status_hints(
        self,
    ) -> None:
        if self.status_hints_dismissed:
            return

        self.status_hints_dismissed = True

        self.status_hint_timer.stop()

        if (
            self.status_bar.currentMessage()
            in self.status_hints
        ):
            self.status_bar.clearMessage()


    def on_tab_changed(
        self,
        _index: int,
    ) -> None:
        if self.status_hints_dismissed:
            return

        if (
            self.tabs.currentWidget()
            is self.kaomoji_tab
        ):
            self.show_next_status_hint()

            return

        if (
            self.status_bar.currentMessage()
            in self.status_hints
        ):
            self.status_bar.clearMessage()

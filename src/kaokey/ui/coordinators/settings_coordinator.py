import sys

from PySide6.QtCore import QObject
from PySide6.QtWidgets import (
    QMainWindow,
    QStatusBar,
)

from kaokey.config.constants import (
    APPLICATION_NAME,
    ICON_PATH,
)
from kaokey.config.i18n import TranslationManager
from kaokey.config.settings import SettingsManager
from kaokey.platforms.popup_backend import PopupHotkeyRegistrationError
from kaokey.platforms.windows.startup import (
    is_startup_enabled,
    migrate_legacy_startup_entry,
)
from kaokey.platforms.windows.startup import (
    set_startup_enabled as set_windows_startup_enabled,
)
from kaokey.ui.controllers.status_hints import StatusHintsController
from kaokey.ui.coordinators.popup_coordinator import PopupCoordinator
from kaokey.ui.popup.popup_window import PopupWindow
from kaokey.ui.styling.style_constants import STATUS_BAR_DURATION
from kaokey.ui.tabs.settings_tab import SettingsTab


class SettingsCoordinator(QObject):
    """Coordinates settings UI with application and popup services."""

    def __init__(
        self,
        settings: SettingsManager,
        translations: TranslationManager,
        window: QMainWindow,
        popup_window: PopupWindow,
        popup_coordinator: PopupCoordinator,
        status_hints: StatusHintsController,
        status_bar: QStatusBar,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self.settings = settings
        self.translations = translations
        self.window = window
        self.popup_window = popup_window
        self.popup_coordinator = popup_coordinator
        self.status_hints = status_hints
        self.status_bar = status_bar

        self.startup_available = sys.platform == "win32"
        self.startup_enabled = self._load_startup_state()

        self.tab = SettingsTab(
            self.translations.available_languages,
            self.settings.language,
            self.settings.show_hints,
            self.settings.add_space_after_insert,
            self.startup_enabled,
            self.startup_available,
            self.settings.minimize_to_tray_on_close,
            self.settings.hotkey,
            self.popup_coordinator.hotkey_available,
            self.settings.window_size,
            self.settings.popup_size,
        )

        self.tab.language_changed.connect(self.apply_language)
        self.tab.show_hints_changed.connect(self.set_show_hints)
        self.tab.add_space_after_insert_changed.connect(
            self.set_add_space_after_insert
        )
        self.tab.startup_changed.connect(self.set_startup_enabled)
        self.tab.hotkey_changed.connect(self.set_hotkey)
        self.tab.window_size_changed.connect(self.set_window_size)
        self.tab.popup_size_changed.connect(self.set_popup_size)
        self.tab.minimize_to_tray_on_close_changed.connect(
            self.set_minimize_to_tray_on_close
        )

    def _load_startup_state(
        self,
    ) -> bool:
        if not self.startup_available:
            return False

        try:
            migrate_legacy_startup_entry(
                APPLICATION_NAME,
                ICON_PATH,
            )
        except OSError:
            pass

        return is_startup_enabled(APPLICATION_NAME)

    def apply_language(
        self,
        preference: str,
    ) -> str:
        self.settings.language = preference
        return self.translations.apply_language(preference)

    def set_show_hints(
        self,
        enabled: bool,
    ) -> None:
        self.settings.show_hints = enabled
        self.status_hints.set_enabled(enabled)

    def set_add_space_after_insert(
        self,
        enabled: bool,
    ) -> None:
        self.settings.add_space_after_insert = enabled

    def set_minimize_to_tray_on_close(
        self,
        enabled: bool,
    ) -> None:
        self.settings.minimize_to_tray_on_close = enabled

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
            current = is_startup_enabled(APPLICATION_NAME)
            self.sync_startup_controls(current)

            self.status_bar.showMessage(
                f"Could not change Windows startup setting: {error}",
                STATUS_BAR_DURATION,
            )
            return

        self.startup_enabled = enabled
        self.sync_startup_controls(enabled)

    def sync_startup_controls(
        self,
        enabled: bool,
    ) -> None:
        self.tab.set_startup_enabled(enabled)

    def set_hotkey(
        self,
        modifier: str,
        key: str,
    ) -> None:
        if not self.popup_coordinator.hotkey_available:
            return

        current_config = self.settings.hotkey
        active_hotkey = self.popup_coordinator.active_hotkey

        if active_hotkey is not None and (
            active_hotkey.modifier,
            active_hotkey.key,
        ) == (
            modifier,
            key,
        ):
            return

        try:
            hotkey = self.popup_coordinator.set_hotkey(
                modifier,
                key,
            )
        except PopupHotkeyRegistrationError as error:
            self.tab.set_hotkey(*current_config)

            requested_label = f"{modifier}+{key}"

            if error.previous_hotkey_restored:
                previous_label = f"{current_config[0]}+{current_config[1]}"
                message = (
                    f"Could not register {requested_label}. "
                    f"{previous_label} is still active."
                )
            else:
                message = f"Could not register {requested_label}."

            self.status_bar.showMessage(
                message,
                STATUS_BAR_DURATION,
            )
            return

        self.settings.set_hotkey(
            modifier,
            key,
        )
        self.tab.set_hotkey(
            modifier,
            key,
        )

        self.status_bar.showMessage(
            f"Popup hotkey changed to {hotkey.label}.",
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
        self.window.resize(
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

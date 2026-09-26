from collections.abc import Callable

from PySide6.QtCore import (
    QObject,
    QTimer,
)
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QStatusBar,
)

from kaokey.config.popup_constants import (
    INSERTION_KEY_RELEASE_MAX_ATTEMPTS,
    INSERTION_KEY_RELEASE_POLL_INTERVAL_MS,
    INSERTION_POPUP_REFOCUS_DELAY_MS,
)
from kaokey.config.settings import SettingsManager
from kaokey.core.models import Kaomoji
from kaokey.platforms.popup_backend import (
    PopupBackend,
    PopupHotkey,
    PopupHotkeyRegistrationError,
    create_popup_backend,
)
from kaokey.ui.popup.popup_window import PopupWindow
from kaokey.ui.styling.style_constants import STATUS_BAR_DURATION


class PopupCoordinator(QObject):
    """Coordinates popup sessions without depending on a specific OS API."""

    def __init__(
        self,
        host_window: QMainWindow,
        popup_window: PopupWindow,
        settings: SettingsManager,
        status_bar: QStatusBar,
        copy_text: Callable[[str], None],
        parent: QObject | None = None,
        backend: PopupBackend | None = None,
    ) -> None:
        super().__init__(parent)

        self.host_window = host_window
        self.popup_window = popup_window
        self.settings = settings
        self.status_bar = status_bar
        self.copy_text = copy_text

        app = QApplication.instance()

        if not isinstance(
            app,
            QApplication,
        ):
            raise RuntimeError("PopupCoordinator requires QApplication.")

        if backend is None:
            backend = create_popup_backend(
                app,
                self,
            )

        self.backend = backend

        self.target: object | None = None
        self.session_id = 0

        self.popup_window.copy_requested.connect(
            self.insert_kaomoji_from_popup
        )
        self.popup_window.closed.connect(self.clear_target)

    @property
    def hotkey_available(
        self,
    ) -> bool:
        return self.backend.available

    @property
    def active_hotkey(
        self,
    ) -> PopupHotkey | None:
        return self.backend.active_hotkey

    def setup_hotkey(
        self,
        modifier: str,
        key: str,
    ) -> None:
        if not self.backend.available:
            return

        try:
            self.set_hotkey(
                modifier,
                key,
            )
        except PopupHotkeyRegistrationError:
            self.status_bar.showMessage(
                f"Could not register global hotkey {modifier}+{key}.",
                STATUS_BAR_DURATION,
            )

    def set_hotkey(
        self,
        modifier: str,
        key: str,
    ) -> PopupHotkey:
        return self.backend.set_hotkey(
            modifier,
            key,
            self.show_popup,
        )

    def show_popup(
        self,
    ) -> None:
        if self.popup_window.isVisible() and self.popup_window.isActiveWindow():
            self.popup_window.reset_search()
            self.popup_window.raise_()
            self.popup_window.activateWindow()
            self.popup_window.focus_search()
            return

        self.session_id += 1

        screens = QApplication.screens()
        context = self.backend.capture_context(screens)

        if self.host_window.isActiveWindow():
            self.target = None
        else:
            self.target = context.target

        caret_rect = context.caret_rect
        fallback_screen = context.fallback_screen or self.host_window.screen()

        if caret_rect is None and self.host_window.isActiveWindow():
            caret_rect = self.popup_window.current_qt_caret_rect()

        self.popup_window.show_popup(
            caret_rect,
            fallback_screen,
        )

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
        if (
            self.active_hotkey is not None
            and not self.backend.hotkey_keys_released()
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

        base_text = kaomoji["text"]
        text = base_text

        if self.settings.add_space_after_insert:
            text += " "

        result = None

        if self.target is not None:
            result = self.backend.insert_text(
                self.target,
                text,
                before_focus_transfer=self.popup_window.suspend_auto_close,
            )

        if result is None or not result.inserted:
            self.copy_text(text)

            if self.popup_window.auto_close_suspended:
                self.popup_window.restore_after_external_action()

            return

        self.status_bar.showMessage(
            f"Inserted: {base_text}",
            STATUS_BAR_DURATION,
        )

        if result.focus_transferred:
            session_id = self.session_id

            QTimer.singleShot(
                INSERTION_POPUP_REFOCUS_DELAY_MS,
                lambda: self.restore_popup_after_insertion(session_id),
            )

    def restore_popup_after_insertion(
        self,
        session_id: int,
    ) -> None:
        if session_id != self.session_id or not self.popup_window.isVisible():
            return

        if self.target is not None and not self.backend.target_still_active(
            self.target
        ):
            self.popup_window.close()
            return

        self.popup_window.restore_after_external_action()

    def clear_target(
        self,
    ) -> None:
        self.target = None
        self.session_id += 1

    def shutdown(
        self,
    ) -> None:
        self.backend.clear_hotkey()

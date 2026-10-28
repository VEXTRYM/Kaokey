from collections.abc import Callable
from pathlib import Path
from typing import cast

from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtWidgets import QApplication, QMainWindow, QStatusBar

from kaokey.config.i18n import TranslationManager
from kaokey.config.settings import SettingsManager
from kaokey.platforms.popup_backend import (
    PopupHotkey,
    PopupHotkeyRegistrationError,
)
from kaokey.platforms.startup import UnavailableStartupBackend
from kaokey.ui.controllers.status_hints import StatusHintsController
from kaokey.ui.coordinators.popup_coordinator import PopupCoordinator
from kaokey.ui.coordinators.settings_coordinator import SettingsCoordinator
from kaokey.ui.popup.popup_window import PopupWindow


class DeferredPopupCoordinator(QObject):
    hotkey_registered = Signal(object)
    hotkey_available = True
    active_hotkey = PopupHotkey("Alt", "K", "Super+K", True)

    def __init__(self) -> None:
        super().__init__()
        self.requests: list[
            tuple[str, str, Callable[[PopupHotkey], None]]
        ] = []

    def set_hotkey(
        self,
        modifier: str,
        key: str,
        *,
        on_registered: Callable[[PopupHotkey], None],
        on_error: Callable[[PopupHotkeyRegistrationError], None],
    ) -> None:
        del on_error
        self.requests.append((modifier, key, on_registered))


def test_reverting_hotkey_submits_request_that_cancels_pending_registration(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    settings = SettingsManager(
        QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )
    settings.set_hotkey("Alt", "K")
    popup = PopupWindow([], [], settings)
    host = QMainWindow()
    status = QStatusBar()
    fake_popup = DeferredPopupCoordinator()
    coordinator = SettingsCoordinator(
        settings,
        TranslationManager(qapp),
        host,
        popup,
        cast(PopupCoordinator, fake_popup),
        cast(StatusHintsController, object()),
        status,
        startup_backend=UnavailableStartupBackend(),
    )

    coordinator.set_hotkey("Alt", "J")
    coordinator.set_hotkey("Alt", "K")
    assert [(modifier, key) for modifier, key, _ in fake_popup.requests] == [
        ("Alt", "J"),
        ("Alt", "K"),
    ]

    fake_popup.requests[0][2](PopupHotkey("Alt", "J", "Alt+J", True))
    assert settings.hotkey == ("Alt", "K")
    fake_popup.requests[1][2](PopupHotkey("Alt", "K", "Super+K", True))
    assert not coordinator._hotkey_change_pending
    assert settings.hotkey == ("Alt", "K")

    coordinator.tab.deleteLater()
    popup.deleteLater()
    host.deleteLater()


def test_failed_startup_change_reconciles_cached_state(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    class PartiallyFailingStartupBackend:
        available = True
        enabled = False

        def initialize(self, app_name: str, icon_path: Path) -> None:
            del app_name, icon_path

        def is_enabled(self, app_name: str) -> bool:
            del app_name
            return self.enabled

        def set_enabled(
            self, app_name: str, enabled: bool, icon_path: Path
        ) -> None:
            del app_name, icon_path
            self.enabled = enabled
            raise OSError("startup write failed")

    settings = SettingsManager(
        QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )
    popup = PopupWindow([], [], settings)
    host = QMainWindow()
    status = QStatusBar()
    coordinator = SettingsCoordinator(
        settings,
        TranslationManager(qapp),
        host,
        popup,
        cast(PopupCoordinator, DeferredPopupCoordinator()),
        cast(StatusHintsController, object()),
        status,
        startup_backend=PartiallyFailingStartupBackend(),
    )

    coordinator.set_startup_enabled(True)
    assert coordinator.startup_enabled
    assert coordinator.tab.startup_checkbox.isChecked()
    assert "Could not change startup setting" in status.currentMessage()

    coordinator.tab.deleteLater()
    popup.deleteLater()
    host.deleteLater()

from PySide6.QtCore import QObject
from PySide6.QtGui import QGuiApplication

from kaokey.platforms.linux.common_popup_backend import (
    LinuxPopupBackendBase,
)
from kaokey.platforms.linux.x11.hotkey import (
    X11GlobalHotkey,
    X11HotkeyError,
    x11_hotkeys_available,
)
from kaokey.platforms.popup_backend import (
    PopupCapabilities,
    PopupHotkey,
    PopupHotkeyActivation,
    PopupHotkeyActivationCallback,
    PopupHotkeyRegistrationCallback,
    PopupHotkeyRegistrationError,
    PopupHotkeyRegistrationErrorCallback,
)


class X11PopupBackend(LinuxPopupBackendBase):
    """X11 popup backend with native hotkeys and shared AT-SPI services."""

    def __init__(
        self,
        app: QGuiApplication,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(
            app,
            parent,
        )

        self._hotkey_available = x11_hotkeys_available()
        self._hotkey: X11GlobalHotkey | None = None

    @property
    def capabilities(
        self,
    ) -> PopupCapabilities:
        common = super().capabilities

        return PopupCapabilities(
            hotkey=self._hotkey_available,
            target_capture=common.target_capture,
            caret_positioning=common.caret_positioning,
            window_positioning=common.window_positioning,
            text_insertion=common.text_insertion,
        )

    @property
    def active_hotkey(
        self,
    ) -> PopupHotkey | None:
        hotkey = self._hotkey

        if hotkey is None:
            return None

        return PopupHotkey(
            modifier=hotkey.modifier,
            key=hotkey.key,
            label=hotkey.label,
        )

    def set_hotkey(
        self,
        modifier: str,
        key: str,
        callback: PopupHotkeyActivationCallback,
        on_registered: PopupHotkeyRegistrationCallback,
        on_error: PopupHotkeyRegistrationErrorCallback,
    ) -> None:
        previous_hotkey = self._hotkey

        if previous_hotkey is not None and (
            previous_hotkey.modifier,
            previous_hotkey.key,
        ) == (
            modifier,
            key,
        ):
            on_registered(
                PopupHotkey(
                    modifier=previous_hotkey.modifier,
                    key=previous_hotkey.key,
                    label=previous_hotkey.label,
                )
            )
            return

        try:
            candidate = X11GlobalHotkey(
                modifier,
                key,
                lambda timestamp: callback(
                    PopupHotkeyActivation(
                        x11_timestamp=timestamp,
                    )
                ),
                self,
            )
        except X11HotkeyError as error:
            on_error(
                PopupHotkeyRegistrationError(
                    str(error),
                    previous_hotkey_restored=previous_hotkey is not None,
                )
            )
            return

        if previous_hotkey is not None:
            previous_hotkey.unregister()

        try:
            candidate.register()
        except X11HotkeyError as error:
            candidate.close()

            restored = False

            if previous_hotkey is not None:
                try:
                    previous_hotkey.register()
                    restored = True
                except X11HotkeyError:
                    previous_hotkey.close()
                    self._hotkey = None

            on_error(
                PopupHotkeyRegistrationError(
                    str(error),
                    previous_hotkey_restored=restored,
                )
            )
            return

        self._hotkey = candidate

        if previous_hotkey is not None:
            previous_hotkey.close()

        on_registered(
            PopupHotkey(
                modifier=candidate.modifier,
                key=candidate.key,
                label=candidate.label,
            )
        )

    def clear_hotkey(
        self,
    ) -> None:
        hotkey = self._hotkey

        if hotkey is None:
            return

        hotkey.close()
        hotkey.deleteLater()
        self._hotkey = None

    def hotkey_keys_released(
        self,
    ) -> bool:
        hotkey = self._hotkey

        if hotkey is None:
            return True

        return hotkey.keys_released()

    def request_popup_activation(
        self,
        window_id: int,
        activation: PopupHotkeyActivation,
    ) -> bool:
        hotkey = self._hotkey
        timestamp = activation.x11_timestamp

        if (
            hotkey is None
            or timestamp is None
            or timestamp <= 0
        ):
            return False

        try:
            hotkey.request_window_activation(
                window_id,
                timestamp,
            )
        except OSError:
            return False

        return True

from PySide6.QtCore import QObject
from PySide6.QtGui import QGuiApplication

from kaokey.platforms.linux.common_popup_backend import (
    LinuxPopupBackendBase,
)
from kaokey.platforms.linux.wayland.global_shortcuts import (
    WaylandGlobalShortcut,
    WaylandPortalError,
    wayland_global_shortcuts_available,
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


class WaylandPopupBackend(LinuxPopupBackendBase):
    """Wayland backend using GlobalShortcuts portal and shared AT-SPI."""

    def __init__(
        self,
        app: QGuiApplication,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(
            app,
            parent,
        )

        self._hotkey_available = wayland_global_shortcuts_available()
        self._hotkey: WaylandGlobalShortcut | None = None
        self._pending_hotkey: WaylandGlobalShortcut | None = None
        self._registration_serial = 0

    @property
    def capabilities(
        self,
    ) -> PopupCapabilities:
        common = super().capabilities

        return PopupCapabilities(
            hotkey=self._hotkey_available,
            target_capture=common.target_capture,
            caret_positioning=common.caret_positioning,
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
        current = self._hotkey

        if current is not None and (
            current.modifier,
            current.key,
        ) == (
            modifier,
            key,
        ):
            on_registered(
                PopupHotkey(
                    modifier=current.modifier,
                    key=current.key,
                    label=current.label,
                )
            )
            return

        self._registration_serial += 1
        serial = self._registration_serial

        pending = self._pending_hotkey

        if pending is not None:
            pending.close()
            pending.deleteLater()

        try:
            candidate = WaylandGlobalShortcut(
                modifier,
                key,
                lambda activation_token: callback(
                    PopupHotkeyActivation(
                        activation_token=activation_token,
                    )
                ),
                self,
            )
        except WaylandPortalError as error:
            on_error(
                PopupHotkeyRegistrationError(
                    str(error),
                    previous_hotkey_restored=current is not None,
                )
            )
            return

        self._pending_hotkey = candidate

        def registered(
            hotkey: PopupHotkey,
        ) -> None:
            if (
                serial != self._registration_serial
                or self._pending_hotkey is not candidate
            ):
                candidate.close()
                candidate.deleteLater()
                return

            previous = self._hotkey
            self._pending_hotkey = None
            self._hotkey = candidate

            if previous is not None:
                previous.close()
                previous.deleteLater()

            on_registered(hotkey)

        def failed(
            message: str,
        ) -> None:
            if (
                serial != self._registration_serial
                or self._pending_hotkey is not candidate
            ):
                candidate.close()
                candidate.deleteLater()
                return

            self._pending_hotkey = None
            candidate.close()
            candidate.deleteLater()

            on_error(
                PopupHotkeyRegistrationError(
                    message,
                    previous_hotkey_restored=self._hotkey is not None,
                )
            )

        candidate.register(
            registered,
            failed,
        )

    def clear_hotkey(
        self,
    ) -> None:
        self._registration_serial += 1

        pending = self._pending_hotkey
        self._pending_hotkey = None

        if pending is not None:
            pending.close()
            pending.deleteLater()

        hotkey = self._hotkey
        self._hotkey = None

        if hotkey is not None:
            hotkey.close()
            hotkey.deleteLater()

    def hotkey_keys_released(
        self,
    ) -> bool:
        # The portal exposes shortcut activation, not raw global key state.
        return True

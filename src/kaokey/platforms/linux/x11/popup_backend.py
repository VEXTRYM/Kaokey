from PySide6.QtCore import QObject
from PySide6.QtGui import QGuiApplication

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
    UnavailablePopupBackend,
)


class X11PopupBackend(UnavailablePopupBackend):
    """Stage 1: X11 hotkeys without AT-SPI capture or native insertion.

    The base class immediately returns an empty popup context, so a broken or
    slow AT-SPI provider cannot delay opening the window. The existing Qt
    popup can still use its saved position or center of the screen.
    """

    def __init__(
        self,
        app: QGuiApplication,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        del app

        self._hotkey_available = x11_hotkeys_available()
        self._hotkey: X11GlobalHotkey | None = None

    @property
    def capabilities(
        self,
    ) -> PopupCapabilities:
        return PopupCapabilities(
            hotkey=self._hotkey_available,
            # Regular saved/centered placement, never caret placement.
            window_positioning=True,
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
            candidate.deleteLater()

            restored = False

            if previous_hotkey is not None:
                try:
                    previous_hotkey.register()
                    restored = True
                except X11HotkeyError:
                    previous_hotkey.close()
                    previous_hotkey.deleteLater()
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
            previous_hotkey.deleteLater()

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

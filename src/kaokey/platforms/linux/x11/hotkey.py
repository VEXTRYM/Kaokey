from collections.abc import Callable

from PySide6.QtCore import (
    QObject,
    QSocketNotifier,
)

from kaokey.platforms.linux.x11.xlib import (
    CONTROL_MASK,
    KEY_PRESS,
    KEY_RELEASE,
    MOD1_MASK,
    SHIFT_MASK,
    X11Connection,
)

MODIFIER_MASK_FALLBACKS = {
    "Alt": MOD1_MASK,
    "Ctrl": CONTROL_MASK,
    "Shift": SHIFT_MASK,
}

MODIFIER_KEYSYMS = {
    "Alt": (
        "Alt_L",
        "Alt_R",
    ),
    "Ctrl": (
        "Control_L",
        "Control_R",
    ),
    "Shift": (
        "Shift_L",
        "Shift_R",
    ),
}


class X11HotkeyError(RuntimeError):
    """Raised when an X11 global hotkey cannot be used."""


class X11GlobalHotkey(QObject):
    """Global X11 shortcut implemented with a passive XGrabKey grab."""

    def __init__(
        self,
        modifier: str,
        key: str,
        callback: Callable[[int], None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self.modifier = modifier
        self.key = key
        self.label = f"{modifier}+{key}"
        self.callback = callback

        try:
            self.connection = X11Connection()
        except OSError as error:
            raise X11HotkeyError(str(error)) from error

        try:
            self.keycode = self._keycode(key)
            self.modifier_mask = self._modifier_mask(modifier)
            self.modifier_keycodes = self._modifier_keycodes(modifier)
            self.lock_variants = self.connection.lock_modifier_variants()
        except Exception:
            self.connection.close()
            raise

        self._registered = False
        self._pressed = False
        self._last_release_timestamp: int | None = None

        self.notifier = QSocketNotifier(
            self.connection.file_descriptor,
            QSocketNotifier.Type.Read,
            self,
        )
        self.notifier.setEnabled(False)
        self.notifier.activated.connect(
            self._drain_events
        )

    def register(
        self,
    ) -> None:
        if self._registered:
            return

        try:
            self.connection.grab_key(
                self.keycode,
                self.modifier_mask,
                self.lock_variants,
            )
        except OSError as error:
            raise X11HotkeyError(str(error)) from error

        self._registered = True
        self._pressed = False
        self._last_release_timestamp = None
        self.notifier.setEnabled(True)

    def unregister(
        self,
    ) -> None:
        if not self._registered:
            return

        self.notifier.setEnabled(False)
        self.connection.ungrab_key(
            self.keycode,
            self.modifier_mask,
            self.lock_variants,
        )
        self._registered = False
        self._pressed = False
        self._last_release_timestamp = None

    def close(
        self,
    ) -> None:
        self.unregister()
        self.notifier.setEnabled(False)
        self.connection.close()

    def keys_released(
        self,
    ) -> bool:
        if self.connection.key_is_pressed(
            self.keycode
        ):
            return False

        return not any(
            self.connection.key_is_pressed(keycode)
            for keycode in self.modifier_keycodes
        )

    def request_window_activation(
        self,
        window_id: int,
        timestamp: int,
    ) -> None:
        self.connection.request_window_activation(
            window_id,
            timestamp,
        )

    def _drain_events(
        self,
        *_args: object,
    ) -> None:
        while self.connection.pending_events() > 0:
            event = self.connection.next_event()

            if event.type not in (KEY_PRESS, KEY_RELEASE):
                continue

            if int(event.xkey.keycode) != self.keycode:
                continue

            timestamp = int(event.xkey.time)

            if event.type == KEY_RELEASE:
                self._pressed = False
                self._last_release_timestamp = timestamp
                continue

            # When detectable XKB auto-repeat is unavailable, X11 emits a
            # synthetic KeyRelease/KeyPress pair with the same timestamp.
            # Treat that pair as a held key, not a new popup invocation.
            if timestamp == self._last_release_timestamp:
                self._pressed = True
                continue

            if self._pressed:
                continue

            self._pressed = True
            self.callback(timestamp)

    def _keycode(
        self,
        key: str,
    ) -> int:
        normalized = key.upper()

        valid = (
            len(normalized) == 1
            and (
                "A" <= normalized <= "Z"
                or "0" <= normalized <= "9"
            )
        ) or (
            normalized.startswith("F")
            and normalized[1:].isdigit()
            and 1 <= int(normalized[1:]) <= 12
        )

        if not valid:
            raise X11HotkeyError(
                f"Unsupported X11 hotkey key: {key}."
            )

        keycode = self.connection.keysym_keycode(
            normalized
        )

        if keycode <= 0:
            raise X11HotkeyError(
                f"X11 could not resolve hotkey key: {key}."
            )

        return keycode

    def _modifier_mask(
        self,
        modifier: str,
    ) -> int:
        keysyms = MODIFIER_KEYSYMS.get(modifier)

        if keysyms is None:
            raise X11HotkeyError(
                f"Unsupported X11 hotkey modifier: {modifier}."
            )

        mask = self.connection.modifier_mask_for_keysyms(
            keysyms
        )

        if mask:
            return mask

        return MODIFIER_MASK_FALLBACKS[modifier]

    def _modifier_keycodes(
        self,
        modifier: str,
    ) -> tuple[int, ...]:
        keysyms = MODIFIER_KEYSYMS.get(modifier)

        if keysyms is None:
            return ()

        return tuple(
            keycode
            for keycode in (
                self.connection.keysym_keycode(name)
                for name in keysyms
            )
            if keycode > 0
        )


def x11_hotkeys_available() -> bool:
    """Return whether libX11 and the active X display can be opened."""
    try:
        connection = X11Connection()
    except OSError:
        return False

    connection.close()
    return True

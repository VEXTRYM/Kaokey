from typing import Protocol

from constants import (
    DEFAULT_ADD_SPACE_AFTER_INSERT,
    DEFAULT_HOTKEY_KEY,
    DEFAULT_HOTKEY_MODIFIER,
    DEFAULT_SHOW_HINTS,
    HOTKEY_KEYS,
    HOTKEY_MODIFIERS,
    SETTINGS_HOTKEY_KEY,
    SETTINGS_HOTKEY_MODIFIER_KEY,
    SETTINGS_LANGUAGE_KEY,
    SETTINGS_POPUP_HEIGHT_KEY,
    SETTINGS_POPUP_WIDTH_KEY,
    SETTINGS_POPUP_X_KEY,
    SETTINGS_POPUP_Y_KEY,
    SETTINGS_SHOW_HINTS_KEY,
    SETTINGS_ADD_SPACE_AFTER_INSERT_KEY,
    SETTINGS_WINDOW_HEIGHT_KEY,
    SETTINGS_WINDOW_WIDTH_KEY,
    SYSTEM_LANGUAGE,
)

from style_constants import (
    POPUP_HEIGHT,
    POPUP_MAX_HEIGHT,
    POPUP_MAX_WIDTH,
    POPUP_MIN_HEIGHT,
    POPUP_MIN_WIDTH,
    POPUP_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_MAX_HEIGHT,
    WINDOW_MAX_WIDTH,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
    WINDOW_WIDTH,
)


class SettingsStore(Protocol):
    def value(
        self,
        key: str,
        defaultValue: object = None,
        type: object = None,
    ) -> object:
        ...

    def setValue(
        self,
        key: str,
        value: object,
    ) -> None:
        ...

    def remove(
        self,
        key: str,
    ) -> None:
        ...

    def sync(self) -> None:
        ...


class SettingsManager:
    def __init__(
        self,
        store: SettingsStore,
    ) -> None:
        self._store = store

    @classmethod
    def create_default(
        cls,
    ) -> "SettingsManager":
        # Importing here keeps this module easy to
        # unit-test without starting a Qt application.
        from PySide6.QtCore import QSettings

        return cls(
            QSettings()
        )

    # =============================
    # Language
    # =============================

    @property
    def language(self) -> str:
        value = self._store.value(
            SETTINGS_LANGUAGE_KEY,
            SYSTEM_LANGUAGE,
        )

        if not isinstance(
            value,
            str,
        ):
            return SYSTEM_LANGUAGE

        language = value.strip()

        if not language:
            return SYSTEM_LANGUAGE

        return language

    @language.setter
    def language(
        self,
        value: str,
    ) -> None:
        language = value.strip()

        if not language:
            language = SYSTEM_LANGUAGE

        self._store.setValue(
            SETTINGS_LANGUAGE_KEY,
            language,
        )

        self._store.sync()

    # =============================
    # Status hints
    # =============================

    @property
    def show_hints(self) -> bool:
        value = self._store.value(
            SETTINGS_SHOW_HINTS_KEY,
            DEFAULT_SHOW_HINTS,
        )

        if isinstance(
            value,
            bool,
        ):
            return value

        if isinstance(
            value,
            int,
        ):
            return value != 0

        if isinstance(
            value,
            str,
        ):
            normalized = (
                value.strip().casefold()
            )

            if normalized in {
                "false",
                "0",
                "no",
                "off",
            }:
                return False

            if normalized in {
                "true",
                "1",
                "yes",
                "on",
            }:
                return True

        return DEFAULT_SHOW_HINTS

    @show_hints.setter
    def show_hints(
        self,
        value: bool,
    ) -> None:
        self._store.setValue(
            SETTINGS_SHOW_HINTS_KEY,
            value,
        )

        self._store.sync()

    # =============================
    # Input behavior
    # =============================

    @property
    def add_space_after_insert(
        self,
    ) -> bool:
        value = self._store.value(
            SETTINGS_ADD_SPACE_AFTER_INSERT_KEY,
            DEFAULT_ADD_SPACE_AFTER_INSERT,
        )

        if isinstance(
            value,
            bool,
        ):
            return value

        if isinstance(
            value,
            int,
        ):
            return value != 0

        if isinstance(
            value,
            str,
        ):
            normalized = (
                value.strip().casefold()
            )

            if normalized in {
                "false",
                "0",
                "no",
                "off",
            }:
                return False

            if normalized in {
                "true",
                "1",
                "yes",
                "on",
            }:
                return True

        return DEFAULT_ADD_SPACE_AFTER_INSERT

    @add_space_after_insert.setter
    def add_space_after_insert(
        self,
        value: bool,
    ) -> None:
        self._store.setValue(
            SETTINGS_ADD_SPACE_AFTER_INSERT_KEY,
            value,
        )

        self._store.sync()

    # =============================
    # Popup hotkey
    # =============================

    @property
    def hotkey(
        self,
    ) -> tuple[str, str]:
        modifier = self._read_choice(
            SETTINGS_HOTKEY_MODIFIER_KEY,
            HOTKEY_MODIFIERS,
            DEFAULT_HOTKEY_MODIFIER,
        )

        key = self._read_choice(
            SETTINGS_HOTKEY_KEY,
            HOTKEY_KEYS,
            DEFAULT_HOTKEY_KEY,
        )

        return (
            modifier,
            key,
        )

    def set_hotkey(
        self,
        modifier: str,
        key: str,
    ) -> None:
        if modifier not in HOTKEY_MODIFIERS:
            raise ValueError(
                "Invalid hotkey modifier."
            )

        if key not in HOTKEY_KEYS:
            raise ValueError(
                "Invalid hotkey key."
            )

        self._store.setValue(
            SETTINGS_HOTKEY_MODIFIER_KEY,
            modifier,
        )

        self._store.setValue(
            SETTINGS_HOTKEY_KEY,
            key,
        )

        self._store.sync()

    # =============================
    # Main window size
    # =============================

    @property
    def window_size(
        self,
    ) -> tuple[int, int]:
        width = self._read_int(
            SETTINGS_WINDOW_WIDTH_KEY
        )

        height = self._read_int(
            SETTINGS_WINDOW_HEIGHT_KEY
        )

        if width is None:
            width = WINDOW_WIDTH

        if height is None:
            height = WINDOW_HEIGHT

        width = max(
            WINDOW_MIN_WIDTH,
            min(
                width,
                WINDOW_MAX_WIDTH,
            ),
        )

        height = max(
            WINDOW_MIN_HEIGHT,
            min(
                height,
                WINDOW_MAX_HEIGHT,
            ),
        )

        return (
            width,
            height,
        )

    def set_window_size(
        self,
        width: int,
        height: int,
    ) -> None:
        width = max(
            WINDOW_MIN_WIDTH,
            min(
                width,
                WINDOW_MAX_WIDTH,
            ),
        )

        height = max(
            WINDOW_MIN_HEIGHT,
            min(
                height,
                WINDOW_MAX_HEIGHT,
            ),
        )

        self._store.setValue(
            SETTINGS_WINDOW_WIDTH_KEY,
            width,
        )

        self._store.setValue(
            SETTINGS_WINDOW_HEIGHT_KEY,
            height,
        )

        self._store.sync()

    # =============================
    # Popup size
    # =============================

    @property
    def popup_size(
        self,
    ) -> tuple[int, int]:
        width = self._read_int(
            SETTINGS_POPUP_WIDTH_KEY
        )

        height = self._read_int(
            SETTINGS_POPUP_HEIGHT_KEY
        )

        if width is None:
            width = POPUP_WIDTH

        if height is None:
            height = POPUP_HEIGHT

        width = max(
            POPUP_MIN_WIDTH,
            min(
                width,
                POPUP_MAX_WIDTH,
            ),
        )

        height = max(
            POPUP_MIN_HEIGHT,
            min(
                height,
                POPUP_MAX_HEIGHT,
            ),
        )

        return (
            width,
            height,
        )

    def set_popup_size(
        self,
        width: int,
        height: int,
    ) -> None:
        width = max(
            POPUP_MIN_WIDTH,
            min(
                width,
                POPUP_MAX_WIDTH,
            ),
        )

        height = max(
            POPUP_MIN_HEIGHT,
            min(
                height,
                POPUP_MAX_HEIGHT,
            ),
        )

        self._store.setValue(
            SETTINGS_POPUP_WIDTH_KEY,
            width,
        )

        self._store.setValue(
            SETTINGS_POPUP_HEIGHT_KEY,
            height,
        )

        self._store.sync()

    # =============================
    # Popup position
    # =============================

    @property
    def popup_position(
        self,
    ) -> tuple[int, int] | None:
        x = self._read_int(
            SETTINGS_POPUP_X_KEY
        )

        y = self._read_int(
            SETTINGS_POPUP_Y_KEY
        )

        if x is None or y is None:
            return None

        return (
            x,
            y,
        )

    def set_popup_position(
        self,
        x: int,
        y: int,
    ) -> None:
        self._store.setValue(
            SETTINGS_POPUP_X_KEY,
            x,
        )

        self._store.setValue(
            SETTINGS_POPUP_Y_KEY,
            y,
        )

        self._store.sync()

    def _read_choice(
        self,
        key: str,
        choices: tuple[str, ...],
        default: str,
    ) -> str:
        value = self._store.value(
            key,
            default,
        )

        if not isinstance(
            value,
            str,
        ):
            return default

        normalized = (
            value.strip().casefold()
        )

        for choice in choices:
            if (
                choice.casefold()
                == normalized
            ):
                return choice

        return default

    def _read_int(
        self,
        key: str,
    ) -> int | None:
        value = self._store.value(
            key,
            None,
        )

        if isinstance(
            value,
            bool,
        ):
            return None

        if isinstance(
            value,
            int,
        ):
            return value

        if isinstance(
            value,
            str,
        ):
            try:
                return int(
                    value.strip()
                )
            except ValueError:
                return None

        return None


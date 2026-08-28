from pathlib import Path
from typing import Any

from constants import (
    SOURCE_LANGUAGE,
    SYSTEM_LANGUAGE,
    TRANSLATION_FILE_PREFIX,
    TRANSLATIONS_DIR,
)


def language_code(
    locale_name: str,
) -> str:
    normalized = (
        locale_name.strip()
        .replace("-", "_")
    )

    if not normalized:
        return SOURCE_LANGUAGE

    return (
        normalized.split(
            "_",
            maxsplit=1,
        )[0].casefold()
    )


def resolve_language_preference(
    preference: str,
    system_locale: str,
) -> str:
    normalized_preference = (
        preference.strip().casefold()
    )

    if (
        not normalized_preference
        or normalized_preference
        == SYSTEM_LANGUAGE
    ):
        return language_code(
            system_locale
        )

    return language_code(
        normalized_preference
    )


def discover_translation_languages(
    translations_dir: Path = TRANSLATIONS_DIR,
) -> list[str]:
    languages = {
        SOURCE_LANGUAGE
    }

    if translations_dir.exists():
        pattern = (
            f"{TRANSLATION_FILE_PREFIX}*.qm"
        )

        for path in translations_dir.glob(
            pattern
        ):
            stem = path.stem
            code = stem.removeprefix(
                TRANSLATION_FILE_PREFIX
            )

            if code:
                languages.add(
                    language_code(
                        code
                    )
                )

    return sorted(
        languages
    )


class TranslationManager:
    def __init__(
        self,
        app: Any,
        translations_dir: Path = TRANSLATIONS_DIR,
    ) -> None:
        # Delayed Qt import keeps the pure helper
        # functions above testable without PySide6.
        from PySide6.QtCore import QTranslator

        self._app = app
        self._translations_dir = (
            translations_dir
        )
        self._translator = QTranslator(
            app
        )
        self._translator_installed = False

        self.preference = SYSTEM_LANGUAGE
        self.active_language = SOURCE_LANGUAGE

    @property
    def available_languages(
        self,
    ) -> list[str]:
        return discover_translation_languages(
            self._translations_dir
        )

    def apply_language(
        self,
        preference: str,
    ) -> str:
        from PySide6.QtCore import QLocale

        self.preference = (
            preference.strip()
            or SYSTEM_LANGUAGE
        )

        resolved_language = (
            resolve_language_preference(
                self.preference,
                QLocale.system().name(),
            )
        )

        if self._translator_installed:
            self._app.removeTranslator(
                self._translator
            )
            self._translator_installed = False

        # English source strings need no .qm file.
        if (
            resolved_language
            == SOURCE_LANGUAGE
        ):
            self.active_language = (
                SOURCE_LANGUAGE
            )
            return self.active_language

        translation_path = (
            self._translations_dir
            / (
                f"{TRANSLATION_FILE_PREFIX}"
                f"{resolved_language}.qm"
            )
        )

        if self._translator.load(
            str(translation_path)
        ):
            self._app.installTranslator(
                self._translator
            )
            self._translator_installed = True
            self.active_language = (
                resolved_language
            )
        else:
            # Missing translation is not fatal.
            # The application simply falls back
            # to its English source strings.
            self.active_language = (
                SOURCE_LANGUAGE
            )

        return self.active_language

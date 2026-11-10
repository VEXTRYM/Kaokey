"""Bundled Noto fonts first, with the host's fonts as a last resort."""

import logging
from functools import cache

from PySide6.QtGui import QFont, QFontDatabase, QFontMetrics
from PySide6.QtWidgets import QApplication

from kaokey.config.app_paths import resource_root

_LOG = logging.getLogger(__name__)

# Register all bundled faces, but put only relevant faces in each widget's
# fallback list. A 160-family QFont makes Qt probe every face for each script.
PRIMARY_FONT_FILES = (
    "NotoSans-Regular.ttf",
    "NotoSansSymbols2-Regular.ttf",
    "NotoSansSymbols-Regular.ttf",
    "NotoSansMath-Regular.ttf",
    "NotoMusic-Regular.ttf",
    "NotoColorEmoji_WindowsCompatible.ttf",
    "NotoEmoji[wght].ttf",
    "NotoSansCJK-Regular.ttc",
)

SYSTEM_FALLBACK_FAMILIES = (
    "Segoe UI Symbol",
    "Segoe UI Emoji",
    "DejaVu Sans",
    "Arial Unicode MS",
)

SCRIPT_FONT_RANGES = (
    (0x13A0, 0x13FF, "NotoSansCherokee-Regular.ttf"),
    (0x1400, 0x167F, "NotoSansCanadianAboriginal-Regular.ttf"),
    (0xAB70, 0xABBF, "NotoSansCherokee-Regular.ttf"),
    (0x0600, 0x06FF, "NotoSansArabic-Regular.ttf"),
    (0x0900, 0x097F, "NotoSansDevanagari-Regular.ttf"),
    (0x0980, 0x09FF, "NotoSansBengali-Regular.ttf"),
    (0x0A00, 0x0A7F, "NotoSansGurmukhi-Regular.ttf"),
    (0x0A80, 0x0AFF, "NotoSansGujarati-Regular.ttf"),
    (0x0B00, 0x0B7F, "NotoSansOriya-Regular.ttf"),
    (0x0B80, 0x0BFF, "NotoSansTamil-Regular.ttf"),
    (0x0C00, 0x0C7F, "NotoSansTelugu-Regular.ttf"),
    (0x0C80, 0x0CFF, "NotoSansKannada-Regular.ttf"),
    (0x0D00, 0x0D7F, "NotoSansMalayalam-Regular.ttf"),
    (0x0D80, 0x0DFF, "NotoSansSinhala-Regular.ttf"),
    (0x0E00, 0x0E7F, "NotoSansThai-Regular.ttf"),
    (0x0E80, 0x0EFF, "NotoSansLao-Regular.ttf"),
    (0x0F00, 0x0FFF, "NotoSerifTibetan-Regular.ttf"),
    (0x1000, 0x109F, "NotoSansMyanmar-Regular.ttf"),
    (0x1100, 0x11FF, "NotoSansCJK-Regular.ttc"),
    (0x1780, 0x17FF, "NotoSansKhmer-Regular.ttf"),
    (0x3040, 0x30FF, "NotoSansCJK-Regular.ttc"),
    (0x3130, 0x318F, "NotoSansCJK-Regular.ttc"),
    (0x3400, 0x9FFF, "NotoSansCJK-Regular.ttc"),
    (0xA000, 0xA4CF, "NotoSansYi-Regular.ttf"),
    (0xAC00, 0xD7AF, "NotoSansCJK-Regular.ttc"),
    (0x11700, 0x1174F, "NotoSerifAhom-Regular.ttf"),
    (0x1D100, 0x1D1FF, "NotoMusic-Regular.ttf"),
    (0x1E100, 0x1E14F, "NotoSerifNyiakengPuachueHmong-Regular.ttf"),
)


def bundled_font_families() -> tuple[tuple[str, ...], dict[str, tuple[str, ...]]]:
    """Register shipped fonts once and retain each file's actual Qt families."""
    if QApplication.instance() is None:
        return (), {}
    return _load_bundled_fonts()


@cache
def _load_bundled_fonts() -> tuple[tuple[str, ...], dict[str, tuple[str, ...]]]:
    font_dir = resource_root() / "fonts"
    files = {path.name: path for path in font_dir.glob("*.tt[fc]")}
    ordered = list(PRIMARY_FONT_FILES)
    ordered.extend(sorted(files.keys() - set(ordered)))
    families: list[str] = []
    by_file: dict[str, tuple[str, ...]] = {}

    for filename in ordered:
        path = files.get(filename)
        if path is None:
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            _LOG.warning("Could not load bundled font: %s", path)
            continue
        names = tuple(QFontDatabase.applicationFontFamilies(font_id))
        if not names:
            _LOG.warning("Bundled font has no Qt family: %s", path)
            continue
        by_file[filename] = names
        for name in names:
            if name not in families:
                families.append(name)

    return tuple(families), by_file


def font_with_unicode_fallbacks(
    base_font: QFont,
    preferred_file: str | None = None,
    extra_families: tuple[str, ...] = (),
) -> QFont:
    """Use shipped faces first and preserve automatic system glyph fallback."""
    font = QFont(base_font)
    _, by_file = bundled_font_families()
    families = list(by_file.get(preferred_file, ())[:1])
    families.extend(extra_families)
    for filename in PRIMARY_FONT_FILES:
        families.extend(by_file.get(filename, ())[:1])
    families.extend(base_font.families() or [base_font.family()])
    families.extend(SYSTEM_FALLBACK_FAMILIES)
    font.setFamilies(_unique_families(families))
    font.setStyleStrategy(font.styleStrategy() & ~QFont.StyleStrategy.NoFontMerging)
    return font


def font_for_text(base_font: QFont, text: str) -> QFont:
    """Pick a bundled face covering the text, or merge bundled glyphs."""
    if not text:
        return font_with_unicode_fallbacks(base_font)

    _, by_file = bundled_font_families()
    preferred_file = _preferred_script_file(text)
    candidates = list(by_file.get(preferred_file, ())[:1])
    for filename in PRIMARY_FONT_FILES:
        candidates.extend(by_file.get(filename, ())[:1])

    candidates = _unique_families(candidates)
    for family in candidates:
        candidate = _single_family_font(base_font, family)
        if _font_contains_text(candidate, text):
            return candidate

    extra_families: list[str] = []
    for character in dict.fromkeys(text):
        if _ignorable_character(character):
            continue
        if any(_family_contains_character(family, ord(character)) for family in candidates):
            continue
        family = _bundled_family_for_character(ord(character))
        if family is not None:
            extra_families.append(family)

    return font_with_unicode_fallbacks(
        base_font, preferred_file, tuple(_unique_families(extra_families))
    )


def _bundled_family_for_character(codepoint: int) -> str | None:
    if QApplication.instance() is None:
        return None
    return _find_bundled_family_for_character(codepoint)


@cache
def _find_bundled_family_for_character(codepoint: int) -> str | None:
    families, _ = bundled_font_families()
    for family in families:
        if _family_contains_character(family, codepoint):
            return family
    return None


@cache
def _family_contains_character(family: str, codepoint: int) -> bool:
    font = _single_family_font(QFont(), family)
    return QFontMetrics(font).inFontUcs4(codepoint)


def _preferred_script_file(text: str) -> str | None:
    matches = {
        filename
        for character in text
        for start, end, filename in SCRIPT_FONT_RANGES
        if start <= ord(character) <= end
    }
    return next(iter(matches)) if len(matches) == 1 else None


def _unique_families(families: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for family in families:
        key = family.strip().casefold()
        if key and key not in seen:
            seen.add(key)
            result.append(family)
    return result


def _single_family_font(base_font: QFont, family: str) -> QFont:
    font = QFont(base_font)
    font.setFamily(family)
    font.setStyleStrategy(font.styleStrategy() | QFont.StyleStrategy.NoFontMerging)
    return font


def _font_contains_text(font: QFont, text: str) -> bool:
    metrics = QFontMetrics(font)
    return all(
        _ignorable_character(character) or metrics.inFontUcs4(ord(character))
        for character in text
    )


def _ignorable_character(character: str) -> bool:
    return character.isspace() or character in {
        "\u200c", "\u200d", "\ufe0e", "\ufe0f"
    }

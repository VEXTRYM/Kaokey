from functools import lru_cache
from pathlib import Path
import os
import sys

from PySide6.QtGui import (
    QFont,
    QFontDatabase,
    QFontMetrics,
)


PREFERRED_UNICODE_FAMILIES = (
    "Gadugi",
    "Nirmala UI",
    "Segoe UI Symbol",
    "Segoe UI Emoji",
    "Microsoft Himalaya",
    "Leelawadee UI",
    "Yu Gothic UI",
    "Malgun Gothic",
    "Microsoft YaHei UI",
    "Microsoft JhengHei UI",
    "Microsoft Yi Baiti",
    "Sylfaen",
    "Cambria Math",
    "DejaVu Sans",
    "Noto Sans",
    "Noto Sans Symbols",
    "Noto Sans Symbols 2",
)


SCRIPT_FONT_RANGES = (
    (
        0x1400,
        0x167F,
        "Gadugi",
    ),
    (
        0x13A0,
        0x13FF,
        "Gadugi",
    ),
    (
        0xAB70,
        0xABBF,
        "Gadugi",
    ),
    (
        0x0A80,
        0x0AFF,
        "Nirmala UI",
    ),
    (
        0x0C80,
        0x0CFF,
        "Nirmala UI",
    ),
    (
        0x0D80,
        0x0DFF,
        "Nirmala UI",
    ),
    (
        0x0E00,
        0x0E7F,
        "Leelawadee UI",
    ),
    (
        0x0F00,
        0x0FFF,
        "Microsoft Himalaya",
    ),
    (
        0x1100,
        0x11FF,
        "Malgun Gothic",
    ),
    (
        0x3130,
        0x318F,
        "Malgun Gothic",
    ),
    (
        0xAC00,
        0xD7AF,
        "Malgun Gothic",
    ),
    (
        0x3040,
        0x30FF,
        "Yu Gothic UI",
    ),
    (
        0xA000,
        0xA4CF,
        "Microsoft Yi Baiti",
    ),
)


WINDOWS_APPLICATION_FONT_FILES = {
    "Gadugi": "gadugi.ttf",
}


@lru_cache(
    maxsize=None
)
def application_font_family(
    requested_family: str,
) -> str:
    """
    Register selected Windows system fonts as application fonts.

    For Canadian Syllabics, diagnostics proved that the physical
    C:\\Windows\\Fonts\\gadugi.ttf file is valid and contains every problematic
    U+1400..U+167F glyph. Loading that exact file into Qt avoids relying on the
    Windows font-matching/fallback path that was probing the unrelated broken
    legacy 8514oem entry.
    """
    if sys.platform != "win32":
        return requested_family

    filename = WINDOWS_APPLICATION_FONT_FILES.get(
        requested_family
    )

    if filename is None:
        return requested_family

    windows_dir = Path(
        os.environ.get(
            "WINDIR",
            r"C:\Windows",
        )
    )

    font_path = (
        windows_dir
        / "Fonts"
        / filename
    )

    if not font_path.exists():
        return requested_family

    font_id = QFontDatabase.addApplicationFont(
        str(
            font_path
        )
    )

    if font_id < 0:
        return requested_family

    families = (
        QFontDatabase.applicationFontFamilies(
            font_id
        )
    )

    if not families:
        return requested_family

    return families[0]


def font_with_unicode_fallbacks(
    base_font: QFont,
) -> QFont:
    font = QFont(
        base_font
    )

    families = list(
        font.families()
    )

    if not families:
        family = (
            font.family()
            .strip()
        )

        if family:
            families.append(
                family
            )

    known = {
        family.casefold()
        for family
        in families
    }

    for requested_family in (
        PREFERRED_UNICODE_FAMILIES
    ):
        family = application_font_family(
            requested_family
        )

        key = family.casefold()

        if key in known:
            continue

        families.append(
            family
        )

        known.add(
            key
        )

    if families:
        font.setFamilies(
            families
        )

    return font


def font_for_text(
    base_font: QFont,
    text: str,
) -> QFont:
    if not text:
        return QFont(
            base_font
        )

    preferred_family = (
        _preferred_script_family(
            text
        )
    )

    if preferred_family is not None:
        preferred_family = (
            application_font_family(
                preferred_family
            )
        )

        preferred_font = _single_family_font(
            base_font,
            preferred_family,
        )

        if _font_contains_text(
            preferred_font,
            text,
        ):
            return preferred_font

    base_family = (
        base_font.family()
        .strip()
    )

    if base_family:
        candidate = _single_family_font(
            base_font,
            base_family,
        )

        if _font_contains_text(
            candidate,
            text,
        ):
            return candidate

    candidates: list[str] = []

    if preferred_family is not None:
        candidates.append(
            preferred_family
        )

    candidates.extend(
        PREFERRED_UNICODE_FAMILIES
    )

    checked: set[str] = set()

    for requested_family in candidates:
        family = application_font_family(
            requested_family
        )

        key = family.casefold()

        if key in checked:
            continue

        checked.add(
            key
        )

        candidate = _single_family_font(
            base_font,
            family,
        )

        if _font_contains_text(
            candidate,
            text,
        ):
            return candidate

    return font_with_unicode_fallbacks(
        base_font
    )


def _preferred_script_family(
    text: str,
) -> str | None:
    families: set[str] = set()

    for character in text:
        codepoint = ord(
            character
        )

        for (
            start,
            end,
            family,
        ) in SCRIPT_FONT_RANGES:
            if (
                start
                <= codepoint
                <= end
            ):
                families.add(
                    family
                )
                break

    if len(families) != 1:
        return None

    return next(
        iter(
            families
        )
    )


def _single_family_font(
    base_font: QFont,
    family: str,
) -> QFont:
    font = QFont(
        base_font
    )

    font.setFamily(
        family
    )

    font.setStyleStrategy(
        (
            font.styleStrategy()
            | QFont.StyleStrategy.NoFontMerging
        )
    )

    return font


def _font_contains_text(
    font: QFont,
    text: str,
) -> bool:
    metrics = QFontMetrics(
        font
    )

    for character in text:
        if (
            character.isspace()
            or character
            in {
                "\u200c",
                "\u200d",
                "\ufe0e",
                "\ufe0f",
            }
        ):
            continue

        if not metrics.inFontUcs4(
            ord(
                character
            )
        ):
            return False

    return True

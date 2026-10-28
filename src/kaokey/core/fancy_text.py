"""Copyable Unicode text styles generated without an external service."""

import re
import string
from dataclasses import dataclass
from functools import cache
from unicodedata import lookup


@dataclass(frozen=True)
class FancyTextVariant:
    name: str
    text: str


_MATH_STYLES: tuple[tuple[str, str, bool], ...] = (
    ("Bold", "BOLD", True),
    ("Italic", "ITALIC", False),
    ("Bold italic", "BOLD ITALIC", False),
    ("Script", "SCRIPT", False),
    ("Bold script", "BOLD SCRIPT", False),
    ("Fraktur", "FRAKTUR", False),
    ("Bold fraktur", "BOLD FRAKTUR", False),
    ("Double-struck", "DOUBLE-STRUCK", True),
    ("Sans serif", "SANS-SERIF", True),
    ("Sans bold", "SANS-SERIF BOLD", True),
    ("Sans italic", "SANS-SERIF ITALIC", False),
    ("Sans bold italic", "SANS-SERIF BOLD ITALIC", False),
    ("Monospace", "MONOSPACE", True),
)

# A few mathematical alphabets reuse earlier Letterlike Symbols code points.
_MATH_EXCEPTIONS: dict[str, dict[str, str]] = {
    "ITALIC": {"h": "ℎ"},
    "SCRIPT": {
        "B": "ℬ", "E": "ℰ", "F": "ℱ", "H": "ℋ", "I": "ℐ", "L": "ℒ",
        "M": "ℳ", "R": "ℛ", "e": "ℯ", "g": "ℊ", "o": "ℴ",
    },
    "FRAKTUR": {"C": "ℭ", "H": "ℌ", "I": "ℑ", "R": "ℜ", "Z": "ℨ"},
    "DOUBLE-STRUCK": {
        "C": "ℂ", "H": "ℍ", "N": "ℕ", "P": "ℙ", "Q": "ℚ", "R": "ℝ", "Z": "ℤ",
    },
}

_DIGIT_NAMES = (
    "ZERO", "ONE", "TWO", "THREE", "FOUR",
    "FIVE", "SIX", "SEVEN", "EIGHT", "NINE",
)

_SMALL_CAPS = "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘꞯʀꜱᴛᴜᴠᴡxʏᴢ"
_ASCII_ALNUM = frozenset(string.ascii_letters + string.digits)


@cache
def _math_translation(style: str, include_digits: bool) -> dict[int, str]:
    replacements: dict[int, str] = {}
    exceptions = _MATH_EXCEPTIONS.get(style, {})

    for source_letters, case in (
        (string.ascii_uppercase, "CAPITAL"),
        (string.ascii_lowercase, "SMALL"),
    ):
        for letter in source_letters:
            replacements[ord(letter)] = exceptions.get(letter) or lookup(
                f"MATHEMATICAL {style} {case} {letter.upper()}"
            )

    if include_digits:
        for digit, name in enumerate(_DIGIT_NAMES):
            replacements[ord(str(digit))] = lookup(
                f"MATHEMATICAL {style} DIGIT {name}"
            )

    return replacements


@cache
def _circled_translation() -> dict[int, str]:
    replacements = {
        ord(letter): chr(0x24B6 + index)
        for index, letter in enumerate(string.ascii_uppercase)
    }
    replacements.update({
        ord(letter): chr(0x24D0 + index)
        for index, letter in enumerate(string.ascii_lowercase)
    })
    replacements[ord("0")] = "⓪"
    replacements.update({
        ord(str(digit)): chr(0x2460 + digit - 1)
        for digit in range(1, 10)
    })
    return replacements


@cache
def _fullwidth_translation() -> dict[int, str]:
    replacements = {
        codepoint: chr(codepoint + 0xFEE0)
        for codepoint in range(0x21, 0x7F)
    }
    replacements[ord(" ")] = "　"
    return replacements


@cache
def _small_caps_translation() -> dict[int, str]:
    replacements: dict[int, str] = {}
    for index, letter in enumerate(string.ascii_lowercase):
        replacements[ord(letter)] = _SMALL_CAPS[index]
        replacements[ord(letter.upper())] = _SMALL_CAPS[index]
    return replacements


def _mark_ascii(text: str, mark: str) -> str:
    return "".join(
        character + mark if character in _ASCII_ALNUM
        else character
        for character in text
    )


def _space_words(text: str) -> str:
    return re.sub(
        r"[A-Za-z0-9]+",
        lambda match: " ".join(match.group()),
        text,
    )


def generate_fancy_text(text: str) -> list[FancyTextVariant]:
    """Return distinct styled versions while preserving unsupported characters."""
    if not text.strip():
        return []

    candidates = [
        FancyTextVariant(name, text.translate(_math_translation(style, digits)))
        for name, style, digits in _MATH_STYLES
    ]
    candidates.extend((
        FancyTextVariant("Circled", text.translate(_circled_translation())),
        FancyTextVariant("Fullwidth", text.translate(_fullwidth_translation())),
        FancyTextVariant("Small caps", text.translate(_small_caps_translation())),
        FancyTextVariant("Underlined", _mark_ascii(text, "\u0332")),
        FancyTextVariant("Strikethrough", _mark_ascii(text, "\u0336")),
        FancyTextVariant("Spaced", _space_words(text)),
        FancyTextVariant("Sparkles", f"✨ {text} ✨"),
        FancyTextVariant("Hearts", f"♡ {text} ♡"),
        FancyTextVariant("Stars", f"⋆｡°✩ {text} ✩°｡⋆"),
        FancyTextVariant("Brackets", f"『{text}』"),
        FancyTextVariant("Ornate", f"꧁ {text} ꧂"),
    ))

    seen = {text}
    variants: list[FancyTextVariant] = []
    for candidate in candidates:
        if candidate.text not in seen:
            variants.append(candidate)
            seen.add(candidate.text)
    return variants

from unicode_fonts import (
    _preferred_script_family,
)


def test_canadian_syllabics_use_gadugi():
    for symbol in (
        "ᗝ",
        "ᗜ",
        "ᗣ",
        "ᗕ",
        "ᗒ",
        "ᗢ",
        "ᕙ",
        "ᕗ",
        "ᕦ",
        "ᕤ",
        "ᘏ",
        "ᓚ",
    ):
        assert _preferred_script_family(
            symbol
        ) == "Gadugi"


def test_sinhala_uses_nirmala_ui():
    assert _preferred_script_family(
        "ෆ"
    ) == "Nirmala UI"

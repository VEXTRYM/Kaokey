from unicode_fonts import (
    WINDOWS_APPLICATION_FONT_FILES,
    _preferred_script_family,
)


def test_gadugi_file_mapping():
    assert WINDOWS_APPLICATION_FONT_FILES[
        "Gadugi"
    ] == "gadugi.ttf"


def test_problem_symbols_map_to_gadugi():
    for symbol in (
        "ᗝ",
        "ᗜ",
        "ᗣ",
        "ᗕ",
        "ᗒ",
    ):
        assert _preferred_script_family(
            symbol
        ) == "Gadugi"

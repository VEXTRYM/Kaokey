from platforms.windows.insertion import (
    KEYEVENTF_KEYUP,
    KEYEVENTF_UNICODE,
    build_unicode_inputs,
    utf16_code_units,
)


def test_utf16_code_units_for_bmp_text():
    assert utf16_code_units(
        "A☆"
    ) == [
        0x0041,
        0x2606,
    ]


def test_utf16_code_units_for_non_bmp_character():
    assert utf16_code_units(
        "😀"
    ) == [
        0xD83D,
        0xDE00,
    ]


def test_build_unicode_inputs_creates_key_down_and_up():
    inputs = build_unicode_inputs(
        "A"
    )

    assert len(
        inputs
    ) == 2

    assert inputs[0].ki.wScan == 0x0041
    assert inputs[0].ki.dwFlags == KEYEVENTF_UNICODE

    assert inputs[1].ki.wScan == 0x0041
    assert inputs[1].ki.dwFlags == (
        KEYEVENTF_UNICODE
        | KEYEVENTF_KEYUP
    )


def test_non_bmp_character_uses_four_input_events():
    inputs = build_unicode_inputs(
        "😀"
    )

    assert len(
        inputs
    ) == 4

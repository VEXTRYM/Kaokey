from popup_positioning import Rect, position_near_caret


def test_above_position_can_use_larger_gap():
    available = Rect(
        x=0,
        y=0,
        width=500,
        height=500,
    )
    caret = Rect(
        x=100,
        y=450,
        width=1,
        height=20,
    )

    x, y = position_near_caret(
        caret,
        popup_width=200,
        popup_height=200,
        available=available,
        gap=4,
        above_gap=8,
    )

    assert x == 100
    assert y == 242


def test_below_position_still_uses_normal_gap():
    available = Rect(
        x=0,
        y=0,
        width=500,
        height=500,
    )
    caret = Rect(
        x=100,
        y=100,
        width=1,
        height=20,
    )

    x, y = position_near_caret(
        caret,
        popup_width=200,
        popup_height=200,
        available=available,
        gap=4,
        above_gap=8,
    )

    assert x == 100
    assert y == 124

from popup_positioning import (
    Rect,
    center_popup,
    clamp_popup_position,
    position_near_caret,
)


def test_popup_prefers_below_caret() -> None:
    screen = Rect(
        x=0,
        y=0,
        width=1000,
        height=800,
    )

    caret = Rect(
        x=300,
        y=200,
        width=2,
        height=20,
    )

    assert position_near_caret(
        caret,
        400,
        300,
        screen,
        4,
    ) == (
        300,
        224,
    )


def test_popup_moves_above_caret_when_bottom_is_too_small() -> None:
    screen = Rect(
        x=0,
        y=0,
        width=1000,
        height=800,
    )

    caret = Rect(
        x=300,
        y=700,
        width=2,
        height=20,
    )

    assert position_near_caret(
        caret,
        400,
        300,
        screen,
        4,
    ) == (
        300,
        396,
    )


def test_popup_is_clamped_at_right_edge() -> None:
    screen = Rect(
        x=0,
        y=0,
        width=1000,
        height=800,
    )

    caret = Rect(
        x=950,
        y=200,
        width=2,
        height=20,
    )

    assert position_near_caret(
        caret,
        400,
        300,
        screen,
        4,
    ) == (
        600,
        224,
    )


def test_saved_position_is_clamped_to_available_area() -> None:
    screen = Rect(
        x=100,
        y=50,
        width=900,
        height=700,
    )

    assert clamp_popup_position(
        900,
        700,
        400,
        300,
        screen,
    ) == (
        600,
        450,
    )


def test_popup_centers_in_available_area() -> None:
    screen = Rect(
        x=100,
        y=50,
        width=900,
        height=700,
    )

    assert center_popup(
        400,
        300,
        screen,
    ) == (
        350,
        250,
    )

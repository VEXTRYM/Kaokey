from popup_positioning import Rect
from platforms.windows.ui_automation import (
    correct_stale_caret_for_element_move,
)


def test_compensates_when_same_element_moves_and_caret_is_stale():
    previous = Rect(3428, 555, 1, 22)
    raw = Rect(3428, 555, 1, 22)

    corrected, applied = correct_stale_caret_for_element_move(
        raw,
        previous,
        (0, 306),
        True,
    )

    assert applied is True
    assert corrected == Rect(3428, 861, 1, 22)


def test_does_not_compensate_when_caret_already_updated():
    previous = Rect(3428, 555, 1, 22)
    raw = Rect(3428, 861, 1, 22)

    corrected, applied = correct_stale_caret_for_element_move(
        raw,
        previous,
        (0, 306),
        True,
    )

    assert applied is False
    assert corrected == raw


def test_does_not_compensate_for_different_element():
    raw = Rect(3428, 555, 1, 22)

    corrected, applied = correct_stale_caret_for_element_move(
        raw,
        Rect(3428, 555, 1, 22),
        (0, 306),
        False,
    )

    assert applied is False
    assert corrected == raw


def test_compensates_horizontal_element_move_too():
    previous = Rect(500, 300, 1, 20)
    raw = Rect(500, 300, 1, 20)

    corrected, applied = correct_stale_caret_for_element_move(
        raw,
        previous,
        (120, -40),
        True,
    )

    assert applied is True
    assert corrected == Rect(620, 260, 1, 20)

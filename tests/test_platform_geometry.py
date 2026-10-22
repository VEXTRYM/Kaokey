from dataclasses import dataclass

import pytest

from kaokey.platforms.windows.coordinates import convert_native_rect
from kaokey.platforms.windows.hotkey_config import (
    hotkey_modifier_flags,
    hotkey_release_virtual_keys,
    hotkey_virtual_key,
)
from kaokey.ui.popup.popup_positioning import (
    Rect,
    center_popup,
    clamp_popup_position,
    position_near_caret,
)


@dataclass
class FakeGeometry:
    left: int
    top: int
    wide: int
    tall: int

    def x(self) -> int:
        return self.left

    def y(self) -> int:
        return self.top

    def width(self) -> int:
        return self.wide

    def height(self) -> int:
        return self.tall


@dataclass
class FakeScreen:
    rect: FakeGeometry
    ratio: float

    def geometry(self) -> FakeGeometry:
        return self.rect

    def devicePixelRatio(self) -> float:
        return self.ratio


def test_native_caret_uses_correct_screen_and_scales_to_qt() -> None:
    left = FakeScreen(FakeGeometry(-1280, 0, 1280, 720), 1.0)
    right = FakeScreen(FakeGeometry(0, 0, 960, 540), 2.0)
    result = convert_native_rect(Rect(1500, 500, 20, 40), [left, right])
    assert result == (Rect(750, 250, 10, 20), right)
    assert convert_native_rect(Rect(3000, 500, 20, 40), [left, right]) is None


def test_popup_prefers_below_caret_then_above_and_clamps_to_screen() -> None:
    screen = Rect(-100, 20, 300, 200)
    assert position_near_caret(Rect(0, 40, 2, 18), 80, 60, screen, 5) == (0, 63)
    assert position_near_caret(Rect(0, 180, 2, 18), 80, 60, screen, 5) == (0, 115)
    assert clamp_popup_position(999, -999, 400, 300, screen) == (-100, 20)
    assert center_popup(100, 80, screen) == (0, 80)


def test_hotkey_configuration_rejects_unsupported_keys() -> None:
    assert hotkey_virtual_key("K") == ord("K")
    assert hotkey_virtual_key("F12") > hotkey_virtual_key("F1")
    assert hotkey_release_virtual_keys("Ctrl", "K")[1] == ord("K")
    assert hotkey_modifier_flags("Alt") > 0
    with pytest.raises(ValueError, match="key"):
        hotkey_virtual_key("F13")
    with pytest.raises(ValueError, match="modifier"):
        hotkey_modifier_flags("Super")

from dataclasses import dataclass

from platforms.windows.coordinates import (
    convert_native_rect,
    native_rect_to_qt,
    native_screen_rect,
    screen_for_native_rect,
)
from popup_positioning import Rect


@dataclass(frozen=True)
class FakeGeometry:
    left: int
    top: int
    w: int
    h: int

    def x(self) -> int:
        return self.left

    def y(self) -> int:
        return self.top

    def width(self) -> int:
        return self.w

    def height(self) -> int:
        return self.h


@dataclass(frozen=True)
class FakeScreen:
    rect: FakeGeometry
    ratio: float

    def geometry(self) -> FakeGeometry:
        return self.rect

    def devicePixelRatio(self) -> float:
        return self.ratio


def test_native_screen_rect_uses_device_pixel_ratio() -> None:
    screen = FakeScreen(
        FakeGeometry(
            1920,
            0,
            1707,
            960,
        ),
        1.5,
    )

    assert native_screen_rect(
        screen
    ) == Rect(
        x=1920,
        y=0,
        width=2560,
        height=1440,
    )


def test_native_rect_is_converted_relative_to_screen_origin() -> None:
    screen = FakeScreen(
        FakeGeometry(
            1920,
            0,
            1707,
            960,
        ),
        1.5,
    )

    caret = Rect(
        x=3420,
        y=900,
        width=2,
        height=30,
    )

    assert native_rect_to_qt(
        caret,
        screen,
    ) == Rect(
        x=2920,
        y=600,
        width=1,
        height=20,
    )


def test_screen_for_native_rect_handles_mixed_dpi_monitors() -> None:
    screen_1080 = FakeScreen(
        FakeGeometry(
            0,
            0,
            1920,
            1080,
        ),
        1.0,
    )

    screen_1440 = FakeScreen(
        FakeGeometry(
            1920,
            0,
            1707,
            960,
        ),
        1.5,
    )

    caret = Rect(
        x=3000,
        y=700,
        width=1,
        height=30,
    )

    assert screen_for_native_rect(
        caret,
        [
            screen_1080,
            screen_1440,
        ],
    ) is screen_1440


def test_convert_native_rect_returns_rect_and_screen() -> None:
    screen = FakeScreen(
        FakeGeometry(
            0,
            0,
            1280,
            720,
        ),
        2.0,
    )

    result = convert_native_rect(
        Rect(
            x=1000,
            y=500,
            width=2,
            height=40,
        ),
        [screen],
    )

    assert result == (
        Rect(
            x=500,
            y=250,
            width=1,
            height=20,
        ),
        screen,
    )

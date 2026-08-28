from collections.abc import Iterable
from typing import Protocol, TypeVar

from platforms.windows.constants import (
    CARET_DIAGNOSTICS_ENABLED,
)
from popup_positioning import Rect


class QRectLike(Protocol):
    def x(self) -> int: ...
    def y(self) -> int: ...
    def width(self) -> int: ...
    def height(self) -> int: ...


class ScreenLike(Protocol):
    def geometry(self) -> QRectLike: ...
    def devicePixelRatio(self) -> float: ...


ScreenT = TypeVar(
    "ScreenT",
    bound=ScreenLike,
)


def screen_for_native_rect(
    rect: Rect,
    screens: Iterable[ScreenT],
) -> ScreenT | None:
    """Find the Qt screen containing a rectangle expressed in native pixels.

    On Windows, Qt keeps each screen's virtual-desktop origin in native desktop
    coordinates, but scales the screen *size* into device-independent pixels.
    Reconstructing the native-sized screen rectangle lets us match Win32/UIA
    physical coordinates to the correct QScreen before converting them.
    """
    center_x = (
        rect.left
        + rect.width // 2
    )
    center_y = (
        rect.top
        + rect.height // 2
    )

    for screen in screens:
        native_screen = native_screen_rect(
            screen
        )

        if (
            native_screen.left
            <= center_x
            < native_screen.right
            and native_screen.top
            <= center_y
            < native_screen.bottom
        ):
            return screen

    return None


def native_rect_to_qt(
    rect: Rect,
    screen: ScreenLike,
) -> Rect:
    """Convert native/physical Windows pixels to Qt device-independent pixels."""
    geometry = screen.geometry()
    ratio = max(
        1.0,
        float(
            screen.devicePixelRatio()
        ),
    )

    x = geometry.x() + round(
        (
            rect.x
            - geometry.x()
        )
        / ratio
    )

    y = geometry.y() + round(
        (
            rect.y
            - geometry.y()
        )
        / ratio
    )

    width = max(
        1,
        round(
            rect.width
            / ratio
        ),
    )

    height = max(
        1,
        round(
            rect.height
            / ratio
        ),
    )

    return Rect(
        x=x,
        y=y,
        width=width,
        height=height,
    )


def convert_native_rect(
    rect: Rect,
    screens: Iterable[ScreenT],
) -> tuple[Rect, ScreenT] | None:
    screens_list = list(
        screens
    )

    screen = screen_for_native_rect(
        rect,
        screens_list,
    )

    if screen is None:
        if CARET_DIAGNOSTICS_ENABLED:
            print(
                "[Kaokey coordinates] "
                f"no QScreen for native rect {rect}",
                flush=True,
            )

        return None

    converted = native_rect_to_qt(
        rect,
        screen,
    )

    if CARET_DIAGNOSTICS_ENABLED:
        geometry = screen.geometry()
        name_method = getattr(
            screen,
            "name",
            None,
        )
        screen_name = (
            name_method()
            if callable(name_method)
            else "<unknown>"
        )

        print(
            "[Kaokey coordinates] "
            f"screen={screen_name!r}, "
            f"dpr={screen.devicePixelRatio()}, "
            "qt_geometry="
            f"({geometry.x()}, {geometry.y()}, "
            f"{geometry.width()}, {geometry.height()}), "
            f"native={rect}, qt={converted}",
            flush=True,
        )

    return (
        converted,
        screen,
    )


def native_screen_rect(
    screen: ScreenLike,
) -> Rect:
    geometry = screen.geometry()
    ratio = max(
        1.0,
        float(
            screen.devicePixelRatio()
        ),
    )

    return Rect(
        x=geometry.x(),
        y=geometry.y(),
        width=max(
            1,
            round(
                geometry.width()
                * ratio
            ),
        ),
        height=max(
            1,
            round(
                geometry.height()
                * ratio
            ),
        ),
    )

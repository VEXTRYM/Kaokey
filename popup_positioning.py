from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def left(self) -> int:
        return self.x

    @property
    def top(self) -> int:
        return self.y

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height


def clamp_popup_position(
    x: int,
    y: int,
    popup_width: int,
    popup_height: int,
    available: Rect,
) -> tuple[int, int]:
    max_x = (
        available.right
        - popup_width
    )

    max_y = (
        available.bottom
        - popup_height
    )

    if max_x < available.left:
        clamped_x = available.left
    else:
        clamped_x = max(
            available.left,
            min(
                x,
                max_x,
            ),
        )

    if max_y < available.top:
        clamped_y = available.top
    else:
        clamped_y = max(
            available.top,
            min(
                y,
                max_y,
            ),
        )

    return (
        clamped_x,
        clamped_y,
    )


def position_near_caret(
    caret: Rect,
    popup_width: int,
    popup_height: int,
    available: Rect,
    gap: int,
    above_gap: int | None = None,
) -> tuple[int, int]:
    x = caret.left

    below_y = (
        caret.bottom
        + gap
    )

    if above_gap is None:
        above_gap = gap

    above_y = (
        caret.top
        - popup_height
        - above_gap
    )

    if (
        below_y + popup_height
        <= available.bottom
    ):
        y = below_y
    elif above_y >= available.top:
        y = above_y
    else:
        y = below_y

    return clamp_popup_position(
        x,
        y,
        popup_width,
        popup_height,
        available,
    )


def center_popup(
    popup_width: int,
    popup_height: int,
    available: Rect,
) -> tuple[int, int]:
    x = (
        available.left
        + (
            available.width
            - popup_width
        ) // 2
    )

    y = (
        available.top
        + (
            available.height
            - popup_height
        ) // 2
    )

    return clamp_popup_position(
        x,
        y,
        popup_width,
        popup_height,
        available,
    )

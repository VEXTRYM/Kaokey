from collections.abc import Sequence

from PySide6.QtGui import QScreen

from kaokey.ui.popup.popup_positioning import Rect


def native_rect_to_qt(
    rect: Rect,
    screens: Sequence[QScreen],
) -> tuple[Rect, QScreen | None]:
    """Translate X11/AT-SPI pixels to Qt's device-independent desktop.

    Qt preserves the native screen origins on X11 but scales their sizes.
    Scaling the global position directly breaks monitors with nonzero origins.
    """
    for screen in screens:
        geometry = screen.geometry()
        ratio = screen.devicePixelRatio()
        if ratio <= 0:
            continue
        if (
            geometry.x() <= rect.x < geometry.x() + geometry.width() * ratio
            and geometry.y() <= rect.y < geometry.y() + geometry.height() * ratio
        ):
            return (
                Rect(
                    geometry.x() + round((rect.x - geometry.x()) / ratio),
                    geometry.y() + round((rect.y - geometry.y()) / ratio),
                    max(1, round(rect.width / ratio)),
                    max(1, round(rect.height / ratio)),
                ),
                screen,
            )
    return rect, None

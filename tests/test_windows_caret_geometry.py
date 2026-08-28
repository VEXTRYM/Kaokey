import ctypes

from platforms.windows.foreground import (
    GUIThreadInfo,
    _get_native_caret_rect,
)


class FakeUser32:
    def ClientToScreen(
        self,
        hwnd: object,
        point_pointer: object,
    ) -> int:
        del hwnd

        point = point_pointer._obj
        point.x += 100
        point.y += 200
        return 1


def test_native_caret_uses_right_edge_as_insertion_x() -> None:
    info = GUIThreadInfo()
    info.hwndCaret = 1
    info.rcCaret.left = 10
    info.rcCaret.top = 20
    info.rcCaret.right = 18
    info.rcCaret.bottom = 35

    rect = _get_native_caret_rect(
        FakeUser32(),
        info,
    )

    assert rect is not None
    assert rect.x == 117
    assert rect.y == 220
    assert rect.width == 1
    assert rect.height == 15

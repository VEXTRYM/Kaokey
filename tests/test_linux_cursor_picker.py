from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from kaokey.config.popup_constants import POPUP_WINDOW_TITLE
from kaokey.platforms.linux.wayland.kwin import KWinBridge
from kaokey.platforms.linux.wayland.popup_backend import WaylandPopupBackend
from kaokey.platforms.popup_backend import PopupContext
from kaokey.ui.coordinators.popup_coordinator import PopupCoordinator


@pytest.mark.parametrize("add_space", [False, True])
def test_wayland_selection_copies_text_with_configured_spacing(qapp, add_space):
    backend = WaylandPopupBackend(qapp)
    contexts = []
    backend.capture_context_async([], contexts.append)
    assert contexts == [PopupContext(target=None)]
    assert not backend.capabilities.text_insertion
    picker = SimpleNamespace(
        active_hotkey=None,
        backend=backend,
        copy_text=Mock(),
        popup_window=SimpleNamespace(auto_close_suspended=False),
        settings=SimpleNamespace(add_space_after_insert=add_space),
        target=contexts[0].target,
    )
    PopupCoordinator.try_popup_insertion(picker, {"text": "(≧▽≦)"}, 0)
    picker.copy_text.assert_called_once_with("(≧▽≦)" + (" " if add_space else ""))


def test_kwin_cursor_placement_targets_only_picker_and_clamps():
    bridge = SimpleNamespace(execute=Mock())
    KWinBridge.place_at_cursor(bridge, "Kaokey picker")
    script = bridge.execute.call_args.args[0]
    assert "workspace.cursorPos" in script
    assert "workspace.screenAt(p)" in script
    assert 'w.caption === "Kaokey picker"' in script
    assert "w.pid ===" in script
    assert "Math.max(a.x" in script
    assert "Math.max(a.y" in script


@pytest.mark.parametrize("visible", [False, True])
def test_wayland_placement_waits_for_exposure_and_skips_closed_windows(visible):
    window = Mock()
    window.title.return_value = POPUP_WINDOW_TITLE
    window.winId.return_value = 42
    window.isVisible.return_value = visible
    window.isExposed.side_effect = [False, True]
    backend = SimpleNamespace(
        app=SimpleNamespace(allWindows=lambda: [window]),
        _kwin=SimpleNamespace(available=True, place_at_cursor=Mock()),
        _placement_window_id=42,
        _placement_attempts=20,
        _placement_timer=Mock(),
    )
    WaylandPopupBackend._place_exposed_popup(backend)
    backend._kwin.place_at_cursor.assert_not_called()
    if visible:
        backend._placement_timer.start.assert_called_once_with(16)
        WaylandPopupBackend._place_exposed_popup(backend)
        backend._kwin.place_at_cursor.assert_called_once_with(POPUP_WINDOW_TITLE)
    else:
        backend._placement_timer.start.assert_not_called()

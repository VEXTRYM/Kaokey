"""Linux popup regressions; also runnable with python -m unittest discover."""

import ctypes
import os
import tempfile
import unittest
from contextlib import nullcontext
from typing import Any, cast
from unittest.mock import Mock, patch

from PySide6.QtCore import QRect, QSettings
from PySide6.QtWidgets import QApplication

from kaokey.config.settings import SettingsManager
from kaokey.platforms.linux import common_popup_backend, native_accessibility
from kaokey.platforms.linux.native_accessibility import (
    ATSPI_STATE_ACTIVE,
    ATSPI_STATE_FOCUSED,
    LinuxAccessibility,
    LinuxAccessibleTarget,
    _AtspiLibrary,
    _AtspiRect,
    _GArray,
)
from kaokey.platforms.linux.x11 import hotkey, popup_backend
from kaokey.platforms.linux.x11.coordinates import native_rect_to_qt
from kaokey.platforms.linux.x11.desktop import X11Desktop, X11Target
from kaokey.platforms.linux.x11.xlib import KEY_PRESS, KEY_RELEASE, WINDOW, XEvent
from kaokey.platforms.popup_backend import (
    PopupContext, PopupHotkeyActivation, PopupInsertionResult,
)
from kaokey.ui.popup.popup_positioning import Rect
from kaokey.ui.popup.popup_window import PopupWindow


class TreeLibrary:
    def __init__(self, active: bool = True) -> None:
        # The inactive application's last text field still reports FOCUSED.
        self.tree = {1: [10, 20], 10: [11], 11: [12], 20: [21], 21: [22]}
        self.active = active
        self.released: list[int] = []

    def desktop(self):
        return 1

    def child_count(self, pointer):
        return len(self.tree.get(pointer, []))

    def child_at(self, pointer, index):
        return self.tree[pointer][index]

    def state_enabled(self, pointer, state):
        if state == ATSPI_STATE_ACTIVE:
            return self.active and pointer == 21
        return state == ATSPI_STATE_FOCUSED and pointer in (12, 22)

    def text_interface(self, pointer):
        return pointer + 100 if pointer in (12, 22) else None

    def caret_offset(self, text_interface):
        return 4

    def focused_matches(self, pointer):
        return ()

    def prime_accessibility(self, pointer):
        pass

    def process_id(self, pointer):
        return {10: 1000, 20: 2000}[pointer]

    def unref(self, pointer):
        self.released.append(pointer)


class AccessibilityTests(unittest.TestCase):
    def test_active_application_wins_over_stale_focused_widget(self):
        library = TreeLibrary()
        accessibility = cast(Any, LinuxAccessibility.__new__(LinuxAccessibility))
        accessibility.library = library
        target = accessibility.capture_target()
        self.assertIsNotNone(target)
        assert target is not None
        self.assertEqual(target.pointer, 22)
        self.assertNotIn(22, library.released)
        target.close()
        self.assertEqual(set(library.released), {1, 10, 11, 20, 21, 22, 122})
        self.assertEqual(len(library.released), len(set(library.released)))

    def test_focus_scan_still_works_without_active_state(self):
        library = TreeLibrary(active=False)
        accessibility = cast(Any, LinuxAccessibility.__new__(LinuxAccessibility))
        accessibility.library = library
        target = accessibility.capture_target()
        assert target is not None
        self.assertEqual(target.pointer, 12)
        target.close()

    def test_scan_deadline_releases_every_owned_reference(self):
        library = TreeLibrary()
        accessibility = cast(Any, LinuxAccessibility.__new__(LinuxAccessibility))
        accessibility.library = library
        clock = iter(index / 10 for index in range(100))
        with patch.object(native_accessibility.time, "monotonic", side_effect=lambda: next(clock)):
            self.assertIsNone(accessibility.capture_target())
        self.assertIn(1, library.released)
        self.assertEqual(len(library.released), len(set(library.released)))

    def test_native_process_id_limits_search_to_the_foreground_app(self):
        library = TreeLibrary(active=False)
        accessibility = cast(Any, LinuxAccessibility.__new__(LinuxAccessibility))
        accessibility.library = library
        target = accessibility.capture_target(process_id=2000)
        assert target is not None
        self.assertEqual(target.pointer, 22)
        target.close()
        self.assertNotIn(11, library.released)  # unrelated app was not traversed

    def test_missing_foreground_provider_does_not_select_another_app(self):
        library = TreeLibrary()
        accessibility = cast(Any, LinuxAccessibility.__new__(LinuxAccessibility))
        accessibility.library = library
        self.assertIsNone(accessibility.capture_target(process_id=9999))
        self.assertEqual(set(library.released), {1, 10, 20})

    def test_focused_object_query_bypasses_menu_tree(self):
        library = TreeLibrary()
        library.focused_matches = Mock(return_value=(22,))
        library.child_count = Mock(wraps=library.child_count)
        accessibility = cast(Any, LinuxAccessibility.__new__(LinuxAccessibility))
        accessibility.library = library
        target = accessibility.capture_target(process_id=2000)
        assert target is not None
        self.assertEqual(target.pointer, 22)
        library.focused_matches.assert_called_once_with(21)
        self.assertNotIn(22, [call.args[0] for call in library.child_count.call_args_list])
        target.close()
        self.assertEqual(set(library.released), {1, 10, 20, 21, 22, 122})

    def test_focused_query_duplicate_references_are_released(self):
        library = TreeLibrary()
        library.focused_matches = Mock(return_value=(21, 22, 22))
        accessibility = cast(Any, LinuxAccessibility.__new__(LinuxAccessibility))
        accessibility.library = library
        target = accessibility.capture_target(process_id=2000)
        assert target is not None
        self.assertEqual(target.pointer, 22)
        target.close()
        self.assertEqual(library.released.count(21), 2)
        self.assertEqual(library.released.count(22), 2)

    def test_collection_array_transfers_accessibles_and_frees_query_objects(self):
        library = cast(Any, _AtspiLibrary.__new__(_AtspiLibrary))
        library.atspi = Mock()
        library.glib = Mock()
        library.unref = Mock()
        library.atspi.atspi_accessible_get_collection_iface.return_value = 90
        library.atspi.atspi_state_set_new.return_value = 91
        library.atspi.atspi_match_rule_new.return_value = 92
        data = (ctypes.c_void_p * 2)(42, 43)
        array = _GArray(ctypes.cast(data, ctypes.c_void_p), 2)
        library.atspi.atspi_collection_get_matches.return_value = ctypes.pointer(array)
        self.assertEqual(library.focused_matches(123), (42, 43))
        self.assertEqual([call.args[0] for call in library.unref.call_args_list], [92, 91, 90])
        library.glib.g_array_unref.assert_called_once()
        library.atspi.atspi_state_set_add.assert_called_once_with(91, ATSPI_STATE_FOCUSED)

    def test_collection_query_unavailable_leaves_tree_search_usable(self):
        library = cast(Any, _AtspiLibrary.__new__(_AtspiLibrary))
        library.atspi = Mock()
        library.atspi.atspi_accessible_get_collection_iface.return_value = None
        self.assertEqual(library.focused_matches(123), ())
        library.atspi.atspi_collection_get_matches.assert_not_called()

    def test_negative_monitor_coordinates_are_valid(self):
        library = cast(Any, _AtspiLibrary.__new__(_AtspiLibrary))
        library.free = Mock()
        value = _AtspiRect(-900, -200, 0, 18)
        self.assertEqual(library._consume_rect(ctypes.pointer(value)), Rect(-900, -200, 0, 18))
        library.free.assert_called_once()

    def test_empty_extents_are_not_a_caret_at_the_origin(self):
        library = cast(Any, _AtspiLibrary.__new__(_AtspiLibrary))
        library.free = Mock()
        self.assertIsNone(library._consume_rect(ctypes.pointer(_AtspiRect(0, 0, 0, 0))))
        library.free.assert_called_once()

    def test_caret_at_end_of_text_uses_previous_glyph(self):
        library = Mock()
        library.text_interface.return_value = 100
        library.caret_offset.return_value = 4
        library.character_extents.side_effect = [None, Rect(-200, 30, 12, 20)]
        library.range_extents.return_value = None
        target = LinuxAccessibleTarget(42, library)
        accessibility = cast(Any, LinuxAccessibility.__new__(LinuxAccessibility))
        accessibility.library = library
        self.assertEqual(accessibility.caret_rect(target), Rect(-188, 30, 1, 20))
        library.unref.assert_called_once_with(100)
        target.close()


class CoordinateTests(unittest.TestCase):
    def screen(self, rect, ratio):
        screen = Mock()
        screen.geometry.return_value = QRect(*rect)
        screen.devicePixelRatio.return_value = ratio
        return screen

    def test_scaled_screen_with_nonzero_origin(self):
        left = self.screen((-1920, 0, 1920, 1080), 1)
        right = self.screen((0, 0, 1920, 1080), 2)
        self.assertEqual(
            native_rect_to_qt(Rect(2000, 600, 2, 36), [left, right]),
            (Rect(1000, 300, 1, 18), right),
        )

    def test_monitor_origin_is_not_scaled(self):
        screen = self.screen((1920, -200, 1280, 720), 1.5)
        self.assertEqual(
            native_rect_to_qt(Rect(2220, -50, 3, 30), [screen]),
            (Rect(2120, -100, 2, 20), screen),
        )


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            os.environ["QT_QPA_PLATFORM"] = "offscreen"
            app = QApplication([])
        cls.app = app

    def setUp(self):
        self.desktop = Mock()
        self.desktop.xtest = Mock()
        self.desktop.active_window.return_value = 123
        self.desktop.window_process_id.return_value = 2000
        self.desktop.pointer_rect.return_value = Rect(450, 300, 1, 1)
        self.desktop.paste_text.return_value = True
        self.accessibility = Mock(available=False)
        with (
            patch.object(popup_backend, "X11Desktop", return_value=self.desktop),
            patch.object(popup_backend, "x11_hotkeys_available", return_value=True),
            patch.object(common_popup_backend, "LinuxAccessibility", return_value=self.accessibility),
        ):
            self.backend = popup_backend.X11PopupBackend(self.app)

    def tearDown(self):
        self.backend.clear_hotkey()

    def test_native_target_survives_accessibility_timeout_and_ignores_late_reply(self):
        timers = []
        contexts = []
        with (
            patch.object(popup_backend.QTimer, "singleShot", side_effect=lambda ms, cb: timers.append((ms, cb))),
            patch.object(common_popup_backend.LinuxPopupBackendBase, "capture_context_async") as capture,
        ):
            self.backend.capture_context_async([], contexts.append)
            self.assertEqual(capture.call_args.kwargs, {"process_id": 2000})
            self.desktop.active_window.assert_called_once()
            self.assertLess(timers[0][0], 500)
            timers[0][1]()
            self.assertEqual(contexts, [PopupContext(X11Target(123), Rect(450, 300, 1, 1))])
            capture.call_args.args[1](PopupContext(None, Rect(10, 20, 1, 15)))
            self.assertEqual(len(contexts), 1)

    def test_accessible_caret_takes_precedence_over_pointer(self):
        contexts = []
        with (
            patch.object(popup_backend.QTimer, "singleShot"),
            patch.object(common_popup_backend.LinuxPopupBackendBase, "capture_context_async") as capture,
        ):
            self.backend.capture_context_async([], contexts.append)
            capture.call_args.args[1](PopupContext(None, Rect(10, 20, 1, 15)))
        self.assertEqual(contexts[0].caret_rect, Rect(10, 20, 1, 15))

    def test_insertion_works_without_accessible_text_field(self):
        before_transfer = Mock()
        result = self.backend.insert_text(X11Target(123), "(◕‿◕) ", before_focus_transfer=before_transfer)
        self.assertEqual(result, PopupInsertionResult(True, True))
        self.desktop.paste_text.assert_called_once_with(123, "(◕‿◕) ", before_transfer)
        self.accessibility.insert_text.assert_not_called()

    def test_failed_focus_does_not_claim_insertion(self):
        self.desktop.paste_text.return_value = False
        result = self.backend.insert_text(X11Target(123), "x", before_focus_transfer=Mock())
        self.assertEqual(result, PopupInsertionResult(False))

    def test_changed_target_is_detected_before_popup_refocus(self):
        self.desktop.target_still_active.return_value = False
        self.assertFalse(self.backend.target_still_active(X11Target(123)))

    def test_popup_refocus_uses_a_fresh_native_activation(self):
        self.assertTrue(self.backend.request_popup_activation(456, PopupHotkeyActivation()))
        self.desktop.request_window_activation.assert_called_once_with(456, None)

    def paste_desktop(self):
        desktop = cast(Any, X11Desktop.__new__(X11Desktop))
        desktop.connection = Mock()
        codes = {"Shift_L": 50, "Insert": 118}
        desktop.connection.keysym_keycode.side_effect = lambda name: codes.get(name, 0)
        desktop.connection.key_is_pressed.return_value = False
        desktop.xtest = Mock()
        desktop.xtest.XTestFakeKeyEvent.return_value = 1
        desktop._checked = nullcontext
        desktop.server_timestamp = Mock(return_value=456)
        desktop.target_still_active = Mock(return_value=True)
        desktop._focus_belongs_to = Mock(return_value=True)
        return desktop

    def test_paste_transfers_unicode_and_releases_every_synthetic_key(self):
        desktop = self.paste_desktop()
        before_transfer = Mock()
        text = "(ﾉ◕ヮ◕)ﾉ*:･ﾟ✧ 😀 "
        self.assertTrue(desktop.paste_text(123, text, before_transfer))
        before_transfer.assert_called_once()
        desktop.connection.request_window_activation.assert_called_once_with(123, 456)
        events = [(call.args[1], call.args[2]) for call in desktop.xtest.XTestFakeKeyEvent.call_args_list]
        self.assertEqual(events, [(50, 1), (118, 1), (118, 0), (50, 0)])
        self.assertEqual(self.app.clipboard().text(), text)

    def test_paste_never_types_into_unrelated_window(self):
        desktop = self.paste_desktop()
        desktop.target_still_active.return_value = False
        clock = iter(index / 5 for index in range(100))
        with (
            patch("kaokey.platforms.linux.x11.desktop.time.monotonic", side_effect=lambda: next(clock)),
            patch("kaokey.platforms.linux.x11.desktop.time.sleep"),
        ):
            self.assertFalse(desktop.paste_text(123, "x", Mock()))
        desktop.xtest.XTestFakeKeyEvent.assert_not_called()

    def test_held_modifiers_prevent_paste(self):
        desktop = self.paste_desktop()
        desktop.connection.key_is_pressed.return_value = True
        before_transfer = Mock()
        clock = iter(index / 5 for index in range(100))
        with (
            patch("kaokey.platforms.linux.x11.desktop.time.monotonic", side_effect=lambda: next(clock)),
            patch("kaokey.platforms.linux.x11.desktop.time.sleep"),
        ):
            self.assertFalse(desktop.paste_text(123, "x", before_transfer))
        desktop.xtest.XTestFakeKeyEvent.assert_not_called()
        before_transfer.assert_not_called()

    def test_partial_key_failure_still_releases_shift(self):
        desktop = self.paste_desktop()
        desktop.xtest.XTestFakeKeyEvent.side_effect = [1, 0, 1]
        self.assertFalse(desktop.paste_text(123, "x", Mock()))
        events = [(call.args[1], call.args[2]) for call in desktop.xtest.XTestFakeKeyEvent.call_args_list]
        self.assertEqual(events, [(50, 1), (118, 1), (50, 0)])

    def native_hotkey(self):
        read_fd, write_fd = os.pipe()
        connection = Mock(file_descriptor=read_fd)
        codes = {"K": 45, "Alt_L": 64, "Alt_R": 108}
        connection.keysym_keycode.side_effect = lambda name: codes.get(name, 0)
        connection.modifier_mask_for_keysyms.return_value = 8
        connection.lock_modifier_variants.return_value = (0,)
        activated = Mock()
        with patch.object(hotkey, "X11Connection", return_value=connection):
            shortcut = hotkey.X11GlobalHotkey("Alt", "K", activated)
        shortcut.register()
        self.addCleanup(os.close, read_fd)
        self.addCleanup(os.close, write_fd)
        self.addCleanup(shortcut.close)
        return shortcut, connection, activated

    def feed_key(self, shortcut, connection, event_type, timestamp=789):
        event = XEvent()
        event.type = event_type
        event.xkey.keycode = 45
        event.xkey.time = timestamp
        connection.pending_events.side_effect = [1, 0]
        connection.next_event.return_value = event
        shortcut._drain_events()

    def test_hotkey_waits_for_release_before_querying_gtk_caret(self):
        shortcut, connection, activated = self.native_hotkey()
        connection.key_is_pressed.return_value = True
        self.feed_key(shortcut, connection, KEY_PRESS)
        activated.assert_not_called()
        shortcut._activate_after_release()
        activated.assert_not_called()
        connection.key_is_pressed.return_value = False
        self.feed_key(shortcut, connection, KEY_RELEASE)
        shortcut._activate_after_release()
        activated.assert_called_once_with(789)
        self.assertFalse(shortcut.activation_timer.isActive())

    def test_hotkey_waits_for_alt_as_well_as_the_letter(self):
        shortcut, connection, activated = self.native_hotkey()
        self.feed_key(shortcut, connection, KEY_PRESS)
        connection.key_is_pressed.side_effect = lambda code: code == 64
        shortcut._activate_after_release()
        activated.assert_not_called()
        connection.key_is_pressed.side_effect = lambda code: False
        shortcut._activate_after_release()
        activated.assert_called_once_with(789)

    def test_hotkey_unregister_cancels_delayed_activation(self):
        shortcut, connection, activated = self.native_hotkey()
        self.feed_key(shortcut, connection, KEY_PRESS)
        shortcut.unregister()
        connection.key_is_pressed.return_value = False
        shortcut._activate_after_release()
        activated.assert_not_called()


class NativeWindowTests(unittest.TestCase):
    def test_timestamp_is_obtained_from_an_x_server_event(self):
        desktop = cast(Any, X11Desktop.__new__(X11Desktop))
        desktop.connection = Mock()
        desktop._time_window = 100

        def property_event(display, window, mask, event):
            ctypes.cast(event, ctypes.POINTER(XEvent)).contents.xproperty.time = 987654

        desktop.connection.x11.lib.XWindowEvent.side_effect = property_event
        self.assertEqual(desktop.server_timestamp(), 987654)
        desktop.connection.x11.lib.XChangeProperty.assert_called_once()

    def test_focus_in_a_child_window_is_accepted(self):
        desktop = cast(Any, X11Desktop.__new__(X11Desktop))
        desktop.connection = Mock(root_window=1)

        def input_focus(display, focus, revert):
            ctypes.cast(focus, ctypes.POINTER(WINDOW)).contents.value = 124

        def query_tree(display, window, root, parent, children, count):
            ctypes.cast(parent, ctypes.POINTER(WINDOW)).contents.value = 123
            return 1

        desktop.connection.x11.lib.XGetInputFocus.side_effect = input_focus
        desktop.connection.x11.lib.XQueryTree.side_effect = query_tree
        self.assertTrue(desktop._focus_belongs_to(123))
        self.assertFalse(desktop._focus_belongs_to(999))


class PopupPlacementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            os.environ["QT_QPA_PLATFORM"] = "offscreen"
            app = QApplication([])
        cls.app = app

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="kaokey-placement-test-")
        store = QSettings(self.directory.name + "/settings.ini", QSettings.Format.IniFormat)
        self.popup = PopupWindow([], [], SettingsManager(store))
        self.screen = Mock()
        self.screen.availableGeometry.return_value = QRect(0, 0, 1000, 800)

    def tearDown(self):
        self.popup.close()
        self.popup.deleteLater()
        self.directory.cleanup()

    def position(self, caret, width=448, height=330):
        with (
            patch.object(self.popup, "frameGeometry", return_value=QRect(0, 0, width, height)),
            patch.object(QApplication, "screenAt", return_value=self.screen),
        ):
            self.popup.position_popup(caret, self.screen)
        return self.popup.pos().toTuple()

    def test_places_entire_window_immediately_below_caret(self):
        self.assertEqual(self.position(Rect(100, 100, 1, 20)), (100, 124))

    def test_places_above_when_client_fits_below_but_title_bar_does_not(self):
        self.assertEqual(self.position(Rect(100, 475, 1, 20)), (100, 141))

    def test_above_placement_uses_the_same_small_gap_as_below(self):
        self.assertEqual(self.position(Rect(100, 750, 1, 20)), (100, 416))

    def test_right_screen_edge_clamps_the_entire_frame(self):
        self.assertEqual(self.position(Rect(990, 100, 1, 20)), (552, 124))

    def test_other_monitor_uses_its_own_work_area(self):
        self.screen.availableGeometry.return_value = QRect(-1280, 40, 1280, 680)
        self.assertEqual(self.position(Rect(-1000, 690, 1, 20)), (-1000, 356))


if __name__ == "__main__":
    unittest.main()

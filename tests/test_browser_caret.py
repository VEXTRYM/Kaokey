"""Browser caret regressions, runnable with unittest without a desktop bus."""

import unittest
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock, patch

from PySide6.QtDBus import QDBusMessage, QDBusVariant

from kaokey.platforms.linux import common_popup_backend, dbus
from kaokey.platforms.linux import native_accessibility
from kaokey.platforms.linux.native_accessibility import (
    ATSPI_STATE_ACTIVE, ATSPI_STATE_FOCUSED, LinuxAccessibility, LinuxAccessibleTarget, _AtspiLibrary,
)
from kaokey.ui.popup.popup_positioning import Rect


class AccessibilityStatusTests(unittest.TestCase):
    def reply(self, *values):
        reply = Mock()
        reply.type.return_value = QDBusMessage.MessageType.ReplyMessage
        reply.arguments.return_value = list(values)
        return reply

    def test_enables_browser_accessibility_with_a_boolean_variant(self):
        bus = Mock()
        bus.call.side_effect = [self.reply(QDBusVariant(False)), self.reply()]
        with patch.object(dbus.QDBusConnection, "sessionBus", return_value=bus):
            self.assertTrue(dbus.ensure_accessibility_enabled())
        get_request, set_request = (call.args[0] for call in bus.call.call_args_list)
        self.assertEqual(get_request.member(), "Get")
        self.assertEqual(get_request.arguments(), ["org.a11y.Status", "IsEnabled"])
        self.assertEqual(set_request.member(), "Set")
        arguments = set_request.arguments()
        self.assertEqual(arguments[:2], ["org.a11y.Status", "IsEnabled"])
        self.assertIsInstance(arguments[2], QDBusVariant)
        self.assertIs(arguments[2].variant(), True)
        self.assertTrue(all(call.args[2] == 500 for call in bus.call.call_args_list))

    def test_enabled_desktop_requires_no_settings_write(self):
        bus = Mock()
        bus.call.return_value = self.reply(QDBusVariant(True))
        with patch.object(dbus.QDBusConnection, "sessionBus", return_value=bus):
            self.assertTrue(dbus.ensure_accessibility_enabled())
        bus.call.assert_called_once()

    def test_disconnected_bus_does_not_attempt_a_settings_write(self):
        bus = Mock()
        bus.isConnected.return_value = False
        with patch.object(dbus.QDBusConnection, "sessionBus", return_value=bus):
            self.assertFalse(dbus.ensure_accessibility_enabled())
        bus.call.assert_not_called()

    def test_unknown_status_is_not_overwritten(self):
        bus = Mock()
        bus.call.return_value = self.reply("not a boolean")
        with patch.object(dbus.QDBusConnection, "sessionBus", return_value=bus):
            self.assertFalse(dbus.ensure_accessibility_enabled())
        bus.call.assert_called_once()

    def test_read_error_does_not_attempt_a_settings_write(self):
        bus = Mock()
        reply = Mock()
        reply.type.return_value = QDBusMessage.MessageType.ErrorMessage
        bus.call.return_value = reply
        with patch.object(dbus.QDBusConnection, "sessionBus", return_value=bus):
            self.assertFalse(dbus.ensure_accessibility_enabled())
        bus.call.assert_called_once()

    def test_rejected_write_is_reported_without_raising(self):
        bus = Mock()
        rejected = Mock()
        rejected.type.return_value = QDBusMessage.MessageType.ErrorMessage
        bus.call.side_effect = [self.reply(False), rejected]
        with patch.object(dbus.QDBusConnection, "sessionBus", return_value=bus):
            self.assertFalse(dbus.ensure_accessibility_enabled())


class BrowserTree:
    """An active browser frame with a focused document and an input field."""

    def __init__(self):
        self.tree = {1: [10], 10: [11], 11: [12, 13]}
        self.released = []

    def desktop(self):
        return 1

    def child_count(self, pointer):
        return len(self.tree.get(pointer, []))

    def child_at(self, pointer, index):
        return self.tree[pointer][index]

    def process_id(self, pointer):
        return 1000

    def state_enabled(self, pointer, state):
        if state == ATSPI_STATE_ACTIVE:
            return pointer == 11
        return state == ATSPI_STATE_FOCUSED and pointer in (12, 13)

    def focused_matches(self, pointer):
        return (12, 13)

    def prime_accessibility(self, pointer):
        pass

    def text_interface(self, pointer):
        return pointer + 100 if pointer in (12, 13) else None

    def caret_offset(self, text_interface):
        return None if text_interface == 112 else 0

    def unref(self, pointer):
        self.released.append(pointer)


class AccessibilityPreparationTests(unittest.TestCase):
    def test_successful_preparation_is_shared_across_hotkey_rebindings(self):
        state = cast(Any, SimpleNamespace(_accessibility_requested=False, _accessibility_available=True))
        with patch.object(common_popup_backend, "ensure_accessibility_enabled", return_value=True) as enable:
            self.assertTrue(common_popup_backend.LinuxPopupBackendBase.prepare_accessibility(state))
            self.assertTrue(common_popup_backend.LinuxPopupBackendBase.prepare_accessibility(state))
        enable.assert_called_once()

    def test_failed_preparation_can_be_retried(self):
        state = cast(Any, SimpleNamespace(_accessibility_requested=False, _accessibility_available=True))
        with patch.object(common_popup_backend, "ensure_accessibility_enabled", side_effect=[False, True]):
            self.assertFalse(common_popup_backend.LinuxPopupBackendBase.prepare_accessibility(state))
            self.assertTrue(common_popup_backend.LinuxPopupBackendBase.prepare_accessibility(state))

    def test_unavailable_native_accessibility_does_not_change_desktop_settings(self):
        state = cast(Any, SimpleNamespace(_accessibility_requested=False, _accessibility_available=False))
        with patch.object(common_popup_backend, "ensure_accessibility_enabled") as enable:
            self.assertFalse(common_popup_backend.LinuxPopupBackendBase.prepare_accessibility(state))
        enable.assert_not_called()


class BrowserCaretTests(unittest.TestCase):
    def test_chrome_metadata_request_releases_its_native_attributes_table(self):
        library = cast(Any, _AtspiLibrary.__new__(_AtspiLibrary))
        library.atspi = Mock()
        library.glib = Mock()
        library.atspi.atspi_accessible_get_attributes.return_value = 1234
        library.prime_accessibility(11)
        library.atspi.atspi_accessible_get_attributes.assert_called_once()
        library.glib.g_hash_table_unref.assert_called_once()
        self.assertEqual(library.glib.g_hash_table_unref.call_args.args[0].value, 1234)

    def test_chrome_cold_frame_is_requeried_when_renderer_tree_arrives(self):
        library = BrowserTree()
        library.tree[11] = []
        library.focused_matches = Mock(side_effect=[(), (13,)])
        library.prime_accessibility = Mock()
        accessibility = cast(Any, LinuxAccessibility.__new__(LinuxAccessibility))
        accessibility.library = library
        with patch.object(native_accessibility.time, "sleep"):
            target = accessibility.capture_target(process_id=1000)
        assert target is not None
        self.assertEqual(target.pointer, 13)
        library.prime_accessibility.assert_called_once_with(11)
        self.assertEqual(library.focused_matches.call_count, 2)
        target.close()

    def test_document_without_caret_does_not_hide_focused_input(self):
        library = BrowserTree()
        accessibility = cast(Any, LinuxAccessibility.__new__(LinuxAccessibility))
        accessibility.library = library
        target = accessibility.capture_target(process_id=1000)
        assert target is not None
        self.assertEqual(target.pointer, 13)
        self.assertIn(112, library.released)
        self.assertIn(12, library.released)
        target.close()
        self.assertEqual(library.released.count(13), 1)

    def test_tree_fallback_also_skips_text_containers_without_carets(self):
        library = BrowserTree()
        library.focused_matches = Mock(return_value=())
        accessibility = cast(Any, LinuxAccessibility.__new__(LinuxAccessibility))
        accessibility.library = library
        target = accessibility.capture_target(process_id=1000)
        assert target is not None
        self.assertEqual(target.pointer, 13)
        target.close()

    def caret_accessibility(self, offset):
        library = Mock()
        library.text_interface.return_value = 100
        library.caret_offset.return_value = offset
        library.character_extents.return_value = None
        accessibility = cast(Any, LinuxAccessibility.__new__(LinuxAccessibility))
        accessibility.library = library
        target = LinuxAccessibleTarget(42, library)
        self.addCleanup(target.close)
        return accessibility, library, target

    def test_empty_browser_field_uses_collapsed_range(self):
        accessibility, library, target = self.caret_accessibility(0)
        library.range_extents.return_value = Rect(120, 200, 0, 22)
        self.assertEqual(accessibility.caret_rect(target), Rect(120, 200, 1, 22))
        library.range_extents.assert_called_once_with(100, 0, 0)
        library.character_extents.assert_called_once_with(100, 0)

    def test_newline_uses_current_line_range_before_previous_glyph(self):
        accessibility, library, target = self.caret_accessibility(5)
        library.range_extents.return_value = Rect(120, 222, 0, 22)
        self.assertEqual(accessibility.caret_rect(target), Rect(120, 222, 1, 22))
        library.character_extents.assert_called_once_with(100, 5)

    def test_existing_character_caret_does_not_need_a_range_fallback(self):
        accessibility, library, target = self.caret_accessibility(5)
        library.character_extents.return_value = Rect(500, 300, 10, 22)
        self.assertEqual(accessibility.caret_rect(target), Rect(500, 300, 1, 22))
        library.range_extents.assert_not_called()


if __name__ == "__main__":
    unittest.main()

from PySide6.QtCore import (
    QEvent,
    QPoint,
    QRect,
    QTimer,
    Qt,
    Signal,
)

from PySide6.QtGui import (
    QCloseEvent,
    QKeySequence,
    QScreen,
    QShortcut,
)

from PySide6.QtWidgets import (
    QApplication,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from constants import WINDOW_TITLE
from models import Kaomoji
from popup_positioning import (
    Rect,
    center_popup,
    clamp_popup_position,
    position_near_caret,
)
from settings import SettingsManager
from style_constants import (
    POPUP_CARET_ABOVE_GAP,
    POPUP_CARET_GAP,
)
from widget_styles import (
    style_popup_layout,
    style_popup_window,
)
from widgets.kaomoji_browser import (
    KaomojiBrowser,
)


class PopupWindow(QWidget):
    copy_requested = Signal(object)
    favorite_toggle_requested = Signal(object)
    closed = Signal()

    def __init__(
        self,
        main_tags: list[str],
        kaomoji: list[Kaomoji],
        settings: SettingsManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent,
            (
                Qt.WindowType.Tool
                | Qt.WindowType.WindowStaysOnTopHint
            ),
        )

        self.settings = settings
        self.has_been_shown = False
        self.auto_close_suspended = False

        # When automatic insertion temporarily activates the target
        # application, remember which popup widget owned keyboard focus.
        # Restoring that exact widget makes repeated keyboard selection
        # continue from the same place instead of unexpectedly jumping
        # back to Search.
        self.focus_before_external_action: (
            QWidget | None
        ) = None

        self.setWindowTitle(
            WINDOW_TITLE
        )

        style_popup_window(
            self,
            *self.settings.popup_size,
        )

        layout = QVBoxLayout(
            self
        )

        style_popup_layout(
            layout
        )

        self.browser = KaomojiBrowser(
            main_tags,
            kaomoji,
        )

        layout.addWidget(
            self.browser
        )

        self.browser.copy_requested.connect(
            self.handle_copy
        )

        self.browser.favorite_toggle_requested.connect(
            self.favorite_toggle_requested.emit
        )

        self.escape_shortcut = QShortcut(
            QKeySequence("Esc"),
            self,
        )

        self.escape_shortcut.activated.connect(
            self.close
        )

    # =============================
    # Size
    # =============================

    def apply_configured_size(
        self,
    ) -> None:
        style_popup_window(
            self,
            *self.settings.popup_size,
        )

    def set_popup_size(
        self,
        width: int,
        height: int,
    ) -> None:
        style_popup_window(
            self,
            width,
            height,
        )

    # =============================
    # Data
    # =============================

    def set_main_tags(
        self,
        main_tags: list[str],
    ) -> None:
        self.browser.set_main_tags(
            main_tags
        )

    def set_kaomoji(
        self,
        kaomoji: list[Kaomoji],
    ) -> None:
        self.browser.set_kaomoji(
            kaomoji
        )

    def refresh(
        self,
    ) -> None:
        self.browser.refresh()

    # =============================
    # Show / close
    # =============================

    def show_popup(
        self,
        caret_rect: Rect | None = None,
        fallback_screen: QScreen | None = None,
    ) -> None:
        # Every hotkey invocation starts with
        # a fresh text search. Other filters
        # (favorite/main tag) are intentionally
        # preserved.
        self.reset_search()

        self.apply_configured_size()

        self.position_popup(
            caret_rect,
            fallback_screen,
        )

        self.has_been_shown = True

        self.show()
        self.raise_()
        self.activateWindow()

        # Focus after Qt has finished showing
        # and activating the tool window.
        QTimer.singleShot(
            0,
            self.focus_search,
        )

    def reset_search(
        self,
    ) -> None:
        self.browser.search_input.clear()

    def focus_search(
        self,
    ) -> None:
        self.browser.search_input.setFocus()

    def suspend_auto_close(
        self,
    ) -> None:
        # Automatic insertion temporarily moves focus to the target app.
        # That deactivation is intentional and must not close the popup.
        focus_widget = (
            QApplication.focusWidget()
        )

        if (
            focus_widget is not None
            and (
                focus_widget is self
                or self.isAncestorOf(
                    focus_widget
                )
            )
        ):
            self.focus_before_external_action = (
                focus_widget
            )
        else:
            self.focus_before_external_action = None

        self.auto_close_suspended = True

    def restore_after_external_action(
        self,
    ) -> None:
        if not self.isVisible():
            self.auto_close_suspended = False
            self.focus_before_external_action = None
            return

        self.raise_()
        self.activateWindow()

        # Let Windows/Qt finish activating the popup first. On the following
        # event-loop turn, restore the exact control that owned keyboard focus.
        QTimer.singleShot(
            0,
            self.finish_external_restore,
        )

    def finish_external_restore(
        self,
    ) -> None:
        if not self.isVisible():
            self.auto_close_suspended = False
            self.focus_before_external_action = None
            return

        focus_widget = (
            self.focus_before_external_action
        )

        self.focus_before_external_action = None

        if (
            focus_widget is not None
            and focus_widget.isVisible()
            and focus_widget.isEnabled()
        ):
            focus_widget.setFocus(
                Qt.FocusReason.OtherFocusReason
            )
        else:
            self.focus_search()

        # Keep deactivation suppression for one more event-loop turn. This
        # prevents a queued WindowDeactivate from the intentional target-app
        # handoff from closing a popup that has just been reactivated.
        QTimer.singleShot(
            0,
            self.resume_auto_close,
        )

    def resume_auto_close(
        self,
    ) -> None:
        self.auto_close_suspended = False

    def event(
        self,
        event: QEvent,
    ) -> bool:
        event_type = event.type()

        if (
            event_type
            == QEvent.Type.WindowDeactivate
            and self.isVisible()
            and not self.auto_close_suspended
        ):
            # Clicking another application/window should end the popup
            # session, matching the native Windows picker behavior.
            QTimer.singleShot(
                0,
                self.close_if_inactive,
            )

        elif (
            event_type
            == QEvent.Type.WindowStateChange
            and (
                self.windowState()
                & Qt.WindowState.WindowMinimized
            )
        ):
            QTimer.singleShot(
                0,
                self.close,
            )

        return super().event(
            event
        )

    def close_if_inactive(
        self,
    ) -> None:
        if (
            self.isVisible()
            and not self.isActiveWindow()
            and not self.auto_close_suspended
        ):
            self.close()

    def closeEvent(
        self,
        event: QCloseEvent,
    ) -> None:
        if self.has_been_shown:
            position = self.pos()

            self.settings.set_popup_position(
                position.x(),
                position.y(),
            )

        self.auto_close_suspended = False
        self.focus_before_external_action = None
        self.closed.emit()

        super().closeEvent(
            event
        )

    # =============================
    # Positioning
    # =============================

    def position_popup(
        self,
        caret_rect: Rect | None,
        fallback_screen: QScreen | None,
    ) -> None:
        if caret_rect is not None:
            screen = QApplication.screenAt(
                QPoint(
                    (
                        caret_rect.left
                        + caret_rect.width // 2
                    ),
                    (
                        caret_rect.top
                        + caret_rect.height // 2
                    ),
                )
            )

            if screen is None:
                screen = fallback_screen

            if screen is None:
                screen = (
                    QApplication.primaryScreen()
                )

            if screen is not None:
                available = self.rect_from_qrect(
                    screen.availableGeometry()
                )

                x, y = position_near_caret(
                    caret_rect,
                    self.width(),
                    self.height(),
                    available,
                    POPUP_CARET_GAP,
                    POPUP_CARET_ABOVE_GAP,
                )

                self.move(
                    x,
                    y,
                )

                return

        saved_position = (
            self.settings.popup_position
        )

        if saved_position is not None:
            saved_x, saved_y = (
                saved_position
            )

            screen = QApplication.screenAt(
                QPoint(
                    saved_x,
                    saved_y,
                )
            )

            if screen is not None:
                available = self.rect_from_qrect(
                    screen.availableGeometry()
                )

                x, y = clamp_popup_position(
                    saved_x,
                    saved_y,
                    self.width(),
                    self.height(),
                    available,
                )

                self.move(
                    x,
                    y,
                )

                return

        screen = fallback_screen

        if screen is None:
            screen = (
                QApplication.primaryScreen()
            )

        if screen is None:
            return

        available = self.rect_from_qrect(
            screen.availableGeometry()
        )

        x, y = center_popup(
            self.width(),
            self.height(),
            available,
        )

        self.move(
            x,
            y,
        )

    def current_qt_caret_rect(
        self,
    ) -> Rect | None:
        focus_widget = (
            QApplication.focusWidget()
        )

        if focus_widget is None:
            return None

        if (
            focus_widget is self
            or self.isAncestorOf(
                focus_widget
            )
        ):
            return None

        if isinstance(
            focus_widget,
            QLineEdit,
        ):
            cursor_rect = (
                focus_widget.cursorRect()
            )
        elif isinstance(
            focus_widget,
            QTextEdit,
        ):
            cursor_rect = (
                focus_widget.cursorRect()
            )
        elif isinstance(
            focus_widget,
            QPlainTextEdit,
        ):
            cursor_rect = (
                focus_widget.cursorRect()
            )
        else:
            return None

        global_top_left = (
            focus_widget.mapToGlobal(
                cursor_rect.topLeft()
            )
        )

        return Rect(
            x=global_top_left.x(),
            y=global_top_left.y(),
            width=cursor_rect.width(),
            height=cursor_rect.height(),
        )

    def rect_from_qrect(
        self,
        rect: QRect,
    ) -> Rect:
        return Rect(
            x=rect.x(),
            y=rect.y(),
            width=rect.width(),
            height=rect.height(),
        )

    # =============================
    # Selection
    # =============================

    def handle_copy(
        self,
        kaomoji: Kaomoji,
    ) -> None:
        self.copy_requested.emit(
            kaomoji
        )

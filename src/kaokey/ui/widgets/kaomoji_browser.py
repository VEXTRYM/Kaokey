from PySide6.QtCore import (
    QEvent,
    QObject,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QKeyEvent,
    QResizeEvent,
    QShowEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from kaokey.core.models import Kaomoji
from kaokey.ui.layout.responsive_layout import (
    columns_for_width,
)
from kaokey.ui.styling.style_constants import (
    GRID_DEFAULT_COLUMNS,
    GRID_SPACING,
    KAOMOJI_GRID_MIN_COLUMN_WIDTH,
    TOOLTIP_DURATION,
)
from kaokey.ui.styling.widget_styles import (
    style_kaomoji_button,
    style_kaomoji_filters_layout,
    style_kaomoji_grid,
    style_kaomoji_grid_scroll,
    style_kaomoji_main_tag_button,
    style_kaomoji_main_tags_layout,
    style_kaomoji_main_tags_scroll,
    style_kaomoji_search_input,
)
from kaokey.ui.widgets.kaomoji_button import (
    KaomojiButton,
)

KAOMOJI_REFRESH_DELAY_MS = 8


class KaomojiBrowser(QWidget):
    copy_requested = Signal(object)
    favorite_toggle_requested = Signal(object)

    # MainWindow uses this signal to stop
    # rotating help hints.
    interaction_started = Signal()

    def __init__(
        self,
        main_tags: list[str],
        kaomoji: list[Kaomoji],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.main_tags = main_tags
        self.kaomoji = kaomoji

        self.selected_main_tag: str | None = None

        # =========================
        # Keyboard navigation
        # =========================

        self.main_tag_buttons: list[QPushButton] = []

        self.kaomoji_buttons: list[KaomojiButton] = []

        self.kaomoji_sections: list[tuple[QLabel, list[KaomojiButton]]] = []

        self.kaomoji_rows: list[list[KaomojiButton]] = []

        self.kaomoji_button_cache: dict[int, KaomojiButton] = {}

        self.all_button: QPushButton | None = None

        self.refresh_timer = QTimer(self)

        self.refresh_timer.setSingleShot(True)

        self.refresh_timer.timeout.connect(self.apply_filters)

        self.grid_columns = GRID_DEFAULT_COLUMNS

        # =========================
        # Main layout
        # =========================

        layout = QVBoxLayout(self)

        # =========================
        # Search
        # =========================

        self.search_input = QLineEdit()

        style_kaomoji_search_input(self.search_input)

        layout.addWidget(self.search_input)

        # =========================
        # Filters
        # =========================

        filters_layout = QHBoxLayout()

        style_kaomoji_filters_layout(filters_layout)

        # =========================
        # Main tags
        # =========================

        self.main_tags_scroll_area = QScrollArea()

        style_kaomoji_main_tags_scroll(self.main_tags_scroll_area)

        filters_layout.addWidget(
            self.main_tags_scroll_area,
            1,
        )

        layout.addLayout(filters_layout)

        self.main_tag_group = QButtonGroup(self)

        self.main_tag_group.setExclusive(True)

        # =========================
        # Kaomoji grid
        # =========================

        self.grid_widget = QWidget()

        self.kaomoji_grid = QGridLayout(self.grid_widget)

        style_kaomoji_grid(self.kaomoji_grid)

        for column in range(self.grid_columns):
            self.kaomoji_grid.setColumnStretch(
                column,
                1,
            )

        self.scroll_area = QScrollArea()

        style_kaomoji_grid_scroll(self.scroll_area)

        self.scroll_area.setWidget(self.grid_widget)

        layout.addWidget(self.scroll_area)

        # =========================
        # Signals
        # =========================

        self.search_input.textChanged.connect(self.on_search_changed)

        # =========================
        # Initial content
        # =========================

        self.fill_main_tag_bar()
        self.apply_filters()

        # =========================
        # Global event filter
        # =========================
        #
        # We need to catch text input even
        # while one of the buttons has focus.
        #
        # The filter ignores events that do
        # not belong to this tab.

        app = QApplication.instance()

        if app is not None:
            app.installEventFilter(self)

        self.retranslate_ui()
        self.search_input.setFocus()

    # =============================
    # Responsive grid
    # =============================

    def resizeEvent(
        self,
        event: QResizeEvent,
    ) -> None:
        super().resizeEvent(event)

        self.update_grid_columns()

    def showEvent(
        self,
        event: QShowEvent,
    ) -> None:
        super().showEvent(event)

        # A hidden QScrollArea can report a placeholder viewport width
        # unrelated to the window that will actually contain it.
        # Wait until the browser is visible and Qt has completed the layout.
        QTimer.singleShot(
            0,
            self.update_grid_columns,
        )

    def update_grid_columns(
        self,
    ) -> None:
        if not self.isVisible():
            return

        viewport_width = self.scroll_area.viewport().width()

        if viewport_width <= 0:
            return

        columns = columns_for_width(
            viewport_width,
            KAOMOJI_GRID_MIN_COLUMN_WIDTH,
            GRID_SPACING,
        )

        if columns == self.grid_columns:
            return

        previous_columns = self.grid_columns
        self.grid_columns = columns

        for column in range(
            max(
                previous_columns,
                self.grid_columns,
            )
        ):
            self.kaomoji_grid.setColumnStretch(
                column,
                0,
            )

        for column in range(self.grid_columns):
            self.kaomoji_grid.setColumnStretch(
                column,
                1,
            )

        self.relayout_kaomoji_sections()

    def relayout_kaomoji_sections(
        self,
    ) -> None:
        # Remove current positions without
        # destroying widgets.
        for (
            label,
            buttons,
        ) in self.kaomoji_sections:
            self.kaomoji_grid.removeWidget(label)

            for button in buttons:
                self.kaomoji_grid.removeWidget(button)

        self.kaomoji_rows = []

        layout_row = 0

        for (
            label,
            buttons,
        ) in self.kaomoji_sections:
            # =========================
            # Section title
            # =========================

            self.kaomoji_grid.addWidget(
                label,
                layout_row,
                0,
                1,
                self.grid_columns,
            )

            layout_row += 1

            # =========================
            # Kaomoji rows
            # =========================

            for start in range(
                0,
                len(buttons),
                self.grid_columns,
            ):
                row_buttons = buttons[start : start + self.grid_columns]

                for (
                    column,
                    button,
                ) in enumerate(row_buttons):
                    self.kaomoji_grid.addWidget(
                        button,
                        layout_row,
                        column,
                    )

                self.kaomoji_rows.append(row_buttons)

                layout_row += 1

        self.kaomoji_grid.invalidate()
        self.kaomoji_grid.activate()

        self.grid_widget.updateGeometry()
        self.grid_widget.update()

        self.scroll_area.viewport().update()

    # =============================
    # Translation
    # =============================

    def retranslate_ui(
        self,
    ) -> None:
        self.search_input.setPlaceholderText(self.tr("Search kaomoji..."))

        if self.all_button is not None:
            self.all_button.setText(self.tr("All"))

    def changeEvent(
        self,
        event: QEvent,
    ) -> None:
        super().changeEvent(event)

        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()

    # =============================
    # Event filter
    # =============================

    def eventFilter(
        self,
        watched: QObject,
        event: QEvent,
    ) -> bool:
        # Keyboard navigation belongs to
        # whichever KaomojiBrowser is in
        # the currently active window.
        #
        # This matters later when the main
        # window and popup both contain a
        # browser at the same time.

        if not self.isVisible() or not self.window().isActiveWindow():
            return super().eventFilter(
                watched,
                event,
            )

        # =========================
        # Keyboard
        # =========================
        #
        # The event may belong to QTabBar,
        # QMainWindow, or another widget in
        # the active window. We intentionally
        # do not require watched to be a child
        # of this browser. That makes
        # "type to search" reliable.

        if event.type() == QEvent.Type.KeyPress and isinstance(
            event,
            QKeyEvent,
        ):
            if self.handle_key_press(event):
                return True

        # =========================
        # Mouse
        # =========================
        #
        # Mouse interaction counts only when
        # the click actually happened inside
        # this browser.

        if not isinstance(
            watched,
            QWidget,
        ):
            return super().eventFilter(
                watched,
                event,
            )

        belongs_to_browser = watched is self or self.isAncestorOf(watched)

        # =============================
        # Main tags wheel scrolling
        # =============================
        #
        # The horizontal scrollbar itself is
        # hidden, but the scroll area can still
        # be moved programmatically.
        belongs_to_main_tags = (
            watched is self.main_tags_scroll_area
            or self.main_tags_scroll_area.isAncestorOf(watched)
        )

        if (
            belongs_to_main_tags
            and event.type() == QEvent.Type.Wheel
            and isinstance(
                event,
                QWheelEvent,
            )
        ):
            scroll_bar = self.main_tags_scroll_area.horizontalScrollBar()

            # Touchpads can provide pixel-precise
            # scrolling.
            pixel_delta = event.pixelDelta()

            if not pixel_delta.isNull():
                if pixel_delta.x() != 0:
                    delta = pixel_delta.x()
                else:
                    delta = pixel_delta.y()

                scroll_bar.setValue(scroll_bar.value() - delta)

                event.accept()
                return True

            # Ordinary mouse wheels usually
            # provide angleDelta().
            angle_delta = event.angleDelta()

            if angle_delta.x() != 0:
                delta = angle_delta.x()
            else:
                delta = angle_delta.y()

            if delta != 0:
                steps = delta / 120

                scroll_bar.setValue(
                    scroll_bar.value() - int(steps * scroll_bar.singleStep() * 3)
                )

                event.accept()
                return True

        if belongs_to_browser and event.type() == QEvent.Type.MouseButtonPress:
            self.interaction_started.emit()

        return super().eventFilter(
            watched,
            event,
        )

    # =============================
    # Keyboard input
    # =============================

    def handle_key_press(
        self,
        event: QKeyEvent,
    ) -> bool:
        key = event.key()

        # =========================
        # Tab / Shift+Tab
        # =========================

        if key == Qt.Key.Key_Tab:
            self.interaction_started.emit()

            reverse = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)

            self.focus_adjacent_section(reverse=reverse)

            return True

        if key == Qt.Key.Key_Backtab:
            self.interaction_started.emit()

            self.focus_adjacent_section(reverse=True)

            return True

        # =========================
        # Enter
        # =========================

        if key in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            self.interaction_started.emit()

            self.activate_current_item()

            return True

        # =========================
        # Arrows
        # =========================

        if key in (
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
            Qt.Key.Key_Up,
            Qt.Key.Key_Down,
        ):
            section = self.get_current_section()

            # =========================
            # Search
            # =========================

            if section == "search":
                if key == Qt.Key.Key_Up:
                    return True

                if key == Qt.Key.Key_Down:
                    self.interaction_started.emit()

                    self.focus_section("tags")

                    return True

                # Left / Right keep their normal
                # text cursor behavior.
                return False

            # =========================
            # Main tags
            # =========================

            if section == "tags":
                if key == Qt.Key.Key_Left:
                    self.interaction_started.emit()

                    self.move_main_tag(-1)

                    return True

                if key == Qt.Key.Key_Right:
                    self.interaction_started.emit()

                    self.move_main_tag(1)

                    return True

                if key == Qt.Key.Key_Up:
                    self.interaction_started.emit()

                    self.focus_adjacent_section(reverse=True)

                    return True

                if key == Qt.Key.Key_Down:
                    self.interaction_started.emit()

                    self.focus_adjacent_section(reverse=False)

                    return True

            # =========================
            # Kaomoji
            # =========================

            if section == "kaomoji":
                self.interaction_started.emit()

                self.move_kaomoji(key)

                return True

            return False

        # =========================
        # Type to search
        # =========================

        modifiers = event.modifiers()

        blocked_modifiers = (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
        )

        if modifiers & blocked_modifiers:
            return False

        text = event.text()

        if text and text.isprintable():
            self.interaction_started.emit()

            # If Search already has focus,
            # let QLineEdit process the
            # original event normally.

            if self.search_input.hasFocus():
                return False

            # Otherwise move to Search and
            # insert THIS first character,
            # so it is not lost.

            self.search_input.setFocus()

            self.search_input.insert(text)

            return True

        return False

    # =============================
    # Sections
    # =============================

    def get_current_section(
        self,
    ) -> str | None:
        focus_widget = QApplication.focusWidget()

        if focus_widget is self.search_input:
            return "search"

        if focus_widget in self.main_tag_buttons:
            return "tags"

        if focus_widget in self.kaomoji_buttons:
            return "kaomoji"

        return None

    def get_available_sections(
        self,
    ) -> list[str]:
        sections = [
            "search",
        ]

        if self.main_tag_buttons:
            sections.append("tags")

        if self.kaomoji_buttons:
            sections.append("kaomoji")

        return sections

    def focus_adjacent_section(
        self,
        reverse: bool,
    ) -> None:
        sections = self.get_available_sections()

        current = self.get_current_section()

        if current not in sections:
            if reverse:
                self.focus_section(sections[-1])

            else:
                self.focus_section(sections[0])

            return

        index = sections.index(current)

        if reverse:
            index = (index - 1) % len(sections)

        else:
            index = (index + 1) % len(sections)

        self.focus_section(sections[index])

    def focus_section(
        self,
        section: str,
    ) -> None:
        if section == "search":
            self.search_input.setFocus()
            return

        if section == "tags":
            self.focus_main_tag(0)

            return

        if section == "kaomoji":
            self.focus_kaomoji(0)

    # =============================
    # Main tag keyboard navigation
    # =============================

    def focus_main_tag(
        self,
        index: int,
    ) -> None:
        if not self.main_tag_buttons:
            return

        index = max(
            0,
            min(
                index,
                len(self.main_tag_buttons) - 1,
            ),
        )

        button = self.main_tag_buttons[index]

        button.setFocus()

        self.main_tags_scroll_area.ensureWidgetVisible(button)

    def move_main_tag(
        self,
        direction: int,
    ) -> None:
        if not self.main_tag_buttons:
            return

        focus_widget = QApplication.focusWidget()

        if (
            isinstance(
                focus_widget,
                QPushButton,
            )
            and focus_widget in self.main_tag_buttons
        ):
            index = self.main_tag_buttons.index(focus_widget)

        else:
            index = 0

        self.focus_main_tag(index + direction)

    # =============================
    # Kaomoji keyboard navigation
    # =============================

    def focus_kaomoji(
        self,
        index: int,
    ) -> None:
        if not self.kaomoji_buttons:
            return

        index = max(
            0,
            min(
                index,
                len(self.kaomoji_buttons) - 1,
            ),
        )

        button = self.kaomoji_buttons[index]

        button.setFocus()

        self.scroll_area.ensureWidgetVisible(button)

    def move_kaomoji(
        self,
        key: int,
    ) -> None:
        if not self.kaomoji_rows:
            return

        focus_widget = QApplication.focusWidget()

        if not isinstance(
            focus_widget,
            KaomojiButton,
        ):
            self.focus_kaomoji(0)
            return

        current_row = -1
        current_column = -1

        # =============================
        # Current visual position
        # =============================

        for (
            row_index,
            row_buttons,
        ) in enumerate(self.kaomoji_rows):
            if focus_widget not in row_buttons:
                continue

            current_row = row_index

            current_column = row_buttons.index(focus_widget)

            break

        if current_row < 0:
            self.focus_kaomoji(0)
            return

        row_buttons = self.kaomoji_rows[current_row]

        # =============================
        # Left
        # =============================

        if key == Qt.Key.Key_Left:
            if current_column > 0:
                button = row_buttons[current_column - 1]

                button.setFocus()

                self.scroll_area.ensureWidgetVisible(button)

            return

        # =============================
        # Right
        # =============================

        if key == Qt.Key.Key_Right:
            if current_column + 1 < len(row_buttons):
                button = row_buttons[current_column + 1]

                button.setFocus()

                self.scroll_area.ensureWidgetVisible(button)

            return

        # =============================
        # Up
        # =============================

        if key == Qt.Key.Key_Up:
            if current_row == 0:
                self.focus_section("tags")
                return

            target_row = self.kaomoji_rows[current_row - 1]

            target_column = min(
                current_column,
                len(target_row) - 1,
            )

            button = target_row[target_column]

            button.setFocus()

            self.scroll_area.ensureWidgetVisible(button)

            return

        # =============================
        # Down
        # =============================

        if key == Qt.Key.Key_Down:
            if current_row + 1 >= len(self.kaomoji_rows):
                return

            target_row = self.kaomoji_rows[current_row + 1]

            target_column = min(
                current_column,
                len(target_row) - 1,
            )

            button = target_row[target_column]

            button.setFocus()

            self.scroll_area.ensureWidgetVisible(button)

    # =============================
    # Enter
    # =============================

    def activate_current_item(
        self,
    ) -> None:
        section = self.get_current_section()

        if section == "search":
            if self.kaomoji_buttons:
                self.focus_kaomoji(0)

            return

        focus_widget = QApplication.focusWidget()

        if section == "tags":
            if (
                isinstance(
                    focus_widget,
                    QPushButton,
                )
                and focus_widget in self.main_tag_buttons
            ):
                focus_widget.click()

            return

        if section == "kaomoji":
            if (
                isinstance(
                    focus_widget,
                    KaomojiButton,
                )
                and focus_widget in self.kaomoji_buttons
            ):
                focus_widget.click()

    # =============================
    # Data setters
    # =============================

    def set_main_tags(
        self,
        main_tags: list[str],
    ) -> None:
        self.main_tags = main_tags

        if self.selected_main_tag not in self.main_tags:
            self.selected_main_tag = None

        self.fill_main_tag_bar()
        self.apply_filters()

    def set_kaomoji(
        self,
        kaomoji: list[Kaomoji],
    ) -> None:
        self.kaomoji = kaomoji

        self.apply_filters()

    def refresh(
        self,
    ) -> None:
        self.request_refresh()

    # =============================
    # Main tags
    # =============================

    def fill_main_tag_bar(
        self,
    ) -> None:
        for button in self.main_tag_group.buttons():
            self.main_tag_group.removeButton(button)

        old_widget = self.main_tags_scroll_area.takeWidget()

        if old_widget is not None:
            old_widget.deleteLater()

        self.main_tag_buttons = []

        self.main_tags_widget = QWidget()

        self.main_tags_layout = QHBoxLayout(self.main_tags_widget)

        style_kaomoji_main_tags_layout(self.main_tags_layout)

        # =========================
        # All
        # =========================

        all_button = QPushButton()

        self.all_button = all_button

        style_kaomoji_main_tag_button(all_button)

        all_button.setText(self.tr("All"))

        all_button.setCheckable(True)

        self.main_tag_group.addButton(all_button)

        self.main_tag_buttons.append(all_button)

        if self.selected_main_tag is None:
            all_button.setChecked(True)

        all_button.clicked.connect(lambda checked=False: self.select_main_tag(None))

        self.main_tags_layout.addWidget(all_button)

        # =========================
        # Tags
        # =========================

        for tag in self.main_tags:
            button = QPushButton(tag)

            style_kaomoji_main_tag_button(button)

            button.setCheckable(True)

            self.main_tag_group.addButton(button)

            self.main_tag_buttons.append(button)

            if tag == self.selected_main_tag:
                button.setChecked(True)

            button.clicked.connect(
                lambda checked=False, item=tag: self.select_main_tag(item)
            )

            self.main_tags_layout.addWidget(button)

        self.main_tags_widget.adjustSize()

        self.main_tags_scroll_area.setWidget(self.main_tags_widget)

    def select_main_tag(
        self,
        tag: str | None,
    ) -> None:
        # Clicking the already active ordinary
        # tag turns that filter off and returns
        # selection to All.
        if tag is not None and tag == self.selected_main_tag:
            self.selected_main_tag = None

            assert self.all_button is not None

            self.all_button.setChecked(True)

        else:
            self.selected_main_tag = tag

        self.request_refresh()

    # =============================
    # Filters
    # =============================

    def on_search_changed(
        self,
        _text: str,
    ) -> None:
        self.request_refresh()

    def request_refresh(self) -> None:
        if self.refresh_timer.isActive():
            return

        self.refresh_timer.start(KAOMOJI_REFRESH_DELAY_MS)

    def apply_filters(
        self,
    ) -> None:
        search_text = self.search_input.text().lower()

        filtered_kaomoji: list[Kaomoji] = []

        for kaomoji in self.kaomoji:
            tags = kaomoji.get(
                "tags",
                [],
            )

            searchable_text = " ".join(
                [
                    kaomoji.get(
                        "name",
                        "",
                    ),
                    kaomoji["text"],
                    *tags,
                ]
            ).lower()

            matches_search = search_text in searchable_text

            matches_main_tag = (
                self.selected_main_tag is None or self.selected_main_tag in tags
            )

            if matches_search and matches_main_tag:
                filtered_kaomoji.append(kaomoji)

        sections = self.group_kaomoji(filtered_kaomoji)

        self.fill_kaomoji_grid(sections)

    # =============================
    # Grid
    # =============================

    def fill_kaomoji_grid(
        self,
        sections: list[
            tuple[
                str,
                str | None,
                list[Kaomoji],
            ]
        ],
    ) -> None:
        scrollbar = self.scroll_area.verticalScrollBar()

        scroll_value = scrollbar.value()

        # =============================
        # Visible items
        # =============================

        kaomoji_items = [
            kaomoji
            for (
                _section_type,
                _tag,
                items,
            ) in sections
            for kaomoji in items
        ]

        visible_ids = {id(kaomoji) for kaomoji in kaomoji_items}

        active_ids = {id(kaomoji) for kaomoji in self.kaomoji}

        # =============================
        # Remove previous sections
        # =============================

        for (
            label,
            buttons,
        ) in self.kaomoji_sections:
            self.kaomoji_grid.removeWidget(label)

            label.deleteLater()

            for button in buttons:
                self.kaomoji_grid.removeWidget(button)

        self.kaomoji_sections = []
        self.kaomoji_rows = []

        # =============================
        # Remove deleted kaomoji
        # =============================

        for key in list(self.kaomoji_button_cache):
            if key in active_ids:
                continue

            button = self.kaomoji_button_cache.pop(key)

            button.hide()
            button.deleteLater()

        # =============================
        # Hide filtered kaomoji
        # =============================

        for (
            key,
            button,
        ) in self.kaomoji_button_cache.items():
            if key not in visible_ids:
                button.hide()

        visible_buttons: list[KaomojiButton] = []

        # =============================
        # Build sections
        # =============================

        for (
            section_type,
            tag,
            items,
        ) in sections:
            label = QLabel(
                self.get_kaomoji_section_title(
                    section_type,
                    tag,
                ),
                self.grid_widget,
            )

            section_buttons: list[KaomojiButton] = []

            for kaomoji in items:
                key = id(kaomoji)

                button = self.kaomoji_button_cache.get(key)

                if button is None:
                    button = KaomojiButton(
                        kaomoji["text"],
                        self.grid_widget,
                    )

                    button.setToolTipDuration(TOOLTIP_DURATION)

                    button.clicked.connect(
                        lambda checked=False, item=kaomoji: self.copy_requested.emit(
                            item
                        )
                    )

                    button.right_clicked.connect(
                        lambda item=kaomoji: self.favorite_toggle_requested.emit(item)
                    )

                    self.kaomoji_button_cache[key] = button

                if button.text() != kaomoji["text"]:
                    button.setText(kaomoji["text"])

                button.setToolTip(kaomoji["text"])

                style_kaomoji_button(
                    button,
                    kaomoji.get(
                        "favorite",
                        False,
                    ),
                )

                if button.isHidden():
                    button.show()

                section_buttons.append(button)

                visible_buttons.append(button)

            self.kaomoji_sections.append(
                (
                    label,
                    section_buttons,
                )
            )

        self.kaomoji_buttons = visible_buttons

        self.relayout_kaomoji_sections()

        scrollbar.setValue(
            min(
                scroll_value,
                scrollbar.maximum(),
            )
        )

    # kaomoji display

    def get_kaomoji_section(
        self,
        kaomoji: Kaomoji,
    ) -> tuple[str, str | None]:
        # Favorites always wins.
        if kaomoji.get(
            "favorite",
            False,
        ):
            return (
                "favorites",
                None,
            )

        tags = kaomoji.get(
            "tags",
            [],
        )

        # Find the first main tag in the
        # kaomoji's OWN tag order.
        main_tags = set(self.main_tags)

        for tag in tags:
            if tag in main_tags:
                return (
                    "tag",
                    tag,
                )

        # No main tags: use the first
        # ordinary tag.
        if tags:
            return (
                "tag",
                tags[0],
            )

        return (
            "untagged",
            None,
        )

    def group_kaomoji(
        self,
        kaomoji_items: list[Kaomoji],
    ) -> list[
        tuple[
            str,
            str | None,
            list[Kaomoji],
        ]
    ]:
        groups: dict[
            tuple[str, str | None],
            list[Kaomoji],
        ] = {}

        for kaomoji in kaomoji_items:
            section = self.get_kaomoji_section(kaomoji)

            groups.setdefault(
                section,
                [],
            ).append(kaomoji)

        sections: list[
            tuple[
                str,
                str | None,
                list[Kaomoji],
            ]
        ] = []

        # =============================
        # Favorites
        # =============================

        favorites_key = (
            "favorites",
            None,
        )

        favorites = groups.pop(
            favorites_key,
            None,
        )

        if favorites:
            favorites.sort(
                key=lambda kaomoji: kaomoji.get(
                    "favorite_order",
                    0,
                )
            )

            sections.append(
                (
                    "favorites",
                    None,
                    favorites,
                )
            )

        # =============================
        # Main tags
        # =============================
        #
        # HERE self.main_tags order
        # controls SECTION ORDER.
        #

        for main_tag in self.main_tags:
            key = (
                "tag",
                main_tag,
            )

            items = groups.pop(
                key,
                None,
            )

            if items:
                sections.append(
                    (
                        "tag",
                        main_tag,
                        items,
                    )
                )

        # =============================
        # Other tags
        # =============================

        other_tags = [
            tag
            for section_type, tag in groups
            if (section_type == "tag" and tag is not None)
        ]

        other_tags.sort(
            key=lambda tag: (
                tag.casefold(),
                tag,
            )
        )

        for tag in other_tags:
            key = (
                "tag",
                tag,
            )

            items = groups.pop(key)

            sections.append(
                (
                    "tag",
                    tag,
                    items,
                )
            )

        # =============================
        # Untagged
        # =============================

        untagged = groups.pop(
            (
                "untagged",
                None,
            ),
            None,
        )

        if untagged:
            sections.append(
                (
                    "untagged",
                    None,
                    untagged,
                )
            )

        return sections

    def get_kaomoji_section_title(
        self,
        section_type: str,
        tag: str | None,
    ) -> str:
        if section_type == "favorites":
            return self.tr("Favorites")

        if section_type == "untagged":
            return self.tr("Untagged")

        assert tag is not None

        return tag

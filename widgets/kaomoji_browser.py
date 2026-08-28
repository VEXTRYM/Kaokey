from PySide6.QtCore import (
    QEvent,
    QObject,
    QTimer,
    Qt,
    Signal,
)

from PySide6.QtGui import (
    QKeyEvent,
    QResizeEvent,
    QShowEvent,
)

from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from models import Kaomoji

from style_constants import (
    GRID_DEFAULT_COLUMNS,
    GRID_SPACING,
    KAOMOJI_GRID_MIN_COLUMN_WIDTH,
    TOOLTIP_DURATION,
)

from responsive_layout import (
    columns_for_width,
)

from widget_styles import (
    style_favorites_button,
    style_kaomoji_button,
    style_kaomoji_filters_layout,
    style_kaomoji_grid,
    style_kaomoji_grid_scroll,
    style_kaomoji_main_tag_button,
    style_kaomoji_main_tags_layout,
    style_kaomoji_main_tags_scroll,
    style_kaomoji_search_input,
)

from widgets.kaomoji_button import (
    KaomojiButton,
)


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
        super().__init__(
            parent
        )

        self.main_tags = main_tags
        self.kaomoji = kaomoji

        self.selected_main_tag: (
            str | None
        ) = None

        # =========================
        # Keyboard navigation
        # =========================

        self.main_tag_buttons: list[
            QPushButton
        ] = []

        self.kaomoji_buttons: list[
            KaomojiButton
        ] = []

        self.all_button: QPushButton | None = None

        self.grid_columns = (
            GRID_DEFAULT_COLUMNS
        )

        # =========================
        # Main layout
        # =========================

        layout = QVBoxLayout(
            self
        )

        # =========================
        # Search
        # =========================

        self.search_input = QLineEdit()

        style_kaomoji_search_input(
            self.search_input
        )

        layout.addWidget(
            self.search_input
        )

        # =========================
        # Filters
        # =========================

        filters_layout = QHBoxLayout()

        style_kaomoji_filters_layout(
            filters_layout
        )

        self.favorites_button = QPushButton(
            "★"
        )

        self.favorites_button.setCheckable(
            True
        )

        style_favorites_button(
            self.favorites_button
        )

        filters_layout.addWidget(
            self.favorites_button
        )

        # =========================
        # Main tags
        # =========================

        self.main_tags_scroll_area = (
            QScrollArea()
        )

        style_kaomoji_main_tags_scroll(
            self.main_tags_scroll_area
        )

        filters_layout.addWidget(
            self.main_tags_scroll_area,
            1,
        )

        layout.addLayout(
            filters_layout
        )

        self.main_tag_group = QButtonGroup(
            self
        )

        self.main_tag_group.setExclusive(
            True
        )

        # =========================
        # Kaomoji grid
        # =========================

        self.grid_widget = QWidget()

        self.kaomoji_grid = QGridLayout(
            self.grid_widget
        )

        style_kaomoji_grid(
            self.kaomoji_grid
        )

        for column in range(
            self.grid_columns
        ):
            self.kaomoji_grid.setColumnStretch(
                column,
                1,
            )

        self.scroll_area = QScrollArea()

        style_kaomoji_grid_scroll(
            self.scroll_area
        )

        self.scroll_area.setWidget(
            self.grid_widget
        )

        layout.addWidget(
            self.scroll_area
        )

        # =========================
        # Signals
        # =========================

        self.search_input.textChanged.connect(
            self.on_search_changed
        )

        self.favorites_button.toggled.connect(
            self.on_favorites_toggled
        )

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
            app.installEventFilter(
                self
            )

        self.retranslate_ui()
        self.search_input.setFocus()

    # =============================
    # Responsive grid
    # =============================

    def resizeEvent(
        self,
        event: QResizeEvent,
    ) -> None:
        super().resizeEvent(
            event
        )

        self.update_grid_columns()

    def showEvent(
        self,
        event: QShowEvent,
    ) -> None:
        super().showEvent(
            event
        )

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

        viewport_width = (
            self.scroll_area.viewport().width()
        )

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

        for column in range(
            self.grid_columns
        ):
            self.kaomoji_grid.setColumnStretch(
                column,
                1,
            )

        self.relayout_kaomoji_buttons()

    def relayout_kaomoji_buttons(
        self,
    ) -> None:
        for button in self.kaomoji_buttons:
            self.kaomoji_grid.removeWidget(
                button
            )

        for index, button in enumerate(
            self.kaomoji_buttons
        ):
            row = (
                index
                // self.grid_columns
            )

            column = (
                index
                % self.grid_columns
            )

            self.kaomoji_grid.addWidget(
                button,
                row,
                column,
            )

    # =============================
    # Translation
    # =============================

    def retranslate_ui(
        self,
    ) -> None:
        self.search_input.setPlaceholderText(
            self.tr("Search kaomoji...")
        )

        if self.all_button is not None:
            self.all_button.setText(
                self.tr("All")
            )

    def changeEvent(
        self,
        event: QEvent,
    ) -> None:
        super().changeEvent(
            event
        )

        if (
            event.type()
            == QEvent.Type.LanguageChange
        ):
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

        if (
            not self.isVisible()
            or not self.window().isActiveWindow()
        ):
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

        if (
            event.type()
            == QEvent.Type.KeyPress
            and isinstance(
                event,
                QKeyEvent,
            )
        ):
            if self.handle_key_press(
                event
            ):
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

        belongs_to_browser = (
            watched is self
            or self.isAncestorOf(
                watched
            )
        )

        if (
            belongs_to_browser
            and event.type()
            == QEvent.Type.MouseButtonPress
        ):
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

        if (
            key
            == Qt.Key.Key_Tab
        ):
            self.interaction_started.emit()

            reverse = bool(
                event.modifiers()
                & Qt.KeyboardModifier.ShiftModifier
            )

            self.focus_adjacent_section(
                reverse=reverse
            )

            return True

        if (
            key
            == Qt.Key.Key_Backtab
        ):
            self.interaction_started.emit()

            self.focus_adjacent_section(
                reverse=True
            )

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
            section = (
                self.get_current_section()
            )

            if section == "tags":
                if key == Qt.Key.Key_Left:
                    self.interaction_started.emit()

                    self.move_main_tag(
                        -1
                    )

                    return True

                if key == Qt.Key.Key_Right:
                    self.interaction_started.emit()

                    self.move_main_tag(
                        1
                    )

                    return True

            elif section == "kaomoji":
                self.interaction_started.emit()

                self.move_kaomoji(
                    key
                )

                return True

            # Search keeps normal arrow
            # behavior for moving the text
            # cursor.

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

        if (
            text
            and text.isprintable()
        ):
            self.interaction_started.emit()

            # If Search already has focus,
            # let QLineEdit process the
            # original event normally.

            if (
                self.search_input
                .hasFocus()
            ):
                return False

            # Otherwise move to Search and
            # insert THIS first character,
            # so it is not lost.

            self.search_input.setFocus()

            self.search_input.insert(
                text
            )

            return True

        return False

    # =============================
    # Sections
    # =============================

    def get_current_section(
        self,
    ) -> str | None:
        focus_widget = (
            QApplication.focusWidget()
        )

        if (
            focus_widget
            is self.search_input
        ):
            return "search"

        if (
            focus_widget
            is self.favorites_button
        ):
            return "favorites"

        if (
            focus_widget
            in self.main_tag_buttons
        ):
            return "tags"

        if (
            focus_widget
            in self.kaomoji_buttons
        ):
            return "kaomoji"

        return None

    def get_available_sections(
        self,
    ) -> list[str]:
        sections = [
            "search",
            "favorites",
        ]

        if self.main_tag_buttons:
            sections.append(
                "tags"
            )

        if self.kaomoji_buttons:
            sections.append(
                "kaomoji"
            )

        return sections

    def focus_adjacent_section(
        self,
        reverse: bool,
    ) -> None:
        sections = (
            self.get_available_sections()
        )

        current = (
            self.get_current_section()
        )

        if current not in sections:
            if reverse:
                self.focus_section(
                    sections[-1]
                )

            else:
                self.focus_section(
                    sections[0]
                )

            return

        index = sections.index(
            current
        )

        if reverse:
            index = (
                index - 1
            ) % len(sections)

        else:
            index = (
                index + 1
            ) % len(sections)

        self.focus_section(
            sections[index]
        )

    def focus_section(
        self,
        section: str,
    ) -> None:
        if section == "search":
            self.search_input.setFocus()
            return

        if section == "favorites":
            self.favorites_button.setFocus()
            return

        if section == "tags":
            self.focus_main_tag(
                0
            )

            return

        if section == "kaomoji":
            self.focus_kaomoji(
                0
            )

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

        button = self.main_tag_buttons[
            index
        ]

        button.setFocus()

        self.main_tags_scroll_area.ensureWidgetVisible(
            button
        )

    def move_main_tag(
        self,
        direction: int,
    ) -> None:
        if not self.main_tag_buttons:
            return

        focus_widget = (
            QApplication.focusWidget()
        )

        if (
            isinstance(
                focus_widget,
                QPushButton,
            )
            and focus_widget
            in self.main_tag_buttons
        ):
            index = (
                self.main_tag_buttons
                .index(
                    focus_widget
                )
            )

        else:
            index = 0

        self.focus_main_tag(
            index + direction
        )

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
                len(
                    self.kaomoji_buttons
                )
                - 1,
            ),
        )

        button = (
            self.kaomoji_buttons[
                index
            ]
        )

        button.setFocus()

        self.scroll_area.ensureWidgetVisible(
            button
        )

    def move_kaomoji(
        self,
        key: int,
    ) -> None:
        if not self.kaomoji_buttons:
            return

        focus_widget = (
            QApplication.focusWidget()
        )

        if (
            isinstance(
                focus_widget,
                KaomojiButton,
            )
            and focus_widget
            in self.kaomoji_buttons
        ):
            index = (
                self.kaomoji_buttons
                .index(
                    focus_widget
                )
            )

        else:
            index = 0

        column = (
            index
            % self.grid_columns
        )

        new_index = index

        if (
            key
            == Qt.Key.Key_Left
        ):
            if column > 0:
                new_index = (
                    index - 1
                )

        elif (
            key
            == Qt.Key.Key_Right
        ):
            if (
                column
                < self.grid_columns - 1
                and index + 1
                < len(
                    self.kaomoji_buttons
                )
            ):
                new_index = (
                    index + 1
                )

        elif (
            key
            == Qt.Key.Key_Up
        ):
            candidate = (
                index
                - self.grid_columns
            )

            if candidate >= 0:
                new_index = (
                    candidate
                )

        elif (
            key
            == Qt.Key.Key_Down
        ):
            candidate = (
                index
                + self.grid_columns
            )

            if candidate < len(
                self.kaomoji_buttons
            ):
                new_index = (
                    candidate
                )

        if new_index != index:
            self.focus_kaomoji(
                new_index
            )

    # =============================
    # Enter
    # =============================

    def activate_current_item(
        self,
    ) -> None:
        section = (
            self.get_current_section()
        )

        if section == "search":
            if self.kaomoji_buttons:
                self.focus_kaomoji(
                    0
                )

            return

        if section == "favorites":
            self.favorites_button.click()
            return

        focus_widget = (
            QApplication.focusWidget()
        )

        if section == "tags":
            if (
                isinstance(
                    focus_widget,
                    QPushButton,
                )
                and focus_widget
                in self.main_tag_buttons
            ):
                focus_widget.click()

            return

        if section == "kaomoji":
            if (
                isinstance(
                    focus_widget,
                    KaomojiButton,
                )
                and focus_widget
                in self.kaomoji_buttons
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

        if (
            self.selected_main_tag
            not in self.main_tags
        ):
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
        self.apply_filters()

    # =============================
    # Main tags
    # =============================

    def fill_main_tag_bar(
        self,
    ) -> None:
        for button in (
            self.main_tag_group.buttons()
        ):
            self.main_tag_group.removeButton(
                button
            )

        old_widget = (
            self.main_tags_scroll_area
            .takeWidget()
        )

        if old_widget is not None:
            old_widget.deleteLater()

        self.main_tag_buttons = []

        self.main_tags_widget = QWidget()

        self.main_tags_layout = QHBoxLayout(
            self.main_tags_widget
        )

        style_kaomoji_main_tags_layout(
            self.main_tags_layout
        )

        # =========================
        # All
        # =========================

        all_button = QPushButton()

        self.all_button = all_button

        style_kaomoji_main_tag_button(
            all_button
        )

        all_button.setText(
            self.tr("All")
        )

        all_button.setCheckable(
            True
        )

        self.main_tag_group.addButton(
            all_button
        )

        self.main_tag_buttons.append(
            all_button
        )

        if (
            self.selected_main_tag
            is None
        ):
            all_button.setChecked(
                True
            )

        all_button.clicked.connect(
            lambda checked=False:
                self.select_main_tag(
                    None
                )
        )

        self.main_tags_layout.addWidget(
            all_button
        )

        # =========================
        # Tags
        # =========================

        for tag in self.main_tags:
            button = QPushButton(
                tag
            )

            style_kaomoji_main_tag_button(
                button
            )

            button.setCheckable(
                True
            )

            self.main_tag_group.addButton(
                button
            )

            self.main_tag_buttons.append(
                button
            )

            if (
                tag
                == self.selected_main_tag
            ):
                button.setChecked(
                    True
                )

            button.clicked.connect(
                lambda checked=False, item=tag:
                    self.select_main_tag(
                        item
                    )
            )

            self.main_tags_layout.addWidget(
                button
            )

        self.main_tags_widget.adjustSize()

        self.main_tags_scroll_area.setWidget(
            self.main_tags_widget
        )

    def select_main_tag(
        self,
        tag: str | None,
    ) -> None:
        # Clicking the already active ordinary
        # tag turns that filter off and returns
        # selection to All.
        if (
            tag is not None
            and tag == self.selected_main_tag
        ):
            self.selected_main_tag = None

            assert self.all_button is not None

            self.all_button.setChecked(
                True
            )

        else:
            self.selected_main_tag = tag

        self.apply_filters()

    # =============================
    # Filters
    # =============================

    def on_search_changed(
        self,
        _text: str,
    ) -> None:
        self.apply_filters()

    def on_favorites_toggled(
        self,
        _checked: bool,
    ) -> None:
        self.apply_filters()

    def apply_filters(
        self,
    ) -> None:
        search_text = (
            self.search_input
            .text()
            .lower()
        )

        filtered_kaomoji: list[
            Kaomoji
        ] = []

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

            matches_search = (
                search_text
                in searchable_text
            )

            matches_favorite = (
                not self.favorites_button
                .isChecked()
                or kaomoji.get(
                    "favorite",
                    False,
                )
            )

            matches_main_tag = (
                self.selected_main_tag
                is None
                or self.selected_main_tag
                in tags
            )

            if (
                matches_search
                and matches_favorite
                and matches_main_tag
            ):
                filtered_kaomoji.append(
                    kaomoji
                )

        favorites = [
            kaomoji
            for kaomoji
            in filtered_kaomoji
            if kaomoji.get(
                "favorite",
                False,
            )
        ]

        non_favorites = [
            kaomoji
            for kaomoji
            in filtered_kaomoji
            if not kaomoji.get(
                "favorite",
                False,
            )
        ]

        favorites.sort(
            key=lambda kaomoji:
                kaomoji.get(
                    "favorite_order",
                    0,
                )
        )

        self.fill_kaomoji_grid(
            favorites
            + non_favorites
        )

    # =============================
    # Grid
    # =============================

    def fill_kaomoji_grid(
        self,
        kaomoji_items: list[Kaomoji],
    ) -> None:
        while self.kaomoji_grid.count():
            layout_item = (
                self.kaomoji_grid
                .takeAt(0)
            )

            if layout_item is None:
                continue

            widget = (
                layout_item.widget()
            )

            if widget is not None:
                widget.deleteLater()

        self.kaomoji_buttons = []

        for index, kaomoji in enumerate(
            kaomoji_items
        ):
            button = KaomojiButton(
                kaomoji["text"]
            )

            button.setToolTip(
                kaomoji["text"]
            )

            button.setToolTipDuration(
                TOOLTIP_DURATION
            )

            style_kaomoji_button(
                button,
                kaomoji.get(
                    "favorite",
                    False,
                ),
            )

            button.clicked.connect(
                lambda checked=False, item=kaomoji:
                    self.copy_requested.emit(
                        item
                    )
            )

            button.right_clicked.connect(
                lambda item=kaomoji:
                    self.favorite_toggle_requested.emit(
                        item
                    )
            )

            self.kaomoji_buttons.append(
                button
            )

            row = (
                index
                // self.grid_columns
            )

            column = (
                index
                % self.grid_columns
            )

            self.kaomoji_grid.addWidget(
                button,
                row,
                column,
            )


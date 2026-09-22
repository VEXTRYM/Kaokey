from PySide6.QtCore import (
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QKeyEvent,
    QResizeEvent,
    QShowEvent,
    QTextCursor,
    QTextOption,
)
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from kaokey.core.models import KaomojiInput
from kaokey.core.validators import parse_tags
from kaokey.ui.layout.responsive_layout import (
    columns_for_width,
)
from kaokey.ui.styling.style_constants import (
    CONSTRUCTOR_GRID_COLUMNS,
    CONSTRUCTOR_GRID_SPACING,
    CONSTRUCTOR_SYMBOL_BUTTON_WIDTH,
)
from kaokey.ui.styling.widget_styles import (
    style_constructor_content_layout,
    style_constructor_scroll,
    style_constructor_symbol_button,
    style_constructor_symbol_grid,
    style_unicode_text,
)


class ConstructorTab(QWidget):
    submit_requested = Signal(object)
    cancel_edit_requested = Signal()

    def __init__(
        self,
        categories: dict[str, list[str]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.categories = categories
        self.edit_mode = False

        # =========================
        # Main layout
        # =========================

        layout = QVBoxLayout(self)

        # =========================
        # Name
        # =========================

        self.name_input = QLineEdit()

        self.name_input.setPlaceholderText("Name (Optional)")

        layout.addWidget(self.name_input)

        # =========================
        # Tags
        # =========================

        self.tags_input = QLineEdit()

        self.tags_input.setPlaceholderText("Tags: cute, happy, cat")

        layout.addWidget(self.tags_input)

        # =========================
        # Kaomoji + actions
        # =========================

        kaomoji_layout = QHBoxLayout()

        self.kaomoji_input = KaomojiTextEdit()

        self.kaomoji_input.setPlaceholderText("Build your kaomoji...")

        text_option = self.kaomoji_input.document().defaultTextOption()

        text_option.setTextDirection(Qt.LayoutDirection.LeftToRight)

        text_option.setWrapMode(QTextOption.WrapMode.NoWrap)

        self.kaomoji_input.document().setDefaultTextOption(text_option)

        self.kaomoji_input.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.kaomoji_input.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.kaomoji_input.setFixedHeight(self.name_input.sizeHint().height())

        style_unicode_text(self.kaomoji_input)

        self.clear_button = QPushButton("Clear")

        self.submit_button = QPushButton("Add")

        kaomoji_layout.addWidget(
            self.kaomoji_input,
            1,
        )

        kaomoji_layout.addWidget(self.clear_button)

        kaomoji_layout.addWidget(self.submit_button)

        layout.addLayout(kaomoji_layout)

        # =========================
        # Symbol palette
        # =========================

        self.symbol_grid_columns = CONSTRUCTOR_GRID_COLUMNS

        self.symbol_grids: list[
            tuple[
                QGridLayout,
                list[QPushButton],
            ]
        ] = []

        self.symbols_widget = QWidget()

        self.symbols_layout = QVBoxLayout(self.symbols_widget)

        style_constructor_content_layout(self.symbols_layout)

        self.symbols_scroll_area = QScrollArea()

        style_constructor_scroll(self.symbols_scroll_area)

        self.symbols_scroll_area.setWidget(self.symbols_widget)

        layout.addWidget(
            self.symbols_scroll_area,
            1,
        )

        # =========================
        # Signals
        # =========================

        self.clear_button.clicked.connect(self.handle_clear_button)

        self.submit_button.clicked.connect(self.request_submit)

        # =========================
        # Palette
        # =========================

        self.fill_symbol_palette()

    # =============================
    # Symbol palette
    # =============================

    def fill_symbol_palette(
        self,
    ) -> None:
        for category, symbols in self.categories.items():
            category_label = QLabel(category)

            self.symbols_layout.addWidget(category_label)

            grid_widget = QWidget()

            grid_layout = QGridLayout(grid_widget)

            style_constructor_symbol_grid(grid_layout)

            buttons: list[QPushButton] = []

            for index, symbol in enumerate(symbols):
                button = QPushButton(symbol)

                button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

                style_constructor_symbol_button(button)

                button.clicked.connect(
                    lambda checked=False, item=symbol: self.insert_symbol(item)
                )

                row = index // self.symbol_grid_columns
                column = index % self.symbol_grid_columns

                grid_layout.addWidget(
                    button,
                    row,
                    column,
                )

                buttons.append(button)

            self.symbol_grids.append(
                (
                    grid_layout,
                    buttons,
                )
            )

            self.symbols_layout.addWidget(grid_widget)

    # =============================
    # Symbol editing
    # =============================

    def insert_symbol(
        self,
        symbol: str,
    ) -> None:
        self.kaomoji_input.insertPlainText(symbol)

        self.kaomoji_input.setFocus()

    # =============================
    # Clear / Cancel
    # =============================

    def handle_clear_button(
        self,
    ) -> None:
        if self.edit_mode:
            self.cancel_edit_requested.emit()
            return

        self.kaomoji_input.clear()

        self.kaomoji_input.setFocus()

    # =============================
    # Edit mode
    # =============================

    def load_for_edit(
        self,
        data: KaomojiInput,
    ) -> None:
        self.edit_mode = True

        self.name_input.setText(data["name"])

        self.tags_input.setText(", ".join(data["tags"]))

        self.kaomoji_input.setPlainText(data["text"])

        # self.force_kaomoji_input_ltr()

        self.clear_button.setText("Cancel")

        self.submit_button.setText("Edit")

        self.kaomoji_input.setFocus()

        cursor = self.kaomoji_input.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.kaomoji_input.setTextCursor(cursor)

    # =============================
    # Reset
    # =============================

    def reset_form(
        self,
    ) -> None:
        self.edit_mode = False

        self.name_input.clear()
        self.tags_input.clear()
        self.kaomoji_input.clear()

        self.clear_button.setText("Clear")

        self.submit_button.setText("Add")

        self.kaomoji_input.setFocus()

    # =============================
    # Submit
    # =============================

    def request_submit(
        self,
    ) -> None:
        data: KaomojiInput = {
            "name": (self.name_input.text().strip()),
            "text": (self.kaomoji_input.toPlainText().strip()),
            "tags": parse_tags(self.tags_input.text()),
        }

        self.submit_requested.emit(data)

    # Responsive grid logic

    def resizeEvent(
        self,
        event: QResizeEvent,
    ) -> None:
        super().resizeEvent(event)

        self.update_symbol_grid_columns()

    def showEvent(
        self,
        event: QShowEvent,
    ) -> None:
        super().showEvent(event)

        QTimer.singleShot(
            0,
            self.update_symbol_grid_columns,
        )

    def update_symbol_grid_columns(
        self,
    ) -> None:
        if not self.isVisible():
            return

        viewport_width = self.symbols_scroll_area.viewport().width()

        if viewport_width <= 0:
            return

        content_margins = self.symbols_layout.contentsMargins()

        available_width = (
            viewport_width - content_margins.left() - content_margins.right()
        )

        if self.symbol_grids:
            grid_margins = self.symbol_grids[0][0].contentsMargins()

            available_width -= grid_margins.left() + grid_margins.right()

        columns = columns_for_width(
            available_width,
            CONSTRUCTOR_SYMBOL_BUTTON_WIDTH,
            CONSTRUCTOR_GRID_SPACING,
        )

        if columns == self.symbol_grid_columns:
            return

        self.symbol_grid_columns = columns

        self.relayout_symbol_buttons()

    def relayout_symbol_buttons(
        self,
    ) -> None:
        for grid_layout, buttons in self.symbol_grids:
            for button in buttons:
                grid_layout.removeWidget(button)

            for index, button in enumerate(buttons):
                row = index // self.symbol_grid_columns
                column = index % self.symbol_grid_columns

                grid_layout.addWidget(
                    button,
                    row,
                    column,
                )

            grid_layout.invalidate()
            grid_layout.activate()


class KaomojiTextEdit(QPlainTextEdit):
    def keyPressEvent(
        self,
        event: QKeyEvent,
    ) -> None:
        if event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            return

        super().keyPressEvent(event)

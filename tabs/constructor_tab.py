from PySide6.QtCore import (
    Qt,
    Signal,
)

from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from widget_styles import (
    style_constructor_content_layout,
    style_constructor_scroll,
    style_constructor_symbol_button,
    style_constructor_symbol_grid,
    style_unicode_text,
)

from models import KaomojiInput

from style_constants import (
    CONSTRUCTOR_GRID_COLUMNS,
)

from validators import parse_tags


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

        self.name_input.setPlaceholderText(
            "Optional name"
        )

        layout.addWidget(
            self.name_input
        )

        # =========================
        # Tags
        # =========================

        self.tags_input = QLineEdit()

        self.tags_input.setPlaceholderText(
            "Tags: cute, happy, cat"
        )

        layout.addWidget(
            self.tags_input
        )

        # =========================
        # Kaomoji + actions
        # =========================

        kaomoji_layout = QHBoxLayout()

        self.kaomoji_input = QLineEdit()

        self.kaomoji_input.setPlaceholderText(
            "Build your kaomoji..."
        )

        style_unicode_text(
            self.kaomoji_input
        )

        self.kaomoji_input.textChanged.connect(
            self.update_kaomoji_input_font
        )

        self.clear_button = QPushButton(
            "Clear"
        )

        self.submit_button = QPushButton(
            "Add"
        )

        kaomoji_layout.addWidget(
            self.kaomoji_input,
            1,
        )

        kaomoji_layout.addWidget(
            self.clear_button
        )

        kaomoji_layout.addWidget(
            self.submit_button
        )

        layout.addLayout(
            kaomoji_layout
        )

        # =========================
        # Symbol palette
        # =========================

        self.symbols_widget = QWidget()

        self.symbols_layout = QVBoxLayout(
            self.symbols_widget
        )

        style_constructor_content_layout(
            self.symbols_layout
        )

        self.symbols_scroll_area = QScrollArea()

        style_constructor_scroll(
            self.symbols_scroll_area
        )

        self.symbols_scroll_area.setWidget(
            self.symbols_widget
        )

        layout.addWidget(
            self.symbols_scroll_area,
            1,
        )

        # =========================
        # Signals
        # =========================

        self.clear_button.clicked.connect(
            self.handle_clear_button
        )

        self.submit_button.clicked.connect(
            self.request_submit
        )

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
        for category, symbols in (
            self.categories.items()
        ):
            category_label = QLabel(
                category
            )

            self.symbols_layout.addWidget(
                category_label
            )

            grid_widget = QWidget()

            grid_layout = QGridLayout(
                grid_widget
            )

            style_constructor_symbol_grid(
                grid_layout
            )

            for index, symbol in enumerate(
                symbols
            ):
                button = QPushButton(
                    symbol
                )

                button.setFocusPolicy(
                    Qt.FocusPolicy.NoFocus
                )

                style_constructor_symbol_button(
                    button
                )

                button.clicked.connect(
                    lambda checked=False, item=symbol:
                        self.insert_symbol(
                            item
                        )
                )

                row = (
                    index
                    // CONSTRUCTOR_GRID_COLUMNS
                )

                column = (
                    index
                    % CONSTRUCTOR_GRID_COLUMNS
                )

                grid_layout.addWidget(
                    button,
                    row,
                    column,
                )

            self.symbols_layout.addWidget(
                grid_widget
            )

    # =============================
    # Unicode font
    # =============================

    def update_kaomoji_input_font(
        self,
        text: str,
    ) -> None:
        style_unicode_text(
            self.kaomoji_input,
            text,
        )

    # =============================
    # Symbol editing
    # =============================

    def insert_symbol(
        self,
        symbol: str,
    ) -> None:
        self.kaomoji_input.insert(
            symbol
        )

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

        self.name_input.setText(
            data["name"]
        )

        self.tags_input.setText(
            ", ".join(
                data["tags"]
            )
        )

        self.kaomoji_input.setText(
            data["text"]
        )

        self.clear_button.setText(
            "Cancel"
        )

        self.submit_button.setText(
            "Edit"
        )

        self.kaomoji_input.setFocus()

        self.kaomoji_input.setCursorPosition(
            len(data["text"])
        )

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

        self.clear_button.setText(
            "Clear"
        )

        self.submit_button.setText(
            "Add"
        )

        self.kaomoji_input.setFocus()

    # =============================
    # Submit
    # =============================

    def request_submit(
        self,
    ) -> None:
        data: KaomojiInput = {
            "name": (
                self.name_input
                .text()
                .strip()
            ),
            "text": (
                self.kaomoji_input
                .text()
                .strip()
            ),
            "tags": parse_tags(
                self.tags_input.text()
            ),
        }

        self.submit_requested.emit(
            data
        )
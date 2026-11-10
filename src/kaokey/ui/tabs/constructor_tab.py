from PySide6.QtCore import (
    QEvent,
    QPointF,
    QMimeData,
    QRect,
    QRectF,
    QTextBoundaryFinder,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QFocusEvent,
    QInputMethodEvent,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QShowEvent,
    QTextCharFormat,
    QTextCursor,
    QTextLayout,
    QTextLine,
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
    """Edit raw Unicode while displaying every grapheme in logical LTR order."""

    _margin = 4

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.setCursorWidth(0)
        self._scroll_x = 0.0
        self._preedit_text = ""
        self._preedit_position = 0
        self._layout_cache: (
            tuple[tuple[str, str, int, str], QTextLayout, QTextLine] | None
        ) = None
        self.textChanged.connect(self._refresh_display)
        self.cursorPositionChanged.connect(self._refresh_display)

    def _visual_layout(self) -> tuple[QTextLayout, QTextLine]:
        # LRO changes the visual order without adding controls to the stored text.
        text = self.toPlainText()
        cache_key = (
            text,
            self._preedit_text,
            self._preedit_position,
            self.font().toString(),
        )
        if self._layout_cache is not None and self._layout_cache[0] == cache_key:
            return self._layout_cache[1], self._layout_cache[2]
        if self._preedit_text:
            units = 0
            index = 0
            for character in text:
                if units >= self._preedit_position:
                    break
                units += 2 if ord(character) > 0xFFFF else 1
                index += 1
            text = text[:index] + self._preedit_text + text[index:]
        layout = QTextLayout("\u202d" + text + "\u202c", self.font())
        option = QTextOption()
        option.setTextDirection(Qt.LayoutDirection.LeftToRight)
        option.setWrapMode(QTextOption.WrapMode.NoWrap)
        layout.setTextOption(option)
        layout.beginLayout()
        line = layout.createLine()
        line.setLineWidth(1_000_000)
        layout.endLayout()
        self._layout_cache = (cache_key, layout, line)
        return layout, line

    def _boundaries(
        self,
        boundary_type: QTextBoundaryFinder.BoundaryType = (
            QTextBoundaryFinder.BoundaryType.Grapheme
        ),
    ) -> list[int]:
        finder = QTextBoundaryFinder(
            boundary_type,
            self.toPlainText(),
        )
        positions = [0]
        while (position := finder.toNextBoundary()) >= 0:
            positions.append(position)
        return positions

    def _caret_x(self, line: QTextLine, position: int) -> float:
        preedit_units = len(self._preedit_text.encode("utf-16-le")) // 2
        visual_position = position + (
            preedit_units
            if self._preedit_text and position >= self._preedit_position
            else 0
        )
        return self._margin - self._scroll_x + line.cursorToX(visual_position + 1)[0]

    def _refresh_display(self) -> None:
        _, line = self._visual_layout()
        x = self._caret_x(line, self.textCursor().position())
        right_edge = max(self._margin, self.viewport().width() - self._margin)
        if x > right_edge:
            self._scroll_x += x - right_edge
        elif x < self._margin:
            self._scroll_x = max(0.0, self._scroll_x - (self._margin - x))
        self.viewport().update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self.viewport())
        painter.fillRect(event.rect(), self.palette().base())
        layout, line = self._visual_layout()
        origin = QPointF(
            self._margin - self._scroll_x,
            (self.viewport().height() - line.height()) / 2,
        )
        painter.setPen(self.palette().text().color())

        if self.toPlainText() or self._preedit_text:
            selections = []
            if self._preedit_text:
                preedit = QTextLayout.FormatRange()
                preedit.start = self._preedit_position + 1
                preedit.length = len(self._preedit_text.encode("utf-16-le")) // 2
                preedit.format = QTextCharFormat()
                preedit.format.setUnderlineStyle(
                    QTextCharFormat.UnderlineStyle.SingleUnderline
                )
                selections.append(preedit)
            cursor = self.textCursor()
            if cursor.hasSelection():
                selection = QTextLayout.FormatRange()
                selection.start = cursor.selectionStart() + 1
                selection.length = cursor.selectionEnd() - cursor.selectionStart()
                selection.format = QTextCharFormat()
                selection.format.setBackground(self.palette().highlight())
                selection.format.setForeground(self.palette().highlightedText())
                selections.append(selection)
            layout.draw(painter, origin, selections)
        else:
            painter.setPen(self.palette().placeholderText().color())
            painter.drawText(
                self.viewport().rect().adjusted(self._margin, 0, -self._margin, 0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                self.placeholderText(),
            )

        if self.hasFocus():
            scale = painter.device().devicePixelRatioF()
            x = round(self._caret_x(line, self.textCursor().position()) * scale)
            top = round(origin.y() * scale)
            height = max(1, round(line.height() * scale))
            painter.fillRect(
                QRectF(x / scale, top / scale, 1 / scale, height / scale),
                self.palette().highlight(),
            )

    def _position_at_x(self, x: float) -> int:
        _, line = self._visual_layout()
        boundaries = self._boundaries()
        return min(
            boundaries,
            key=lambda position: abs(self._caret_x(line, position) - x),
        )

    def insertPlainText(self, text: str) -> None:
        super().insertPlainText(self._single_line(text))

    def setPlainText(self, text: str) -> None:
        self._preedit_text = ""
        self._preedit_position = 0
        super().setPlainText(self._single_line(text))
        self._refresh_display()

    def clear(self) -> None:
        self._preedit_text = ""
        self._preedit_position = 0
        super().clear()
        self._refresh_display()

    @staticmethod
    def _single_line(text: str) -> str:
        lines = text.splitlines()
        return " ".join(lines) if lines else text

    def insertFromMimeData(self, source: QMimeData) -> None:
        if source.hasText():
            self.insertPlainText(source.text())

    def inputMethodEvent(self, event: QInputMethodEvent) -> None:
        position = self.textCursor().position()
        super().inputMethodEvent(event)
        self._preedit_text = event.preeditString()
        self._preedit_position = position if self._preedit_text else 0
        self._refresh_display()

    def _set_position(self, position: int, keep_anchor: bool = False) -> None:
        cursor = self.textCursor()
        cursor.setPosition(
            position,
            QTextCursor.MoveMode.KeepAnchor
            if keep_anchor else QTextCursor.MoveMode.MoveAnchor,
        )
        self.setTextCursor(cursor)
        self._refresh_display()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            self._set_position(
                self._position_at_x(event.position().x()),
                bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier),
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._set_position(self._position_at_x(event.position().x()), True)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            position = self._position_at_x(event.position().x())
            boundaries = self._boundaries()
            start = (
                position
                if position < boundaries[-1]
                else boundaries[-2] if len(boundaries) > 1 else 0
            )
            end = min((p for p in boundaries if p > start), default=start)
            self._set_position(start)
            self._set_position(end, True)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(
        self,
        event: QKeyEvent,
    ) -> None:
        if event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            return

        if event.key() in (
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
            Qt.Key.Key_Home,
            Qt.Key.Key_End,
        ):
            cursor = self.textCursor()
            boundary_type = (
                QTextBoundaryFinder.BoundaryType.Word
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier
                and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right)
                else QTextBoundaryFinder.BoundaryType.Grapheme
            )
            boundaries = self._boundaries(boundary_type)
            keep_anchor = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            if not keep_anchor and cursor.hasSelection() and event.key() in (
                Qt.Key.Key_Left,
                Qt.Key.Key_Right,
            ):
                position = (
                    cursor.selectionStart()
                    if event.key() == Qt.Key.Key_Left
                    else cursor.selectionEnd()
                )
            elif event.key() == Qt.Key.Key_Left:
                position = max(
                    (p for p in boundaries if p < cursor.position()),
                    default=0,
                )
            elif event.key() == Qt.Key.Key_Right:
                position = min(
                    (p for p in boundaries if p > cursor.position()),
                    default=boundaries[-1],
                )
            else:
                position = (
                    boundaries[0]
                    if event.key() == Qt.Key.Key_Home
                    else boundaries[-1]
                )
            self._set_position(position, keep_anchor)
            event.accept()
            return

        super().keyPressEvent(event)

    def focusInEvent(self, event: QFocusEvent) -> None:
        super().focusInEvent(event)
        self.viewport().update()

    def focusOutEvent(self, event: QFocusEvent) -> None:
        super().focusOutEvent(event)
        self._preedit_text = ""
        self._preedit_position = 0
        self.viewport().update()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._refresh_display()

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.PaletteChange):
            self._refresh_display()

    def inputMethodQuery(self, query: Qt.InputMethodQuery) -> object:
        if query == Qt.InputMethodQuery.ImCursorRectangle:
            _, line = self._visual_layout()
            return QRect(
                round(self._caret_x(line, self.textCursor().position())),
                round((self.viewport().height() - line.height()) / 2),
                1,
                round(line.height()),
            )
        return super().inputMethodQuery(query)

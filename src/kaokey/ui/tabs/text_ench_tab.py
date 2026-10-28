import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from kaokey.core.fancy_text import FancyTextVariant, generate_fancy_text
from kaokey.ui.styling.widget_styles import style_unicode_text


class TextEnchTab(QWidget):
    copy_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.variants: list[FancyTextVariant] = []
        self._result_controls: list[tuple[FancyTextVariant, QPushButton]] = []

        layout = QVBoxLayout(self)

        self.input_label = QLabel()
        layout.addWidget(self.input_label)

        self.text_input = QPlainTextEdit()
        style_unicode_text(self.text_input)
        line_height = self.text_input.fontMetrics().lineSpacing()
        vertical_padding = (
            2 * self.text_input.document().documentMargin()
            + 2 * self.text_input.frameWidth()
        )
        self.text_input.setFixedHeight(
            math.ceil(2 * line_height + vertical_padding)
        )
        layout.addWidget(self.text_input)

        self.enchance_button = QPushButton()
        self.enchance_button.setEnabled(False)
        layout.addWidget(self.enchance_button, 0, Qt.AlignmentFlag.AlignLeft)

        self.results_label = QLabel()
        layout.addWidget(self.results_label)

        self.results_scroll_area = QScrollArea()
        self.results_scroll_area.setWidgetResizable(True)
        self.results_scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.results_widget = QWidget()
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.results_scroll_area.setWidget(self.results_widget)
        layout.addWidget(self.results_scroll_area, 1)

        self.text_input.textChanged.connect(self.on_input_changed)
        self.enchance_button.clicked.connect(self.enchance_text)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.input_label.setText(self.tr("Text to enhance"))
        self.text_input.setPlaceholderText(self.tr("Type or paste text here..."))
        self.enchance_button.setText(self.tr("Enchance"))
        self.results_label.setText(
            self.tr("Variants ({count})").format(count=len(self.variants))
            if self.variants else self.tr("Variants")
        )
        for _, copy_button in self._result_controls:
            copy_button.setText(self.tr("Copy"))

    def on_input_changed(self) -> None:
        self.enchance_button.setEnabled(bool(self.text_input.toPlainText().strip()))
        self.clear_results()

    def clear_results(self) -> None:
        self.variants = []
        self._result_controls.clear()

        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.hide()
                widget.deleteLater()

        self.results_label.setText(self.tr("Variants"))

    def enchance_text(self, _checked: bool = False) -> None:
        self.clear_results()
        self.variants = generate_fancy_text(self.text_input.toPlainText())

        for variant in self.variants:
            row = QFrame(self.results_widget)
            row.setFrameShape(QFrame.Shape.StyledPanel)
            row_layout = QHBoxLayout(row)

            sample_label = QLabel()
            sample_label.setTextFormat(Qt.TextFormat.PlainText)
            # Show multiline input on one row without altering the copied text.
            preview = (
                variant.text.replace("\r\n", " ↵ ")
                .replace("\n", " ↵ ")
                .replace("\r", " ↵ ")
            )
            sample_label.setText(preview)
            sample_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            sample_label.setWordWrap(False)
            sample_label.setSizePolicy(
                QSizePolicy.Policy.Ignored,
                QSizePolicy.Policy.Preferred,
            )
            style_unicode_text(sample_label, "".join(dict.fromkeys(variant.text)))

            copy_button = QPushButton(self.tr("Copy"))
            copy_button.clicked.connect(
                lambda checked=False, value=variant.text: self.copy_requested.emit(value)
            )
            row_layout.addWidget(sample_label, 1)
            row_layout.addWidget(copy_button)
            self.results_layout.addWidget(row)
            self._result_controls.append((variant, copy_button))

        self.retranslate_ui()

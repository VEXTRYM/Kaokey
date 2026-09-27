from PySide6.QtCore import (
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from kaokey.core.kaomoji_search import matches_kaomoji_search
from kaokey.core.models import Kaomoji
from kaokey.ui.styling.widget_styles import (
    style_edit_action_button,
    style_edit_details_layout,
    style_edit_list_layout,
    style_edit_list_scroll,
    style_edit_row_layout,
    style_kaomoji_search_input,
    style_unicode_text,
)
from kaokey.ui.widgets.main_tags_editor import MainTagsEditor


class EditTab(QWidget):

    edit_kaomoji_requested = Signal(object)

    delete_kaomoji_requested = Signal(object)

    add_main_tag_requested = Signal(str)

    remove_main_tag_requested = Signal(str)

    move_main_tag_requested = Signal(str, int)

    def __init__(
        self,
        main_tags: list[str],
        kaomoji: list[Kaomoji],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.main_tags = main_tags
        self.kaomoji = kaomoji

        # =========================
        # Main layout
        # =========================

        layout = QVBoxLayout(self)

        # =========================
        # Main tags
        # =========================

        main_tags_label = QLabel("Main tags")

        layout.addWidget(main_tags_label)

        self.main_tags_editor = MainTagsEditor(self.main_tags)

        layout.addWidget(self.main_tags_editor)

        # =========================
        # Add main tag
        # =========================

        main_tag_add_layout = QHBoxLayout()

        self.main_tag_combo = QComboBox()

        self.add_main_tag_button = QPushButton("Add main tag")

        main_tag_add_layout.addWidget(self.main_tag_combo)

        main_tag_add_layout.addWidget(self.add_main_tag_button)

        layout.addLayout(main_tag_add_layout)

        # =========================
        # Search
        # =========================

        self.search_input = QLineEdit()

        style_kaomoji_search_input(self.search_input)

        self.search_input.setPlaceholderText(self.tr("Search kaomoji..."))

        layout.addWidget(self.search_input)

        # =========================
        # Edit list
        # =========================

        self.edit_list_widget = QWidget()

        self.edit_list_layout = QVBoxLayout(self.edit_list_widget)

        style_edit_list_layout(self.edit_list_layout)

        self.edit_scroll_area = QScrollArea()

        style_edit_list_scroll(self.edit_scroll_area)

        self.edit_scroll_area.setWidget(self.edit_list_widget)

        layout.addWidget(self.edit_scroll_area)

        # =========================
        # Signals
        # =========================

        self.add_main_tag_button.clicked.connect(self.request_add_main_tag)

        self.main_tags_editor.remove_requested.connect(
            self.remove_main_tag_requested.emit
        )
        self.main_tags_editor.move_requested.connect(
            self.move_main_tag_requested.emit
        )

        self.search_input.textChanged.connect(self.on_search_changed)

        # =========================
        # Initial UI
        # =========================

        self.refresh_main_tag_combo()
        self.fill_edit_list()

    # =============================
    # Public data
    # =============================

    def set_main_tags(
        self,
        main_tags: list[str],
    ) -> None:
        self.main_tags = main_tags

        self.main_tags_editor.set_tags(main_tags)
        self.refresh_main_tag_combo()

    def set_kaomoji(
        self,
        kaomoji: list[Kaomoji],
    ) -> None:
        self.kaomoji = kaomoji

        self.fill_edit_list()
        self.refresh_main_tag_combo()

    # =============================
    # Tags
    # =============================

    def get_all_tags(
        self,
    ) -> list[str]:
        tags = {
            tag
            for kaomoji in self.kaomoji
            for tag in kaomoji.get(
                "tags",
                [],
            )
        }

        return sorted(
            tags,
            key=str.lower,
        )

    # =============================
    # Main tag combo
    # =============================

    def refresh_main_tag_combo(
        self,
    ) -> None:
        all_tags = self.get_all_tags()

        available_tags = [tag for tag in all_tags if tag not in self.main_tags]

        self.main_tag_combo.clear()

        if available_tags:
            self.main_tag_combo.addItems(available_tags)

            self.main_tag_combo.setCurrentIndex(0)

            self.main_tag_combo.setEnabled(True)

            self.add_main_tag_button.setEnabled(True)

        else:
            self.main_tag_combo.setPlaceholderText("No tags available")

            self.main_tag_combo.setCurrentIndex(-1)

            self.main_tag_combo.setEnabled(False)

            self.add_main_tag_button.setEnabled(False)

    def request_add_main_tag(
        self,
    ) -> None:
        tag = self.main_tag_combo.currentText().strip()

        if not tag:
            return

        self.add_main_tag_requested.emit(tag)

    # =============================
    # Search
    # =============================

    def on_search_changed(
        self,
        _text: str,
    ) -> None:
        self.fill_edit_list()

    # =============================
    # Edit list
    # =============================

    def fill_edit_list(
        self,
    ) -> None:
        while self.edit_list_layout.count():
            layout_item = self.edit_list_layout.takeAt(0)

            if layout_item is None:
                continue

            widget = layout_item.widget()

            if widget is not None:
                widget.deleteLater()

        search_text = self.search_input.text()

        for kaomoji in self.kaomoji:
            if not matches_kaomoji_search(
                kaomoji,
                search_text,
            ):
                continue

            row_widget = QWidget()

            row_layout = QHBoxLayout(row_widget)

            style_edit_row_layout(row_layout)

            details_layout = QVBoxLayout()

            style_edit_details_layout(details_layout)

            name = kaomoji.get(
                "name",
                "",
            )

            if not name:
                name = "(unnamed)"

            name_label = QLabel(name)

            text = kaomoji["text"]
            kaomoji_label = QLabel(f"\u2066{text}\u2069")

            style_unicode_text(
                kaomoji_label,
                kaomoji["text"],
            )

            kaomoji_label.setAlignment(
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignTop
                | Qt.AlignmentFlag.AlignAbsolute
            )

            kaomoji_label.setWordWrap(True)

            tags = kaomoji.get(
                "tags",
                [],
            )

            tags_text = ", ".join(tags)

            if not tags_text:
                tags_text = "No tags"

            tags_label = QLabel(f"Tags: {tags_text}")

            edit_button = QPushButton("✎")

            style_edit_action_button(edit_button)

            edit_button.clicked.connect(
                lambda checked=False, item=kaomoji: self.edit_kaomoji_requested.emit(
                    item
                )
            )

            delete_button = QPushButton("×")

            style_edit_action_button(delete_button)

            delete_button.clicked.connect(
                lambda checked=False, item=kaomoji: self.delete_kaomoji_requested.emit(
                    item
                )
            )

            details_layout.addWidget(name_label)

            details_layout.addWidget(kaomoji_label)

            details_layout.addWidget(tags_label)

            row_layout.addLayout(details_layout)

            row_layout.addWidget(edit_button)

            row_layout.addWidget(delete_button)

            self.edit_list_layout.addWidget(row_widget)

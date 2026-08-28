from PySide6.QtCore import Signal

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from widget_styles import (
    style_list_action_button,
    style_list_select_button,
    style_lists_list_layout,
    style_lists_row_layout,
    style_lists_scroll,
)


class ListsTab(QWidget):
    use_list_requested = Signal(
        str
    )

    create_list_requested = Signal(
        str
    )

    rename_list_requested = Signal(
        str
    )

    delete_list_requested = Signal(
        str
    )

    export_list_requested = Signal(
        str
    )

    import_list_requested = Signal()

    def __init__(
        self,
        list_names: list[str],
        active_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.list_names = list_names
        self.active_name = active_name

        # =========================
        # Main layout
        # =========================

        layout = QVBoxLayout(
            self
        )

        # =========================
        # Create list
        # =========================

        create_layout = QHBoxLayout()

        self.new_list_input = QLineEdit()

        self.new_list_input.setPlaceholderText(
            "New list name"
        )

        self.create_list_button = QPushButton(
            "Create"
        )

        create_layout.addWidget(
            self.new_list_input
        )

        create_layout.addWidget(
            self.create_list_button
        )

        layout.addLayout(
            create_layout
        )

        # =========================
        # Import / Export
        # =========================

        file_actions_layout = QHBoxLayout()

        self.export_list_button = QPushButton(
            "Export current"
        )

        self.import_list_button = QPushButton(
            "Import list..."
        )

        file_actions_layout.addWidget(
            self.export_list_button
        )

        file_actions_layout.addWidget(
            self.import_list_button
        )

        layout.addLayout(
            file_actions_layout
        )

        # =========================
        # Lists label
        # =========================

        lists_label = QLabel(
            "Lists"
        )

        layout.addWidget(
            lists_label
        )

        # =========================
        # Lists
        # =========================

        self.list_widget = QWidget()

        self.list_layout = QVBoxLayout(
            self.list_widget
        )

        style_lists_list_layout(
            self.list_layout
        )

        self.list_scroll_area = (
            QScrollArea()
        )

        style_lists_scroll(
            self.list_scroll_area
        )

        self.list_scroll_area.setWidget(
            self.list_widget
        )

        layout.addWidget(
            self.list_scroll_area
        )

        # =========================
        # Signals
        # =========================

        self.create_list_button.clicked.connect(
            self.request_create_list
        )

        self.new_list_input.returnPressed.connect(
            self.request_create_list
        )

        self.export_list_button.clicked.connect(
            self.request_export_list
        )

        self.import_list_button.clicked.connect(
            self.import_list_requested.emit
        )

        # =========================
        # Initial UI
        # =========================

        self.fill_list()

    # =============================
    # Public methods
    # =============================

    def set_lists(
        self,
        list_names: list[str],
        active_name: str,
    ) -> None:
        self.list_names = list_names
        self.active_name = active_name

        self.fill_list()

    def clear_new_list_name(
        self,
    ) -> None:
        self.new_list_input.clear()

    # =============================
    # Fill list
    # =============================

    def fill_list(
        self,
    ) -> None:
        while self.list_layout.count():
            layout_item = (
                self.list_layout
                .takeAt(0)
            )

            if layout_item is None:
                continue

            widget = (
                layout_item.widget()
            )

            if widget is not None:
                widget.deleteLater()

        for name in self.list_names:
            row_widget = QWidget()

            row_layout = QHBoxLayout(
                row_widget
            )

            style_lists_row_layout(
                row_layout
            )

            # =====================
            # Select
            # =====================

            select_button = QPushButton(
                name
            )

            is_active = (
                name
                == self.active_name
            )

            style_list_select_button(
                select_button,
                is_active,
            )

            select_button.clicked.connect(
                lambda checked=False, item=name:
                    self.request_use_list(
                        item
                    )
            )

            # =====================
            # Edit
            # =====================

            edit_button = QPushButton(
                "✎"
            )

            style_list_action_button(
                edit_button
            )

            edit_button.clicked.connect(
                lambda checked=False, item=name:
                    self.rename_list_requested.emit(
                        item
                    )
            )

            # =====================
            # Delete
            # =====================

            delete_button = QPushButton(
                "×"
            )

            style_list_action_button(
                delete_button
            )

            delete_button.clicked.connect(
                lambda checked=False, item=name:
                    self.delete_list_requested.emit(
                        item
                    )
            )

            # =====================
            # Assemble
            # =====================

            row_layout.addWidget(
                select_button,
                1,
            )

            row_layout.addWidget(
                edit_button
            )

            row_layout.addWidget(
                delete_button
            )

            self.list_layout.addWidget(
                row_widget
            )

    # =============================
    # Requests
    # =============================

    def request_use_list(
        self,
        name: str,
    ) -> None:
        if (
            name
            == self.active_name
        ):
            return

        self.use_list_requested.emit(
            name
        )

    def request_create_list(
        self,
    ) -> None:
        name = (
            self.new_list_input
            .text()
            .strip()
        )

        if not name:
            return

        self.create_list_requested.emit(
            name
        )

    def request_export_list(
        self,
    ) -> None:
        if not self.active_name:
            return

        self.export_list_requested.emit(
            self.active_name
        )
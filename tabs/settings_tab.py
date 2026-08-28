from PySide6.QtCore import (
    QLocale,
    Signal,
    Qt,
)

from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from constants import (
    DEFAULT_HOTKEY_KEY,
    DEFAULT_HOTKEY_MODIFIER,
    HOTKEY_KEYS,
    HOTKEY_MODIFIERS,
    SYSTEM_LANGUAGE,
)

from style_constants import (
    POPUP_HEIGHT,
    POPUP_MAX_HEIGHT,
    POPUP_MAX_WIDTH,
    POPUP_MIN_HEIGHT,
    POPUP_MIN_WIDTH,
    POPUP_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_MAX_HEIGHT,
    WINDOW_MAX_WIDTH,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
    WINDOW_WIDTH,
)

from widget_styles import (
    style_settings_layout,
    style_settings_row_layout,
)


class SettingsTab(QWidget):
    language_changed = Signal(str)
    show_hints_changed = Signal(bool)
    add_space_after_insert_changed = Signal(bool)
    startup_changed = Signal(bool)
    hotkey_changed = Signal(str, str)
    window_size_changed = Signal(int, int)
    popup_size_changed = Signal(int, int)

    def __init__(
        self,
        available_languages: list[str],
        language: str,
        show_hints: bool,
        add_space_after_insert: bool,
        startup_enabled: bool,
        startup_available: bool,
        hotkey: tuple[str, str],
        hotkey_available: bool,
        window_size: tuple[int, int],
        popup_size: tuple[int, int],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.available_languages = (
            available_languages
        )

        # =========================
        # Main layout
        # =========================

        layout = QVBoxLayout(
            self
        )

        style_settings_layout(
            layout
        )

        # =========================
        # General
        # =========================

        self.general_group = QGroupBox()

        general_layout = QVBoxLayout(
            self.general_group
        )

        language_row = QHBoxLayout()

        style_settings_row_layout(
            language_row
        )

        self.language_label = QLabel()

        self.language_combo = QComboBox()

        self.fill_language_combo(
            language
        )

        language_row.addWidget(
            self.language_label
        )

        language_row.addWidget(
            self.language_combo,
            1,
        )

        general_layout.addLayout(
            language_row
        )

        self.show_hints_checkbox = QCheckBox()

        self.show_hints_checkbox.setChecked(
            show_hints
        )

        general_layout.addWidget(
            self.show_hints_checkbox
        )

        self.add_space_checkbox = QCheckBox()

        self.add_space_checkbox.setChecked(
            add_space_after_insert
        )

        general_layout.addWidget(
            self.add_space_checkbox
        )

        self.startup_checkbox = QCheckBox()

        self.startup_checkbox.setChecked(
            startup_enabled
        )

        self.startup_checkbox.setEnabled(
            startup_available
        )

        general_layout.addWidget(
            self.startup_checkbox
        )

        layout.addWidget(
            self.general_group
        )

        # =========================
        # Hotkey
        # =========================

        self.hotkey_group = QGroupBox()

        hotkey_layout = QVBoxLayout(
            self.hotkey_group
        )

        hotkey_row = QHBoxLayout()

        style_settings_row_layout(
            hotkey_row
        )

        self.hotkey_modifier_label = QLabel()
        self.hotkey_modifier_combo = QComboBox()

        self.hotkey_modifier_combo.addItems(
            list(
                HOTKEY_MODIFIERS
            )
        )

        self.hotkey_key_label = QLabel()
        self.hotkey_key_combo = QComboBox()

        self.hotkey_key_combo.addItems(
            list(
                HOTKEY_KEYS
            )
        )

        self.set_hotkey(
            *hotkey
        )

        self.hotkey_group.setEnabled(
            hotkey_available
        )

        hotkey_row.addWidget(
            self.hotkey_modifier_label
        )

        hotkey_row.addWidget(
            self.hotkey_modifier_combo
        )

        hotkey_row.addWidget(
            self.hotkey_key_label
        )

        hotkey_row.addWidget(
            self.hotkey_key_combo
        )

        hotkey_row.addStretch(
            1
        )

        hotkey_layout.addLayout(
            hotkey_row
        )

        self.reset_hotkey_button = QPushButton()

        hotkey_layout.addWidget(
            self.reset_hotkey_button,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )

        layout.addWidget(
            self.hotkey_group
        )

        # =========================
        # Window
        # =========================

        self.window_group = QGroupBox()

        window_layout = QVBoxLayout(
            self.window_group
        )

        size_row = QHBoxLayout()

        style_settings_row_layout(
            size_row
        )

        self.window_width_label = QLabel()
        self.window_width_spin = QSpinBox()

        self.window_width_spin.setRange(
            WINDOW_MIN_WIDTH,
            WINDOW_MAX_WIDTH,
        )

        self.window_width_spin.setValue(
            window_size[0]
        )

        self.window_width_spin.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )

        self.window_height_label = QLabel()
        self.window_height_spin = QSpinBox()

        self.window_height_spin.setRange(
            WINDOW_MIN_HEIGHT,
            WINDOW_MAX_HEIGHT,
        )

        self.window_height_spin.setValue(
            window_size[1]
        )

        self.window_height_spin.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )

        size_row.addWidget(
            self.window_width_label
        )

        size_row.addWidget(
            self.window_width_spin
        )

        size_row.addWidget(
            self.window_height_label
        )

        size_row.addWidget(
            self.window_height_spin
        )

        size_row.addStretch(
            1
        )

        window_layout.addLayout(
            size_row
        )

        self.reset_window_size_button = QPushButton()

        window_layout.addWidget(
            self.reset_window_size_button,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )

        layout.addWidget(
            self.window_group
        )

        # =========================
        # Popup
        # =========================

        self.popup_group = QGroupBox()

        popup_layout = QVBoxLayout(
            self.popup_group
        )

        popup_size_row = QHBoxLayout()

        style_settings_row_layout(
            popup_size_row
        )

        self.popup_width_label = QLabel()
        self.popup_width_spin = QSpinBox()

        self.popup_width_spin.setRange(
            POPUP_MIN_WIDTH,
            POPUP_MAX_WIDTH,
        )

        self.popup_width_spin.setValue(
            popup_size[0]
        )

        self.popup_width_spin.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )

        self.popup_height_label = QLabel()
        self.popup_height_spin = QSpinBox()

        self.popup_height_spin.setRange(
            POPUP_MIN_HEIGHT,
            POPUP_MAX_HEIGHT,
        )

        self.popup_height_spin.setValue(
            popup_size[1]
        )

        self.popup_height_spin.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )

        popup_size_row.addWidget(
            self.popup_width_label
        )

        popup_size_row.addWidget(
            self.popup_width_spin
        )

        popup_size_row.addWidget(
            self.popup_height_label
        )

        popup_size_row.addWidget(
            self.popup_height_spin
        )

        popup_size_row.addStretch(
            1
        )

        popup_layout.addLayout(
            popup_size_row
        )

        self.reset_popup_size_button = QPushButton()

        popup_layout.addWidget(
            self.reset_popup_size_button,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )

        layout.addWidget(
            self.popup_group
        )

        # =========================
        # Signals
        # =========================

        self.language_combo.currentIndexChanged.connect(
            self.request_language_change
        )

        self.show_hints_checkbox.toggled.connect(
            self.show_hints_changed.emit
        )

        self.add_space_checkbox.toggled.connect(
            self.add_space_after_insert_changed.emit
        )

        self.startup_checkbox.toggled.connect(
            self.startup_changed.emit
        )

        self.hotkey_modifier_combo.currentTextChanged.connect(
            self.request_hotkey_change
        )

        self.hotkey_key_combo.currentTextChanged.connect(
            self.request_hotkey_change
        )

        self.reset_hotkey_button.clicked.connect(
            self.reset_hotkey
        )

        self.window_width_spin.valueChanged.connect(
            self.request_window_size_change
        )

        self.window_height_spin.valueChanged.connect(
            self.request_window_size_change
        )

        self.reset_window_size_button.clicked.connect(
            self.reset_window_size
        )

        self.popup_width_spin.valueChanged.connect(
            self.request_popup_size_change
        )

        self.popup_height_spin.valueChanged.connect(
            self.request_popup_size_change
        )

        self.reset_popup_size_button.clicked.connect(
            self.reset_popup_size
        )

        self.retranslate_ui()

    # =============================
    # Language
    # =============================

    def fill_language_combo(
        self,
        current_language: str,
    ) -> None:
        self.language_combo.addItem(
            "",
            SYSTEM_LANGUAGE,
        )

        for language in self.available_languages:
            self.language_combo.addItem(
                self.language_display_name(
                    language
                ),
                language,
            )

        index = self.language_combo.findData(
            current_language
        )

        if index < 0:
            index = 0

        self.language_combo.setCurrentIndex(
            index
        )

    def language_display_name(
        self,
        language: str,
    ) -> str:
        locale = QLocale(
            language
        )

        name = locale.nativeLanguageName().strip()

        if not name:
            return language.upper()

        return (
            name[0].upper()
            + name[1:]
        )

    def request_language_change(
        self,
        index: int,
    ) -> None:
        value = self.language_combo.itemData(
            index
        )

        if not isinstance(
            value,
            str,
        ):
            return

        self.language_changed.emit(
            value
        )

    # =============================
    # Startup
    # =============================

    def set_startup_enabled(
        self,
        enabled: bool,
    ) -> None:
        self.startup_checkbox.blockSignals(
            True
        )

        self.startup_checkbox.setChecked(
            enabled
        )

        self.startup_checkbox.blockSignals(
            False
        )

    # =============================
    # Hotkey
    # =============================

    def request_hotkey_change(
        self,
        _value: str,
    ) -> None:
        self.hotkey_changed.emit(
            self.hotkey_modifier_combo.currentText(),
            self.hotkey_key_combo.currentText(),
        )

    def set_hotkey(
        self,
        modifier: str,
        key: str,
    ) -> None:
        self.hotkey_modifier_combo.blockSignals(
            True
        )

        self.hotkey_key_combo.blockSignals(
            True
        )

        modifier_index = (
            self.hotkey_modifier_combo.findText(
                modifier
            )
        )

        key_index = (
            self.hotkey_key_combo.findText(
                key
            )
        )

        if modifier_index >= 0:
            self.hotkey_modifier_combo.setCurrentIndex(
                modifier_index
            )

        if key_index >= 0:
            self.hotkey_key_combo.setCurrentIndex(
                key_index
            )

        self.hotkey_modifier_combo.blockSignals(
            False
        )

        self.hotkey_key_combo.blockSignals(
            False
        )

    def reset_hotkey(
        self,
        _checked: bool = False,
    ) -> None:
        self.set_hotkey(
            DEFAULT_HOTKEY_MODIFIER,
            DEFAULT_HOTKEY_KEY,
        )

        self.hotkey_changed.emit(
            DEFAULT_HOTKEY_MODIFIER,
            DEFAULT_HOTKEY_KEY,
        )

    # =============================
    # Window
    # =============================

    def request_window_size_change(
        self,
        _value: int,
    ) -> None:
        self.window_size_changed.emit(
            self.window_width_spin.value(),
            self.window_height_spin.value(),
        )

    def reset_window_size(
        self,
        _checked: bool = False,
    ) -> None:
        self.window_width_spin.blockSignals(
            True
        )

        self.window_height_spin.blockSignals(
            True
        )

        self.window_width_spin.setValue(
            WINDOW_WIDTH
        )

        self.window_height_spin.setValue(
            WINDOW_HEIGHT
        )

        self.window_width_spin.blockSignals(
            False
        )

        self.window_height_spin.blockSignals(
            False
        )

        self.window_size_changed.emit(
            WINDOW_WIDTH,
            WINDOW_HEIGHT,
        )

    # =============================
    # Popup
    # =============================

    def request_popup_size_change(
        self,
        _value: int,
    ) -> None:
        self.popup_size_changed.emit(
            self.popup_width_spin.value(),
            self.popup_height_spin.value(),
        )

    def reset_popup_size(
        self,
        _checked: bool = False,
    ) -> None:
        self.popup_width_spin.blockSignals(
            True
        )

        self.popup_height_spin.blockSignals(
            True
        )

        self.popup_width_spin.setValue(
            POPUP_WIDTH
        )

        self.popup_height_spin.setValue(
            POPUP_HEIGHT
        )

        self.popup_width_spin.blockSignals(
            False
        )

        self.popup_height_spin.blockSignals(
            False
        )

        self.popup_size_changed.emit(
            POPUP_WIDTH,
            POPUP_HEIGHT,
        )

    # =============================
    # Translation
    # =============================

    def retranslate_ui(
        self,
    ) -> None:
        self.general_group.setTitle(
            self.tr("General")
        )

        self.language_label.setText(
            self.tr("Language:")
        )

        self.language_combo.setItemText(
            0,
            self.tr("System")
        )

        self.show_hints_checkbox.setText(
            self.tr("Show help hints")
        )

        self.add_space_checkbox.setText(
            self.tr(
                "Add a space after inserting kaomoji"
            )
        )

        self.startup_checkbox.setText(
            self.tr(
                "Start Kaokey with Windows"
            )
        )

        self.hotkey_group.setTitle(
            self.tr("Popup hotkey")
        )

        self.hotkey_modifier_label.setText(
            self.tr("Modifier:")
        )

        self.hotkey_key_label.setText(
            self.tr("Key:")
        )

        self.reset_hotkey_button.setText(
            self.tr("Reset to default")
        )

        self.window_group.setTitle(
            self.tr("Main window")
        )

        self.window_width_label.setText(
            self.tr("Width:")
        )

        self.window_height_label.setText(
            self.tr("Height:")
        )

        self.reset_window_size_button.setText(
            self.tr(
                "Reset to default"
            )
        )

        self.popup_group.setTitle(
            self.tr("Popup")
        )

        self.popup_width_label.setText(
            self.tr("Width:")
        )

        self.popup_height_label.setText(
            self.tr("Height:")
        )

        self.reset_popup_size_button.setText(
            self.tr(
                "Reset to default"
            )
        )

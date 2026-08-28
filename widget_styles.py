from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from unicode_fonts import (
    font_for_text,
    font_with_unicode_fallbacks,
)

from style_constants import (
    EDIT_ACTION_BUTTON_SIZE,
    EDIT_DETAILS_MARGINS,
    EDIT_LIST_MARGINS,
    EDIT_MAIN_TAG_ITEM_SPACING,
    EDIT_MAIN_TAG_MARGINS,
    EDIT_MAIN_TAG_REMOVE_BUTTON_SIZE,
    EDIT_MAIN_TAGS_BAR_HEIGHT,
    EDIT_MAIN_TAGS_MARGINS,
    EDIT_ROW_MARGINS,
    EDIT_ROW_SPACING,
    FAVORITE_BORDER_COLOR,
    FAVORITE_BORDER_RADIUS,
    FAVORITE_BORDER_WIDTH,
    FAVORITE_BUTTON_BACKGROUND,
    FAVORITE_BUTTON_TEXT_COLOR,
    FAVORITES_BUTTON_FONT_SIZE,
    FAVORITES_BUTTON_PADDING,
    FAVORITES_BUTTON_WIDTH,
    FAVORITES_FILTER_BORDER_COLOR,
    GRID_SPACING,
    KAOMOJI_BUTTON_FONT_SIZE,
    KAOMOJI_BUTTON_MIN_HEIGHT,
    KAOMOJI_BUTTON_PADDING,
    KAOMOJI_FILTERS_MARGINS,
    KAOMOJI_MAIN_TAGS_BAR_HEIGHT,
    KAOMOJI_MAIN_TAGS_MARGINS,
    KAOMOJI_MAIN_TAG_SPACING,
    KEYBOARD_FOCUS_BORDER_COLOR,
    KEYBOARD_FOCUS_BORDER_RADIUS,
    KEYBOARD_FOCUS_BORDER_WIDTH,
    MAIN_TAG_ACTIVE_BACKGROUND,
    MAIN_TAG_ACTIVE_FONT_WEIGHT,
    MAIN_TAG_ACTIVE_TEXT_COLOR,
    POPUP_HEIGHT,
    POPUP_LAYOUT_MARGINS,
    POPUP_WIDTH,
    LISTS_ACTIVE_FONT_WEIGHT,
    LISTS_DELETE_BUTTON_SIZE,
    LISTS_LIST_MARGINS,
    LISTS_ROW_MARGINS,
    LISTS_ROW_SPACING,
    LISTS_ACTION_BUTTON_SIZE,
    CONSTRUCTOR_CATEGORY_SPACING,
    CONSTRUCTOR_CONTENT_MARGINS,
    CONSTRUCTOR_GRID_SPACING,
    CONSTRUCTOR_SYMBOL_BUTTON_HEIGHT,
    CONSTRUCTOR_SYMBOL_BUTTON_WIDTH,
    SETTINGS_LAYOUT_MARGINS,
    SETTINGS_ROW_SPACING,
    SETTINGS_SECTION_SPACING,
)


# =============================
# Buttons
# =============================

def style_unicode_text(
    widget: QWidget,
    text: str | None = None,
) -> None:
    base_font = widget.font()

    if text is None:
        font = font_with_unicode_fallbacks(
            base_font
        )

    else:
        font = font_for_text(
            base_font,
            text,
        )

    widget.setFont(
        font
    )


def style_constructor_scroll(
    scroll_area: QScrollArea,
) -> None:
    scroll_area.setWidgetResizable(
        True
    )


def style_constructor_content_layout(
    layout: QVBoxLayout,
) -> None:
    layout.setContentsMargins(
        *CONSTRUCTOR_CONTENT_MARGINS
    )

    layout.setSpacing(
        CONSTRUCTOR_CATEGORY_SPACING
    )

    layout.setAlignment(
        Qt.AlignmentFlag.AlignTop
    )


def style_constructor_symbol_grid(
    layout: QGridLayout,
) -> None:
    layout.setSpacing(
        CONSTRUCTOR_GRID_SPACING
    )

    layout.setAlignment(
        Qt.AlignmentFlag.AlignLeft
        | Qt.AlignmentFlag.AlignTop
    )


def style_constructor_symbol_button(
    button: QPushButton,
) -> None:
    style_unicode_text(
        button,
        button.text(),
    )

    button.setFixedSize(
        CONSTRUCTOR_SYMBOL_BUTTON_WIDTH,
        CONSTRUCTOR_SYMBOL_BUTTON_HEIGHT,
    )

def style_list_action_button(
    button: QPushButton,
) -> None:
    button.setFixedSize(
        LISTS_ACTION_BUTTON_SIZE,
        LISTS_ACTION_BUTTON_SIZE,
    )

def style_favorites_button(
    button: QPushButton,
) -> None:
    button.setFixedWidth(
        FAVORITES_BUTTON_WIDTH
    )

    button.setStyleSheet(
        f"""
        QPushButton {{
            font-size:
                {FAVORITES_BUTTON_FONT_SIZE}px;
            padding:
                {FAVORITES_BUTTON_PADDING}px;
        }}

        QPushButton:checked {{
            background-color:
                {FAVORITE_BUTTON_BACKGROUND};
            color:
                {FAVORITE_BUTTON_TEXT_COLOR};
            border:
                {FAVORITE_BORDER_WIDTH}px
                solid
                {FAVORITES_FILTER_BORDER_COLOR};
        }}

        QPushButton:focus {{
            border:
                {KEYBOARD_FOCUS_BORDER_WIDTH}px
                solid
                {KEYBOARD_FOCUS_BORDER_COLOR};
            border-radius:
                {KEYBOARD_FOCUS_BORDER_RADIUS}px;
        }}

        QPushButton:checked:focus {{
            border:
                {KEYBOARD_FOCUS_BORDER_WIDTH}px
                solid
                {KEYBOARD_FOCUS_BORDER_COLOR};
        }}
        """
    )


def style_kaomoji_button(
    button: QPushButton,
    favorite: bool,
) -> None:
    style_unicode_text(
        button,
        button.text(),
    )

    button.setMinimumHeight(
        KAOMOJI_BUTTON_MIN_HEIGHT
    )

    button.setSizePolicy(
        QSizePolicy.Policy.Ignored,
        QSizePolicy.Policy.Fixed,
    )

    if favorite:
        button.setStyleSheet(
            f"""
            QPushButton {{
                font-size:
                    {KAOMOJI_BUTTON_FONT_SIZE}px;
                padding:
                    {KAOMOJI_BUTTON_PADDING}px;
                border:
                    {FAVORITE_BORDER_WIDTH}px
                    solid
                    {FAVORITE_BORDER_COLOR};
                border-radius:
                    {FAVORITE_BORDER_RADIUS}px;
            }}

            QPushButton:focus {{
                border:
                    {KEYBOARD_FOCUS_BORDER_WIDTH}px
                    solid
                    {KEYBOARD_FOCUS_BORDER_COLOR};
                border-radius:
                    {KEYBOARD_FOCUS_BORDER_RADIUS}px;
            }}
            """
        )

    else:
        button.setStyleSheet(
            f"""
            QPushButton {{
                font-size:
                    {KAOMOJI_BUTTON_FONT_SIZE}px;
                padding:
                    {KAOMOJI_BUTTON_PADDING}px;
            }}

            QPushButton:focus {{
                border:
                    {KEYBOARD_FOCUS_BORDER_WIDTH}px
                    solid
                    {KEYBOARD_FOCUS_BORDER_COLOR};
                border-radius:
                    {KEYBOARD_FOCUS_BORDER_RADIUS}px;
            }}
            """
        )


def style_kaomoji_search_input(
    line_edit: QLineEdit,
) -> None:
    line_edit.setStyleSheet(
        f"""
        QLineEdit:focus {{
            border:
                {KEYBOARD_FOCUS_BORDER_WIDTH}px
                solid
                {KEYBOARD_FOCUS_BORDER_COLOR};
            border-radius:
                {KEYBOARD_FOCUS_BORDER_RADIUS}px;
        }}
        """
    )


def style_kaomoji_main_tag_button(
    button: QPushButton,
) -> None:
    button.setStyleSheet(
        f"""
        QPushButton:checked {{
            background-color:
                {MAIN_TAG_ACTIVE_BACKGROUND};
            color:
                {MAIN_TAG_ACTIVE_TEXT_COLOR};
            font-weight:
                {MAIN_TAG_ACTIVE_FONT_WEIGHT};
        }}

        QPushButton:focus {{
            border:
                {KEYBOARD_FOCUS_BORDER_WIDTH}px
                solid
                {KEYBOARD_FOCUS_BORDER_COLOR};
            border-radius:
                {KEYBOARD_FOCUS_BORDER_RADIUS}px;
        }}

        QPushButton:checked:focus {{
            background-color:
                {MAIN_TAG_ACTIVE_BACKGROUND};
            color:
                {MAIN_TAG_ACTIVE_TEXT_COLOR};
            font-weight:
                {MAIN_TAG_ACTIVE_FONT_WEIGHT};
            border:
                {KEYBOARD_FOCUS_BORDER_WIDTH}px
                solid
                {KEYBOARD_FOCUS_BORDER_COLOR};
            border-radius:
                {KEYBOARD_FOCUS_BORDER_RADIUS}px;
        }}
        """
    )


def style_edit_action_button(
    button: QPushButton,
) -> None:
    button.setFixedSize(
        EDIT_ACTION_BUTTON_SIZE,
        EDIT_ACTION_BUTTON_SIZE,
    )


def style_main_tag_remove_button(
    button: QPushButton,
) -> None:
    button.setFixedSize(
        EDIT_MAIN_TAG_REMOVE_BUTTON_SIZE,
        EDIT_MAIN_TAG_REMOVE_BUTTON_SIZE,
    )


# =============================
# Kaomoji tab layouts
# =============================


def style_kaomoji_filters_layout(
    layout: QHBoxLayout,
) -> None:
    layout.setContentsMargins(
        *KAOMOJI_FILTERS_MARGINS
    )

    layout.setSpacing(
        KAOMOJI_MAIN_TAG_SPACING
    )


def style_kaomoji_main_tags_layout(
    layout: QHBoxLayout,
) -> None:
    layout.setContentsMargins(
        *KAOMOJI_MAIN_TAGS_MARGINS
    )

    layout.setSpacing(
        KAOMOJI_MAIN_TAG_SPACING
    )

    layout.setAlignment(
        Qt.AlignmentFlag.AlignLeft
    )


def style_kaomoji_grid(
    layout: QGridLayout,
) -> None:
    layout.setSpacing(
        GRID_SPACING
    )

    layout.setAlignment(
        Qt.AlignmentFlag.AlignTop
    )


# =============================
# Kaomoji tab scroll areas
# =============================


def style_kaomoji_main_tags_scroll(
    scroll_area: QScrollArea,
) -> None:
    scroll_area.setWidgetResizable(
        False
    )

    scroll_area.setVerticalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )

    scroll_area.setHorizontalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAsNeeded
    )

    scroll_area.setFixedHeight(
        KAOMOJI_MAIN_TAGS_BAR_HEIGHT
    )


def style_kaomoji_grid_scroll(
    scroll_area: QScrollArea,
) -> None:
    scroll_area.setWidgetResizable(
        True
    )


# =============================
# Edit tab layouts
# =============================


def style_edit_main_tags_layout(
    layout: QHBoxLayout,
) -> None:
    layout.setContentsMargins(
        *EDIT_MAIN_TAGS_MARGINS
    )

    layout.setSpacing(
        EDIT_MAIN_TAG_ITEM_SPACING
    )

    layout.setAlignment(
        Qt.AlignmentFlag.AlignLeft
    )


def style_edit_main_tag_layout(
    layout: QHBoxLayout,
) -> None:
    layout.setContentsMargins(
        *EDIT_MAIN_TAG_MARGINS
    )

    layout.setSpacing(
        EDIT_MAIN_TAG_ITEM_SPACING
    )


def style_edit_list_layout(
    layout: QVBoxLayout,
) -> None:
    layout.setContentsMargins(
        *EDIT_LIST_MARGINS
    )

    layout.setSpacing(
        EDIT_ROW_SPACING
    )

    layout.setAlignment(
        Qt.AlignmentFlag.AlignTop
    )


def style_edit_row_layout(
    layout: QHBoxLayout,
) -> None:
    layout.setContentsMargins(
        *EDIT_ROW_MARGINS
    )

    layout.setSpacing(
        EDIT_ROW_SPACING
    )


def style_edit_details_layout(
    layout: QVBoxLayout,
) -> None:
    layout.setContentsMargins(
        *EDIT_DETAILS_MARGINS
    )

    layout.setSpacing(
        EDIT_ROW_SPACING
    )


# =============================
# Edit tab scroll areas
# =============================


def style_edit_main_tags_scroll(
    scroll_area: QScrollArea,
) -> None:
    scroll_area.setWidgetResizable(
        False
    )

    scroll_area.setVerticalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )

    scroll_area.setHorizontalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAsNeeded
    )

    scroll_area.setFixedHeight(
        EDIT_MAIN_TAGS_BAR_HEIGHT
    )


def style_edit_list_scroll(
    scroll_area: QScrollArea,
) -> None:
    scroll_area.setWidgetResizable(
        True
    )

def style_lists_list_layout(
    layout: QVBoxLayout,
) -> None:
    layout.setContentsMargins(
        *LISTS_LIST_MARGINS
    )

    layout.setSpacing(
        LISTS_ROW_SPACING
    )

    layout.setAlignment(
        Qt.AlignmentFlag.AlignTop
    )


def style_lists_row_layout(
    layout: QHBoxLayout,
) -> None:
    layout.setContentsMargins(
        *LISTS_ROW_MARGINS
    )

    layout.setSpacing(
        LISTS_ROW_SPACING
    )


def style_lists_scroll(
    scroll_area: QScrollArea,
) -> None:
    scroll_area.setWidgetResizable(
        True
    )


def style_list_select_button(
    button: QPushButton,
    active: bool,
) -> None:
    button.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Fixed,
    )

    if active:
        button.setStyleSheet(
            f"""
            QPushButton {{
                font-weight:
                    {LISTS_ACTIVE_FONT_WEIGHT};
                text-align: left;
            }}
            """
        )

    else:
        button.setStyleSheet(
            """
            QPushButton {
                text-align: left;
            }
            """
        )

# =============================
# Popup
# =============================


def style_popup_window(
    window: QWidget,
    width: int = POPUP_WIDTH,
    height: int = POPUP_HEIGHT,
) -> None:
    # Popup size is a setting, not a window-state preference.
    # setFixedSize() prevents manual resizing with the window frame.
    window.setFixedSize(
        width,
        height,
    )


def style_popup_layout(
    layout: QVBoxLayout,
) -> None:
    layout.setContentsMargins(
        *POPUP_LAYOUT_MARGINS
    )



# =============================
# Settings tab
# =============================

def style_settings_layout(
    layout: QVBoxLayout,
) -> None:
    layout.setContentsMargins(
        *SETTINGS_LAYOUT_MARGINS
    )

    layout.setSpacing(
        SETTINGS_SECTION_SPACING
    )

    layout.setAlignment(
        Qt.AlignmentFlag.AlignTop
    )


def style_settings_row_layout(
    layout: QHBoxLayout,
) -> None:
    layout.setContentsMargins(
        0,
        0,
        0,
        0,
    )

    layout.setSpacing(
        SETTINGS_ROW_SPACING
    )

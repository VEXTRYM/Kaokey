from app_paths import (
    resource_root,
    user_data_dir,
)


# Application

APPLICATION_NAME = "Kaokey"
ORGANIZATION_NAME = "Kaokey"
WINDOW_TITLE = APPLICATION_NAME

SINGLE_INSTANCE_SERVER_NAME = (
    "Kaokey.SingleInstance"
)


# Paths

# Read-only files shipped with the application. In a PyInstaller one-file
# build this resolves to the temporary bundle directory; in source mode it
# resolves to the project root.
RESOURCE_ROOT = resource_root()

# Kept as an alias because older modules/tests may still refer to BASE_DIR.
BASE_DIR = RESOURCE_ROOT

DEFAULT_DATA_PATH = (
    RESOURCE_ROOT
    / "data"
    / "kaomoji.json"
)

USER_DATA_DIR = user_data_dir(
    APPLICATION_NAME
)

# Writable library. On Windows this is normally:
# %APPDATA%\Kaokey\kaomoji.json
DATA_PATH = (
    USER_DATA_DIR
    / "kaomoji.json"
)

CONSTRUCTOR_SYMBOLS_PATH = (
    RESOURCE_ROOT
    / "data"
    / "constructor_symbols.json"
)

TRANSLATIONS_DIR = (
    RESOURCE_ROOT
    / "resources"
    / "translations"
)

ICON_PATH = (
    RESOURCE_ROOT
    / "resources"
    / "icons"
    / "kaokey.ico"
)


# Data

DATA_FORMAT_VERSION = 1
DEFAULT_LIST_NAME = "Default"
NEW_LIST_NAME = "New List"

LIST_EXPORT_TYPE = "kaokey_list"

LIST_FILE_FILTER = (
    "Kaokey list (*.json);;"
    "JSON files (*.json)"
)


# Settings

SETTINGS_LANGUAGE_KEY = "general/language"
SETTINGS_SHOW_HINTS_KEY = "ui/show_hints"
SETTINGS_WINDOW_WIDTH_KEY = "ui/window_width"
SETTINGS_WINDOW_HEIGHT_KEY = "ui/window_height"
SETTINGS_POPUP_WIDTH_KEY = "ui/popup_width"
SETTINGS_POPUP_HEIGHT_KEY = "ui/popup_height"
SETTINGS_ADD_SPACE_AFTER_INSERT_KEY = (
    "input/add_space_after_insert"
)
SETTINGS_HOTKEY_MODIFIER_KEY = (
    "input/hotkey_modifier"
)
SETTINGS_HOTKEY_KEY = (
    "input/hotkey_key"
)
SETTINGS_POPUP_X_KEY = "ui/popup_x"
SETTINGS_POPUP_Y_KEY = "ui/popup_y"

SYSTEM_LANGUAGE = "system"
SOURCE_LANGUAGE = "en"
DEFAULT_SHOW_HINTS = True
DEFAULT_ADD_SPACE_AFTER_INSERT = False

# Popup hotkey. Keep these values platform-neutral: Settings stores readable
# names, while platforms/windows/hotkey_config.py converts them to Win32
# modifier flags / virtual-key codes.
DEFAULT_HOTKEY_MODIFIER = "Alt"
DEFAULT_HOTKEY_KEY = "K"

HOTKEY_MODIFIERS = (
    "Alt",
    "Ctrl",
)

HOTKEY_KEYS = (
    *tuple(
        chr(code)
        for code in range(
            ord("A"),
            ord("Z") + 1,
        )
    ),
    *tuple(
        str(number)
        for number in range(10)
    ),
    *tuple(
        f"F{number}"
        for number in range(
            1,
            13,
        )
    ),
)

TRANSLATION_FILE_PREFIX = "kaokey_"


# Validation

MAX_KAOMOJI_LENGTH = 200
MAX_TAGS = 10
MAX_TAG_LENGTH = 30
MAX_MAIN_TAGS = 20

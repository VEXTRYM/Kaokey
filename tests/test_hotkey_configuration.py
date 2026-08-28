from platforms.windows.constants import (
    GLOBAL_HOTKEY_LABEL,
    GLOBAL_HOTKEY_MODIFIERS,
    GLOBAL_HOTKEY_RELEASE_VIRTUAL_KEYS,
    GLOBAL_HOTKEY_VIRTUAL_KEY,
    MOD_ALT,
    MOD_NOREPEAT,
    VK_MENU,
)


def test_default_hotkey_is_alt_k():
    assert GLOBAL_HOTKEY_LABEL == "Alt+K"
    assert GLOBAL_HOTKEY_VIRTUAL_KEY == ord("K")
    assert GLOBAL_HOTKEY_MODIFIERS == (
        MOD_ALT
        | MOD_NOREPEAT
    )


def test_release_check_tracks_alt_and_k():
    assert GLOBAL_HOTKEY_RELEASE_VIRTUAL_KEYS == (
        VK_MENU,
        ord("K"),
    )

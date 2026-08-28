from platforms.windows.constants import (
    MOD_ALT,
    MOD_CONTROL,
    MOD_NOREPEAT,
    MOD_SHIFT,
    VK_CONTROL,
    VK_MENU,
    VK_SHIFT,
)
from platforms.windows.hotkey_config import (
    hotkey_label,
    hotkey_modifier_flags,
    hotkey_release_virtual_keys,
    hotkey_virtual_key,
)


def test_default_style_mapping():
    assert hotkey_label(
        "Alt",
        "K",
    ) == "Alt+K"

    assert hotkey_modifier_flags(
        "Alt"
    ) == (
        MOD_ALT
        | MOD_NOREPEAT
    )

    assert hotkey_virtual_key(
        "K"
    ) == ord("K")

    assert hotkey_release_virtual_keys(
        "Alt",
        "K",
    ) == (
        VK_MENU,
        ord("K"),
    )


def test_ctrl_shift_and_function_keys():
    assert hotkey_modifier_flags(
        "Ctrl"
    ) == (
        MOD_CONTROL
        | MOD_NOREPEAT
    )

    assert hotkey_modifier_flags(
        "Shift"
    ) == (
        MOD_SHIFT
        | MOD_NOREPEAT
    )

    assert hotkey_release_virtual_keys(
        "Ctrl",
        "F12",
    ) == (
        VK_CONTROL,
        0x7B,
    )

    assert hotkey_release_virtual_keys(
        "Shift",
        "1",
    ) == (
        VK_SHIFT,
        ord("1"),
    )

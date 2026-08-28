from platforms.windows.constants import (
    MOD_ALT,
    MOD_CONTROL,
    MOD_NOREPEAT,
    MOD_SHIFT,
    VK_CONTROL,
    VK_F1,
    VK_MENU,
    VK_SHIFT,
)


MODIFIER_FLAGS = {
    "Alt": MOD_ALT,
    "Ctrl": MOD_CONTROL,
    "Shift": MOD_SHIFT,
}

MODIFIER_VIRTUAL_KEYS = {
    "Alt": VK_MENU,
    "Ctrl": VK_CONTROL,
    "Shift": VK_SHIFT,
}


def hotkey_label(
    modifier: str,
    key: str,
) -> str:
    return f"{modifier}+{key}"


def hotkey_modifier_flags(
    modifier: str,
) -> int:
    try:
        flag = MODIFIER_FLAGS[
            modifier
        ]
    except KeyError as error:
        raise ValueError(
            "Unsupported hotkey modifier."
        ) from error

    return (
        flag
        | MOD_NOREPEAT
    )


def hotkey_virtual_key(
    key: str,
) -> int:
    if (
        len(key) == 1
        and (
            "A" <= key <= "Z"
            or "0" <= key <= "9"
        )
    ):
        return ord(
            key
        )

    if (
        key.startswith("F")
        and key[1:].isdigit()
    ):
        number = int(
            key[1:]
        )

        if 1 <= number <= 12:
            return (
                VK_F1
                + number
                - 1
            )

    raise ValueError(
        "Unsupported hotkey key."
    )


def hotkey_release_virtual_keys(
    modifier: str,
    key: str,
) -> tuple[int, int]:
    try:
        modifier_key = (
            MODIFIER_VIRTUAL_KEYS[
                modifier
            ]
        )
    except KeyError as error:
        raise ValueError(
            "Unsupported hotkey modifier."
        ) from error

    return (
        modifier_key,
        hotkey_virtual_key(
            key
        ),
    )

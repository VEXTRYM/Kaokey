from copy import deepcopy
from typing import TypedDict

from constants import (
    MAX_MAIN_TAGS,
    NEW_LIST_NAME,
)

from models import (
    KaokeyData,
    Kaomoji,
    KaomojiList,
)


class MergeReport(TypedDict):
    added: int
    main_tags_added: int


# =============================
# Helpers
# =============================


def create_empty_list(
    name: str,
) -> KaomojiList:
    return {
        "name": name,
        "main_tags": [],
        "kaomoji": [],
    }


# =============================
# List lookup
# =============================


def get_active_list(
    data: KaokeyData,
) -> KaomojiList:
    active_name = data[
        "active_list"
    ]

    for kaomoji_list in data[
        "lists"
    ]:
        if (
            kaomoji_list["name"]
            == active_name
        ):
            return kaomoji_list

    raise ValueError(
        (
            "Active list does not exist: "
            f"{active_name}"
        )
    )


def find_list(
    data: KaokeyData,
    name: str,
) -> KaomojiList | None:
    normalized_name = (
        name.casefold()
    )

    for kaomoji_list in data[
        "lists"
    ]:
        if (
            kaomoji_list[
                "name"
            ].casefold()
            == normalized_name
        ):
            return kaomoji_list

    return None


def get_list_names(
    data: KaokeyData,
) -> list[str]:
    active_name = data[
        "active_list"
    ]

    other_names = [
        kaomoji_list["name"]
        for kaomoji_list
        in data["lists"]
        if (
            kaomoji_list["name"]
            != active_name
        )
    ]

    return [
        active_name,
        *other_names,
    ]


# =============================
# Create list
# =============================


def create_kaomoji_list(
    data: KaokeyData,
    name: str,
) -> KaomojiList:
    name = name.strip()

    if not name:
        raise ValueError(
            "List name cannot be empty."
        )

    if (
        find_list(
            data,
            name,
        )
        is not None
    ):
        raise ValueError(
            f'List "{name}" already exists.'
        )

    new_list = create_empty_list(
        name
    )

    data["lists"].append(
        new_list
    )

    return new_list


# =============================
# Select list
# =============================


def set_active_list(
    data: KaokeyData,
    name: str,
) -> KaomojiList:
    kaomoji_list = find_list(
        data,
        name,
    )

    if kaomoji_list is None:
        raise ValueError(
            f'List "{name}" does not exist.'
        )

    data["active_list"] = (
        kaomoji_list["name"]
    )

    return kaomoji_list


# =============================
# Rename list
# =============================


def rename_kaomoji_list(
    data: KaokeyData,
    old_name: str,
    new_name: str,
) -> KaomojiList:
    kaomoji_list = find_list(
        data,
        old_name,
    )

    if kaomoji_list is None:
        raise ValueError(
            f'List "{old_name}" does not exist.'
        )

    new_name = new_name.strip()

    if not new_name:
        raise ValueError(
            "List name cannot be empty."
        )

    existing_list = find_list(
        data,
        new_name,
    )

    # The same list is allowed.
    # This lets us rename:
    #
    # Animals -> animals
    #
    # without treating it as a conflict.

    if (
        existing_list is not None
        and existing_list
        is not kaomoji_list
    ):
        raise ValueError(
            f'List "{new_name}" already exists.'
        )

    was_active = (
        kaomoji_list["name"]
        == data["active_list"]
    )

    kaomoji_list["name"] = (
        new_name
    )

    if was_active:
        data["active_list"] = (
            new_name
        )

    return kaomoji_list


# =============================
# Delete list
# =============================


def delete_kaomoji_list(
    data: KaokeyData,
    name: str,
) -> None:
    kaomoji_list = find_list(
        data,
        name,
    )

    if kaomoji_list is None:
        raise ValueError(
            f'List "{name}" does not exist.'
        )

    was_active = (
        kaomoji_list["name"]
        == data["active_list"]
    )

    data["lists"].remove(
        kaomoji_list
    )

    # If the last list was deleted,
    # create a fresh empty list.

    if not data["lists"]:
        new_list = create_empty_list(
            NEW_LIST_NAME
        )

        data["lists"].append(
            new_list
        )

        data["active_list"] = (
            new_list["name"]
        )

        return

    # If another active list was
    # deleted, select the first
    # remaining list.

    if was_active:
        data["active_list"] = (
            data["lists"][0][
                "name"
            ]
        )


# =============================
# Import helpers
# =============================


def reset_imported_favorites(
    kaomoji: Kaomoji,
) -> None:
    kaomoji["favorite"] = False

    kaomoji.pop(
        "favorite_order",
        None,
    )


def make_unique_list_name(
    data: KaokeyData,
    name: str,
) -> str:
    if (
        find_list(
            data,
            name,
        )
        is None
    ):
        return name

    number = 1

    while True:
        candidate = (
            f"{name}({number})"
        )

        if (
            find_list(
                data,
                candidate,
            )
            is None
        ):
            return candidate

        number += 1


def add_imported_list(
    data: KaokeyData,
    imported_list: KaomojiList,
) -> KaomojiList:
    new_list = deepcopy(
        imported_list
    )

    new_list["name"] = (
        make_unique_list_name(
            data,
            new_list["name"],
        )
    )

    for kaomoji in new_list[
        "kaomoji"
    ]:
        reset_imported_favorites(
            kaomoji
        )

    data["lists"].append(
        new_list
    )

    return new_list


# =============================
# Kaomoji name conflicts
# =============================


def make_unique_kaomoji_name(
    name: str,
    existing_names: set[str],
) -> str:
    if not name:
        return ""

    normalized_name = (
        name.casefold()
    )

    if (
        normalized_name
        not in existing_names
    ):
        existing_names.add(
            normalized_name
        )

        return name

    number = 1

    while True:
        candidate = (
            f"{name}({number})"
        )

        normalized_candidate = (
            candidate.casefold()
        )

        if (
            normalized_candidate
            not in existing_names
        ):
            existing_names.add(
                normalized_candidate
            )

            return candidate

        number += 1


# =============================
# Merge
# =============================


def merge_kaomoji_lists(
    current_list: KaomojiList,
    imported_list: KaomojiList,
) -> MergeReport:
    report: MergeReport = {
        "added": 0,
        "main_tags_added": 0,
    }

    existing_texts = {
        kaomoji["text"]
        for kaomoji
        in current_list[
            "kaomoji"
        ]
    }

    existing_names = {
        kaomoji["name"].casefold()
        for kaomoji
        in current_list[
            "kaomoji"
        ]
        if kaomoji["name"]
    }

    # =========================
    # Kaomoji
    # =========================

    for imported_kaomoji in (
        imported_list[
            "kaomoji"
        ]
    ):
        text = imported_kaomoji[
            "text"
        ]

        if text in existing_texts:
            continue

        new_kaomoji = deepcopy(
            imported_kaomoji
        )

        reset_imported_favorites(
            new_kaomoji
        )

        new_kaomoji["name"] = (
            make_unique_kaomoji_name(
                new_kaomoji["name"],
                existing_names,
            )
        )

        current_list[
            "kaomoji"
        ].append(
            new_kaomoji
        )

        existing_texts.add(
            text
        )

        report["added"] += 1

    # =========================
    # Main tags
    # =========================

    for tag in imported_list[
        "main_tags"
    ]:
        if (
            tag
            in current_list[
                "main_tags"
            ]
        ):
            continue

        if (
            len(
                current_list[
                    "main_tags"
                ]
            )
            >= MAX_MAIN_TAGS
        ):
            break

        current_list[
            "main_tags"
        ].append(
            tag
        )

        report[
            "main_tags_added"
        ] += 1

    return report
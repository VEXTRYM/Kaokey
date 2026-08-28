import json

from pathlib import Path

from constants import (
    DATA_FORMAT_VERSION,
    LIST_EXPORT_TYPE,
    MAX_MAIN_TAGS,
    MAX_TAG_LENGTH,
)

from models import (
    Kaomoji,
    KaomojiList,
)

from validators import (
    validate_kaomoji_content,
)


def export_kaomoji_list(
    path: str,
    kaomoji_list: KaomojiList,
) -> Path:
    file_path = Path(
        path
    )

    if (
        file_path.suffix.lower()
        != ".json"
    ):
        file_path = file_path.with_suffix(
            ".json"
        )

    export_list = make_export_list(
        kaomoji_list
    )

    export_data = {
        "format_version": (
            DATA_FORMAT_VERSION
        ),
        "type": LIST_EXPORT_TYPE,
        "list": export_list,
    }

    try:
        with file_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                export_data,
                file,
                ensure_ascii=False,
                indent=4,
            )

    except OSError as error:
        raise ValueError(
            (
                "Could not export list: "
                f"{error}"
            )
        ) from error

    return file_path


def import_kaomoji_list(
    path: str,
) -> KaomojiList:
    file_path = Path(
        path
    )

    try:
        with file_path.open(
            encoding="utf-8"
        ) as file:
            raw_data = json.load(
                file
            )

    except json.JSONDecodeError as error:
        raise ValueError(
            "File is not valid JSON."
        ) from error

    except OSError as error:
        raise ValueError(
            (
                "Could not read file: "
                f"{error}"
            )
        ) from error

    # =========================
    # Export container
    # =========================

    if not isinstance(
        raw_data,
        dict,
    ):
        raise ValueError(
            "Invalid Kaokey list file."
        )

    if (
        raw_data.get(
            "format_version"
        )
        != DATA_FORMAT_VERSION
    ):
        raise ValueError(
            "Unsupported list format version."
        )

    # A normal Export list file has this shape:
    #
    # {
    #     "format_version": 1,
    #     "type": "kaokey_list",
    #     "list": {...}
    # }
    #
    # Kaokey's bundled/user library instead has:
    #
    # {
    #     "format_version": 1,
    #     "active_list": "Default",
    #     "lists": [{...}]
    # }
    #
    # Import List also accepts the library form when it contains exactly one
    # list. This makes the shipped Default seed importable into an existing
    # profile without weakening validation for ambiguous multi-list files.

    if (
        raw_data.get(
            "type"
        )
        == LIST_EXPORT_TYPE
    ):
        raw_list = raw_data.get(
            "list"
        )

    elif "lists" in raw_data:
        raw_lists = raw_data.get(
            "lists"
        )

        if not isinstance(
            raw_lists,
            list,
        ):
            raise ValueError(
                "Kaokey library lists are invalid."
            )

        if len(raw_lists) != 1:
            raise ValueError(
                (
                    "This Kaokey library contains "
                    f"{len(raw_lists)} lists. "
                    "Import List can import only one list at a time."
                )
            )

        raw_list = raw_lists[0]

    else:
        raise ValueError(
            "File is not a Kaokey list."
        )

    if not isinstance(
        raw_list,
        dict,
    ):
        raise ValueError(
            "Imported list is invalid."
        )

    # =========================
    # List name
    # =========================

    name = raw_list.get(
        "name"
    )

    if not isinstance(
        name,
        str,
    ):
        raise ValueError(
            "List name is invalid."
        )

    name = name.strip()

    if not name:
        raise ValueError(
            "List name cannot be empty."
        )

    # =========================
    # Main tags
    # =========================

    raw_main_tags = raw_list.get(
        "main_tags"
    )

    if not isinstance(
        raw_main_tags,
        list,
    ):
        raise ValueError(
            "Main tags are invalid."
        )

    main_tags: list[str] = []

    for tag in raw_main_tags:
        if not isinstance(
            tag,
            str,
        ):
            raise ValueError(
                "Main tags must be strings."
            )

        if len(
            tag
        ) > MAX_TAG_LENGTH:
            raise ValueError(
                (
                    f'Main tag "{tag}" '
                    "is too long."
                )
            )

        if tag in main_tags:
            raise ValueError(
                (
                    "Duplicate main tag: "
                    f"{tag}"
                )
            )

        main_tags.append(
            tag
        )

    if (
        len(main_tags)
        > MAX_MAIN_TAGS
    ):
        raise ValueError(
            (
                "Imported list contains "
                "too many main tags."
            )
        )

    # =========================
    # Kaomoji
    # =========================

    raw_kaomoji = raw_list.get(
        "kaomoji"
    )

    if not isinstance(
        raw_kaomoji,
        list,
    ):
        raise ValueError(
            "Kaomoji data is invalid."
        )

    kaomoji_items: list[
        Kaomoji
    ] = []

    existing_names: set[str] = set()

    for index, raw_item in enumerate(
        raw_kaomoji,
        start=1,
    ):
        if not isinstance(
            raw_item,
            dict,
        ):
            raise ValueError(
                (
                    "Invalid kaomoji at "
                    f"position {index}."
                )
            )

        item_name = raw_item.get(
            "name"
        )

        text = raw_item.get(
            "text"
        )

        tags = raw_item.get(
            "tags"
        )

        if not isinstance(
            item_name,
            str,
        ):
            raise ValueError(
                (
                    "Invalid name at "
                    f"position {index}."
                )
            )

        if not isinstance(
            text,
            str,
        ):
            raise ValueError(
                (
                    "Invalid text at "
                    f"position {index}."
                )
            )

        if not isinstance(
            tags,
            list,
        ):
            raise ValueError(
                (
                    "Invalid tags at "
                    f"position {index}."
                )
            )

        if not all(
            isinstance(
                tag,
                str,
            )
            for tag in tags
        ):
            raise ValueError(
                (
                    "Tags must be strings "
                    f"at position {index}."
                )
            )

        error = validate_kaomoji_content(
            text,
            tags,
        )

        if error is not None:
            raise ValueError(
                (
                    f"Kaomoji {index}: "
                    f"{error}"
                )
            )

        normalized_name = (
            item_name.casefold()
        )

        if (
            item_name
            and normalized_name
            in existing_names
        ):
            raise ValueError(
                (
                    "Duplicate kaomoji name: "
                    f"{item_name}"
                )
            )

        if item_name:
            existing_names.add(
                normalized_name
            )

        item: Kaomoji = {
            "name": item_name,
            "text": text,
            "tags": list(tags),
            "favorite": False,
        }

        kaomoji_items.append(
            item
        )

    return {
        "name": name,
        "main_tags": main_tags,
        "kaomoji": kaomoji_items,
    }

def make_export_list(
    kaomoji_list: KaomojiList,
) -> KaomojiList:
    export_kaomoji: list[Kaomoji] = []

    for kaomoji in kaomoji_list[
        "kaomoji"
    ]:
        export_item: Kaomoji = {
            "name": kaomoji.get(
                "name",
                "",
            ),
            "text": kaomoji["text"],
            "tags": list(
                kaomoji.get(
                    "tags",
                    [],
                )
            ),
            "favorite": False,
        }

        export_kaomoji.append(
            export_item
        )

    return {
        "name": kaomoji_list["name"],
        "main_tags": list(
            kaomoji_list["main_tags"]
        ),
        "kaomoji": export_kaomoji,
    }
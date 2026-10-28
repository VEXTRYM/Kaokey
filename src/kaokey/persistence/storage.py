import json
import os
import shutil
from pathlib import Path
from typing import cast

from kaokey.config.constants import (
    DATA_FORMAT_VERSION,
    DATA_PATH,
    DEFAULT_DATA_PATH,
    DEFAULT_LIST_NAME,
)
from kaokey.core.models import (
    KaokeyData,
    Kaomoji,
    KaomojiList,
)


def create_default_data(
    main_tags: list[str] | None = None,
    kaomoji: list[Kaomoji] | None = None,
) -> KaokeyData:
    if main_tags is None:
        main_tags = []

    if kaomoji is None:
        kaomoji = []

    default_list: KaomojiList = {
        "name": DEFAULT_LIST_NAME,
        "main_tags": main_tags,
        "kaomoji": kaomoji,
    }

    return {
        "format_version": (DATA_FORMAT_VERSION),
        "active_list": (DEFAULT_LIST_NAME),
        "lists": [default_list],
    }


def ensure_user_data_file(
    data_path: Path = DATA_PATH,
    default_data_path: Path = DEFAULT_DATA_PATH,
) -> None:
    """Create the writable user library without overwriting user data."""
    if data_path.exists():
        return

    data_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # In source mode this is the project's existing data/kaomoji.json.
    # In a packaged build it is the bundled read-only default library.
    # Copying it on first run gives a fresh installation its initial content.
    if default_data_path.exists():
        shutil.copy2(
            default_data_path,
            data_path,
        )
        return

    _write_data_file(
        create_default_data(),
        data_path,
    )


def validate_library_data(
    raw_data: object,
) -> KaokeyData:
    """Accept only the versioned, multi-list Kaokey JSON structure."""
    if not isinstance(raw_data, dict):
        raise ValueError("Invalid Kaokey library format.")

    if (
        type(raw_data.get("format_version")) is not int
        or raw_data["format_version"] != DATA_FORMAT_VERSION
        or not isinstance(raw_data.get("active_list"), str)
        or not isinstance(raw_data.get("lists"), list)
    ):
        raise ValueError("Invalid Kaokey library format.")

    for raw_list in raw_data["lists"]:
        if (
            not isinstance(raw_list, dict)
            or not isinstance(raw_list.get("name"), str)
            or not isinstance(raw_list.get("main_tags"), list)
            or not isinstance(raw_list.get("kaomoji"), list)
        ):
            raise ValueError("Invalid Kaokey library format.")

        if not all(isinstance(tag, str) for tag in raw_list["main_tags"]):
            raise ValueError("Invalid Kaokey library format.")

        for item in raw_list["kaomoji"]:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("name"), str)
                or not isinstance(item.get("text"), str)
                or not isinstance(item.get("tags"), list)
                or not all(isinstance(tag, str) for tag in item["tags"])
            ):
                raise ValueError("Invalid Kaokey library format.")

    return cast(KaokeyData, raw_data)


def load_data() -> KaokeyData:
    ensure_user_data_file()

    with DATA_PATH.open(encoding="utf-8") as file:
        raw_data = json.load(file)

    data = validate_library_data(raw_data)

    changed = False

    # A valid library should always
    # contain at least one list.

    if not data["lists"]:
        default_list: KaomojiList = {
            "name": DEFAULT_LIST_NAME,
            "main_tags": [],
            "kaomoji": [],
        }

        data["lists"].append(default_list)

        data["active_list"] = DEFAULT_LIST_NAME

        changed = True

    # Make sure active_list actually
    # points to an existing list.

    list_names = {kaomoji_list["name"] for kaomoji_list in data["lists"]}

    if data["active_list"] not in list_names:
        data["active_list"] = data["lists"][0]["name"]

        changed = True

    if changed:
        save_data(data)

    return data


def save_data(
    data: KaokeyData,
) -> None:
    _write_data_file(
        data,
        DATA_PATH,
    )


def _write_data_file(
    data: KaokeyData,
    path: Path,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = path.with_name(f"{path.name}.tmp")

    try:
        with temporary_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=4,
            )

            file.flush()
            os.fsync(file.fileno())

        os.replace(
            temporary_path,
            path,
        )

    finally:
        try:
            temporary_path.unlink()

        except FileNotFoundError:
            pass

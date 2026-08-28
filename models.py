from typing import (
    NotRequired,
    TypedDict,
)


class KaomojiInput(TypedDict):
    name: str
    text: str
    tags: list[str]


class Kaomoji(KaomojiInput):
    favorite: NotRequired[bool]
    favorite_order: NotRequired[int]


class KaomojiList(TypedDict):
    name: str
    main_tags: list[str]
    kaomoji: list[Kaomoji]


class KaokeyData(TypedDict):
    format_version: int
    active_list: str
    lists: list[KaomojiList]


# Used only for migration from our
# current JSON format.
class LegacyKaomojiData(TypedDict):
    main_tags: list[str]
    kaomoji: list[Kaomoji]
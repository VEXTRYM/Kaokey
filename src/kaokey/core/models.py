from typing import TypedDict


class KaomojiInput(TypedDict):
    name: str
    text: str
    tags: list[str]


class Kaomoji(KaomojiInput, total=False):
    favorite: bool
    favorite_order: int


class KaomojiList(TypedDict):
    name: str
    main_tags: list[str]
    kaomoji: list[Kaomoji]


class KaokeyData(TypedDict):
    format_version: int
    active_list: str
    lists: list[KaomojiList]

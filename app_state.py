from collections.abc import Callable

from constants import MAX_MAIN_TAGS
from library import (
    MergeReport,
    add_imported_list,
    create_kaomoji_list,
    delete_kaomoji_list,
    find_list,
    get_active_list,
    get_list_names,
    merge_kaomoji_lists,
    rename_kaomoji_list,
    set_active_list,
)
from models import (
    KaokeyData,
    Kaomoji,
    KaomojiInput,
    KaomojiList,
)
from storage import load_data, save_data


SaveCallback = Callable[[KaokeyData], None]


class AppState:
    def __init__(
        self,
        data: KaokeyData,
        save_callback: SaveCallback = save_data,
    ) -> None:
        self.data = data
        self._save_callback = save_callback
        self.next_favorite_order = 1

        if self._initialize_favorites():
            self.save()

    @classmethod
    def load(cls) -> "AppState":
        return cls(
            load_data()
        )

    # =============================
    # Active list access
    # =============================

    @property
    def current_list(self) -> KaomojiList:
        return get_active_list(
            self.data
        )

    @property
    def main_tags(self) -> list[str]:
        return self.current_list[
            "main_tags"
        ]

    @property
    def kaomoji(self) -> list[Kaomoji]:
        return self.current_list[
            "kaomoji"
        ]

    @property
    def active_list_name(self) -> str:
        return self.data[
            "active_list"
        ]

    @property
    def list_names(self) -> list[str]:
        return get_list_names(
            self.data
        )

    def find_list(
        self,
        name: str,
    ) -> KaomojiList | None:
        return find_list(
            self.data,
            name,
        )

    # =============================
    # Persistence
    # =============================

    def save(self) -> None:
        self._save_callback(
            self.data
        )

    # =============================
    # Favorites
    # =============================

    def _initialize_favorites(
        self,
    ) -> bool:
        highest_order = 0
        changed = False

        for kaomoji in self.kaomoji:
            if not kaomoji.get(
                "favorite",
                False,
            ):
                continue

            favorite_order = kaomoji.get(
                "favorite_order"
            )

            if (
                isinstance(
                    favorite_order,
                    int,
                )
                and not isinstance(
                    favorite_order,
                    bool,
                )
            ):
                highest_order = max(
                    highest_order,
                    favorite_order,
                )

        for kaomoji in self.kaomoji:
            if not kaomoji.get(
                "favorite",
                False,
            ):
                continue

            favorite_order = kaomoji.get(
                "favorite_order"
            )

            if (
                not isinstance(
                    favorite_order,
                    int,
                )
                or isinstance(
                    favorite_order,
                    bool,
                )
            ):
                highest_order += 1

                kaomoji[
                    "favorite_order"
                ] = highest_order

                changed = True

        self.next_favorite_order = (
            highest_order + 1
        )

        return changed

    def toggle_favorite(
        self,
        kaomoji: Kaomoji,
    ) -> bool:
        is_favorite = kaomoji.get(
            "favorite",
            False,
        )

        if is_favorite:
            kaomoji[
                "favorite"
            ] = False

            kaomoji.pop(
                "favorite_order",
                None,
            )

            new_state = False

        else:
            kaomoji[
                "favorite"
            ] = True

            kaomoji[
                "favorite_order"
            ] = self.next_favorite_order

            self.next_favorite_order += 1
            new_state = True

        self.save()

        return new_state

    # =============================
    # Kaomoji CRUD
    # =============================

    def existing_kaomoji_names(
        self,
        exclude: Kaomoji | None = None,
    ) -> set[str]:
        return {
            kaomoji["name"].casefold()
            for kaomoji in self.kaomoji
            if (
                kaomoji["name"]
                and kaomoji is not exclude
            )
        }

    def add_kaomoji(
        self,
        input_data: KaomojiInput,
    ) -> Kaomoji:
        new_kaomoji: Kaomoji = {
            "name": input_data["name"],
            "text": input_data["text"],
            "tags": list(
                input_data["tags"]
            ),
            "favorite": False,
        }

        self.kaomoji.append(
            new_kaomoji
        )

        self.save()

        return new_kaomoji

    def update_kaomoji(
        self,
        kaomoji: Kaomoji,
        input_data: KaomojiInput,
    ) -> None:
        kaomoji["name"] = (
            input_data["name"]
        )

        kaomoji["text"] = (
            input_data["text"]
        )

        kaomoji["tags"] = list(
            input_data["tags"]
        )

        # favorite and favorite_order are
        # deliberately preserved.

        self.save()

    def delete_kaomoji(
        self,
        kaomoji: Kaomoji,
    ) -> None:
        self.kaomoji.remove(
            kaomoji
        )

        self.save()

    # =============================
    # Main tags
    # =============================

    def add_main_tag(
        self,
        tag: str,
    ) -> bool:
        if not tag:
            return False

        if tag in self.main_tags:
            return False

        if (
            len(self.main_tags)
            >= MAX_MAIN_TAGS
        ):
            raise ValueError(
                (
                    "Maximum number of main "
                    f"tags is {MAX_MAIN_TAGS}."
                )
            )

        self.main_tags.append(
            tag
        )

        self.save()

        return True

    def remove_main_tag(
        self,
        tag: str,
    ) -> bool:
        if tag not in self.main_tags:
            return False

        self.main_tags.remove(
            tag
        )

        self.save()

        return True

    # =============================
    # Lists
    # =============================

    def switch_list(
        self,
        name: str,
    ) -> bool:
        if name == self.active_list_name:
            return False

        set_active_list(
            self.data,
            name,
        )

        self._initialize_favorites()
        self.save()

        return True

    def create_list(
        self,
        name: str,
    ) -> KaomojiList:
        new_list = create_kaomoji_list(
            self.data,
            name,
        )

        self.data[
            "active_list"
        ] = new_list["name"]

        self._initialize_favorites()
        self.save()

        return new_list

    def rename_list(
        self,
        old_name: str,
        new_name: str,
    ) -> KaomojiList:
        renamed_list = rename_kaomoji_list(
            self.data,
            old_name,
            new_name,
        )

        self.save()

        return renamed_list

    def delete_list(
        self,
        name: str,
    ) -> bool:
        was_active = (
            name == self.active_list_name
        )

        delete_kaomoji_list(
            self.data,
            name,
        )

        if was_active:
            self._initialize_favorites()

        self.save()

        return was_active

    # =============================
    # Import / merge
    # =============================

    def import_as_new_list(
        self,
        imported_list: KaomojiList,
    ) -> KaomojiList:
        new_list = add_imported_list(
            self.data,
            imported_list,
        )

        self.data[
            "active_list"
        ] = new_list["name"]

        self._initialize_favorites()
        self.save()

        return new_list

    def merge_into_current_list(
        self,
        imported_list: KaomojiList,
    ) -> MergeReport:
        report = merge_kaomoji_lists(
            self.current_list,
            imported_list,
        )

        self.save()

        return report

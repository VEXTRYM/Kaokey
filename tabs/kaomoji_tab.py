from PySide6.QtWidgets import QWidget

from models import Kaomoji
from widgets.kaomoji_browser import KaomojiBrowser


class KaomojiTab(KaomojiBrowser):
    """Kaomoji browser embedded in the main tab widget."""

    def __init__(
        self,
        main_tags: list[str],
        kaomoji: list[Kaomoji],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            main_tags,
            kaomoji,
            parent,
        )

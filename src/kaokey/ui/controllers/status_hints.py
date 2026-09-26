from PySide6.QtCore import (
    QCoreApplication,
    QObject,
    QTimer,
)
from PySide6.QtWidgets import (
    QStatusBar,
    QTabWidget,
    QWidget,
)

from kaokey.ui.styling.style_constants import STATUS_HINT_INTERVAL


class StatusHintsController(QObject):
    """Owns the rotating status-bar hints for the main kaomoji tab."""

    def __init__(
        self,
        tabs: QTabWidget,
        kaomoji_tab: QWidget,
        status_bar: QStatusBar,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self.tabs = tabs
        self.kaomoji_tab = kaomoji_tab
        self.status_bar = status_bar

        self.hints: tuple[str, ...] = ()
        self.index = 0
        self.dismissed = True

        self.timer = QTimer(self)
        self.timer.setInterval(STATUS_HINT_INTERVAL)
        self.timer.timeout.connect(self.show_next)

        interaction_started = getattr(
            self.kaomoji_tab,
            "interaction_started",
            None,
        )

        if interaction_started is not None:
            interaction_started.connect(self.dismiss)

        self.tabs.currentChanged.connect(self.on_tab_changed)

        self.retranslate()

    @staticmethod
    def _tr(
        text: str,
    ) -> str:
        return QCoreApplication.translate(
            "MainWindow",
            text,
        )

    def build_hints(
        self,
    ) -> tuple[str, ...]:
        return (
            self._tr("Mouse: Left = Copy · Right = Favorite"),
            self._tr(
                "Keyboard: Tab = Section · "
                "Arrows = Navigate · "
                "Enter = Select · "
                "Type to search"
            ),
        )

    def retranslate(
        self,
    ) -> None:
        old_hints = self.hints
        current_message = self.status_bar.currentMessage()
        was_showing_hint = current_message in old_hints

        self.hints = self.build_hints()

        if was_showing_hint and not self.dismissed:
            self.index = 0
            self.status_bar.clearMessage()
            self.show_next()

    def set_enabled(
        self,
        enabled: bool,
    ) -> None:
        if enabled:
            self.dismissed = False
            self.index = 0
            self.show_next()
            self.timer.start()
            return

        self.dismiss()

    def show_next(
        self,
    ) -> None:
        if self.dismissed:
            return

        if self.tabs.currentWidget() is not self.kaomoji_tab:
            return

        current_message = self.status_bar.currentMessage()

        if current_message and current_message not in self.hints:
            return

        if not self.hints:
            return

        message = self.hints[self.index]
        self.status_bar.showMessage(message)

        self.index = (self.index + 1) % len(self.hints)

    def dismiss(
        self,
    ) -> None:
        if self.dismissed:
            return

        self.dismissed = True
        self.timer.stop()

        if self.status_bar.currentMessage() in self.hints:
            self.status_bar.clearMessage()

    def on_tab_changed(
        self,
        _index: int,
    ) -> None:
        if self.dismissed:
            return

        if self.tabs.currentWidget() is self.kaomoji_tab:
            self.show_next()
            return

        if self.status_bar.currentMessage() in self.hints:
            self.status_bar.clearMessage()

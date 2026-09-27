from PySide6.QtCore import (
    QByteArray,
    QMimeData,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QDrag,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QMouseEvent,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QWidget,
)

from kaokey.ui.styling.style_constants import (
    EDIT_MAIN_TAG_DRAG_PREVIEW_OPACITY,
    EDIT_MAIN_TAG_DROP_INDICATOR_WIDTH,
    KEYBOARD_FOCUS_BORDER_COLOR,
)
from kaokey.ui.styling.widget_styles import (
    style_edit_main_tag_layout,
    style_edit_main_tags_layout,
    style_edit_main_tags_scroll,
    style_main_tag_remove_button,
)

MAIN_TAG_MIME_TYPE = "application/x-kaokey-main-tag"


class _MainTagWidget(QWidget):
    remove_requested = Signal(str)

    def __init__(
        self,
        tag: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.tag = tag
        self.drag_start_position = None

        layout = QHBoxLayout(self)

        style_edit_main_tag_layout(layout)

        tag_label = QLabel(tag)

        tag_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

        remove_button = QPushButton("×")

        style_main_tag_remove_button(remove_button)

        remove_button.clicked.connect(
            lambda checked=False: self.remove_requested.emit(self.tag)
        )

        layout.addWidget(tag_label)
        layout.addWidget(remove_button)

    def mousePressEvent(
        self,
        event: QMouseEvent,
    ) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.position().toPoint()

        super().mousePressEvent(event)

    def mouseMoveEvent(
        self,
        event: QMouseEvent,
    ) -> None:
        if self.drag_start_position is None:
            super().mouseMoveEvent(event)
            return

        if not event.buttons() & Qt.MouseButton.LeftButton:
            self.drag_start_position = None
            super().mouseMoveEvent(event)
            return

        current_position = event.position().toPoint()

        if (
            current_position - self.drag_start_position
        ).manhattanLength() < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return

        mime_data = QMimeData()

        mime_data.setData(
            MAIN_TAG_MIME_TYPE,
            QByteArray(self.tag.encode("utf-8")),
        )

        drag = QDrag(self)

        drag.setMimeData(mime_data)

        source_pixmap = self.grab()
        drag_pixmap = QPixmap(source_pixmap.size())
        drag_pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(drag_pixmap)
        painter.setOpacity(EDIT_MAIN_TAG_DRAG_PREVIEW_OPACITY)
        painter.drawPixmap(
            0,
            0,
            source_pixmap,
        )
        painter.end()

        drag.setPixmap(drag_pixmap)
        drag.setHotSpot(self.drag_start_position)

        drag.exec(Qt.DropAction.MoveAction)

        self.drag_start_position = None


class _MainTagsDropWidget(QWidget):
    move_requested = Signal(str, int)

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setAcceptDrops(True)

        self.drop_indicator = QWidget(self)
        self.drop_indicator.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        self.drop_indicator.setStyleSheet(
            f"background-color: {KEYBOARD_FOCUS_BORDER_COLOR};"
        )
        self.drop_indicator.hide()

    def _tag_widgets(
        self,
    ) -> list[_MainTagWidget]:
        layout = self.layout()

        if layout is None:
            return []

        widgets: list[_MainTagWidget] = []

        for index in range(layout.count()):
            layout_item = layout.itemAt(index)

            if layout_item is None:
                continue

            widget = layout_item.widget()

            if isinstance(
                widget,
                _MainTagWidget,
            ):
                widgets.append(widget)

        return widgets

    def _drop_target(
        self,
        source_widget: _MainTagWidget,
        drop_x: float,
    ) -> tuple[int, int] | None:
        widgets = self._tag_widgets()

        if source_widget not in widgets:
            return None

        remaining_widgets = [
            widget
            for widget in widgets
            if widget is not source_widget
        ]

        target_index = len(remaining_widgets)

        for index, widget in enumerate(remaining_widgets):
            if drop_x < widget.geometry().center().x():
                target_index = index
                break

        if not remaining_widgets:
            indicator_x = source_widget.geometry().left()
        elif target_index == 0:
            indicator_x = remaining_widgets[0].geometry().left()
        elif target_index == len(remaining_widgets):
            indicator_x = remaining_widgets[-1].geometry().right() + 1
        else:
            left_edge = remaining_widgets[target_index - 1].geometry().right() + 1
            right_edge = remaining_widgets[target_index].geometry().left()

            indicator_x = (left_edge + right_edge) // 2

        return (
            target_index,
            indicator_x,
        )

    def _show_drop_indicator(
        self,
        indicator_x: int,
    ) -> None:
        widgets = self._tag_widgets()

        if not widgets:
            self.drop_indicator.hide()
            return

        top = min(widget.geometry().top() for widget in widgets)
        bottom = max(widget.geometry().bottom() for widget in widgets)

        indicator_left = indicator_x - EDIT_MAIN_TAG_DROP_INDICATOR_WIDTH // 2
        indicator_left = max(
            0,
            min(
                indicator_left,
                self.width() - EDIT_MAIN_TAG_DROP_INDICATOR_WIDTH,
            ),
        )

        self.drop_indicator.setGeometry(
            indicator_left,
            top,
            EDIT_MAIN_TAG_DROP_INDICATOR_WIDTH,
            bottom - top + 1,
        )
        self.drop_indicator.raise_()
        self.drop_indicator.show()

    def _hide_drop_indicator(
        self,
    ) -> None:
        self.drop_indicator.hide()

    def dragEnterEvent(
        self,
        event: QDragEnterEvent,
    ) -> None:
        source_widget = event.source()

        if (
            event.mimeData().hasFormat(MAIN_TAG_MIME_TYPE)
            and isinstance(
                source_widget,
                _MainTagWidget,
            )
        ):
            drop_target = self._drop_target(
                source_widget,
                event.position().x(),
            )

            if drop_target is not None:
                _, indicator_x = drop_target
                self._show_drop_indicator(indicator_x)

            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
            return

        self._hide_drop_indicator()
        event.ignore()

    def dragMoveEvent(
        self,
        event: QDragMoveEvent,
    ) -> None:
        source_widget = event.source()

        if (
            event.mimeData().hasFormat(MAIN_TAG_MIME_TYPE)
            and isinstance(
                source_widget,
                _MainTagWidget,
            )
        ):
            drop_target = self._drop_target(
                source_widget,
                event.position().x(),
            )

            if drop_target is not None:
                _, indicator_x = drop_target
                self._show_drop_indicator(indicator_x)

                event.setDropAction(Qt.DropAction.MoveAction)
                event.accept()
                return

        self._hide_drop_indicator()
        event.ignore()

    def dragLeaveEvent(
        self,
        event: QDragLeaveEvent,
    ) -> None:
        self._hide_drop_indicator()

        super().dragLeaveEvent(event)

    def dropEvent(
        self,
        event: QDropEvent,
    ) -> None:
        self._hide_drop_indicator()

        if not event.mimeData().hasFormat(MAIN_TAG_MIME_TYPE):
            event.ignore()
            return

        source_widget = event.source()

        if not isinstance(
            source_widget,
            _MainTagWidget,
        ):
            event.ignore()
            return

        widgets = self._tag_widgets()

        if source_widget not in widgets:
            event.ignore()
            return

        source_index = widgets.index(source_widget)

        drop_target = self._drop_target(
            source_widget,
            event.position().x(),
        )

        if drop_target is None:
            event.ignore()
            return

        target_index, _indicator_x = drop_target

        if target_index != source_index:
            self.move_requested.emit(
                source_widget.tag,
                target_index,
            )

        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()


class MainTagsEditor(QScrollArea):
    remove_requested = Signal(str)
    move_requested = Signal(str, int)

    def __init__(
        self,
        tags: list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        style_edit_main_tags_scroll(self)

        self.set_tags(tags)

    def set_tags(
        self,
        tags: list[str],
    ) -> None:
        old_widget = self.takeWidget()

        if old_widget is not None:
            old_widget.deleteLater()

        tags_widget = _MainTagsDropWidget()

        tags_layout = QHBoxLayout(tags_widget)

        style_edit_main_tags_layout(tags_layout)

        for tag in tags:
            tag_widget = _MainTagWidget(tag)

            tag_widget.remove_requested.connect(
                self.remove_requested.emit
            )

            tags_layout.addWidget(tag_widget)

        tags_widget.move_requested.connect(
            self.move_requested.emit
        )

        tags_widget.adjustSize()

        self.setWidget(tags_widget)

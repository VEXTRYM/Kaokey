from PySide6.QtCore import (
    QByteArray,
    QMimeData,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QDrag,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QMouseEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QWidget,
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
        drag.setPixmap(self.grab())
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

    def dragEnterEvent(
        self,
        event: QDragEnterEvent,
    ) -> None:
        if event.mimeData().hasFormat(MAIN_TAG_MIME_TYPE):
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
            return

        event.ignore()

    def dragMoveEvent(
        self,
        event: QDragMoveEvent,
    ) -> None:
        if event.mimeData().hasFormat(MAIN_TAG_MIME_TYPE):
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
            return

        event.ignore()

    def dropEvent(
        self,
        event: QDropEvent,
    ) -> None:
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

        layout = self.layout()

        if layout is None:
            event.ignore()
            return

        source_index = layout.indexOf(source_widget)

        if source_index < 0:
            event.ignore()
            return

        tag = source_widget.tag

        insertion_index = layout.count()
        drop_x = event.position().x()

        for index in range(layout.count()):
            layout_item = layout.itemAt(index)

            if layout_item is None:
                continue

            widget = layout_item.widget()

            if widget is None:
                continue

            if drop_x < widget.geometry().center().x():
                insertion_index = index
                break

        target_index = insertion_index

        if source_index < insertion_index:
            target_index -= 1

        target_index = max(
            0,
            min(
                target_index,
                layout.count() - 1,
            ),
        )

        if target_index != source_index:
            self.move_requested.emit(
                tag,
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

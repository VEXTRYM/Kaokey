from PySide6.QtCore import (
    QEvent,
    QObject,
)
from PySide6.QtGui import (
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QAbstractSpinBox,
    QComboBox,
    QWidget,
)


class NoWheelFilter(QObject):
    def eventFilter(
        self,
        watched: QObject,
        event: QEvent,
    ) -> bool:
        if event.type() != QEvent.Type.Wheel or not isinstance(
            event,
            QWheelEvent,
        ):
            return False

        if not isinstance(
            watched,
            (
                QComboBox,
                QAbstractSpinBox,
            ),
        ):
            return False

        scroll_area = self._find_scroll_area(watched)

        if scroll_area is not None:
            self._scroll_area(
                scroll_area,
                event,
            )

        # Consume the wheel event so the
        # control itself cannot change value.
        event.accept()

        return True

    def install_on(
        self,
        root: QWidget,
    ) -> None:
        # QComboBox covers Language and
        # Hotkey modifier/key controls.
        for combo_box in root.findChildren(QComboBox):
            combo_box.installEventFilter(self)

        # QAbstractSpinBox covers QSpinBox,
        # QDoubleSpinBox and similar numeric
        # controls, including future settings.
        for spin_box in root.findChildren(QAbstractSpinBox):
            spin_box.installEventFilter(self)

    @staticmethod
    def _find_scroll_area(
        widget: QWidget,
    ) -> QAbstractScrollArea | None:
        parent = widget.parentWidget()

        while parent is not None:
            if isinstance(
                parent,
                QAbstractScrollArea,
            ):
                return parent

            parent = parent.parentWidget()

        return None

    @staticmethod
    def _scroll_area(
        scroll_area: QAbstractScrollArea,
        event: QWheelEvent,
    ) -> None:
        scroll_bar = scroll_area.verticalScrollBar()

        # Touchpads may provide pixel-precise
        # scrolling instead of wheel steps.
        pixel_delta = event.pixelDelta().y()

        if pixel_delta != 0:
            scroll_bar.setValue(scroll_bar.value() - pixel_delta)
            return

        # A normal mouse wheel usually reports
        # 120 units for one wheel step.
        angle_delta = event.angleDelta().y()

        if angle_delta == 0:
            return

        steps = angle_delta / 120

        distance = int(steps * scroll_bar.singleStep() * 3)

        # Very small high-resolution wheel
        # deltas should still move the page.
        if distance == 0 and angle_delta != 0:
            distance = 1 if angle_delta > 0 else -1

        scroll_bar.setValue(scroll_bar.value() - distance)

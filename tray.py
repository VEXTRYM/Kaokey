from PySide6.QtCore import (
    QCoreApplication,
    QObject,
    Signal,
)

from PySide6.QtGui import (
    QAction,
    QIcon,
)

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMenu,
    QStyle,
    QSystemTrayIcon,
)


class TrayController(QObject):
    open_requested = Signal()
    close_requested = Signal()
    settings_requested = Signal()

    def __init__(
        self,
        window: QMainWindow,
    ) -> None:
        super().__init__(
            window
        )

        self.window = window

        self.tray_icon = QSystemTrayIcon(
            self
        )

        self.tray_icon.setIcon(
            self.tray_icon_for_window()
        )

        self.menu = QMenu(
            window
        )

        self.open_action = QAction(
            self.menu
        )

        self.close_action = QAction(
            self.menu
        )

        self.settings_action = QAction(
            self.menu
        )

        self.menu.addAction(
            self.open_action
        )

        self.menu.addAction(
            self.close_action
        )

        self.menu.addAction(
            self.settings_action
        )

        self.tray_icon.setContextMenu(
            self.menu
        )

        self.open_action.triggered.connect(
            self.open_requested.emit
        )

        self.close_action.triggered.connect(
            self.close_requested.emit
        )

        self.settings_action.triggered.connect(
            self.settings_requested.emit
        )

        self.tray_icon.activated.connect(
            self.on_activated
        )

        self.retranslate_ui()

    @staticmethod
    def is_available(
    ) -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()

    def tray_icon_for_window(
        self,
    ) -> QIcon:
        icon = self.window.windowIcon()

        if not icon.isNull():
            return icon

        app = QApplication.instance()

        if app is None:
            return QIcon()

        app_icon = app.windowIcon()

        if not app_icon.isNull():
            return app_icon

        return app.style().standardIcon(
            QStyle.StandardPixmap.SP_ComputerIcon
        )

    def show(
        self,
    ) -> None:
        self.tray_icon.show()

    def hide(
        self,
    ) -> None:
        self.tray_icon.hide()

    def retranslate_ui(
        self,
    ) -> None:
        translate = QCoreApplication.translate

        self.open_action.setText(
            translate(
                "TrayController",
                "Open Kaokey",
            )
        )

        self.close_action.setText(
            translate(
                "TrayController",
                "Close Kaokey",
            )
        )

        self.settings_action.setText(
            translate(
                "TrayController",
                "Settings",
            )
        )

        self.tray_icon.setToolTip(
            "Kaokey"
        )

    def on_activated(
        self,
        reason: QSystemTrayIcon.ActivationReason,
    ) -> None:
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        }:
            self.open_requested.emit()

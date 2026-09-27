from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from kaokey.config.constants import (
    APPLICATION_VERSION,
    GITHUB_REPOSITORY_URL,
)
from kaokey.ui.styling.widget_styles import (
    style_settings_layout,
    style_settings_row_layout,
    style_settings_scroll,
)


class AboutTab(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        # =========================
        # Main layout
        # =========================

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        style_settings_scroll(self.scroll_area)

        self.content_widget = QWidget()

        layout = QVBoxLayout(self.content_widget)
        style_settings_layout(layout)

        self.scroll_area.setWidget(self.content_widget)

        outer_layout.addWidget(self.scroll_area)

        # =========================
        # About
        # =========================

        self.about_group = QGroupBox()

        about_layout = QVBoxLayout(self.about_group)

        about_row = QHBoxLayout()
        style_settings_row_layout(about_row)

        self.version_label = QLabel()

        self.github_button = QPushButton()

        about_row.addWidget(self.version_label)
        about_row.addStretch(1)
        about_row.addWidget(self.github_button)

        about_layout.addLayout(about_row)

        layout.addWidget(self.about_group)

        # Future sections can be added here:
        #
        # self.support_group = QGroupBox()
        # layout.addWidget(self.support_group)

        # =========================
        # Signals
        # =========================

        self.github_button.clicked.connect(self.open_github)

        self.retranslate_ui()

    def open_github(
        self,
        _checked: bool = False,
    ) -> None:
        QDesktopServices.openUrl(
            QUrl(GITHUB_REPOSITORY_URL),
        )

    # =============================
    # Translation
    # =============================

    def retranslate_ui(
        self,
    ) -> None:
        self.about_group.setTitle(self.tr("About"))

        self.version_label.setText(
            self.tr("Version {version}").format(
                version=APPLICATION_VERSION,
            )
        )

        self.github_button.setText(self.tr("Visit GitHub"))
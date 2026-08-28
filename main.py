import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from constants import (
    APPLICATION_NAME,
    ICON_PATH,
    ORGANIZATION_NAME,
    SINGLE_INSTANCE_SERVER_NAME,
)
from i18n import TranslationManager
from main_window import MainWindow
from platforms.windows.startup import (
    STARTUP_LAUNCH_ARGUMENT,
)
from settings import SettingsManager
from single_instance import (
    SingleInstanceCoordinator,
)
from styles import KaokeyStyle


def main() -> None:
    start_hidden = (
        STARTUP_LAUNCH_ARGUMENT
        in sys.argv[1:]
    )

    app = QApplication([])

    app.setOrganizationName(
        ORGANIZATION_NAME
    )
    app.setApplicationName(
        APPLICATION_NAME
    )

    app.setWindowIcon(
        QIcon(
            str(
                ICON_PATH
            )
        )
    )

    single_instance = (
        SingleInstanceCoordinator(
            SINGLE_INSTANCE_SERVER_NAME
        )
    )

    if not single_instance.claim_primary_instance():
        return

    settings = (
        SettingsManager.create_default()
    )

    translations = TranslationManager(
        app
    )
    translations.apply_language(
        settings.language
    )

    app.setStyle(
        KaokeyStyle(
            app.style()
        )
    )

    window = MainWindow(
        settings,
        translations,
    )
    single_instance.activation_requested.connect(
        window.show_main_window
    )

    # A normal launch opens the main window. Windows autostart passes
    # --startup, in which case Kaokey quietly lives in the tray. If the tray
    # is unavailable, showing the window is safer than becoming unreachable.
    if (
        not start_hidden
        or window.tray_controller is None
    ):
        window.show()

    app.exec()


if __name__ == "__main__":
    main()

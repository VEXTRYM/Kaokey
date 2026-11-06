"""Read-only caret diagnostics: python -m kaokey.platforms.linux.diagnostics."""

import argparse
import logging
from dataclasses import asdict

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtDBus import QDBusConnection, QDBusInterface

from kaokey.platforms.linux.x11.popup_backend import X11PopupBackend
from kaokey.platforms.popup_backend import PopupContext


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect the focused application's caret without opening a window.")
    parser.add_argument("--delay", type=float, default=5, help="Seconds to switch to the target text field (default: 5).")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG, format="%(relativeCreated).0f ms %(name)s: %(message)s")
    app = QGuiApplication([])
    backend = X11PopupBackend(app)
    print(f"Qt display plugin: {app.platformName()}", flush=True)
    print(f"Capabilities: {asdict(backend.capabilities)}", flush=True)
    status = QDBusInterface("org.a11y.Bus", "/org/a11y/bus", "org.a11y.Status", QDBusConnection.sessionBus())
    print(f"AT-SPI status: IsEnabled={status.property('IsEnabled')} ScreenReaderEnabled={status.property('ScreenReaderEnabled')}", flush=True)
    for screen in app.screens():
        print(f"Screen {screen.name()}: geometry={screen.geometry().getRect()} scale={screen.devicePixelRatio()}", flush=True)
    print(f"Focus a text field within {args.delay:g} seconds. No text or window titles are read.", flush=True)

    def captured(context: PopupContext) -> None:
        print(f"Popup anchor (Qt coordinates; source is logged above): {context.caret_rect}", flush=True)
        # Leave enough time for a late accessibility reply to be logged too.
        QTimer.singleShot(2000, app.quit)

    def capture() -> None:
        window, pointer, process_id = backend._native_context()
        print(f"Foreground X11 window={window} PID={process_id} pointer={pointer}", flush=True)
        backend.capture_context_async(app.screens(), captured)

    QTimer.singleShot(max(0, round(args.delay * 1000)), capture)
    QTimer.singleShot(max(0, round(args.delay * 1000)) + 5000, app.quit)
    app.exec()
    backend.clear_hotkey()


if __name__ == "__main__":
    main()

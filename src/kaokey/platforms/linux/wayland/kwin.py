"""Optional KWin 6 compositor integration; no persistent desktop configuration.

Short-lived scripts move only this process's picker window. Calls are asynchronous and bounded; scripts and files are
removed after every response, failure, or timeout.
"""

import json
import logging
import os
import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import ClassInfo, QObject, QTimer, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtDBus import (
    QDBusConnection, QDBusMessage, QDBusPendingCallWatcher,
)

_LOG = logging.getLogger(__name__)
INTERFACE = "io.github.VEXTRYM.Kaokey.KWin"


@ClassInfo(**{"D-Bus Interface": INTERFACE})  # type: ignore[reportCallIssue, reportArgumentType]
class KWinBridge(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.bus = QDBusConnection.sessionBus()
        self.path = f"/io/github/VEXTRYM/Kaokey/KWin_{uuid.uuid4().hex}"
        self._pending: dict[str, tuple[Path, Callable[[dict], None]]] = {}
        interface = self.bus.interface()
        self.available = bool(
            QGuiApplication.platformName().startswith("wayland")
            and interface is not None
            and interface.isServiceRegistered("org.kde.KWin").value()
            and self.bus.registerObject(
                self.path, self, QDBusConnection.RegisterOption.ExportAllSlots,
            )
        )

    def _call(self, path: str, interface: str, member: str, arguments: list) -> QDBusMessage:
        message = QDBusMessage.createMethodCall("org.kde.KWin", path, interface, member)
        message.setArguments(arguments)
        return message

    def execute(self, body: str, callback: Callable[[dict], None]) -> None:
        if not self.available:
            callback({})
            return
        token = f"kaokey_{os.getpid()}_{uuid.uuid4().hex}"
        destination = json.dumps(self.bus.baseService())
        script = (
            "var result = {}; try { result = (function() {\n" + body
            + "\n})(); } catch (e) { result = {error: String(e)}; }\n"
            + f"callDBus({destination}, {json.dumps(self.path)}, {json.dumps(INTERFACE)}, "
            + f"'report', {json.dumps(token)}, JSON.stringify(result || {{}}));\n"
        )
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".js", prefix="kaokey-", delete=False) as stream:
                stream.write(script)
                path = Path(stream.name)
        except OSError:
            _LOG.debug("Cannot create KWin script", exc_info=True)
            callback({})
            return
        self._pending[token] = (path, callback)
        message = self._call("/Scripting", "org.kde.kwin.Scripting", "loadScript", [str(path), token])
        watcher = QDBusPendingCallWatcher(self.bus.asyncCall(message, 250), self)

        def loaded(watcher: QDBusPendingCallWatcher) -> None:
            reply = watcher.reply()
            watcher.deleteLater()
            if token not in self._pending:
                # A late load reply must not leave an orphaned script.
                self._unload(token)
                return
            values = reply.arguments()
            if reply.type() == QDBusMessage.MessageType.ErrorMessage or not values or int(values[0]) < 0:
                self.report(token, "{}")
                return
            run = self._call(f"/Scripting/Script{int(values[0])}", "org.kde.kwin.Script", "run", [])
            self.bus.asyncCall(run, 250)

        watcher.finished.connect(loaded)
        QTimer.singleShot(300, lambda: self.report(token, "{}"))

    @Slot(str, str)
    def report(self, token: str, payload: str) -> None:
        pending = self._pending.pop(token, None)
        if pending is None:
            return
        path, callback = pending
        self._unload(token)
        path.unlink(missing_ok=True)
        try:
            result = json.loads(payload)
        except (ValueError, TypeError):
            result = {}
        if not isinstance(result, dict) or "error" in result:
            _LOG.debug("KWin script failed: %s", result)
            result = {}
        callback(result)

    def _unload(self, token: str) -> None:
        self.bus.asyncCall(self._call("/Scripting", "org.kde.kwin.Scripting", "unloadScript", [token]))

    def close(self) -> None:
        self.available = False
        for token, (path, _) in list(self._pending.items()):
            self._unload(token)
            path.unlink(missing_ok=True)
        self._pending.clear()
        self.bus.unregisterObject(self.path)

    def place_at_cursor(self, title: str) -> None:
        """Place the picker at the compositor's cursor, constrained to its screen."""
        self.execute(f"""
            var w = workspace.windowList().find(w => w.pid === {os.getpid()}
                && w.caption === {json.dumps(title)} && !w.deleted);
            if (!w) return {{placed:false}};
            var p = workspace.cursorPos;
            var a = workspace.clientArea(KWin.PlacementArea, workspace.screenAt(p), workspace.currentDesktop);
            var g = w.frameGeometry;
            var x = Math.max(a.x, Math.min(p.x, a.x + a.width - g.width));
            var y = Math.max(a.y, Math.min(p.y, a.y + a.height - g.height));
            w.frameGeometry = {{x:x, y:y, width:g.width, height:g.height}};
            workspace.activeWindow = w;
            return {{placed:true}};
        """, lambda result: _LOG.debug('KWin cursor placement: %s', result))

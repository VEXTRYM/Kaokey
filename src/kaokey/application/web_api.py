"""Opt-in loopback bridge. All state access runs on the Qt GUI thread."""

import hmac
import json
import secrets
from urllib.parse import parse_qs, urlsplit

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QHostAddress, QTcpServer, QTcpSocket

from kaokey.application.app_state import AppState
from kaokey.persistence.list_io import export_list_data, import_list_data

API_PORT = 17654
MAX_BODY = 2 * 1024 * 1024
MAX_HEADERS = 8192


def website_origin(value: str) -> str:
    """Accept an exact HTTPS origin, or HTTP loopback for local development."""
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
        if (
            parsed.scheme not in {"https", "http"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query or parsed.fragment
            or (parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"})
        ):
            raise ValueError
        host = parsed.hostname.encode("idna").decode("ascii")
        if not all(c.isalnum() or c in ".-" for c in host):
            raise ValueError
        default = 443 if parsed.scheme == "https" else 80
        suffix = f":{port}" if port is not None and port != default else ""
        return f"{parsed.scheme}://{host}{suffix}"
    except (ValueError, UnicodeError) as error:
        raise ValueError("Enter the website origin, e.g. https://example.com (no page path).") from error


class WebApi(QObject):
    library_changed = Signal()

    def __init__(self, state: AppState, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.state = state
        self.server = QTcpServer(self)
        self.server.newConnection.connect(self._accept)
        self.origin = ""
        self.token = ""
        self._buffers: dict[QTcpSocket, bytearray] = {}

    @property
    def running(self) -> bool:
        return self.server.isListening()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.server.serverPort()}"

    def start(self, origin: str, port: int = API_PORT) -> None:
        normalized = website_origin(origin)
        self.stop()
        if not self.server.listen(QHostAddress.SpecialAddress.LocalHost, port):
            raise ValueError(f"Could not start website connection: {self.server.errorString()}")
        self.origin = normalized
        self.token = secrets.token_urlsafe(32)

    def stop(self) -> None:
        self.server.close()
        self.token = ""
        self.origin = ""
        for socket in list(self._buffers):
            socket.abort()
        self._buffers.clear()

    def _accept(self) -> None:
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            if socket is None:
                continue
            if len(self._buffers) >= 16:
                socket.abort()
                socket.deleteLater()
                continue
            socket.setReadBufferSize(MAX_BODY + MAX_HEADERS + 1)
            self._buffers[socket] = bytearray()
            timer = QTimer(socket)
            timer.setSingleShot(True)
            timer.timeout.connect(socket.abort)
            timer.start(15000)
            socket.readyRead.connect(lambda s=socket: self._read(s))
            socket.disconnected.connect(lambda s=socket: self._discard(s))
            self._read(socket)

    def _discard(self, socket: QTcpSocket) -> None:
        self._buffers.pop(socket, None)
        socket.deleteLater()

    def _reply(self, socket: QTcpSocket, status: int, data: object, cors: bool = False) -> None:
        self._buffers.pop(socket, None)
        body = b"" if status == 204 else json.dumps(data, ensure_ascii=False).encode("utf-8")
        reasons = {200: "OK", 201: "Created", 204: "No Content", 400: "Bad Request",
                   401: "Unauthorized", 403: "Forbidden", 404: "Not Found",
                   413: "Payload Too Large", 415: "Unsupported Media Type", 500: "Internal Server Error"}
        headers = [f"HTTP/1.1 {status} {reasons[status]}", "Connection: close",
                   "Content-Type: application/json; charset=utf-8", f"Content-Length: {len(body)}",
                   "Cache-Control: no-store", "X-Content-Type-Options: nosniff", "Vary: Origin"]
        if cors:
            headers += [f"Access-Control-Allow-Origin: {self.origin}",
                        "Access-Control-Allow-Methods: GET, POST, OPTIONS",
                        "Access-Control-Allow-Headers: Authorization, Content-Type",
                        "Access-Control-Allow-Private-Network: true"]
        socket.write(("\r\n".join(headers) + "\r\n\r\n").encode("ascii") + body)
        socket.disconnectFromHost()

    def _read(self, socket: QTcpSocket) -> None:
        buffer = self._buffers.get(socket)
        if buffer is None:
            return
        buffer.extend(socket.readAll().data())
        marker = buffer.find(b"\r\n\r\n")
        if marker < 0:
            if len(buffer) > MAX_HEADERS:
                self._reply(socket, 413, {"error": "Headers too large."})
            return
        cors = False
        try:
            if marker > MAX_HEADERS:
                self._reply(socket, 413, {"error": "Headers too large."})
                return
            lines = bytes(buffer[:marker]).decode("ascii").split("\r\n")
            method, target, version = lines[0].split(" ")
            if version != "HTTP/1.1" or not target.startswith("/") or target.startswith("//"):
                raise ValueError("Invalid request line.")
            headers: dict[str, str] = {}
            for line in lines[1:]:
                key, value = line.split(":", 1)
                key = key.lower()
                if key in headers or not key or key.strip() != key:
                    raise ValueError("Invalid or duplicate header.")
                headers[key] = value.strip()
            allowed_hosts = {f"127.0.0.1:{self.server.serverPort()}", f"localhost:{self.server.serverPort()}"}
            if headers.get("host") not in allowed_hosts:
                self._reply(socket, 403, {"error": "Invalid Host."})
                return
            origin = headers.get("origin")
            if origin is not None and origin != self.origin:
                self._reply(socket, 403, {"error": "Website not connected."})
                return
            cors = origin == self.origin
            if "transfer-encoding" in headers:
                raise ValueError("Transfer-Encoding is not supported.")
            length_text = headers.get("content-length", "0")
            if not length_text.isascii() or not length_text.isdecimal():
                raise ValueError("Invalid Content-Length.")
            length = int(length_text)
            if length > MAX_BODY:
                self._reply(socket, 413, {"error": "Maximum body size is 2 MiB."}, cors)
                return
            if method == "OPTIONS":
                if not cors:
                    self._reply(socket, 403, {"error": "Origin required."})
                else:
                    self._reply(socket, 204, None, True)
                return
            if not hmac.compare_digest(headers.get("authorization", ""), f"Bearer {self.token}"):
                self._reply(socket, 401, {"error": "Invalid connection token."}, cors)
                return
            if len(buffer) < marker + 4 + length:
                return
            if len(buffer) != marker + 4 + length:
                raise ValueError("Unexpected data after request.")
            body = bytes(buffer[marker + 4:])
            route = urlsplit(target)
            if method == "GET" and route.path == "/v1/lists":
                self._reply(socket, 200, {"api_version": 1, "active_list": self.state.active_list_name,
                                          "lists": self.state.list_names}, cors)
            elif method == "GET" and route.path == "/v1/export":
                names = parse_qs(route.query).get("list", [self.state.active_list_name])
                selected = self.state.find_list(names[0])
                if selected is None:
                    self._reply(socket, 404, {"error": "List not found."}, cors)
                else:
                    self._reply(socket, 200, export_list_data(selected), cors)
            elif method == "POST" and route.path == "/v1/import":
                if headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
                    self._reply(socket, 415, {"error": "Use application/json."}, cors)
                    return
                payload = json.loads(body.decode("utf-8"))
                result = self._import(payload)
                self._reply(socket, 201, result, cors)
            else:
                self._reply(socket, 404, {"error": "Unknown endpoint or method."}, cors)
        except (ValueError, UnicodeError, RecursionError) as error:
            message = "Invalid JSON or request." if isinstance(error, RecursionError) else str(error)
            self._reply(socket, 400, {"error": message}, cors)
        except Exception:
            # Never return file paths, library contents, or tracebacks to a website.
            self._reply(socket, 500, {"error": "Could not complete request."}, cors)

    def _import(self, payload: object) -> dict:
        if not isinstance(payload, dict) or payload.get("mode") not in ("new", "merge"):
            raise ValueError("Import mode must be new or merge.")
        imported = import_list_data(payload.get("data"))
        result = self.state.import_list_transaction(imported, payload["mode"])
        self.library_changed.emit()
        return result

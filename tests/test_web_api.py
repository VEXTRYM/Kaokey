import json
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from typing import Any

import pytest
from shiboken6 import delete

from kaokey.application.app_state import AppState
from kaokey.application.web_api import MAX_BODY, WebApi, website_origin
from kaokey.persistence.list_io import export_list_data, import_list_data
from kaokey.persistence.storage import create_default_data
from kaokey.ui.web_connection_dialog import WebConnectionDialog

ORIGIN = "https://example.com"
DOCUMENT = {"format_version": 1, "active_list": "Web", "lists": [{
    "name": "Web", "main_tags": ["happy"], "kaomoji": [{
        "name": "Smile", "text": "(◕‿◕)", "tags": ["happy"], "favorite": True,
    }],
}]}


@pytest.fixture
def api(qapp):
    saved = []
    state = AppState(create_default_data(), save_callback=lambda data: saved.append(deepcopy(data)))
    server = WebApi(state, qapp)
    server.start(ORIGIN, port=0)
    yield server, saved
    server.stop()
    delete(server)


def exchange(qapp, api, method="GET", path="/v1/lists", payload=None, *,
             token=None, origin: str | None = ORIGIN, extra=None, raw=None,
             fragment=False) -> tuple[int, str, Any]:
    port = api.server.serverPort()
    body = b"" if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Host": f"127.0.0.1:{port}", "Authorization": f"Bearer {api.token if token is None else token}",
               "Content-Type": "application/json", "Content-Length": str(len(body))}
    if origin is not None:
        headers["Origin"] = origin
    headers.update(extra or {})
    request = raw or ((f"{method} {path} HTTP/1.1\r\n" + "\r\n".join(
        f"{key}: {value}" for key, value in headers.items()) + "\r\n\r\n").encode() + body)

    def client():
        with socket.create_connection(("127.0.0.1", port), timeout=3) as connection:
            if fragment:
                connection.sendall(request[:20])
                time.sleep(0.02)
                connection.sendall(request[20:])
            else:
                connection.sendall(request)
            response = b""
            while chunk := connection.recv(65536):
                response += chunk
        head, data = response.split(b"\r\n\r\n", 1)
        return int(head.split(b" ")[1]), head.decode(), json.loads(data) if data else None

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(client)
        deadline = time.monotonic() + 4
        while not future.done() and time.monotonic() < deadline:
            qapp.processEvents()
            time.sleep(0.001)
        return future.result()


def test_http_roundtrip_and_merge(qapp, api):
    server, saved = api
    changes = []
    server.library_changed.connect(lambda: changes.append(True))
    status, headers, data = exchange(qapp, server, "POST", "/v1/import",
                                     {"mode": "new", "data": DOCUMENT}, fragment=True)
    assert status == 201 and data == {"mode": "new", "list": "Web"}
    assert saved[-1] == server.state.data
    assert server.state.kaomoji[0]["favorite"] is False
    assert changes == [True]
    status, headers, exported = exchange(qapp, server, path="/v1/export?list=Web")
    assert status == 200
    assert f"Access-Control-Allow-Origin: {ORIGIN}" in headers
    assert import_list_data(exported) == server.state.current_list
    status, _, data = exchange(qapp, server)
    assert status == 200 and data["active_list"] == "Web"
    status, _, data = exchange(qapp, server, "POST", "/v1/import", {"mode": "new", "data": exported})
    assert status == 201 and data["list"] == "Web(1)"
    status, _, data = exchange(qapp, server, "POST", "/v1/import", {"mode": "merge", "data": exported})
    assert status == 201 and data["added"] == 0
    status, _, data = exchange(qapp, server, path="/v1/export?list=missing")
    assert status == 404


def test_cors_and_auth(qapp, api):
    server, saved = api
    assert exchange(qapp, server, token="wrong")[0] == 401
    status, headers, _ = exchange(qapp, server, origin="https://evil.example")
    assert status == 403 and "Access-Control-Allow-Origin" not in headers
    assert exchange(qapp, server, origin="null")[0] == 403
    assert exchange(qapp, server, extra={"Host": "evil.example"})[0] == 403
    status, headers, _ = exchange(qapp, server, "OPTIONS", token="", extra={
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
        "Access-Control-Request-Private-Network": "true",
    })
    assert status == 204 and "Access-Control-Allow-Private-Network: true" in headers
    assert "Authorization, Content-Type" in headers
    assert exchange(qapp, server, origin=None)[0] == 200  # native clients still require token
    assert not saved


def test_validation_and_limits_leave_library_unchanged(qapp, api):
    server, saved = api
    before = deepcopy(server.state.data)
    for payload in [None, [], {"mode": "replace", "data": DOCUMENT},
                    {"mode": "new", "data": {}}, {"mode": "new", "data": {
                        **DOCUMENT, "format_version": 999}}]:
        assert exchange(qapp, server, "POST", "/v1/import", payload)[0] == 400
    assert exchange(qapp, server, "POST", "/v1/import", {}, extra={"Content-Type": "text/plain"})[0] == 415
    assert exchange(qapp, server, extra={"Content-Length": str(MAX_BODY + 1)})[0] == 413
    assert exchange(qapp, server, extra={"Transfer-Encoding": "chunked"})[0] == 400
    assert exchange(qapp, server, extra={"Content-Length": "-1"})[0] == 400
    assert server.state.data == before and not saved


def test_failed_save_is_atomic(qapp, api):
    server, _ = api
    before = server.state.data
    def fail(data):
        raise OSError("secret path")
    server.state._save_callback = fail
    status, _, data = exchange(qapp, server, "POST", "/v1/import", {"mode": "new", "data": DOCUMENT})
    assert status == 500 and "secret" not in data["error"]
    assert server.state.data is before and len(before["lists"]) == 1


def test_disconnect_rotates_token(qapp, api):
    server, _ = api
    token = server.token
    server.stop()
    assert not server.running and not server.token
    server.start(ORIGIN, port=0)
    assert server.token != token
    assert exchange(qapp, server, token=token)[0] == 401


def test_connection_dialog(qapp, api):
    server, _ = api
    dialog = WebConnectionDialog(server)
    assert dialog.token.text() == server.token
    assert not dialog.origin.isEnabled()
    dialog.toggle_connection()
    assert not server.running and dialog.token.text() == ""
    dialog.close()


@pytest.mark.parametrize("origin", ["https://example.com/page", "null", "file:///foo",
    "http://example.com", "https://user:pass@example.com", "https://example.com?x=1",
    "https://example.com:bad", "https://example.com\r\nInjected: yes"])
def test_reject_invalid_origin(origin):
    with pytest.raises(ValueError):
        website_origin(origin)


def test_normalize_origin_and_shared_document():
    assert website_origin(" https://EXAMPLE.com:443/ ") == ORIGIN
    assert website_origin("http://localhost:3000") == "http://localhost:3000"
    imported = import_list_data(DOCUMENT)
    assert export_list_data(imported)["lists"][0] == imported
    assert imported["kaomoji"][0].get("favorite") is False

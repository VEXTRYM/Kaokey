# Website import/export API

Kaokey provides an optional HTTP bridge on `http://127.0.0.1:17654`. It runs
inside the desktop application's Qt event loop, using the same implementation
on Windows and Linux (X11 and Wayland). No OS-specific protocol registration,
shell commands, background service, or additional dependency is required.

## Connect

1. Open **Lists → Website connection…** in Kaokey.
2. Enter the website's origin, e.g. `https://example.com`, and click **Connect**.
   HTTP is allowed only for `localhost` / `127.0.0.1` development origins.
3. Copy the displayed connection address and token into the website's integration.
4. Keep Kaokey running. **Disconnect** or quitting closes the listener and revokes
   the token. Restarting a connection creates a new token. The API is off on launch.

The website and app must run on the same device. The listener binds IPv4
loopback only. If the port is occupied, the dialog reports the error without
connecting to another process. A trusted origin alone does not grant access:
every request except the CORS preflight also needs `Authorization: Bearer TOKEN`.
Only the configured exact origin receives CORS permission. Native clients may
omit Origin but still need the token. Tokens are kept in memory only.

## HTTP contract (v1)

All responses are UTF-8 JSON; errors have the shape `{"error": "message"}`.
Requests use HTTP/1.1 with a loopback Host header, Content-Length for bodies,
and no Transfer-Encoding. Each connection handles one request and closes.

| Request | Result |
| --- | --- |
| `GET /v1/lists` | `200`: `{ "api_version": 1, "active_list": "Default", "lists": ["Default"] }` |
| `GET /v1/export` | `200`: active list as a portable Kaokey document |
| `GET /v1/export?list=NAME` | `200`: selected list; URL-encode NAME; `404` if absent |
| `POST /v1/import` | `201`: imports one document; body below |
| `OPTIONS /v1/...` | `204`: CORS preflight for the configured origin |

Import requires `Content-Type: application/json` and:

```json
{
  "mode": "new",
  "data": {
    "format_version": 1,
    "active_list": "Web",
    "lists": [{
      "name": "Web",
      "main_tags": ["happy"],
      "kaomoji": [{
        "name": "Smile",
        "text": "(◕‿◕)",
        "tags": ["happy"],
        "favorite": false
      }]
    }]
  }
}
```

`new` adds the list, generates a unique name if necessary, and makes it active.
Response: `{"mode":"new","list":"Web"}`.

`merge` merges into the list active when the request is handled, skips duplicate
kaomoji text, resolves name conflicts, and respects the main-tag limit.
Response: `{"mode":"merge","list":"Default","added":1,"main_tags_added":1}`.

The document is identical to the existing JSON file format and must contain
exactly one list. File and HTTP imports use the same validation and reset imported
favorites; exports omit personal favorite ordering. Imports are additive; the
API does not delete or replace the library. After saving, all active-list views
refresh immediately. Invalid documents and failed saves leave live data unchanged.

Limits: 2 MiB request body, 8 KiB headers, 16 incomplete requests, 15-second
connection timeout. Responses are not cached. Status codes: `400` invalid
request/document, `401` missing/wrong token, `403` disallowed Origin/Host,
`404` missing list or unknown route/method, `413` size limit, `415` wrong media
type, `500` operation/save failure. A failed network response after a completed
import is ambiguous: check `/v1/lists` before retrying `new`, which can create
another uniquely named list.

## Website integration example

This is the application-side contract; the website repository is not changed.
Collect the address and token from the user. Keep the token in page memory,
not a URL, analytics, logs, or persistent browser storage.

```js
// Values copied by the user from the desktop connection dialog.
const address = 'http://127.0.0.1:17654';
let token = ''; // supplied by the user

async function kaokey(path, payload) {
  const response = await fetch(address + path, {
    method: payload === undefined ? 'GET' : 'POST',
    credentials: 'omit',
    cache: 'no-store',
    headers: {
      Authorization: `Bearer ${token}`,
      ...(payload === undefined ? {} : { 'Content-Type': 'application/json' }),
    },
    ...(payload === undefined ? {} : { body: JSON.stringify(payload) }),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error);
  return result;
}

const lists = await kaokey('/v1/lists');
const document = await kaokey('/v1/export?list=' + encodeURIComponent(lists.active_list));
// Send a site-generated document to the app without a downloaded file:
await kaokey('/v1/import', { mode: 'new', data: document });
// Or: await kaokey('/v1/import', { mode: 'merge', data: document });
```

The site must allow `http://127.0.0.1:17654` in its CSP `connect-src` if it has
one. The bridge answers CORS and Private Network Access preflights. Browser
policies can still require the user to grant local-network access, or block it
in some browsers/managed environments. Show a useful connection error and keep
the existing JSON file import/export available as a fallback. Do not attempt to
bypass browser permission checks. Actual website/browser integration must be
verified separately with that website; this change covers the desktop side.

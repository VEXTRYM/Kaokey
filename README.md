# Kaokey

**A fast kaomoji picker for Windows and Linux.**

Kaokey lets you quickly find and insert kaomoji into the application you're currently using.

## Features

* **Global popup hotkey** — open Kaokey from almost anywhere with `Alt+K`
* **Quick insertion** — insert the selected kaomoji into the active application
* **Caret-aware popup** — the popup tries to appear near the current text cursor
* **Kaomoji library** — browse and manage your collection
* **Custom lists** — organize kaomoji into separate lists
* **Import and export** — move lists between installations using JSON files
* **Kaomoji constructor** — build your own kaomoji from individual parts
* **Configurable hotkey** — change the popup shortcut in Settings
* **System tray support** — keep Kaokey running without keeping the main window open
* **Start with your desktop** — optionally launch Kaokey automatically

## Download

Windows builds are available from [GitHub Releases](https://github.com/VEXTRYM/Kaokey/releases).

1. Download `Kaokey-v0.1.1-win64.zip`
2. Extract the archive
3. Run `Kaokey.exe`

> [!NOTE]
> Windows SmartScreen may show a warning because Kaokey is currently distributed without a code-signing certificate.

No Python installation is required when using the packaged Windows release.

## Usage

1. Start Kaokey.
2. Focus a text field in another application.
3. Press `Alt+K`.
4. Select a kaomoji.
5. Kaokey inserts it into the active application.

The default `Alt+K` shortcut can be changed in **Settings**.

Kaokey can also remain minimized to the system tray and start automatically
with your desktop session.

## Running from source

Kaokey is written in Python using PySide6 and Qt.

Clone the repository:

```sh
git clone https://github.com/VEXTRYM/Kaokey.git
cd Kaokey
```

Create and activate a virtual environment:

```sh
python -m venv .venv
# Linux: source .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
```

Install the dependencies:

```sh
python -m pip install -e .
```

Run Kaokey:

```sh
kaokey
```

On Linux, install your distribution's `libatspi` runtime library and the Qt
display plugin dependencies. X11 also needs `libX11` for the global shortcut.
Wayland uses the desktop's **GlobalShortcuts portal**, which requires
`xdg-desktop-portal` and a portal backend that implements that interface.
AT-SPI accessibility is used for text insertion in both sessions.

On Linux, install the desktop launcher before using the Wayland global
shortcut. The portal uses its desktop ID to identify Kaokey:

```sh
install -Dm644 packaging/linux/io.github.VEXTRYM.Kaokey.desktop \
  ~/.local/share/applications/io.github.VEXTRYM.Kaokey.desktop
```

The launcher runs the `kaokey` command, so it must be on the desktop session's
`PATH`. For a virtual environment, edit its `Exec` line to use the absolute
path to `.venv/bin/kaokey`. Restart Kaokey after installing the launcher.

## Building the Windows executable

Install the development dependencies:

```powershell
python -m pip install -r requirements-dev.txt
```

This also installs the Linux portal dependency on Windows so Pylance can check
every platform module. Select the repository's `.venv` as the Python interpreter
in VS Code. Run the tests and type check with:

```sh
python -m pytest -q
pyright
```

Build with PyInstaller:

```powershell
python -m PyInstaller --clean Kaokey.spec
```

The resulting executable will be created at:

```text
dist\Kaokey.exe
```

See [PACKAGING.md](PACKAGING.md) for additional packaging information.

## Data

Kaokey does not require an account or an online service.

The kaomoji library is stored locally at:

```text
%APPDATA%\Kaokey\kaomoji.json
```

On Linux it is stored at `~/.local/share/Kaokey/kaomoji.json`, or under
`$XDG_DATA_HOME/Kaokey/kaomoji.json` when `XDG_DATA_HOME` is set.

Application settings are also stored locally.

## Platform support

Kaokey supports Windows and Linux X11/Wayland sessions. On X11 it registers a
global shortcut with XGrabKey and positions the popup near the text caret when
AT-SPI provides its location. On Wayland the desktop's GlobalShortcuts portal
manages the shortcut and the compositor positions the popup. The desktop may
ask you to approve or choose a shortcut.

On either Linux session, direct insertion works when the target application
exposes an editable AT-SPI text field. Otherwise Kaokey copies the selected
kaomoji to the clipboard. If the GlobalShortcuts portal is unavailable, open
Kaokey from its launcher and use the main window. The Start with system setting
uses XDG autostart on Linux.

## License

Kaokey is free software licensed under the **GNU General Public License version 3 only** (`GPL-3.0-only`).

Copyright © 2026 VEXTRYM.

See [LICENSE](LICENSE) for the full license text.

Kaokey includes third-party open-source software. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and the [`licenses`](licenses/) directory for additional licensing information.

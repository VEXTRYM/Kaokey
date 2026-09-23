# Kaokey

**A fast kaomoji picker for Windows.**

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
* **Start with Windows** — optionally launch Kaokey automatically

## Download

Kaokey currently targets **Windows**.

Download the latest version from [GitHub Releases](https://github.com/VEXTRYM/Kaokey/releases).

1. Download `Kaokey-v0.1.0-win64.zip`
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

Kaokey can also remain minimized to the system tray and start automatically with Windows.

## Running from source

Kaokey is written in Python using PySide6 and Qt.

Clone the repository:

```powershell
git clone https://github.com/VEXTRYM/Kaokey.git
cd Kaokey
```

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the dependencies:

```powershell
python -m pip install -r requirements.txt
python -m pip install -e .
```

Run Kaokey:

```powershell
python -m kaokey.main
```

## Building the Windows executable

Install the development dependencies:

```powershell
python -m pip install -r requirements-dev.txt
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

Application settings are also stored locally.

## Platform support

Kaokey currently supports **Windows only**.

Several core features rely on Windows-specific functionality, including:

* global hotkeys
* active-window interaction
* text insertion
* caret detection
* startup integration

Support for other operating systems is not currently provided.

## License

Kaokey is free software licensed under the **GNU General Public License version 3 only** (`GPL-3.0-only`).

Copyright © 2026 VEXTRYM.

See [LICENSE](LICENSE) for the full license text.

Kaokey includes third-party open-source software. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and the [`licenses`](licenses/) directory for additional licensing information.

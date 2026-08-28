# Kaokey

Kaokey is a desktop kaomoji keyboard built with Python and PySide6.

It is inspired by the native Windows emoji/kaomoji picker, but adds a reusable
library, favorites, search, custom lists, a kaomoji constructor, configurable
window/popup behavior, and automatic insertion into the currently focused
application.

## Status

Kaokey is currently in pre-release development. The core application is
working and the next milestone is the first packaged Windows executable.

## Features

- Global popup hotkey with a configurable modifier/key combination
- Automatic kaomoji insertion into the previously focused application
- Native insertion support for Windows Edit/RichEdit controls
- Clipboard fallback only when automatic insertion fails
- Search, favorites, main-tag filters, and keyboard navigation
- Multiple kaomoji lists with create, rename, delete, activate, import, export,
  and merge workflows
- Kaomoji constructor with a Unicode symbol palette
- Edit mode for existing kaomoji
- Responsive main and popup grids
- Configurable main-window and popup sizes
- Optional trailing space after automatic insertion
- System tray integration
- Optional start-with-Windows behavior
- Single-instance application behavior
- Unicode font fallback for the scripts used by the bundled kaomoji library
- Bundled Windows-style default list with 353 unique kaomoji

## Platform

Windows is the primary supported platform at the moment. Windows-specific code
is isolated under `platforms/windows/` so platform-independent parts of the
application can remain reusable.

## Requirements

- Python 3.14 is the current development environment
- PySide6 6.11.2

Runtime dependencies are listed in `requirements.txt`.
Development and packaging dependencies are listed in `requirements-dev.txt`.

## Run from source

Create a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install runtime dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Run Kaokey:

```powershell
python main.py
```

The default popup hotkey is:

```text
Alt + K
```

It can be changed in **Settings → Popup hotkey**.

## Development setup

Install the development dependencies:

```powershell
python -m pip install -r requirements-dev.txt
```

Run the test suite:

```powershell
python -m pytest
```

## Project structure

```text
Kaokey/
├─ main.py
├─ main_window.py
├─ app_state.py
├─ app_paths.py
├─ constants.py
├─ settings.py
├─ storage.py
├─ list_io.py
├─ library.py
├─ unicode_fonts.py
├─ data/
│  ├─ kaomoji.json
│  └─ constructor_symbols.json
├─ resources/
│  ├─ icons/
│  │  └─ kaokey.ico
│  └─ translations/
├─ tabs/
├─ widgets/
├─ platforms/
│  └─ windows/
└─ tests/
```

## Application data

The files inside the repository are application resources and defaults.
User-editable library data is stored separately in the user's application-data
directory.

On Windows, Kaokey stores the user's library under:

```text
%APPDATA%\Kaokey\kaomoji.json
```

This separation is important for packaged builds: updating or replacing the
application must not overwrite the user's custom lists, favorites, or edits.

## Default kaomoji library

`data/kaomoji.json` is the seed used for a new user profile. It contains the
bundled Default list.

A standalone importable copy can also be kept as:

```text
data/Windows Default.json
```

The storage-library JSON and exported-list JSON intentionally use different
container formats.

## Packaging

The first Windows release will be built with PyInstaller. Packaging files such
as `Kaokey.spec` are intended to be committed to Git; only generated `build/`
and `dist/` directories are ignored.

## License

A license has not been selected yet. Add a `LICENSE` file before publishing a
public release if you want others to have explicit permission to use, modify,
or redistribute the source.

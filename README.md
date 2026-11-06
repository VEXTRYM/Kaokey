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
* **Text ench** — create up to 24 copyable Unicode styles and decorations from your text
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

For fancy text, open **Text ench**, enter text, press **Enchance**, then use
**Copy** beside the version you want. This generator runs locally.

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
display plugin dependencies. X11 also needs `libX11` for the global shortcut
and `libXtst` for automatic paste.
Wayland uses the desktop's **GlobalShortcuts portal**, which requires
`xdg-desktop-portal` and a portal backend that implements that interface.
AT-SPI accessibility supplies caret locations and Wayland text insertion.

For Debian 13 with an X11 desktop such as XFCE, install the runtime libraries
before following the virtual environment instructions above:

```sh
sudo apt install python3-venv at-spi2-core libatspi2.0-0t64 libx11-6 libxtst6 \
  libxcb-cursor0 libxkbcommon-x11-0
```

After updating the source, fully quit the running Kaokey from its tray menu
and launch `.venv/bin/python -m kaokey.main` again. Launching a second copy only activates the
existing process; it does not load the updated code.

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

Libraries and exported lists use the same versioned JSON structure with
`format_version`, `active_list`, and `lists` fields. An exported individual
list is represented as a library containing exactly one list. Legacy JSON
layouts are no longer imported or migrated.

## Platform support

Kaokey supports Windows and Linux X11/Wayland sessions. On X11 it registers a
global shortcut with XGrabKey and positions the popup near the text caret when
AT-SPI provides its location, accounting for display scaling. If no usable
caret location is available, it opens near the mouse pointer, clamped to the
screen's work area. The foreground X11 window is captured immediately, so
insertion still works when accessibility is unavailable or times out.

X11 insertion restores focus to the captured application and sends
`Shift+Insert` through XTEST. It puts the selected Unicode text on both the
clipboard and the X11 primary selection, covering editors, browsers, and
terminals that use either selection for paste. This replaces those clipboard
contents. Kaokey verifies target focus before sending the shortcut and then
returns focus to the picker for repeated insertion. Applications must support
`Shift+Insert` to use this path. If XTEST is unavailable, it tries AT-SPI
EditableText insertion instead.

On Wayland the desktop's GlobalShortcuts portal
manages the shortcut and the compositor positions the popup. The desktop may
ask you to approve or choose a shortcut.

Wayland direct insertion requires the target application to expose an editable
AT-SPI text field. When automatic insertion is unavailable, Kaokey copies the
selected kaomoji to the clipboard. If the GlobalShortcuts portal is unavailable, open
Kaokey from its launcher and use the main window. The Start with system setting
uses XDG autostart on Linux.

The X11 popup regression tests can run without pytest or a desktop connection:

```sh
.venv/bin/python -m unittest discover -s tests -p test_x11_popup.py -v
```

For a desktop check, focus a text field in Mousepad or a browser, press `Alt+K`,
and insert a kaomoji twice without closing the picker. Repeat in a terminal
with an empty prompt, and near each screen edge. The text should appear in
the original field and the picker should retain keyboard focus after each
insertion. Apps without caret accessibility use mouse-relative placement.

X11 opens the picker after you release the shortcut keys, so GTK applications
have regained text focus before Kaokey queries their caret. Placement includes
the window frame and uses the same small caret gap above and below.

When its shortcut is registered, Kaokey requests toolkit accessibility through
the desktop's `org.a11y.Status.IsEnabled` property. Firefox and Chromium use
this setting to expose their accessibility trees. The `ScreenReaderEnabled`
setting is left unchanged. A browser started with accessibility disabled may
need to be fully closed and reopened after starting Kaokey.

For Chromium, Kaokey also requests the active window's accessibility metadata
to activate its web-content tree, and waits within the existing capture
deadline if that tree is still initializing. Focused text containers without
an insertion point are skipped in favor of the actual text field. Collapsed
text ranges supply caret bounds for empty fields and positions after a newline
when character bounds are unavailable.

To diagnose a caret-location problem on the actual desktop, run:

```sh
bash packaging/linux/diagnose-caret.sh
```

Switch to the affected application and focus the text field within eight
seconds. The report is written to `caret-diagnostics.log` in the repository;
it contains positions and accessibility metadata, without reading text or
window titles.

To keep separate browser captures, pass the browser name:

```sh
bash packaging/linux/diagnose-caret.sh firefox
bash packaging/linux/diagnose-caret.sh chrome
```

Focus a text field inside the browser page during each capture. These write
`caret-firefox.log` and `caret-chrome.log`. The diagnostic itself does not change
desktop accessibility settings; start Kaokey first to enable browser support.

The browser regressions can also run without pytest:

```sh
.venv/bin/python -m unittest discover -s tests -p test_browser_caret.py -v
```

## License

Kaokey is free software licensed under the **GNU General Public License version 3 only** (`GPL-3.0-only`).

Copyright © 2026 VEXTRYM.

See [LICENSE](LICENSE) for the full license text.

Kaokey includes third-party open-source software. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and the [`licenses`](licenses/) directory for additional licensing information.

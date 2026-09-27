# Kaokey Windows packaging

Kaokey is packaged as a **one-file, windowed Windows executable** with
PyInstaller.

Output:

```text
dist\Kaokey.exe
```

## Why one-file

For Windows releases, one-file keeps distribution simple: the user receives
one `Kaokey.exe`.

At runtime PyInstaller extracts bundled read-only files to its temporary
directory. Kaokey already handles this through `app_paths.resource_root()`.
Writable user data is kept separately under:

```text
%APPDATA%\Kaokey\kaomoji.json
```

Therefore changes to lists, favorites, and custom kaomoji are not written back
into the executable.

## Included resources

`Kaokey.spec` explicitly bundles:

```text
src\kaokey\resources\data\kaomoji.json
src\kaokey\resources\data\constructor_symbols.json
src\kaokey\resources\translations\
src\kaokey\resources\icons\kaokey.ico
```

PyInstaller's PySide6 hooks collect the required Qt/PySide6 runtime libraries
and plugins.

## Install build dependencies

From the project root, with the virtual environment active:

```powershell
python -m pip install -r requirements-dev.txt
```

Check versions:

```powershell
python --version
python -m PyInstaller --version
```

## Build

Run:

```powershell
python -m PyInstaller --clean Kaokey.spec
```

Before packaging, verify that the bundled Default library exists at
`src\kaokey\resources\data\kaomoji.json` and is not empty.

## Build output

Generated files are placed under:

```text
build\
dist\
```

Both are ignored by Git.

The distributable file is:

```text
dist\Kaokey.exe
```

## Smoke test

Before testing the executable, completely exit any source-mode Kaokey process.
The single-instance coordinator should not have another Kaokey instance alive.

Test these items:

1. **Normal launch**
   - Run `dist\Kaokey.exe`.
   - Main window opens.
   - Application/tray/window icon is Kaokey's icon.
   - No console window opens.

2. **Bundled Default library / clean profile**
   - Exit Kaokey.
   - Back up:
     `%APPDATA%\Kaokey\kaomoji.json`
   - Remove the active user copy.
   - Launch `dist\Kaokey.exe`.
   - A new `%APPDATA%\Kaokey\kaomoji.json` is created.
   - `Default` contains the bundled Windows-style kaomoji set instead of an
     empty list.
   - Restore the backup after the test if needed.

3. **Persistence**
   - Create a list or favorite a kaomoji.
   - Exit and relaunch the packaged executable.
   - The change remains.

4. **Popup hotkey**
   - Default `Alt+K` opens the popup.
   - Change the hotkey in Settings.
   - The new hotkey works immediately.
   - Restart Kaokey; the configured hotkey still works.
   - Try a combination already owned by another application and verify Kaokey
     keeps the previous working hotkey.

5. **Automatic insertion**
   - Notepad.
   - Chrome.
   - Firefox.
   - VS Code.
   - Any other applications previously used during development.
   - Successful automatic insertion must not overwrite the clipboard.
   - If automatic insertion fails, clipboard fallback still works.

6. **Popup positioning**
   - Verify caret positioning in Chrome/Firefox/Notepad.
   - Verify below/above placement near screen edges.
   - Verify the configured popup size remains fixed.

7. **Unicode**
   - Constructor.
   - Main Kaomoji tab.
   - Edit tab.
   - Status bar.
   - Hover tooltips.
   - In particular verify symbols such as:
     `ᗝ ᗜ ᗣ ᗕ ᗒ`

8. **Tray**
   - Closing the main window hides it to tray.
   - Left-click tray icon restores it.
   - Right-click menu remains:
     `Open Kaokey / Close Kaokey / Settings`.

9. **Single instance**
   - Keep Kaokey running.
   - Launch `dist\Kaokey.exe` again.
   - No second process/window should remain; the existing main window should
     be restored.

10. **Start with Windows**
    - Enable the setting.
    - Inspect the Startup-folder shortcut.
    - For the packaged build its target should be `Kaokey.exe` with:
      `--startup`
    - Launch the shortcut manually once.
    - Kaokey should start hidden in the tray.
    - A normal second launch should restore the existing hidden instance.

11. **Executable metadata**
    - Right-click `dist\Kaokey.exe` → Properties → Details.
    - Product name: `Kaokey`
    - Product version: `0.1.1`
    - File version: `0.1.1.0`

## Git after successful build work

The generated `build/` and `dist/` directories stay untracked.

Release preparation changes should be committed before tagging.

After the packaged build passes the smoke test, create the release tag:

```powershell
git tag -a v0.1.1 -m "Kaokey v0.1.1"
git push origin v0.1.1
```

Do not tag the release until the packaged executable has passed the smoke
tests.

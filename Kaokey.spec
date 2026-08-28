# -*- mode: python ; coding: utf-8 -*-

# Kaokey Windows one-file build.
#
# Build from the project root:
#     python -m PyInstaller --clean --noconfirm Kaokey.spec
#
# Read-only application resources are collected into the bundle. At runtime,
# app_paths.resource_root() resolves PyInstaller's sys._MEIPASS extraction
# directory, while writable user data remains under %APPDATA%\Kaokey.

datas = [
    ("data/kaomoji.json", "data"),
    ("data/constructor_symbols.json", "data"),
    (
        "resources/translations",
        "resources/translations",
    ),
    (
        "resources/icons/kaokey.ico",
        "resources/icons",
    ),
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(
    a.pure,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Kaokey",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="resources/icons/kaokey.ico",
    version="version_info.txt",
)

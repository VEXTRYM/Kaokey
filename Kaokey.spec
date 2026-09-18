# -*- mode: python ; coding: utf-8 -*-

datas = [
    (
        "src/kaokey/resources/data/kaomoji.json",
        "kaokey/resources/data",
    ),
    (
        "src/kaokey/resources/data/constructor_symbols.json",
        "kaokey/resources/data",
    ),
    (
        "src/kaokey/resources/translations",
        "kaokey/resources/translations",
    ),
    (
        "src/kaokey/resources/icons/kaokey.ico",
        "kaokey/resources/icons",
    ),
]

a = Analysis(
    ["src/kaokey/main.py"],
    pathex=["src"],
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
    icon="src/kaokey/resources/icons/kaokey.ico",
    version="version_info.txt",
)
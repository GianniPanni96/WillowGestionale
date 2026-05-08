# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path(SPECPATH)
datas = [(str(project_root / "Data"), "Data")]
icon_path = project_root / "Data" / "images" / "WillowLogo.icns"


a = Analysis(
    ['MainQT.py'],
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
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    name='WillowGestionale-QT',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    exclude_binaries=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path) if icon_path.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='WillowGestionale-QT',
)

app = BUNDLE(
    coll,
    name='WillowGestionale-QT.app',
    icon=str(icon_path) if icon_path.exists() else None,
    bundle_identifier='com.willow.gestionale.qt',
)

# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path(SPECPATH)
datas = [(str(project_root / "Data"), "Data")]
icon_path = project_root / "Data" / "images" / "WillowLogo.ico"


a = Analysis(
    ['MainQT.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['six', 'six.moves', 'six.moves._thread'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(project_root / 'pyinstaller_hooks' / 'pyi_rth_six_shiboken_fix.py')],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='WillowGestionale-QT',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path) if icon_path.exists() else None,
)

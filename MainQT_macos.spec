# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

project_root = Path(SPECPATH)
sys.path.insert(0, str(project_root))
from build_version import resolve_version

_version = resolve_version()
print(f"[spec] Building WillowGestionale (macOS) {_version.semver}")

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
    name=f'WillowGestionale_{_version.file_name_tag}',
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
    name=f'WillowGestionale_{_version.file_name_tag}',
)

app = BUNDLE(
    coll,
    name=f'WillowGestionale_{_version.file_name_tag}.app',
    icon=str(icon_path) if icon_path.exists() else None,
    bundle_identifier='com.willow.gestionale.qt',
    version=_version.semver,
)

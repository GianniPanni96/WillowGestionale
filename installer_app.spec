# -*- mode: python ; coding: utf-8 -*-

# Spec PyInstaller per l'installer del gestionale Willow.
#
# Layout post-migrazione: Data/ e Patches/ NON vengono bundled nell'exe.
# L'installer le cerca accanto a sys.executable a runtime; cosi' il pacchetto
# di distribuzione finale (dist/WillowGestionale-vX.Y.Z/) puo' tenere
# installer.exe + WillowGestionale_X_Y.exe + Data/ + Patches/ tutti allo
# stesso livello, e l'installer si limita a copiare i file dal package alla
# install folder.
#
# Build:
#     pyinstaller installer_app.spec --noconfirm
# Produce dist/installer_app/installer_app.exe + _internal/ (mode onedir).

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

from pathlib import Path
import sys

project_root = Path(SPECPATH)
sys.path.insert(0, str(project_root))


hiddenimports = (
    collect_submodules('DatabaseCreation')
    + collect_submodules('customtkinter')
    + [
        'Model',
        'Gestionale_Enums',
        'Utils.App_paths',
        'PatchLauncher',
    ]
)

# customtkinter carica i suoi temi (JSON) e gli asset font in modo dinamico:
# senza collect_data_files PyInstaller li perde e l'avvio fallisce con
# "FileNotFoundError" sui file dei temi anche se l'import statico funziona.
datas = collect_data_files('customtkinter')


a = Analysis(
    ['Installer\\installer_app.py'],
    pathex=['.', '.\\Installer'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='installer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    exclude_binaries=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / 'Data' / 'images' / 'WillowLogo.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='installer',
)

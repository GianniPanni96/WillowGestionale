# -*- mode: python ; coding: utf-8 -*-
#
# Spec per buildare fix_taxes_books_2025.py come exe standalone da usare
# come patch nell'installer (Patch v140/).
#
# Questo file si trova in: Patches/Patch v140/
# release.ps1 lo scopre automaticamente e lo builda durante la release.
# L'exe prodotto viene copiato in:
#   <WillowGestionale_installer>/Patches/Patch v140/fix_taxes_books_2025.exe
#
# patchLauncher imposta GESTIONALE_DB_PATH e GESTIONALE_INSTALLATION_PATH
# prima di avviare l'exe, quindi get_runtime_paths() li legge correttamente.

from pathlib import Path

# SPECPATH e' la dir dello spec (Patches/Patch v140/); la root e' due livelli su.
spec_dir = Path(SPECPATH)
project_root = spec_dir.parent.parent

a = Analysis(
    [str(spec_dir / "fix_taxes_books_2025.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[],
    hiddenimports=[
        # ConfigManagers carica i sotto-moduli dinamicamente tramite __init__
        "ConfigManagers.config_manager",
        "ConfigManagers.config_models",
        "ConfigManagers.app_settings_manager",
        "ConfigManagers.catalogs_manager",
        "ConfigManagers.fiscal_rules_manager",
        "ConfigManagers.historical_financial_data_manager",
        "ConfigManagers.recurring_expenses_manager",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Esclude tutto Qt/PySide6 — non serve la GUI
        "PySide6",
        "PySide6.QtWidgets",
        "PySide6.QtCore",
        "PySide6.QtGui",
        # Esclude librerie pesanti non usate da questo script
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "sklearn",
        "PIL",
        "cv2",
        "requests",
        "pycryptodome",
        "Crypto",
    ],
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
    name="fix_taxes_books_2025",
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
    icon=None,
)

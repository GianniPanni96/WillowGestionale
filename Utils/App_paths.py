import os
import sys
import ctypes
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn


APP_NAME = "WillowGestionale"
INSTALLATION_PATH_ENV_VAR = "GESTIONALE_INSTALLATION_PATH"
DB_PATH_ENV_VAR = "GESTIONALE_DB_PATH"

WINDOWS_DEFAULT_INSTALL_ROOT = Path(r"C:\Program Files\WillowGestionale")


@dataclass(frozen=True)
class RuntimePaths:
    storage_root: Path    # writable data root: db, config, books, backups
    install_root: Path    # read-only install root: exe, Data/
    db_file: Path
    config_file: Path
    books_dir: Path
    backups_dir: Path
    resource_root: Path   # alias for install_root (backward compatibility)
    data_dir: Path
    images_dir: Path


def is_macos() -> bool:
    return sys.platform == "darwin"


def is_windows() -> bool:
    return os.name == "nt"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _default_data_root() -> Path:
    """Platform-appropriate default for writable user data."""
    if is_macos():
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if is_windows():
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            return Path(local_appdata) / APP_NAME
        return Path.home() / "AppData" / "Local" / APP_NAME
    return Path.home() / f".{APP_NAME}"


def _is_usable_writable_root(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    expected_entries = ("gestionale.db", "app_config.json", "Books", "Backups")
    return any((path / entry).exists() for entry in expected_entries)


def _is_usable_install_root(path: Path) -> bool:
    return path.exists() and path.is_dir() and (path / "Data").exists()


def _show_error_and_exit(title: str, message: str) -> NoReturn:
    """Show an error popup and terminate the entire process (all threads)."""
    if is_windows():
        try:
            ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
        except Exception:
            pass
    print(message, file=sys.stderr)
    os._exit(1)


def _resolve_writable_root() -> Path:
    """
    Resolve the writable data directory (gestionale.db, config, Books, Backups).
    Priority: platform default path → GESTIONALE_DB_PATH env var → fatal error.
    In dev (non-frozen) mode, falls back to project root only if no usable path is found.
    """
    default_root = _default_data_root()
    env_value = os.environ.get(DB_PATH_ENV_VAR)
    env_root = Path(env_value).expanduser() if env_value else None

    if _is_usable_writable_root(default_root):
        return default_root

    if env_root and _is_usable_writable_root(env_root):
        return env_root

    if not is_frozen():
        return _project_root()

    env_display = env_value or "<non valorizzata>"
    _show_error_and_exit(
        APP_NAME,
        (
            "Impossibile individuare la cartella dati del gestionale.\n\n"
            f"Percorso predefinito verificato:\n{default_root}\n\n"
            f"Variabile d'ambiente {DB_PATH_ENV_VAR}:\n{env_display}\n\n"
            "Cosa fare:\n"
            "1. Verifica che il gestionale sia stato installato correttamente "
            "e che la cartella dati esista.\n"
            f"2. Se hai scelto un percorso personalizzato, imposta la variabile "
            f"d'ambiente {DB_PATH_ENV_VAR} e riavvia Windows, poi riapri l'app.\n"
            "3. Se il problema persiste, riesegui l'installer."
        ),
    )


def _resolve_install_root() -> Path:
    """
    Resolve the installation directory (contains exe and Data/).
    Priority: platform default path → GESTIONALE_INSTALLATION_PATH env var → fatal error.
    In dev (non-frozen) mode, always returns project root.
    """
    if not is_frozen():
        return _project_root()

    if is_windows():
        default_root = WINDOWS_DEFAULT_INSTALL_ROOT
        env_value = os.environ.get(INSTALLATION_PATH_ENV_VAR)
        env_root = Path(env_value).expanduser() if env_value else None

        if _is_usable_install_root(default_root):
            return default_root

        if env_root and _is_usable_install_root(env_root):
            return env_root

        env_display = env_value or "<non valorizzata>"
        _show_error_and_exit(
            APP_NAME,
            (
                "Impossibile individuare la cartella di installazione del gestionale.\n\n"
                f"Percorso predefinito verificato:\n{default_root}\n\n"
                f"Variabile d'ambiente {INSTALLATION_PATH_ENV_VAR}:\n{env_display}\n\n"
                "Cosa fare:\n"
                f"1. Verifica che il gestionale sia installato in:\n   {default_root}\n"
                f"2. Se hai installato in un percorso personalizzato, imposta "
                f"{INSTALLATION_PATH_ENV_VAR} nelle variabili d'ambiente di sistema "
                f"e riavvia Windows, poi riapri l'app.\n"
                "3. Se il problema persiste, riesegui l'installer."
            ),
        )

    # macOS / Linux: env var, then PyInstaller _MEIPASS, then executable directory
    env_value = os.environ.get(INSTALLATION_PATH_ENV_VAR)
    if env_value:
        env_root = Path(env_value).expanduser()
        if _is_usable_install_root(env_root):
            return env_root

    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)

    return Path(sys.executable).parent


def get_storage_root() -> Path:
    root = _resolve_writable_root()
    resolved = root.resolve()
    os.environ[DB_PATH_ENV_VAR] = str(resolved)
    return resolved


def get_install_root() -> Path:
    return _resolve_install_root().resolve()


def get_resource_root() -> Path:
    return get_install_root()


_runtime_paths_cache: RuntimePaths | None = None
_runtime_paths_lock = threading.Lock()


def initialize_runtime_paths() -> RuntimePaths:
    global _runtime_paths_cache
    with _runtime_paths_lock:
        if _runtime_paths_cache is not None:
            return _runtime_paths_cache

        storage_root = get_storage_root()
        storage_root.mkdir(parents=True, exist_ok=True)

        books_dir = storage_root / "Books"
        backups_dir = storage_root / "Backups"
        books_dir.mkdir(parents=True, exist_ok=True)
        backups_dir.mkdir(parents=True, exist_ok=True)

        install_root = get_install_root()
        data_dir = install_root / "Data"
        images_dir = data_dir / "images"

        _runtime_paths_cache = RuntimePaths(
            storage_root=storage_root,
            install_root=install_root,
            db_file=storage_root / "gestionale.db",
            config_file=storage_root / "app_config.json",
            books_dir=books_dir,
            backups_dir=backups_dir,
            resource_root=install_root,
            data_dir=data_dir,
            images_dir=images_dir,
        )
        return _runtime_paths_cache


def get_runtime_paths() -> RuntimePaths:
    return initialize_runtime_paths()

import os
import sys
from dataclasses import dataclass
from pathlib import Path


APP_NAME = "WillowGestionale"
DB_PATH_ENV_VAR = "GESTIONALE_DB_PATH"


@dataclass(frozen=True)
class RuntimePaths:
    storage_root: Path
    db_file: Path
    config_file: Path
    books_dir: Path
    backups_dir: Path
    resource_root: Path
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


def get_resource_root() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return _project_root()


def _default_storage_root() -> Path:
    if is_frozen():
        if is_macos():
            return Path.home() / "Library" / "Application Support" / APP_NAME
        if is_windows():
            appdata = os.environ.get("APPDATA")
            if appdata:
                return Path(appdata) / APP_NAME
        return Path.home() / f".{APP_NAME}"
    return _project_root()


def get_storage_root() -> Path:
    configured = os.environ.get(DB_PATH_ENV_VAR)
    root = Path(configured).expanduser() if configured else _default_storage_root()
    resolved = root.resolve()
    os.environ[DB_PATH_ENV_VAR] = str(resolved)
    return resolved


def initialize_runtime_paths() -> RuntimePaths:
    storage_root = get_storage_root()
    storage_root.mkdir(parents=True, exist_ok=True)

    books_dir = storage_root / "Books"
    backups_dir = storage_root / "Backups"
    books_dir.mkdir(parents=True, exist_ok=True)
    backups_dir.mkdir(parents=True, exist_ok=True)

    resource_root = get_resource_root()
    data_dir = resource_root / "Data"
    images_dir = data_dir / "images"

    return RuntimePaths(
        storage_root=storage_root,
        db_file=storage_root / "gestionale.db",
        config_file=storage_root / "app_config.json",
        books_dir=books_dir,
        backups_dir=backups_dir,
        resource_root=resource_root,
        data_dir=data_dir,
        images_dir=images_dir,
    )


def get_runtime_paths() -> RuntimePaths:
    return initialize_runtime_paths()

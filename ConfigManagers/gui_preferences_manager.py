"""
Config manager per le preferenze GUI dell'app.

Aggrega in un unico file (``gui_preferences.json``) varie preferenze
dell'interfaccia, in modo da non frammentare la storage_root in tanti
piccoli file:

.. code-block:: json

    {
        "warnings": {
            "fatture": {"payment_total_mismatch": true, ...},
            "pagamenti": {...},
            ...
        },
        "list_views": {
            "clients":  {"window_index": 1},
            "invoices": {"window_index": 0},
            ...
        },
        "general": {
            "startup_tab": "Utenti"
        }
    }

API esposte:
- warnings: ``is_warning_enabled``, ``set_warning_enabled``,
  ``warnings_snapshot``, ``replace_warnings``;
- list views: ``get_list_view_window_index``,
  ``set_list_view_window_index``, ``list_views_snapshot``,
  ``replace_list_views``;
- generale: ``get_startup_tab``, ``set_startup_tab``.

In ``ensure_exists`` viene eseguita una migrazione dal vecchio
``warnings_visibility.json`` se presente: il contenuto finisce sotto la
chiave ``warnings`` del nuovo file.
"""

import json
from copy import deepcopy

from ConfigManagers.base_json_manager import BaseJsonConfigManager
from ConfigManagers.defaults import (
    DEFAULT_STARTUP_TAB,
    build_gui_preferences_default,
)


class GuiPreferencesManager(BaseJsonConfigManager):
    file_name = "gui_preferences.json"

    LEGACY_WARNINGS_FILE_NAME = "warnings_visibility.json"

    _CACHE_SENTINEL = object()

    def build_default_data(self):
        return build_gui_preferences_default()

    def __init__(self):
        super().__init__()
        self._cached_data = self._CACHE_SENTINEL

    # ------------------------------------------------------------------
    # Migrazione dal vecchio warnings_visibility.json
    # ------------------------------------------------------------------

    def ensure_exists(self):
        if self.file_path.exists():
            return
        legacy = self.storage_root / self.LEGACY_WARNINGS_FILE_NAME
        if legacy.exists():
            try:
                with open(legacy, "r", encoding="utf-8") as fh:
                    legacy_warnings = json.load(fh)
                migrated = self.build_default_data()
                if isinstance(legacy_warnings, dict):
                    migrated["warnings"] = legacy_warnings
                self.save(migrated)
                return
            except Exception as exc:
                print(f"[gui_preferences] migrazione legacy fallita: {exc}")
        super().ensure_exists()

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def _data(self) -> dict:
        if self._cached_data is self._CACHE_SENTINEL:
            self._cached_data = self.load()
        return self._cached_data

    def invalidate_cache(self):
        self._cached_data = self._CACHE_SENTINEL

    # ------------------------------------------------------------------
    # Warnings API
    # ------------------------------------------------------------------

    def is_warning_enabled(self, domain: str, type_key: str) -> bool:
        warnings = self._data().get("warnings") or {}
        domain_data = warnings.get(domain) or {}
        return bool(domain_data.get(type_key, True))

    def set_warning_enabled(self, domain: str, type_key: str, enabled: bool):
        data = self._data()
        warnings = data.setdefault("warnings", {})
        domain_data = warnings.setdefault(domain, {})
        domain_data[type_key] = bool(enabled)
        self.save(data)
        self.invalidate_cache()

    def warnings_snapshot(self) -> dict:
        return deepcopy(self._data().get("warnings") or {})

    def replace_warnings(self, new_warnings: dict):
        data = self._data()
        data["warnings"] = new_warnings or {}
        self.save(data)
        self.invalidate_cache()

    # ------------------------------------------------------------------
    # List views API
    # ------------------------------------------------------------------

    def get_list_view_window_index(self, list_view_key: str, default: int = 0) -> int:
        list_views = self._data().get("list_views") or {}
        entry = list_views.get(list_view_key) or {}
        value = entry.get("window_index", default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def set_list_view_window_index(self, list_view_key: str, idx: int):
        data = self._data()
        list_views = data.setdefault("list_views", {})
        entry = list_views.setdefault(list_view_key, {})
        entry["window_index"] = int(idx)
        self.save(data)
        self.invalidate_cache()

    def list_views_snapshot(self) -> dict:
        return deepcopy(self._data().get("list_views") or {})

    def replace_list_views(self, new_list_views: dict):
        data = self._data()
        data["list_views"] = new_list_views or {}
        self.save(data)
        self.invalidate_cache()

    # ------------------------------------------------------------------
    # General API
    # ------------------------------------------------------------------

    def get_startup_tab(self) -> str:
        general = self._data().get("general") or {}
        value = general.get("startup_tab")
        if isinstance(value, str) and value.strip():
            return value
        return DEFAULT_STARTUP_TAB

    def set_startup_tab(self, tab_name: str):
        data = self._data()
        general = data.setdefault("general", {})
        general["startup_tab"] = str(tab_name)
        self.save(data)
        self.invalidate_cache()


# Alias di retrocompatibilita': il vecchio nome era ``WarningsVisibilityManager``.
# Conservato per ridurre il blast radius del rename in caso di import
# residui altrove.
WarningsVisibilityManager = GuiPreferencesManager

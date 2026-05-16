"""
Config manager per la visibilita' dei warning.

Schema del file JSON (``warnings_visibility.json``):

.. code-block:: json

    {
        "fatture": {
            "payment_total_mismatch": true,
            "previous_year": false
        },
        "pagamenti": { ... },
        ...
    }

Solo i warning di severity 2 (INCONSISTENCY) e 3 (INFO) sono presenti
nel file: i sev 1 (CONSISTENCY) sono sempre attivi per design.

L'API utile per il resto dell'app e' ``is_warning_enabled(domain,
type_key)``, che restituisce ``True`` se il warning va mostrato.
"""

from ConfigManagers.base_json_manager import BaseJsonConfigManager
from ConfigManagers.defaults import build_warnings_visibility_default


class WarningsVisibilityManager(BaseJsonConfigManager):
    file_name = "warnings_visibility.json"

    def build_default_data(self):
        return build_warnings_visibility_default()

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    _CACHE_SENTINEL = object()

    def __init__(self):
        super().__init__()
        self._cached_data = self._CACHE_SENTINEL

    def _data(self) -> dict:
        if self._cached_data is self._CACHE_SENTINEL:
            self._cached_data = self.load()
        return self._cached_data

    def invalidate_cache(self):
        self._cached_data = self._CACHE_SENTINEL

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def is_warning_enabled(self, domain: str, type_key: str) -> bool:
        """``True`` se il warning va mostrato. Per i sev 1 (assenti dal
        file) la chiamata torna sempre ``True``."""
        domain_data = self._data().get(domain) or {}
        # Se la chiave non e' presente nel file (sev 1 oppure type_key
        # nuovo non ancora migrato in default), assumiamo che il warning
        # sia visibile. La GUI sovrascrive il file con i defaults
        # mergiati, quindi questo path serve solo come hardening.
        return bool(domain_data.get(type_key, True))

    def set_warning_enabled(self, domain: str, type_key: str, enabled: bool):
        data = self._data()
        domain_data = data.setdefault(domain, {})
        domain_data[type_key] = bool(enabled)
        self.save(data)
        # Invalida cache per ricaricare il merge con i defaults.
        self.invalidate_cache()

    def replace_all(self, new_data: dict):
        """Sovrascrive completamente la configurazione di visibilita'."""
        self.save(new_data)
        self.invalidate_cache()

    def snapshot(self) -> dict:
        """Ritorna una copia mutabile dello stato corrente — utile alla
        dialog di settings, che opera su una copia e salva via
        ``replace_all`` solo se l'utente conferma."""
        from copy import deepcopy
        return deepcopy(self._data())

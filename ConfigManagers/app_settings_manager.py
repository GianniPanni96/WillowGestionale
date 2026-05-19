import os

from ConfigManagers.base_json_manager import BaseJsonConfigManager
from ConfigManagers.defaults import APP_SETTINGS_DEFAULT, clone_default_config
from ConfigManagers.type_utils import MISSING, coerce_like_existing_or_default


# Fallback hard-coded: usato dal getter se il file di config esistente
# (es. app gia' in produzione) non contiene ancora la sezione 'general'
# o la chiave 'collective_name'. ``merge_with_defaults`` dovrebbe gia'
# coprire questo caso, ma manteniamo il fallback come hardening.
DEFAULT_COLLECTIVE_NAME = "Willow"


class AppSettingsManager(BaseJsonConfigManager):
    file_name = "app_settings.json"
    default_data = APP_SETTINGS_DEFAULT

    def build_default_data(self):
        data = clone_default_config(self.default_data)
        data["backup_settings"]["backup_base_path"]["value"] = os.path.join(
            str(self.storage_root), "Backups"
        )
        return data

    def get_collective_name(self) -> str:
        """Nome del collettivo di partite IVA, mostrato nella UI.

        Fa fallback a ``DEFAULT_COLLECTIVE_NAME`` se la sezione 'general'
        o la chiave 'collective_name' non esistono o sono vuote (caso
        delle installazioni in produzione il cui ``app_settings.json``
        e' stato creato prima dell'introduzione di questo campo).
        """
        try:
            data = self.load()
        except Exception:
            return DEFAULT_COLLECTIVE_NAME

        general = data.get("general") if isinstance(data, dict) else None
        if not isinstance(general, dict):
            return DEFAULT_COLLECTIVE_NAME
        node = general.get("collective_name")
        if isinstance(node, dict):
            value = node.get("value")
        else:
            value = node
        if not isinstance(value, str) or not value.strip():
            return DEFAULT_COLLECTIVE_NAME
        return value.strip()

    def set_collective_name(self, name: str):
        """Aggiorna il nome del collettivo nel file di config.

        Vuoto / None / soli spazi resettano al default ``Willow``.
        """
        cleaned = (name or "").strip() or DEFAULT_COLLECTIVE_NAME
        self.update_section("general", {"collective_name": cleaned})

    def update_section(self, section_key: str, new_section_data: dict):
        try:
            current_config = self.load()
            default_config = self.build_default_data()
            if section_key not in current_config:
                current_config[section_key] = {}

            for key, new_val in new_section_data.items():
                existing_node = current_config[section_key].get(key, {})
                default_node = (
                    default_config.get(section_key, {}).get(key, {})
                    if isinstance(default_config.get(section_key, {}), dict)
                    else {}
                )
                existing_value = existing_node.get("value", MISSING) if isinstance(existing_node, dict) else MISSING
                default_value = default_node.get("value", MISSING) if isinstance(default_node, dict) else MISSING
                coerced_value = coerce_like_existing_or_default(
                    new_val,
                    existing=existing_value,
                    default=default_value,
                )

                if key in current_config[section_key] and isinstance(current_config[section_key][key], dict):
                    current_config[section_key][key]["value"] = coerced_value
                else:
                    current_config[section_key][key] = {"value": coerced_value, "description": ""}

            self.save(current_config)
        except Exception as exc:
            raise Exception(
                f"Errore durante il salvataggio della sezione '{section_key}': {str(exc)}"
            ) from exc

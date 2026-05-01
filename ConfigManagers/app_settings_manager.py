import os

from ConfigManagers.base_json_manager import BaseJsonConfigManager
from ConfigManagers.defaults import APP_SETTINGS_DEFAULT, clone_default_config
from ConfigManagers.type_utils import MISSING, coerce_like_existing_or_default


class AppSettingsManager(BaseJsonConfigManager):
    file_name = "app_settings.json"
    default_data = APP_SETTINGS_DEFAULT

    def build_default_data(self):
        data = clone_default_config(self.default_data)
        data["backup_settings"]["backup_base_path"]["value"] = os.path.join(
            str(self.storage_root), "Backups"
        )
        return data

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

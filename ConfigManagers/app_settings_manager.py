import os

from ConfigManagers.base_json_manager import BaseJsonConfigManager
from ConfigManagers.defaults import APP_SETTINGS_DEFAULT, clone_default_config


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
            if section_key not in current_config:
                current_config[section_key] = {}

            for key, new_val in new_section_data.items():
                if key in current_config[section_key] and isinstance(current_config[section_key][key], dict):
                    current_config[section_key][key]["value"] = new_val
                else:
                    current_config[section_key][key] = {"value": new_val, "description": ""}

            self.save(current_config)
        except Exception as exc:
            raise Exception(
                f"Errore durante il salvataggio della sezione '{section_key}': {str(exc)}"
            ) from exc

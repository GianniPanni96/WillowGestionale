import re

from ConfigManagers.base_json_manager import BaseJsonConfigManager
from ConfigManagers.defaults import FISCAL_RULES_DEFAULT


class FiscalRulesManager(BaseJsonConfigManager):
    file_name = "fiscal_rules.json"
    default_data = FISCAL_RULES_DEFAULT

    def update_fiscal_settings(self, new_fiscal_data: dict):
        try:
            current_config = self.load()
            fiscal_settings = current_config.setdefault("fiscal_settings", {})

            for section_key, new_section in new_fiscal_data.items():
                target_section = fiscal_settings.setdefault(section_key, {})

                if section_key == "partita_iva_ordinaria":
                    for key, new_val in new_section.items():
                        if not isinstance(new_val, dict):
                            new_val = {"value": new_val}
                        if re.match(r"^aliquota_irpef_\d+$", key):
                            current = target_section.get(key, {})
                            target_section[key] = {
                                "value": new_val.get("value", current.get("value", "")),
                                "reddito_min": new_val.get("reddito_min", current.get("reddito_min", "")),
                                "reddito_max": new_val.get("reddito_max", current.get("reddito_max", "")),
                                "description": new_val.get("description", current.get("description", "")),
                            }
                        else:
                            current = target_section.get(key, {})
                            if isinstance(current, dict):
                                current["value"] = new_val.get("value", current.get("value", ""))
                                target_section[key] = current
                            else:
                                target_section[key] = {
                                    "value": new_val.get("value", new_val),
                                    "description": "",
                                }

                    current_irpef_keys = [
                        key for key in target_section.keys() if re.match(r"^aliquota_irpef_\d+$", key)
                    ]
                    new_irpef_keys = {
                        key for key in new_section.keys() if re.match(r"^aliquota_irpef_\d+$", key)
                    }
                    for key in current_irpef_keys:
                        if key not in new_irpef_keys:
                            del target_section[key]

                elif section_key == "iva":
                    for key, new_val in new_section.items():
                        if not isinstance(new_val, dict):
                            new_val = {"value": new_val}
                        current = target_section.get(key, {})
                        target_section[key] = {
                            "value": new_val.get("value", current.get("value", "")),
                            "description": new_val.get("description", current.get("description", "")),
                        }

                else:
                    for key, new_val in new_section.items():
                        if not isinstance(new_val, dict):
                            new_val = {"value": new_val}
                        if key == "value":
                            target_section[key] = new_val.get("value", new_val)
                            continue

                        current = target_section.get(key, {})
                        if isinstance(current, dict):
                            current["value"] = new_val.get("value", current.get("value", ""))
                            target_section[key] = current
                        else:
                            target_section[key] = {
                                "value": new_val.get("value", new_val),
                                "description": "",
                            }

            self.save(current_config)
        except Exception as exc:
            raise Exception(f"Errore durante l'aggiornamento dei dati fiscali: {str(exc)}") from exc

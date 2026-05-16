import re

from ConfigManagers.base_json_manager import BaseJsonConfigManager
from ConfigManagers.defaults import FISCAL_RULES_DEFAULT
from ConfigManagers.type_utils import MISSING, coerce_like_existing_or_default


class FiscalRulesManager(BaseJsonConfigManager):
    file_name = "fiscal_rules.json"
    default_data = FISCAL_RULES_DEFAULT

    def update_fiscal_settings(self, new_fiscal_data: dict):
        try:
            current_config = self.load()
            default_config = self.build_default_data()
            fiscal_settings = current_config.setdefault("fiscal_settings", {})
            default_fiscal_settings = default_config.get("fiscal_settings", {})

            for section_key, new_section in new_fiscal_data.items():
                target_section = fiscal_settings.setdefault(section_key, {})
                default_section = default_fiscal_settings.get(section_key, {})

                if section_key == "partita_iva_ordinaria":
                    for key, new_val in new_section.items():
                        if not isinstance(new_val, dict):
                            new_val = {"value": new_val}
                        if re.match(r"^aliquota_irpef_\d+$", key):
                            current = target_section.get(key, {})
                            if not isinstance(current, dict):
                                current = {}
                            default_current = default_section.get(key, {})
                            if not isinstance(default_current, dict):
                                default_current = {}
                            target_section[key] = {
                                "value": coerce_like_existing_or_default(
                                    new_val.get("value", current.get("value", "")),
                                    existing=current.get("value", MISSING),
                                    default=default_current.get("value", MISSING),
                                ),
                                "reddito_min": coerce_like_existing_or_default(
                                    new_val.get("reddito_min", current.get("reddito_min", "")),
                                    existing=current.get("reddito_min", MISSING),
                                    default=default_current.get("reddito_min", MISSING),
                                ),
                                "reddito_max": coerce_like_existing_or_default(
                                    new_val.get("reddito_max", current.get("reddito_max", "")),
                                    existing=current.get("reddito_max", MISSING),
                                    default=default_current.get("reddito_max", MISSING),
                                ),
                                "description": new_val.get("description", current.get("description", "")),
                            }
                        else:
                            current = target_section.get(key, {})
                            default_current = default_section.get(key, {})
                            coerced_value = coerce_like_existing_or_default(
                                new_val.get("value", current.get("value", "")),
                                existing=current.get("value", MISSING) if isinstance(current, dict) else MISSING,
                                default=default_current.get("value", MISSING) if isinstance(default_current, dict) else MISSING,
                            )
                            if isinstance(current, dict):
                                current["value"] = coerced_value
                                target_section[key] = current
                            else:
                                target_section[key] = {
                                    "value": coerced_value,
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
                        if not isinstance(current, dict):
                            current = {}
                        default_current = default_section.get(key, {})
                        if not isinstance(default_current, dict):
                            default_current = {}
                        target_section[key] = {
                            "value": coerce_like_existing_or_default(
                                new_val.get("value", current.get("value", "")),
                                existing=current.get("value", MISSING),
                                default=default_current.get("value", MISSING),
                            ),
                            "description": new_val.get("description", current.get("description", "")),
                        }

                else:
                    for key, new_val in new_section.items():
                        if not isinstance(new_val, dict):
                            new_val = {"value": new_val}
                        if key == "value":
                            target_section[key] = coerce_like_existing_or_default(
                                new_val.get("value", new_val),
                                existing=target_section.get(key, MISSING),
                                default=default_section.get(key, MISSING),
                            )
                            continue

                        current = target_section.get(key, {})
                        default_current = default_section.get(key, {})
                        coerced_value = coerce_like_existing_or_default(
                            new_val.get("value", current.get("value", "")),
                            existing=current.get("value", MISSING) if isinstance(current, dict) else MISSING,
                            default=default_current.get("value", MISSING) if isinstance(default_current, dict) else MISSING,
                        )
                        if isinstance(current, dict):
                            current["value"] = coerced_value
                            target_section[key] = current
                        else:
                            target_section[key] = {
                                "value": coerced_value,
                                "description": "",
                            }

            self.save(current_config)
        except Exception as exc:
            raise Exception(f"Errore durante l'aggiornamento dei dati fiscali: {str(exc)}") from exc

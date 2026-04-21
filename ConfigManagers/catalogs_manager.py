from ConfigManagers.base_json_manager import BaseJsonConfigManager
from ConfigManagers.defaults import CATALOGS_DEFAULT


class CatalogsManager(BaseJsonConfigManager):
    file_name = "catalogs.json"
    default_data = CATALOGS_DEFAULT

    def update_list_field(self, section_name: str, key: str, value: str = None, operation: str = "update"):
        config = self.load()

        if section_name not in config:
            if operation == "update":
                config[section_name] = {}
            else:
                raise Exception(f"La sezione '{section_name}' non esiste.")

        section_dict = config[section_name]

        if operation == "update":
            if key in section_dict:
                section_dict[key] = value
            else:
                trigger_map = {
                    "clients_business_sectors": "ADD_SECTOR",
                    "production_types": "ADD_PROD_TYPE",
                    "production_output_types": "ADD_PROD_OUT_TYPE",
                    "expenses_category": "ADD_CATEGORY",
                }
                trigger_key = trigger_map.get(section_name)
                items = list(section_dict.items())
                trigger_item = None

                if trigger_key and items and items[-1][0] == trigger_key:
                    trigger_item = items.pop(-1)

                new_section = {key: value}
                for current_key, current_value in items:
                    new_section[current_key] = current_value
                if trigger_item:
                    new_section[trigger_item[0]] = trigger_item[1]

                config[section_name] = new_section

        elif operation == "delete":
            if key in section_dict:
                del section_dict[key]
        else:
            raise Exception("Operazione non riconosciuta. Utilizzare 'update' o 'delete'.")

        self.save(config)

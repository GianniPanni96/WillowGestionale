from ConfigManagers.base_json_manager import BaseJsonConfigManager
from ConfigManagers.defaults import RECURRING_EXPENSES_DEFAULT


class RecurringExpensesManager(BaseJsonConfigManager):
    file_name = "recurring_expenses.json"
    default_data = RECURRING_EXPENSES_DEFAULT

    def update_recurring_expenses(self, new_recurring_data: dict):
        config = self.load()

        for expense_key, fields in new_recurring_data.items():
            node = config.setdefault(expense_key, {})
            normalized_fields = dict(fields)

            if "description" in normalized_fields:
                node["description"] = normalized_fields.pop("description")

            for field_name, new_val in normalized_fields.items():
                existing = node.get(field_name)
                if isinstance(existing, dict):
                    existing["value"] = new_val
                else:
                    node[field_name] = {"value": new_val, "description": ""}

        self.save(config)

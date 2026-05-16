from ConfigManagers.base_json_manager import BaseJsonConfigManager
from ConfigManagers.defaults import RECURRING_EXPENSES_DEFAULT
from ConfigManagers.type_utils import MISSING, coerce_like_existing_or_default


class RecurringExpensesManager(BaseJsonConfigManager):
    file_name = "recurring_expenses.json"
    default_data = RECURRING_EXPENSES_DEFAULT

    def update_recurring_expenses(self, new_recurring_data: dict):
        config = self.load()
        expenses = config.setdefault("recurring_expenses", {})

        for expense_key, fields in new_recurring_data.items():
            node = expenses.setdefault(expense_key, {})
            normalized_fields = dict(fields)

            if "description" in normalized_fields:
                node["description"] = normalized_fields.pop("description")

            for field_name, new_val in normalized_fields.items():
                existing = node.get(field_name)
                existing_value = existing.get("value", MISSING) if isinstance(existing, dict) else MISSING
                coerced_value = coerce_like_existing_or_default(new_val, existing=existing_value)
                if isinstance(existing, dict):
                    existing["value"] = coerced_value
                else:
                    node[field_name] = {"value": coerced_value, "description": ""}

        self.save(config)

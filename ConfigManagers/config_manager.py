from ConfigManagers.app_settings_manager import AppSettingsManager
from ConfigManagers.catalogs_manager import CatalogsManager
from ConfigManagers.fiscal_rules_manager import FiscalRulesManager
from ConfigManagers.historical_financial_data_manager import (
    HistoricalFinancialDataManager,
    normalize_historical_file_data,
)
from ConfigManagers.recurring_expenses_manager import RecurringExpensesManager


class ConfigManager:
    def __init__(self):
        self.app_settings_manager = AppSettingsManager()
        self.fiscal_rules_manager = FiscalRulesManager()
        self.catalogs_manager = CatalogsManager()
        self.recurring_expenses_manager = RecurringExpensesManager()
        self.historical_financial_data_manager = HistoricalFinancialDataManager()

    def load_config(self):
        config = {}
        config.update(self.app_settings_manager.load())
        config.update(self.fiscal_rules_manager.load())
        config.update(self.catalogs_manager.load())
        config["recurring_expenses"] = self.recurring_expenses_manager.load()
        config["historical_financial_data"] = self.historical_financial_data_manager.load()
        return config

    def save_config(self, config):
        self.app_settings_manager.save(
            {
                "backup_settings": config.get(
                    "backup_settings",
                    self.app_settings_manager.build_default_data()["backup_settings"],
                )
            }
        )
        self.fiscal_rules_manager.save(
            {
                "fiscal_settings": config.get(
                    "fiscal_settings",
                    self.fiscal_rules_manager.build_default_data()["fiscal_settings"],
                )
            }
        )

        catalogs_defaults = self.catalogs_manager.build_default_data()
        self.catalogs_manager.save(
            {
                "clients_business_sectors": config.get(
                    "clients_business_sectors", catalogs_defaults["clients_business_sectors"]
                ),
                "production_types": config.get("production_types", catalogs_defaults["production_types"]),
                "production_output_types": config.get(
                    "production_output_types", catalogs_defaults["production_output_types"]
                ),
                "expenses_category": config.get("expenses_category", catalogs_defaults["expenses_category"]),
            }
        )
        self.recurring_expenses_manager.save(config.get("recurring_expenses", {}))
        self.historical_financial_data_manager.save(
            normalize_historical_file_data(config.get("historical_financial_data", {}))
        )

    def update_config_section(self, section_key: str, new_section_data: dict):
        self.app_settings_manager.update_section(section_key, new_section_data)

    def update_fiscal_settings(self, new_fiscal_data: dict):
        self.fiscal_rules_manager.update_fiscal_settings(new_fiscal_data)

    def update_list_field(self, section_name: str, key: str, value: str = None, operation: str = "update"):
        self.catalogs_manager.update_list_field(section_name, key, value, operation)

    def update_recurring_expenses(self, new_recurring_data: dict):
        self.recurring_expenses_manager.update_recurring_expenses(new_recurring_data)

    def update_historical_financial_data(self, historical_data: dict):
        self.historical_financial_data_manager.update_historical_financial_data(historical_data)

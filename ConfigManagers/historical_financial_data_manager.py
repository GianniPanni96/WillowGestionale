from ConfigManagers.base_json_manager import BaseJsonConfigManager
from ConfigManagers.defaults import HISTORICAL_FINANCIAL_DATA_DEFAULT


def normalize_historical_file_data(data: dict) -> dict:
    if not data:
        return {"revenues": {}, "deducted_expenses": {}}

    if "revenues" in data or "deducted_expenses" in data:
        normalized = {
            "revenues": {},
            "deducted_expenses": {},
        }
        for year, year_revenues in (data.get("revenues", {}) or {}).items():
            normalized["revenues"][str(year)] = year_revenues or {}

        for year, amount in (data.get("deducted_expenses", {}) or {}).items():
            normalized["deducted_expenses"][str(year)] = float(amount or 0.0)

        return normalized

    normalized = {
        "revenues": {},
        "deducted_expenses": {},
    }
    for year, payload in data.items():
        year_key = str(year)
        year_payload = payload or {}
        normalized["revenues"][year_key] = year_payload.get("revenues", {}) or {}
        normalized["deducted_expenses"][year_key] = float(
            year_payload.get("deducted_expenses", 0.0) or 0.0
        )
    return normalized


class HistoricalFinancialDataManager(BaseJsonConfigManager):
    file_name = "historical_financial_data.json"
    default_data = HISTORICAL_FINANCIAL_DATA_DEFAULT

    def load(self):
        return normalize_historical_file_data(super().load())

    def update_historical_financial_data(self, historical_data: dict):
        try:
            current_config = self.load()
            normalized_input = normalize_historical_file_data(historical_data)

            for year, year_revenues in normalized_input.get("revenues", {}).items():
                current_config["revenues"][str(year)] = year_revenues or {}

            for year, amount in normalized_input.get("deducted_expenses", {}).items():
                current_config["deducted_expenses"][str(year)] = float(amount or 0.0)

            self.save(current_config)
        except Exception as exc:
            raise Exception(
                f"Errore durante l'aggiornamento dei dati finanziari storici: {str(exc)}"
            ) from exc

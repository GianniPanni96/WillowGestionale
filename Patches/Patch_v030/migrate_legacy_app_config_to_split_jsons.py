import json
from pathlib import Path

from ConfigManagers.defaults import (
    APP_SETTINGS_DEFAULT,
    CATALOGS_DEFAULT,
    FISCAL_RULES_DEFAULT,
    HISTORICAL_FINANCIAL_DATA_DEFAULT,
    RECURRING_EXPENSES_DEFAULT,
    clone_default_config,
)
from ConfigManagers.historical_financial_data_manager import normalize_historical_file_data
from ConfigManagers.type_utils import merge_with_defaults
from Utils.App_paths import DB_PATH_ENV_VAR, get_runtime_paths


def read_json_file(file_path: Path) -> dict:
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def write_json_file(file_path: Path, payload: dict):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=4)


def all_target_files_exist(storage_root: Path) -> bool:
    return all(
        (storage_root / file_name).exists()
        for file_name in (
            "app_settings.json",
            "fiscal_rules.json",
            "catalogs.json",
            "recurring_expenses.json",
            "historical_financial_data.json",
        )
    )


def build_app_settings_payload(legacy_config: dict) -> dict:
    payload = clone_default_config(APP_SETTINGS_DEFAULT)
    return merge_with_defaults(
        {"backup_settings": legacy_config.get("backup_settings", {})},
        payload,
    )


def build_fiscal_rules_payload(legacy_config: dict) -> dict:
    payload = clone_default_config(FISCAL_RULES_DEFAULT)
    return merge_with_defaults(
        {"fiscal_settings": legacy_config.get("fiscal_settings", {})},
        payload,
    )


def build_catalogs_payload(legacy_config: dict) -> dict:
    payload = clone_default_config(CATALOGS_DEFAULT)
    return merge_with_defaults(
        {key: legacy_config.get(key, payload[key]) for key in payload.keys()},
        payload,
    )


def build_recurring_expenses_payload(legacy_config: dict) -> dict:
    payload = clone_default_config(RECURRING_EXPENSES_DEFAULT)
    return merge_with_defaults(
        {"recurring_expenses": legacy_config.get("recurring_expenses", {})},
        payload,
    )


def build_historical_financial_data_payload(legacy_config: dict) -> dict:
    legacy_historical_data = legacy_config.get(
        "historical_financial_data",
        clone_default_config(HISTORICAL_FINANCIAL_DATA_DEFAULT),
    )
    return normalize_historical_file_data(legacy_historical_data)


def migrate_legacy_app_config():
    runtime_paths = get_runtime_paths()
    storage_root = runtime_paths.storage_root
    legacy_config_path = runtime_paths.legacy_config_file

    if not legacy_config_path.exists():
        if all_target_files_exist(storage_root):
            print("File legacy assente, ma i file di configurazione split esistono gia'.")
            print("Nessuna migrazione necessaria.")
            return
        else:
            raise FileNotFoundError(
                f"File legacy non trovato: {legacy_config_path}. "
                f"Configura correttamente {DB_PATH_ENV_VAR} prima di eseguire lo script."
            )

    legacy_config = read_json_file(legacy_config_path)

    target_files = {
        "app_settings.json": build_app_settings_payload(legacy_config),
        "fiscal_rules.json": build_fiscal_rules_payload(legacy_config),
        "catalogs.json": build_catalogs_payload(legacy_config),
        "recurring_expenses.json": build_recurring_expenses_payload(legacy_config),
        "historical_financial_data.json": build_historical_financial_data_payload(legacy_config),
    }

    print(f"Storage root: {storage_root}")
    print(f"Legacy config sorgente: {legacy_config_path}")
    print("Il file legacy verra lasciato inalterato.")

    for file_name, payload in target_files.items():
        target_path = storage_root / file_name
        if target_path.exists():
            print(f"Gia' presente, non sovrascrivo: {target_path}")
            continue
        write_json_file(target_path, payload)
        print(f"Creato: {target_path}")

    print("Migrazione completata con successo.")


if __name__ == "__main__":
    migrate_legacy_app_config()

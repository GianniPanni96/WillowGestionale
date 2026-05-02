import os
import sys
import importlib


_TABLE_MODULES = [
    "DatabaseCreation.Create_table_accounts",
    "DatabaseCreation.Create_table_users",
    "DatabaseCreation.Create_table_clients",
    "DatabaseCreation.Create_table_invoices",
    "DatabaseCreation.Create_table_expenses",
    "DatabaseCreation.Create_table_payments",
    "DatabaseCreation.Create_table_productions",
    "DatabaseCreation.Create_table_transfers",
    "DatabaseCreation.Create_table_suppliers",
    "DatabaseCreation.Create_table_salaries",
    "DatabaseCreation.Create_table_refunders",
]

_CACHED_MODULES_TO_CLEAR = [
    "Model",
    "Utils.App_paths",
]


def create_all_tables(target_folder: str) -> list:
    """
    Crea tutte le tabelle del database nella cartella target_folder.

    Deve essere chiamata DOPO aver settato os.environ['GESTIONALE_DB_PATH'] = target_folder.
    Restituisce una lista di tuple (nome_modulo, success: bool, errore: str).
    """
    os.environ["GESTIONALE_DB_PATH"] = str(target_folder)

    results = []
    for module_path in _TABLE_MODULES:
        short_name = module_path.split(".")[-1]
        try:
            for cached in _CACHED_MODULES_TO_CLEAR + [module_path]:
                sys.modules.pop(cached, None)

            importlib.import_module(module_path)
            results.append((short_name, True, ""))
        except Exception as exc:
            results.append((short_name, False, str(exc)))

    return results

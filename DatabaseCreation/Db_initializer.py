import os
import sys
from pathlib import Path

_TABLE_MODULES = [
    "Create_table_accounts",
    "Create_table_users",
    "Create_table_clients",
    "Create_table_invoices",
    "Create_table_expenses",
    "Create_table_payments",
    "Create_table_productions",
    "Create_table_transfers",
    "Create_table_suppliers",
    "Create_table_salaries",
    "Create_table_refunders",
    "Create_table_admin",
]

_CACHED_MODULES_TO_CLEAR = [
    "Model",
    "Utils.App_paths",
]


def _load_table_module(module_name: str):
    if module_name == "Create_table_accounts":
        from DatabaseCreation import Create_table_accounts as module
    elif module_name == "Create_table_users":
        from DatabaseCreation import Create_table_users as module
    elif module_name == "Create_table_clients":
        from DatabaseCreation import Create_table_clients as module
    elif module_name == "Create_table_invoices":
        from DatabaseCreation import Create_table_invoices as module
    elif module_name == "Create_table_expenses":
        from DatabaseCreation import Create_table_expenses as module
    elif module_name == "Create_table_payments":
        from DatabaseCreation import Create_table_payments as module
    elif module_name == "Create_table_productions":
        from DatabaseCreation import Create_table_productions as module
    elif module_name == "Create_table_transfers":
        from DatabaseCreation import Create_table_transfers as module
    elif module_name == "Create_table_suppliers":
        from DatabaseCreation import Create_table_suppliers as module
    elif module_name == "Create_table_salaries":
        from DatabaseCreation import Create_table_salaries as module
    elif module_name == "Create_table_refunders":
        from DatabaseCreation import Create_table_refunders as module
    elif module_name == "Create_table_admin":
        from DatabaseCreation import Create_table_admin as module
    else:
        raise ValueError(f"Modulo tabella non gestito: {module_name}")

    return module


def create_all_tables(target_folder: str) -> list:
    """
    Crea tutte le tabelle del database nella cartella target_folder.

    Self-sufficient: assicura che target_folder esista (con Books/Backups) e
    setta os.environ['GESTIONALE_DB_PATH'] prima di importare i moduli che
    caricheranno Model -> Utils.App_paths. In questo modo App_paths non puo'
    cadere in un fatal-exit anche se l'installer non ha pre-creato la struttura.
    Restituisce una lista di tuple (nome_modulo, success: bool, errore: str).
    """
    target_path = Path(target_folder)
    target_path.mkdir(parents=True, exist_ok=True)
    (target_path / "Books").mkdir(exist_ok=True)
    (target_path / "Backups").mkdir(exist_ok=True)

    os.environ["GESTIONALE_DB_PATH"] = str(target_path.resolve())

    results = []
    for short_name in _TABLE_MODULES:
        module_path = f"DatabaseCreation.{short_name}"
        try:
            for cached in _CACHED_MODULES_TO_CLEAR + [module_path]:
                sys.modules.pop(cached, None)

            _load_table_module(short_name)
            results.append((short_name, True, ""))
        except Exception as exc:
            results.append((short_name, False, str(exc)))

    return results

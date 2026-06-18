"""
Bootstrap condiviso tra le due entry-point della UI (legacy Tkinter e Qt).

Si occupa di tutto cio' che e' indipendente dal frontend:
- carica la configurazione dal disco;
- costruisce le strutture di settings (fiscal, recurring expenses, ecc.);
- avvia il backup scheduler in un thread daemon;
- istanzia BackupImporter e AppContext.

Restituisce la coppia (AppContext, BackupScheduler) cosi' che le due
entry-point siano poi ridotte a poche righe: prendere il context, lanciare
la UI, fermare lo scheduler in chiusura.
"""

import threading

from App_context import AppContext
from Backup_manager import BackupImporter, BackupScheduler
from ConfigManagers import (
    ConfigManager,
    FiscalSettings,
    HistoricalFinancialData,
    RecurringExpense,
)
from Utils.App_paths import get_runtime_paths
from Utils.Db_health_check import verify_database_health


def build_app_context():
    """Costruisce AppContext + scheduler, gia' con il backup thread avviato."""

    runtime_paths = get_runtime_paths()
    path = str(runtime_paths.storage_root)

    db_path = str(runtime_paths.db_file)

    # Fail-fast con popup nativo se il DB manca o ha tabelle incomplete:
    # evita crash silenziosi nei moduli che assumono lo schema completo.
    verify_database_health(runtime_paths.db_file)
    data_path = str(runtime_paths.data_dir)
    images_path = str(runtime_paths.images_dir)
    books_default_path = str(runtime_paths.books_dir)

    config_manager = ConfigManager()
    config = config_manager.load_config()

    backup_settings = config.get("backup_settings", {})
    interval_minutes = backup_settings.get("interval_minutes", {}).get("value", 15)
    max_backups = backup_settings.get("max_backups", {}).get("value", 35)
    db_backup_base_path = backup_settings.get("backup_base_path", {}).get("value")
    books_backup_path = backup_settings.get("backup_books_path", {}).get("value")
    delta_days = backup_settings.get("delta_days", {}).get("value", 7)

    if not db_backup_base_path:
        db_backup_base_path = str(runtime_paths.backups_dir)

    fiscal_config = config.get("fiscal_settings", {})
    fiscal_settings = FiscalSettings.from_dict(fiscal_config)

    recurring_expenses_config = config.get("recurring_expenses", {})
    recurring_expenses_settings = {
        expense_key: RecurringExpense.from_dict(expense_data)
        for expense_key, expense_data in recurring_expenses_config.items()
    }

    historical_financial_data_config = config.get("historical_financial_data", {})
    historical_financial_data_settings = HistoricalFinancialData.from_dict(
        historical_financial_data_config
    )

    clients_business_sectors = [
        (key, value) for key, value in config.get("clients_business_sectors", {}).items()
    ]
    productions_types = [
        (key, value) for key, value in config.get("production_types", {}).items()
    ]
    productions_outputs_types = [
        (key, value) for key, value in config.get("production_output_types", {}).items()
    ]
    expenses_category = [
        (key, value) for key, value in config.get("expenses_category", {}).items()
    ]
    catalogo_elenchi = {
        "clients_business_sectors": clients_business_sectors,
        "production_types": productions_types,
        "production_output_types": productions_outputs_types,
        "expenses_category": expenses_category,
    }

    scheduler = BackupScheduler(
        interval_minutes=interval_minutes,
        max_backups=max_backups,
        db_backup_base_path=db_backup_base_path,
        delta_days=delta_days,
        books_backup_path=books_backup_path,
        books_default_path=books_default_path,
    )

    print("Avvio dell'applicazione e scheduler dei backup...\n")
    backup_thread = threading.Thread(target=scheduler.start, daemon=True)
    backup_thread.start()

    backup_importer = BackupImporter(
        db_backup_base_path=db_backup_base_path,
        db_path=db_path,
    )

    app_context = AppContext(
        fiscal_settings=fiscal_settings,
        historical_financial_data_settings=historical_financial_data_settings,
        recurring_expenses_settings=recurring_expenses_settings,
        catalogo_elenchi=catalogo_elenchi,
        config_manager=config_manager,
        backup_importer=backup_importer,
        backup_scheduler=scheduler,
        environment_db_variable=path,
        db_path=db_path,
        data_path=data_path,
        images_path=images_path,
        db_backup_path=db_backup_base_path,
        books_path=books_default_path,
    )

    return app_context, scheduler

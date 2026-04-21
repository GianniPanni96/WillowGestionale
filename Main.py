import threading
from Views.View import MainWindow
import os
from ConfigManagers import ConfigManager, RecurringExpense, FiscalSettings, HistoricalFinancialData
from Backup_manager import BackupScheduler, BackupImporter
from App_context import AppContext
from Utils.App_paths import DB_PATH_ENV_VAR, get_runtime_paths

# Avvia l'applicazione
if __name__ == "__main__":

    runtime_paths = get_runtime_paths()
    path = str(runtime_paths.storage_root)
    os.environ[DB_PATH_ENV_VAR] = path

    db_path = str(runtime_paths.db_file)
    data_path = str(runtime_paths.data_dir)
    images_path = str(runtime_paths.images_dir)
    books_default_path = str(runtime_paths.books_dir)


    # Inizializza il gestore delle configurazioni
    config_manager = ConfigManager()
    config = config_manager.load_config()  # Carica la configurazione

    # Estrai le impostazioni di backup dalla configurazione,
    # recuperando solo il campo "value" di ciascuna impostazione
    backup_settings = config.get("backup_settings", {})
    interval_minutes = backup_settings.get("interval_minutes", {}).get("value", 15)
    max_backups = backup_settings.get("max_backups", {}).get("value", 35)
    db_backup_base_path = backup_settings.get("backup_base_path", {}).get("value")
    books_backup_path = backup_settings.get("backup_books_path", {}).get("value")
    delta_days = backup_settings.get("delta_days", {}).get("value", 7)

    if not db_backup_base_path:
        db_backup_base_path = str(runtime_paths.backups_dir)

    # Estrai le impostazioni fiscali dalla configurazione
    fiscal_config = config.get("fiscal_settings", {})
    # Crea un'istanza di FiscalSettings
    fiscal_settings = FiscalSettings.from_dict(fiscal_config)

    recurring_expenses_config = config.get("recurring_expenses", {})
    recurring_expenses_settings = {
        expense_key: RecurringExpense.from_dict(expense_data)
        for expense_key, expense_data in recurring_expenses_config.items()
    }

    historical_financial_data_config = config.get("historical_financial_data", {})
    historical_financial_data_settings = HistoricalFinancialData.from_dict(historical_financial_data_config)

    #creo il dizionario degli elenchi
    # Trasforma le sezioni in liste di tuple (chiave, valore)
    clients_business_sectors = [
        (key, value)
        for key, value in config.get("clients_business_sectors", {}).items()
    ]
    productions_types = [
        (key, value)
        for key, value in config.get("production_types", {}).items()
    ]
    productions_outputs_types = [
        (key, value)
        for key, value in config.get("production_output_types", {}).items()
    ]

    expenses_category = [
        (key, value)
        for key, value in config.get("expenses_category", {}).items()
    ]

    catalogo_elenchi = {
        "clients_business_sectors": clients_business_sectors,
        "production_types": productions_types,
        "production_output_types": productions_outputs_types,
        "expenses_category": expenses_category
    }


    # Inizializza il gestore del backup con i parametri dalla configurazione
    scheduler = BackupScheduler(
        interval_minutes=interval_minutes,
        max_backups=max_backups,
        db_backup_base_path=db_backup_base_path,
        delta_days=delta_days,
        books_backup_path = books_backup_path,
        books_default_path=books_default_path
    )

    print("Avvio dell'applicazione e scheduler dei backup...\n")
    backup_thread = threading.Thread(target=scheduler.start, daemon=True)
    backup_thread.start()

    #inzializza il backup importer da passare alla main view
    backup_importer = BackupImporter(
        db_backup_base_path=db_backup_base_path,
        db_path=db_path
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
        books_path=books_default_path
        )

    # Avvia il frontend
    app = MainWindow(app_context)


    def on_closing():
        print("Finestra chiusa: arresto scheduler backup…")

        # Aggiungi queste righe per pulire il lazy loading
        if hasattr(app, '_cancel_all_after'):
            app._cancel_all_after()

        # Ferma il backup scheduler
        scheduler.stop()
        app.quit()
        app.destroy()


    # Registra la callback
    app.protocol("WM_DELETE_WINDOW", on_closing)

    # Entra nel loop
    try:
        app.mainloop()
    except KeyboardInterrupt:
        # In caso di Ctrl+C da console
        print("Interruzione manuale. Fermando il backup...")
        scheduler.stop()
        raise

import threading
from Views.View import MainWindow
import os
from Config import BackupScheduler, ConfigManager, RecurringExpense, FiscalSettings, PartitaIVAOrdinaria, PartitaIVAForfettaria, AliquotaIva, ScaglioneIrpef, HistoricalFinancialData


# Avvia l'applicazione
if __name__ == "__main__":

    # Nome della variabile d'ambiente
    PATH_ENV_VAR = "GESTIONALE_DB_PATH"

    # Ottieni il percorso del database dalla variabile d'ambiente
    path = os.environ.get(PATH_ENV_VAR)

    if not path:
        raise EnvironmentError(f"La variabile d'ambiente {PATH_ENV_VAR} non è stata configurata.")

    db_path = os.path.join(path, "gestionale.db")
    backup_path = os.path.join(path, "backups")


    # Inizializza il gestore delle configurazioni
    config_manager = ConfigManager()
    config = config_manager.load_config()  # Carica la configurazione

    # Estrai le impostazioni di backup dalla configurazione,
    # recuperando solo il campo "value" di ciascuna impostazione
    backup_settings = config.get("backup_settings", {})
    interval_minutes = backup_settings.get("interval_minutes", {}).get("value", 15)
    max_backups = backup_settings.get("max_backups", {}).get("value", 35)
    #backup_base_path = backup_settings.get("backup_base_path", {}).get("value")
    delta_days = backup_settings.get("delta_days", {}).get("value", 7)

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
        backup_base_path=backup_path,
        delta_days=delta_days
    )

    print("Avvio dell'applicazione e scheduler dei backup...\n")
    backup_thread = threading.Thread(target=scheduler.start, daemon=True)
    backup_thread.start()

    # Avvia il frontend
    app = MainWindow(config_manager, fiscal_settings, catalogo_elenchi, recurring_expenses_settings, historical_financial_data_settings)


    # Definisci cosa fare alla chiusura della finestra principale
    def on_closing():
        # Ferma il backup scheduler
        print("Finestra chiusa: arresto scheduler backup…")
        scheduler.stop()
        app._cancel_all_after()
        app.quit()  # esce subito dal loop degli eventi
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

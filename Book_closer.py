from Model import DBAccountsColumns, DBUsersColumns
import os
import csv
from datetime import datetime
from typing import Dict, List, Any

class BookCloser:
    def __init__(self, main_view, app_context):
        self.main_view = main_view
        self.app_context = app_context
        self.environment_db_variable = self.app_context.environment_db_variable

        self.current_exercise_year = int(datetime.now().strftime('%Y')) - 1

        # Crea la directory se non esiste
        self.books_dir = os.path.join(self.environment_db_variable, "Books")
        if not os.path.exists(self.books_dir):
            os.makedirs(self.books_dir, exist_ok=True)
            print(f"Creata directory: {self.books_dir}")

        self.annual_data_file_path = os.path.join(self.books_dir, "annual_aggregated_data.csv")
        self.monthly_data_file_path = os.path.join(self.books_dir, "monthly_aggregated_data.csv")
        self.iva_data_file_path = os.path.join(self.books_dir, "iva_aggregated_data.csv")

        # Recupera tutti i conti
        self.accounts = self.app_context.account_controller.retrieve_accounts_map_list()

    def set_current_exercise_year(self, year):
        self.current_exercise_year = year

    def get_current_exercise_year(self):
        return self.current_exercise_year

    def export_accounts_movements(self):
        """Esporta tutti i movimenti dei conti in un file CSV."""
        try:
            print("Inizio esportazione movimenti conti...")

            # Crea il percorso completo del file
            dir_path = os.path.join(self.books_dir, "Accounts_movements")

            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
                print(f"Creata directory: {dir_path}")

            file_path = os.path.join(dir_path, f"Accounts_movements_{self.current_exercise_year}.csv")

            # Apre il file CSV per la scrittura
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                # Definisce l'intestazione del CSV
                fieldnames = [
                    'Conto',
                    'Data',
                    'Descrizione',
                    'Importo',
                    'Segno',
                    'Tipo'
                ]

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                # Contatori per statistiche
                total_movements = 0
                total_accounts = 0

                # Per ogni conto, recupera i movimenti e scrive nel CSV
                for account in self.accounts:
                    account_id = account.get(DBAccountsColumns.ID.value)
                    account_name = account.get(DBAccountsColumns.NAME.value)

                    if not account_id:
                        continue

                    # Recupera i movimenti per questo conto
                    movements = self.app_context.analyzer.retrieve_account_movements_by_account_id(account_id, year = self.current_exercise_year)

                    if not movements:
                        continue

                    total_accounts += 1

                    # Scrivi ogni movimento nel CSV
                    for movement in movements:
                        # Prepara la riga per il CSV
                        row = {
                            'Conto': account_name,
                            'Data': movement.get('date', ''),
                            'Descrizione': movement.get('name', ''),
                            'Importo': abs(float(movement.get('amount', 0))),
                            'Segno': movement.get('sign', ''),
                            'Tipo': movement.get('type', '')
                        }

                        writer.writerow(row)
                        total_movements += 1

            print(f"Esportazione completata!")
            print(f"File salvato in: {file_path}")
            print(f"Conti elaborati: {total_accounts}")
            print(f"Movimenti totali: {total_movements}")

            return file_path, ""

        except Exception as e:
            print(f"Errore durante l'esportazione dei movimenti: {e}")
            return None, f"Errore durante l'esportazione dei movimenti: {e}"

    def update_historical_financial_data(self):
        """Aggiorna i dati finanziari storici per l'anno corrente dell'esercizio."""

        year_str = str(self.current_exercise_year)

        revenues = self.app_context.user_controller.retrieve_users_with_tot_fatturato(year = self.current_exercise_year)
        users = self.app_context.user_controller.retrieve_users_map_list()

        # Crea una mappa ID -> nome completo per facilitare la ricerca
        user_id_to_name = {}
        for user in users:
            user_id = user.get(DBUsersColumns.ID.value)
            first_name = user.get(DBUsersColumns.FIRST_NAME.value)
            last_name = user.get(DBUsersColumns.LAST_NAME.value)
            user_id_to_name[user_id] = f"{first_name} {last_name}"

        spese_dedotte_tot = 0.0

        # Calcola le spese dedotte totali per l'anno (solo per regime ordinario)
        for user in users:
            user_id = user.get(DBUsersColumns.ID.value)
            if user.get(
                    DBUsersColumns.REGIME_FISCALE.value) == self.app_context.user_controller.RegimeFiscale.ORDINARIO.value:
                spese_dedotte_tot += self.app_context.user_controller.calcola_tot_spese_utente_dedotte(user_id, year = self.current_exercise_year)

        # Prepara i dati per la sezione historical_financial_data
        historical_data = {
            "revenues": {},
            "deducted_expenses": {}
        }

        # Carica i dati esistenti
        config = self.app_context.config_manager.load_config()

        if "historical_financial_data" in config:
            # Mantieni i dati esistenti
            existing_data = config["historical_financial_data"]
            historical_data["revenues"] = existing_data.get("revenues", {})
            historical_data["deducted_expenses"] = existing_data.get("deducted_expenses", {})

        # Processa i ricavi
        revenues_dict = {}

        # Unisci i ricavi da entrambi i regimi (forfettario e ordinario)
        # L'output di retrieve_users_with_tot_fatturato() è:
        # {
        #   "FORFETTARIO": {"Cognome1": 10000, "Cognome2": 20000},
        #   "ORDINARIO": {"Cognome3": 30000}
        # }

        for regime in [self.app_context.user_controller.RegimeFiscale.FORFETTARIO.value,
                       self.app_context.user_controller.RegimeFiscale.ORDINARIO.value]:
            if regime in revenues:
                for last_name, total_revenue in revenues[regime].items():
                    # Trova l'utente corrispondente per ottenere il nome completo
                    found_user = None
                    for user in users:
                        if user.get(DBUsersColumns.LAST_NAME.value) == last_name:
                            found_user = user
                            break

                    if found_user:
                        # Usa il nome completo
                        first_name = found_user.get(DBUsersColumns.FIRST_NAME.value, "")
                        full_name = f"{first_name} {last_name}".strip()
                        revenues_dict[full_name] = float(total_revenue)
                    else:
                        # Fallback: usa solo il cognome
                        revenues_dict[last_name] = float(total_revenue)

        # Aggiungi/Aggiorna i dati per l'anno corrente
        historical_data["revenues"][year_str] = revenues_dict
        historical_data["deducted_expenses"][year_str] = spese_dedotte_tot

        # Aggiungi al config manager (aggiorna direttamente la sezione)
        self.app_context.config_manager.update_historical_financial_data(historical_data)

    def export_annual_data(self):
        """
        Create csv file with annual aggregated data
        :return: saldo_conti, media_fatture, media_ore_per_produzione, media_prezzo_orario_produzione, irpef_willow, inps_willow
        """

        # Calcola i dati aggregati
        balances = {}
        for account in self.accounts:
            account_id = account.get(DBAccountsColumns.ID.value)
            account_name = account.get(DBAccountsColumns.NAME.value)
            balances[account_name] = self.app_context.analyzer.calculate_account_balance_by_account_id(account_id, year = self.current_exercise_year)

        tot_fatturato = self.app_context.invoice_controller.calculate_FATT_LORDO_invoiced(year = self.current_exercise_year)
        tot_spese = self.app_context.expense_controller.calculate_tot_expenses(year = self.current_exercise_year)
        media_fatture = self.app_context.invoice_controller.calculate_MEDIA_FATTURA_LORDO_invoiced(year = self.current_exercise_year)
        media_ore_per_produzione = self.app_context.production_controller.mean_hours_for_production(year = self.current_exercise_year)
        media_prezzo_orario_produzione = self.app_context.production_controller.mean_prezzo_orario(year = self.current_exercise_year)
        previsione_tasse = self.app_context.analyzer.calculate_previsione_tasse_willow(year = self.current_exercise_year)
        irpef_willow = previsione_tasse["TOTALE"].get("IRPEF WILLOW", 0.0)
        inps_willow = previsione_tasse["TOTALE"].get("INPS WILLOW", 0.0)

        # Verifica se il file esiste per determinare se scrivere l'header
        file_exists = os.path.isfile(self.annual_data_file_path)

        # Prepara i dati per il CSV
        row_data = {
            'data_esportazione': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'anno': self.current_exercise_year,
            'totale_fatturato': tot_fatturato,
            'totale_spese': tot_spese,
            'media_fatture': media_fatture,
            'media_ore_per_produzione': media_ore_per_produzione,
            'media_prezzo_orario_produzione': media_prezzo_orario_produzione,
            'numero_conti': len(balances),
            'irpef_willow': irpef_willow,
            'inps_willow': inps_willow
        }

        # Aggiungi i saldi dei conti
        for account_name, balance in balances.items():
            # Sostituisci spazi con underscore per nomi colonna più leggibili
            column_name = f"saldo_{account_name.replace(' ', '_').lower()}"
            row_data[column_name] = balance

        # MODIFICA: Gestione aggiornamento se la riga esiste già
        if file_exists:
            try:
                # Leggi il file esistente
                with open(self.annual_data_file_path, 'r', newline='', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    rows = list(reader)

                # Cerca la riga con l'anno corrente
                row_found = False
                for i, row in enumerate(rows):
                    if row.get('anno') == str(self.current_exercise_year):
                        # Aggiorna la riga esistente
                        rows[i] = row_data
                        row_found = True
                        print(f"Aggiornata riga esistente per l'anno {self.current_exercise_year}")
                        break

                # Se non trovata, aggiungi nuova riga
                if not row_found:
                    rows.append(row_data)
                    print(f"Aggiunta nuova riga per l'anno {self.current_exercise_year}")

                # Scrivi di nuovo tutto il file
                with open(self.annual_data_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    if rows:
                        # Ordine colonne: preserva quello originale
                        existing_fieldnames = reader.fieldnames or []

                        # Individua eventuali nuove colonne (es. nuovi conti)
                        new_fieldnames = []
                        for row in rows:
                            for key in row.keys():
                                if key not in existing_fieldnames and key not in new_fieldnames:
                                    new_fieldnames.append(key)

                        fieldnames = existing_fieldnames + new_fieldnames

                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(rows)

            except Exception as e:
                print(f"Errore nell'aggiornamento del file esistente: {e}")
                # Fallback: append della riga
                with open(self.annual_data_file_path, 'a', newline='', encoding='utf-8') as csvfile:
                    fieldnames = list(row_data.keys())
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                    # Se il file è vuoto o corrotto, scrivi l'header
                    if not file_exists or os.path.getsize(self.annual_data_file_path) == 0:
                        writer.writeheader()

                    writer.writerow(row_data)

        else:
            # File non esiste: crealo con la prima riga
            with open(self.annual_data_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = list(row_data.keys())
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerow(row_data)

            print(f"Creato nuovo file per l'anno {self.current_exercise_year}")

        print(f"Dati annuali aggregati esportati in: {self.annual_data_file_path}")
        print(f"Anno di riferimento: {self.current_exercise_year}")

        return balances, media_fatture, media_ore_per_produzione, media_prezzo_orario_produzione, irpef_willow, inps_willow

    def export_monthly_data(self):
        """
        Create csv file with monthly aggregated data
        :return: dict con i dati mensili esportati
        """

        # Recupera i dati mensili dall'analyzer
        monthly_data = self.app_context.analyzer.retrieve_monthly_data(year = self.current_exercise_year)

        # Verifica se il file esiste per determinare se scrivere l'header
        file_exists = os.path.isfile(self.monthly_data_file_path)

        # Dati da raccogliere per ogni mese
        monthly_rows = []

        for month in range(1, 13):
            # Recupera il salario medio per il mese
            try:
                mean_salary = self.app_context.salary_controller.calculate_mean_salary_by_month(month = month, year = self.current_exercise_year)
                if mean_salary is None:
                    mean_salary = 0.0
            except Exception as e:
                print(f"Errore nel calcolo del salario medio per il mese {month}: {e}")
                mean_salary = 0.0

            # Prepara i dati del mese
            month_key = month
            month_data = monthly_data.get(month_key, {})
            values = month_data.get('values', {})
            averages = month_data.get('averages', {})
            deviations = month_data.get('deviations', {})

            # Formatta il nome del mese-anno
            month_year = f"{month:02d}-{self.current_exercise_year}"

            # Nome del mese in italiano
            months_ita = [
                'Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
                'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre'
            ]
            month_name = months_ita[month - 1]

            # Crea la riga del mese
            row_data = {
                'mese_anno': month_year,
                'mese': month,
                'nome_mese': month_name,
                'anno': self.current_exercise_year,
                'data_esportazione': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'fatturato': values.get('fatturato', 0.0),
                'spese': values.get('spese', 0.0),
                'entrate': values.get('incomes', 0.0),
                'uscite': values.get('outcomes', 0.0),
                'salario_medio_utente': mean_salary,
                'bilancio_mensile': values.get('incomes', 0.0) - values.get('outcomes', 0.0),  # Entrate - Uscite
                'fatturato_medio': averages.get('fatturato', 0.0),
                'spese_medie': averages.get('spese', 0.0),
                'entrate_medie': averages.get('incomes', 0.0),
                'uscite_medie': averages.get('outcomes', 0.0),
                'deviazione_fatturato': deviations.get('fatturato', 0.0),
                'deviazione_spese': deviations.get('spese', 0.0),
                'deviazione_entrate': deviations.get('incomes', 0.0),
                'deviazione_uscite': deviations.get('outcomes', 0.0)
            }

            # Calcola indicatori aggiuntivi
            try:
                # Margine operativo
                fatturato = values.get('fatturato', 0.0)
                spese = values.get('spese', 0.0)
                if fatturato > 0:
                    row_data['margine_operativo_percentuale'] = ((fatturato - spese) / fatturato) * 100
                else:
                    row_data['margine_operativo_percentuale'] = 0.0

                # Saldo netto mensile
                row_data['saldo_netto'] = row_data['bilancio_mensile']

                # Rapporto entrate/uscite
                uscite = values.get('outcomes', 0.0)
                if uscite > 0:
                    row_data['rapporto_entrate_uscite'] = values.get('incomes', 0.0) / uscite
                else:
                    row_data['rapporto_entrate_uscite'] = 0.0

            except Exception as e:
                print(f"Errore nel calcolo degli indicatori per il mese {month}: {e}")
                row_data['margine_operativo_percentuale'] = 0.0
                row_data['rapporto_entrate_uscite'] = 0.0

            monthly_rows.append(row_data)

        # Ordina le righe per mese
        monthly_rows.sort(key=lambda x: x['mese'])

        # MODIFICA: Gestione aggiornamento se il file esiste già
        if file_exists:
            try:
                # Leggi il file esistente
                with open(self.monthly_data_file_path, 'r', newline='', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    existing_rows = list(reader)

                if existing_rows:
                    # Filtra le righe: rimuovi quelle dell'anno corrente per sostituirle
                    filtered_rows = [
                        row for row in existing_rows
                        if row.get('anno') != str(self.current_exercise_year)
                    ]

                    # Aggiungi le nuove righe per l'anno corrente
                    filtered_rows.extend(monthly_rows)

                    # Ordina tutte le righe per anno e mese
                    filtered_rows.sort(key=lambda x: (int(x.get('anno', 0)), int(x.get('mese', 0))))

                    # Riscrivi tutto il file con tutte le righe
                    with open(self.monthly_data_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                        # Prepara l'header con tutte le chiavi (unione di tutte le righe)
                        # Ordine colonne: preserva quello originale
                        existing_fieldnames = reader.fieldnames or []

                        # Trova eventuali nuove colonne non presenti nel file originale
                        new_fieldnames = []
                        for row in filtered_rows:
                            for key in row.keys():
                                if key not in existing_fieldnames and key not in new_fieldnames:
                                    new_fieldnames.append(key)

                        fieldnames = existing_fieldnames + new_fieldnames

                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(filtered_rows)

                    replaced_months = len(existing_rows) - len(filtered_rows) + len(monthly_rows)
                    print(f"Aggiornati dati mensili per l'anno {self.current_exercise_year} ({replaced_months} mesi)")
                else:
                    # File esiste ma è vuoto o ha solo header
                    with open(self.monthly_data_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                        if monthly_rows:
                            fieldnames = list(monthly_rows[0].keys())
                            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                            writer.writeheader()
                            writer.writerows(monthly_rows)

                    print(f"Aggiunti dati mensili per l'anno {self.current_exercise_year} (file esistente ma vuoto)")

            except Exception as e:
                print(f"Errore nell'aggiornamento del file mensile esistente: {e}")
                # Fallback: sovrascrivi il file con i nuovi dati
                with open(self.monthly_data_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    if monthly_rows:
                        fieldnames = list(monthly_rows[0].keys())
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(monthly_rows)

                print(f"Creato nuovo file mensile per l'anno {self.current_exercise_year} (fallback per errore)")

        else:
            # File non esiste: crealo con i dati
            with open(self.monthly_data_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                if monthly_rows:
                    fieldnames = list(monthly_rows[0].keys())
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(monthly_rows)

            print(f"Creato nuovo file mensile per l'anno {self.current_exercise_year}")

        return {
            'monthly_data': monthly_rows,
            'file_path': self.monthly_data_file_path
        }

    def export_trimestral_iva_data(self):
        """
        Create / update CSV file with trimestral IVA data aggregated by user and year
        :return: dict con i dati IVA trimestrali esportati
        """

        # Recupera i dati IVA trimestrali dall'analyzer
        iva_data = self.app_context.analyzer.calculate_tot_trimestral_iva(year = self.current_exercise_year)

        # Verifica se il file esiste
        file_exists = os.path.isfile(self.iva_data_file_path)

        trimestral_rows = []

        trimestri_order = [
            ("Gen-Marz", 1),
            ("Apr-Giu", 2),
            ("Lug-Sett", 3),
            ("Ott-Dic", 4)
        ]

        export_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Costruzione righe
        for user_name, trimestri in iva_data.items():
            for trimestre_name, trimestre_num in trimestri_order:
                valori = trimestri.get(trimestre_name, {})

                debito = float(valori.get("debito", 0.0))
                credito = float(valori.get("credito", 0.0))
                da_pagare = float(valori.get("da_pagare", 0.0))

                row = {
                    "anno": self.current_exercise_year,
                    "trimestre": trimestre_num,
                    "nome_trimestre": trimestre_name,
                    "utente": user_name,
                    "iva_debito": round(debito, 2),
                    "iva_credito": round(credito, 2),
                    "iva_da_pagare": round(da_pagare, 2),
                    "data_esportazione": export_timestamp
                }

                trimestral_rows.append(row)

        # Ordina per anno, utente, trimestre
        trimestral_rows.sort(
            key=lambda x: (
                int(x["anno"]),
                x["utente"],
                int(x["trimestre"])
            )
        )

        # =========================
        # SCRITTURA / AGGIORNAMENTO FILE
        # =========================

        if file_exists:
            try:
                with open(self.iva_data_file_path, 'r', newline='', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    existing_rows = list(reader)
                    existing_fieldnames = reader.fieldnames or []

                # Rimuovi righe dell'anno corrente
                filtered_rows = [
                    row for row in existing_rows
                    if str(row.get("anno")) != str(self.current_exercise_year)
                ]

                # Aggiungi nuove righe
                filtered_rows.extend(trimestral_rows)

                # Ricalcola fieldnames (mantiene ordine originale)
                new_fieldnames = []
                for row in filtered_rows:
                    for key in row.keys():
                        if key not in existing_fieldnames and key not in new_fieldnames:
                            new_fieldnames.append(key)

                fieldnames = existing_fieldnames + new_fieldnames

                # Riscrittura completa file
                with open(self.iva_data_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(filtered_rows)

                print(f"Aggiornati dati IVA trimestrali per l'anno {self.current_exercise_year}")

            except Exception as e:
                print(f"Errore aggiornamento file IVA trimestrale: {e}")
                # Fallback: sovrascrittura completa
                with open(self.iva_data_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = list(trimestral_rows[0].keys()) if trimestral_rows else []
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(trimestral_rows)

                print(f"Creato nuovo file IVA trimestrale (fallback)")

        else:
            # File non esiste
            with open(self.iva_data_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                if trimestral_rows:
                    fieldnames = list(trimestral_rows[0].keys())
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(trimestral_rows)

            print(f"Creato nuovo file IVA trimestrale per l'anno {self.current_exercise_year}")

        return {
            "trimestral_iva_data": trimestral_rows,
            "file_path": self.iva_data_file_path
        }

    def import_initial_balances(self):
        """
        Legge i saldi dei conti dal file annual_aggregated_data.csv per l'anno corrente
        e aggiorna i conti nel database con questi valori come saldo iniziale.
        """
        try:
            # Verifica che il file annuale esista
            annual_file_path = os.path.join(self.books_dir, "annual_aggregated_data.csv")
            if not os.path.isfile(annual_file_path):
                return False, f"File annuale non trovato: {annual_file_path}"

            # Leggi il file CSV
            with open(annual_file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                rows = list(reader)

            # Trova la riga per l'anno corrente
            target_row = None
            for row in rows:
                if row.get('anno') == str(self.current_exercise_year):
                    target_row = row
                    break

            if not target_row:
                return False, f"Nessun dato trovato per l'anno {self.current_exercise_year} nel file annuale"

            # Recupera tutti i conti
            self.accounts = self.app_context.account_controller.retrieve_accounts_map_list()

            updated_count = 0
            errors = []

            for account in self.accounts:
                try:
                    account_id = account.get(DBAccountsColumns.ID.value)
                    account_name = account.get(DBAccountsColumns.NAME.value)

                    # Costruisci il nome della colonna come nel file CSV
                    column_name = f"saldo_{account_name.replace(' ', '_').lower()}"

                    # Prendi il valore dal file
                    value_str = target_row.get(column_name)

                    if value_str is not None and value_str != '':
                        try:
                            value_from_file = float(value_str)
                        except ValueError:
                            errors.append(f"Valore non valido per {account_name}: '{value_str}'")
                            continue

                        # Prepara i dati per l'aggiornamento
                        data = {
                            DBAccountsColumns.INIT_BALANCE.value: value_from_file,
                            DBAccountsColumns.UPDATED_AT.value: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }

                        # Chiama il controller per aggiornare il conto
                        success, message = self.app_context.account_controller.update_account(account_id, data)

                        if success:
                            updated_count += 1
                            print(f"Aggiornato saldo iniziale per '{account_name}': €{value_from_file:,.2f}")
                        else:
                            errors.append(f"Errore aggiornamento {account_name}: {message}")
                    else:
                        # Nessun valore per questo conto nel file
                        continue

                except Exception as e:
                    account_name = account.get(DBAccountsColumns.NAME.value, "Unknown")
                    errors.append(f"Errore elaborazione conto {account_name}: {str(e)}")

            # Costruisci messaggio di risultato
            if updated_count == 0 and not errors:
                return False, "Nessun conto è stato aggiornato. Verificare la struttura del file."
            elif errors:
                error_summary = f"Aggiornati {updated_count} conti. Errori: {len(errors)}"
                if len(errors) <= 3:
                    error_summary += f"\n" + "\n".join(errors)
                else:
                    error_summary += f"\nPrimi 3 errori:\n" + "\n".join(errors[:3])
                return (updated_count > 0), error_summary
            else:
                return True, f"Successo! Aggiornati {updated_count} conti su {len(self.accounts)}"

        except Exception as e:
            return False, f"Errore durante l'importazione dei saldi iniziali: {str(e)}"

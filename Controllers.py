import re
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from enum import Enum

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
import hashlib
import pandas as pd
import numpy as np


from Fatturazione_elettronica_API import FatturazioneElettronicaProvider
from Model import DatabaseModel, DBUsersColumns, DBClientsColumns, DBInvoicesColumns, \
DBPaymentsColumns, DBProductionsColumns, DBAccountsColumns, DBExpensesColumns, \
DBSuppliersColumns, DBTransfersColumns, DBSalariesColumns, DBRefundsColumns

from Views.View_utils import ViewUtils

no_data_string = "no data"


# Classe Helper per le validazioni
class ValidationUtils:
    @staticmethod
    def validate_partita_iva(partita_iva):
        """Valida la partita IVA: deve contenere esattamente 11 cifre"""
        return bool(re.fullmatch(r"\d{11}", partita_iva))

    @staticmethod
    def validate_email(email):
        """Valida un indirizzo email"""
        return bool(re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email))

    @staticmethod
    def validate_phone_number(phone_number):
        """Valida che il numero di telefono sia composto solo da cifre e abbia una lunghezza accettabile."""
        return isinstance(phone_number, str) and phone_number.isdigit() and 8 <= len(phone_number) <= 15

    @staticmethod
    def validate_amount(amount):
        """
        Valida che l'importo sia una stringa che rappresenta un numero non negativo,
        con opzionalmente una parte decimale (al massimo due cifre decimali).

        Esempi di formati accettati:
          - "100"
          - "100.5"
          - "100.50"

        Ritorna True se l'input è valido, altrimenti False.
        """
        if not isinstance(amount, str):
            return False

        # Regex: una o più cifre, opzionalmente seguite da un punto e 1 o 2 cifre
        pattern = r"^\d+(\.\d{1,2})?$"
        return re.fullmatch(pattern, amount) is not None

    @staticmethod
    def validate_integers(int):
        """
        Valida che l'intero sia effettivamente una stringa che può essere trasformata in un intero
        """
        if not int.isdigit():
            return False
        else:
            return True

    @staticmethod
    def _row_to_map(row, database_columns):
        """Converte una singola riga in un dizionario."""
        if row is None:
            return None
        keys = [column.value for column in database_columns]
        return dict(zip(keys, row))


class ControllerUtils:
    @staticmethod
    def parse_date(date_str):
        """Prova a convertire una stringa in un oggetto date."""
        if date_str is None:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").date()
        except ValueError:
            try:
                return datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return None

    @staticmethod
    def normalize_string_for_key(s: str) -> str:
        # Inserisce uno spazio prima di ogni lettera maiuscola se preceduta da una lettera minuscola (gestione camelCase)
        s = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', s)
        # Divide la stringa su spazi, underscore o trattini
        words = re.split(r'[\s_-]+', s)
        # Rimuove eventuali elementi vuoti e trasforma in uppercase
        words = [word.upper() for word in words if word]
        # Unisce le parole con "_"
        return "_".join(words)

    @staticmethod
    def is_in_current_year(date_str: str, date_formats: list[str] = None) -> bool:
        """
        Restituisce True se la data passata (stringa) cade nell'anno corrente.
        :param date_str: data in formato 'YYYY-MM-DD' o 'YYYY-MM-DD HH:MM:SS'
        :param date_formats: lista di formati da provare in ordine (default quelli comuni)
        """
        fmts = date_formats or ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]
        for fmt in fmts:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.year == datetime.now().year
            except ValueError:
                continue
        # se nessun formato corrisponde, consideriamo fuori anno
        return False

    # Formati di data supportati
    DATE_FORMATS = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d"
    ]

    @staticmethod
    def _parse_date(date_str):
        """Tenta di parsare una data da stringa con vari formati"""
        for fmt in ControllerUtils.DATE_FORMATS:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def filter_invoices(invoices, db_model, current_year=True):
        """
        Filtra le fatture mantenendo:
          - Tutte le fatture emesse nell'anno corrente
          - Fatture di anni precedenti solo se:
              a) Hanno ancora rate non saldate
              b) Hanno almeno una rata pagata nell'anno corrente

        Funziona sia con liste che con singole fatture.

        :param invoices: Singola fattura o lista di fatture (tuple)
        :param db_model: Istanza del DatabaseModel per accedere ai dati
        :param current_year: Se True, applica il filtro combinato
        :return: Lista filtrata di fatture o singola fattura
        """
        # Gestione del caso di singola fattura
        single_item = not isinstance(invoices, list)
        if single_item:
            invoices = [invoices]

        if not current_year or not invoices:
            return invoices[0] if single_item else invoices

        # Recupera TUTTI i pagamenti (non solo recenti)
        all_payments = db_model.fetch_payments()
        payments_map = [ValidationUtils._row_to_map(p, DBPaymentsColumns) for p in all_payments]

        # Preparazione per l'accesso alle colonne
        columns = [col.value for col in DBInvoicesColumns]
        creation_index = columns.index(DBInvoicesColumns.DATA_CREAZIONE.value)
        id_index = columns.index(DBInvoicesColumns.ID.value)
        rate_index = columns.index(DBInvoicesColumns.NUMERO_RATE.value)

        current_year_value = datetime.now().year
        filtered_rows = []

        # Creiamo strutture per tracciare i pagamenti
        invoice_payments = {}
        for payment in payments_map:
            invoice_id = payment[DBPaymentsColumns.INVOICE_ID.value]
            if invoice_id not in invoice_payments:
                invoice_payments[invoice_id] = []
            invoice_payments[invoice_id].append(payment)

        for row in invoices:
            invoice_id = row[id_index]
            num_rate = row[rate_index] if row[rate_index] is not None else 1

            # Estrai l'anno di creazione della fattura
            date_str = row[creation_index]
            try:
                creation_dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                creation_dt = datetime.strptime(date_str, "%Y-%m-%d")

            # Fatture dell'anno corrente: sempre incluse
            if creation_dt.year == current_year_value:
                filtered_rows.append(row)
                continue

            # Fatture di anni precedenti: verifica le condizioni
            has_unpaid_rates = False
            has_current_year_payment = False

            # Controlla se ci sono pagamenti per questa fattura
            payments = invoice_payments.get(invoice_id, [])

            # Verifica se ci sono rate non pagate
            paid_rates = set()
            for payment in payments:
                paid_rates.add(payment[DBPaymentsColumns.LINKED_RATA.value])

                # Verifica se il pagamento è nell'anno corrente
                payment_date_str = payment[DBPaymentsColumns.PAYMENT_DATE.value]
                try:
                    payment_dt = datetime.strptime(payment_date_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    payment_dt = datetime.strptime(payment_date_str, "%Y-%m-%d")

                if payment_dt.year == current_year_value:
                    has_current_year_payment = True

            if len(paid_rates) < num_rate:
                has_unpaid_rates = True

            # Mantieni le fatture di anni precedenti che soddisfano le condizioni
            if has_unpaid_rates or has_current_year_payment:
                filtered_rows.append(row)

        return filtered_rows[0] if single_item and filtered_rows else filtered_rows

    @staticmethod
    def filter_expenses(expenses, current_year=True):
        if not current_year or not expenses:
            return expenses

        current_year_value = datetime.now().year
        return [
            exp for exp in expenses
            if (date_str := exp.get(DBExpensesColumns.DATE.value)) and
               (dt := ControllerUtils._parse_date(date_str)) and
               dt.year == current_year_value
        ]

    @staticmethod
    def filter_payments(payments, current_year=True):
        if not current_year or not payments:
            return payments

        current_year_value = datetime.now().year
        return [
            p for p in payments
            if (date_str := p.get(DBPaymentsColumns.PAYMENT_DATE.value)) and
               (dt := ControllerUtils._parse_date(date_str)) and
               dt.year == current_year_value
        ]

    @staticmethod
    def filter_refunds(refunds, current_year=True):
        if not current_year or not refunds:
            return refunds

        current_year_value = datetime.now().year
        return [
            r for r in refunds
            if (date_str := r.get(DBRefundsColumns.REFUND_DATE.value)) and
               (dt := ControllerUtils._parse_date(date_str)) and
               dt.year == current_year_value
        ]

    @staticmethod
    def filter_productions(productions, current_year=True):
        """
        Filtra le produzioni mantenendo solo quelle create nell'anno corrente.
        Gestisce sia liste che singole produzioni.

        :param productions: Singola produzione o lista di produzioni (dizionari)
        :param current_year: Se True, applica il filtro dell'anno corrente
        :return: Lista filtrata o singola produzione
        """
        # Gestione del caso di singolo elemento
        single_item = not isinstance(productions, list)
        if single_item:
            productions = [productions]

        if not current_year or not productions:
            return productions[0] if single_item else productions

        current_year_value = datetime.now().year
        filtered = []

        for prod in productions:
            date_str = prod.get(DBProductionsColumns.CREATED_AT.value)
            if not date_str:
                continue

            try:
                # Utilizza il metodo di parsing esistente
                dt = ControllerUtils._parse_date(date_str)
                if dt.year == current_year_value:
                    filtered.append(prod)
            except Exception as e:
                print(f"Errore durante il parsing della data '{date_str}': {e}")

        return filtered[0] if single_item and filtered else filtered

    @staticmethod
    def filter_salaries(salaries, current_year=True):
        """
        Filtra i versamenti mantenendo solo quelli effettuati nell'anno corrente.
        Gestisce sia liste che singoli versamenti.

        :param salaries: Singolo versamento o lista di versamenti (dizionari)
        :param current_year: Se True, applica il filtro dell'anno corrente
        :return: Lista filtrata o singolo versamento
        """
        # Gestione del caso di singolo elemento
        single_item = not isinstance(salaries, list)
        if single_item:
            salaries = [salaries]

        if not current_year or not salaries:
            return salaries[0] if single_item else salaries

        current_year_value = datetime.now().year
        filtered = []

        for sal in salaries:
            date_str = sal.get(DBSalariesColumns.DATE.value)
            if not date_str:
                continue

            try:
                dt = ControllerUtils._parse_date(date_str)
                if dt.year == current_year_value:
                    filtered.append(sal)
            except Exception as e:
                print(f"Errore durante il parsing della data '{date_str}': {e}")

        return filtered[0] if single_item and filtered else filtered

    @staticmethod
    def filter_transfers(transfers, current_year=True):
        if not current_year or not transfers:
            return transfers

        current_year_value = datetime.now().year
        return [
            tr for tr in transfers
            if (date_str := tr.get(DBTransfersColumns.DATE.value)) and
               (dt := ControllerUtils._parse_date(date_str)) and
               dt.year == current_year_value
        ]

    @staticmethod
    def clear_invoices_list_from_NDC_and_stornate(invoices_list_of_maps):

        return [inv for inv in invoices_list_of_maps if
                inv[DBInvoicesColumns.TIPO.value] != InvoiceController.Tipologia.NOTA_DI_CREDITO.value and inv[
                    DBInvoicesColumns.STATUS.value] != InvoiceController.InvoiceRateizzSatus.STORNATA.value]





class UserController:

    class RegimeFiscale(Enum):
        FORFETTARIO = "Forfettario"
        ORDINARIO = "Ordinario"

    class UserStatus(Enum):
        ATTIVO = "attivo"
        DISATTIVO = "disattivo"

    def __init__(self, db_model: DatabaseModel, fiscal_settings):
        """Inizializza il controller con il modello del database"""
        self.db_model = db_model
        self.fiscal_settings = fiscal_settings

        #definisco qui i campi obbligatori chel'utente deve inserire da interfaccia per salvare/updatare uno user nel db
        self.required_fields = {
            DBUsersColumns.FIRST_NAME.value,
            DBUsersColumns.LAST_NAME.value,
            DBUsersColumns.PARTITA_IVA.value,
            DBUsersColumns.REGIME_FISCALE.value,
            DBUsersColumns.ANNO_APERTURA_PIVA.value,
            DBUsersColumns.PROVIDER_FATTURE.value
        }

        self.secret_key = hashlib.sha256("Neomisia".encode()).digest()

        #self.users_list = self.retrieve_users_map_list()

    def save_user(self, user_data):
        """
        Gestisce il salvataggio di un utente, con validazioni di primo livello.
        :param user_data: Dizionario contenente i dati dell'utente
        :return: Tuple (success, message), dove success è True/False
        """
        if user_data[DBUsersColumns.PROVIDER_FATTURE.value] != FatturazioneElettronicaProvider.NESSUNO.value:
            self.required_fields.add(DBUsersColumns.USERNAME_PROVIDER.value)
            self.required_fields.add(DBUsersColumns.PASSWORD_PROVIDER.value)

        # Validazione dei campi obbligatori
        missing_fields = [field for field in self.required_fields if not user_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."


        # Validazione Partita IVA
        if not ValidationUtils.validate_partita_iva(user_data[DBUsersColumns.PARTITA_IVA.value]):
            return False, "La partita IVA non è valida. Deve contenere esattamente 11 cifre."

        # Validazione Email
        email = user_data.get(DBUsersColumns.EMAIL.value)
        if email and not ValidationUtils.validate_email(email):
            return False, "L'indirizzo email non è valido."

        # Cifra i dati di accesso se il provider è selezionato
        if user_data.get(DBUsersColumns.PROVIDER_FATTURE.value) != FatturazioneElettronicaProvider.NESSUNO.value:
            try:
                username_provider = user_data.get(DBUsersColumns.USERNAME_PROVIDER.value)
                password_provider = user_data.get(DBUsersColumns.PASSWORD_PROVIDER.value)

                if username_provider:
                    user_data[DBUsersColumns.USERNAME_PROVIDER.value] = self.encrypt_string(username_provider)
                else:
                    user_data[DBUsersColumns.USERNAME_PROVIDER.value] = None

                if password_provider:
                    user_data[DBUsersColumns.PASSWORD_PROVIDER.value] = self.encrypt_string(password_provider)
                else:
                    user_data[DBUsersColumns.PASSWORD_PROVIDER.value] = None

            except Exception as e:
                # Log dell'errore per debug (da rimuovere o proteggere in produzione)
                print(f"Errore durante la cifratura dei dati di accesso: {e}")

                # Imposta i valori come None per sicurezza
                user_data[DBUsersColumns.USERNAME_PROVIDER.value] = None
                user_data[DBUsersColumns.PASSWORD_PROVIDER.value] = None

        # Preparazione dei dati per il salvataggio
        user_data_filtered = {
            column.value: user_data.get(column.value)
            for column in DBUsersColumns
            if column.value in user_data
        }

        # Rimuove i campi None
        user_data_filtered = {key: value for key, value in user_data_filtered.items() if value is not None}

        # Salvataggio nel DB
        try:
            self.db_model.add_user(**user_data_filtered)
            #self.update_users_list()
            return True, "Utente salvato con successo!"
        except Exception as e:
            return False, f"Errore durante il salvataggio: {str(e)}"

    def retrieve_users(self):
        return self.db_model.fetch_users()

    def retrieve_user_by_id(self, user_id):
        return self.db_model.fetch_user_by_id(user_id)

    def retrieve_user_by_fullname(self, user_first_name, user_last_name):
        return self.db_model.fetch_user_by_fullname(user_first_name, user_last_name)

    def retrieve_user_map_by_fullname(self, user_first_name, user_last_name):
        row = self.retrieve_user_by_fullname(user_first_name, user_last_name)
        return ValidationUtils._row_to_map(row, DBUsersColumns)

    def retrieve_user_map_by_extended_name(self, user_extended_name):
        """
        :param user_extended_name: str composed as following: user_first_name user_last_name
        :return: the DBuser as a dictionary
        """

        array = user_extended_name.split(" ")
        first = array[0]
        last = array[1]

        return self.retrieve_user_map_by_fullname(first, last)

    def id_to_full_name_tuple(self, user_id:int) -> [str, str]:
        """:return The tuple containing first and second name"""

        user = self.retrieve_user_by_id(user_id)
        return [user[DBUsersColumns.FIRST_NAME.value], user[DBUsersColumns.LAST_NAME.value]]

    def id_to_full_name_str(self, user_id: int) -> str:
        """:return The string containing first and second name"""

        user = self.retrieve_user_map_by_id(user_id)
        return user[DBUsersColumns.FIRST_NAME.value] + " " + user[DBUsersColumns.LAST_NAME.value]

    def retrieve_user_map_by_id(self, user_id):
        """Recupera un utente specifico e lo restituisce come dizionario."""
        row = self.db_model.fetch_user_by_id(user_id)
        return ValidationUtils._row_to_map(row, DBUsersColumns)

    def retrieve_users_map_list(self):
        """Recupera tutti gli utenti e li restituisce come lista di dizionari."""
        rows = self.db_model.fetch_users()
        return [ValidationUtils._row_to_map(row, DBUsersColumns) for row in rows]

    def retrieve_user_with_invoices_map_list(self, user_id):
        """
        Recupera lo specifico user unito alle rispettive fatture e
        li restituisce come lista di dizionari.

        Utilizza la funzione fetch_user_with_invoices per ottenere le righe,
        quindi combina le colonne dei client e delle invoices per convertire
        ogni riga in un dizionario tramite _row_to_map.
        """
        # Recupera le righe dal database per lo specifico client
        rows = self.db_model.fetch_user_with_invoices(user_id)

        all_columns = list(DBUsersColumns) + list(DBInvoicesColumns)

        # Converte ogni riga in un dizionario
        return [ValidationUtils._row_to_map(row, all_columns) for row in rows]

    def retrieve_users_with_tot_fatturato(self) -> dict[str, dict[str, float]]:
        output_map = {
            self.RegimeFiscale.FORFETTARIO.value : {},
            self.RegimeFiscale.ORDINARIO.value: {}
        }

        for user in self.retrieve_users_map_list():
            if user[DBUsersColumns.REGIME_FISCALE.value] == self.RegimeFiscale.FORFETTARIO.value:
                output_map[self.RegimeFiscale.FORFETTARIO.value][user[DBUsersColumns.LAST_NAME.value]] = self.calcola_tot_fatturato_utente(user[DBUsersColumns.ID.value])
            elif user[DBUsersColumns.REGIME_FISCALE.value] == self.RegimeFiscale.ORDINARIO.value:
                output_map[self.RegimeFiscale.ORDINARIO.value][user[DBUsersColumns.LAST_NAME.value]] = self.calcola_tot_fatturato_utente(user[DBUsersColumns.ID.value])

        return output_map

    def retrieve_users_with_tot_spese(self) -> dict[str, float]:
        output_map: dict[str, float] = {}

        for user in self.retrieve_users_map_list():
            user_id = user[DBUsersColumns.ID.value]
            cognome = user[DBUsersColumns.LAST_NAME.value]
            chiave = f"{cognome}"

            output_map[chiave] = self.calcola_tot_spese_utente_dedotte(user_id)

        return output_map

    def retrieve_user_with_anticipated_expenses_map_list(self, user_id):
        """
        Recupera lo specifico user unito alle rispettive spese anticipate e
        li restituisce come lista di dizionari.

        Utilizza la funzione fetch_user_with_expenses per ottenere le righe,
        quindi combina le colonne dei client e delle invoices per convertire
        ogni riga in un dizionario tramite _row_to_map.
        """
        # Recupera le righe dal database per lo specifico client
        rows = self.db_model.fetch_user_with_anticipated_expenses(user_id)

        all_columns = list(DBUsersColumns) + list(DBExpensesColumns)

        # Converte ogni riga in un dizionario
        return [ValidationUtils._row_to_map(row, all_columns) for row in rows]

    def retrieve_user_with_deducted_expenses_map_list(self, user_id):
        """
        Recupera lo specifico user unito alle rispettive spese in deduzione e
        li restituisce come lista di dizionari.

        Utilizza la funzione fetch_user_with_expenses per ottenere le righe,
        quindi combina le colonne dei client e delle invoices per convertire
        ogni riga in un dizionario tramite _row_to_map.
        """
        # Recupera le righe dal database per lo specifico client
        rows = self.db_model.fetch_user_with_deducted_expenses(user_id)

        all_columns = list(DBUsersColumns) + list(DBExpensesColumns)

        # Converte ogni riga in un dizionario
        return [ValidationUtils._row_to_map(row, all_columns) for row in rows]

    def retrieve_user_with_salaries_map_list(self, user_id):
        """
        Recupera lo specifico user unito ai rispettivi salari e
        li restituisce come lista di dizionari.
        """
        # Recupera le righe dal database per lo specifico client
        rows = self.db_model.fetch_user_with_salaries(user_id)

        all_columns = list(DBUsersColumns) + list(DBSalariesColumns)

        # Converte ogni riga in un dizionario
        return [ValidationUtils._row_to_map(row, all_columns) for row in rows]

    def delete_user_by_ID(self, user_id):
        """Elimina un utente dato un certo user"""
        table = "users"
        try:
            self.db_model.delete_row(table, DBUsersColumns.ID.value, user_id)
            print(f"Utente {user_id} rimmosso con successo")
            return True, f"Utente {user_id} rimmosso con successo"
        except Exception as e:
            return False, f"Errore durante l'eliminazione dell'utente: {str(e)}"

    def update_user(self, user_id, user_data):
        """
        Aggiorna i dati di un utente esistente, applicando le stesse validazioni di `save_user`.
        :param user_id: ID dell'utente da aggiornare
        :param user_data: Dizionario contenente i dati da aggiornare
        :return: Tuple (success, message), dove success è True/False
        """

        # Controllo validità user_id
        if not user_id or not isinstance(user_id, int):
            return False, "ID utente non valido. Deve essere un intero positivo."

        # Filtra solo i campi validi definiti nell'Enum
        valid_columns = {column.value for column in DBUsersColumns}
        update_fields = {key: value for key, value in user_data.items() if key in valid_columns}

        if not update_fields:
            return False, "Nessun campo valido fornito per l'aggiornamento."


        # Validazione campi obbligatori
        if update_fields.get(
                DBUsersColumns.PROVIDER_FATTURE.value) != FatturazioneElettronicaProvider.NESSUNO.value:
            self.required_fields.add(DBUsersColumns.USERNAME_PROVIDER.value)
            self.required_fields.add(DBUsersColumns.PASSWORD_PROVIDER.value)

        missing_fields = [field for field in self.required_fields if not update_fields.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        # Validazione Partita IVA
        if DBUsersColumns.PARTITA_IVA.value in update_fields:
            if not ValidationUtils.validate_partita_iva(update_fields[DBUsersColumns.PARTITA_IVA.value]):
                return False, "La partita IVA non è valida. Deve contenere esattamente 11 cifre."

        # Validazione Email
        if DBUsersColumns.EMAIL.value in update_fields:
            email = update_fields[DBUsersColumns.EMAIL.value]
            if email and not ValidationUtils.validate_email(email):
                return False, "L'indirizzo email non è valido."

        # Cifratura dei dati di accesso se il provider è selezionato
        if update_fields.get(DBUsersColumns.PROVIDER_FATTURE.value) != FatturazioneElettronicaProvider.NESSUNO.value:
            try:
                if DBUsersColumns.USERNAME_PROVIDER.value in update_fields:
                    update_fields[DBUsersColumns.USERNAME_PROVIDER.value] = self.encrypt_string(
                        update_fields[DBUsersColumns.USERNAME_PROVIDER.value]
                    )
                if DBUsersColumns.PASSWORD_PROVIDER.value in update_fields:
                    update_fields[DBUsersColumns.PASSWORD_PROVIDER.value] = self.encrypt_string(
                        update_fields[DBUsersColumns.PASSWORD_PROVIDER.value]
                    )
            except Exception as e:
                print(f"Errore durante la cifratura dei dati di accesso: {e}")
                return False, "Errore durante la cifratura dei dati di accesso."
        else:
            update_fields.pop(DBUsersColumns.USERNAME_PROVIDER.value)
            update_fields.pop(DBUsersColumns.PASSWORD_PROVIDER.value)

        try:
            # Invoca il metodo del model per aggiornare l'utente
            self.db_model.update_user(user_id, **update_fields)
            return True, "Utente aggiornato con successo!"

        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento dell'utente: {str(e)}"

    def calcola_reddito_tot_utente(self, user_id):
        """
        Calcola il reddito di un utente a partire da un reddito esterno e la somma dei lordi delle fatture
        :param user_id: ID dell'utente
        :return: il reddito
        """
        invoices = self.db_model.fetch_invoices_by_user_id(user_id)
        reddito_esterno = self.retrieve_user_map_by_id(user_id)[DBUsersColumns.REDDITO_ESTERNO.value]
        reddito = reddito_esterno

        # Filtro le fatture emesse solo nell'anno corrente
        current_year_value = datetime.now().year
        invoices = [
            invoice
            for invoice in invoices
            if datetime.strptime(invoice[DBInvoicesColumns.DATA_CREAZIONE.value], "%Y-%m-%d").year == current_year_value
        ]

        for invoice in invoices:
            reddito = reddito + invoice[DBInvoicesColumns.TOT_DOCUMENTO.value]

        return reddito

    def calcola_tot_fatturato_utente(self, user_id):
        """
        Calcola il fatturato di un utente come somma delle fatture
        emesse nell'anno corrente, sfruttando il join user‑invoices.

        :param user_id: ID dell'utente
        :return: il fatturato (float)
        """
        # Recupera l'utente + tutte le sue fatture
        rows = self.retrieve_user_with_invoices_map_list(user_id)
        if not rows:
            return 0.0

        # Estraggo il regime fiscale dall'utente (prendo il primo row)
        regime_utente = rows[0][DBUsersColumns.REGIME_FISCALE.value]

        # Calcolo l'anno corrente
        current_year = datetime.now().year

        fatturato = 0.0
        for row in rows:
            # Se la fattura non c'è (outer join), salto
            data_str = row.get(DBInvoicesColumns.DATA_CREAZIONE.value)
            if not data_str:
                continue

            # Controllo che la data di creazione sia nell'anno corrente
            try:
                anno = datetime.strptime(data_str, "%Y-%m-%d").year
            except ValueError:
                # formato data non valido: skip
                continue

            if anno == current_year:
                # Sommo il totale del documento
                tot = row.get(DBInvoicesColumns.TOT_DOCUMENTO.value) or 0.0
                fatturato += float(tot)

        return fatturato

    def calcola_tot_spese_utente_anticipate(self, user_id):
        """
        Calcola le spese anticipate di un utente come somma delle expenses
        emesse nell'anno corrente, sfruttando il join user‑expenses.

        :param user_id: ID dell'utente
        :return: il totale delle spese (float)
        """
        # Recupera l'utente + tutte le sue spese
        rows = self.retrieve_user_with_anticipated_expenses_map_list(user_id)
        if not rows:
            return 0.0

        # Estraggo il regime fiscale dall'utente (prendo il primo row)
        regime_utente = rows[0][DBUsersColumns.REGIME_FISCALE.value]

        # Calcolo l'anno corrente
        current_year = datetime.now().year

        tot_spese = 0.0
        for row in rows:
            # Se la fattura non c'è (outer join), salto
            data_str = row.get(DBExpensesColumns.created_at.value)
            if not data_str:
                continue

            # Controllo che la data di creazione sia nell'anno corrente
            try:
                anno = datetime.strptime(data_str, "%Y-%m-%d %H:%M:%S").year
            except ValueError:
                # formato data non valido: skip
                continue

            if anno == current_year:
                # Sommo il totale del documento
                tot = row.get(DBExpensesColumns.TOT_AMOUNT.value) or 0.0
                tot_spese += float(tot)

        return tot_spese

    def calcola_tot_spese_utente_dedotte(self, user_id):
        """
        Calcola le spese in deduzione di un utente come somma delle expenses
        emesse nell'anno corrente, sfruttando il join user‑expenses.

        :param user_id: ID dell'utente
        :return: il totale delle spese (float)
        """
        # Recupera l'utente + tutte le sue spese
        rows = self.retrieve_user_with_deducted_expenses_map_list(user_id)
        if not rows:
            return 0.0

        # Estraggo il regime fiscale dall'utente (prendo il primo row)
        regime_utente = rows[0][DBUsersColumns.REGIME_FISCALE.value]

        # Calcolo l'anno corrente
        current_year = datetime.now().year

        tot_spese = 0.0
        for row in rows:
            # Se la fattura non c'è (outer join), salto
            data_str = row.get(DBExpensesColumns.created_at.value)
            if not data_str:
                continue

            # Controllo che la data di creazione sia nell'anno corrente
            try:
                anno = datetime.strptime(data_str, "%Y-%m-%d %H:%M:%S").year
            except ValueError:
                # formato data non valido: skip
                continue

            if anno == current_year:
                # Sommo il totale del documento
                tot = row.get(DBExpensesColumns.TOT_AMOUNT.value) or 0.0
                tot_spese += float(tot)

        return tot_spese

    def calcola_tot_salari_utente(self, user_id):
        """
        Calcola gli ingressi di un utente come somma dei salari
        emesse nell'anno corrente, sfruttando il join user‑expenses.

        :param user_id: ID dell'utente
        :return: il totale delle spese (float)
        """
        # Recupera l'utente + tutte le sue spese
        rows = self.retrieve_user_with_salaries_map_list(user_id)
        if not rows:
            return 0.0

        # Estraggo il regime fiscale dall'utente (prendo il primo row)
        regime_utente = rows[0][DBUsersColumns.REGIME_FISCALE.value]

        # Calcolo l'anno corrente
        current_year = datetime.now().year

        tot_salary = 0.0
        for row in rows:
            # Se la fattura non c'è (outer join), salto
            data_str = row.get(DBSalariesColumns.CREATED_AT.value)
            if not data_str:
                continue

            # Controllo che la data di creazione sia nell'anno corrente
            try:
                anno = datetime.strptime(data_str, "%Y-%m-%d %H:%M:%S").year
            except ValueError as v:
                print(f"formato data non valido: skip {str(v)}")
                continue

            if anno == current_year:
                # Sommo il totale del documento
                tot = row.get(DBSalariesColumns.AMOUNT.value) or 0.0
                tot_salary += float(tot)

        return tot_salary

    def calcola_tot_ritenuta_acconto_ordinaria(self, user_id):
        invoices = self.retrieve_user_with_invoices_map_list(user_id)
        invoices = ControllerUtils.clear_invoices_list_from_NDC_and_stornate(invoices)

        tot = 0.0

        for i in invoices:
            if i[DBInvoicesColumns.ID_CLIENTE.value]:
                tot = tot + float(i[DBInvoicesColumns.RITENUTA.value])

        return tot


    def get_regime_fiscale_by_id(self, user_id):
        user_map = self.retrieve_user_map_by_id(user_id)
        regime_fiscale = user_map[DBUsersColumns.REGIME_FISCALE.value]
        return regime_fiscale

    def get_regime_fiscale_by_full_name(self, user_first_name, user_last_name):
        user_id = self.retrieve_user_by_fullname(user_first_name, user_last_name)[0]
        return self.get_regime_fiscale_by_id(user_id)

    def calcola_aliquota_tax_forfettaria(self, anno_apertura_piva):
        """
        Calcola l'aliquota fiscale in base al regime fiscale e all'anno di apertura della partita IVA.
        :param anno_apertura_piva: Anno di apertura della partita IVA.
        :return: Aliquota fiscale o None se il regime fiscale non è supportato.
        """
        try:
            current_year = datetime.now().year
            anni_di_attivita = current_year - int(anno_apertura_piva)
            return self.fiscal_settings.partita_iva_forfettaria.aliquota_irpef_min if anni_di_attivita < int(self.fiscal_settings.partita_iva_forfettaria.anni_agevolazione) else self.fiscal_settings.partita_iva_forfettaria.aliquota_irpef_max
        except (ValueError, AttributeError):
            pass
        return None

    def calcola_aliquota_tax_ordinaria(self, user_id):
        """
        Calcola l'aliquota IRPEF per un utente con partita IVA ordinaria.
        Il calcolo si basa sul reddito dell'utente (calcolato con calcola_reddito_utente)
        e sugli scaglioni IRPEF definiti nel file di configurazione.

        :param user_id: ID dell'utente (assunto appartenente a una partita IVA ordinaria)
        :return: Aliquota IRPEF oppure None se non è possibile calcolarla.
        """
        # Calcola il reddito dell'utente (eventualmente per l'anno corrente)
        reddito = self.calcola_reddito_tot_utente(user_id)

        # Recupera la lista degli scaglioni IRPEF dalla sezione 'partita_iva_ordinaria'
        scaglioni = self.fiscal_settings.partita_iva_ordinaria.scaglioni_irpef

        # Itera sugli scaglioni (si assume che la lista sia ordinata in base all'indice)
        for scaglione in scaglioni:
            # Verifica se il reddito rientra nell'intervallo dello scaglione:
            # Nota: si assume che il primo scaglione parta da 0 e l'ultimo abbia reddito_max == inf
            if reddito >= scaglione.reddito_min and reddito <= scaglione.reddito_max:
                # Restituisce l'aliquota
                return scaglione.value

        # Se nessuno scaglione "cattura" il reddito (ad esempio se il reddito è superiore a tutti i limiti)
        # restituisce l'aliquota dell'ultimo scaglione.
        if scaglioni:
            return scaglioni[-1].value

        # Se non sono definiti scaglioni, restituisce None.
        return None

    def update_tax_rates(self):
        """
        Aggiorna l'aliquota fiscale per tutte le partite IVA forfettarie nel database.
        Stampa per ogni utente il risultato:
          - se non cambia: “User id #X: nessun cambiamento (aliquota = Y)”
          - se cambia: “User id #X: aliquota aggiornata da Y a Z”
        Ritorna (True, msg) o (False, errore).
        """
        users = self.retrieve_users_map_list()
        total = len(users)
        updated_count = 0

        for user in users:
            try:
                user_id = user[DBUsersColumns.ID.value]
                regime = user[DBUsersColumns.REGIME_FISCALE.value]
                anno = user[DBUsersColumns.ANNO_APERTURA_PIVA.value]

                # 1) parse sicuro dell'aliquota corrente
                raw_current = user.get(DBUsersColumns.ALIQUOTA_TAX.value) or "0"
                current = float(raw_current)

                # 2) calcolo della nuova (solo per forfettario)
                new = current
                if regime == UserController.RegimeFiscale.FORFETTARIO.value:
                    new = self.calcola_aliquota_tax_forfettaria(anno)
                    # se calcola None, mantengo current
                    if new is None:
                        new = current

                # 3) confronto e update
                if str(new) != str(current):
                    self.db_model.update_user_tax_rate(user_id, new)
                    updated_count += 1
                    print(f"User id #{user_id}: aliquota aggiornata da {float(current):.2f} a {float(new):.2f}")
                else:
                    print(f"User id #{user_id}: nessun cambiamento (aliquota = {float(current):.2f})")


            except Exception as e:
                # qualsiasi altro errore
                print(f"User id #{user_id}: errore in aggiornamento: {e}")

        summary = f"Aggiornamento completato: {updated_count} su {total} utenti aggiornati."
        return True, summary

    def pick_fiscal_data_by_user_id(self, user_id: int) -> dict[str, dict[str, str]]:
        """
        Prepara i dati fiscali di un utente, suddivisi in due sezioni:
          - 'aliquote': { titolo: valore }
          - 'imponibili': { titolo: valore }

        Pronto per essere mostrato in View come label-readonly.
        """
        user = self.retrieve_user_map_by_id(user_id)
        regime = user.get(DBUsersColumns.REGIME_FISCALE.value)
        anno = user.get(DBUsersColumns.ANNO_APERTURA_PIVA.value)

        aliquote: dict[str, str] = {}
        imponibili: dict[str, str] = {}

        if regime == UserController.RegimeFiscale.FORFETTARIO.value:
            f = self.fiscal_settings.partita_iva_forfettaria
            # Aliquote
            aliquote["IRPEF forfettaria (%)"] = f"{self.calcola_aliquota_tax_forfettaria(anno)}"
            aliquote["INPS (%)"] = f"{f.aliquota_inps}"
            aliquote["Rivalsa INPS (%)"] = f"{f.aliquota_rivalsa_inps}"
            # Imponibili
            imponibili["Imponibile forfettario (%)"] = f"{f.imponibile}"

        else:
            # Regime ordinario
            o = self.fiscal_settings.partita_iva_ordinaria
            iva = self.fiscal_settings.aliquota_iva
            # Aliquote
            aliquote["INPS (%)"] = f"{o.aliquota_inps}"
            aliquote["Cassa INPS (%)"] = f"{o.aliquota_cassa_inps}"
            aliquote["Ritenuta (%)"] = f"{o.aliquota_ritenuta}"
            aliquote["IVA ordinaria (%)"] = f"{iva.aliquota_iva_ordinaria}"
            # Imponibili
            imponibili["Imponibile IVA (%)"] = f"{o.imponibile_iva}"
            imponibili["Imponibile ritenuta (%)"] = f"{o.imponibile_ritenuta_acconto}"
            imponibili["Imponibile cassa INPS (%)"] = f"{o.imponibile_cassa_inps}"
            imponibili["Imponibile INPS (%)"] = f"{o.imponibile_inps}"
            imponibili["Imponibile IRPEF (%)"] = f"{o.imponibile_irpef}"

        return {
            "aliquote": aliquote,
            "imponibili": imponibili
        }

    def encrypt_string(self, plain_text: str) -> str:
        """
        Cripta una stringa usando AES (CBC mode) con PyCryptodome.
        :param plain_text: La stringa da criptare.
        :return: La stringa criptata in formato esadecimale (IV + dati criptati).
        """
        try:
            # Genera un IV (Initialization Vector) casuale
            iv = get_random_bytes(16)

            # Crea il cifrario AES in modalità CBC
            cipher = AES.new(self.secret_key, AES.MODE_CBC, iv)

            # Aggiunge il padding e cifra il testo
            encrypted_data = cipher.encrypt(pad(plain_text.encode(), AES.block_size))

            # Combina IV e dati criptati e restituisce in formato esadecimale
            return f"{iv.hex()}{encrypted_data.hex()}"
        except Exception as e:
            # Logga l'errore o gestiscilo a livello applicativo
            print(f"Errore durante la crittografia: {e}")
            return None

    def decrypt_string(self, encrypted_text: str) -> str:
        """
        Decripta una stringa criptata usando AES (CBC mode) con PyCryptodome.
        :param encrypted_text: La stringa criptata in esadecimale (IV + dati criptati).
        :return: La stringa originale in chiaro.
        """
        try:
            # Decodifica i dati esadecimali
            encrypted_bytes = bytes.fromhex(encrypted_text)

            # Estrai IV e dati criptati
            iv = encrypted_bytes[:16]  # I primi 16 byte sono l'IV
            encrypted_data = encrypted_bytes[16:]  # Il resto è il dato criptato

            # Crea il cifrario AES in modalità CBC
            cipher = AES.new(self.secret_key, AES.MODE_CBC, iv)

            # Decifra e rimuove il padding
            plain_data = unpad(cipher.decrypt(encrypted_data), AES.block_size)

            return plain_data.decode("utf-8")
        except Exception as e:
            # Logga l'errore o gestiscilo a livello applicativo
            print(f"Errore durante la decrittografia: {e}")
            return None

    def print_utente(self, user):
        """
        Stampa a scopo di debug l'utente passato come argomento.
        :param user: Dizionario contenente i dati dell'utente.
        """
        if not user:
            return f"Utente non trovato."

        # Genera la stringa formattata usando l'enum DBUsersColumns
        printed_string = "\n".join(
            f"{column.value}: {user.get(column.value, 'N/A')}"
            for column in DBUsersColumns
        )

        print(printed_string)

    def print_utenti(self):
        users = self.retrieve_users_map_list()
        for user in users:
            self.print_utente(user)


class ClientController:

    class TipologiaCliente(Enum):
        PRIVATO = "PRIVATO"
        AZIENDA = "AZIENDA"
        ENTE_PUBBLICO = "ENTE_PUBBLICO"
        ALTRO = "ALTRO"

    class BusinessSector(Enum):
        AEROSPACE = "Aerospaziale e Difesa"
        AGRICULTURE = "Agricoltura e Allevamento"
        CREATIVE_AGENCY = "Agenzia Creativa"
        FOOD_AND_BEVERAGE = "Alimentare e Bevande"
        AUTOMOTIVE = "Automobilistico"
        CHEMICAL = "Chimico"
        RETAIL = "Commercio al Dettaglio"
        WHOLESALE = "Commercio all'Ingrosso"
        CONSULTING = "Consulenza e Servizi Professionali"
        CONSTRUCTION = "Costruzioni e Edilizia"
        ENERGY = "Energia e Risorse Naturali"
        PHARMACEUTICAL = "Farmaceutico"
        FINANCE = "Finanza e Assicurazioni"
        GOVERNMENT = "Governo e Settore Pubblico"
        REAL_ESTATE = "Immobiliare"
        EDUCATION = "Istruzione e Formazione"
        ENTERTAINMENT = "Intrattenimento e Media"
        MANUFACTURING = "Manifatturiero e Produzione"
        NON_PROFIT = "Organizzazioni Non Profit"
        RESEARCH_AND_DEVELOPMENT = "Ricerca e Sviluppo"
        HEALTHCARE = "Sanità e Servizi Medici"
        ENVIRONMENTAL_SERVICES = "Servizi Ambientali"
        SECURITY = "Sicurezza e Vigilanza"
        SPORTS = "Sport e Benessere"
        INFORMATION_TECHNOLOGY = "Tecnologia dell'Informazione (IT)"
        TELECOMMUNICATIONS = "Telecomunicazioni"
        TEXTILE = "Tessile e Abbigliamento"
        TOURISM = "Turismo e Ospitalità"
        TRANSPORTATION = "Trasporti e Logistica"

    class Aggregate_data(Enum):
        TOT_ENTRATE = "tot_entrate"
        NUM_FATTURE = "num_fatture"
        MEDIA_FATTURE = "media_fatture"
        TOT_CREDITI = "tot_crediti"
        PAGAM_ORARIO_MEDIO = "pagam_orario_medio"
        TOT_GIORNI_RIT = "tot_giorni_ritardo"
        MEDIA_RITARDO = "media_ritardo"


    def __init__(self, db_model: DatabaseModel):
        """Inizializza il controller con il modello del database"""
        self.db_model = db_model

        #self.clients_list = self.retrieve_clients_map_list()

    def save_client(self, client_data):
        """
        Gestisce il salvataggio di un cliente, con validazioni di primo livello.
        :param client_data: Dizionario contenente i dati del cliente
        :return: Tuple (success, message), dove success è True/False
        """
        # Campi obbligatori
        required_fields = {DBClientsColumns.NAME.value, DBClientsColumns.TIPOLOGIA.value}

        # Validazione dei campi obbligatori
        missing_fields = [field for field in required_fields if not client_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        # Validazione Partita IVA
        partita_iva = client_data.get(DBClientsColumns.PARTITA_IVA.value)
        if partita_iva and not ValidationUtils.validate_partita_iva(partita_iva):
            return False, "La partita IVA non è valida. Deve contenere esattamente 11 cifre."

        # Validazione Email
        email = client_data.get(DBClientsColumns.EMAIL.value)
        if email and not ValidationUtils.validate_email(email):
            return False, "L'indirizzo email non è valido."

        # Validazione contatto referente (se presente)
        contatto_referente = client_data.get(DBClientsColumns.CONTATTO_REFERENTE.value)
        if contatto_referente and not ValidationUtils.validate_phone_number(contatto_referente):
            return False, "Il contatto del referente non è valido. Deve essere un numero di telefono valido."

        # Preparazione dei dati per il salvataggio
        client_data_filtered = {
            column.value: client_data.get(column.value)
            for column in DBClientsColumns
            if column.value in client_data
        }

        # Rimuove i campi None
        client_data_filtered = {key: value for key, value in client_data_filtered.items() if value is not None}

        # Salvataggio nel DB
        try:
            self.db_model.add_client(**client_data_filtered)
            #self.update_clients_list()
            return True, "Cliente salvato con successo!"
        except Exception as e:
            return False, f"Errore durante il salvataggio del cliente: {str(e)}"

    def delete_client(self, client_id):
        return self.db_model.remove_client(client_id)

    def update_client(self, client_id, client_data):
        """
        Aggiorna i dati di un cliente esistente.
        :param client_id: ID del cliente da aggiornare
        :param client_data: Dizionario contenente i dati da aggiornare
        :return: Tuple (success, message), dove success è True/False
        """
        try:
            # Controllo validità
            if not client_id or not isinstance(client_id, int):
                return False, "ID cliente non valido. Deve essere un intero positivo."

            required_fields = {DBClientsColumns.NAME.value}

            # Validazione campi obbligatori
            missing_fields = [field for field in required_fields if not client_data.get(field)]
            if missing_fields:
                return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

            # Invoca il metodo del model per aggiornare l'utente
            self.db_model.update_client(client_id, **client_data)
            return True, "Cliente aggiornato con successo!"

        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento del cliente: {str(e)}"

    def retrieve_clients(self):
        """Recupera tutti i clienti."""
        return self.db_model.fetch_clients()

    def retrieve_client_by_id(self, client_id):
        """Recupera un cliente specifico per ID."""
        return self.db_model.fetch_client_by_id(client_id)

    def retrieve_client_by_name(self, client_name):
        """Recupera un cliente specifico per nome."""
        return self.db_model.fetch_client_by_name(client_name)

    def retrieve_client_map_by_name(self, client_name):
        """Recupera un cliente specifico e lo restituisce come dizionario."""
        row = self.retrieve_client_by_name(client_name)
        return ValidationUtils._row_to_map(row, DBClientsColumns)

    def retrieve_client_map_by_id(self, client_id):
        """Recupera un cliente specifico e lo restituisce come dizionario."""
        row = self.db_model.fetch_client_by_id(client_id)
        return ValidationUtils._row_to_map(row, DBClientsColumns)

    def retrieve_clients_map_list(self):
        """Recupera tutti i clienti e li restituisce come lista di dizionari."""
        rows = self.db_model.fetch_clients()
        return [ValidationUtils._row_to_map(row, DBClientsColumns) for row in rows]

    def retrieve_client_with_invoices_map_list(self, client_id):
        """
        Recupera lo specifico client unito alle rispettive fatture e
        li restituisce come lista di dizionari.

        Utilizza la funzione fetch_client_with_invoices per ottenere le righe,
        quindi combina le colonne dei client e delle invoices per convertire
        ogni riga in un dizionario tramite _row_to_map.
        """
        # Recupera le righe dal database per lo specifico client
        rows = self.db_model.fetch_client_with_invoices(client_id)

        # Combina le colonne dei client e delle invoices in un'unica lista.
        # Assumiamo che la query abbia selezionato prima le colonne dei client,
        # poi quelle delle invoices.
        all_columns = list(DBClientsColumns) + list(DBInvoicesColumns)

        # Converte ogni riga in un dizionario
        return [ValidationUtils._row_to_map(row, all_columns) for row in rows]

    def construct_client_map_aggregate_data(self, client_id):

        client_aggregate_data = {
            ClientController.Aggregate_data.TOT_ENTRATE.value: self.calcola_tot_entrate_cliente(client_id),
            ClientController.Aggregate_data.NUM_FATTURE.value: self.calcola_numero_fatture_cliente(client_id),
            ClientController.Aggregate_data.MEDIA_FATTURE.value: self.calcola_media_fatture_cliente(client_id),
            ClientController.Aggregate_data.TOT_CREDITI.value: self.calcola_totale_crediti_cliente(client_id),
            ClientController.Aggregate_data.PAGAM_ORARIO_MEDIO.value: self.calcola_pagam_orario_medio_cliente(client_id),
            ClientController.Aggregate_data.TOT_GIORNI_RIT.value: self.calcola_totale_ritardi_cliente(client_id),
            ClientController.Aggregate_data.MEDIA_RITARDO.value: self.calcola_ritardo_medio_cliente(client_id)
        }

        return client_aggregate_data

    def print_cliente(self, client):
        """
        Stampa a scopo di debug il cliente passato come argomento.
        :param client: Dizionario contenente i dati del cliente.
        """
        if not client:
            return "Cliente non trovato."

        # Genera la stringa formattata usando l'enum DBClientsColumns
        printed_string = "\n".join(
            f"{column.value}: {client.get(column.value, 'N/A')}"
            for column in DBClientsColumns
        )

        print(printed_string)

    def print_clienti(self):
        """
        Recupera e stampa tutti i clienti.
        """
        clients = self.retrieve_clients_map_list()
        for client in clients:
            self.print_cliente(client)

    def calcola_tot_entrate_cliente(self, client_id):
        client_with_invoices = self.retrieve_client_with_invoices_map_list(client_id)
        tot = 0.0
        for row in client_with_invoices: #in questo modo sto in realtà scorrendo le fatture
            if (row[DBInvoicesColumns.TIPO.value] != InvoiceController.Tipologia.NOTA_DI_CREDITO.value or
                    row[DBInvoicesColumns.STATUS.value] != InvoiceController.InvoiceSatus.STORNATA.value):
                tot = tot + float(row[DBInvoicesColumns.TOT_DOCUMENTO.value]) if row[DBInvoicesColumns.TOT_DOCUMENTO.value] != None else tot

        return tot

    def calcola_numero_fatture_cliente(self, client_id):
        client_with_invoices = self.retrieve_client_with_invoices_map_list(client_id)
        tot = 0
        for row in client_with_invoices:
            valid_row = row[DBInvoicesColumns.ID_CLIENTE.value] is not None
            if (row[DBInvoicesColumns.TIPO.value] != InvoiceController.Tipologia.NOTA_DI_CREDITO.value and valid_row or
                    row[DBInvoicesColumns.STATUS.value] != InvoiceController.InvoiceSatus.STORNATA.value and valid_row):
                tot = tot + 1

        return tot

    def calcola_media_fatture_cliente(self, client_id):
        numero = self.calcola_numero_fatture_cliente(client_id)
        tot = self.calcola_tot_entrate_cliente(client_id)

        return tot/numero if numero > 0 else 0

    def calcola_totale_crediti_cliente(self, client_id):
        outstanding = self.db_model.fetch_outstanding_by_client(client_id)
        return sum(outstanding.values())

    def calcola_pagam_orario_medio_cliente(self, client_id):
        invoices_with_prod = self.db_model.fetch_invoices_with_productions()
        all_columns = list(DBInvoicesColumns) + list(DBProductionsColumns)

        invoices_with_prod_maps = [ValidationUtils._row_to_map(row, all_columns) for row in invoices_with_prod]
        invoices_with_prod_maps = InvoiceController.clear_invoices_list_from_NDC_and_stornate(invoices_with_prod_maps)

        tot_pagam = 0.0
        tot_orario = 0.0
        #ciclo sulle produzioni
        for invoice in invoices_with_prod_maps:
            if invoice[DBInvoicesColumns.ID_CLIENTE.value] == client_id:
                tot_pagam = tot_pagam + float(invoice[DBInvoicesColumns.TOT_DOCUMENTO.value]) #legito se esiste una sola produzione per fattura, altrimenti sommo più volte la stessa fattura
                tot_orario = tot_orario + float(invoice[DBProductionsColumns.HOURS.value])

        result = tot_pagam / tot_orario if tot_orario > 0 else -1
        return result

    def calcola_ritardo_medio_cliente(self, client_id):
        """
        Calcola il ritardo medio in giorni per un cliente, considerando:
        - Pagamenti effettuati dopo la scadenza
        - Rate non pagate con scadenza passata

        Ritorna:
        - Ritardo medio in giorni (float)
        - 0 se non ci sono rate in ritardo
        """
        # 1. Recupera tutte le fatture del cliente
        invoice_rows = self.db_model.fetch_invoices_by_client_id(client_id)
        invoices_maps = [ValidationUtils._row_to_map(row, DBInvoicesColumns) for row in invoice_rows]
        invoices_maps = InvoiceController.clear_invoices_list_from_NDC_and_stornate(invoices_maps)

        # 2. Recupera tutti i pagamenti associati alle fatture del cliente
        payment_rows = self.db_model.fetch_payments_with_invoice_for_client(client_id)

        # 3. Organizza i pagamenti per fattura e rata
        payments_dict = {}
        for row in payment_rows:
            # Estrae i dati del pagamento (prima parte della tupla)
            payment_data = row[:len(DBPaymentsColumns)]
            payment_map = ValidationUtils._row_to_map(payment_data, DBPaymentsColumns)

            # Estrae i dati della fattura (seconda parte della tupla)
            invoice_data = row[len(DBPaymentsColumns):len(DBPaymentsColumns) + len(DBInvoicesColumns)]
            invoice_map = ValidationUtils._row_to_map(invoice_data, DBInvoicesColumns)

            invoice_id = invoice_map[DBInvoicesColumns.ID.value]
            rata = payment_map[DBPaymentsColumns.LINKED_RATA.value]

            if invoice_id not in payments_dict:
                payments_dict[invoice_id] = {}

            payments_dict[invoice_id][rata] = payment_map

        totale_ritardo = 0
        conteggio_rate_in_ritardo = 0
        date_format = "%Y-%m-%d"
        oggi = datetime.today()

        for invoice in invoices_maps:
            try:
                num_rate = int(invoice[DBInvoicesColumns.NUMERO_RATE.value])
            except (ValueError, TypeError):
                num_rate = 1  # Default a 1 rata se il valore non è valido

            for rata in range(1, num_rate + 1):
                # Recupera la data di scadenza della rata
                if rata == 1:
                    due_date_str = invoice[DBInvoicesColumns.DATA_SCADENZA_1.value]
                elif rata == 2:
                    due_date_str = invoice[DBInvoicesColumns.DATA_SCADENZA_2.value]
                elif rata == 3:
                    due_date_str = invoice[DBInvoicesColumns.DATA_SCADENZA_3.value]
                else:
                    continue  # Supporta solo fino a 3 rate

                if not due_date_str:
                    continue  # Salta se la data di scadenza non è presente

                try:
                    due_date = datetime.strptime(due_date_str, date_format)
                except ValueError:
                    continue  # Salta se il formato della data non è valido

                # Cerca un pagamento per questa rata
                invoice_id = invoice[DBInvoicesColumns.ID.value]
                payment = payments_dict.get(invoice_id, {}).get(rata)

                ritardo_calcolato = 0
                in_ritardo = False

                if payment:
                    # Calcola ritardo per pagamento effettuato
                    payment_date_str = payment[DBPaymentsColumns.PAYMENT_DATE.value]
                    try:
                        payment_date = datetime.strptime(payment_date_str, date_format)
                        if payment_date > due_date:
                            ritardo_calcolato = (payment_date - due_date).days
                            in_ritardo = True
                    except ValueError:
                        continue
                else:
                    # Calcola ritardo per rata non pagata (solo se scaduta)
                    if oggi > due_date:
                        ritardo_calcolato = (oggi - due_date).days
                        in_ritardo = True

                if in_ritardo:
                    totale_ritardo += ritardo_calcolato
                    conteggio_rate_in_ritardo += 1

        # Calcola la media
        if conteggio_rate_in_ritardo > 0:
            return totale_ritardo / conteggio_rate_in_ritardo
        else:
            return 0  # Nessuna rata in ritardo

    def calcola_totale_ritardi_cliente(self, client_id):
        """
        Calcola il ritardo totale in giorni per un cliente, considerando:
        - Pagamenti effettuati dopo la scadenza
        - Rate non pagate con scadenza passata
        """
        # 1. Recupera tutte le fatture del cliente
        invoice_rows = self.db_model.fetch_invoices_by_client_id(client_id)
        invoices_maps = [ValidationUtils._row_to_map(row, DBInvoicesColumns) for row in invoice_rows]
        invoices_maps = InvoiceController.clear_invoices_list_from_NDC_and_stornate(invoices_maps)

        # 2. Recupera tutti i pagamenti associati alle fatture del cliente
        payment_rows = self.db_model.fetch_payments_with_invoice_for_client(client_id)

        # 3. Organizza i pagamenti per fattura e rata
        payments_dict = {}
        for row in payment_rows:
            # Estrae i dati del pagamento (prima parte della tupla)
            payment_data = row[:len(DBPaymentsColumns)]
            payment_map = ValidationUtils._row_to_map(payment_data, DBPaymentsColumns)

            # Estrae i dati della fattura (seconda parte della tupla)
            invoice_data = row[len(DBPaymentsColumns):len(DBPaymentsColumns) + len(DBInvoicesColumns)]
            invoice_map = ValidationUtils._row_to_map(invoice_data, DBInvoicesColumns)

            invoice_id = invoice_map[DBInvoicesColumns.ID.value]
            rata = payment_map[DBPaymentsColumns.LINKED_RATA.value]

            if invoice_id not in payments_dict:
                payments_dict[invoice_id] = {}

            payments_dict[invoice_id][rata] = payment_map

        giorni_ritardo_totale = 0
        date_format = "%Y-%m-%d"
        oggi = datetime.today()

        for invoice in invoices_maps:
            try:
                num_rate = int(invoice[DBInvoicesColumns.NUMERO_RATE.value])
            except (ValueError, TypeError):
                num_rate = 1  # Default a 1 rata se il valore non è valido

            for rata in range(1, num_rate + 1):
                # Recupera la data di scadenza della rata
                if rata == 1:
                    due_date_str = invoice[DBInvoicesColumns.DATA_SCADENZA_1.value]
                elif rata == 2:
                    due_date_str = invoice[DBInvoicesColumns.DATA_SCADENZA_2.value]
                elif rata == 3:
                    due_date_str = invoice[DBInvoicesColumns.DATA_SCADENZA_3.value]
                else:
                    continue  # Supporta solo fino a 3 rate

                if not due_date_str:
                    continue  # Salta se la data di scadenza non è presente

                try:
                    due_date = datetime.strptime(due_date_str, date_format)
                except ValueError:
                    continue  # Salta se il formato della data non è valido

                # Cerca un pagamento per questa rata
                invoice_id = invoice[DBInvoicesColumns.ID.value]
                payment = payments_dict.get(invoice_id, {}).get(rata)

                if payment:
                    # Calcola ritardo per pagamento effettuato
                    payment_date_str = payment[DBPaymentsColumns.PAYMENT_DATE.value]
                    try:
                        payment_date = datetime.strptime(payment_date_str, date_format)
                        if payment_date > due_date:
                            ritardo = (payment_date - due_date).days
                            giorni_ritardo_totale += ritardo
                    except ValueError:
                        continue
                else:
                    # Calcola ritardo per rata non pagata (solo se scaduta)
                    if oggi > due_date:
                        ritardo = (oggi - due_date).days
                        giorni_ritardo_totale += ritardo

        return giorni_ritardo_totale

    def calcola_tot_rimborsi_by_client(self, client_id):
        refunds = [ValidationUtils._row_to_map(row, DBRefundsColumns) for row in self.db_model.fetch_refunds_by_client_id(client_id)]
        tot = 0.0
        for r in refunds:
            tot += float(r[DBRefundsColumns.REFUND_AMOUNT.value])

        return tot


class InvoiceController:

    class InvoiceSatus(Enum): #stati per le fatture con una rata
        DA_EMETTERE = "DA EMETTERE" #questo valore non prenderlo in considerazione per ora
        EMESSA = "EMESSA"
        SALDATA = "SALDATA"
        SCADUTA = "SCADUTA"
        STORNATA = "STORNATA" #questo valore non prenderlo in considerazione per ora

    class InvoiceRateizzSatus(Enum): #stati per le fatture con tre rate (le rate possibili sono solo 1 o 3)
        DA_EMETTERE = "DA EMETTERE" #questo valore non prenderlo in considerazione per ora
        EMESSA = "EMESSA" #nessuna rata scaduta e nessuna rata pagata
        PARZIALMENTE_SALDATA = "PARZIALMENTE SALDATA" #una o più rate pagate e nessuna rata scaduta
        CRITICA = "CRITICA" #una o più rate scadute
        SCADUTA = "SCADUTA" #tutte le rate sono scadute e nessuna è stata saldata
        PAGATA = "PAGATA" #tutte le rate pagate
        STORNATA = "STORNATA" #questo valore non prenderlo in considerazione per ora

    class PaymentsMethods(Enum):
        BONIFICO = "BONIFICO"
        CONTANTI = "CONTANTI"
        ASSEGNO = "ASSEGNO"

    class Rateizzazione(Enum):
        UNA = "1"
        TRE = "3"

    class Tipologia(Enum):
        FATTURA = "FATTURA"
        NOTA_DI_CREDITO = "NOTA DI CREDITO"

    class InvoiceAggregatedData(Enum):
        NUMERO_FATTURE = "NUMERO_FATTURE"
        FATT_LORDO = "FATT_LORDO"
        FATT_NETTO = "FATT_NETTO"
        IVA_DEBITO = "IVA_DEBITO"
        CREDITI_LORDO = "CREDITI_LORDO"
        CREDITI_NETTO = "CREDITI_NETTO"
        MEDIA_FATTURA_LORDO = "MEDIA_FATTURA_LORDO"
        MEDIA_FATTURA_NETTO = "MEDIA_FATTURA_NETTO"
        MEDIA_PAGAM_ORARIO_LORDO = "MEDIA_PAGAM_ORARIO_LORDO"
        MEDIA_PAGAM_ORARIO_NETTO = "MDIA_PAGAM_ORARIO_NETTO"

    def __init__(self, db_model: DatabaseModel, user_controller, client_controller, production_controller, payment_controller, account_controller, fiscal_settings, historical_financial_data_settings):
        """Inizializza il controller con il modello del database"""
        self.db_model = db_model
        self.fiscal_settings = fiscal_settings
        self.user_controller = user_controller
        self.client_controller = client_controller
        self.production_controller = production_controller
        self.payment_controller = payment_controller
        self.account_controller = account_controller
        self.historical_financial_data_settings = historical_financial_data_settings


        #self.invoices_list = {}
        #self.current_year_invoices_list = {}

        #updates alle liste locali
        #self.update_invoices_list()

        print("Aggiornamento dello stato delle fatture in funzione della data di oggi...")
        self.update_stato_fatture()
        print("\n")

        #i dati aggregati sono variabili di classe, aggiornati ogni volta che viene fatto un save di una nuova fattura
        self.invoices_aggregated_data = {}
        self.current_year_invoices_aggregated_data = {}

        self.update_aggregated_data() #aggiorna entrambi i dati aggregati, sia per current year, sia in generale

        self.on_updating_invoice_controller_callbacks = []

    def save_invoice(self, invoice_data):
        """
        Gestisce il salvataggio di una fattura, con validazioni di primo livello.
        :param invoice_data: Dizionario contenente i dati della fattura
        :return: Tuple (success, message), dove success è True/False
        """

        # Campi obbligatori (solo quelli modellati tramite entry)
        required_fields = {DBInvoicesColumns.NUMERO_FATTURA.value, DBInvoicesColumns.SERVIZI.value, DBInvoicesColumns.RIMBORSI.value}

        # Validazione dei campi obbligatori
        missing_fields = [field for field in required_fields if not invoice_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        # Validazione importi
        servizi = invoice_data.get(DBInvoicesColumns.SERVIZI.value)
        if not ValidationUtils.validate_amount(servizi):
            return False, "L'importo dei servizi non è valido"

        tot_non_ivato = invoice_data.get(DBInvoicesColumns.RIMBORSI.value)
        if not ValidationUtils.validate_amount(tot_non_ivato):
            return False, "L'importo di tot_non_ivato non è valido"

        #prendo i dati della produzione associata
        production_name = invoice_data.get("NOME PRODUZIONE") #definito nella view (è un po' una porcata)
        if production_name:
            production = self.production_controller.retrieve_production_map_by_name(production_name)
            if production:
                production_id = production[DBProductionsColumns.ID.value]
            else:
                return False, "Aggiungere una produzione prima di emettere questa fattura"

        #prendo i dati necessari dell'utente
        nome_utente = invoice_data.get("NOME UTENTE").split(" ")
        utente = self.user_controller.retrieve_user_map_by_fullname(nome_utente[0], nome_utente[1])
        id_utente = utente[DBUsersColumns.ID.value]
        regime_fiscale = utente[DBUsersColumns.REGIME_FISCALE.value]


        #prendo i dati necessari del cliente
        nome_cliente = invoice_data.get("NOME CLIENTE")
        cliente_list = self.client_controller.retrieve_client_by_name(nome_cliente)
        cliente_map = self.client_controller.retrieve_client_map_by_id(cliente_list[0])
        id_cliente = cliente_map[DBClientsColumns.ID.value]
        tipologia_cliente = cliente_map[DBClientsColumns.TIPOLOGIA.value]

        #prendo i dati necessari al conto
        nome_conto = invoice_data.get("CONTO")
        conto = self.account_controller.retrieve_account_map_by_name(nome_conto)
        if conto:
            conto_id = conto[DBAccountsColumns.ID.value]

        totale_servizi = invoice_data.get(DBInvoicesColumns.SERVIZI.value)
        totale_rimborsi = invoice_data.get(DBInvoicesColumns.RIMBORSI.value)

        #se la fattura è una nota di credito prendo l'ID della fattura a cui è collegata
        id_linked_invoice = None
        if invoice_data.get(DBInvoicesColumns.TIPO.value) == InvoiceController.Tipologia.NOTA_DI_CREDITO.value and invoice_data.get(DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value):
            id_linked_invoice = invoice_data.get(DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value)


        invoice_data_prepared = {}


        # Preparazione dei dati per il salvataggio
        if regime_fiscale == UserController.RegimeFiscale.ORDINARIO.value:

            #prendo le aliquote e gli imponibili per il calcolo degli importi derivati della fattura
            aliquota_cassa_inps = self.fiscal_settings.partita_iva_ordinaria.aliquota_cassa_inps
            aliquota_ritenuta_acconto = self.fiscal_settings.partita_iva_ordinaria.aliquota_ritenuta
            aliquota_iva = self.fiscal_settings.aliquota_iva.aliquota_iva_ordinaria
            imponibile_tax = self.fiscal_settings.partita_iva_ordinaria.imponibile_irpef
            imponibile_cassa_inps = self.fiscal_settings.partita_iva_ordinaria.imponibile_cassa_inps
            imponibile_iva = self.fiscal_settings.partita_iva_ordinaria.imponibile_iva

            #calcolo importi derivati
            importi_derivati_ordinaria = self.calcola_derivati_fattura_ordinaria(
                float(aliquota_cassa_inps),
                float(aliquota_ritenuta_acconto),
                float(aliquota_iva),
                float(imponibile_tax),
                float(imponibile_cassa_inps),
                float(imponibile_iva),
                tipologia_cliente,
                float(totale_servizi),
                float(totale_rimborsi)
            )

            #riempio i dati da passare al model
            invoice_data_prepared = {
                DBInvoicesColumns.NUMERO_FATTURA.value : invoice_data.get(DBInvoicesColumns.NUMERO_FATTURA.value),  # view
                DBInvoicesColumns.DATA_CREAZIONE.value : invoice_data.get(DBInvoicesColumns.DATA_CREAZIONE.value),  # view
                DBInvoicesColumns.DATA_SCADENZA_1.value : self.calculate_three_expiration_dates(invoice_data.get(DBInvoicesColumns.DATA_CREAZIONE.value))[0],
                DBInvoicesColumns.DATA_SCADENZA_2.value : self.calculate_three_expiration_dates(invoice_data.get(DBInvoicesColumns.DATA_CREAZIONE.value))[1] if invoice_data.get(DBInvoicesColumns.NUMERO_RATE.value) == InvoiceController.Rateizzazione.TRE.value else None,
                DBInvoicesColumns.DATA_SCADENZA_3.value : self.calculate_three_expiration_dates(invoice_data.get(DBInvoicesColumns.DATA_CREAZIONE.value))[2] if invoice_data.get(DBInvoicesColumns.NUMERO_RATE.value) == InvoiceController.Rateizzazione.TRE.value else None,
                DBInvoicesColumns.ID_UTENTE.value : id_utente,  # controller(view)
                DBInvoicesColumns.ID_CLIENTE.value : id_cliente,  # controller(view)
                DBInvoicesColumns.ID_CONTO.value : conto_id,
                DBInvoicesColumns.NOTE.value : invoice_data.get(DBInvoicesColumns.NOTE.value),  # view
                DBInvoicesColumns.SERVIZI.value : totale_servizi,  # view (comprensivo di rivalsa)
                DBInvoicesColumns.CASSA_INPS.value : importi_derivati_ordinaria[DBInvoicesColumns.CASSA_INPS.value],  # controller -> servizi*coeff redditività*aliquota INPS
                DBInvoicesColumns.IMPONIBILE.value : importi_derivati_ordinaria[DBInvoicesColumns.IMPONIBILE.value],  # controller -> servizi*coeff redditività
                DBInvoicesColumns.IVA.value : importi_derivati_ordinaria[DBInvoicesColumns.IVA.value],  # controller = 0
                DBInvoicesColumns.RIMBORSI.value : totale_rimborsi,  # view
                DBInvoicesColumns.TOT_DOCUMENTO.value : importi_derivati_ordinaria[DBInvoicesColumns.TOT_DOCUMENTO.value],
                DBInvoicesColumns.RITENUTA.value : importi_derivati_ordinaria[DBInvoicesColumns.RITENUTA.value],  # controller = 0
                DBInvoicesColumns.RIVALSA_INPS.value: 0,
                DBInvoicesColumns.NETTO_A_PAGARE.value : importi_derivati_ordinaria[DBInvoicesColumns.NETTO_A_PAGARE.value],  # controller = 0
                DBInvoicesColumns.STATUS.value : InvoiceController.InvoiceRateizzSatus.EMESSA.value if invoice_data.get(DBInvoicesColumns.NUMERO_RATE.value) == InvoiceController.Rateizzazione.TRE.value else InvoiceController.InvoiceSatus.EMESSA.value, # controller -> default: emessa
                DBInvoicesColumns.METODO_PAGAMENTO.value : invoice_data.get(DBInvoicesColumns.METODO_PAGAMENTO.value),  # view
                DBInvoicesColumns.NUMERO_RATE.value : invoice_data.get(DBInvoicesColumns.NUMERO_RATE.value),  # view
                DBInvoicesColumns.TIPO.value : invoice_data.get(DBInvoicesColumns.TIPO.value),  # se è nota di credito #view
                DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value : invoice_data.get(DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value) if invoice_data.get(DBInvoicesColumns.TIPO.value) == InvoiceController.Tipologia.NOTA_DI_CREDITO.value else None,  # view (a comparsa)
                DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value : production_id
            }
        elif regime_fiscale == UserController.RegimeFiscale.FORFETTARIO.value:
            tot_lordo = float(totale_servizi) + float(invoice_data.get(DBInvoicesColumns.RIMBORSI.value)) + float(invoice_data.get(DBInvoicesColumns.RIVALSA_INPS.value))
            invoice_data_prepared = {
                DBInvoicesColumns.NUMERO_FATTURA.value: invoice_data.get(DBInvoicesColumns.NUMERO_FATTURA.value),  # view
                DBInvoicesColumns.DATA_CREAZIONE.value: invoice_data.get(DBInvoicesColumns.DATA_CREAZIONE.value),  # view
                DBInvoicesColumns.DATA_SCADENZA_1.value: self.calculate_three_expiration_dates(invoice_data.get(DBInvoicesColumns.DATA_CREAZIONE.value))[0],
                DBInvoicesColumns.DATA_SCADENZA_2.value: self.calculate_three_expiration_dates(invoice_data.get(DBInvoicesColumns.DATA_CREAZIONE.value))[1] if invoice_data.get(DBInvoicesColumns.NUMERO_RATE.value) == InvoiceController.Rateizzazione.TRE.value else None,
                DBInvoicesColumns.DATA_SCADENZA_3.value: self.calculate_three_expiration_dates(invoice_data.get(DBInvoicesColumns.DATA_CREAZIONE.value))[2] if invoice_data.get(DBInvoicesColumns.NUMERO_RATE.value) == InvoiceController.Rateizzazione.TRE.value else None,
                DBInvoicesColumns.ID_UTENTE.value: id_utente,  # controller(view)
                DBInvoicesColumns.ID_CLIENTE.value: id_cliente,  # controller(view)
                DBInvoicesColumns.ID_CONTO.value: conto_id,
                DBInvoicesColumns.NOTE.value: invoice_data.get(DBInvoicesColumns.NOTE.value),  # view
                DBInvoicesColumns.SERVIZI.value: totale_servizi,  # view (comprensivo di rivalsa)
                DBInvoicesColumns.CASSA_INPS.value: 0,
                DBInvoicesColumns.IMPONIBILE.value: totale_servizi,
                DBInvoicesColumns.IVA.value: 0,  # controller = 0
                DBInvoicesColumns.RIMBORSI.value: totale_rimborsi,  # view
                DBInvoicesColumns.RIVALSA_INPS.value : invoice_data.get(DBInvoicesColumns.RIVALSA_INPS.value),
                DBInvoicesColumns.TOT_DOCUMENTO.value: tot_lordo,
                DBInvoicesColumns.RITENUTA.value: 0,
                DBInvoicesColumns.NETTO_A_PAGARE.value: tot_lordo,
                DBInvoicesColumns.STATUS.value: InvoiceController.InvoiceRateizzSatus.EMESSA.value if invoice_data.get(DBInvoicesColumns.NUMERO_RATE.value) == InvoiceController.Rateizzazione.TRE.value else InvoiceController.InvoiceSatus.EMESSA.value,
                DBInvoicesColumns.METODO_PAGAMENTO.value: invoice_data.get(DBInvoicesColumns.METODO_PAGAMENTO.value),
                DBInvoicesColumns.NUMERO_RATE.value: invoice_data.get(DBInvoicesColumns.NUMERO_RATE.value),  # view
                DBInvoicesColumns.TIPO.value: invoice_data.get(DBInvoicesColumns.TIPO.value),  # se è nota di credito #view
                DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value: invoice_data.get(DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value) if invoice_data.get(DBInvoicesColumns.TIPO.value) == InvoiceController.Tipologia.NOTA_DI_CREDITO.value else None,  # view (a comparsa)
                DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value: production_id

            }

        # Salvataggio nel DB
        try:
            self.db_model.add_invoice(**invoice_data_prepared)
            self.update_stato_fatture() #aggiorno lo stato in funzione della data di oggi e dei pagamenti associati alla fattura
            if id_linked_invoice:
                self.db_model.modify_invoice_datum(id_linked_invoice, DBInvoicesColumns.STATUS.value, InvoiceController.InvoiceSatus.STORNATA.value)
            #self.update_invoices_list()
            self.update_aggregated_data()
            return True, "Fattura salvata con successo!"
        except Exception as e:
            return False, f"Errore durante il salvataggio: {str(e)}"

    def update_invoice(self, invoice_id, invoice_data):

        invoice = self.retrieve_invoice_map_by_id(invoice_id)

        # Campi obbligatori (solo quelli modellati tramite entry)
        required_fields = {DBInvoicesColumns.SERVIZI.value, DBInvoicesColumns.RIMBORSI.value}

        # Validazione dei campi obbligatori
        missing_fields = [field for field in required_fields if not invoice_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        # Validazione importi
        servizi = invoice_data.get(DBInvoicesColumns.SERVIZI.value)
        if not ValidationUtils.validate_amount(servizi):
            return False, "L'importo dei servizi non è valido"

        tot_non_ivato = invoice_data.get(DBInvoicesColumns.RIMBORSI.value)
        if not ValidationUtils.validate_amount(tot_non_ivato):
            return False, "L'importo dei rimborsi non è valido"

        invoice_data_prepared = {}
        for col in DBInvoicesColumns:
            try:
                invoice_data_prepared[col.value] = float(invoice_data.get(col.value))
            except Exception as e:
                invoice_data_prepared[col.value] = invoice_data.get(col.value)


        #sistemazione dei dati prima di pushare verso db
        for key, data in invoice_data.items():
            if data is None:
                invoice_data_prepared.pop(key)
        invoice_data_prepared.pop(DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value) #da valutare se reintrodurla
        invoice_data_prepared.pop(DBInvoicesColumns.ID.value)
        invoice_data_prepared.pop(DBInvoicesColumns.CREATED_AT.value)
        invoice_data_prepared.pop(DBInvoicesColumns.TIPO.value)
        invoice_data_prepared.pop(DBInvoicesColumns.STATUS.value)
        invoice_data_prepared.pop(DBInvoicesColumns.ID_UTENTE.value)
        invoice_data_prepared.pop(DBInvoicesColumns.NUMERO_FATTURA.value)

        invoice_data_prepared[DBInvoicesColumns.CREATED_AT.value] = invoice[DBInvoicesColumns.CREATED_AT.value]

        invoice_data_prepared[DBInvoicesColumns.UPDATED_AT.value] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            # Invoca il metodo del model per aggiornare l'utente
            self.db_model.update_invoice(invoice_id, **invoice_data_prepared)
            return True, "Fattura aggiornata con successo!"

        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento della fattura: {str(e)}"

    def storna_invoice(self, invoice_id, invoice_data):
        # Campi obbligatori (solo quelli modellati tramite entry)
        required_fields = {DBInvoicesColumns.STATUS.value}

        # Validazione dei campi obbligatori
        missing_fields = [field for field in required_fields if not invoice_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        invoice_data_prepared = invoice_data
        invoice_data_prepared[DBInvoicesColumns.UPDATED_AT.value] = datetime.now().replace(microsecond=0)

        try:
            # Invoca il metodo del model per aggiornare l'utente
            self.db_model.update_invoice(invoice_id, **invoice_data_prepared)
            return True, "Fattura aggiornata con successo!"

        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento della fattura: {str(e)}"

    def retrieve_invoices(self, current_year=True):
        """
        Recupera tutte le fatture, filtrandole per l'anno corrente o mantenendo quelle con rate non pagate.
        :param current_year: Booleano. Se True, ritorna solo le fatture emesse nell'anno corrente o con rate non pagate.
        :return: Lista di tuple (righe) con i dati delle fatture.
        """
        rows = self.db_model.fetch_invoices()
        if current_year:
            rows = ControllerUtils.filter_invoices(rows, self.db_model, current_year)
        return rows

    def retrieve_invoice_by_id(self, invoice_id, current_year=True):
        """
        Recupera una fattura specifica per ID, opzionalmente filtrando per l'anno corrente.
        :param invoice_id: ID della fattura.
        :param current_year: Se True, ritorna None se la fattura non è dell'anno corrente o non ha rate non pagate.
        :return: Una tupla con i dati della fattura oppure None.
        """
        row = self.db_model.fetch_invoice_by_id(invoice_id)
        if row and current_year:
            # Passa la singola riga come lista di un elemento
            filtered = ControllerUtils.filter_invoices([row], self.db_model, current_year)
            return filtered[0] if filtered else None
        return row

    def retrieve_invoice_map_by_id(self, invoice_id, current_year=True):
        """
        Recupera una fattura specifica e la restituisce come dizionario, filtrando per l'anno corrente se specificato.
        :param invoice_id: ID della fattura.
        :param current_year: Se True, ritorna None se la fattura non è dell'anno corrente o non ha rate non pagate.
        :return: Dizionario con i dati della fattura oppure None.
        """
        row = self.db_model.fetch_invoice_by_id(invoice_id)
        if not row:
            return None

        if current_year:
            # Filtra la singola fattura
            filtered_row = ControllerUtils.filter_invoices(row, self.db_model, current_year)
            # Se il filtro restituisce None, la fattura non passa i criteri
            if not filtered_row:
                return None
            row = filtered_row

        return ValidationUtils._row_to_map(row, DBInvoicesColumns)

    def retrieve_invoice_map_by_name(self, invoice_name, current_year=True):
        """
        Recupera una fattura in base al nome e la restituisce come dizionario,
        filtrando per l'anno corrente se specificato.

        :param invoice_name: Nome della fattura.
        :param current_year: Se True, ritorna un dizionario vuoto se la fattura non è dell'anno corrente o non ha rate non pagate.
        :return: Dizionario con i dati della fattura oppure un dizionario vuoto.
        """
        row = self.db_model.fetch_invoice_by_name(invoice_name)
        if not row:
            return {}

        if current_year:
            # Filtra la singola fattura
            filtered_row = ControllerUtils.filter_invoices(row, self.db_model, current_year)
            # Se il filtro restituisce None, la fattura non passa i criteri
            if not filtered_row:
                return {}
            row = filtered_row

        return ValidationUtils._row_to_map(row, DBInvoicesColumns)

    def retrieve_invoices_map_list_by_user(self, user_id, current_year=True):
        """
        Recupera tutte le fatture di un certo utente e le restituisce come lista di dizionari,
        filtrandole per l'anno corrente o mantenendo quelle con rate non pagate.

        :param user_id: ID dell'utente.
        :param current_year: Se True, ritorna solo le fatture dell'anno corrente o con rate non pagate.
        :return: Lista di dizionari contenenti i dati delle fatture.
        """
        rows = self.db_model.fetch_invoices_by_user_id(user_id)

        if current_year and rows:
            rows = ControllerUtils.filter_invoices(rows, self.db_model, current_year)

        return [ValidationUtils._row_to_map(row, DBInvoicesColumns) for row in rows]

    def retrieve_invoice_map_list_by_production(self, prod_id, current_year=True):
        """
        Recupera tutte le fatture di una produzione e le restituisce come lista di dizionari,
        filtrandole per l'anno corrente o mantenendo quelle con rate non pagate.

        :param prod_id: ID della produzione.
        :param current_year: Se True, ritorna solo le fatture dell'anno corrente o con rate non pagate.
        :return: Lista di dizionari contenenti i dati delle fatture.
        """
        rows = self.db_model.fetch_invoices_by_prod_id(prod_id)

        if current_year and rows:
            rows = ControllerUtils.filter_invoices(rows, self.db_model, current_year)

        return [ValidationUtils._row_to_map(row, DBInvoicesColumns) for row in rows]

    def retrieve_invoice_map_list_by_client(self, client_id, current_year=True):
        """
        Recupera tutte le fatture di un cliente e le restituisce come lista di dizionari,
        filtrandole per l'anno corrente o mantenendo quelle con rate non pagate.

        :param client_id: ID del cliente.
        :param current_year: Se True, ritorna solo le fatture dell'anno corrente o con rate non pagate.
        :return: Lista di dizionari contenenti i dati delle fatture.
        """
        rows = self.db_model.fetch_invoices_by_client_id(client_id)

        if current_year and rows:
            rows = ControllerUtils.filter_invoices(rows, self.db_model, current_year)

        return [ValidationUtils._row_to_map(row, DBInvoicesColumns) for row in rows]

    def retrieve_invoices_map_list(self, current_year=True):
        """
        Recupera tutte le fatture e le restituisce come lista di dizionari,
        filtrandole per l'anno corrente o mantenendo quelle con rate non pagate.
        """
        rows = self.db_model.fetch_invoices()

        if current_year and rows:
            rows = ControllerUtils.filter_invoices(rows, self.db_model, current_year)

        return [ValidationUtils._row_to_map(row, DBInvoicesColumns) for row in rows]

    def retrieve_last_invoice_insert_map(self):
        row = self.db_model.fetch_last_invoice_insert()
        return ValidationUtils._row_to_map(row, DBInvoicesColumns)

    def retrieve_invoice_with_payments_map_list(self, invoice_id):
        """
        Recupera la specifica fattura unita ai rispettivi pagamenti e
        li restituisce come lista di dizionari.

        """
        # Recupera le righe dal database per lo specifico client
        rows = self.db_model.fetch_invoice_with_payments(invoice_id)

        all_columns = list(DBInvoicesColumns) + list(DBPaymentsColumns)

        # Converte ogni riga in un dizionario
        return [ValidationUtils._row_to_map(row, all_columns) for row in rows]

    def retrieve_invoice_with_expenses_map_list(self, invoice_id):
        """
        Recupera la specifica fattura unita alle rispettive spese di produzione e
        li restituisce come lista di dizionari.

        """
        # Recupera le righe dal database per lo specifico client
        rows = self.db_model.fetch_invoice_with_expenses(invoice_id)

        all_columns = list(DBInvoicesColumns) + list(DBExpensesColumns)

        # Converte ogni riga in un dizionario
        return [ValidationUtils._row_to_map(row, all_columns) for row in rows]

    def check_linked_tot_expenses(self, invoice_id):
        """
        Controlla il totale delle spese associate a una fattura e verifica
        se copre l’importo dei rimborsi con una tolleranza di 5.
        Ritorna una tupla (check, linked_expenses_tot) dove:
          - check: True se esistono spese e linked_expenses_tot >= rimborsi
                   oppure |linked_expenses_tot - rimborsi| < 5; altrimenti False
          - linked_expenses_tot: somma degli importi delle spese associate
        """
        # Recupera tutte le spese collegate alla fattura
        expenses = self.retrieve_invoice_with_expenses_map_list(invoice_id)
        # Somma tutti gli importi
        total = 0.0
        for exp in expenses:
            try:
                total += float(exp[DBExpensesColumns.TOT_AMOUNT.value])
            except (KeyError, ValueError, TypeError):
                continue

        # Se non ci sono spese, esci subito
        if not expenses:
            return False, total

        # Ottieni l’importo dei rimborsi (prendo il primo record)
        try:
            rimborsi = float(expenses[0][DBInvoicesColumns.RIMBORSI.value])
        except (KeyError, ValueError, TypeError):
            rimborsi = 0.0

        # Verifica copertura con tolleranza ±5
        check = (total >= rimborsi) or (abs(total - rimborsi) < 5)
        return check, total

    def count_invoices(self, current_year=True):
        """
        Conta il numero di fatture che non siano state stornate, applicando il filtro per l'anno corrente se specificato.

        :param current_year: Booleano. Se True, conta solo le fatture dell'anno corrente o con rate non pagate.
        :return: Numero di fatture (int)
        """
        # Recupera le fatture già filtrate
        invoices = self.retrieve_invoices_map_list(current_year)
        # Filtra ulteriormente per rimuovere NDC e stornate
        filtered_invoices = self.clear_invoices_list_from_NDC_and_stornate(invoices)
        return len(filtered_invoices)

    def calculate_TOT_DOCUMENTO_invoiced(self, current_year=True):
        """
        Calcola il totale fatturato, escludendo NDC e fatture stornate.

        :param current_year: Se True, considera solo fatture dell'anno corrente o con rate non pagate.
        :return: Totale fatturato (float)
        """
        # Recupera le fatture già filtrate
        invoices = self.retrieve_invoices_map_list(current_year)
        # Filtra ulteriormente per rimuovere NDC e stornate
        filtered_invoices = self.clear_invoices_list_from_NDC_and_stornate(invoices)

        tot = 0.0
        for invoice in filtered_invoices:
            amount = invoice.get(DBInvoicesColumns.TOT_DOCUMENTO.value)
            if amount:
                tot += float(amount)
        return tot

    def calculate_IVA_invoiced(self, current_year=True):
        """
        Calcola il totale IVA fatturata, escludendo NDC e fatture stornate.

        :param current_year: Se True, considera solo fatture dell'anno corrente o con rate non pagate.
        :return: Totale IVA (float)
        """
        # Recupera le fatture già filtrate
        invoices = self.retrieve_invoices_map_list(current_year)
        # Filtra ulteriormente per rimuovere NDC e stornate
        filtered_invoices = self.clear_invoices_list_from_NDC_and_stornate(invoices)

        iva_total = 0.0
        for invoice in filtered_invoices:
            iva = invoice.get(DBInvoicesColumns.IVA.value)
            if iva:
                iva_total += float(iva)
        return iva_total

    def calculate_RITENUTA_ACCONTO_invoiced(self, current_year=True):
        """
        Calcola il totale della ritenuta d'acconto fatturata.
        """
        # Recupera le fatture già filtrate
        invoices = self.retrieve_invoices_map_list(current_year)
        # Filtra ulteriormente per rimuovere NDC e stornate
        filtered_invoices = self.clear_invoices_list_from_NDC_and_stornate(invoices)

        ritenuta = 0.0
        for invoice in filtered_invoices:
            amount = invoice.get(DBInvoicesColumns.RITENUTA.value)
            if amount:
                ritenuta += float(amount)
        return ritenuta

    def calculate_FATT_LORDO_invoiced(self, current_year=True):
        """
        Calcola il fatturato lordo (totale documento - IVA).
        """
        tot_documento = self.calculate_TOT_DOCUMENTO_invoiced(current_year)
        iva = self.calculate_IVA_invoiced(current_year)
        return tot_documento - iva

    def calculate_FATT_NETTO_invoiced(self, current_year=True):
        """
        Calcola il fatturato netto (totale documento - IVA - ritenuta).
        """
        tot_documento = self.calculate_TOT_DOCUMENTO_invoiced(current_year)
        iva = self.calculate_IVA_invoiced(current_year)
        ritenuta = self.calculate_RITENUTA_ACCONTO_invoiced(current_year)
        return tot_documento - iva - ritenuta

    def calculate_CRED_LORDO_invoiced(self, current_year=True):
        """
        Calcola i crediti lordi basandosi sulle fatture non pagate.
        """
        # Utilizza la funzione comune di processing
        return self._process_crediti(current_year, netto=False)

    def calculate_CRED_NETTO_invoiced(self, current_year=True):
        """
        Calcola i crediti netti basandosi sulle fatture non pagate.
        """
        # Utilizza la funzione comune di processing
        return self._process_crediti(current_year, netto=True)

    def calculate_MEDIA_FATTURA_LORDO_invoiced(self, current_year=True):
        """
        Calcola la media del fatturato lordo per fattura.
        """
        fatt_lordo = self.calculate_FATT_LORDO_invoiced(current_year)
        numero_fatt = self.count_invoices(current_year)
        return fatt_lordo / numero_fatt if numero_fatt > 0 else -1

    def calculate_MEDIA_FATTURA_NETTO_invoiced(self, current_year=True):
        """
        Calcola la media del fatturato netto per fattura.
        """
        fatt_netto = self.calculate_FATT_NETTO_invoiced(current_year)
        numero_fatt = self.count_invoices(current_year)
        return fatt_netto / numero_fatt if numero_fatt > 0 else -1

    # Funzione helper comune per il calcolo dei crediti
    def _process_crediti(self, current_year, netto=True):
        """
        Funzione comune per il calcolo dei crediti lordi o netti.
        """
        # Recupera le fatture con i pagamenti associati
        rows = self.db_model.fetch_invoices_with_payments()
        num_invoice_cols = len(DBInvoicesColumns)

        # Crea un set di ID fatture da includere (usando la nuova logica di filtraggio)
        included_ids = {inv[DBInvoicesColumns.ID.value] for inv in self.retrieve_invoices_map_list(current_year)}

        # Raggruppa per invoice_id
        grouped = {}
        for row in rows:
            invoice_id = row[0]
            if invoice_id not in included_ids:  # Filtra per le fatture da includere
                continue

            if invoice_id not in grouped:
                grouped[invoice_id] = {
                    "invoice_raw": row[0:num_invoice_cols],
                    "payments": []
                }
            payment_raw = row[num_invoice_cols:]
            if payment_raw and payment_raw[0] is not None:
                grouped[invoice_id]["payments"].append(payment_raw)

        # Converti in mappe e filtra
        all_invoice_maps = {}
        for inv_id, data in grouped.items():
            inv_map = ValidationUtils._row_to_map(data["invoice_raw"], DBInvoicesColumns)
            inv_map["payments"] = data["payments"]
            all_invoice_maps[inv_id] = inv_map

        filtered_invoices = self.clear_invoices_list_from_NDC_and_stornate(list(all_invoice_maps.values()))
        payment_cols = [col.value for col in DBPaymentsColumns]
        totale_credito = 0.0

        for invoice in filtered_invoices:
            try:
                num_rate = int(invoice[DBInvoicesColumns.NUMERO_RATE.value])
                tot_documento = float(invoice[DBInvoicesColumns.TOT_DOCUMENTO.value])
                iva = float(invoice[DBInvoicesColumns.IVA.value])
                ritenuta = float(invoice.get(DBInvoicesColumns.RITENUTA.value, 0))
            except (ValueError, TypeError):
                continue

            # Converti i pagamenti
            payments_maps = []
            for p in invoice.get("payments", []):
                if p and p[0] is not None:
                    payments_maps.append(dict(zip(payment_cols, p)))

            # Calcola il credito in base al tipo di fattura
            if num_rate == int(InvoiceController.Rateizzazione.UNA.value):
                paid = any(int(pm.get(DBPaymentsColumns.LINKED_RATA.value, 0)) == 1 for pm in payments_maps)
                if not paid:
                    credito = tot_documento - iva - (ritenuta if netto else 0)
                    totale_credito += credito

            elif num_rate == int(InvoiceController.Rateizzazione.TRE.value):
                credito_per_rata = (tot_documento - iva - (ritenuta if netto else 0)) / 3.0
                for rata in [1, 2, 3]:
                    paid = any(int(pm.get(DBPaymentsColumns.LINKED_RATA.value, 0)) == rata for pm in payments_maps)
                    if not paid:
                        totale_credito += credito_per_rata

        return totale_credito

    # ancora da implementare perché manca la parte di produzioni
    def calculate_MEDIA_PAGAM_ORARIO_LORDO_invoiced(self, current_year=True):
        return 0

    def calculate_MEDIA_PAGAM_ORARIO_NETTO_invoiced(self, current_year=True):
        return 0

    def update_aggregated_data(self):
        self.current_year_invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.NUMERO_FATTURE.value] = self.count_invoices(True)
        self.current_year_invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.FATT_LORDO.value] = round(self.calculate_FATT_LORDO_invoiced(True),2)
        self.current_year_invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.IVA_DEBITO.value] = round(self.calculate_IVA_invoiced(True),2)
        self.current_year_invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.FATT_NETTO.value] = round(self.calculate_FATT_NETTO_invoiced(True),2)
        self.current_year_invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.CREDITI_LORDO.value] = round(self.calculate_CRED_LORDO_invoiced(True),2)
        self.current_year_invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.CREDITI_NETTO.value] = round(self.calculate_CRED_NETTO_invoiced(True),2)
        self.current_year_invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.MEDIA_FATTURA_LORDO.value] = round(self.calculate_MEDIA_FATTURA_LORDO_invoiced(True),2)
        self.current_year_invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.MEDIA_FATTURA_NETTO.value] = round(self.calculate_MEDIA_FATTURA_NETTO_invoiced(True),2)
        self.current_year_invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.MEDIA_PAGAM_ORARIO_LORDO.value] = round(self.calculate_MEDIA_PAGAM_ORARIO_LORDO_invoiced(True),2)
        self.current_year_invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.MEDIA_PAGAM_ORARIO_NETTO.value] = round(self.calculate_MEDIA_PAGAM_ORARIO_NETTO_invoiced(True),2)

        self.invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.NUMERO_FATTURE.value] = self.count_invoices(False)
        self.invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.FATT_LORDO.value] = round(self.calculate_FATT_LORDO_invoiced(False),2)
        self.invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.IVA_DEBITO.value] = round(self.calculate_IVA_invoiced(False),2)
        self.invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.FATT_NETTO.value] = round(self.calculate_FATT_NETTO_invoiced(False),2)
        self.invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.CREDITI_LORDO.value] = round(self.calculate_CRED_LORDO_invoiced(False),2)
        self.invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.CREDITI_NETTO.value] = round(self.calculate_CRED_NETTO_invoiced(False),2)
        self.invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.MEDIA_FATTURA_LORDO.value] = round(self.calculate_MEDIA_FATTURA_LORDO_invoiced(False),2)
        self.invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.MEDIA_FATTURA_NETTO.value] = round(self.calculate_MEDIA_FATTURA_NETTO_invoiced(False),2)
        self.invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.MEDIA_PAGAM_ORARIO_LORDO.value] = round(self.calculate_MEDIA_PAGAM_ORARIO_LORDO_invoiced(False),2)
        self.invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.MEDIA_PAGAM_ORARIO_NETTO.value] = round(self.calculate_MEDIA_PAGAM_ORARIO_NETTO_invoiced(False),2)

    def calcola_derivati_fattura_ordinaria(self,
                                            aliquota_cassa_inps,
                                            aliquota_ritenuta_acconto,
                                            aliquota_iva,
                                            imponibile_tax,
                                            imponibile_cassa_inps,
                                            imponibile_iva,
                                            tipologia_cliente,
                                            tot_servizi,
                                            tot_rimborsi):

        imponibile = tot_servizi * imponibile_tax
        cassa_inps = tot_servizi * imponibile_cassa_inps * aliquota_cassa_inps
        iva = imponibile * aliquota_iva * imponibile_iva
        tot_documento = imponibile + cassa_inps + iva + tot_rimborsi
        ritenuta = 0 if tipologia_cliente == ClientController.TipologiaCliente.PRIVATO.value else imponibile * aliquota_ritenuta_acconto
        netto_a_pagare = tot_documento - ritenuta

        invoice_data = {
            DBInvoicesColumns.CASSA_INPS.value: cassa_inps,
            DBInvoicesColumns.IMPONIBILE.value: imponibile,
            DBInvoicesColumns.IVA.value: iva,
            DBInvoicesColumns.TOT_DOCUMENTO.value: tot_documento,
            DBInvoicesColumns.RITENUTA.value: ritenuta,
            DBInvoicesColumns.NETTO_A_PAGARE.value: netto_a_pagare
        }
        return invoice_data

    def calcola_derivati_fattura(self, regime_fiscale, tipologia_cliente, tot_servizi, tot_rimborsi, ext_rivalsa_inps):
        """
        Calcola i campi derivati della fattura sulla base del regime fiscale dell'utente e della tipologia di cliente.
        Usa i dati fiscali da self.fiscal_settings.
        """

        if regime_fiscale == self.user_controller.RegimeFiscale.ORDINARIO.value:
            settings = self.fiscal_settings.partita_iva_ordinaria

            imponibile = tot_servizi * float(settings.imponibile_irpef)
            cassa_inps = tot_servizi * float(settings.imponibile_cassa_inps) * float(settings.aliquota_cassa_inps)
            iva = imponibile * float(self.fiscal_settings.aliquota_iva.aliquota_iva_ordinaria) * float(settings.imponibile_iva)
            tot_documento = imponibile + cassa_inps + iva + tot_rimborsi

            ritenuta = 0
            if tipologia_cliente != ClientController.TipologiaCliente.PRIVATO.value:
                ritenuta = imponibile * float(settings.aliquota_ritenuta)

            netto_a_pagare = tot_documento - ritenuta
            rivalsa_inps = 0  # Non prevista nel regime ordinario

        elif regime_fiscale == self.user_controller.RegimeFiscale.FORFETTARIO.value:
            settings = self.fiscal_settings.partita_iva_forfettaria

            imponibile = tot_servizi
            cassa_inps = 0
            iva = 0
            ritenuta = 0
            rivalsa_inps = tot_servizi * float(settings.aliquota_rivalsa_inps) if ext_rivalsa_inps != 0 else ext_rivalsa_inps
            tot_documento = imponibile + rivalsa_inps + tot_rimborsi
            netto_a_pagare = tot_documento

        else:
            raise ValueError(f"Regime fiscale non supportato: {regime_fiscale}")

        return {
            DBInvoicesColumns.CASSA_INPS.value: cassa_inps,
            DBInvoicesColumns.IMPONIBILE.value: imponibile,
            DBInvoicesColumns.IVA.value: iva,
            DBInvoicesColumns.TOT_DOCUMENTO.value: tot_documento,
            DBInvoicesColumns.RITENUTA.value: ritenuta,
            DBInvoicesColumns.NETTO_A_PAGARE.value: netto_a_pagare,
            DBInvoicesColumns.RIVALSA_INPS.value: rivalsa_inps
        }

    def calcola_totale_pagamenti_fattura(self, id_invoice):
        payments = self.retrieve_invoice_with_payments_map_list(id_invoice)
        tot = 0.0
        tot_1 = 0.0
        tot_2 = 0.0
        tot_3 = 0.0

        for payment in payments:
            if payment[DBPaymentsColumns.PAYMENT_NAME.value] is not None:
                tot = tot + float(payment[DBPaymentsColumns.PAYMENT_AMOUNT.value])
                if payment[DBPaymentsColumns.LINKED_RATA.value] == 1:
                    tot_1 = tot_1 + float(payment[DBPaymentsColumns.PAYMENT_AMOUNT.value])
                elif payment[DBPaymentsColumns.LINKED_RATA.value] == 2:
                    tot_2 = tot_2 + float(payment[DBPaymentsColumns.PAYMENT_AMOUNT.value])
                elif payment[DBPaymentsColumns.LINKED_RATA.value] == 3:
                    tot_3 = tot_3 + float(payment[DBPaymentsColumns.PAYMENT_AMOUNT.value])

        return [tot, tot_1, tot_2, tot_3]

    def calcola_totale_spese_produzione_fattura(self, id_invoice):
        expenses = self.retrieve_invoice_with_expenses_map_list(id_invoice)
        tot = 0.0

        for expense in expenses:
            if expense[DBExpensesColumns.NAME.value] is not None:
                tot = tot + float(expense[DBExpensesColumns.TOT_AMOUNT.value])

        return tot

    def print_invoice(self, invoice):
        """
        Stampa a scopo di debug il cliente passato come argomento.
        :param invoice: Dizionario contenente i dati della fattura.
        """
        if not invoice:
            return "Fattura non trovata."

        # Genera la stringa formattata usando l'enum DBinvoiceColumns
        printed_string = "\n".join(
            f"{column.value}: {invoice.get(column.value, 'N/A')}"
            for column in DBInvoicesColumns
        )

        print(printed_string)

    def print_invoices(self):
        """
        Recupera e stampa tutti i clienti.
        """
        invoices = self.retrieve_invoices_map_list(True)
        for invoice in invoices:
            self.print_invoice(invoice)

    def update_stato_fatture(self, current_year=True):
        """
        Aggiorna lo stato di tutte le fatture nel database in base ai dati correnti,
        utilizzando il nuovo enum InvoiceRateizzSatus e sfruttando i dati dei pagamenti
        ottenuti dal join tra invoices e payments.

        Per fatture con 1 rata:
          - Se esiste un pagamento associato (con LINKED_RATA == 1) → PAGATA
          - Se non esiste pagamento e la scadenza (DATA_SCADENZA_1) è passata → SCADUTA
          - Altrimenti → EMESSA

        Per fatture con 3 rate:
          - Se tutte le 3 rate sono pagate → PAGATA
          - Se nessuna rata è pagata:
                * Se tutte le scadenze sono passate → SCADUTA
                * Se almeno una rata non pagata è scaduta (ma non tutte) → CRITICA
                * Altrimenti → EMESSA
          - Se alcune rate sono pagate (1 o 2):
                * Se almeno una rata ancora non pagata è scaduta → CRITICA
                * Altrimenti → PARZIALMENTE_SALDATA

        Viene stampato a console il feedback per ogni fattura e un riepilogo finale.
        """
        # Recupera i dati dal join tra invoices e payments
        rows = self.db_model.fetch_invoices_with_payments()
        oggi = datetime.today().date()
        num_invoice_cols = len(DBInvoicesColumns)

        # Estrai solo la parte fatture (senza pagamenti) per il filtraggio
        invoice_tuples = [row[0:num_invoice_cols] for row in rows]

        # Applica il filtro utilizzando ControllerUtils
        filtered_invoice_tuples = ControllerUtils.filter_invoices(
            invoice_tuples,
            self.db_model,
            current_year=current_year
        )

        # Crea un set con gli ID delle fatture filtrate
        filtered_ids = {t[0] for t in filtered_invoice_tuples}  # ID è il primo elemento

        # Filtra le righe originali mantenendo solo quelle delle fatture filtrate
        filtered_rows = [row for row in rows if row[0] in filtered_ids]

        # Raggruppa i record per invoice_id
        grouped = {}
        for row in filtered_rows:
            invoice_id = row[0]
            if invoice_id not in grouped:
                grouped[invoice_id] = {
                    "invoice_raw": row[0:num_invoice_cols],
                    "payments": []
                }
            payment_raw = row[num_invoice_cols:]
            if payment_raw and payment_raw[0] is not None:
                grouped[invoice_id]["payments"].append(payment_raw)

        # Converte ogni gruppo in una mappa
        all_invoice_maps = {}
        for inv_id, data in grouped.items():
            inv_map = ValidationUtils._row_to_map(data["invoice_raw"], DBInvoicesColumns)
            inv_map["payments"] = data["payments"]
            all_invoice_maps[inv_id] = inv_map

        # Filtra ulteriormente rimuovendo note di credito e fatture stornate
        filtered_invoices = InvoiceController.clear_invoices_list_from_NDC_and_stornate(
            list(all_invoice_maps.values())
        )

        updates = 0
        total = len(filtered_invoices)
        payment_cols = [col.value for col in DBPaymentsColumns]

        for invoice in filtered_invoices:
            invoice_id = invoice[DBInvoicesColumns.ID.value]
            stato_attuale = invoice[DBInvoicesColumns.STATUS.value]
            num_rate = int(invoice[DBInvoicesColumns.NUMERO_RATE.value])
            nuovo_stato = stato_attuale  # default

            # Salta note di credito (già gestito in clear_invoices_list... ma doppio check)
            if stato_attuale == InvoiceController.InvoiceSatus.STORNATA.value:
                print(f"Fattura {invoice_id} non aggiornata poichè è nota di credito")
                continue

            # Converti i pagamenti in mappe
            payments = invoice.get("payments", [])
            payments_maps = []
            for p in payments:
                if p and p[0] is not None:
                    payments_maps.append(dict(zip(payment_cols, p)))

            # Logica di aggiornamento stato (invariata)
            if num_rate == int(InvoiceController.Rateizzazione.UNA.value):
                paid = any(int(pm[DBPaymentsColumns.LINKED_RATA.value]) == 1 for pm in payments_maps)
                scadenza = ControllerUtils.parse_date(invoice[DBInvoicesColumns.DATA_SCADENZA_1.value])
                if paid:
                    nuovo_stato = InvoiceController.InvoiceRateizzSatus.PAGATA.value
                else:
                    if scadenza is not None and oggi > scadenza:
                        nuovo_stato = InvoiceController.InvoiceRateizzSatus.SCADUTA.value
                    else:
                        nuovo_stato = InvoiceController.InvoiceRateizzSatus.EMESSA.value

            elif num_rate == int(InvoiceController.Rateizzazione.TRE.value):
                pagamenti = []
                for rata in [1, 2, 3]:
                    payment = next((pm for pm in payments_maps if int(pm[DBPaymentsColumns.LINKED_RATA.value]) == rata),
                                   None)
                    pagamenti.append(
                        ControllerUtils.parse_date(payment[DBPaymentsColumns.PAYMENT_DATE.value]) if payment else None)

                scadenze = [
                    ControllerUtils.parse_date(invoice[DBInvoicesColumns.DATA_SCADENZA_1.value]),
                    ControllerUtils.parse_date(invoice[DBInvoicesColumns.DATA_SCADENZA_2.value]),
                    ControllerUtils.parse_date(invoice[DBInvoicesColumns.DATA_SCADENZA_3.value])
                ]

                count_paid = sum(1 for p in pagamenti if p is not None)
                count_overdue = sum(
                    1 for i in range(3) if pagamenti[i] is None and scadenze[i] is not None and oggi > scadenze[i]
                )

                if count_paid == 3:
                    nuovo_stato = InvoiceController.InvoiceRateizzSatus.PAGATA.value
                elif count_paid == 0:
                    if all(s is not None and oggi > s for s in scadenze):
                        nuovo_stato = InvoiceController.InvoiceRateizzSatus.SCADUTA.value
                    elif count_overdue > 0 and count_overdue < 3:
                        nuovo_stato = InvoiceController.InvoiceRateizzSatus.CRITICA.value
                    else:
                        nuovo_stato = InvoiceController.InvoiceRateizzSatus.EMESSA.value
                else:
                    if count_overdue > 0:
                        nuovo_stato = InvoiceController.InvoiceRateizzSatus.CRITICA.value
                    else:
                        nuovo_stato = InvoiceController.InvoiceRateizzSatus.PARZIALMENTE_SALDATA.value
            else:
                print(
                    f"Invoice id {invoice_id}: numero rate non riconosciuto (valore: {num_rate}). Nessuna azione effettuata.")
                continue

            # Aggiornamento se lo stato è cambiato
            if nuovo_stato != stato_attuale:
                self.db_model.modify_invoice_datum(invoice_id, DBInvoicesColumns.STATUS.value, nuovo_stato)
                print(f"Invoice id {invoice_id}: stato aggiornato da '{stato_attuale}' a '{nuovo_stato}'.")
                updates += 1
            else:
                print(f"Invoice id {invoice_id}: nessun cambiamento (stato corrente: '{stato_attuale}').")

        print(f"Aggiornamento completato: {updates} su {total} fatture aggiornate.")

    def register_on_updating_invoice_controller_callbacks(self, *callbacks):
        self.on_updating_invoice_controller_callbacks = list(callbacks)

    def select_best_invoicer(self, nuovo_importo: float) -> dict[str, float]:
        """
        Suggerisce quale partita IVA debba emettere una nuova fattura,
        con un bilanciamento migliore tra situazione corrente e obiettivi annuali,
        specialmente per la partita IVA ordinaria.
        """
        # 1. Recupero dati base
        user_list = self.user_controller.retrieve_users_map_list()
        id_to_last_name = {user[DBUsersColumns.ID.value]: user[DBUsersColumns.LAST_NAME.value] for user in user_list}
        name_to_id = {v: k for k, v in id_to_last_name.items()}

        # 2. Fatturati e spese correnti
        fatturati = self.user_controller.retrieve_users_with_tot_fatturato()
        spese = self.user_controller.retrieve_users_with_tot_spese()

        ordinari = fatturati.get(self.user_controller.RegimeFiscale.ORDINARIO.value, {})
        if len(ordinari) != 1:
            raise ValueError("Richiesta esattamente 1 partita IVA ordinaria")

        nome_ordinaria = next(iter(ordinari))
        id_ordinaria = name_to_id[nome_ordinaria]

        # 3. Strutture dati
        piva_forfettarie = {
            name_to_id[nome]: {
                "fatturato": tot,
                "spese_deducibili": spese.get(nome, 0.0)
            }
            for nome, tot in fatturati.get(self.user_controller.RegimeFiscale.FORFETTARIO.value, {}).items()
        }

        piva_ordinaria = {
            id_ordinaria: {
                "fatturato": ordinari[nome_ordinaria],
                "spese_deducibili": spese.get(nome_ordinaria, 0.0)
            }
        }

        # 4. Storico fatture e spese
        fatture = self.retrieve_invoices_map_list(current_year=False)
        storico_fatture = [{
            "piva": f.get(DBInvoicesColumns.ID_UTENTE.value),
            "data": f.get(DBInvoicesColumns.DATA_CREAZIONE.value),
            "amount": f.get(DBInvoicesColumns.TOT_DOCUMENTO.value)
        } for f in fatture]

        spese_ordinaria_raw = self.user_controller.retrieve_user_with_deducted_expenses_map_list(id_ordinaria)
        storico_spese_ordinaria = [{
            "data": s.get(DBExpensesColumns.DATE.value),
            "amount": s.get(DBExpensesColumns.TOT_AMOUNT.value)
        } for s in spese_ordinaria_raw]

        # 5. Dati storici annuali
        storico_annuale_fatturato = self.historical_financial_data_settings.revenues
        storico_annuale_spese_ordinaria = self.historical_financial_data_settings.deducted_expenses

        oggi = datetime.today()
        anno_corrente = oggi.year
        mese_corrente = oggi.month

        # 6. Calcolo valori correnti (situazione attuale)
        fatturati_correnti = {}
        for piva, data in {**piva_forfettarie, **piva_ordinaria}.items():
            storico_piva = [f for f in storico_fatture if f["piva"] == piva]
            df = pd.DataFrame(storico_piva)
            if not df.empty:
                df["data"] = pd.to_datetime(df["data"])
                df["anno"] = df["data"].dt.year
                fatturati_correnti[piva] = df[df["anno"] == anno_corrente]["amount"].sum()
            else:
                fatturati_correnti[piva] = 0

        # Spese YTD corrente per ordinaria
        df_spese = pd.DataFrame(storico_spese_ordinaria)
        if not df_spese.empty:
            df_spese["data"] = pd.to_datetime(df_spese["data"])
            df_spese["anno"] = df_spese["data"].dt.year
            spese_correnti_ordinaria = df_spese[df_spese["anno"] == anno_corrente]["amount"].sum()
        else:
            spese_correnti_ordinaria = 0

        # 7. Previsioni semplificate (solo per bilanciamento)
        previsioni = {}
        for piva, data in {**piva_forfettarie, **piva_ordinaria}.items():
            nome = self.user_controller.id_to_full_name_str(piva)

            # Recupera dati storici se disponibili
            storico_annuale = 0
            count = 0
            for anno, valori in storico_annuale_fatturato.items():
                if int(anno) < anno_corrente and nome in valori:
                    storico_annuale += valori[nome]
                    count += 1

            media_storica = storico_annuale / count if count > 0 else 0
            fatturato_attuale = fatturati_correnti[piva]

            # Peso dinamico: più peso al corrente man mano che avanziamo nell'anno
            peso_corrente = min(0.9, max(0.5, mese_corrente / 12))
            peso_storico = 1 - peso_corrente

            # Previsione conservativa
            previsioni[piva] = (fatturato_attuale * peso_corrente) + (media_storica * peso_storico)

        # Previsione spese ordinaria
        storico_spese = 0
        count = 0
        for anno, valore in storico_annuale_spese_ordinaria.items():
            if int(anno) < anno_corrente:
                storico_spese += valore
                count += 1

        media_spese_storiche = storico_spese / count if count > 0 else 0
        peso_corrente_spese = min(0.9, max(0.5, mese_corrente / 12))
        spese_previste = (spese_correnti_ordinaria * peso_corrente_spese) + (
                    media_spese_storiche * (1 - peso_corrente_spese))

        # 8. Calcolo punteggi integrati
        TARGET_FORFETTARIO = 85000
        MARGINE_SICURO = 2000
        punteggi = {}

        # Soglia per bonus/malus
        SOGLIA_IMPORTO = 5000
        # Fattori aumentati per maggiore impatto
        MALUS_FACTOR_FORFETTARIE = 0.3
        BONUS_FACTOR_ORDINARIA = 0.25

        # Calcola il fatturato totale corrente di tutte le forfettarie
        totale_forfettarie_corrente = sum(fatturati_correnti[piva] for piva in piva_forfettarie)

        # Calcola il fatturato medio corrente delle forfettarie
        if piva_forfettarie:
            media_forfettarie_corrente = totale_forfettarie_corrente / len(piva_forfettarie)
        else:
            media_forfettarie_corrente = 0

        # Punteggi forfettarie
        for piva in piva_forfettarie:
            # Punteggio base basato su distanza dalla soglia
            distanza_soglia = max(0, TARGET_FORFETTARIO - previsioni[piva])

            # Considera l'impatto della nuova fattura
            impatto_nuova_fattura = min(nuovo_importo, distanza_soglia)

            # Differenziale rispetto alla media
            differenziale_media = media_forfettarie_corrente - fatturati_correnti[piva]

            punteggio = (
                                (distanza_soglia * 0.7) +
                                (impatto_nuova_fattura * 0.5) +
                                (max(0, differenziale_media) * 0.4)
                        ) / 1000

            # Applica malus più impattante se l'importo è grande
            if nuovo_importo > SOGLIA_IMPORTO:
                eccesso = nuovo_importo - SOGLIA_IMPORTO
                # Malus proporzionale alla distanza dalla soglia
                fattore_distanza = min(1, distanza_soglia / TARGET_FORFETTARIO)
                malus = eccesso * MALUS_FACTOR_FORFETTARIE * (1 + fattore_distanza) / 500
                punteggio = max(0, punteggio - malus)

            punteggi[piva] = max(0, punteggio)

        # Punteggio ordinaria - RIBILANCIATO
        current_revenue = fatturati_correnti[id_ordinaria]
        current_expenses = spese_correnti_ordinaria
        projected_revenue = previsioni[id_ordinaria]

        # 1. Base score basato sul deficit corrente
        deficit_corrente = max(0, current_expenses - current_revenue)
        base_score = deficit_corrente * 0.8  # 0.8 punti per euro di deficit

        # 2. Score per avvicinamento al margine di sicurezza
        gap_previsto = max(0, projected_revenue - spese_previste)
        avvicinamento_margine = min(nuovo_importo, max(0, MARGINE_SICURO - gap_previsto))
        margine_score = avvicinamento_margine * 0.6  # 0.6 punti per euro che avvicinano al margine

        # 3. Bonus per copertura immediata del deficit
        copertura_immediata = min(nuovo_importo, deficit_corrente)
        copertura_score = copertura_immediata * 1.2  # Bonus più alto per copertura diretta

        # 4. Fattore di urgenza (deficit corrente vs previsione)
        fattore_urgenza = 1 + (deficit_corrente / max(1, current_revenue))

        punteggio_ordinaria = (base_score + margine_score + copertura_score) * fattore_urgenza / 100

        # Applica bonus più impattante se l'importo è grande
        if nuovo_importo > SOGLIA_IMPORTO:
            eccesso = nuovo_importo - SOGLIA_IMPORTO
            # Bonus proporzionale all'urgenza
            bonus = eccesso * BONUS_FACTOR_ORDINARIA * fattore_urgenza / 50
            punteggio_ordinaria += bonus

        # Aggiusta il punteggio per evitare valori estremi
        punteggio_ordinaria = min(100, max(5, punteggio_ordinaria))  # Minimo 5 per essere sempre considerata
        punteggi[id_ordinaria] = punteggio_ordinaria

        # 9. Normalizzazione e ordinamento
        # Calcola il punteggio massimo per normalizzazione
        max_punteggio = max(punteggi.values()) if punteggi else 1

        punteggi_finali = {}
        for piva, score in punteggi.items():
            cognome = id_to_last_name[piva]
            # Normalizza tra 0 e 100 se c'è un punteggio positivo
            punteggi_finali[cognome] = round((score / max_punteggio) * 100, 2) if max_punteggio > 0 else 0

        return dict(sorted(punteggi_finali.items(), key=lambda x: x[1], reverse=True))


    @staticmethod
    def calculate_three_expiration_dates(creation_date):
        """
        Calcola tre date di scadenza aggiungendo 30, 60 e 90 giorni alla data di creazione.

        :param creation_date: Data di creazione in formato stringa ("yyyy-mm-dd")
        :return: Lista di tre date di scadenza in formato stringa ("yyyy-mm-dd")
        """
        try:
            # Converte la stringa in un oggetto date
            date_obj = datetime.strptime(creation_date, "%Y-%m-%d").date()

            # Calcola le tre date di scadenza
            expiration_date_30 = date_obj + timedelta(days=30)
            expiration_date_60 = date_obj + timedelta(days=60)
            expiration_date_90 = date_obj + timedelta(days=90)

            # Restituisce le date formattate come stringhe
            return [
                expiration_date_30.strftime("%Y-%m-%d"),
                expiration_date_60.strftime("%Y-%m-%d"),
                expiration_date_90.strftime("%Y-%m-%d")
            ]
        except ValueError as e:
            # Gestisce errori di formattazione della data
            print(f"Errore nella conversione della data: {e}")
            return None

    @staticmethod
    def clear_invoices_list_from_NDC_and_stornate(invoices_list_of_maps):

        return [inv for inv in invoices_list_of_maps if
                inv[DBInvoicesColumns.TIPO.value] != InvoiceController.Tipologia.NOTA_DI_CREDITO.value and inv[
                    DBInvoicesColumns.STATUS.value] != InvoiceController.InvoiceRateizzSatus.STORNATA.value]


class PaymentsController:

    class PaymentsAggregateData(Enum):
        NUMERO_PAGAMENTI = "#PAGAMENTI"
        TOT_PAGAMENTI = "TOT. PAGAMENTI"

    def __init__(self, db_model: DatabaseModel, account_controller):
        self.db_model = db_model
        self.account_controller = account_controller

        #self.CY_payment_list = {}
        #self.payment_list = {}

        # i dati aggregati sono variabili di classe, aggiornati ogni volta che viene fatto un save di una nuova fattura
        self.payments_aggregated_data = {}
        self.CY_payments_aggregated_data = {}

        #self.update_payments_lists()
        self.update_aggregate_data()

        self.on_adding_payment_callbacks = []

    def update_aggregate_data(self):
        self.CY_payments_aggregated_data[PaymentsController.PaymentsAggregateData.NUMERO_PAGAMENTI.value] = self.count_payments(True)
        self.CY_payments_aggregated_data[PaymentsController.PaymentsAggregateData.TOT_PAGAMENTI.value] = self.calculate_tot_payments(True)

        self.payments_aggregated_data[PaymentsController.PaymentsAggregateData.NUMERO_PAGAMENTI.value] = self.count_payments(False)
        self.payments_aggregated_data[PaymentsController.PaymentsAggregateData.TOT_PAGAMENTI.value] = self.calculate_tot_payments(False)

    def save_payment(self, payment_data):
        """
        Gestisce il salvataggio di un pagamento, con validazioni di primo livello.
        :param payment_data: Dizionario contenente i dati del pagamento
        :return: Tuple (success, message), dove success è True/False
        """

        # Campi obbligatori (solo quelli modellati tramite entry)
        self.required_fields = {DBPaymentsColumns.PAYMENT_NAME.value, DBPaymentsColumns.PAYMENT_AMOUNT.value}

        # Validazione dei campi obbligatori
        missing_fields = [field for field in self.required_fields if not payment_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        # Validazione importi
        tot_pagamento = payment_data.get(DBPaymentsColumns.PAYMENT_AMOUNT.value)
        if not ValidationUtils.validate_amount(tot_pagamento):
            return False, "L'importo del preventivo non è valido"

        # prendo i dati necessari del conto
        nome_conto = payment_data.get("NOME CONTO")
        conto = self.account_controller.retrieve_account_map_by_name(nome_conto)
        id_conto = conto[DBAccountsColumns.ID.value]


        payment_data_prepared = {
            DBPaymentsColumns.PAYMENT_NAME.value : payment_data.get(DBPaymentsColumns.PAYMENT_NAME.value),
            DBPaymentsColumns.PAYMENT_AMOUNT.value: payment_data.get(DBPaymentsColumns.PAYMENT_AMOUNT.value),
            DBPaymentsColumns.INVOICE_ID.value : payment_data.get(DBPaymentsColumns.INVOICE_ID.value),
            DBPaymentsColumns.PAYMENT_DATE.value: payment_data.get(DBPaymentsColumns.PAYMENT_DATE.value),
            DBPaymentsColumns.LINKED_RATA.value: payment_data.get(DBPaymentsColumns.LINKED_RATA.value),
            DBPaymentsColumns.CONTO_ID.value: id_conto,
        }

        try:
            self.db_model.add_payment(**payment_data_prepared)
            self.update_aggregate_data()
            #for callback in self.on_adding_payment_callbacks:
            #    callback(payment_data.get(DBPaymentsColumns.INVOICE_ID.value))
            return True, "Produzione salvata con successo!"
        except Exception as e:
            return False, f"Errore durante il salvataggio: {str(e)}"

    def retrieve_payments(self, current_year=True):
        """
        Recupera tutti i pagamenti, filtrandoli per l'anno corrente se specificato.
        :param current_year: Booleano. Se True, ritorna solo i pagamenti effettuati nell'anno corrente.
        :return: Lista di tuple (righe) con i dati dei pagamenti.
        """
        rows = self.db_model.fetch_payments()
        if not current_year or not rows:
            return rows

        columns = [col.value for col in DBPaymentsColumns]
        # Converti le righe in dizionari
        payments_dicts = [dict(zip(columns, row)) for row in rows]
        # Applica il filtro utilizzando ControllerUtils
        filtered_dicts = ControllerUtils.filter_payments(payments_dicts, current_year)
        # Converti i dizionari filtrati nuovamente in tuple
        return [tuple(d[col] for col in columns) for d in filtered_dicts]

    def retrieve_payment_by_id(self, payment_id, current_year=True):
        """
        Recupera un pagamento specifico per ID, opzionalmente filtrando per l'anno corrente.
        :param payment_id: ID del pagamento.
        :param current_year: Se True, ritorna None se il pagamento non è dell'anno corrente.
        :return: Una tupla con i dati del pagamento oppure None.
        """
        row = self.db_model.fetch_payment_by_id(payment_id)
        if not row or not current_year:
            return row

        columns = [col.value for col in DBPaymentsColumns]
        payment_dict = dict(zip(columns, row))
        # Applica il filtro utilizzando ControllerUtils
        if ControllerUtils.filter_payments([payment_dict], current_year):
            return row
        return None

    def retrieve_payment_map_by_id(self, payment_id, current_year=True):
        """
        Recupera un pagamento specifico e lo restituisce come dizionario,
        filtrando per l'anno corrente se specificato.
        :param payment_id: ID del pagamento.
        :param current_year: Se True, ritorna None se il pagamento non è dell'anno corrente.
        :return: Dizionario con i dati del pagamento oppure None.
        """
        row = self.db_model.fetch_payment_by_id(payment_id)
        if not row:
            return None

        columns = [col.value for col in DBPaymentsColumns]
        payment_dict = dict(zip(columns, row))

        # Applica il filtro se necessario
        if current_year and not ControllerUtils.filter_payments([payment_dict], current_year):
            return None

        return payment_dict

    def retrieve_payments_map_list(self, current_year=True):
        """
        Recupera tutti i pagamenti e li restituisce come lista di dizionari,
        filtrandoli per l'anno corrente se specificato.
        """
        rows = self.db_model.fetch_payments()
        # Converti le righe in dizionari
        payments = [ValidationUtils._row_to_map(row, DBPaymentsColumns) for row in rows]

        # Applica il filtro utilizzando ControllerUtils
        if current_year:
            payments = ControllerUtils.filter_payments(payments, current_year)

        return payments

    def retrieve_payments_map_list_by_invoice_id(self, invoice_id, current_year=True):
        rows = self.db_model.fetch_payments_by_invoice_id(invoice_id)
        # Converti le righe in dizionari
        payments = [ValidationUtils._row_to_map(row, DBPaymentsColumns) for row in rows]

        # Applica il filtro utilizzando ControllerUtils
        if current_year:
            payments = ControllerUtils.filter_payments(payments, current_year)

        return payments

    def retrieve_last_payment_insert_map(self):
        """
        Recupera l'ultimo pagamento inserito e lo restituisce come dizionario.
        """
        row = self.db_model.fetch_last_payment_insert()
        return ValidationUtils._row_to_map(row, DBPaymentsColumns)

    def count_payments(self, current_year=True):
        """
        Conta il numero di pagamenti, applicando il filtro per l'anno corrente se specificato.

        :param current_year: Booleano. Se True, conta solo i pagamenti dell'anno corrente.
        :return: Numero di pagamenti (int)
        """
        # Usa retrieve_payments_map_list già modificata
        payments = self.retrieve_payments_map_list(current_year)
        return len(payments)

    def calculate_tot_payments(self, current_year=True):
        # Usa retrieve_payments_map_list già modificata
        payment_list = self.retrieve_payments_map_list(current_year)
        tot = 0.0
        for payment in payment_list:
            tot = tot + float(payment[DBPaymentsColumns.PAYMENT_AMOUNT.value])
        return tot

    def update_payment(self, payment_id, payment_data):
        """
        Aggiorna i dati di un pagamento esistente.
        :param payment_id: ID del pagamento da aggiornare
        :param payment_data: Dizionario contenente i dati da aggiornare
        :return: Tuple (success, message), dove success è True/False
        """
        try:
            # Controllo validità payment_id
            if not payment_id or not isinstance(payment_id, int):
                return False, "ID pagamento non valido. Deve essere un intero positivo."

            required_fields = {DBPaymentsColumns.PAYMENT_AMOUNT.value}

            # Validazione campi obbligatori
            missing_fields = [field for field in required_fields if not payment_data.get(field)]
            if missing_fields:
                return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."


            # Validazione Importo
            if DBPaymentsColumns.PAYMENT_AMOUNT.value in payment_data:
                amount = payment_data[DBPaymentsColumns.PAYMENT_AMOUNT.value]
                if amount and not ValidationUtils.validate_amount(amount):
                    return False, "L'importo inserito non è valido."

            payment_data[DBPaymentsColumns.UPDATED_AT.value] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Invoca il metodo del model per aggiornare l'utente
            self.db_model.update_payment(payment_id, **payment_data)
            return True, "Pagamento aggiornato con successo!"

        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento del pagamento: {str(e)}"

    def register_on_adding_payment_callbacks(self, *callbacks):
        self.on_adding_payment_callbacks = list(callbacks)

    def sum_payments_for_account(self, account_id):
        return self.db_model.sum_payments_by_account(account_id)

    # Controller corretto
    def delete_payment(self, payment_id):
        try:
            # Ottieni il risultato dal model
            result = self.db_model.delete_payment(payment_id)
            if result:
                return True, "Pagamento eliminato con successo."  # Successo
            else:
                return False, "Pagamento non trovato o errore durante l'eliminazione."  # Fallimento
        except Exception as e:
            return False, f"Errore durante l'eliminazione del pagamento: {str(e)}"  # Eccezione


class AccountController:

    class AccountsAggregateData(Enum):
        NUM_ACCOUNTS = "num_accounts"
        TOTAL_BALANCE = "total_balance"

    def __init__(self, db_model, user_controller):
        """
        Inizializza il controller con il model.
        :param db_model: Istanza di db_model per accedere ai dati.
        """
        self.db_model = db_model
        self.user_controller = user_controller

        #self.CY_account_list = {}
        #self.account_list = {}

        # i dati aggregati sono variabili di classe, aggiornati ogni volta che viene fatto un save di una nuova fattura
        self.accounts_aggregated_data = {}
        self.CY_accounts_aggregated_data = {}

        self.update_aggregate_data()
        #self.update_accounts_lists()

    def save_account(self, account_data):
        """
        Gestisce il salvataggio di un conto corrente, con validazioni di primo livello.
        :param account_data: Dizionario contenente i dati del conto
        :return: Tuple (success, message), dove success è True/False
        """

        # Campi obbligatori (solo quelli modellati tramite entry)
        self.required_fields = {DBAccountsColumns.NAME.value, DBAccountsColumns.INIT_BALANCE.value}

        # Validazione dei campi obbligatori
        missing_fields = [field for field in self.required_fields if not account_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        # Validazione importi
        init_balance = account_data.get(DBAccountsColumns.INIT_BALANCE.value)
        if not ValidationUtils.validate_amount(init_balance):
            return False, "L'importo INIT_BALANCE non è valido"

        account_data_prepared = {
            DBAccountsColumns.NAME.value : account_data.get(DBAccountsColumns.NAME.value),
            DBAccountsColumns.INIT_BALANCE.value: float(init_balance)
        }

        try:
            self.db_model.add_account(**account_data_prepared)
            self.update_aggregate_data()
            return True, "Produzione salvata con successo!"
        except Exception as e:
            return False, f"Errore durante il salvataggio: {str(e)}"

    def update_aggregate_data(self):
        """
        Inizializza (o resetta) i dati aggregati per gli account.
        Ad esempio, si potrebbe voler contare il numero totale di account e sommare i saldi.
        """
        # Dati aggregati per tutti gli account
        self.accounts_aggregated_data = {
            AccountController.AccountsAggregateData.NUM_ACCOUNTS.value: 0,
            AccountController.AccountsAggregateData.TOTAL_BALANCE.value: 0.0
        }
        # Dati aggregati per gli account dell'anno corrente
        self.CY_accounts_aggregated_data = {
            AccountController.AccountsAggregateData.NUM_ACCOUNTS.value: 0,
            AccountController.AccountsAggregateData.TOTAL_BALANCE.value: 0.0
        }

        # Recupera tutte le mappe e aggiorna i totali
        for account in self.retrieve_accounts_map_list():
            self.accounts_aggregated_data[AccountController.AccountsAggregateData.NUM_ACCOUNTS.value] += 1
            self.accounts_aggregated_data[AccountController.AccountsAggregateData.TOTAL_BALANCE.value] += float(account[DBAccountsColumns.INIT_BALANCE.value])

        for account in self.retrieve_accounts_map_list():
            self.CY_accounts_aggregated_data[AccountController.AccountsAggregateData.NUM_ACCOUNTS.value] += 1
            self.CY_accounts_aggregated_data[AccountController.AccountsAggregateData.TOTAL_BALANCE.value] += float(account[DBAccountsColumns.INIT_BALANCE.value])

    def retrieve_accounts(self):
        """
        Recupera tutte le tuple degli account dalla tabella, filtrandoli per l'anno corrente se specificato.
        La data di riferimento è il campo CREATED_AT.

        :param current_year: Booleano. Se True, ritorna solo gli account con CREATED_AT dell'anno corrente.
        :return: Lista di tuple.
        """
        rows = self.db_model.fetch_accounts()
        return rows

    def retrieve_account_by_id(self, account_id):
        """
        Recupera una tupla dell'account specifico per ID, opzionalmente filtrando per l'anno corrente.

        :param account_id: ID dell'account.
        :param current_year: Se True, ritorna None se l'account non ha ULTIMO_MOV nell'anno corrente.
        :return: Tupla con i dati dell'account oppure None.
        """
        row = self.db_model.fetch_account_by_id(account_id)
        return row

    def retrieve_account_map_by_id(self, account_id):
        """
        Recupera un account specifico per ID e lo restituisce come dizionario,
        opzionalmente filtrando per l'anno corrente.

        :param account_id: ID dell'account.
        :param current_year: Se True, ritorna None se l'account non è dell'anno corrente.
        :return: Dizionario con i dati dell'account oppure None.
        """
        row = self.db_model.fetch_account_by_id(account_id)
        return ValidationUtils._row_to_map(row, DBAccountsColumns)

    def retrieve_account_map_by_name(self, account_name):
        """
        Recupera un account specifico per nome, opzionalmente filtrando per l'anno corrente.

        :param account_name: Nome dell'account.
        :param current_year: Se True, ritorna None se l'account non ha ULTIMO_MOV nell'anno corrente.
        :return: Una tupla con i dati dell'account oppure None.
        """
        row = self.db_model.fetch_account_by_name(account_name)
        return ValidationUtils._row_to_map(row, DBAccountsColumns)

    def retrieve_accounts_map_list(self):
        """
        Recupera tutti gli account e li restituisce come lista di dizionari,
        filtrandoli per l'anno corrente se specificato.

        :param current_year: Booleano. Se True, filtra in base al campo ULTIMO_MOV.
        :return: Lista di dizionari con i dati degli account.
        """
        rows = self.db_model.fetch_accounts()
        return [ValidationUtils._row_to_map(row, DBAccountsColumns) for row in rows]

    def retrieve_last_account_insert_map(self):
        """
        Recupera l'ultimo account inserito e lo restituisce come dizionario.

        :return: Dizionario con i dati dell'ultimo account oppure None.
        """
        row = self.db_model.fetch_last_account_insert()
        return ValidationUtils._row_to_map(row, DBAccountsColumns)

    def count_accounts(self):
        """
        Conta il numero di account, applicando il filtro per l'anno corrente se specificato.

        :param current_year: Booleano. Se True, conta solo gli account dell'anno corrente.
        :return: Numero di account (int)
        """
        accounts = self.retrieve_accounts_map_list()
        return len(accounts)

    def get_accounts_names(self):
        """
        Recupera i nomi dei conti correnti dalla tabella degli accounts.
        :return: Una lista di nomi di conti correnti.
        """
        accounts = self.db_model.fetch_accounts()
        # Supponiamo che la colonna 'name' sia al secondo posto nella tabella
        return [account[1] for account in accounts]

    def calcola_saldo_attuale_conto(self, account_id):
        account = self.retrieve_account_by_id(account_id)
        if account:
            saldo = float(account[DBAccountsColumns.INIT_BALANCE.value])



            return saldo
        else:
            return None

    @staticmethod
    def get_accounts_mapping(db_model):
        """
        Recupera un dizionario di mapping {nome: id} dei conti correnti.
        Se la tabella è vuota, restituisce un dizionario vuoto.
        :return: Dizionario con mapping {nome: id} o un messaggio predefinito.
        """
        accounts = db_model.fetch_accounts()
        if not accounts:  # Verifica se la lista è vuota
            return {}
        return {account[1]: account[0] for account in
                accounts}  # Supponendo che account[0] sia l'ID e account[1] il nome


class TransfersController:
    def __init__(self, db_model, account_controller):
        """
        Inizializza il controller con il model.
        :param db_model: Istanza di db_model per accedere ai dati.
        """
        self.db_model = db_model
        self.account_controller = account_controller

    def save_transfer(self, transfer_data):
        """
        Gestisce il salvataggio di un bonifico, con validazioni di primo livello.
        :param transfer_data: Dizionario contenente i dati del bonifico
        :return: Tuple (success, message), dove success è True/False
        """

        # Campi obbligatori (solo quelli modellati tramite entry)
        self.required_fields = {DBTransfersColumns.DESCRIPTION.value, DBTransfersColumns.AMOUNT.value}

        # Validazione dei campi obbligatori
        missing_fields = [field for field in self.required_fields if not transfer_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        # Validazione importi
        spesa_lorda = transfer_data.get(DBTransfersColumns.AMOUNT.value)
        if not ValidationUtils.validate_amount(spesa_lorda):
            return False, "L'importo inserito non è valido"

        #prendo ID Conto Ricevente
        receiver_account_id = None
        receiver_account_name = transfer_data.get("CONTO RICEVENTE")
        receiver_account = self.account_controller.retrieve_account_map_by_name(receiver_account_name)
        receiver_account_id = receiver_account[DBTransfersColumns.ID.value] if receiver_account else None

        transfer_data_prepared = {
            DBTransfersColumns.DESCRIPTION.value: transfer_data.get(DBTransfersColumns.DESCRIPTION.value),
            DBTransfersColumns.AMOUNT.value: transfer_data.get(DBTransfersColumns.AMOUNT.value),
            DBTransfersColumns.SENDER_ACCOUNT_ID.value: transfer_data.get(DBTransfersColumns.SENDER_ACCOUNT_ID.value),
            DBTransfersColumns.RECEIVER_ACCOUNT_ID.value: receiver_account_id
        }

        try:
            self.db_model.add_transfer(**transfer_data_prepared)
            return True, "Bonifico salvato con successo!"
        except Exception as e:
            return False, f"Errore durante il salvataggio: {str(e)}"

    def retrieve_transfers(self):
        """
        Recupera tutte le tuple dei trasferimenti dalla tabella.
        :return: Lista di tuple.
        """
        rows = self.db_model.fetch_all_transfers()
        return rows

    def retrieve_transfer_by_id(self, transfer_id):
        """
        Recupera una tupla del trasferimento specifico per ID.
        :param transfer_id: ID del trasferimento.
        :return: Tupla con i dati del trasferimento oppure None.
        """
        row = self.db_model.fetch_transfer_by_id(transfer_id)
        return row

    def retrieve_transfer_map_by_id(self, transfer_id):
        """
        Recupera un trasferimento specifico per ID e lo restituisce come dizionario.
        :param transfer_id: ID del trasferimento.
        :return: Dizionario con i dati del trasferimento oppure None.
        """
        row = self.db_model.fetch_transfer_by_id(transfer_id)
        return ValidationUtils._row_to_map(row, DBTransfersColumns)

    def retrieve_transfers_map_list(self, current_year=True):
        """
        Recupera tutti i trasferimenti come lista di dizionari.
        :param current_year: Se True, filtra per l'anno corrente
        :return: Lista di dizionari con i dati dei trasferimenti.
        """
        rows = self.db_model.fetch_all_transfers()
        transfers = [ValidationUtils._row_to_map(row, DBTransfersColumns) for row in rows]
        return ControllerUtils.filter_transfers(transfers, current_year)

    def retrieve_last_transfer_insert_map(self):
        """
        Recupera l'ultimo trasferimento inserito come dizionario.
        :return: Dizionario con i dati dell'ultimo trasferimento oppure None.
        """
        row = self.db_model.fetch_last_transfer_insert()
        return ValidationUtils._row_to_map(row, DBTransfersColumns)

    def retrieve_sent_transfers_map_by_account(self, account_id, current_year=True):
        """
        Recupera i trasferimenti inviati da un conto come lista di dizionari
        :param account_id: ID del conto mittente
        :param current_year: Se True, filtra per l'anno corrente
        """
        transfers = self.db_model.fetch_sent_transfers_by_account(account_id)
        if not transfers:
            return []
        transfers_map = [ValidationUtils._row_to_map(transfer, DBTransfersColumns) for transfer in transfers]
        return ControllerUtils.filter_transfers(transfers_map, current_year)

    def retrieve_received_transfers_map_by_account(self, account_id, current_year=True):
        """
        Recupera i trasferimenti ricevuti da un conto come lista di dizionari
        :param account_id: ID del conto destinatario
        :param current_year: Se True, filtra per l'anno corrente
        """
        transfers = self.db_model.fetch_received_transfers_by_account(account_id)
        if not transfers:
            return []
        transfers_map = [ValidationUtils._row_to_map(transfer, DBTransfersColumns) for transfer in transfers]
        return ControllerUtils.filter_transfers(transfers_map, current_year)

    def retrieve_received_transfers_map(self, account_id, current_year=True):
        """
        Recupera i trasferimenti ricevuti da un conto come lista di dizionari.
        :param account_id: ID del conto ricevente
        :param current_year: Se True, filtra per l'anno corrente
        :return: Lista di dizionari
        """
        rows = self.db_model.fetch_received_transfers_by_account(account_id)
        transfers = [ValidationUtils._row_to_map(row, DBTransfersColumns) for row in rows]
        return ControllerUtils.filter_transfers(transfers, current_year)

    def retrieve_sent_transfers_map(self, account_id, current_year=True):
        """
        Recupera i trasferimenti inviati da un conto come lista di dizionari.
        :param account_id: ID del conto mittente
        :param current_year: Se True, filtra per l'anno corrente
        :return: Lista di dizionari
        """
        rows = self.db_model.fetch_sended_transfers_by_account(account_id)
        transfers = [ValidationUtils._row_to_map(row, DBTransfersColumns) for row in rows]
        return ControllerUtils.filter_transfers(transfers, current_year)

    def calculate_tot_amount_sent_transfers_by_account(self, account_id, current_year=True):
        """
        Calcola il totale dei trasferimenti inviati da un conto.
        :param account_id: ID del conto mittente
        :param current_year: Se True, considera solo l'anno corrente
        :return: Importo totale inviato
        """
        sent_transfers = self.retrieve_sent_transfers_map_by_account(account_id, current_year)
        amount = 0.0

        for transfer in sent_transfers:
            amount = amount + float(transfer[DBTransfersColumns.AMOUNT.value])

        return amount

    def calculate_tot_amount_received_transfers_by_account(self, account_id, current_year=True):
        """
        Calcola il totale dei trasferimenti ricevuti da un conto.
        :param account_id: ID del conto destinatario
        :param current_year: Se True, considera solo l'anno corrente
        :return: Importo totale ricevuto
        """
        received_transfers = self.retrieve_received_transfers_map_by_account(account_id, current_year)
        amount = 0.0

        for transfer in received_transfers:
            amount = amount + float(transfer[DBTransfersColumns.AMOUNT.value])

        return amount


class ProductionController:

    class ProductionsAggregateData(Enum):
        NUMERO_PRODUZIONI = "#PRODUZIONI"
        NUMERO_PRODUZIONI_ATTIVE = "#PRODUZIONI\nATTIVE"
        NUMERO_PRODUZIONI_CHIUSE = "#PRODUZIONI\nCHIUSE"
        MEDIA_ORE_PRODUZIONE = ViewUtils.split_string_by_length("MEDIA ORE PER PRODUZIONE", 15)
        MEDIA_PREZZO_ORARIO = ViewUtils.split_string_by_length("MEDIA PREZZO PER ORA DI PRODUZIONE", 17)

    class TipologiaProduzione(Enum): #DA ESTENDERE CON FILE DI CONFIGURAZIONE MODIFICABILE DA UTENTE
        PRODUZIONE = "PRODUZIONE"
        POST_PRODUZIONE = "POST_PRODUZIONE"
        MISTA = "MISTA" #POST + PRODUZIONE
        CONSULENZA = "CONSULENZA"

    class TipologiaOutput(Enum): #DA ESTENDERE CON FILE DI CONFIGURAZIONE MODIFICABILE DA UTENTE
        VIDEO_MUSICALE = "VIDEO_MUSICALE"
        ADV_SOCIAL = "ADV_SOCIAL"
        COMMERCIAL = "COMMERCIAL"
        INTEGRAZIONE_VFX = "INTEGRAZIONE_VFX"

    class Stato(Enum):
        START_WAITING = "START_WAITING"
        DOC_WAITING = "DOC_WAITING"
        WORKING = "WORKING"
        REVISION = "REVISION"
        CLOSED = "CLOSED"

    def __init__(self,  db_model: DatabaseModel, client_controller):
        self.db_model = db_model
        self.client_controller = client_controller

        #self.CY_production_list = {}
        #self.production_list = {}

        #self.update_productions_lists()

        # i dati aggregati sono variabili di classe, aggiornati ogni volta che viene fatto un save di una nuova fattura
        self.productions_aggregated_data = {}
        self.CY_productions_aggregated_data = {}

    def save_production(self, production_data):
        """
        Gestisce il salvataggio di una produzione, con validazioni di primo livello.
        :param production_data: Dizionario contenente i dati della produzione
        :return: Tuple (success, message), dove success è True/False
        """

        # Campi obbligatori (solo quelli modellati tramite entry)
        self.required_fields = {DBProductionsColumns.NAME.value, DBProductionsColumns.HOURS.value, DBProductionsColumns.TOTALE_PREVENTIVO.value}

        # Validazione dei campi obbligatori
        missing_fields = [field for field in self.required_fields if not production_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        # Validazione importi
        tot_preventivo = production_data.get(DBProductionsColumns.TOTALE_PREVENTIVO.value)
        if not ValidationUtils.validate_amount(tot_preventivo):
            return False, "L'importo del preventivo non è valido"

        #validazione hours
        hours = production_data.get(DBProductionsColumns.HOURS.value)
        if not ValidationUtils.validate_integers(tot_preventivo):
            return False, "Il monte ore non è valido"

        # prendo i dati necessari del cliente
        nome_cliente = production_data.get("NOME CLIENTE")
        cliente_list = self.client_controller.retrieve_client_by_name(nome_cliente)
        cliente_map = self.client_controller.retrieve_client_map_by_id(cliente_list[0])
        id_cliente = cliente_map[DBClientsColumns.ID.value]
        tipologia_cliente = cliente_map[DBClientsColumns.TIPOLOGIA.value]

        #aggiungo al nome della produzione il nome del cliente
        prod_name = production_data.get(DBProductionsColumns.NAME.value)
        prod_name = nome_cliente + " - " + prod_name

        production_data_prepared = {
            DBProductionsColumns.NAME.value : prod_name,
            DBProductionsColumns.CLIENT_ID.value: id_cliente,
            DBProductionsColumns.HOURS.value: production_data.get(DBProductionsColumns.HOURS.value),
            DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value: production_data.get(DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value),
            DBProductionsColumns.TIPOLOGIA_OUTPUT.value: production_data.get(DBProductionsColumns.TIPOLOGIA_OUTPUT.value),
            DBProductionsColumns.STATO.value: production_data.get(DBProductionsColumns.STATO.value),
            DBProductionsColumns.END_DATE.value: production_data.get(DBProductionsColumns.END_DATE.value),
            DBProductionsColumns.TOTALE_PREVENTIVO.value: production_data.get(DBProductionsColumns.TOTALE_PREVENTIVO.value),
        }

        try:
            self.db_model.add_production(**production_data_prepared)
            self.update_aggregate_data()
            return True, "Produzione salvata con successo!"
        except Exception as e:
            return False, f"Errore durante il salvataggio: {str(e)}"

    def update_production(self, production_id, production_data):
        """
        Aggiorna i dati di una produzione esistente.
        :param production_id: ID della produzione da aggiornare
        :param production_data: Dizionario contenente i dati da aggiornare
        :return: Tuple (success, message), dove success è True/False
        """
        try:
            # Controllo validità payment_id
            if not production_id or not isinstance(production_id, int):
                return False, "ID pagamento non valido. Deve essere un intero positivo."

            required_fields = {DBProductionsColumns.NAME.value, DBProductionsColumns.HOURS.value, DBProductionsColumns.TOTALE_PREVENTIVO.value}

            # Validazione campi obbligatori
            missing_fields = [field for field in required_fields if not production_data.get(field)]
            if missing_fields:
                return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."


            # Validazione ore di lavoro
            if DBProductionsColumns.HOURS.value in production_data:
                hours = production_data[DBProductionsColumns.HOURS.value]
                if hours and not ValidationUtils.validate_amount(hours):
                    return False, "L'importo orario inserito non è valido, inserire un valore numerico"

            # Validazione Importo
            if DBProductionsColumns.TOTALE_PREVENTIVO.value in production_data:
                amount = production_data[DBProductionsColumns.TOTALE_PREVENTIVO.value]
                if amount and not ValidationUtils.validate_amount(amount):
                    return False, "L'importo del preventivo inserito non è valido."

            production_data[DBProductionsColumns.UPDATED_AT.value] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Invoca il metodo del model per aggiornare l'utente
            self.db_model.update_production(production_id, **production_data)
            self.update_aggregate_data()
            return True, "Produzione aggiornata con successo!"

        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento della produzione: {str(e)}"

    def delete_production(self, production_id):
        return self.db_model.remove_production(production_id)

    def update_specific_production_data(self, production_id, production_data):
        try:
            self.db_model.update_production(production_id, **production_data)
            self.update_aggregate_data()
            return True, "Produzione aggiornata con successo!"
        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento della produzione: {str(e)}"

    def retrieve_productions(self, current_year=True):
        """
        Recupera tutte le productions, filtrandole per l'anno corrente se specificato.

        :param current_year: Se True, ritorna solo le productions dell'anno corrente.
        :return: Lista di tuple (righe) con i dati delle productions.
        """
        rows = self.db_model.fetch_productions()
        if current_year:
            current_year_value = datetime.now().year
            columns = [col.value for col in DBProductionsColumns]
            # Supponiamo che il campo della data sia CREATION_DATE
            date_index = columns.index(DBProductionsColumns.CREATED_AT.value)
            filtered_rows = []
            for row in rows:
                date_str = row[date_index]
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                if dt.year == current_year_value:
                    filtered_rows.append(row)
            rows = filtered_rows
        return rows

    def retrieve_production_by_id(self, production_id):
        """
        Recupera una production specifica per ID, opzionalmente filtrando per l'anno corrente.

        :param production_id: ID della production.
        :param current_year: Se True, ritorna None se la production non è dell'anno corrente.
        :return: Una tupla con i dati della production oppure None.
        """
        row = self.db_model.fetch_production_by_id(production_id)
        return row

    def retrieve_production_map_by_name(self, production_name, current_year=True):
        """
        Recupera una production specifica per ID, opzionalmente filtrando per l'anno corrente.

        :param production_name: Nome della production.
        :param current_year: Se True, ritorna None se la production non è dell'anno corrente.
        :return: Una tupla con i dati della production oppure None.
        """
        row = self.db_model.fetch_production_by_name(production_name)
        if row and current_year:
            current_year_value = datetime.now().year
            columns = [col.value for col in DBProductionsColumns]
            date_index = columns.index(DBProductionsColumns.CREATED_AT.value)
            date_str = row[date_index]
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
            if dt.year != current_year_value:
                return None
        return ValidationUtils._row_to_map(row, DBProductionsColumns)

    def retrieve_production_map_by_id(self, production_id, current_year=True):
        """
        Recupera una production specifica e la restituisce come dizionario,
        filtrando per l'anno corrente se specificato.

        :param production_id: ID della production.
        :param current_year: Se True, ritorna None se la production non è dell'anno corrente.
        :return: Dizionario con i dati della production oppure None.
        """
        row = self.db_model.fetch_production_by_id(production_id)
        if row and current_year:
            current_year_value = datetime.now().year
            columns = [col.value for col in DBProductionsColumns]
            date_index = columns.index(DBProductionsColumns.CREATED_AT.value)
            date_str = row[date_index]
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
            if dt.year != current_year_value:
                return None
        return ValidationUtils._row_to_map(row, DBProductionsColumns)

    def retrieve_productions_map_list(self, current_year=True):
        """
        Recupera tutte le productions e le restituisce come lista di dizionari,
        filtrandole per l'anno corrente se specificato.
        """
        rows = self.db_model.fetch_productions()
        # Converti subito le tuple in dizionari
        productions = [ValidationUtils._row_to_map(row, DBProductionsColumns) for row in rows]

        # Applica il filtro usando il metodo statico
        return ControllerUtils.filter_productions(productions, current_year)

    def retrieve_production_with_invoices_map_list(self, production_id):
        invoices = self.db_model.fetch_production_with_invoices(production_id)
        all_columns = list(DBProductionsColumns) + list(DBInvoicesColumns)
        invoices_map = [ValidationUtils._row_to_map(invoice, all_columns) for invoice in invoices]

        return invoices_map

    def retrieve_last_production_insert_map(self):
        """
        Recupera l'ultima production inserita e la restituisce come dizionario.
        """
        row = self.db_model.fetch_last_production_insert()
        return ValidationUtils._row_to_map(row, DBProductionsColumns)

    def retrieve_productions_map_list_by_client_id(self, client_id, current_year=True):
        """
        Recupera tutte le produzioni di un certo cliente e le restituisce come lista di dizionari,
        filtrandole per l'anno corrente se specificato.

        :param client_id: ID del cliente.
        :param current_year: Se True, filtra le produzioni per l'anno corrente.
        :return: Lista di dizionari contenenti i dati delle produzioni.
        """
        rows = self.db_model.fetch_productions_by_client_id(client_id)
        # Converti le tuple in dizionari
        productions = [ValidationUtils._row_to_map(row, DBProductionsColumns) for row in rows]

        # Applica il filtro usando il metodo statico
        return ControllerUtils.filter_productions(productions, current_year)

    def calculate_production_cost_per_hour(self, production_id):
        production_map = self.retrieve_production_map_by_id(production_id)
        hours = int(production_map[DBProductionsColumns.HOURS.value])
        tot_preventivo = float(production_map[DBProductionsColumns.TOTALE_PREVENTIVO.value])
        cost_per_hour = tot_preventivo/hours if hours != 0 and hours.is_integer() else -1

        return cost_per_hour

    def count_productions(self, current_year=True):
        """
        Conta il numero di productions, applicando il filtro per l'anno corrente se specificato.

        :param current_year: Se True, conta solo le productions dell'anno corrente.
        :return: Numero di productions (int).
        """
        if current_year:
            productions = self.retrieve_productions_map_list(current_year=True)
        else:
            productions = self.retrieve_productions_map_list(current_year=False)
        return len(productions)

    def count_productions_of_client(self, client_id, current_year=True):
        productions_map = self.retrieve_productions_map_list_by_client_id(client_id, current_year=True)
        return(len(productions_map))

    def count_active_productions(self, current_year=True):
        """
        Conta il numero di productions attive, applicando il filtro per l'anno corrente se specificato.

        :param current_year: Se True, conta solo le productions dell'anno corrente.
        :return: Numero di productions (int).
        """
        if current_year:
            productions = self.retrieve_productions_map_list(current_year=True)
        else:
            productions = self.retrieve_productions_map_list(current_year=False)

        productions = [prod for prod in productions if prod[DBProductionsColumns.STATO.value] != ProductionController.Stato.CLOSED.value]
        return len(productions)

    def count_closed_productions(self, current_year=True):
        closed_productions = self.count_productions(current_year) - self.count_active_productions(current_year)
        return closed_productions

    def mean_hours_for_production(self, current_year=True):
        productions = self.retrieve_productions_map_list(current_year)
        tot_hours = 0
        for prod in productions:
            tot_hours = tot_hours + float(prod[DBProductionsColumns.HOURS.value])
        mean = 0
        if len(productions) > 0:
            mean = tot_hours/len(productions)
        return mean

    def mean_prezzo_orario(self, current_year=True):
        productions = self.retrieve_productions_map_list(current_year)
        sum = 0
        for prod in productions:
            cost_per_hour = self.calculate_production_cost_per_hour(prod[DBProductionsColumns.ID.value])
            sum = sum + cost_per_hour if cost_per_hour != -1 else 0
        mean = 0
        if len(productions) > 0:
            mean = sum/len(productions)
        return mean

    def update_aggregate_data(self):
        self.CY_productions_aggregated_data[ProductionController.ProductionsAggregateData.NUMERO_PRODUZIONI.value] = self.count_productions(True)
        self.CY_productions_aggregated_data[ProductionController.ProductionsAggregateData.NUMERO_PRODUZIONI_ATTIVE.value] = self.count_active_productions(True)
        self.CY_productions_aggregated_data[ProductionController.ProductionsAggregateData.NUMERO_PRODUZIONI_CHIUSE.value] = self.count_closed_productions(True)

    def calcola_totale_servizi_rimborsi_per_produzione(self, production_id):

        invoices_map = self.retrieve_production_with_invoices_map_list(production_id)

        tot = 0.0
        for invoice in invoices_map:
            tot += invoice[DBInvoicesColumns.SERVIZI.value] + invoice[DBInvoicesColumns.RIMBORSI.value] if invoice[DBInvoicesColumns.NUMERO_FATTURA.value] is not None else 0

        return tot


class ExpenseController:

    class ExpensesAggregateData(Enum):
        NUMERO_SPESE = "#SPESE"
        TOT_SPESE = "TOT. SPESE"

    class RecurringExpensesFrequencies(Enum):
        SETTIMANALE = "SETTIMANALE"
        MENSILE = "MENSILE"
        BIMESTRALE = "BIMESTRALE"
        TRIMESTRALE = "TRIMESTRALE"
        QUADRIMESTRALE = "QUADRIMESTRALE"
        SEMESTRALE = "SEMESTRALE"
        ANNUALE = "ANNUALE"

    class RecurringExpensesStatus(Enum):
        ATTIVA = "Attiva"
        SOSPESA = "Sospesa"

    def __init__(self, db_model, user_controller, account_controller, invoice_controller, supplier_controller, recurring_expenses_settings, catalogo_elenchi):
        self.db_model = db_model
        self.user_controller = user_controller
        self.account_controller = account_controller
        self.invoice_controller = invoice_controller
        self.supplier_controller = supplier_controller
        self.recurring_expenses_settings = recurring_expenses_settings
        self.catalogo_elenchi = catalogo_elenchi

        self.create_recurring_expenses()

    def save_expense(self, expense_data):
        """
        Gestisce il salvataggio di una spesa, con validazioni di primo livello.
        :param expense_data: Dizionario contenente i dati della spesa
        :return: Tuple (success, message), dove success è True/False
        """

        # Campi obbligatori (solo quelli modellati tramite entry)
        self.required_fields = {DBExpensesColumns.NAME.value, DBExpensesColumns.TOT_AMOUNT.value}

        # Validazione dei campi obbligatori
        missing_fields = [field for field in self.required_fields if not expense_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        # Validazione importi
        spesa_lorda = expense_data.get(DBExpensesColumns.TOT_AMOUNT.value)
        if not ValidationUtils.validate_amount(spesa_lorda):
            return False, "L'importo lordo non è valido"

        #prendo ID Utente per l'anticipo
        user_id_anticipo = None
        user_name = expense_data.get("QUALCUNO HA ANTICIPATO?")
        if len(user_name.split(" ")) >= 2: #se è un nome di un utente vero allora è Nome Cognome
            user_first = user_name.split(" ")[0]
            user_last = user_name.split(" ")[1]
            user = self.user_controller.retrieve_user_map_by_fullname(user_first, user_last)
            user_id_anticipo = user[DBUsersColumns.ID.value]

        #prendo ID Utente per la deduzione
        user_id_deduzione = None
        user_name = expense_data.get("DEDUZIONE A CARICO")
        if user_name is not None and len(user_name.split(" ")) >= 2: #se è un nome di un utente vero allora è Nome Cognome
            user_first = user_name.split(" ")[0]
            user_last = user_name.split(" ")[1]
            user = self.user_controller.retrieve_user_map_by_fullname(user_first, user_last)
            user_id_deduzione = user[DBUsersColumns.ID.value]

        #prendo ID fattura associata:
        invoice_id = None
        #la view si occupa di non mandare tra i dati la fattura associata se la categoria non è "SPESA DI PRODUZIONE"
        invoice_name = expense_data.get("FATTURA ASSOCIATA")
        if invoice_name is not None:
            invoice = self.invoice_controller.retrieve_invoice_map_by_name(invoice_name, True)
            if invoice != {}:
                invoice_id = invoice[DBInvoicesColumns.ID.value]

        #calcolo importo netto
        aliquota_iva = float(expense_data.get("ALIQUOTA IVA"))
        iva = float(spesa_lorda)*aliquota_iva
        spesa_netta = float(spesa_lorda)-iva


        #prendo ID supplier
        supplier_id = None
        supplier_name = expense_data.get("NOME FORNITORE")
        if supplier_name:
            supplier = self.supplier_controller.retrieve_supplier_map_by_name(supplier_name)
            supplier_id = supplier[DBSuppliersColumns.ID.value]

        #prendo ID conto
        conto_id = None
        conto_name = expense_data.get("CONTO")
        if conto_name:
            conto = self.account_controller.retrieve_account_map_by_name(conto_name)
            conto_id = conto[DBAccountsColumns.ID.value]

        nome_spesa = supplier_name + " - " + expense_data.get(DBExpensesColumns.NAME.value)


        expense_data_prepared = {
            DBExpensesColumns.NAME.value: nome_spesa,
            DBExpensesColumns.USER_ID_ANTICIPO.value: user_id_anticipo,
            DBExpensesColumns.USER_ID_DEDUZIONE.value: user_id_deduzione,
            DBExpensesColumns.SUPPLIER_ID.value: supplier_id,
            DBExpensesColumns.CATEGORY.value: expense_data.get(DBExpensesColumns.CATEGORY.value),
            DBExpensesColumns.NET_AMOUNT.value: spesa_netta,
            DBExpensesColumns.IVA_AMOUNT.value: iva,
            DBExpensesColumns.TOT_AMOUNT.value: float(spesa_lorda),
            DBExpensesColumns.DATE.value: expense_data.get(DBExpensesColumns.DATE.value),
            DBExpensesColumns.DEDUCIBILE.value: expense_data.get(DBExpensesColumns.DEDUCIBILE.value),
            DBExpensesColumns.ACCOUNT_ID.value: conto_id,
            DBExpensesColumns.LINKED_INVOICE_ID.value: invoice_id

        }

        try:
            self.db_model.add_expense(**expense_data_prepared)
            self.update_aggregate_data()
            return True, "Spesa salvata con successo!"
        except Exception as e:
            return False, f"Errore durante il salvataggio: {str(e)}"

    def update_expense(self, expense_id, expense_data):
        """
        Aggiorna i dati di unaa spesa esistente.
        :param expense_id: ID dellla spesa da aggiornare
        :param expense_data: Dizionario contenente i dati da aggiornare
        :return: Tuple (success, message), dove success è True/False
        """
        try:
            # Controllo validità refund_id
            if not expense_id or not isinstance(expense_id, int):
                return False, "ID rimborso non valido. Deve essere un intero positivo."

            required_fields = {DBExpensesColumns.NET_AMOUNT.value, DBExpensesColumns.TOT_AMOUNT.value, DBExpensesColumns.IVA_AMOUNT.value}

            # Validazione campi obbligatori
            missing_fields = [field for field in required_fields if not expense_data.get(field)]
            if missing_fields:
                return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

            # Validazione Importi
            if DBExpensesColumns.NET_AMOUNT.value in expense_data:
                amount = expense_data[DBExpensesColumns.NET_AMOUNT.value]
                if amount and not ValidationUtils.validate_amount(amount):
                    return False, "L'importo netto inserito non è valido."

            if DBExpensesColumns.TOT_AMOUNT.value in expense_data:
                amount = expense_data[DBExpensesColumns.TOT_AMOUNT.value]
                if amount and not ValidationUtils.validate_amount(amount):
                    return False, "L'importo lordo inserito non è valido."

            if DBExpensesColumns.IVA_AMOUNT.value in expense_data:
                amount = expense_data[DBExpensesColumns.IVA_AMOUNT.value]
                if amount and not ValidationUtils.validate_amount(amount):
                    return False, "L'importo iva inserito non è valido."

            if expense_data[DBExpensesColumns.CATEGORY.value] != dict(self.catalogo_elenchi["expenses_category"]).get("PRODUCTION_EXPENSE"):
                expense_data.pop(DBExpensesColumns.LINKED_INVOICE_ID.value)

            if expense_data[DBExpensesColumns.DEDUCIBILE.value] == "No":
                expense_data.pop(DBExpensesColumns.USER_ID_DEDUZIONE.value)

            expense_data[DBExpensesColumns.updated_at.value] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Invoca il metodo del model per aggiornare l'utente
            self.db_model.update_expense(expense_id, **expense_data)
            return True, "Spesa aggiornata con successo!"

        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento della spesa: {str(e)}"

    def delete_expense(self, expense_id):
        return self.db_model.remove_expense(expense_id)

    def retrieve_expenses(self, current_year=True):
        """
        Recupera tutte le expenses, filtrandole per l'anno corrente se specificato.
        :param current_year: Booleano. Se True, ritorna solo le expenses effettuate nell'anno corrente.
        :return: Lista di tuple (righe) con i dati delle expenses.
        """
        rows = self.db_model.fetch_expenses()
        if current_year:
            current_year_value = datetime.now().year
            columns = [col.value for col in DBExpensesColumns]
            # Supponiamo che il campo della data si chiami DATE
            date_index = columns.index(DBExpensesColumns.DATE.value)
            filtered_rows = []
            for row in rows:
                date_str = row[date_index]
                try:
                    # Prova a leggere la data con data e orario; se fallisce, usa solo la data
                    try:
                        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        dt = datetime.strptime(date_str, "%Y-%m-%d")
                    if dt.year == current_year_value:
                        filtered_rows.append(row)
                except Exception as e:
                    print(f"Errore durante il parsing della data '{date_str}': {e}")
            rows = filtered_rows
        return rows

    def retrieve_expense_by_id(self, expense_id):
        """
        Recupera una expense specifica per ID, opzionalmente filtrando per l'anno corrente.
        :param expense_id: ID della expense.
        :param current_year: Se True, ritorna None se la expense non è dell'anno corrente.
        :return: Una tupla con i dati della expense oppure None.
        """
        row = self.db_model.fetch_expense_by_id(expense_id)
        return row

    def retrieve_expense_map_by_id(self, expense_id):
        """
        Recupera una expense specifica e la restituisce come dizionario,
        filtrando per l'anno corrente se specificato.
        :param expense_id: ID della expense.
        :param current_year: Se True, ritorna None se la expense non è dell'anno corrente.
        :return: Dizionario con i dati della expense oppure None.
        """
        row = self.db_model.fetch_expense_by_id(expense_id)
        return ValidationUtils._row_to_map(row, DBExpensesColumns)

    def retrieve_expenses_map_list(self, current_year=True):
        """
        Recupera tutte le expenses e le restituisce come lista di dizionari,
        filtrandole per l'anno corrente se specificato.
        """
        rows = self.db_model.fetch_expenses()
        # Converti le tuple in dizionari
        expenses = [ValidationUtils._row_to_map(row, DBExpensesColumns) for row in rows]

        # Applica il filtro usando il metodo statico
        return ControllerUtils.filter_expenses(expenses, current_year)

    def retrieve_last_expense_insert_map(self):
        """
        Recupera l'ultima expense inserita e la restituisce come dizionario.
        """
        row = self.db_model.fetch_last_expense_insert()
        return ValidationUtils._row_to_map(row, DBExpensesColumns)

    def count_expenses(self, current_year=True):
        """
        Conta il numero di expenses, applicando il filtro per l'anno corrente se specificato.

        :param current_year: Booleano. Se True, conta solo le expenses dell'anno corrente.
        :return: Numero di expenses (int).
        """
        expenses = self.retrieve_expenses_map_list(current_year=current_year)
        return len(expenses)

    def calculate_tot_expenses(self, current_year=True):
        """
        Calcola il totale degli importi delle expenses, filtrandole per l'anno corrente se specificato.

        :param current_year: Booleano. Se True, somma solo le expenses dell'anno corrente.
        :return: Totale degli importi (float).
        """
        tot = 0.0
        # Recupera la lista delle expenses come lista di dizionari
        expense_list = self.retrieve_expenses_map_list(current_year=current_year)
        for expense in expense_list:
            tot += float(expense[DBExpensesColumns.TOT_AMOUNT.value])
        return tot

    def update_aggregate_data(self):
        return

    def create_recurring_expenses(self):
        """
        Controlla per ogni spesa ricorrente attiva se in questo periodo
        (settimanale, mensile, ecc.) ne è già stata emessa una; altrimenti
        la crea con nome f"{description}_{gg-mm-YYYY}".
        """

        print("\nControllo emissione spese ricorrenti...")

        today = datetime.today().date()
        # Recupera tutte le spese già in DB (solo anno corrente per efficienza)
        all_expenses = self.retrieve_expenses_map_list(current_year=True)

        # Funzione di utilità per calcolare la data di inizio del periodo
        def get_period_start(freq: str, ref: date) -> date:
            if freq == ExpenseController.RecurringExpensesFrequencies.SETTIMANALE.value:
                return ref - timedelta(days=7)
            if freq == ExpenseController.RecurringExpensesFrequencies.MENSILE.value:
                return ref - relativedelta(months=1)
            if freq == ExpenseController.RecurringExpensesFrequencies.BIMESTRALE.value:
                return ref - relativedelta(months=2)
            if freq == ExpenseController.RecurringExpensesFrequencies.TRIMESTRALE.value:
                return ref - relativedelta(months=3)
            if freq == ExpenseController.RecurringExpensesFrequencies.QUADRIMESTRALE.value:
                return ref - relativedelta(months=4)
            if freq == ExpenseController.RecurringExpensesFrequencies.SEMESTRALE.value:
                return ref - relativedelta(months=6)
            if freq == ExpenseController.RecurringExpensesFrequencies.ANNUALE.value:
                return ref - relativedelta(years=1)
            # default: tutto l'anno
            return date(ref.year, 1, 1)

        for key, exp in self.recurring_expenses_settings.items():
            # 1) solo le attive
            if not exp.status:
                print(f"emissione di {exp.description} saltata poiché disattiva")
                continue

            # 2) calcola periodo
            start = get_period_start(exp.frequency, today)
            end = today

            # 3) genera pattern nome: description + "_" + dd-mm-YYYY
            suffix = today.strftime("%d-%m-%Y")
            nominal = f"{exp.description}_{suffix}"

            # 4) verifica se esiste già, in modo fuzzy
            raw_prefix = exp.description  # es. "Affitto Ufficio"
            prefix_norm = ControllerUtils.normalize_string_for_key(raw_prefix)

            found = False
            for e in all_expenses:
                name = e[DBExpensesColumns.NAME.value]  # es. "affitto ufficio_27-04-2025"
                name_part, _, date_part = name.rpartition("_")  # split su ultimo "_"
                # normalizza la porzione descrittiva
                name_prefix_norm = ControllerUtils.normalize_string_for_key(name_part)

                # se il prefisso normalizzato corrisponde
                if name_prefix_norm != prefix_norm:
                    continue

                # prova a interpretare la data
                try:
                    dt = datetime.strptime(date_part, "%d-%m-%Y").date()
                except ValueError:
                    continue

                if start <= dt <= end:
                    found = True
                    matched_name = name
                    break

            if found:
                print(f"Emissione di {nominal} saltata: già presente ({matched_name}) nel periodo {start}–{end}")
                continue

            # 5) nessuna trovata: creane una nuova
            # recupera ID conto
            acct = self.account_controller.retrieve_account_map_by_name(exp.account)
            acct_id = acct.get(DBAccountsColumns.ID.value) if acct else None

            gross = exp.amount
            iva_rate = exp.iva

            netto = round(gross / (1 + iva_rate), 2)
            iva_amt = round(gross - netto, 2)

            if exp.deductible:
                deductor_id = exp.deductor
            else:
                deductor_id = None

            new_exp = {
                DBExpensesColumns.NAME.value: nominal,
                DBExpensesColumns.SUPPLIER_ID.value: self.supplier_controller.retrieve_supplier_map_by_name(exp.supplier)[DBSuppliersColumns.ID.value],
                DBExpensesColumns.CATEGORY.value: exp.category,
                DBExpensesColumns.NET_AMOUNT.value: netto,
                DBExpensesColumns.IVA_AMOUNT.value: iva_amt,
                DBExpensesColumns.TOT_AMOUNT.value: gross,
                DBExpensesColumns.USER_ID_DEDUZIONE.value: deductor_id,
                DBExpensesColumns.DATE.value: today.isoformat(),
                DBExpensesColumns.DEDUCIBILE.value: "Sì" if exp.deductible else "No",
                DBExpensesColumns.ACCOUNT_ID.value: acct_id,
                DBExpensesColumns.RICORRENTE.value: 1
            }
            try:
                self.db_model.add_expense(**new_exp)
                print(f"Spesa ricorrente creata: {nominal}")
            except Exception as e:
                print(f"Errore creando spesa '{nominal}': {e}")

    def sum_expenses_for_account(self, account_id):
        return self.db_model.sum_expenses_by_account(account_id)

    def add_DB_voices_for_recurring_expenses(self):
        # Estraggo la chiave del settore di default
        default_sector_key = self.catalogo_elenchi["clients_business_sectors"][0][0]

        for expense in self.recurring_expenses_settings.values():
            supplier_name = expense.supplier
            account_name = expense.account

            # ---- FORNITORE ----
            supp_map = self.supplier_controller.retrieve_supplier_map_by_name(supplier_name)
            if supp_map is None:
                esito, to_print = self.supplier_controller.save_supplier(
                    supplier_data={
                        DBSuppliersColumns.NAME.value: supplier_name,
                        DBSuppliersColumns.CATEGORIA.value: default_sector_key
                    }
                )
                print(to_print)
            else:
                print(f"Fornitore '{supplier_name}' già presente. SKIPPING")

            # ---- CONTO ----
            acc_map = self.account_controller.retrieve_account_map_by_name(account_name)
            if acc_map is None:
                esito, to_print = self.account_controller.save_account(
                    account_data={
                        DBAccountsColumns.NAME.value: account_name,
                        DBAccountsColumns.INIT_BALANCE.value: 0
                    }
                )
                print(to_print)
            else:
                print(f"Conto '{account_name}' già presente. SKIPPING")


class SupplierController:

    class Aggregate_data(Enum):
        TOT_SPESE = "tot_spese"
        NUM_SPESE = "num_spese"
        MEDIA_SPESE = "media_spese"

    def __init__(self, db_model):
        self.db_model = db_model

    def save_supplier(self, supplier_data):
        """
        Gestisce il salvataggio di un fornitore, con validazioni di primo livello.
        :param supplier_data: Dizionario contenente i dati del supplier
        :return: Tuple (success, message), dove success è True/False
        """
        # Campi obbligatori
        required_fields = {DBSuppliersColumns.NAME.value}

        # Validazione dei campi obbligatori
        missing_fields = [field for field in required_fields if not supplier_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        # Validazione Partita IVA
        partita_iva = supplier_data.get(DBSuppliersColumns.PARTITA_IVA.value)
        if partita_iva and not ValidationUtils.validate_partita_iva(partita_iva):
            return False, "La partita IVA non è valida. Deve contenere esattamente 11 cifre."


        # Preparazione dei dati per il salvataggio
        supplier_data_filtered = {
            column.value: supplier_data.get(column.value)
            for column in DBSuppliersColumns
            if column.value in supplier_data
        }

        # Rimuove i campi None
        supplier_data_filtered = {key: value for key, value in supplier_data_filtered.items() if value is not None}

        # Salvataggio nel DB
        try:
            self.db_model.add_supplier(**supplier_data_filtered)
            return True, "Fornitore salvato con successo!"
        except Exception as e:
            return False, f"Errore durante il salvataggio del fornitore: {str(e)}"

    def retrieve_suppliers(self):
        """Recupera tutti i suppliers."""
        return self.db_model.fetch_suppliers()

    def retrieve_supplier_by_id(self, supplier_id):
        """Recupera un supplier specifico per ID."""
        return self.db_model.fetch_supplier_by_id(supplier_id)

    def retrieve_supplier_by_name(self, supplier_name):
        """Recupera un supplier specifico per nome."""
        return self.db_model.fetch_supplier_by_name(supplier_name)

    def retrieve_supplier_map_by_name(self, supplier_name):
        """Recupera un supplier specifico e lo restituisce come dizionario."""
        row = self.retrieve_supplier_by_name(supplier_name)
        return ValidationUtils._row_to_map(row, DBSuppliersColumns)

    def retrieve_supplier_map_by_id(self, supplier_id):
        """Recupera un supplier specifico e lo restituisce come dizionario."""
        row = self.db_model.fetch_supplier_by_id(supplier_id)
        return ValidationUtils._row_to_map(row, DBSuppliersColumns)

    def retrieve_suppliers_map_list(self):
        """Recupera tutti i suppliers e li restituisce come lista di dizionari."""
        rows = self.db_model.fetch_suppliers()
        return [ValidationUtils._row_to_map(row, DBSuppliersColumns) for row in rows]

    def retrieve_last_supplier_insert_map(self):
        """
        Recupera l'ultimo supplier inserito e lo restituisce come dizionario.
        """
        row = self.db_model.fetch_last_supplier_insert()
        return ValidationUtils._row_to_map(row, DBSuppliersColumns)

    def retrieve_supplier_with_expenses_map_list(self, supplier_id):
        """ Recupera lo specifico supplier unito alle rispettive spese e
           li restituisce come lista di dizionari.

           Utilizza la funzione fetch_supplier_with_expenses per ottenere le righe,
           quindi combina le colonne dei supplier e delle spese per convertire
           ogni riga in un dizionario tramite _row_to_map.
           """
        # Recupera le righe dal database per lo specifico client
        rows = self.db_model.fetch_supplier_with_expenses(supplier_id)

        all_columns = list(DBSuppliersColumns) + list(DBExpensesColumns)

        # Converte ogni riga in un dizionario
        return [ValidationUtils._row_to_map(row, all_columns) for row in rows]

    def delete_supplier_by_id(self, supplier_id):
        """Elimina un supplier dato il suo ID."""
        table = "suppliers"
        try:
            self.db_model.delete_row(table, DBSuppliersColumns.ID.value, supplier_id)
            print(f"Supplier {supplier_id} rimosso con successo")
            return True, f"Supplier {supplier_id} rimosso con successo"
        except Exception as e:
            return False, f"Errore durante l'eliminazione del supplier: {str(e)}"

    def construct_supplier_map_aggregate_data(self, supplier_id):
        supplier_aggregate_data = {
            SupplierController.Aggregate_data.TOT_SPESE.value: self.calcola_tot_spese_supplier(supplier_id),
            SupplierController.Aggregate_data.NUM_SPESE.value: self.calcola_numero_spese_supplier(supplier_id),
            SupplierController.Aggregate_data.MEDIA_SPESE.value: self.calcola_media_spese_supplier(supplier_id)
        }

        return supplier_aggregate_data

    def calcola_tot_spese_supplier(self, supplier_id):
        supplier_with_expenses = self.retrieve_supplier_with_expenses_map_list(supplier_id)
        tot = 0.0
        for row in supplier_with_expenses: #in questo modo sto in realtà scorrendo le fatture
            tot = tot + float(row[DBExpensesColumns.TOT_AMOUNT.value]) if row[DBExpensesColumns.TOT_AMOUNT.value] is not None else tot

        return tot

    def calcola_numero_spese_supplier(self, supplier_id):
        supplier_with_expenses = self.retrieve_supplier_with_expenses_map_list(supplier_id)
        tot = 0
        for row in supplier_with_expenses:
            tot = tot + 1

        return tot

    def calcola_media_spese_supplier(self, supplier_id):
        numero = self.calcola_numero_spese_supplier(supplier_id)
        tot = self.calcola_tot_spese_supplier(supplier_id)

        return tot/numero if numero > 0 else 0


class UpdatesController:

    def __init__(self, user_controller, client_controller, invoice_controller, payments_controller, account_controller, production_controller):
        self.user_controller = user_controller
        self.client_controller = client_controller
        self.invoice_controller = invoice_controller
        self.payments_controller = payments_controller
        self.account_controller = account_controller
        self.production_controller = production_controller

        self.on_adding_payment_view_cllbks = []
        self.on_adding_expense_view_cllbks = []
        self.on_adding_transfer_view_cllbks = []
        self.on_modify_invoice_view_cllbks = []
        self.on_delete_production_view_cllbks = []

    def update_invoices(self, invoice_id):
        #richiedo di updatare le liste in back
        self.invoice_controller.update_aggregated_data()
        self.invoice_controller.update_stato_fatture()

        #updato il frontend
        for callback in self.invoice_controller.on_updating_invoice_controller_callbacks:
            try:
                callback(invoice_id)
            except TypeError as e:
                callback()

    def launch_payment_warning(self, payment_name:str, warning:str):
        for cllbk in self.on_modify_invoice_view_cllbks:
            try:
                cllbk(payment_name, warning)
            except TypeError as e:
                cllbk()

    def register_on_adding_payment_view_cllbks(self, *callbacks):
        """
        Register within UpdateController some view callbacks to be called when a new payment is added to the DB.
        IMPORTANT: the callbacks have to be arguments free
        :param callbacks: the functions of views that update the widgets linked somehow with payment's data

        """
        self.on_adding_payment_view_cllbks = list(callbacks)

    def register_on_adding_expense_view_cllbks(self, *callbacks):
        """
        Register within UpdateController some view callbacks to be called when a new expense is added to the DB.
        IMPORTANT: the callbacks have to be arguments free
        :param callbacks: the functions of views that update the widgets linked somehow with expense's data

        """
        self.on_adding_expense_view_cllbks = list(callbacks)

    def register_on_adding_transfer_view_cllbks(self, *callbacks):
        """
        Register within UpdateController some view callbacks to be called when a new transfer is added to the DB.
        IMPORTANT: the callbacks have to be arguments free
        :param callbacks: the functions of views that update the widgets linked somehow with expense's data

        """
        self.on_adding_transfer_view_cllbks = list(callbacks)

    def register_on_modify_invoice_view_cllbks(self, *callbacks):
        self.on_modify_invoice_view_cllbks = list(callbacks)

    def register_on_delete_production_view_cllbks(self, *callbacks):
        self.on_delete_production_view_cllbks = list(callbacks)

    def on_adding_payment(self):
        for callback in self.on_adding_payment_view_cllbks:
            try:
                callback()
            except TypeError as e:
                print("ERRORE: on_adding_payment_view_cllbks contiene una callback non idonea in quanto vuole un argomento")

    def on_adding_expense(self):
        for callback in self.on_adding_expense_view_cllbks:
            try:
                callback()
            except TypeError as e:
                print("ERRORE: on_adding_expense_view_cllbks contiene una callback non idonea in quanto vuole un argomento")

    def on_adding_transfer(self):
        for callback in self.on_adding_transfer_view_cllbks:
            try:
                callback()
            except TypeError as e:
                print(f"ERRORE: {str(e)}")


class SalaryController:

    class SalariesAggregateData(Enum):
        NUMERO_SALARI = "#SALARI"
        TOT_SALARI = "TOT. SALARI"

    def __init__(self, db_model, user_controller, account_controller):
        self.db_model = db_model
        self.user_controller = user_controller
        self.account_controller = account_controller

    def save_salary(self, salary_data):
        """
        Gestisce il salvataggio di un salario, con validazioni di primo livello.
        :param salary_data: Dizionario contenente i dati del salario
        :return: Tuple (success, message), dove success è True/False
        """

        # Campi obbligatori (solo quelli modellati tramite entry)
        self.required_fields = {DBSalariesColumns.NAME.value, DBSalariesColumns.AMOUNT.value}

        # Validazione dei campi obbligatori
        missing_fields = [field for field in self.required_fields if not salary_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        # Validazione importi
        importo = salary_data.get(DBSalariesColumns.AMOUNT.value)
        if not ValidationUtils.validate_amount(importo):
            return False, "L'importo non è valido"

        #prendo ID Utente
        user_id = None
        user_name = salary_data.get("NOME UTENTE")
        if len(user_name.split(" ")) >= 2: #se è un nome di un utente vero allora è Nome Cognome
            user_first = user_name.split(" ")[0]
            user_last = user_name.split(" ")[1]
            user = self.user_controller.retrieve_user_map_by_fullname(user_first, user_last)
            user_id = user[DBUsersColumns.ID.value]

        #prendo ID conto
        conto_id = None
        conto_name = salary_data.get("CONTO")
        if conto_name:
            conto = self.account_controller.retrieve_account_map_by_name(conto_name)
            conto_id = conto[DBAccountsColumns.ID.value]


        salary_data_prepared = {
            DBSalariesColumns.NAME.value: salary_data.get(DBSalariesColumns.NAME.value),
            DBSalariesColumns.USER_ID.value: user_id,
            DBSalariesColumns.DATE.value: salary_data.get(DBSalariesColumns.DATE.value),
            DBSalariesColumns.AMOUNT.value: salary_data.get(DBSalariesColumns.AMOUNT.value),
            DBSalariesColumns.ACCOUNT_ID.value: conto_id
        }

        try:
            self.db_model.add_salary(**salary_data_prepared)
            return True, "Salario salvato con successo!"
        except Exception as e:
            return False, f"Errore durante il salvataggio: {str(e)}"

    def retrieve_salaries(self, current_year: bool = True) -> list[tuple]:
        """
        Recupera tutte le tuple dei versamenti-salario dalla tabella.
        :return: Lista di tuple.
        """
        rows = self.db_model.fetch_all_salaries()
        return rows

    def retrieve_salary_by_id(self, salary_id: int) -> tuple | None:
        """
        Recupera una tupla del versamento specifico per ID.
        :param salary_id: ID del versamento.
        :return: Tupla con i dati del versamento oppure None.
        """
        row = self.db_model.fetch_salary_by_id(salary_id)
        return row

    def retrieve_salary_map_by_name(self, salary_name: str) -> dict | None:
        """
        Recupera un versamento-salario specifico tramite il suo nome e lo restituisce come dizionario.
        :param salary_name: il nome del versamento-salario (campo NAME nella tabella).
        :return: dizionario con i dati del versamento oppure None se non trovato.
        """
        row = self.db_model.fetch_salary_by_name(salary_name)
        if not row:
            return None
        return ValidationUtils._row_to_map(row, DBSalariesColumns)

    def retrieve_salary_map_by_id(self, salary_id: int) -> dict | None:
        """
        Recupera un versamento specifico per ID e lo restituisce come dizionario.
        :param salary_id: ID del versamento.
        :return: Dizionario con i dati del versamento oppure None.
        """
        row = self.db_model.fetch_salary_by_id(salary_id)
        return ValidationUtils._row_to_map(row, DBSalariesColumns)

    def retrieve_salaries_map_list(self, current_year: bool = True) -> list[dict]:
        """
        Recupera tutti i versamenti come lista di dizionari,
        filtrandoli per l'anno corrente se specificato.

        :param current_year: Se True, filtra i versamenti per l'anno corrente
        :return: Lista di dizionari con i dati dei versamenti
        """
        rows = self.db_model.fetch_all_salaries()
        # Converti le tuple in dizionari
        salaries = [ValidationUtils._row_to_map(row, DBSalariesColumns) for row in rows]

        # Applica il filtro usando il metodo statico
        return ControllerUtils.filter_salaries(salaries, current_year)

    def retrieve_last_salary_insert_map(self) -> dict | None:
        """
        Recupera l'ultimo versamento inserito come dizionario.
        :return: Dizionario con i dati dell'ultimo versamento oppure None.
        """
        row = self.db_model.fetch_last_salary_insert()
        return ValidationUtils._row_to_map(row, DBSalariesColumns)

    def count_salaries(self, current_year: bool = True) -> int:
        """
        Conta il numero di versamenti-salario, applicando il filtro per l'anno corrente se specificato.

        :param current_year: Se True, conta solo le salaries dell'anno corrente.
        :return: Numero di salaries (int).
        """
        salaries = self.retrieve_salaries_map_list(current_year=current_year)
        return len(salaries)

    def calculate_tot_salaries(self, current_year: bool = True) -> float:
        """
        Calcola il totale degli importi dei versamenti-salario, filtrandoli per l'anno corrente se specificato.

        :param current_year: Se True, somma solo le salaries dell'anno corrente.
        :return: Totale degli importi (float).
        """
        total = 0.0
        salary_list = self.retrieve_salaries_map_list(current_year=current_year)
        for sal in salary_list:
            total += float(sal[DBSalariesColumns.AMOUNT.value])
        return total

    def sum_salaries_for_account(self, account_id):
        return self.db_model.sum_salaries_by_account(account_id)


class RefundController:

    class RefundsAggregateData(Enum):
        NUMERO_RIMBORSI = "#RIMBORSI"
        TOT_RIMBORSI = "TOT. RIMBORSI"

    def __init__(self, db_model, client_controller, account_controller):
        self.db_model = db_model
        self.client_controller = client_controller
        self.account_controller = account_controller

    def save_refund(self, refund_data):
        """
        Gestisce il salvataggio di un rimborso, con validazioni di primo livello.
        :param refund_data: Dizionario contenente i dati del rimborso
        :return: Tuple (success, message), dove success è True/False
        """

        # Campi obbligatori (solo quelli modellati tramite entry)
        self.required_fields = {DBRefundsColumns.REFUND_NAME.value, DBRefundsColumns.REFUND_AMOUNT.value}

        # Validazione dei campi obbligatori
        missing_fields = [field for field in self.required_fields if not refund_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        # Validazione importi
        tot_refund = refund_data.get(DBRefundsColumns.REFUND_AMOUNT.value)
        if not ValidationUtils.validate_amount(tot_refund):
            return False, "L'importo del preventivo non è valido"

        # prendo i dati necessari del conto
        nome_conto = refund_data.get("NOME CONTO")
        conto = self.account_controller.retrieve_account_map_by_name(nome_conto)
        id_conto = conto[DBAccountsColumns.ID.value]

        # prendo i dati necessari del cliente
        nome_cliente = refund_data.get("NOME CLIENTE")
        cliente = self.client_controller.retrieve_client_map_by_name(nome_cliente)
        id_cliente = cliente[DBClientsColumns.ID.value]


        refund_data_prepared = {
            DBRefundsColumns.REFUND_NAME.value : refund_data.get(DBRefundsColumns.REFUND_NAME.value),
            DBRefundsColumns.REFUND_AMOUNT.value: refund_data.get(DBRefundsColumns.REFUND_AMOUNT.value),
            DBRefundsColumns.REFUND_DATE.value: refund_data.get(DBRefundsColumns.REFUND_DATE.value),
            DBRefundsColumns.CLIENT_ID.value : id_cliente,
            DBPaymentsColumns.CONTO_ID.value: id_conto,
        }

        try:
            self.db_model.add_refund(**refund_data_prepared)
            return True, "Rimborso salvato con successo!"
        except Exception as e:
            return False, f"Errore durante il salvataggio: {str(e)}"

    def update_refund(self, refund_id, refund_data):
        """
        Aggiorna i dati di un rimborso esistente.
        :param refund_id: ID del rimborso da aggiornare
        :param refund_data: Dizionario contenente i dati da aggiornare
        :return: Tuple (success, message), dove success è True/False
        """
        try:
            # Controllo validità refund_id
            if not refund_id or not isinstance(refund_id, int):
                return False, "ID rimborso non valido. Deve essere un intero positivo."

            required_fields = {DBRefundsColumns.REFUND_NAME.value, DBRefundsColumns.REFUND_AMOUNT.value}

            # Validazione campi obbligatori
            missing_fields = [field for field in required_fields if not refund_data.get(field)]
            if missing_fields:
                return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

            # Validazione Importo
            if DBRefundsColumns.REFUND_AMOUNT.value in refund_data:
                amount = refund_data[DBRefundsColumns.REFUND_AMOUNT.value]
                if amount and not ValidationUtils.validate_amount(amount):
                    return False, "L'importo inserito non è valido."

            refund_data[DBRefundsColumns.UPDATED_AT.value] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Invoca il metodo del model per aggiornare l'utente
            self.db_model.update_refund(refund_id, **refund_data)
            return True, "Rimborso aggiornato con successo!"

        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento del rimborso: {str(e)}"

    def delete_refund(self, refund_id):
        return self.db_model.remove_refund(refund_id)

    def retrieve_refunds(self, current_year=True):
        """
        Recupera tutti i rimborsi, filtrandoli per l'anno corrente se specificato.
        :param current_year: Booleano. Se True, ritorna solo i rimborsi effettuati nell'anno corrente.
        :return: Lista di tuple (righe) con i dati dei rimborsi.
        """
        rows = self.db_model.fetch_refunds()
        if not current_year or not rows:
            return rows

        columns = [col.value for col in DBRefundsColumns]
        # Converti le righe in dizionari
        refunds_dicts = [dict(zip(columns, row)) for row in rows]
        # Applica il filtro utilizzando ControllerUtils
        filtered_dicts = ControllerUtils.filter_refunds(refunds_dicts, current_year)
        # Converti i dizionari filtrati nuovamente in tuple
        return [tuple(d[col] for col in columns) for d in filtered_dicts]

    def retrieve_refund_by_id(self, refund_id, current_year=True):
        """
        Recupera un rimborso specifico per ID, opzionalmente filtrando per l'anno corrente.
        :param refund_id: ID del rimborso.
        :param current_year: Se True, ritorna None se il rimborso non è dell'anno corrente.
        :return: Una tupla con i dati del rimborso oppure None.
        """
        row = self.db_model.fetch_refund_by_id(refund_id)
        if not row or not current_year:
            return row

        columns = [col.value for col in DBRefundsColumns]
        refund_dict = dict(zip(columns, row))
        # Applica il filtro utilizzando ControllerUtils
        if ControllerUtils.filter_refunds([refund_dict], current_year):
            return row
        return None

    def retrieve_refund_map_by_id(self, refund_id, current_year=True):
        """
        Recupera un rimborso specifico e lo restituisce come dizionario,
        filtrando per l'anno corrente se specificato.
        :param refund_id: ID del rimborso.
        :param current_year: Se True, ritorna None se il rimborso non è dell'anno corrente.
        :return: Dizionario con i dati del rimborso oppure None.
        """
        row = self.db_model.fetch_refund_by_id(refund_id)
        if not row:
            return None

        columns = [col.value for col in DBRefundsColumns]
        refund_dict = dict(zip(columns, row))

        # Applica il filtro se necessario
        if current_year and not ControllerUtils.filter_refunds([refund_dict], current_year):
            return None

        return refund_dict

    def retrieve_refunds_map_list(self, current_year=True):
        """
        Recupera tutti i rimborsi e li restituisce come lista di dizionari,
        filtrandoli per l'anno corrente se specificato.
        """
        rows = self.db_model.fetch_refunds()
        # Converti le righe in dizionari
        refunds = [ValidationUtils._row_to_map(row, DBRefundsColumns) for row in rows]

        # Applica il filtro utilizzando ControllerUtils
        if current_year:
            refunds = ControllerUtils.filter_refunds(refunds, current_year)

        return refunds

    def retrieve_refunds_map_list_by_client_id(self, client_id, current_year=True):
        """
        Recupera i rimborsi per un specifico cliente, opzionalmente filtrati per anno corrente.
        """
        rows = self.db_model.fetch_refunds_by_client_id(client_id)
        # Converti le righe in dizionari
        refunds = [ValidationUtils._row_to_map(row, DBRefundsColumns) for row in rows]

        # Applica il filtro utilizzando ControllerUtils
        if current_year:
            refunds = ControllerUtils.filter_refunds(refunds, current_year)

        return refunds

    def retrieve_last_refund_insert_map(self):
        """
        Recupera l'ultimo rimborso inserito e lo restituisce come dizionario.
        """
        row = self.db_model.fetch_last_refund_insert()
        return ValidationUtils._row_to_map(row, DBRefundsColumns)

    def count_refunds(self, current_year=True):
        """
        Conta il numero di rimborsi, applicando il filtro per l'anno corrente se specificato.

        :param current_year: Booleano. Se True, conta solo i rimborsi dell'anno corrente.
        :return: Numero di rimborsi (int)
        """
        # Usa retrieve_refunds_map_list già modificata
        refunds = self.retrieve_refunds_map_list(current_year)
        return len(refunds)

    def calculate_tot_refunds(self, current_year=True):
        """
        Calcola il totale degli importi dei rimborsi.
        """
        refund_list = self.retrieve_refunds_map_list(current_year)
        tot = 0.0
        for refund in refund_list:
            tot = tot + float(refund[DBRefundsColumns.REFUND_AMOUNT.value])
        return tot

    def calculate_tot_refunds_of_client(self, client_id, current_year=True):
        """
        Calcola il totale degli importi dei rimborsi.
        """
        refund_list = self.retrieve_refunds_map_list_by_client_id(current_year, client_id)
        tot = 0.0
        for refund in refund_list:
            tot = tot + float(refund[DBRefundsColumns.REFUND_AMOUNT.value])
        return tot


    def update_refund(self, refund_id, refund_data):
        """
        Aggiorna i dati di un rimborso esistente.
        :param refund_id: ID del rimborso da aggiornare
        :param refund_data: Dizionario contenente i dati da aggiornare
        :return: Tuple (success, message), dove success è True/False
        """
        try:
            # Controllo validità refund_id
            if not refund_id or not isinstance(refund_id, int):
                return False, "ID rimborso non valido. Deve essere un intero positivo."

            # Validazione campi obbligatori (da definire in base ai requisiti)
            required_fields = [
                DBRefundsColumns.REFUND_NAME.value,
                DBRefundsColumns.REFUND_AMOUNT.value,
                DBRefundsColumns.REFUND_DATE.value,
                DBRefundsColumns.CLIENT_ID.value,
                DBRefundsColumns.CONTO_ID.value
            ]

            missing_fields = [field for field in required_fields if not refund_data.get(field)]
            if missing_fields:
                return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

            # Validazione Importo
            if DBRefundsColumns.REFUND_AMOUNT.value in refund_data:
                amount = refund_data[DBRefundsColumns.REFUND_AMOUNT.value]
                if amount and not ValidationUtils.validate_amount(amount):
                    return False, "L'importo inserito non è valido."

            # Invoca il metodo del model per aggiornare il rimborso
            self.db_model.update_refund(refund_id, **refund_data)
            return True, "Rimborso aggiornato con successo!"

        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento del rimborso: {str(e)}"

    def sum_refunds_for_account(self, account_id):
        """
        Restituisce la somma totale dei rimborsi associati a un conto specifico.

        :param account_id: ID del conto
        :return: Somma degli importi dei rimborsi (float)
        """
        return self.db_model.sum_refunds_by_account(account_id)




class Analyzer:
    def __init__(self,
                 user_controller,
                 client_controller,
                 account_controller,
                 invoice_controller,
                 transfer_controller,
                 supplier_controller,
                 production_controller,
                 payment_controller,
                 expenses_controller,
                 salary_controller,
                 refunds_controller,
                 fiscal_settings,
                 recurring_expenses_settings
                 ):
        self.user_controller = user_controller
        self.client_controller = client_controller
        self.account_controller = account_controller
        self.invoice_controller = invoice_controller
        self.transfer_controller = transfer_controller
        self.supplier_controller = supplier_controller
        self.production_controller = production_controller
        self.payment_controller = payment_controller
        self.expenses_controller = expenses_controller
        self.salary_controller = salary_controller
        self.refunds_controller = refunds_controller
        self.fiscal_settings = fiscal_settings
        self.recurring_expenses_settings = recurring_expenses_settings

    def calculate_account_balance_by_account_id(self, account_id):
        account = self.account_controller.retrieve_account_map_by_id(account_id)
        balance = 0.0
        if account:
            init_balance = float(account[DBAccountsColumns.INIT_BALANCE.value])

            tot_payments = self.payment_controller.sum_payments_for_account(account_id)
            tot_expenses = self.expenses_controller.sum_expenses_for_account(account_id)
            tot_rec_transf = self.transfer_controller.calculate_tot_amount_received_transfers_by_account(account_id)
            tot_sent_transf = self.transfer_controller.calculate_tot_amount_sent_transfers_by_account(account_id)
            tot_salaries = self.salary_controller.sum_salaries_for_account(account_id)
            tot_refunds = self.refunds_controller.sum_refunds_for_account(account_id)

            tot_entrate = tot_payments + tot_rec_transf + tot_refunds
            tot_uscite = tot_expenses + tot_sent_transf + tot_salaries

            balance = init_balance + float(tot_entrate) - float(tot_uscite)

        return balance

    def calculate_trimestral_iva_by_account_id(self, account_id):
        # Dizionario di output con i trimestri
        output_dict = {
            "Gen-Marz": {"debito": 0.0, "credito": 0.0, "da_pagare": 0.0},
            "Apr-Giu": {"debito": 0.0, "credito": 0.0, "da_pagare": 0.0},
            "Lug-Sett": {"debito": 0.0, "credito": 0.0, "da_pagare": 0.0},
            "Ott-Dic": {"debito": 0.0, "credito": 0.0, "da_pagare": 0.0}
        }

        # Funzione per determinare il trimestre da un mese
        def get_trimestre(month):
            if 1 <= month <= 3:
                return "Gen-Marz"
            elif 4 <= month <= 6:
                return "Apr-Giu"
            elif 7 <= month <= 9:
                return "Lug-Sett"
            else:
                return "Ott-Dic"

        # Recupera le spese deducibili e le fatture
        deducted_expenses = self.user_controller.retrieve_user_with_deducted_expenses_map_list(account_id)
        invoices = self.user_controller.retrieve_user_with_invoices_map_list(account_id)
        invoices = self.invoice_controller.clear_invoices_list_from_NDC_and_stornate(invoices)

        # Elabora le spese (IVA a credito)
        for e in deducted_expenses:
            date_str = e.get(DBExpensesColumns.DATE.value)
            if date_str:
                try:
                    # Converti la stringa in data ed estrai il mese
                    expense_date = datetime.strptime(date_str, "%Y-%m-%d")
                    trimestre = get_trimestre(expense_date.month)

                    # Somma l'IVA a credito
                    iva_amount = float(e.get(DBExpensesColumns.IVA_AMOUNT.value, 0))
                    output_dict[trimestre]["credito"] += iva_amount
                except (ValueError, TypeError):
                    # Gestisci errori di conversione
                    continue

        # Elabora le fatture (IVA a debito)
        for i in invoices:
            date_str = i.get(DBInvoicesColumns.DATA_CREAZIONE.value)
            if date_str:
                try:
                    # Converti la stringa in data e estrai il mese
                    invoice_date = datetime.strptime(date_str, "%Y-%m-%d")
                    trimestre = get_trimestre(invoice_date.month)

                    # Somma l'IVA a debito
                    iva_amount = float(i.get(DBInvoicesColumns.IVA.value, 0))
                    output_dict[trimestre]["debito"] += iva_amount
                except (ValueError, TypeError):
                    # Gestisci errori di conversione
                    continue

        # Calcola l'IVA da pagare per ogni trimestre
        for trimestre, valori in output_dict.items():
            valori["da_pagare"] = valori["debito"] - valori["credito"]

        return output_dict

    def calculate_tot_trimestral_iva(self):
        output_map = {}

        for user in self.user_controller.retrieve_users_map_list():
            if user[DBUsersColumns.REGIME_FISCALE.value] == UserController.RegimeFiscale.ORDINARIO.value:
                user_name = user[DBUsersColumns.FIRST_NAME.value] + " " + user[DBUsersColumns.LAST_NAME.value]
                user_id = user[DBUsersColumns.ID.value]
                output_map[user_name] = self.calculate_trimestral_iva_by_account_id(user_id)

        return output_map

    def calculate_previsione_tasse_forfettaria(self, user_id):
        user = self.user_controller.retrieve_user_map_by_id(user_id)
        reddito_esterno = 0.0
        fatturato_willow = 0.0
        if user:
            reddito_esterno = float(user[DBUsersColumns.REDDITO_ESTERNO.value])
            fatturato_willow = self.user_controller.calcola_tot_fatturato_utente(user_id)
            anno_apertura = int(user[DBUsersColumns.ANNO_APERTURA_PIVA.value])
        else:
            return

        # Recupero impostazioni fiscali
        forfettaria_settings = self.fiscal_settings.partita_iva_forfettaria
        perc_acc_imp_primo = float(forfettaria_settings.percentuale_acconto_imposta_primo)
        perc_acc_imp_secondo = float(forfettaria_settings.percentuale_acconto_imposta_secondo)
        perc_acc_inps = float(forfettaria_settings.percentuale_acconto_inps_forfettario)
        perc_rata_inps = float(forfettaria_settings.percentuale_rata_acconto_inps_forfettario)

        # Recupero anticipo anno precedente
        acconto_anno_precedente_IRPEF = float(user.get(DBUsersColumns.LAST_YEAR_IRPEF_ACCONTO.value, 0.0))
        acconto_anno_precedente_INPS = float(user.get(DBUsersColumns.LAST_YEAR_INPS_ACCONTO.value, 0.0))
        acconto_anno_precedente = acconto_anno_precedente_IRPEF + acconto_anno_precedente_INPS

        # Calcolo valori base
        coefficiente_imponibile = float(forfettaria_settings.imponibile)
        aliquota_inps = float(forfettaria_settings.aliquota_inps)
        aliquota_irpef = float(self.user_controller.calcola_aliquota_tax_forfettaria(
            int(datetime.today().date().year) - anno_apertura
        ))

        # Calcolo reddito imponibile
        reddito_willow = fatturato_willow * coefficiente_imponibile
        reddito_tot = reddito_willow + reddito_esterno

        # Calcolo tasse
        irpef = reddito_tot * aliquota_irpef
        inps = reddito_tot * aliquota_inps
        totale_tasse = inps + irpef

        # Calcolo saldo corrente (tasse totali - acconto anno precedente)
        saldo_corrente = max(0, totale_tasse - acconto_anno_precedente)

        # Calcolo quote Willow
        quota_willow = reddito_willow / reddito_tot if reddito_tot > 0 else 0
        irpef_w = irpef * quota_willow
        inps_w = inps * quota_willow
        tasse_willow = inps_w + irpef_w
        saldo_willow = saldo_corrente * quota_willow

        # Calcolo acconti per l'anno successivo
        # IRPEF
        primo_acconto_irpef = irpef * perc_acc_imp_primo
        secondo_acconto_irpef = irpef * perc_acc_imp_secondo

        # INPS
        acconto_inps_totale = inps * perc_acc_inps
        primo_acconto_inps = acconto_inps_totale * perc_rata_inps
        secondo_acconto_inps = acconto_inps_totale - primo_acconto_inps

        # Calcolo totale acconti
        acconto_totale = (primo_acconto_irpef + secondo_acconto_irpef +
                          primo_acconto_inps + secondo_acconto_inps)
        acconto_willow = acconto_totale * quota_willow

        # Calcolo totale per scadenza
        primo_acconto_totale = primo_acconto_irpef + primo_acconto_inps
        secondo_acconto_totale = secondo_acconto_irpef + secondo_acconto_inps

        # Ripartizione per Willow
        primo_acconto_willow = primo_acconto_totale * quota_willow
        secondo_acconto_willow = secondo_acconto_totale * quota_willow

        # Mappa versamenti (saldo e acconti)
        versamenti_map = {
            "SALDO TOTALE": round(saldo_corrente, 2),
            "ACCONTO TOTALE": round(acconto_totale, 2),
            "SALDO WILLOW": round(saldo_willow, 2),
            "ACCONTO WILLOW": round(acconto_willow, 2)
        }

        # Output map per tooltip e dettagli
        output_map = {
            # Informazioni di base
            "FATTURATO_WILLOW": round(fatturato_willow, 2),
            "REDDITO_ESTERNO": round(reddito_esterno, 2),
            "COEFFICIENTE_IMPONIBILE": coefficiente_imponibile,
            "ALIQUOTA_INPS": aliquota_inps,
            "ALIQUOTA_IRPEF": aliquota_irpef,
            "PERC_ACC_IMP_PRIMO": perc_acc_imp_primo,
            "PERC_ACC_IMP_SECONDO": perc_acc_imp_secondo,
            "PERC_ACC_INPS": perc_acc_inps,
            "PERC_RATA_INPS": perc_rata_inps,

            # Calcoli intermedi
            "REDDITO_WILLOW": round(reddito_willow, 2),
            "REDDITO_TOT": round(reddito_tot, 2),
            "QUOTA_WILLOW": quota_willow,

            # Totali tasse
            "INPS": round(inps, 2),
            "IRPEF": round(irpef, 2),
            "TOTALE_TASSE": round(totale_tasse, 2),
            "INPS WILLOW": round(inps_w, 2),
            "IRPEF WILLOW": round(irpef_w, 2),
            "TASSE_WILLOW": round(tasse_willow, 2),

            # Anticipo anno precedente
            "ACCONTO_ANNO_PRECEDENTE": round(acconto_anno_precedente, 2),
            "ACCONTO_ANNO_PRECEDENTE_IRPEF": round(acconto_anno_precedente_IRPEF, 2),
            "ACCONTO_ANNO_PRECEDENTE_INPS": round(acconto_anno_precedente_INPS, 2),

            # Saldi
            "SALDO_CORRENTE": round(saldo_corrente, 2),
            "SALDO_WILLOW": round(saldo_willow, 2),

            # Acconti anno successivo
            "ACCONTO_TOTALE": round(acconto_totale, 2),
            "ACCONTO_WILLOW": round(acconto_willow, 2),
            "PRIMO_ACCONTO_TOTALE": round(primo_acconto_totale, 2),
            "SECONDO_ACCONTO_TOTALE": round(secondo_acconto_totale, 2),
            "PRIMO_ACCONTO_WILLOW": round(primo_acconto_willow, 2),
            "SECONDO_ACCONTO_WILLOW": round(secondo_acconto_willow, 2),
            "PRIMO_ACCONTO_IRPEF": round(primo_acconto_irpef, 2),
            "SECONDO_ACCONTO_IRPEF": round(secondo_acconto_irpef, 2),
            "PRIMO_ACCONTO_INPS": round(primo_acconto_inps, 2),
            "SECONDO_ACCONTO_INPS": round(secondo_acconto_inps, 2),
            "PRIMO_ACCONTO_IRPEF_WILLOW": round(primo_acconto_irpef * quota_willow, 2),
            "SECONDO_ACCONTO_IRPEF_WILLOW": round(secondo_acconto_irpef * quota_willow, 2),
            "PRIMO_ACCONTO_INPS_WILLOW": round(primo_acconto_inps * quota_willow, 2),
            "SECONDO_ACCONTO_INPS_WILLOW": round(secondo_acconto_inps * quota_willow, 2)
        }

        # Output principale
        return {
            "INPS": round(inps, 2),
            "IRPEF": round(irpef, 2),
            "IRPEF WILLOW": round(irpef_w, 2),
            "INPS WILLOW": round(inps_w, 2)
        }, versamenti_map, output_map

    def calculate_previsione_tasse_ordinaria(self, user_id):
        user = self.user_controller.retrieve_user_map_by_id(user_id)
        if not user:
            return {}

        # Recupero dati utente
        reddito_esterno = float(user.get(DBUsersColumns.REDDITO_ESTERNO.value, 0.0))
        spese_esterne = float(user.get(DBUsersColumns.SPESE_DEDOTTE_ESTERNE.value, 0.0))
        fatturato_willow = self.user_controller.calcola_tot_fatturato_utente(user_id)
        spese_willow = self.user_controller.calcola_tot_spese_utente_dedotte(user_id)
        tot_ritenuta = self.user_controller.calcola_tot_ritenuta_acconto_ordinaria(user_id)
        acconto_anno_precedente_IRPEF = float(user.get(DBUsersColumns.LAST_YEAR_IRPEF_ACCONTO.value, 0.0))
        acconto_anno_precedente_INPS = float(user.get(DBUsersColumns.LAST_YEAR_INPS_ACCONTO.value, 0.0))
        acconto_anno_precedente = acconto_anno_precedente_IRPEF + acconto_anno_precedente_INPS

        # Recupero impostazioni fiscali
        ordinaria_settings = self.fiscal_settings.partita_iva_ordinaria
        aliquota_inps = float(ordinaria_settings.aliquota_inps)
        scaglioni = ordinaria_settings.scaglioni_irpef
        perc_acc_irpef_primo = float(ordinaria_settings.percentuale_acconto_irpef_primo)
        perc_acc_irpef_secondo = float(ordinaria_settings.percentuale_acconto_irpef_secondo)
        perc_acc_inps = float(ordinaria_settings.percentuale_acconto_inps)
        perc_rata_inps = float(ordinaria_settings.percentuale_rata_acconto_inps)

        # 1. Calcolo scenario completo (con Willow)
        ricavi_totali = fatturato_willow + reddito_esterno
        spese_totali = spese_willow + spese_esterne
        reddito_netto_completo = ricavi_totali - spese_totali
        inps_completo = reddito_netto_completo * aliquota_inps
        base_irpef_completo = reddito_netto_completo - inps_completo
        irpef_lorda_completo = self._calcola_irpef(base_irpef_completo, scaglioni)
        irpef_netta_completo = irpef_lorda_completo - tot_ritenuta

        # 2. Calcolo scenario senza Willow
        reddito_netto_senza_willow = reddito_esterno - spese_esterne
        inps_senza_willow = reddito_netto_senza_willow * aliquota_inps
        base_irpef_senza_willow = reddito_netto_senza_willow - inps_senza_willow
        irpef_lorda_senza_willow = self._calcola_irpef(base_irpef_senza_willow, scaglioni)

        # 3. Calcolo della differenza di scaglione
        scaglione_max_senza_willow = 0
        for scaglione in sorted(scaglioni, key=lambda x: float(x.reddito_min)):
            if base_irpef_senza_willow > float(scaglione.reddito_min):
                scaglione_max_senza_willow = float(scaglione.reddito_min)

        # 4. Calcolo IRPEF attribuibile a Willow
        if base_irpef_senza_willow > 0:
            base_comune = min(base_irpef_completo, base_irpef_senza_willow)
            irpef_comune = self._calcola_irpef(base_comune, scaglioni)
            proporzione_comune = base_irpef_senza_willow / base_irpef_completo if base_irpef_completo > 0 else 0
        else:
            irpef_comune = 0
            proporzione_comune = 0

        base_aggiuntiva = max(0, base_irpef_completo - base_irpef_senza_willow)
        irpef_aggiuntiva = irpef_lorda_completo - irpef_lorda_senza_willow

        quota_willow_base = (fatturato_willow - spese_willow) / (ricavi_totali - spese_totali) if (ricavi_totali - spese_totali) > 0 else 0
        irpef_willow = (irpef_comune * quota_willow_base) + irpef_aggiuntiva
        reddito_netto_willow = fatturato_willow - spese_willow
        inps_willow = (reddito_netto_willow / reddito_netto_completo) * inps_completo if reddito_netto_completo > 0 else 0

        # 5. Calcolo tasse totali
        totale_tasse = inps_completo + max(0, irpef_netta_completo)
        tasse_willow = inps_willow + max(0, irpef_willow - tot_ritenuta)
        tasse_non_willow = totale_tasse - tasse_willow

        # 6. Calcolo versamenti (saldo e acconti)
        # Ripartizione proporzionale acconto precedente
        if totale_tasse > 0:
            prop_willow = tasse_willow / totale_tasse
            prop_non_willow = tasse_non_willow / totale_tasse
        else:
            prop_willow = prop_non_willow = 0.0

        # Calcolo saldo corrente
        saldo_corrente = max(0, totale_tasse - acconto_anno_precedente)
        saldo_willow = saldo_corrente * prop_willow
        saldo_non_willow = saldo_corrente * prop_non_willow

        # Calcolo nuovo acconto per l'anno successivo
        acconto_inps = inps_completo * perc_acc_inps
        acconto_irpef = max(0, irpef_netta_completo) * 1.0  # 100% per IRPEF

        # Ripartizione proporzionale acconto
        acconto_totale = acconto_inps + acconto_irpef
        acconto_willow = acconto_totale * prop_willow
        acconto_non_willow = acconto_totale * prop_non_willow

        # Rate acconto INPS
        rata_inps = acconto_inps * perc_rata_inps
        rata_inps_willow = rata_inps * prop_willow
        rata_inps_non_willow = rata_inps * prop_non_willow

        # Rate acconto IRPEF
        rata_irpef_primo = acconto_irpef * perc_acc_irpef_primo
        rata_irpef_secondo = acconto_irpef * perc_acc_irpef_secondo

        rata_irpef_primo_willow = rata_irpef_primo * prop_willow
        rata_irpef_primo_non_willow = rata_irpef_primo * prop_non_willow
        rata_irpef_secondo_willow = rata_irpef_secondo * prop_willow
        rata_irpef_secondo_non_willow = rata_irpef_secondo * prop_non_willow

        # Calcolo totale per scadenza (giugno e novembre)
        totale_giugno = saldo_corrente + rata_inps + rata_irpef_primo
        totale_giugno_willow = saldo_willow + rata_inps_willow + rata_irpef_primo_willow
        totale_giugno_non_willow = saldo_non_willow + rata_inps_non_willow + rata_irpef_primo_non_willow

        totale_novembre = rata_irpef_secondo
        totale_novembre_willow = rata_irpef_secondo_willow
        totale_novembre_non_willow = rata_irpef_secondo_non_willow

        # 7. Mappa versamenti (saldo e acconti)
        versamenti_map = {
            "SALDO TOTALE": round(saldo_corrente, 2),
            "ACCONTO TOTALE": round(acconto_totale, 2),
            "SALDO WILLOW": round(saldo_willow, 2),
            "ACCONTO WILLOW": round(acconto_willow, 2)
        }

        # 8. Output map per tooltip e dettagli
        output_map = {
            # Valori complessivi
            "REDDITO_NETTO": round(reddito_netto_completo, 2),
            "INPS": round(inps_completo, 2),
            "BASE_IRPEF": round(base_irpef_completo, 2),
            "IRPEF_LORDA": round(irpef_lorda_completo, 2),
            "RITENUTA": round(tot_ritenuta, 2),
            "IRPEF_NETTA": round(irpef_netta_completo, 2),
            "TOTALE_TASSE": round(totale_tasse, 2),
            "ALIQUOTA_INPS": round(aliquota_inps, 4),
            "PERC_ACCONTO_INPS": round(perc_acc_inps, 4),
            "PERC_RATA_INPS": round(perc_rata_inps, 4),
            "PERC_ACCONTO_IRPEF_PRIMO": round(perc_acc_irpef_primo, 4),
            "PERC_ACCONTO_IRPEF_SECONDO": round(perc_acc_irpef_secondo, 4),
            "ACCONTO_ANNO_PRECEDENTE": round(acconto_anno_precedente, 2),
            "SALDO_CORRENTE": round(saldo_corrente, 2),
            "ACCONTO_ANNO_SUCCESSIVO": round(acconto_totale, 2),
            "RATA_IRPEF_PRIMO": round(rata_irpef_primo, 2),
            "RATA_IRPEF_SECONDO": round(rata_irpef_secondo, 2),
            "RATA_INPS": round(rata_inps, 2),

            # Valori senza Willow
            "SENZA_WILLOW_REDDITO": round(reddito_netto_senza_willow, 2),
            "SENZA_WILLOW_BASE_IRPEF": round(base_irpef_senza_willow, 2),
            "SENZA_WILLOW_IRPEF": round(irpef_lorda_senza_willow, 2),

            # Ripartizione per Willow
            "WILLOW_IRPEF_BASE": round(irpef_comune * quota_willow_base, 2),
            "WILLOW_IRPEF_AGGIUNTIVA": round(irpef_aggiuntiva, 2),
            "WILLOW_IRPEF_TOT": round(irpef_willow, 2),
            "WILLOW_INPS": round(inps_willow, 2),
            "WILLOW_RITENUTA": round(tot_ritenuta, 2),
            "WILLOW_TASSE_TOT": round(tasse_willow, 2),
            "NON_WILLOW_TASSE_TOT": round(tasse_non_willow, 2),

            # Coefficienti
            "SCAGLIONE_MAX_SENZA_WILLOW": scaglione_max_senza_willow,
            "PROPORZIONE_COMUNE": round(proporzione_comune, 4),
            "QUOTA_WILLOW_BASE": round(quota_willow_base, 4),
            "PROP_WILLOW": round(prop_willow, 4),
            "PROP_NON_WILLOW": round(prop_non_willow, 4),

            "REDDITO_ESTERNO": round(reddito_esterno, 2),
            "RICAVI_TOTALI": round(ricavi_totali, 2),
            "SPESE_ESTERNE": round(spese_esterne, 2),
            "SPESE_TOTALI": round(spese_totali, 2),
            "REDDITO_NETTO_WILLOW": round(reddito_netto_willow, 2),
            "IRPEF_COMUNE": round(irpef_comune, 2),
            "BASE_AGGIUNTIVA": round(base_aggiuntiva, 2),
            "WILLOW_IRPEF_NETTA": round(max(0, irpef_willow - tot_ritenuta), 2),
            "FATTURATO_WILLOW": round(fatturato_willow, 2),
            "SPESE_WILLOW": round(spese_willow, 2),

            # Saldi
            "SALDO_TOTALE": round(saldo_corrente, 2),
            "SALDO_WILLOW": round(saldo_willow, 2),
            "SALDO_NON_WILLOW": round(saldo_non_willow, 2),

            # Acconti totali
            "ACCONTO_TOTALE": round(acconto_totale, 2),
            "ACCONTO_WILLOW": round(acconto_willow, 2),
            "ACCONTO_NON_WILLOW": round(acconto_non_willow, 2),

            # Rate INPS
            "RATA_INPS_WILLOW": round(rata_inps_willow, 2),
            "RATA_INPS_NON_WILLOW": round(rata_inps_non_willow, 2),

            # Rate IRPEF
            "RATA_IRPEF_PRIMO_WILLOW": round(rata_irpef_primo_willow, 2),
            "RATA_IRPEF_PRIMO_NON_WILLOW": round(rata_irpef_primo_non_willow, 2),
            "RATA_IRPEF_SECONDO_WILLOW": round(rata_irpef_secondo_willow, 2),
            "RATA_IRPEF_SECONDO_NON_WILLOW": round(rata_irpef_secondo_non_willow, 2),

            # Totali per scadenza
            "TOTALE_GIUGNO": round(totale_giugno, 2),
            "TOTALE_GIUGNO_WILLOW": round(totale_giugno_willow, 2),
            "TOTALE_GIUGNO_NON_WILLOW": round(totale_giugno_non_willow, 2),
            "TOTALE_NOVEMBRE": round(totale_novembre, 2),
            "TOTALE_NOVEMBRE_WILLOW": round(totale_novembre_willow, 2),
            "TOTALE_NOVEMBRE_NON_WILLOW": round(totale_novembre_non_willow, 2),

            # Date di scadenza
            "SCADENZA_GIUGNO": "30/06",
            "SCADENZA_NOVEMBRE": "30/11"
        }

        # 9. Preparazione risultati
        return {
            "INPS": round(inps_completo, 2),
            "IRPEF NETTA": round(irpef_netta_completo, 2),
            "WILLOW INPS": round(inps_willow, 2),
            "WILLOW IRPEF": round(max(0, irpef_willow - tot_ritenuta), 2)
        }, versamenti_map, output_map

    def calculate_previsione_tasse_willow(self):
        list_of_users = self.user_controller.retrieve_users_map_list()
        result_map = {}
        total_saldo_willow = 0.0
        total_acconto_willow = 0.0
        total_irpef_willow = 0.0
        total_inps_willow = 0.0

        for user in list_of_users:
            user_id = user[DBUsersColumns.ID.value]
            regime_fiscale = user[DBUsersColumns.REGIME_FISCALE.value]
            user_name = f"{user.get(DBUsersColumns.FIRST_NAME.value, '')} {user.get(DBUsersColumns.LAST_NAME.value, '')}"

            saldo_willow = 0.0
            acconto_willow = 0.0
            irpef_willow = 0.0
            inps_willow = 0.0

            try:
                if regime_fiscale == self.user_controller.RegimeFiscale.ORDINARIO.value:
                    tasse_map, versamenti, _ = self.calculate_previsione_tasse_ordinaria(user_id)
                    saldo_willow = versamenti.get("SALDO WILLOW", 0.0)
                    acconto_willow = versamenti.get("ACCONTO WILLOW", 0.0)
                    irpef_willow = tasse_map.get("WILLOW IRPEF", 0.0)
                    inps_willow = tasse_map.get("WILLOW INPS", 0.0)

                elif regime_fiscale == self.user_controller.RegimeFiscale.FORFETTARIO.value:
                    tasse_map, versamenti, _ = self.calculate_previsione_tasse_forfettaria(user_id)
                    saldo_willow = versamenti.get("SALDO WILLOW", 0.0)
                    acconto_willow = versamenti.get("ACCONTO WILLOW", 0.0)
                    irpef_willow = tasse_map.get("IRPEF WILLOW", 0.0)
                    inps_willow = tasse_map.get("INPS WILLOW", 0.0)

                # Aggiungi i valori dell'utente alla mappa
                result_map[user_name] = {
                    "SALDO WILLOW": saldo_willow,
                    "ACCONTO WILLOW": acconto_willow,
                    "IRPEF WILLOW": irpef_willow,
                    "INPS WILLOW": inps_willow
                }

                # Aggiorna i totali
                total_saldo_willow += saldo_willow
                total_acconto_willow += acconto_willow
                total_irpef_willow += irpef_willow
                total_inps_willow += inps_willow

            except Exception as e:
                print(f"Errore nel calcolo per l'utente {user_name} (ID: {user_id}): {str(e)}")
                result_map[user_name] = {
                    "SALDO WILLOW": 0.0,
                    "ACCONTO WILLOW": 0.0,
                    "IRPEF WILLOW": 0.0,
                    "INPS WILLOW": 0.0
                }

        # Aggiungi i totali alla mappa risultato
        result_map["TOTALE"] = {
            "SALDO WILLOW": total_saldo_willow,
            "ACCONTO WILLOW": total_acconto_willow,
            "IRPEF WILLOW": total_irpef_willow,
            "INPS WILLOW": total_inps_willow
        }

        return result_map

    def _calcola_irpef(self, imponibile, scaglioni):
        """Calcola l'IRPEF in base agli scaglioni di reddito"""
        if imponibile <= 0:
            return 0.0

        scaglioni_ordinati = sorted(scaglioni, key=lambda x: x.reddito_min)
        irpef = 0.0
        reddito_residuo = imponibile

        for scaglione in scaglioni_ordinati:
            if reddito_residuo <= 0:
                break

            # Calcola la parte di reddito nello scaglione
            if scaglione.reddito_max == float('inf'):
                parte_scaglione = reddito_residuo
            else:
                ammontare_scaglione = float(scaglione.reddito_max) - float(scaglione.reddito_min)
                parte_scaglione = min(reddito_residuo, ammontare_scaglione)

            # Applica l'aliquota marginale
            irpef += parte_scaglione * (float(scaglione.value))
            reddito_residuo -= parte_scaglione

        return irpef

    def calculate_totale_crediti(self, current_year=True):
        tot_fatture = self.invoice_controller.calculate_TOT_DOCUMENTO_invoiced(current_year)
        tot_ritenuta = self.invoice_controller.calculate_RITENUTA_ACCONTO_invoiced(current_year)
        tot_pagamenti = self.payment_controller.calculate_tot_payments(current_year)

        return round(tot_fatture - tot_ritenuta - tot_pagamenti, 2)







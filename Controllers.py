import re
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from enum import Enum

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
import hashlib

from Fatturazione_elettronica_API import FatturazioneElettronicaProvider

from Model import DatabaseModel, DBUsersColumns, DBClientsColumns, DBInvoicesColumns, \
DBPaymentsColumns, DBProductionsColumns, DBAccountsColumns, DBExpensesColumns, \
DBSuppliersColumns, DBTransfersColumns, DBSalariesColumns

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
        Calcola il reddito di un utente come somma delle fatture
        emesse nell'anno corrente, sfruttando il join user‑invoices.

        :param user_id: ID dell'utente
        :return: il reddito (float)
        """
        # Recupera l'utente + tutte le sue fatture
        rows = self.retrieve_user_with_invoices_map_list(user_id)
        if not rows:
            return 0.0

        # Estraggo il regime fiscale dall'utente (prendo il primo row)
        regime_utente = rows[0][DBUsersColumns.REGIME_FISCALE.value]

        # Calcolo l'anno corrente
        current_year = datetime.now().year

        reddito = 0.0
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
                reddito += float(tot)

        return reddito

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

    def reset_reddito_esterno(self):
        return

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

    def delete_client_by_id(self, client_id):
        """Elimina un cliente dato il suo ID."""
        table = "clients"
        try:
            self.db_model.delete_row(table, DBClientsColumns.ID.value, client_id)
            print(f"Cliente {client_id} rimosso con successo")
            return True, f"Cliente {client_id} rimosso con successo"
        except Exception as e:
            return False, f"Errore durante l'eliminazione del cliente: {str(e)}"

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
        Calcola il ritardo medio in giorni dei pagamenti per un dato cliente.

        Per ciascun pagamento (ottenuto dalla LEFT JOIN tra invoices e payments):
          - Si verifica che la fattura appartenga al cliente specificato.
          - Si ottiene il numero della rata associata al pagamento (campo LINKED_RATA).
          - Si seleziona la data di scadenza corrispondente della fattura:
                Se LINKED_RATA == 1 -> DATA_SCADENZA_1
                Se LINKED_RATA == 2 -> DATA_SCADENZA_2
                Se LINKED_RATA == 3 -> DATA_SCADENZA_3
          - Si confronta la data di pagamento con quella della rata:
                Se il pagamento è in ritardo (maggiore della data di scadenza), si calcola il ritardo in giorni.

        Ritorna il ritardo medio (in giorni). Se non ci sono pagamenti in ritardo, ritorna 0.
        """
        # Recupera tutte le righe dalla join invoices-payments
        invoices_with_payments = self.db_model.fetch_invoices_with_payments()
        # Combina le colonne di invoices e payments: prima quelle della fattura poi quelle del pagamento.
        all_columns = list(DBInvoicesColumns) + list(DBPaymentsColumns)

        # Converte ogni riga in un dizionario per un accesso più semplice
        invoices_with_payments_maps = [
            ValidationUtils._row_to_map(row, all_columns)
            for row in invoices_with_payments
        ]

        # Filtraggio o pulizia ulteriore se necessario (ad es. rimuovere fatture di tipo NDC o stornate)
        invoices_with_payments_maps = InvoiceController.clear_invoices_list_from_NDC_and_stornate(
            invoices_with_payments_maps)

        num_pagamenti = 0
        giorni_ritardo_totale = 0
        # Definisci il formato in cui le date sono memorizzate. Ad esempio: "YYYY-MM-DD"
        date_format = "%Y-%m-%d"

        for record in invoices_with_payments_maps:
            # Controlla se la fattura appartiene al cliente specificato
            if record[DBInvoicesColumns.ID_CLIENTE.value] == client_id:
                # Ottieni il numero della rata associata al pagamento
                linked_rata = record[DBPaymentsColumns.LINKED_RATA.value]

                # Seleziona la data di scadenza in base al numero della rata
                if linked_rata == 1:
                    due_date_str = record[DBInvoicesColumns.DATA_SCADENZA_1.value]
                elif linked_rata == 2:
                    due_date_str = record[DBInvoicesColumns.DATA_SCADENZA_2.value]
                elif linked_rata == 3:
                    due_date_str = record[DBInvoicesColumns.DATA_SCADENZA_3.value]
                else:
                    # Se il valore di linked_rata non è previsto, salta il record
                    continue

                # Ottieni la data del pagamento come stringa
                payment_date_str = record[DBPaymentsColumns.PAYMENT_DATE.value]

                try:
                    payment_date = datetime.strptime(payment_date_str, date_format)
                    due_date = datetime.strptime(due_date_str, date_format)
                except Exception as e:
                    # Se il parsing delle date fallisce, salta questo record
                    print(f"Errore nel parsing delle date per il record: {e}")
                    continue

                # Se il pagamento è avvenuto dopo la data di scadenza, calcola il ritardo
                if payment_date > due_date:
                    ritardo = (payment_date - due_date).days
                    giorni_ritardo_totale += ritardo
                    num_pagamenti += 1

        # Calcola e ritorna il ritardo medio (in giorni)
        if num_pagamenti > 0:
            return giorni_ritardo_totale / num_pagamenti
        else:
            return -1

    def calcola_totale_ritardi_cliente(self, client_id):
        """
            Calcola il ritardo medio in giorni dei pagamenti per un dato cliente.

            Per ciascun pagamento (ottenuto dalla LEFT JOIN tra invoices e payments):
              - Si verifica che la fattura appartenga al cliente specificato.
              - Si ottiene il numero della rata associata al pagamento (campo LINKED_RATA).
              - Si seleziona la data di scadenza corrispondente della fattura:
                    Se LINKED_RATA == 1 -> DATA_SCADENZA_1
                    Se LINKED_RATA == 2 -> DATA_SCADENZA_2
                    Se LINKED_RATA == 3 -> DATA_SCADENZA_3
              - Si confronta la data di pagamento con quella della rata:
                    Se il pagamento è in ritardo (maggiore della data di scadenza), si calcola il ritardo in giorni.

            Ritorna il totale dei ritardi (in giorni). Se non ci sono pagamenti in ritardo, ritorna 0.
        """

        # Recupera tutte le righe dalla join invoices-payments
        invoices_with_payments = self.db_model.fetch_invoices_with_payments()
        # Combina le colonne di invoices e payments: prima quelle della fattura poi quelle del pagamento.
        all_columns = list(DBInvoicesColumns) + list(DBPaymentsColumns)

        # Converte ogni riga in un dizionario per un accesso più semplice
        invoices_with_payments_maps = [
            ValidationUtils._row_to_map(row, all_columns)
            for row in invoices_with_payments
        ]

        # Filtraggio o pulizia ulteriore se necessario (ad es. rimuovere fatture di tipo NDC o stornate)
        invoices_with_payments_maps = InvoiceController.clear_invoices_list_from_NDC_and_stornate(
            invoices_with_payments_maps)

        num_pagamenti = 0
        giorni_ritardo_totale = 0
        # Definisci il formato in cui le date sono memorizzate. Ad esempio: "YYYY-MM-DD"
        date_format = "%Y-%m-%d"

        for record in invoices_with_payments_maps:
            # Controlla se la fattura appartiene al cliente specificato
            if record[DBInvoicesColumns.ID_CLIENTE.value] == client_id:
                # Ottieni il numero della rata associata al pagamento
                linked_rata = record[DBPaymentsColumns.LINKED_RATA.value]

                # Seleziona la data di scadenza in base al numero della rata
                if linked_rata == 1:
                    due_date_str = record[DBInvoicesColumns.DATA_SCADENZA_1.value]
                elif linked_rata == 2:
                    due_date_str = record[DBInvoicesColumns.DATA_SCADENZA_2.value]
                elif linked_rata == 3:
                    due_date_str = record[DBInvoicesColumns.DATA_SCADENZA_3.value]
                else:
                    # Se il valore di linked_rata non è previsto, salta il record
                    continue

                # Ottieni la data del pagamento come stringa
                payment_date_str = record[DBPaymentsColumns.PAYMENT_DATE.value]

                try:
                    payment_date = datetime.strptime(payment_date_str, date_format)
                    due_date = datetime.strptime(due_date_str, date_format)
                except Exception as e:
                    # Se il parsing delle date fallisce, salta questo record
                    print(f"Errore nel parsing delle date per il record: {e}")
                    continue

                # Se il pagamento è avvenuto dopo la data di scadenza, calcola il ritardo
                if payment_date > due_date:
                    ritardo = (payment_date - due_date).days
                    giorni_ritardo_totale += ritardo
                    num_pagamenti += 1

        return giorni_ritardo_totale


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

    def __init__(self, db_model: DatabaseModel, user_controller, client_controller, production_controller, payment_controller, account_controller, fiscal_settings):
        """Inizializza il controller con il modello del database"""
        self.db_model = db_model
        self.fiscal_settings = fiscal_settings
        self.user_controller = user_controller
        self.client_controller = client_controller
        self.production_controller = production_controller
        self.payment_controller = payment_controller
        self.account_controller = account_controller


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
                print(f"{col.name} pushed as string")

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

        invoice_data_prepared[DBInvoicesColumns.UPDATED_AT.value] = datetime.now().replace(microsecond=0)

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
        Recupera tutte le fatture, filtrandole per l'anno corrente se specificato.
        :param current_year: Booleano. Se True, ritorna solo le fatture emesse nell'anno corrente.
        :return: Lista di tuple (righe) con i dati delle fatture.
        """
        rows = self.db_model.fetch_invoices()
        if current_year:
            current_year_value = datetime.now().year
            columns = [col.value for col in DBInvoicesColumns]
            creation_index = columns.index(DBInvoicesColumns.DATA_CREAZIONE.value)
            filtered_rows = []
            for row in rows:
                date_str = row[creation_index]
                try:
                    # Prova a fare il parsing includendo l'orario
                    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    # Altrimenti usa solo la data
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                if dt.year == current_year_value:
                    filtered_rows.append(row)
            rows = filtered_rows
        return rows

    def retrieve_invoice_by_id(self, invoice_id, current_year=True):
        """
        Recupera una fattura specifica per ID, opzionalmente filtrando per l'anno corrente.
        :param invoice_id: ID della fattura.
        :param current_year: Se True, ritorna None se la fattura non è dell'anno corrente.
        :return: Una tupla con i dati della fattura oppure None.
        """
        row = self.db_model.fetch_invoice_by_id(invoice_id)
        if row and current_year:
            current_year_value = datetime.now().year
            columns = [col.value for col in DBInvoicesColumns]
            creation_index = columns.index(DBInvoicesColumns.DATA_CREAZIONE.value)
            date_str = row[creation_index]
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
            if dt.year != current_year_value:
                return None
        return row

    def retrieve_invoice_map_by_id(self, invoice_id, current_year=True):
        """
        Recupera una fattura specifica e la restituisce come dizionario, filtrando per l'anno corrente se specificato.
        :param invoice_id: ID della fattura.
        :param current_year: Se True, ritorna None se la fattura non è dell'anno corrente.
        :return: Dizionario con i dati della fattura oppure None.
        """
        row = self.db_model.fetch_invoice_by_id(invoice_id)
        if row and current_year:
            current_year_value = datetime.now().year
            columns = [col.value for col in DBInvoicesColumns]
            creation_index = columns.index(DBInvoicesColumns.DATA_CREAZIONE.value)
            date_str = row[creation_index]
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
            if dt.year != current_year_value:
                return None
        return ValidationUtils._row_to_map(row, DBInvoicesColumns)

    def retrieve_invoice_map_by_name(self, invoice_name, current_year=True):
        """
        Recupera una fattura in base al nome e la restituisce come dizionario,
        filtrando per l'anno corrente se specificato.

        :param invoice_name: Nome della fattura.
        :param current_year: Se True, ritorna un dizionario vuoto se la fattura non è dell'anno corrente.
        :return: Dizionario con i dati della fattura oppure un dizionario vuoto.
        """
        row = self.db_model.fetch_invoice_by_name(invoice_name)
        if not row:
            return {}

        if current_year:
            current_year_value = datetime.now().year
            columns = [col.value for col in DBInvoicesColumns]
            creation_index = columns.index(DBInvoicesColumns.DATA_CREAZIONE.value)
            date_str = row[creation_index]
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
            if dt.year != current_year_value:
                return {}

        return ValidationUtils._row_to_map(row, DBInvoicesColumns)

    def retrieve_invoices_map_list_by_user(self, user_id, current_year=True):
        """
        Recupera tutte le fatture di un certo utente e le restituisce come lista di dizionari, filtrandole per l'anno corrente se specificato.
        :param user_id: ID dell'utente.
        :param current_year: Se True, ritorna solo le fatture dell'anno corrente.
        :return: Lista di dizionari contenenti i dati delle fatture.
        """
        rows = self.db_model.fetch_invoices_by_user_id(user_id)
        if current_year and rows:
            current_year_value = datetime.now().year
            columns = [col.value for col in DBInvoicesColumns]
            creation_index = columns.index(DBInvoicesColumns.DATA_CREAZIONE.value)
            filtered_rows = []
            for row in rows:
                date_str = row[creation_index]
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                if dt.year == current_year_value:
                    filtered_rows.append(row)
            rows = filtered_rows
        return [ValidationUtils._row_to_map(row, DBInvoicesColumns) for row in rows]

    def retrieve_invoice_map_list_by_production(self, prod_id, current_year=True):
        """
        Recupera tutte le fatture di un certo utente e le restituisce come lista di dizionari, filtrandole per l'anno corrente se specificato.
        :param prod_id: ID della produzione.
        :param current_year: Se True, ritorna solo le fatture dell'anno corrente.
        :return: Lista di dizionari contenenti i dati delle fatture.
        """
        rows = self.db_model.fetch_invoices_by_prod_id(prod_id)
        if current_year and rows:
            current_year_value = datetime.now().year
            columns = [col.value for col in DBInvoicesColumns]
            creation_index = columns.index(DBInvoicesColumns.DATA_CREAZIONE.value)
            filtered_rows = []
            for row in rows:
                date_str = row[creation_index]
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                if dt.year == current_year_value:
                    filtered_rows.append(row)
            rows = filtered_rows
        return [ValidationUtils._row_to_map(row, DBInvoicesColumns) for row in rows]

    def retrieve_invoices_map_list(self, current_year=True):
        """
        Recupera tutte le fatture e le restituisce come lista di dizionari,
        filtrandole per l'anno corrente se specificato.
        """
        rows = self.db_model.fetch_invoices()
        # Costruisci la lista dei nomi delle colonne in base all'enum (l'ordine è importante)
        columns = [column.value for column in DBInvoicesColumns]

        if current_year:
            current_year_value = datetime.now().year
            # Trova l'indice della colonna DATA_CREAZIONE
            creation_index = columns.index(DBInvoicesColumns.DATA_CREAZIONE.value)
            filtered_rows = []
            for row in rows:
                try:
                    date_str = row[creation_index]
                    # Prova prima con l'orario; se fallisce, usa solo la data
                    try:
                        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        dt = datetime.strptime(date_str, "%Y-%m-%d")
                    if dt.year == current_year_value:
                        filtered_rows.append(row)
                except Exception as e:
                    print(f"Errore durante il parsing della data '{date_str}': {e}")
            rows = filtered_rows

        # Converte ogni riga in un dizionario usando la funzione _row_to_map
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

        :param current_year: Booleano. Se True, conta solo le fatture dell'anno corrente.
        :return: Numero di fatture (int)
        """

        if current_year:
            #filtra le fatture che sono note di credito
            invoices = self.clear_invoices_list_from_NDC_and_stornate(self.retrieve_invoices_map_list(True))
        else:
            invoices = self.clear_invoices_list_from_NDC_and_stornate(self.retrieve_invoices_map_list(False))

        return len(invoices)

    def calculate_TOT_DOCUMENTO_invoiced(self, current_year=True):
        if current_year:
            invoices_list = InvoiceController.clear_invoices_list_from_NDC_and_stornate(self.retrieve_invoices_map_list(True))
        else:
            invoices_list = InvoiceController.clear_invoices_list_from_NDC_and_stornate(self.retrieve_invoices_map_list(False))

        tot = 0.00
        for invoice in invoices_list:
            if invoice[DBInvoicesColumns.TOT_DOCUMENTO.value]:
                tot = tot + float(invoice[DBInvoicesColumns.TOT_DOCUMENTO.value])

        return tot

    def calculate_IVA_invoiced(self, current_year=True):
        if current_year:
            invoices_list = InvoiceController.clear_invoices_list_from_NDC_and_stornate(self.retrieve_invoices_map_list(True))
        else:
            invoices_list = InvoiceController.clear_invoices_list_from_NDC_and_stornate(self.retrieve_invoices_map_list(False))

        IVA = 0.00
        for invoice in invoices_list:
            if invoice[DBInvoicesColumns.IVA.value]:
                IVA = IVA + float(invoice[DBInvoicesColumns.IVA.value])

        return IVA

    def calculate_RITENUTA_ACCONTO_invoiced(self, current_year=True):
        if current_year:
            invoices_list = InvoiceController.clear_invoices_list_from_NDC_and_stornate(self.retrieve_invoices_map_list(True))
        else:
            invoices_list = InvoiceController.clear_invoices_list_from_NDC_and_stornate(self.retrieve_invoices_map_list(False))

        ritenuta = 0.00
        for invoice in invoices_list:
            if invoice[DBInvoicesColumns.RITENUTA.value]:
                ritenuta = ritenuta + float(invoice[DBInvoicesColumns.RITENUTA.value])

        return ritenuta

    def calculate_FATT_LORDO_invoiced(self, current_year=True):
        fatt_lordo = float(self.calculate_TOT_DOCUMENTO_invoiced(current_year)) - float(self.calculate_IVA_invoiced(current_year))
        return fatt_lordo

    def calculate_FATT_NETTO_invoiced(self, current_year=True):
        fatt_netto = float(self.calculate_TOT_DOCUMENTO_invoiced(current_year)) - float(self.calculate_IVA_invoiced(current_year)) - float(self.calculate_RITENUTA_ACCONTO_invoiced(current_year))
        return fatt_netto

    def calculate_CRED_LORDO_invoiced(self, current_year=True):
        """
        Calcola i crediti lordi basandosi sulle fatture (non note di credito e non stornate)
        e sui pagamenti ad esse associati, sfruttando il join tra invoices e payments.
        L'IVA viene sottratta dal totale della fattura (o dalla rata, per le fatture rateizzate).

        :param current_year: Se True, considera solo le fatture dell'anno corrente.
        :return: Totale del credito lordo (float).
        """
        # Recupera i dati dal join: la query restituisce una lista di tuple,
        # in cui le prime N colonne corrispondono ai dati della fattura (invoices)
        # e le colonne successive ai dati del pagamento (payments).
        rows = self.db_model.fetch_invoices_with_payments()
        oggi = datetime.today().date()

        # Raggruppa i record per invoice_id.
        # Supponiamo che l'ordine delle colonne in invoices sia quello definito in DBInvoicesColumns;
        # pertanto, il numero di colonne della fattura è:
        num_invoice_cols = len(DBInvoicesColumns)

        grouped = {}
        for row in rows:
            # L'ID della fattura è la prima colonna della parte invoices.
            invoice_id = row[0]
            if invoice_id not in grouped:
                # Salva i dati della fattura (parte iniziale della tupla) e inizializza la lista dei pagamenti.
                grouped[invoice_id] = {
                    "invoice_raw": row[0:num_invoice_cols],
                    "payments": []
                }
            # Le colonne successive rappresentano un pagamento.
            # Se il record di pagamento è presente (id pagamento non None), lo aggiungiamo.
            payment_raw = row[num_invoice_cols:]
            if payment_raw and payment_raw[0] is not None:
                grouped[invoice_id]["payments"].append(payment_raw)

        # Convertiamo le fatture raggruppate in mappe (dizionari) per poterle filtrare.
        all_invoice_maps = {}
        for inv_id, data in grouped.items():
            # Converte la parte "invoice_raw" in una mappa utilizzando l'enum DBInvoicesColumns.
            inv_map = ValidationUtils._row_to_map(data["invoice_raw"], DBInvoicesColumns)
            # Aggiunge alla mappa anche i dati dei pagamenti associati (li lasciamo in forma grezza)
            inv_map["payments"] = data["payments"]
            all_invoice_maps[inv_id] = inv_map

        # Filtra le fatture rimuovendo note di credito e fatture stornate.
        # Il metodo statico clear_invoices_list_from_NDC_and_stornate() riceve una lista di mappe.
        filtered_invoices = InvoiceController.clear_invoices_list_from_NDC_and_stornate(
            list(all_invoice_maps.values())
        )

        totale_credito = 0.0

        # Itera sulle fatture filtrate
        for invoice in filtered_invoices:
            # Se si vuole filtrare per anno corrente, controlla DATA_CREAZIONE
            if current_year:
                creation_date_str = invoice[DBInvoicesColumns.DATA_CREAZIONE.value]
                try:
                    dt = datetime.strptime(creation_date_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    dt = datetime.strptime(creation_date_str, "%Y-%m-%d")
                if dt.year != datetime.today().year:
                    continue

            # Estrae i campi necessari dalla fattura
            try:
                num_rate = int(invoice[DBInvoicesColumns.NUMERO_RATE.value])
            except (ValueError, TypeError):
                continue
            tot_documento = float(invoice[DBInvoicesColumns.TOT_DOCUMENTO.value])
            iva = float(invoice[DBInvoicesColumns.IVA.value])
            # Lo stato è già filtrato dalla clear_invoices_list_from_NDC_and_stornate, per cui non è stornata.

            # Recupera i pagamenti associati (li avevamo salvati sotto la chiave "payments")
            payments = invoice.get("payments", [])
            # I pagamenti sono ancora in forma di tuple: per accedere al campo LINKED_RATA, usiamo l'enum DBPaymentsColumns.
            # Creiamo una lista dei pagamenti convertiti in dizionari per comodità:
            payment_cols = [col.value for col in DBPaymentsColumns]
            payments_maps = []
            for p in payments:
                if p and p[0] is not None:
                    payments_maps.append(dict(zip(payment_cols, p)))

            if num_rate == int(InvoiceController.Rateizzazione.UNA.value):
                # Per fatture con 1 rata, verifichiamo se esiste un pagamento associato con LINKED_RATA == 1.
                paid = any(int(pm[DBPaymentsColumns.LINKED_RATA.value]) == 1 for pm in payments_maps)
                if not paid:
                    lordo_fattura = tot_documento - iva
                    totale_credito += lordo_fattura
            elif num_rate == int(InvoiceController.Rateizzazione.TRE.value):
                # Per fatture con 3 rate, dividiamo il totale lordo per 3
                lordo_rate = (tot_documento - iva) / 3.0
                # Controlla per ciascuna rata (1, 2, 3) se esiste un pagamento associato
                for rata in [1, 2, 3]:
                    paid = any(int(pm[DBPaymentsColumns.LINKED_RATA.value]) == rata for pm in payments_maps)
                    if not paid:
                        totale_credito += lordo_rate
            else:
                print(
                    f"Invoice id {invoice[DBInvoicesColumns.ID.value]}: numero rate non riconosciuto (valore: {num_rate}). Nessuna azione effettuata.")

        return totale_credito

    def calculate_CRED_NETTO_invoiced(self, current_year=True):
        """
        Calcola i crediti netti basandosi sulle fatture non stornate e sui pagamenti associati,
        sottraendo IVA e RITENUTA dal totale delle fatture.

        Il calcolo si basa sulle seguenti regole:

          Per fatture con una rata:
            - Se non esiste un pagamento associato (LINKED_RATA == 1), il credito netto è:
                  tot_documento - IVA - RITENUTA.

          Per fatture rateizzate in 3:
            - Il credito netto per rata è:
                  (tot_documento - IVA - RITENUTA) / 3.
            - Viene sommato per ciascuna rata (1, 2, 3) per cui non esiste un pagamento associato.

        Le fatture vengono ottenute tramite il join tra invoices e payments (con il metodo
        fetch_invoices_with_payments()) e successivamente filtrate per escludere note di credito
        e fatture stornate.

        :param current_year: Se True, considera solo le fatture dell'anno corrente.
        :return: Totale del credito netto (float).
        """
        # Recupera le righe dal join tra invoices e payments.
        rows = self.db_model.fetch_invoices_with_payments()
        oggi = datetime.today().date()

        # Determina quante colonne appartengono a invoices.
        num_invoice_cols = len(DBInvoicesColumns)

        # Raggruppa i risultati per invoice_id.
        grouped = {}
        for row in rows:
            # L'ID della fattura è la prima colonna della parte invoices.
            invoice_id = row[0]
            if invoice_id not in grouped:
                grouped[invoice_id] = {
                    "invoice_raw": row[0:num_invoice_cols],
                    "payments": []
                }
            # Le colonne successive sono quelle del pagamento; se il pagamento non è presente, il primo campo sarà None.
            payment_raw = row[num_invoice_cols:]
            if payment_raw and payment_raw[0] is not None:
                grouped[invoice_id]["payments"].append(payment_raw)

        # Converti ogni fattura in una mappa (dizionario) e associa la lista dei pagamenti (ancora in forma di tuple)
        all_invoice_maps = {}
        for inv_id, data in grouped.items():
            inv_map = ValidationUtils._row_to_map(data["invoice_raw"], DBInvoicesColumns)
            inv_map["payments"] = data["payments"]
            all_invoice_maps[inv_id] = inv_map

        # Filtra le fatture rimuovendo quelle che sono note di credito o stornate.
        filtered_invoices = InvoiceController.clear_invoices_list_from_NDC_and_stornate(
            list(all_invoice_maps.values())
        )

        totale_credito = 0.0
        # Prepara la lista dei nomi delle colonne per accedere ai campi dei pagamenti.
        payment_cols = [col.value for col in DBPaymentsColumns]

        # Itera sulle fatture filtrate
        for invoice in filtered_invoices:
            # Se si vuole considerare solo l'anno corrente, controlla DATA_CREAZIONE.
            if current_year:
                creation_date_str = invoice[DBInvoicesColumns.DATA_CREAZIONE.value]
                try:
                    dt = datetime.strptime(creation_date_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    dt = datetime.strptime(creation_date_str, "%Y-%m-%d")
                if dt.year != datetime.today().year:
                    continue

            # Estrai i dati necessari dalla fattura
            try:
                num_rate = int(invoice[DBInvoicesColumns.NUMERO_RATE.value])
            except (ValueError, TypeError):
                continue
            tot_documento = float(invoice[DBInvoicesColumns.TOT_DOCUMENTO.value])
            iva = float(invoice[DBInvoicesColumns.IVA.value])
            # Ritenuta può essere None, quindi se non presente la consideriamo zero.
            ritenuta = float(invoice[DBInvoicesColumns.RITENUTA.value] or 0)

            # I pagamenti sono memorizzati nella chiave "payments" (lista di tuple).
            # Convertiamo ciascun pagamento in un dizionario per accedere ai campi.
            payments = invoice.get("payments", [])
            payments_maps = []
            for p in payments:
                if p and p[0] is not None:
                    payments_maps.append(dict(zip(payment_cols, p)))

            # Calcola il credito netto in base alla tipologia di rateizzazione
            if num_rate == int(InvoiceController.Rateizzazione.UNA.value):
                # Fattura con 1 rata: se non esiste un pagamento (LINKED_RATA == 1) allora il credito è:
                # tot_documento - IVA - RITENUTA.
                paid = any(int(pm[DBPaymentsColumns.LINKED_RATA.value]) == 1 for pm in payments_maps)
                if not paid:
                    credito = tot_documento - iva - ritenuta
                    totale_credito += credito
            elif num_rate == int(InvoiceController.Rateizzazione.TRE.value):
                # Fattura rateizzata in 3: ogni rata ha un credito netto pari a:
                # (tot_documento - IVA - RITENUTA) / 3.
                credito_rate = (tot_documento - iva - ritenuta) / 3.0
                for rata in [1, 2, 3]:
                    paid = any(int(pm[DBPaymentsColumns.LINKED_RATA.value]) == rata for pm in payments_maps)
                    if not paid:
                        totale_credito += credito_rate
            else:
                print(
                    f"Invoice id {invoice[DBInvoicesColumns.ID.value]}: numero rate non riconosciuto (valore: {num_rate}). Nessuna azione effettuata.")

        return totale_credito

    def calculate_MEDIA_FATTURA_LORDO_invoiced(self, current_year=True):
        if current_year:
            fatt_lordo = self.calculate_FATT_LORDO_invoiced(True)
            numero_fatt = len(InvoiceController.clear_invoices_list_from_NDC_and_stornate(self.retrieve_invoices_map_list(True)))
            if numero_fatt > 0:
                media = fatt_lordo/numero_fatt
            else:
                media = -1
        else:
            fatt_lordo = self.calculate_FATT_LORDO_invoiced(False)
            numero_fatt = len(InvoiceController.clear_invoices_list_from_NDC_and_stornate(self.retrieve_invoices_map_list(False)))
            if numero_fatt > 0:
                media = fatt_lordo/numero_fatt
            else:
                media = -1

        return media

    def calculate_MEDIA_FATTURA_NETTO_invoiced(self, current_year=True):
        if current_year:
            fatt_netto = self.calculate_FATT_NETTO_invoiced(True)
            numero_fatt = len(InvoiceController.clear_invoices_list_from_NDC_and_stornate(self.retrieve_invoices_map_list(True)))
            if numero_fatt > 0:
                media = fatt_netto/numero_fatt
            else:
                media = -1
        else:
            fatt_netto = self.calculate_FATT_LORDO_invoiced(False)
            numero_fatt = len(InvoiceController.clear_invoices_list_from_NDC_and_stornate(self.retrieve_invoices_map_list(False)))
            if numero_fatt > 0:
                media = fatt_netto/numero_fatt
            else:
                media = -1

        return media

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
        # La funzione fetch_invoices_with_payments() restituisce una lista di tuple in cui:
        # - le prime N colonne (N = len(DBInvoicesColumns)) sono i dati della fattura,
        # - le colonne successive sono i dati dei pagamenti associati.
        rows = self.db_model.fetch_invoices_with_payments()
        oggi = datetime.today().date()

        # Raggruppa i record per invoice_id.
        num_invoice_cols = len(DBInvoicesColumns)
        grouped = {}
        for row in rows:
            # L'ID della fattura è la prima colonna della parte invoices
            invoice_id = row[0]
            if invoice_id not in grouped:
                grouped[invoice_id] = {
                    "invoice_raw": row[0:num_invoice_cols],
                    "payments": []
                }
            payment_raw = row[num_invoice_cols:]
            # Se il record di pagamento esiste (ID pagamento non None), lo aggiungiamo.
            if payment_raw and payment_raw[0] is not None:
                grouped[invoice_id]["payments"].append(payment_raw)

        # Converte ogni gruppo in una mappa (dizionario) per la fattura e conserva la lista dei pagamenti.
        all_invoice_maps = {}
        for inv_id, data in grouped.items():
            inv_map = ValidationUtils._row_to_map(data["invoice_raw"], DBInvoicesColumns)
            # Aggiungiamo i pagamenti grezzi (li convertiremo in mappe più avanti)
            inv_map["payments"] = data["payments"]
            all_invoice_maps[inv_id] = inv_map

        # Filtra le fatture, rimuovendo note di credito e fatture stornate
        filtered_invoices = InvoiceController.clear_invoices_list_from_NDC_and_stornate(
            list(all_invoice_maps.values())
        )

        updates = 0
        total = len(filtered_invoices)
        # Prepara la lista dei nomi delle colonne dei pagamenti per accedere ai campi
        payment_cols = [col.value for col in DBPaymentsColumns]

        for invoice in filtered_invoices:
            invoice_id = invoice[DBInvoicesColumns.ID.value]
            stato_attuale = invoice[DBInvoicesColumns.STATUS.value]
            num_rate = int(invoice[DBInvoicesColumns.NUMERO_RATE.value])
            nuovo_stato = stato_attuale  # default

            # Se la fattura è segnata come stornata (nota di credito), non viene modificata
            if stato_attuale == InvoiceController.InvoiceSatus.STORNATA.value:
                print(f"Fattura {invoice_id} non aggiornata poichè è nota di credito")
                continue

            # Se si filtra per anno corrente, controlla DATA_CREAZIONE
            if current_year:
                creation_date_str = invoice[DBInvoicesColumns.DATA_CREAZIONE.value]
                try:
                    dt = datetime.strptime(creation_date_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    dt = datetime.strptime(creation_date_str, "%Y-%m-%d")
                if dt.year != datetime.today().year:
                    continue

            # Converti i pagamenti in mappe per accedere ai campi (es. LINKED_RATA)
            payments = invoice.get("payments", [])
            payments_maps = []
            for p in payments:
                if p and p[0] is not None:
                    payments_maps.append(dict(zip(payment_cols, p)))

            if num_rate == int(InvoiceController.Rateizzazione.UNA.value):
                # Fattura con 1 rata: se esiste un pagamento con LINKED_RATA == 1 → PAGATA,
                # altrimenti se la scadenza (DATA_SCADENZA_1) è passata → SCADUTA, altrimenti EMESSA.
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
                # Fattura con 3 rate: raggruppa i pagamenti per rata.
                # Per ciascuna rata (1, 2, 3) verifica se esiste un pagamento con LINKED_RATA uguale.
                pagamenti = []
                for rata in [1, 2, 3]:
                    # Per ogni rata, seleziona il pagamento (se esiste) con LINKED_RATA == rata
                    payment = next((pm for pm in payments_maps if int(pm[DBPaymentsColumns.LINKED_RATA.value]) == rata),
                                   None)
                    pagamenti.append(
                        ControllerUtils.parse_date(payment[DBPaymentsColumns.PAYMENT_DATE.value]) if payment else None)
                # Recupera le scadenze dalle fatture
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
                    # Se nessun pagamento: se tutte le scadenze (definite) sono passate → SCADUTA,
                    # altrimenti se almeno una rata non pagata è scaduta (ma non tutte) → CRITICA,
                    # altrimenti EMESSA.
                    if all(s is not None and oggi > s for s in scadenze):
                        nuovo_stato = InvoiceController.InvoiceRateizzSatus.SCADUTA.value
                    elif count_overdue > 0 and count_overdue < 3:
                        nuovo_stato = InvoiceController.InvoiceRateizzSatus.CRITICA.value
                    else:
                        nuovo_stato = InvoiceController.InvoiceRateizzSatus.EMESSA.value
                else:
                    # Se alcune rate sono pagate (1 o 2):
                    if count_overdue > 0:
                        nuovo_stato = InvoiceController.InvoiceRateizzSatus.CRITICA.value
                    else:
                        nuovo_stato = InvoiceController.InvoiceRateizzSatus.PARZIALMENTE_SALDATA.value
            else:
                print(
                    f"Invoice id {invoice_id}: numero rate non riconosciuto (valore: {num_rate}). Nessuna azione effettuata.")
                continue

            # Aggiorna lo stato della fattura se è cambiato
            if nuovo_stato != stato_attuale:
                self.db_model.modify_invoice_datum(invoice_id, DBInvoicesColumns.STATUS.value, nuovo_stato)
                print(f"Invoice id {invoice_id}: stato aggiornato da '{stato_attuale}' a '{nuovo_stato}'.")
                updates += 1
            else:
                print(f"Invoice id {invoice_id}: nessun cambiamento (stato corrente: '{stato_attuale}').")

        print(f"Aggiornamento completato: {updates} su {total} fatture aggiornate.")

    def register_on_updating_invoice_controller_callbacks(self, *callbacks):
        self.on_updating_invoice_controller_callbacks = list(callbacks)

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
        if current_year:
            current_year_value = datetime.now().year
            columns = [col.value for col in DBPaymentsColumns]
            # Supponiamo che il campo della data di pagamento si chiami PAYMENT_DATE
            date_index = columns.index(DBPaymentsColumns.PAYMENT_DATE.value)
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

    def retrieve_payment_by_id(self, payment_id, current_year=True):
        """
        Recupera un pagamento specifico per ID, opzionalmente filtrando per l'anno corrente.
        :param payment_id: ID del pagamento.
        :param current_year: Se True, ritorna None se il pagamento non è dell'anno corrente.
        :return: Una tupla con i dati del pagamento oppure None.
        """
        row = self.db_model.fetch_payment_by_id(payment_id)
        if row and current_year:
            current_year_value = datetime.now().year
            columns = [col.value for col in DBPaymentsColumns]
            date_index = columns.index(DBPaymentsColumns.PAYMENT_DATE.value)
            date_str = row[date_index]
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
            if dt.year != current_year_value:
                return None
        return row

    def retrieve_payment_map_by_id(self, payment_id, current_year=True):
        """
        Recupera un pagamento specifico e lo restituisce come dizionario,
        filtrando per l'anno corrente se specificato.
        :param payment_id: ID del pagamento.
        :param current_year: Se True, ritorna None se il pagamento non è dell'anno corrente.
        :return: Dizionario con i dati del pagamento oppure None.
        """
        row = self.db_model.fetch_payment_by_id(payment_id)
        if row and current_year:
            current_year_value = datetime.now().year
            columns = [col.value for col in DBPaymentsColumns]
            date_index = columns.index(DBPaymentsColumns.PAYMENT_DATE.value)
            date_str = row[date_index]
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
            if dt.year != current_year_value:
                return None
        return ValidationUtils._row_to_map(row, DBPaymentsColumns)

    def retrieve_payments_map_list(self, current_year=True):
        """
        Recupera tutti i pagamenti e li restituisce come lista di dizionari,
        filtrandoli per l'anno corrente se specificato.
        """
        rows = self.db_model.fetch_payments()
        # Costruisci la lista dei nomi delle colonne in base all'enum (l'ordine è importante)
        columns = [column.value for column in DBPaymentsColumns]

        if current_year:
            current_year_value = datetime.now().year
            # Trova l'indice della colonna PAYMENT_DATE
            date_index = columns.index(DBPaymentsColumns.PAYMENT_DATE.value)
            filtered_rows = []
            for row in rows:
                try:
                    date_str = row[date_index]
                    # Prova prima con l'orario; se fallisce, usa solo la data
                    try:
                        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        dt = datetime.strptime(date_str, "%Y-%m-%d")
                    if dt.year == current_year_value:
                        filtered_rows.append(row)
                except Exception as e:
                    print(f"Errore durante il parsing della data '{date_str}': {e}")
            rows = filtered_rows

        # Converte ogni riga in un dizionario usando la funzione _row_to_map
        return [ValidationUtils._row_to_map(row, DBPaymentsColumns) for row in rows]

    def retrieve_payments_map_list_by_invoice_id(self, invoice_id, current_year=True):
        rows = self.db_model.fetch_payments_by_invoice_id(invoice_id)

        # Costruisci la lista dei nomi delle colonne in base all'enum (l'ordine è importante)
        columns = [column.value for column in DBPaymentsColumns]

        if current_year:
            current_year_value = datetime.now().year
            # Trova l'indice della colonna PAYMENT_DATE
            date_index = columns.index(DBPaymentsColumns.PAYMENT_DATE.value)
            filtered_rows = []
            for row in rows:
                try:
                    date_str = row[date_index]
                    # Prova prima con l'orario; se fallisce, usa solo la data
                    try:
                        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        dt = datetime.strptime(date_str, "%Y-%m-%d")
                    if dt.year == current_year_value:
                        filtered_rows.append(row)
                except Exception as e:
                    print(f"Errore durante il parsing della data '{date_str}': {e}")
            rows = filtered_rows

        # Converte ogni riga in un dizionario usando la funzione _row_to_map
        return [ValidationUtils._row_to_map(row, DBPaymentsColumns) for row in rows]

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
        if current_year:
            # Recupera e filtra la lista dei pagamenti per l'anno corrente
            payments = self.retrieve_payments_map_list(current_year=True)
        else:
            payments = self.retrieve_payments_map_list(current_year=False)

        return len(payments)

    def calculate_tot_payments(self, current_year=True):
        tot = 0.0
        payment_list = self.retrieve_payments_map_list(current_year)
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


            # Validazione campi obbligatori
            missing_fields = [field for field in self.required_fields if not payment_data.get(field)]
            if missing_fields:
                return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."


            # Validazione Importo
            if DBPaymentsColumns.PAYMENT_AMOUNT.value in payment_data:
                amount = payment_data[DBPaymentsColumns.PAYMENT_AMOUNT.value]
                if amount and not ValidationUtils.validate_amount(amount):
                    return False, "L'importo inserito non è valido."

            # Invoca il metodo del model per aggiornare l'utente
            self.db_model.update_user(payment_id, **payment_data)
            return True, "Pagamento aggiornato con successo!"

        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento del pagamento: {str(e)}"

    def register_on_adding_payment_callbacks(self, *callbacks):
        self.on_adding_payment_callbacks = list(callbacks)

    def sum_payments_for_account(self, account_id):
        return self.db_model.sum_payments_by_account(account_id)


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

    def retrieve_transfers_map_list(self):
        """
        Recupera tutti i trasferimenti come lista di dizionari.
        :return: Lista di dizionari con i dati dei trasferimenti.
        """
        rows = self.db_model.fetch_all_transfers()
        return [ValidationUtils._row_to_map(row, DBTransfersColumns) for row in rows]

    def retrieve_last_transfer_insert_map(self):
        """
        Recupera l'ultimo trasferimento inserito come dizionario.
        :return: Dizionario con i dati dell'ultimo trasferimento oppure None.
        """
        row = self.db_model.fetch_last_transfer_insert()
        return ValidationUtils._row_to_map(row, DBTransfersColumns)

    def retrieve_sent_transfers_map_by_account(self, account_id):
        """
        Recupera i trasferimenti inviati da un conto come lista di dizionari
        """
        transfers = self.db_model.fetch_sent_transfers_by_account(account_id)
        if not transfers:
            return []
        return [ValidationUtils._row_to_map(transfer, DBTransfersColumns) for transfer in transfers]

    def retrieve_received_transfers_map_by_account(self, account_id):
        """
        Recupera i trasferimenti ricevuti da un conto come lista di dizionari
        """
        transfers = self.db_model.fetch_received_transfers_by_account(account_id)
        if not transfers:
            return []
        return [ValidationUtils._row_to_map(transfer, DBTransfersColumns) for transfer in transfers]

    def retrieve_received_transfers_map(self, account_id):
        """
        Recupera i trasferimenti ricevuti da un conto come lista di dizionari.
        :param account_id: ID del conto ricevente
        :return: Lista di dizionari
        """
        rows = self.db_model.fetch_received_transfers_by_account(account_id)
        return [ValidationUtils._row_to_map(row, DBTransfersColumns) for row in rows]

    def retrieve_sent_transfers_map(self, account_id):
        """
        Recupera i trasferimenti inviati da un conto come lista di dizionari.
        :param account_id: ID del conto mittente
        :return: Lista di dizionari
        """
        rows = self.db_model.fetch_sended_transfers_by_account(account_id)
        return [ValidationUtils._row_to_map(row, DBTransfersColumns) for row in rows]

    def calculate_tot_amount_sent_transfers_by_account(self, account_id):
        sent_transfers = self.retrieve_sent_transfers_map_by_account(account_id)
        amount = 0.0

        for transfer in sent_transfers:
            amount = amount + float(transfer[DBTransfersColumns.AMOUNT.value])

        return amount

    def calculate_tot_amount_received_transfers_by_account(self, account_id):
        received_transfers = self.retrieve_received_transfers_map_by_account(account_id)
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


            # Validazione campi obbligatori
            missing_fields = [field for field in self.required_fields if not production_data.get(field)]
            if missing_fields:
                return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."


            # Validazione ore di lavoro
            if DBProductionsColumns.HOURS.value in production_data:
                hours = production_data[DBProductionsColumns.HOURS.value]
                if hours and not ValidationUtils.validate_integers(hours):
                    return False, "L'importo orario inserito non è valido, inserire un numero intero."

            # Validazione Importo
            if DBProductionsColumns.TOTALE_PREVENTIVO.value in production_data:
                amount = production_data[DBProductionsColumns.TOTALE_PREVENTIVO.value]
                if amount and not ValidationUtils.validate_amount(amount):
                    return False, "L'importo del preventivo inserito non è valido."

            # Invoca il metodo del model per aggiornare l'utente
            self.db_model.update_production(production_id, **production_data)
            self.update_aggregate_data()
            return True, "Produzione aggiornata con successo!"

        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento della produzione: {str(e)}"

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

    def retrieve_production_by_id(self, production_id, current_year=True):
        """
        Recupera una production specifica per ID, opzionalmente filtrando per l'anno corrente.

        :param production_id: ID della production.
        :param current_year: Se True, ritorna None se la production non è dell'anno corrente.
        :return: Una tupla con i dati della production oppure None.
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
        columns = [column.value for column in DBProductionsColumns]

        if current_year:
            current_year_value = datetime.now().year
            date_index = columns.index(DBProductionsColumns.CREATED_AT.value)
            filtered_rows = []
            for row in rows:
                try:
                    date_str = row[date_index]
                    try:
                        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        dt = datetime.strptime(date_str, "%Y-%m-%d")
                    if dt.year == current_year_value:
                        filtered_rows.append(row)
                except Exception as e:
                    print(f"Errore durante il parsing della data '{date_str}': {e}")
            rows = filtered_rows

        return [ValidationUtils._row_to_map(row, DBProductionsColumns) for row in rows]

    def retrieve_last_production_insert_map(self):
        """
        Recupera l'ultima production inserita e la restituisce come dizionario.
        """
        row = self.db_model.fetch_last_production_insert()
        return ValidationUtils._row_to_map(row, DBProductionsColumns)

    def retrieve_productions_map_list_by_client_id(self, client_id, current_year=True):
        """
        Recupera tutte le produzioni di un certo cliente e le restituisce come lista di dizionari, filtrandole per l'anno corrente se specificato.
        :param client_id: ID del cliente.
        :param current_year: Se True, ritorna solo le fatture dell'anno corrente.
        :return: Lista di dizionari contenenti i dati delle produzioni.
        """
        rows = self.db_model.fetch_productions_by_client_id(client_id)
        if current_year and rows:
            current_year_value = datetime.now().year
            columns = [col.value for col in DBProductionsColumns]
            creation_index = columns.index(DBProductionsColumns.CREATED_AT.value)
            filtered_rows = []
            for row in rows:
                date_str = row[creation_index]
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                if dt.year == current_year_value:
                    filtered_rows.append(row)
            rows = filtered_rows
        return [ValidationUtils._row_to_map(row, DBProductionsColumns) for row in rows]

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
        if len(user_name.split(" ")) >= 2: #se è un nome di un utente vero allora è Nome Cognome
            user_first = user_name.split(" ")[0]
            user_last = user_name.split(" ")[1]
            user = self.user_controller.retrieve_user_map_by_fullname(user_first, user_last)
            user_id_deduzione = user[DBUsersColumns.ID.value]

        #prendo ID fattura associata:
        invoice_id = None
        #la view si occupa di non mandare tra i dati la fattura associata se la categoria non è "SPESA DI PRODUZIONE"
        invoice_name = expense_data.get("FATTURA ASSOCIATA")
        if invoice_name:
            invoice = self.invoice_controller.retrieve_invoice_map_by_name(invoice_name, True)
            invoice_id = invoice[DBInvoicesColumns.ID.value]

        #calcolo importo netto
        aliquota_iva = float(expense_data.get("ALIQUOTA IVA"))
        spesa_netta = float(spesa_lorda)/( 1 + aliquota_iva)
        iva = spesa_netta * aliquota_iva

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


        expense_data_prepared = {
            DBExpensesColumns.NAME.value: expense_data.get(DBExpensesColumns.NAME.value),
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

    def retrieve_expense_by_id(self, expense_id, current_year=True):
        """
        Recupera una expense specifica per ID, opzionalmente filtrando per l'anno corrente.
        :param expense_id: ID della expense.
        :param current_year: Se True, ritorna None se la expense non è dell'anno corrente.
        :return: Una tupla con i dati della expense oppure None.
        """
        row = self.db_model.fetch_expense_by_id(expense_id)
        if row and current_year:
            current_year_value = datetime.now().year
            columns = [col.value for col in DBExpensesColumns]
            date_index = columns.index(DBExpensesColumns.DATE.value)
            date_str = row[date_index]
            try:
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                if dt.year != current_year_value:
                    return None
            except Exception as e:
                print(f"Errore durante il parsing della data '{date_str}': {e}")
                return None
        return row

    def retrieve_expense_map_by_id(self, expense_id, current_year=True):
        """
        Recupera una expense specifica e la restituisce come dizionario,
        filtrando per l'anno corrente se specificato.
        :param expense_id: ID della expense.
        :param current_year: Se True, ritorna None se la expense non è dell'anno corrente.
        :return: Dizionario con i dati della expense oppure None.
        """
        row = self.db_model.fetch_expense_by_id(expense_id)
        if row and current_year:
            current_year_value = datetime.now().year
            columns = [col.value for col in DBExpensesColumns]
            date_index = columns.index(DBExpensesColumns.DATE.value)
            date_str = row[date_index]
            try:
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                if dt.year != current_year_value:
                    return None
            except Exception as e:
                print(f"Errore nel parsing della data '{date_str}': {e}")
                return None
        return ValidationUtils._row_to_map(row, DBExpensesColumns)

    def retrieve_expenses_map_list(self, current_year=True):
        """
        Recupera tutte le expenses e le restituisce come lista di dizionari,
        filtrandole per l'anno corrente se specificato.
        """
        rows = self.db_model.fetch_expenses()
        columns = [col.value for col in DBExpensesColumns]

        if current_year:
            current_year_value = datetime.now().year
            date_index = columns.index(DBExpensesColumns.DATE.value)
            filtered_rows = []
            for row in rows:
                try:
                    date_str = row[date_index]
                    try:
                        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        dt = datetime.strptime(date_str, "%Y-%m-%d")
                    if dt.year == current_year_value:
                        filtered_rows.append(row)
                except Exception as e:
                    print(f"Errore durante il parsing della data '{date_str}': {e}")
            rows = filtered_rows

        return [ValidationUtils._row_to_map(row, DBExpensesColumns) for row in rows]

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

            new_exp = {
                DBExpensesColumns.NAME.value: nominal,
                DBExpensesColumns.SUPPLIER_ID.value: self.supplier_controller.retrieve_supplier_map_by_name(exp.supplier)[DBSuppliersColumns.ID.value],
                DBExpensesColumns.CATEGORY.value: exp.category,
                DBExpensesColumns.NET_AMOUNT.value: netto,
                DBExpensesColumns.IVA_AMOUNT.value: iva_amt,
                DBExpensesColumns.TOT_AMOUNT.value: gross,
                DBExpensesColumns.DATE.value: today.isoformat(),
                DBExpensesColumns.DEDUCIBILE.value: "Sì" if exp.deductible else "No",
                DBExpensesColumns.ACCOUNT_ID.value: acct_id
            # USER_ID e LINKED_INVOICE_ID non inclusi => rimangono NULL
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
        Recupera tutti i versamenti come lista di dizionari.
        :return: Lista di dizionari con i dati dei versamenti.
        """
        rows = self.db_model.fetch_all_salaries()
        return [ValidationUtils._row_to_map(row, DBSalariesColumns) for row in rows]

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




class Analyzer:
    def __init__(self,
                 user_controller,
                 client_controller,
                 account_controller,
                 transfer_controller,
                 supplier_controller,
                 production_controller,
                 payment_controller,
                 expenses_controller,
                 salary_controller,
                 fiscal_settings,
                 recurring_expenses_settings
                 ):
        self.user_controller = user_controller
        self.client_controller = client_controller
        self.account_controller = account_controller
        self.transfer_controller = transfer_controller
        self.supplier_controller = supplier_controller
        self.production_controller = production_controller
        self.payment_controller = payment_controller
        self.expenses_controller = expenses_controller
        self.salary_controller = salary_controller
        self.fiscal_settings = fiscal_settings
        self.recurring_expenses_settings = recurring_expenses_settings

    def calculate_account_balance_by_account_id(self, account_id):
        account = self.account_controller.retrieve_account_map_by_id(account_id)
        balance = 0.0
        if account:
            init_balance = float(account[DBAccountsColumns.INIT_BALANCE.value])

            tot_entrate = self.payment_controller.sum_payments_for_account(account_id) + self.transfer_controller.calculate_tot_amount_received_transfers_by_account(account_id)
            tot_uscite = self.expenses_controller.sum_expenses_for_account(account_id) + self.transfer_controller.calculate_tot_amount_sent_transfers_by_account(account_id)

            balance = init_balance + float(tot_entrate) - float(tot_uscite)

        return balance


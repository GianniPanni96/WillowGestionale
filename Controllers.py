import re
from datetime import datetime, timedelta, date
from Gestionale_Enums import*
from enum import Enum

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
import hashlib, secrets, hmac

from Fatturazione_elettronica_API import FatturazioneElettronicaProvider
from Model import DatabaseModel, DBUsersColumns, DBClientsColumns, DBInvoicesColumns, \
DBPaymentsColumns, DBProductionsColumns, DBAccountsColumns, DBExpensesColumns, \
DBSuppliersColumns, DBTransfersColumns, DBSalariesColumns, DBRefundsColumns
from QueryServices.Suppliers_query_service import SupplierQueryService

from QueryServices.Invoices_query_service import InvoiceQueryService

no_data_string = "no data"


# Classe Helper per le validazioni
#todo: eliminare dopo spostamento dei controller nei file singoli (uno per classe)
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
        pattern = r"^-?\d+(\.\d{1,2})?$"
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

    @staticmethod
    def validate_password_strength(password: str) -> tuple[bool, str]:
        """
        Verifica che la password soddisfi i criteri di sicurezza.

        Args:
            password (str): La password da validare

        Returns:
            tuple[bool, str]: (True, "") se valida, (False, messaggio di errore) altrimenti
        """
        # Verifica lunghezza minima
        if len(password) < 8:
            return False, "La password deve essere lunga almeno 8 caratteri"

        # Puoi aggiungere altri criteri qui in futuro
        # Esempio:
        # if not any(c.isupper() for c in password):
        #     return False, "La password deve contenere almeno una lettera maiuscola"
        # if not any(c.islower() for c in password):
        #     return False, "La password deve contenere almeno una lettera minuscola"
        # if not any(c.isdigit() for c in password):
        #     return False, "La password deve contenere almeno un numero"

        return True, ""



#todo: eliminare dopo spostamento dei controller nei file singoli (uno per classe)
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
    def filter_invoices(
            invoices,
            db_model,
            year: int = None,
            include_unpaid_invoices: bool = True
    ):
        """
        Filtra le fatture in base all'anno e, opzionalmente, include
        quelle non completamente saldate anche se di anni diversi.

        Regole:
        - Una fattura è SEMPRE inclusa se l'anno di emissione è quello richiesto
        - Se NON è dell'anno richiesto:
            - viene inclusa SOLO se include_unpaid_invoices=True
            - e la fattura ha almeno una rata non pagata

        :param invoices: Lista di fatture (dizionari)
        :param db_model: Istanza del DatabaseModel
        :param year:
            - None → anno corrente
            - -1   → nessun filtro
            - altro int → anno specifico
        :param include_unpaid_invoices: include fatture non saldate fuori anno
        :return: Lista filtrata di fatture
        """
        if not invoices or year == -1:
            return invoices

        target_year = year if year is not None else datetime.now().year

        # -------------------------
        # Pagamenti raggruppati per fattura
        # -------------------------
        all_payments = db_model.fetch_payments()
        payments_by_invoice = {}

        for p in all_payments:
            p_map = ValidationUtils._row_to_map(p, DBPaymentsColumns)
            inv_id = p_map[DBPaymentsColumns.INVOICE_ID.value]
            payments_by_invoice.setdefault(inv_id, []).append(p_map)

        # -------------------------
        # Filtro principale
        # -------------------------
        filtered = []

        for invoice in invoices:
            include = False

            invoice_id = invoice.get(DBInvoicesColumns.ID.value)
            num_rate = invoice.get(DBInvoicesColumns.NUMERO_RATE.value) or 1

            # --- 1. Controllo anno fattura ---
            date_str = invoice.get(DBInvoicesColumns.DATA_CREAZIONE.value)
            if date_str:
                try:
                    creation_dt = ControllerUtils._parse_date(date_str)
                    if creation_dt.year == target_year:
                        include = True
                except Exception as e:
                    print(f"Errore parsing data fattura '{date_str}': {e}")

            # --- 2. Controllo rate non saldate (opzionale) ---
            if not include and include_unpaid_invoices:
                payments = payments_by_invoice.get(invoice_id, [])
                paid_rates = {
                    p.get(DBPaymentsColumns.LINKED_RATA.value)
                    for p in payments
                }

                if len(paid_rates) < num_rate:
                    include = True

            if include:
                filtered.append(invoice)

        return filtered

    @staticmethod
    def filter_expenses(expenses, year: int = None):
        """
        Filtra le spese in base all'anno.

        :param expenses: Lista di spese (dizionari)
        :param year:
            - None → anno corrente
            - -1   → nessun filtro
            - altro int → anno specifico
        :return: Lista filtrata di spese
        """
        if not expenses or year == -1:
            return expenses

        target_year = year if year is not None else datetime.now().year
        filtered = []

        for exp in expenses:
            date_str = exp.get(DBExpensesColumns.DATE.value)
            if not date_str:
                continue

            try:
                dt = ControllerUtils._parse_date(date_str)
                if dt.year == target_year:
                    filtered.append(exp)
            except Exception as e:
                print(f"Errore parsing data spesa '{date_str}': {e}")

        return filtered

    @staticmethod
    def filter_payments(
            payments,
            db_model,
            year: int = None,
            include_unpaid_invoice_payments: bool = True
    ):
        """
        Filtra i pagamenti in base all'anno e, opzionalmente, include quelli
        collegati a fatture non completamente saldate.

        Regole:
        - Un pagamento è SEMPRE incluso se la sua data è nell'anno richiesto
        - Se NON è nell'anno richiesto:
            - viene incluso SOLO se include_unpaid_invoice_payments=True
            - e la fattura collegata ha almeno una rata non pagata

        :param payments: Lista di pagamenti (dizionari)
        :param db_model: Istanza del DatabaseModel
        :param year:
            - None → anno corrente
            - -1   → nessun filtro
            - altro int → anno specifico
        :param include_unpaid_invoice_payments: abilita il recupero dei pagamenti
            legati a fatture non completamente saldate anche fuori anno
        :return: Lista filtrata di pagamenti
        """
        if not payments or year == -1:
            return payments

        target_year = year if year is not None else datetime.now().year

        # -------------------------
        # Fatture (map per ID)
        # -------------------------
        invoices = db_model.fetch_invoices()
        invoices_map = {
            inv_map[DBInvoicesColumns.ID.value]: inv_map
            for inv_map in (
                ValidationUtils._row_to_map(inv, DBInvoicesColumns)
                for inv in invoices
            )
        }

        # -------------------------
        # Pagamenti raggruppati per fattura
        # -------------------------
        all_payments = db_model.fetch_payments()
        payments_by_invoice = {}

        for p in all_payments:
            p_map = ValidationUtils._row_to_map(p, DBPaymentsColumns)
            inv_id = p_map[DBPaymentsColumns.INVOICE_ID.value]
            payments_by_invoice.setdefault(inv_id, []).append(p_map)

        # -------------------------
        # Filtro principale
        # -------------------------
        filtered = []

        for payment in payments:
            include = False

            # --- 1. Controllo anno pagamento ---
            date_str = payment.get(DBPaymentsColumns.PAYMENT_DATE.value)
            if date_str:
                try:
                    dt = ControllerUtils._parse_date(date_str)
                    if dt.year == target_year:
                        include = True
                except Exception as e:
                    print(f"Errore parsing data pagamento '{date_str}': {e}")

            # --- 2. Controllo fattura non saldata (opzionale) ---
            if not include and include_unpaid_invoice_payments:
                invoice_id = payment.get(DBPaymentsColumns.INVOICE_ID.value)
                invoice = invoices_map.get(invoice_id)

                if invoice:
                    num_rate = invoice.get(DBInvoicesColumns.NUMERO_RATE.value) or 1
                    paid_rates = {
                        p[DBPaymentsColumns.LINKED_RATA.value]
                        for p in payments_by_invoice.get(invoice_id, [])
                    }

                    if len(paid_rates) < num_rate:
                        include = True

            if include:
                filtered.append(payment)

        return filtered

    @staticmethod
    def filter_refunds(refunds, year: int = None):
        """
        Filtra i rimborsi in base all'anno.

        :param refunds: Lista di rimborsi (dizionari)
        :param year:
            - None → anno corrente
            - -1   → nessun filtro
            - altro int → anno specifico
        :return: Lista filtrata di rimborsi
        """
        if not refunds or year == -1:
            return refunds

        target_year = year if year is not None else datetime.now().year
        filtered = []

        for refund in refunds:
            date_str = refund.get(DBRefundsColumns.REFUND_DATE.value)
            if not date_str:
                continue

            try:
                dt = ControllerUtils._parse_date(date_str)
                if dt.year == target_year:
                    filtered.append(refund)
            except Exception as e:
                print(f"Errore parsing data rimborso '{date_str}': {e}")

        return filtered

    @staticmethod
    def filter_productions(
            productions,
            db_model,
            year: int = None,
            include_prod_with_unpaid_invoices: bool = False
    ):
        """
        Filtra le produzioni mantenendo:
          - Tutte le produzioni create nell'anno richiesto
          - Produzioni di altri anni SOLO se:
                include_prod_with_unpaid_invoices == True
                E collegate a fatture con almeno una rata non saldata

        Se year == -1, non viene applicato alcun filtro.

        Gestisce sia liste che singole produzioni.
        """

        # ----------------------------
        # Gestione singolo elemento
        # ----------------------------
        single_item = not isinstance(productions, list)
        if single_item:
            productions = [productions]

        if not productions:
            return productions[0] if single_item else productions

        # ----------------------------
        # Default: anno corrente
        # ----------------------------
        if year is None:
            year = datetime.now().year

        # Nessun filtro
        if year == -1:
            return productions[0] if single_item else productions

        # ----------------------------
        # Recupero fatture e pagamenti
        # ----------------------------
        invoices = db_model.fetch_invoices()
        payments = db_model.fetch_payments()

        invoices_map = [ValidationUtils._row_to_map(inv, DBInvoicesColumns) for inv in invoices]
        payments_map = [ValidationUtils._row_to_map(p, DBPaymentsColumns) for p in payments]

        # invoice_id → lista pagamenti
        invoice_payments = {}
        for p in payments_map:
            invoice_id = p[DBPaymentsColumns.INVOICE_ID.value]
            invoice_payments.setdefault(invoice_id, []).append(p)

        # ----------------------------
        # Fatture NON completamente saldate
        # ----------------------------
        unpaid_invoice_ids = set()

        for inv in invoices_map:
            invoice_id = inv[DBInvoicesColumns.ID.value]
            num_rate = inv.get(DBInvoicesColumns.NUMERO_RATE.value) or 1

            paid_rates = {
                p[DBPaymentsColumns.LINKED_RATA.value]
                for p in invoice_payments.get(invoice_id, [])
            }

            if len(paid_rates) < num_rate:
                unpaid_invoice_ids.add(invoice_id)

        # ----------------------------
        # Filtraggio produzioni
        # ----------------------------
        filtered = []

        for prod in productions:
            date_str = prod.get(DBProductionsColumns.CREATED_AT.value)
            if not date_str:
                continue

            try:
                dt = ControllerUtils._parse_date(date_str)
            except Exception as e:
                print(f"Errore durante il parsing della data '{date_str}': {e}")
                continue

            # 1️ Produzione dell'anno richiesto → sempre inclusa
            if dt.year == year:
                filtered.append(prod)
                continue

            # 2️ Produzione di altro anno
            if not include_prod_with_unpaid_invoices:
                # flag False → ESCLUDI SEMPRE
                continue

            # flag True → includi solo se ha fatture non saldate
            has_unpaid_invoice = any(
                inv[DBInvoicesColumns.ID.value] in unpaid_invoice_ids
                and inv.get(DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value)
                == prod.get(DBProductionsColumns.ID.value)
                for inv in invoices_map
            )

            if has_unpaid_invoice:
                filtered.append(prod)

        return filtered[0] if single_item and filtered else filtered

    @staticmethod
    def filter_salaries(salaries, year: int = None):
        """
        Filtra i versamenti mantenendo solo quelli effettuati nell'anno specificato.
        Gestisce sia liste che singoli versamenti.

        :param salaries: Singolo versamento o lista di versamenti (dizionari)
        :param year: Anno di riferimento. None → anno corrente, -1 → nessun filtro.
        :return: Lista filtrata o singolo versamento
        """
        # Gestione del caso di singolo elemento
        single_item = not isinstance(salaries, list)
        if single_item:
            salaries = [salaries]

        if not salaries or year == -1:
            return salaries[0] if single_item else salaries

        if year is None:
            year = datetime.now().year

        filtered = []
        for sal in salaries:
            date_str = sal.get(DBSalariesColumns.DATE.value)
            if not date_str:
                continue
            try:
                dt = ControllerUtils._parse_date(date_str)
                if dt.year == year:
                    filtered.append(sal)
            except Exception as e:
                print(f"Errore durante il parsing della data '{date_str}': {e}")

        return filtered[0] if single_item and filtered else filtered

    @staticmethod
    def filter_transfers(transfers, year: int = None):
        """
        Filtra i trasferimenti in base all'anno specificato.
        Gestisce sia liste che singoli trasferimenti.

        :param transfers: Singolo trasferimento o lista di trasferimenti (dizionari)
        :param year: Anno di riferimento. None → anno corrente, -1 → nessun filtro
        :return: Lista filtrata o singolo trasferimento
        """
        # Gestione del caso di singolo elemento
        single_item = not isinstance(transfers, list)
        if single_item:
            transfers = [transfers]

        if transfers is None or year == -1:
            return transfers[0] if single_item else transfers

        if year is None:
            year = datetime.now().year

        filtered = []
        for tr in transfers:
            date_str = tr.get(DBTransfersColumns.CREATED_AT.value)
            if not date_str:
                continue
            try:
                dt = ControllerUtils._parse_date(date_str)
                if dt.year == year:
                    filtered.append(tr)
            except Exception as e:
                print(f"Errore durante il parsing della data '{date_str}': {e}")

        return filtered[0] if single_item and filtered else filtered

    @staticmethod
    def filter_suppliers(suppliers, year: int = None):
        """
        Filtra i fornitori in base all'anno di creazione/attività.

        :param suppliers: Singolo fornitore o lista di fornitori (dizionari)
        :param year:
            - None → anno corrente
            - -1   → nessun filtro
            - altro int → anno specifico
        :return: Lista filtrata o singolo fornitore
        """
        # Gestione caso singolo elemento
        single_item = not isinstance(suppliers, list)
        if single_item:
            suppliers = [suppliers]

        if not suppliers or year == -1:
            return suppliers[0] if single_item else suppliers

        target_year = year if year is not None else datetime.now().year
        filtered = []

        for sup in suppliers:
            date_str = sup.get(DBSuppliersColumns.CREATED_AT.value)  # O altro campo data
            if not date_str:
                continue

            try:
                dt = ControllerUtils._parse_date(date_str)
                if dt.year == target_year:
                    filtered.append(sup)
            except Exception as e:
                print(f"Errore parsing data fornitore '{date_str}': {e}")

        return filtered[0] if single_item and filtered else filtered

    @staticmethod
    def clear_invoices_list_from_NDC_and_stornate(invoices_list_of_maps):

        return [inv for inv in invoices_list_of_maps if
                inv[DBInvoicesColumns.TIPO.value] != TipologiaFattura.NOTA_DI_CREDITO.value and inv[
                    DBInvoicesColumns.STATUS.value] != InvoiceRateizzSatus.STORNATA.value]

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Crea un hash sicuro della password con salt.

        Args:
            password (str): La password da hashare

        Returns:
            str: Stringa contenente salt + hash in formato esadecimale
        """
        # Genera un salt casuale
        salt = secrets.token_bytes(32)

        # Combina password e salt, poi hasha
        hashed = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000  # Numero di iterazioni
        )

        # Restituisce salt + hash in formato esadecimale
        return f"{salt.hex()}{hashed.hex()}"

    @staticmethod
    def verify_password(password: str, stored_hash: str) -> bool:
        """
        Verifica se la password corrisponde all'hash memorizzato.

        Args:
            password (str): La password da verificare
            stored_hash (str): L'hash memorizzato nel database

        Returns:
            bool: True se la password è corretta, False altrimenti
        """
        try:
            # Estrai salt e hash dallo stored value
            # 32 bytes = 64 caratteri esadecimali
            salt = bytes.fromhex(stored_hash[:64])
            stored_hashed = bytes.fromhex(stored_hash[64:])

            # Calcola l'hash della password fornita con lo stesso salt
            computed_hashed = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt,
                100000
            )

            # Confronta in modo safe contro timing attacks
            return hmac.compare_digest(computed_hashed, stored_hashed)

        except Exception as e:
            print(f"Errore nella verifica password: {e}")
            return False

    @staticmethod
    def row_to_map(row, database_columns):
        """Converte una singola riga in un dizionario."""
        if row is None:
            return None
        keys = [column.value for column in database_columns]
        return dict(zip(keys, row))

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

    def retrieve_user_with_invoices_map_list(self, user_id, include_unpaid_invoices:bool = True, year: int = None):
        """
        Recupera lo specifico user unito alle rispettive fatture e
        li restituisce come lista di dizionari, filtrando opzionalmente
        per anno di emissione.

        :param user_id: ID dello user
        :param include_unpaid_invoices: booleano per includere le fatture non saldate ma di esercizi passati
        :param year:
            - None → anno corrente
            - -1   → nessun filtro
            - altro int → anno specifico
        :return: Lista di dizionari user + invoice
        """
        rows = self.db_model.fetch_user_with_invoices(user_id)
        if not rows:
            return []

        all_columns = list(DBUsersColumns) + list(DBInvoicesColumns)

        mapped_rows = [
            ValidationUtils._row_to_map(row, all_columns)
            for row in rows
        ]

        return ControllerUtils.filter_invoices(mapped_rows, self.db_model, year, include_unpaid_invoices=include_unpaid_invoices)

    def retrieve_users_with_tot_fatturato(self, year: int = None) -> dict[str, dict[str, float]]:
        output_map = {
            self.RegimeFiscale.FORFETTARIO.value : {},
            self.RegimeFiscale.ORDINARIO.value: {}
        }

        for user in self.retrieve_users_map_list():
            if user[DBUsersColumns.REGIME_FISCALE.value] == self.RegimeFiscale.FORFETTARIO.value:
                output_map[self.RegimeFiscale.FORFETTARIO.value][user[DBUsersColumns.LAST_NAME.value]] = self.calcola_tot_fatturato_utente(user[DBUsersColumns.ID.value], year = year)
            elif user[DBUsersColumns.REGIME_FISCALE.value] == self.RegimeFiscale.ORDINARIO.value:
                output_map[self.RegimeFiscale.ORDINARIO.value][user[DBUsersColumns.LAST_NAME.value]] = self.calcola_tot_fatturato_utente(user[DBUsersColumns.ID.value], year = year)

        return output_map

    def retrieve_users_with_tot_spese(self, year:int = None) -> dict[str, float]:
        output_map: dict[str, float] = {}

        for user in self.retrieve_users_map_list():
            user_id = user[DBUsersColumns.ID.value]
            cognome = user[DBUsersColumns.LAST_NAME.value]
            chiave = f"{cognome}"

            output_map[chiave] = self.calcola_tot_spese_utente_dedotte(user_id, year = year)

        return output_map

    def retrieve_user_with_anticipated_expenses_map_list(self, user_id, year:int = None):
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
        mapped_rows = [ValidationUtils._row_to_map(row, all_columns) for row in rows]

        return ControllerUtils.filter_expenses(mapped_rows, year = year)

    def retrieve_user_with_deducted_expenses_map_list(self, user_id, year: int = None):
        """
        Recupera lo specifico user unito alle rispettive spese in deduzione e
        li restituisce come lista di dizionari, filtrando opzionalmente per anno
        di emissione della spesa.

        :param user_id: ID dello user
        :param year:
            - None → anno corrente
            - -1   → nessun filtro
            - altro int → anno specifico
        :return: Lista di dizionari user + expense
        """
        rows = self.db_model.fetch_user_with_deducted_expenses(user_id)
        if not rows:
            return []

        all_columns = list(DBUsersColumns) + list(DBExpensesColumns)

        mapped_rows = [
            ValidationUtils._row_to_map(row, all_columns)
            for row in rows
        ]

        # Riutilizzo diretto del filtro centralizzato
        return ControllerUtils.filter_expenses(mapped_rows, year = year)

    def retrieve_user_with_salaries_map_list(self, user_id, year:int = None):
        """
        Recupera lo specifico user unito ai rispettivi salari e
        li restituisce come lista di dizionari.
        """
        # Recupera le righe dal database per lo specifico client
        rows = self.db_model.fetch_user_with_salaries(user_id)

        all_columns = list(DBUsersColumns) + list(DBSalariesColumns)

        mapped_rows = [ValidationUtils._row_to_map(row, all_columns) for row in rows]

        # Converte ogni riga in un dizionario
        return ControllerUtils.filter_salaries(mapped_rows, year = year)

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

        #validazione password login
        if DBUsersColumns.PASSWORD_LOGIN.value in update_fields:
            login_password = update_fields[DBUsersColumns.PASSWORD_LOGIN.value]
            if login_password and not ValidationUtils.validate_password_strength(login_password):
                return False, "Password non valida, digitare almeno 8 caratteri"

        # Gestione password login - HASHING
        if DBUsersColumns.PASSWORD_LOGIN.value in update_fields:
            password_value = update_fields[DBUsersColumns.PASSWORD_LOGIN.value]
            if password_value and password_value.strip():  # Se la password non è vuota
                try:
                    # Crea l'hash della password
                    hashed_password = ControllerUtils.hash_password(password_value)
                    update_fields[DBUsersColumns.PASSWORD_LOGIN.value] = hashed_password
                except Exception as e:
                    print(f"Errore durante l'hashing della password di login: {e}")
                    return False, "Errore durante la creazione della password di login."
            else:
                # Se la password è vuota, rimuovila dai campi da aggiornare
                # (mantieni il valore esistente nel database)
                update_fields.pop(DBUsersColumns.PASSWORD_LOGIN.value)

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
            # Se il provider è "NESSUNO", rimuovi username e password provider
            if DBUsersColumns.USERNAME_PROVIDER.value in update_fields:
                update_fields.pop(DBUsersColumns.USERNAME_PROVIDER.value)
            if DBUsersColumns.PASSWORD_PROVIDER.value in update_fields:
                update_fields.pop(DBUsersColumns.PASSWORD_PROVIDER.value)

        try:
            # Invoca il metodo del model per aggiornare l'utente
            self.db_model.update_user(user_id, **update_fields)
            return True, "Utente aggiornato con successo!"

        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento dell'utente: {str(e)}"

    def calcola_reddito_tot_utente(self, user_id, year:int = None):
        """
        Calcola il reddito di un utente a partire da un reddito esterno e la somma dei lordi delle fatture
        :param user_id: ID dell'utente
        :return: il reddito
        """
        invoices = self.db_model.fetch_invoices_by_user_id(user_id)
        reddito_esterno = self.retrieve_user_map_by_id(user_id)[DBUsersColumns.REDDITO_ESTERNO.value]
        reddito = reddito_esterno

        filter_invoices = True

        if year is not None:
            selected_year = year
            if year == -1:
                filter_invoices = False
        else:
            selected_year = datetime.now().year

        # Filtro le fatture emesse solo nell'anno corrente
        if filter_invoices:
            invoices = [
                invoice
                for invoice in invoices
                if datetime.strptime(invoice[DBInvoicesColumns.DATA_CREAZIONE.value], "%Y-%m-%d").year == selected_year
            ]

        for invoice in invoices:
            reddito = reddito + invoice[DBInvoicesColumns.TOT_DOCUMENTO.value]

        return reddito

    def calcola_tot_fatturato_utente(self, user_id, include_unpaid_invoices:bool = True, year:int = None):
        """
        Calcola il fatturato di un utente come somma delle fatture
        emesse nell'anno corrente, sfruttando il join user‑invoices.

        :param user_id: ID dell'utente
        :return: il fatturato (float)
        """
        # Recupera l'utente + tutte le sue fatture
        rows = self.retrieve_user_with_invoices_map_list(user_id, include_unpaid_invoices = include_unpaid_invoices, year = year)
        if not rows:
            return 0.0


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

            if anno == year:
                # Sommo il totale del documento
                tot = row.get(DBInvoicesColumns.TOT_DOCUMENTO.value) or 0.0
                fatturato += float(tot)

        return fatturato

    def calcola_tot_spese_utente_anticipate(self, user_id, year:int = None):
        """
        Calcola le spese anticipate di un utente come somma delle expenses
        emesse nell'anno corrente, sfruttando il join user‑expenses.

        :param user_id: ID dell'utente
        :return: il totale delle spese (float)
        """
        # Recupera l'utente + tutte le sue spese
        rows = self.retrieve_user_with_anticipated_expenses_map_list(user_id, year = year)
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

    def calcola_tot_spese_utente_dedotte(self, user_id, year:int = None):
        """
        Calcola le spese in deduzione di un utente come somma delle expenses
        emesse nell'anno corrente, sfruttando il join user‑expenses.

        :param user_id: ID dell'utente
        :return: il totale delle spese (float)
        """
        # Recupera l'utente + tutte le sue spese
        rows = self.retrieve_user_with_deducted_expenses_map_list(user_id, year = year)
        if not rows:
            return 0.0

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

            if anno == year:
                # Sommo il totale del documento
                tot = row.get(DBExpensesColumns.TOT_AMOUNT.value) or 0.0
                tot_spese += float(tot)

        return tot_spese

    def calcola_tot_salari_utente(self, user_id, year:int = None):
        """
        Calcola gli ingressi di un utente come somma dei salari
        emesse nell'anno corrente, sfruttando il join user‑expenses.

        :param user_id: ID dell'utente
        :return: il totale delle spese (float)
        """
        # Recupera l'utente + tutte le sue spese
        rows = self.retrieve_user_with_salaries_map_list(user_id, year = year)
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

    def calcola_tot_ritenuta_acconto_ordinaria(self, user_id, year:int = None):
        invoices = self.retrieve_user_with_invoices_map_list(user_id, year = year)
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


    def check_password_for_login(self, username, password):
        user = self.retrieve_user_map_by_extended_name(username)
        if user:
            db_hash = user.get(DBUsersColumns.PASSWORD_LOGIN.value)
            if db_hash == "" or db_hash is None:
                return False, ("L'utente selezionato non ha impostato una password per il login\n"
                               "Impostare uno nuova password dal dettaglio dell'utente"), -1
        else:
            print("Utente selezionato non trovato")
            return False, "Utente selezionato non trovato", -1

        if ControllerUtils.verify_password(password, db_hash):
            print("Login Effettuato")
            return True, "Login Effettuato", int(user.get(DBUsersColumns.ID.value))
        else:
            print("Password errata!")
            return False, "Password errata!", -1


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

    def update_account(self, account_id, account_data):
        """
        Aggiorna i dati di un conto esistente.
        :param account_id: ID del conto da aggiornare
        :param account_data: Dizionario contenente i dati da aggiornare
        :return: Tuple (success, message), dove success è True/False
        """
        try:
            # Controllo validità refund_id
            if not account_id or not isinstance(account_id, int):
                return False, "ID account non valido. Deve essere un intero positivo."

            required_fields = {DBAccountsColumns.NAME.value, DBAccountsColumns.INIT_BALANCE.value}

            # Validazione campi obbligatori
            missing_fields = [field for field in required_fields if not account_data.get(field)]
            if missing_fields:
                return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

            # Validazione Importi
            if DBAccountsColumns.INIT_BALANCE.value in account_data:
                amount = account_data[DBAccountsColumns.INIT_BALANCE.value]
                if amount and not ValidationUtils.validate_amount(amount):
                    return False, "L'importo inserito non è valido."

            account_data[DBAccountsColumns.UPDATED_AT.value] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Invoca il metodo del model per aggiornare l'utente
            self.db_model.update_account(account_id, **account_data)
            return True, "Account aggiornato con successo!"

        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento del conto: {str(e)}"

    def retrieve_account_map_by_id(self, account_id):
        """
        Recupera un account specifico per ID e lo restituisce come dizionario,
        opzionalmente filtrando per l'anno corrente.

        :param account_id: ID dell'account.
        :return: Dizionario con i dati dell'account oppure None.
        """
        row = self.db_model.fetch_account_by_id(account_id)
        return ValidationUtils._row_to_map(row, DBAccountsColumns)

    def retrieve_account_map_by_name(self, account_name):
        """
        Recupera un account specifico per nome, opzionalmente filtrando per l'anno corrente.

        :param account_name: Nome dell'account.
        :return: Una tupla con i dati dell'account oppure None.
        """
        row = self.db_model.fetch_account_by_name(account_name)
        return ValidationUtils._row_to_map(row, DBAccountsColumns)

    def retrieve_accounts_map_list(self):
        """
        Recupera tutti gli account e li restituisce come lista di dizionari,
        filtrandoli per l'anno corrente se specificato.
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

    def retrieve_transfer_map_by_id(self, transfer_id):
        """
        Recupera un trasferimento specifico per ID e lo restituisce come dizionario.
        :param transfer_id: ID del trasferimento.
        :return: Dizionario con i dati del trasferimento oppure None.
        """
        row = self.db_model.fetch_transfer_by_id(transfer_id)
        return ValidationUtils._row_to_map(row, DBTransfersColumns)

    def retrieve_transfers_map_list(self, year: int = None):
        """
        Recupera tutti i trasferimenti come lista di dizionari.
        :param year: Anno di riferimento. None → anno corrente, -1 → nessun filtro
        :return: Lista di dizionari con i dati dei trasferimenti.
        """
        rows = self.db_model.fetch_all_transfers()
        transfers = [ValidationUtils._row_to_map(row, DBTransfersColumns) for row in rows]
        return ControllerUtils.filter_transfers(transfers, year)

    def retrieve_last_transfer_insert_map(self):
        """
        Recupera l'ultimo trasferimento inserito come dizionario.
        :return: Dizionario con i dati dell'ultimo trasferimento oppure None.
        """
        row = self.db_model.fetch_last_transfer_insert()
        return ValidationUtils._row_to_map(row, DBTransfersColumns)

    def retrieve_sent_transfers_map_by_account(self, account_id, year: int = None):
        """
        Recupera i trasferimenti inviati da un conto come lista di dizionari.
        :param account_id: ID del conto mittente
        :param year: Anno di riferimento
        """
        transfers = self.db_model.fetch_sent_transfers_by_account(account_id)
        if not transfers:
            return []
        transfers_map = [ValidationUtils._row_to_map(tr, DBTransfersColumns) for tr in transfers]
        return ControllerUtils.filter_transfers(transfers_map, year)

    def retrieve_received_transfers_map_by_account(self, account_id, year: int = None):
        """
        Recupera i trasferimenti ricevuti da un conto come lista di dizionari.
        :param account_id: ID del conto destinatario
        :param year: Anno di riferimento
        """
        transfers = self.db_model.fetch_received_transfers_by_account(account_id)
        if not transfers:
            return []
        transfers_map = [ValidationUtils._row_to_map(tr, DBTransfersColumns) for tr in transfers]
        return ControllerUtils.filter_transfers(transfers_map, year)

    def retrieve_received_transfers_map(self, account_id, year: int = None):
        """
        Recupera i trasferimenti ricevuti da un conto come lista di dizionari.
        :param account_id: ID del conto ricevente
        :param year: Anno di riferimento
        :return: Lista di dizionari
        """
        rows = self.db_model.fetch_received_transfers_by_account(account_id)
        transfers = [ValidationUtils._row_to_map(row, DBTransfersColumns) for row in rows]
        return ControllerUtils.filter_transfers(transfers, year)

    def retrieve_sent_transfers_map(self, account_id, year: int = None):
        """
        Recupera i trasferimenti inviati da un conto come lista di dizionari.
        :param account_id: ID del conto mittente
        :param year: Anno di riferimento
        :return: Lista di dizionari
        """
        rows = self.db_model.fetch_sended_transfers_by_account(account_id)
        transfers = [ValidationUtils._row_to_map(row, DBTransfersColumns) for row in rows]
        return ControllerUtils.filter_transfers(transfers, year)

    def calculate_tot_amount_sent_transfers_by_account(self, account_id, year: int = None):
        """
        Calcola il totale dei trasferimenti inviati da un conto.
        :param account_id: ID del conto mittente
        :param year: Anno di riferimento
        :return: Importo totale inviato
        """
        sent_transfers = self.retrieve_sent_transfers_map_by_account(account_id, year)
        amount = sum(float(tr[DBTransfersColumns.AMOUNT.value]) for tr in sent_transfers)
        return amount

    def calculate_tot_amount_received_transfers_by_account(self, account_id, year: int = None):
        """
        Calcola il totale dei trasferimenti ricevuti da un conto.
        :param account_id: ID del conto destinatario
        :param year: Anno di riferimento
        :return: Importo totale ricevuto
        """
        received_transfers = self.retrieve_received_transfers_map_by_account(account_id, year)
        amount = sum(float(tr[DBTransfersColumns.AMOUNT.value]) for tr in received_transfers)
        return amount


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

    def __init__(self, db_model:DatabaseModel, user_controller:UserController, account_controller:AccountController,
                 invoice_controller, supplier_query_service:SupplierQueryService,
                 recurring_expenses_settings, catalogo_elenchi):
        self.db_model: DatabaseModel = db_model
        self.user_controller: UserController = user_controller
        self.account_controller: AccountController = account_controller
        self.invoice_controller = invoice_controller
        self.supplier_query_service: SupplierQueryService = supplier_query_service
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
            invoice = self.invoices_query_service.retrieve_invoice_map_by_name(invoice_name)
            if invoice != {}:
                invoice_id = invoice[DBInvoicesColumns.ID.value]

        #calcolo importo netto
        aliquota_iva = float(expense_data.get("ALIQUOTA IVA"))
        spesa_netta = float(float(spesa_lorda)/(1 + aliquota_iva))
        iva = float(spesa_lorda) - spesa_netta


        #prendo ID supplier
        supplier_id = None
        supplier_name = expense_data.get("NOME FORNITORE")
        if supplier_name:
            supplier = self.supplier_query_service.retrieve_supplier_map_by_name(supplier_name)
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

    def retrieve_expense_by_id(self, expense_id):
        """
        Recupera una expense specifica per ID, opzionalmente filtrando per l'anno corrente.
        :param expense_id: ID della expense.
        :return: Una tupla con i dati della expense oppure None.
        """
        row = self.db_model.fetch_expense_by_id(expense_id)
        return row

    def retrieve_expense_map_by_id(self, expense_id):
        """
        Recupera una expense specifica e la restituisce come dizionario,
        filtrando per l'anno corrente se specificato.
        :param expense_id: ID della expense.
        :return: Dizionario con i dati della expense oppure None.
        """
        row = self.db_model.fetch_expense_by_id(expense_id)
        return ValidationUtils._row_to_map(row, DBExpensesColumns)

    def retrieve_expense_map_by_name(self, expense_name):
        """
        Recupera una expense specifica e la restituisce come dizionario,
        filtrando per l'anno corrente se specificato.
        :param expense_name: nome della expense.
        :return: Dizionario con i dati della expense oppure None.
        """
        row = self.db_model.fetch_expense_by_name(expense_name)
        return ValidationUtils._row_to_map(row, DBExpensesColumns)

    def retrieve_expenses_map_list(self, year: int = None):
        """
        Recupera tutte le expenses e le restituisce come lista di dizionari,
        filtrandole per l'anno specificato.

        :param year:
            - None → anno corrente
            - -1   → nessun filtro
            - altro int → anno specifico
        """
        rows = self.db_model.fetch_expenses()

        expenses = [
            ValidationUtils._row_to_map(row, DBExpensesColumns)
            for row in rows
        ]

        return ControllerUtils.filter_expenses(expenses, year)

    def retrieve_expense_map_list_by_supplier(self, supplier_id, year: int = None):
        """
        Recupera tutte le spese legate a un fornitore e le restituisce come lista di dizionari,
        filtrandole per anno.

        :param supplier_id: ID del fornitore.
        :param year:
            - None → anno corrente
            - -1   → nessun filtro
            - altro int → anno specifico
        """
        rows = self.db_model.fetch_expenses_by_supplier_id(supplier_id)

        expenses = [
            ValidationUtils._row_to_map(row, DBExpensesColumns)
            for row in rows
        ]

        return ControllerUtils.filter_expenses(expenses, year)

    def retrieve_last_expense_insert_map(self):
        """
        Recupera l'ultima expense inserita e la restituisce come dizionario.
        """
        row = self.db_model.fetch_last_expense_insert()
        return ValidationUtils._row_to_map(row, DBExpensesColumns)

    def count_expenses(self, year: int = None):
        """
        Conta il numero di expenses filtrate per anno.

        :param year:
            - None → anno corrente
            - -1   → nessun filtro
            - altro int → anno specifico
        """
        expenses = self.retrieve_expenses_map_list(year=year)
        return len(expenses)

    def calculate_tot_expenses(self, year: int = None):
        """
        Calcola il totale degli importi delle expenses filtrate per anno.

        :param year:
            - None → anno corrente
            - -1   → nessun filtro
            - altro int → anno specifico
        :return: Totale (float)
        """
        expense_list = self.retrieve_expenses_map_list(year=year)

        tot = 0.0
        for expense in expense_list:
            try:
                tot += float(expense[DBExpensesColumns.TOT_AMOUNT.value])
            except (TypeError, ValueError):
                pass

        return tot

    def update_aggregate_data(self):
        return

    def create_recurring_expenses(self):
        """
        Per ogni spesa ricorrente attiva:
        - verifica se ne esiste già una nello stesso periodo di calendario
          (settimana / mese / bimestre / ecc.)
        - se non esiste, ne crea una nuova con nome {descrizione}_{dd-mm-YYYY}
        """

        print("\nControllo emissione spese ricorrenti...")

        today: date = datetime.today().date()
        all_expenses = self.retrieve_expenses_map_list()

        # --------------------------------------------------
        # Funzione: verifica se due date sono nello stesso periodo
        # --------------------------------------------------
        def is_same_period(freq: str, ref: date, candidate: date) -> bool:

            f = ExpenseController.RecurringExpensesFrequencies

            if freq == f.SETTIMANALE.value:
                start = ref - timedelta(days=7)
                return start <= candidate <= ref

            if freq == f.MENSILE.value:
                return ref.year == candidate.year and ref.month == candidate.month

            if freq == f.BIMESTRALE.value:
                return (
                        ref.year == candidate.year
                        and (ref.month - 1) // 2 == (candidate.month - 1) // 2
                )

            if freq == f.TRIMESTRALE.value:
                return (
                        ref.year == candidate.year
                        and (ref.month - 1) // 3 == (candidate.month - 1) // 3
                )

            if freq == f.QUADRIMESTRALE.value:
                return (
                        ref.year == candidate.year
                        and (ref.month - 1) // 4 == (candidate.month - 1) // 4
                )

            if freq == f.SEMESTRALE.value:
                return (
                        ref.year == candidate.year
                        and (ref.month - 1) // 6 == (candidate.month - 1) // 6
                )

            if freq == f.ANNUALE.value:
                return ref.year == candidate.year

            # fallback: stesso anno
            return ref.year == candidate.year

        # --------------------------------------------------
        # Loop principale
        # --------------------------------------------------
        for _, exp in self.recurring_expenses_settings.items():

            # 1) solo spese attive
            if not exp.status:
                print(f"Emissione di {exp.description} saltata: disattiva")
                continue

            # 2) nome spesa
            suffix = today.strftime("%d-%m-%Y")
            nominal = f"{exp.description}_{suffix}"

            # 3) normalizzazione prefisso
            prefix_norm = ControllerUtils.normalize_string_for_key(exp.description)

            found = False
            matched_name = None
            matched_date = None

            # 4) ricerca spesa già emessa nello stesso periodo
            for e in all_expenses:

                name = e[DBExpensesColumns.NAME.value]
                name_part, _, date_part = name.rpartition("_")

                if not date_part:
                    continue

                if ControllerUtils.normalize_string_for_key(name_part) != prefix_norm:
                    continue

                try:
                    dt = datetime.strptime(date_part, "%d-%m-%Y").date()
                except ValueError:
                    continue

                if is_same_period(exp.frequency, today, dt):
                    found = True
                    matched_name = name
                    matched_date = dt
                    break

            if found:
                print(
                    f"Emissione di {nominal} saltata: già presente "
                    f"({matched_name}) per il periodo {matched_date}"
                )
                continue

            # --------------------------------------------------
            # 5) Creazione nuova spesa
            # --------------------------------------------------
            acct = self.account_controller.retrieve_account_map_by_name(exp.account)
            acct_id = acct.get(DBAccountsColumns.ID.value) if acct else None

            gross = exp.amount
            iva_rate = exp.iva

            netto = round(gross / (1 + iva_rate), 2)
            iva_amt = round(gross - netto, 2)

            deductor_id = exp.deductor if exp.deductible else None

            new_exp = {
                DBExpensesColumns.NAME.value: nominal,
                DBExpensesColumns.SUPPLIER_ID.value: self.supplier_query_service
                .retrieve_supplier_map_by_name(exp.supplier)[DBSuppliersColumns.ID.value],
                DBExpensesColumns.CATEGORY.value: exp.category,
                DBExpensesColumns.NET_AMOUNT.value: netto,
                DBExpensesColumns.IVA_AMOUNT.value: iva_amt,
                DBExpensesColumns.TOT_AMOUNT.value: gross,
                DBExpensesColumns.USER_ID_DEDUZIONE.value: deductor_id,
                DBExpensesColumns.DATE.value: today.isoformat(),
                DBExpensesColumns.DEDUCIBILE.value: "Sì" if exp.deductible else "No",
                DBExpensesColumns.ACCOUNT_ID.value: acct_id,
                DBExpensesColumns.RICORRENTE.value: 1,
            }

            try:
                self.db_model.add_expense(**new_exp)
                print(f"Spesa ricorrente creata: {nominal}")
            except Exception as e:
                print(f"Errore creando spesa '{nominal}': {e}")

    def sum_expenses_for_account(self, account_id, year:int = None):
        target_year = year if year is not None else datetime.now().year
        return self.db_model.sum_expenses_by_account(account_id, year = target_year)

    def add_DB_voices_for_recurring_expenses(self):
        # Estraggo la chiave del settore di default
        default_sector_key = self.catalogo_elenchi["clients_business_sectors"][0][0]

        for expense in self.recurring_expenses_settings.values():
            supplier_name = expense.supplier
            account_name = expense.account

            # ---- FORNITORE ----
            supp_map = self.supplier_query_service.retrieve_supplier_map_by_name(supplier_name)
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

    def update_salary(self, salary_id, salary_data):
        """
        Aggiorna i dati di un salario esistente.
        :param salary_id: ID del salario da aggiornare
        :param salary_data: Dizionario contenente i dati da aggiornare
        :return: Tuple (success, message), dove success è True/False
        """
        try:
            # Controllo validità refund_id
            if not salary_id or not isinstance(salary_id, int):
                return False, "ID salario non valido. Deve essere un intero positivo."

            required_fields = {DBSalariesColumns.NAME.value, DBSalariesColumns.AMOUNT.value}

            # Validazione campi obbligatori
            missing_fields = [field for field in required_fields if not salary_data.get(field)]
            if missing_fields:
                return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

            # Validazione Importi
            if DBSalariesColumns.AMOUNT.value in salary_data:
                amount = salary_data[DBSalariesColumns.AMOUNT.value]
                if amount and not ValidationUtils.validate_amount(amount):
                    return False, "L'importo inserito non è valido."

            salary_data[DBSalariesColumns.UPDATED_AT.value] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Invoca il metodo del model per aggiornare l'utente
            self.db_model.update_salary(salary_id, **salary_data)
            return True, "Salario aggiornato con successo!"

        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento del salario: {str(e)}"

    def delete_salary(self, salary_id):
        return self.db_model.remove_salary(salary_id)

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

    def retrieve_salaries_map_list(self, year: int = None) -> list[dict]:
        """
        Recupera tutti i versamenti come lista di dizionari,
        filtrandoli per l'anno specificato.

        :param year: Anno di riferimento. None → anno corrente, -1 → nessun filtro.
        :return: Lista di dizionari con i dati dei versamenti
        """
        rows = self.db_model.fetch_all_salaries()
        # Converti le tuple in dizionari
        salaries = [ValidationUtils._row_to_map(row, DBSalariesColumns) for row in rows]

        # Applica il filtro usando il metodo statico
        return ControllerUtils.filter_salaries(salaries, year)

    def retrieve_last_salary_insert_map(self) -> dict | None:
        """
        Recupera l'ultimo versamento inserito come dizionario.
        :return: Dizionario con i dati dell'ultimo versamento oppure None.
        """
        row = self.db_model.fetch_last_salary_insert()
        return ValidationUtils._row_to_map(row, DBSalariesColumns)

    def count_salaries(self, year: int = None) -> int:
        """
        Conta il numero di versamenti-salario, applicando il filtro per l'anno specificato.

        :param year: Anno di riferimento. None → anno corrente, -1 → nessun filtro.
        :return: Numero di salaries (int).
        """
        salaries = self.retrieve_salaries_map_list(year=year)
        return len(salaries)

    def calculate_tot_salaries(self, year: int = None) -> float:
        """
        Calcola il totale degli importi dei versamenti-salario, filtrandoli per l'anno specificato.

        :param year: Anno di riferimento. None → anno corrente, -1 → nessun filtro.
        :return: Totale degli importi (float).
        """
        total = 0.0
        salary_list = self.retrieve_salaries_map_list(year=year)
        for sal in salary_list:
            total += float(sal[DBSalariesColumns.AMOUNT.value])
        return total

    def sum_salaries_for_account(self, account_id, year:int = None):
        target_year = year if year is not None else datetime.now().year
        return self.db_model.sum_salaries_by_account(account_id, year = target_year)

    def calculate_mean_salary_by_month(self, month: int, year:int = None) -> float | None:
        """
        Calculates the mean salary across all users for a specific month.

        :param month: Month as integer (1-12)
        :return: Mean salary as float, or None if no data or invalid month
        """
        # Validate month input
        if month < 1 or month > 12:
            print(f"SalaryController.calculate_mean_salary_by_month(): Invalid month {month}. Must be between 1-12.")
            return None

        try:
            # Retrieve all salaries
            salaries = self.retrieve_salaries_map_list(year = year)

            # Early return if no salaries
            if not salaries:
                print(f"SalaryController.calculate_mean_salary_by_month(): No salary data found.")
                return None

            #filter salaries based on the year
            filtered_salaries = ControllerUtils.filter_salaries(salaries = salaries, year = year)

            monthly_tot = 0.0
            count = 0

            for salary in filtered_salaries:
                # Get the date safely
                date_str = salary.get(DBSalariesColumns.DATE.value)
                if not date_str:
                    continue

                try:
                    date = datetime.strptime(date_str, '%Y-%m-%d')
                    if date.month == month:
                        amount = salary.get(DBSalariesColumns.AMOUNT.value)
                        if amount is not None:
                            monthly_tot += float(amount)
                            count += 1
                except (ValueError, TypeError) as e:
                    print(f"Warning: Invalid date format for salary: {date_str} - {e}")
                    continue

            # Return None if no salaries for this month
            if count == 0:
                print(f"No salary data found for month {month}")
                return None

            # Calculate and return mean
            mean = monthly_tot / count
            return mean

        except Exception as e:
            print(f"Error in calculate_mean_salary_by_month: {e}")
            return None


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
                 payments_analyzer_service,
                 payments_query_service,
                 refunds_query_service,
                 expenses_controller,
                 salary_controller,
                 refunds_analyzer_service,
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
        self.payments_analyzer_service = payments_analyzer_service
        self.refunds_query_service = refunds_query_service
        self.payments_query_service = payments_query_service
        self.expenses_controller = expenses_controller
        self.salary_controller = salary_controller
        self.refunds_analyzer_service = refunds_analyzer_service
        self.fiscal_settings = fiscal_settings
        self.recurring_expenses_settings = recurring_expenses_settings

    def calculate_account_balance_by_account_id(self, account_id, year:int = None, init_balance_arg:str = ""):
        account = self.account_controller.retrieve_account_map_by_id(account_id)
        balance = 0.0
        if account:
            init_balance = float(account[DBAccountsColumns.INIT_BALANCE.value]) if init_balance_arg == "" else float(init_balance_arg)

            tot_payments = self.payments_analyzer_service.sum_payments_for_account(account_id, year = year)
            tot_expenses = self.expenses_controller.sum_expenses_for_account(account_id, year = year)
            tot_rec_transf = self.transfer_controller.calculate_tot_amount_received_transfers_by_account(account_id, year = year)
            tot_sent_transf = self.transfer_controller.calculate_tot_amount_sent_transfers_by_account(account_id, year = year)
            tot_salaries = self.salary_controller.sum_salaries_for_account(account_id, year = year)
            tot_refunds = self.refunds_analyzer_service.sum_refunds_for_account(account_id, year = year)

            tot_entrate = tot_payments + tot_rec_transf + tot_refunds
            tot_uscite = tot_expenses + tot_sent_transf + tot_salaries

            balance = init_balance + float(tot_entrate) - float(tot_uscite)

        return balance

    def calculate_trimestral_iva_by_account_id(self, account_id, year:int = None):
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
        deducted_expenses = self.user_controller.retrieve_user_with_deducted_expenses_map_list(account_id, year=year)
        invoices = self.user_controller.retrieve_user_with_invoices_map_list(account_id, include_unpaid_invoices=False, year=year)
        invoices = ControllerUtils.clear_invoices_list_from_NDC_and_stornate(invoices)

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

    def calculate_tot_trimestral_iva(self, year:int = None):
        output_map = {}

        for user in self.user_controller.retrieve_users_map_list():
            if user[DBUsersColumns.REGIME_FISCALE.value] == UserController.RegimeFiscale.ORDINARIO.value:
                user_name = user[DBUsersColumns.FIRST_NAME.value] + " " + user[DBUsersColumns.LAST_NAME.value]
                user_id = user[DBUsersColumns.ID.value]
                output_map[user_name] = self.calculate_trimestral_iva_by_account_id(user_id, year=year)

        return output_map

    def retrieve_account_movements_by_account_id(self, account_id, year:int = None):
        movements = []

        # Payments (+) - Entrate
        payments = self.payments_query_service.retrieve_payments_map_list(year = year, include_unpaid_invoice_payments = False)
        filtered_payments = [p for p in payments if p[DBPaymentsColumns.CONTO_ID.value] == account_id]
        for payment in filtered_payments:
            movements.append({
                "name": payment[DBPaymentsColumns.PAYMENT_NAME.value],
                "date": payment[DBPaymentsColumns.PAYMENT_DATE.value],
                "amount": float(payment[DBPaymentsColumns.PAYMENT_AMOUNT.value]),
                "type": "Pagamento",
                "sign": "+"
            })

        # Refunds (+) - Entrate
        refunds = self.refunds_query_service.retrieve_refunds_map_list(year = year)
        filtered_refunds = [r for r in refunds if r[DBRefundsColumns.CONTO_ID.value] == account_id]
        for refund in filtered_refunds:
            movements.append({
                "name": refund[DBRefundsColumns.REFUND_NAME.value],
                "date": refund[DBRefundsColumns.REFUND_DATE.value],
                "amount": float(refund[DBRefundsColumns.REFUND_AMOUNT.value]),
                "type": "Rimborso",
                "sign": "+"
            })

        # Expenses (-) - Uscite
        expenses = self.expenses_controller.retrieve_expenses_map_list(year = year)
        filtered_expenses = [e for e in expenses if e[DBExpensesColumns.ACCOUNT_ID.value] == account_id]
        for expense in filtered_expenses:
            movements.append({
                "name": expense[DBExpensesColumns.NAME.value],
                "date": expense[DBExpensesColumns.DATE.value],
                "amount": float(expense[DBExpensesColumns.TOT_AMOUNT.value]),
                "type": "Spesa",
                "sign": "-"
            })

        # Salaries (-) - Uscite
        salaries = self.salary_controller.retrieve_salaries_map_list(year = year)
        filtered_salaries = [s for s in salaries if s[DBSalariesColumns.ACCOUNT_ID.value] == account_id]
        for salary in filtered_salaries:
            movements.append({
                "name": salary[DBSalariesColumns.NAME.value],
                "date": salary[DBSalariesColumns.DATE.value],
                "amount": float(salary[DBSalariesColumns.AMOUNT.value]),
                "type": "Stipendio",
                "sign": "-"
            })

        # Transfers (bonifici) - Possono essere entrate o uscite
        transfers = self.transfer_controller.retrieve_transfers_map_list(year = year)

        # Bonifici in entrata (ricevuti)
        incoming_transfers = [t for t in transfers if t[DBTransfersColumns.RECEIVER_ACCOUNT_ID.value] == account_id]
        for transfer in incoming_transfers:
            movements.append({
                "name": f"{transfer[DBTransfersColumns.DESCRIPTION.value]}",
                "date": transfer[DBTransfersColumns.CREATED_AT.value].split(" ")[0],
                "amount": float(transfer[DBTransfersColumns.AMOUNT.value]),
                "type": "Bonifico",
                "sign": "+"
            })

        # Bonifici in uscita (inviati)
        outgoing_transfers = [t for t in transfers if t[DBTransfersColumns.SENDER_ACCOUNT_ID.value] == account_id]
        for transfer in outgoing_transfers:
            movements.append({
                "name": f"{transfer[DBTransfersColumns.DESCRIPTION.value]}",
                "date": transfer[DBTransfersColumns.CREATED_AT.value].split(" ")[0],
                "amount": float(transfer[DBTransfersColumns.AMOUNT.value]),
                "type": "Bonifico",
                "sign": "-"
            })

        # Ordina per data (dalla più recente alla più vecchia)
        movements.sort(key=lambda x: x["date"], reverse=True)

        return movements

    def calculate_previsione_tasse_forfettaria(self, user_id, year:int = None):
        user = self.user_controller.retrieve_user_map_by_id(user_id)
        reddito_esterno = 0.0
        fatturato_willow = 0.0
        if user:
            reddito_esterno = float(user[DBUsersColumns.REDDITO_ESTERNO.value])
            fatturato_willow = self.user_controller.calcola_tot_fatturato_utente(user_id, year = year)
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

    def calculate_previsione_tasse_ordinaria(self, user_id, year:int = None):
        user = self.user_controller.retrieve_user_map_by_id(user_id)
        if not user:
            return {}

        # Recupero dati utente
        reddito_esterno = float(user.get(DBUsersColumns.REDDITO_ESTERNO.value, 0.0))
        spese_esterne = float(user.get(DBUsersColumns.SPESE_DEDOTTE_ESTERNE.value, 0.0))
        fatturato_willow = self.user_controller.calcola_tot_fatturato_utente(user_id, year = year, include_unpaid_invoices = False)
        spese_willow = self.user_controller.calcola_tot_spese_utente_dedotte(user_id, year = year)
        tot_ritenuta = self.user_controller.calcola_tot_ritenuta_acconto_ordinaria(user_id, year = year)
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

    def calculate_previsione_tasse_willow(self, year:int = None):
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
                    tasse_map, versamenti, _ = self.calculate_previsione_tasse_ordinaria(user_id, year = year)
                    saldo_willow = versamenti.get("SALDO WILLOW", 0.0)
                    acconto_willow = versamenti.get("ACCONTO WILLOW", 0.0)
                    irpef_willow = tasse_map.get("WILLOW IRPEF", 0.0)
                    inps_willow = tasse_map.get("WILLOW INPS", 0.0)

                elif regime_fiscale == self.user_controller.RegimeFiscale.FORFETTARIO.value:
                    tasse_map, versamenti, _ = self.calculate_previsione_tasse_forfettaria(user_id, year = year)
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

    def calculate_totale_crediti(self, year: int = None):
        tot_fatture = self.invoice_controller.calculate_TOT_DOCUMENTO_invoiced(year = year)
        tot_ritenuta = self.invoice_controller.calculate_RITENUTA_ACCONTO_invoiced(year = year)
        tot_pagamenti = self.payment_controller.calculate_tot_payments(year = year)

        return round(tot_fatture - tot_ritenuta - tot_pagamenti, 2)

    def retrieve_monthly_data(self, year: int = None):
        # Recupera i dati per l'anno corrente
        invoices = self.invoices_query_service.retrieve_invoices_map_list(year = year, include_unpaid_invoices = False)
        payments = self.payment_controller.retrieve_payments_map_list(year = year, include_unpaid_invoice_payments= False)
        expenses = self.expenses_controller.retrieve_expenses_map_list(year = year)
        salaries = self.salary_controller.retrieve_salaries_map_list(year = year)
        refunds = self.refunds_query_service.retrieve_refunds_map_list(year = year)

        # Inizializza la struttura per i dati mensili
        monthly_data = {month: {
            'fatturato': 0.0,
            'spese': 0.0,
            'incomes': 0.0,
            'outcomes': 0.0
        } for month in range(1, 13)}

        # Funzione di supporto per estrarre il mese dalle date
        def extract_month(date_str):
            if isinstance(date_str, datetime):
                return date_str.month
            try:
                return datetime.strptime(date_str, "%Y-%m-%d").month
            except:
                return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").month

        # 1. Calcola il fatturato (TOT_DOCUMENTO - IVA)
        for inv in invoices:
            month = extract_month(inv[DBInvoicesColumns.DATA_CREAZIONE.value])
            tot_doc = float(inv[DBInvoicesColumns.TOT_DOCUMENTO.value])
            iva = float(inv[DBInvoicesColumns.IVA.value])
            monthly_data[month]['fatturato'] += (tot_doc - iva)

        # 2. Calcola le spese (NET_AMOUNT)
        for exp in expenses:
            month = extract_month(exp[DBExpensesColumns.DATE.value])
            monthly_data[month]['spese'] += float(exp[DBExpensesColumns.NET_AMOUNT.value])

        # 3. Calcola gli incomes (NETTO_A_PAGARE + REFUND_AMOUNT)
        for pay in payments:
            month = extract_month(pay[DBPaymentsColumns.PAYMENT_DATE.value])
            monthly_data[month]['incomes'] += float(pay[DBPaymentsColumns.PAYMENT_AMOUNT.value])

        for ref in refunds:
            month = extract_month(ref[DBRefundsColumns.REFUND_DATE.value])
            monthly_data[month]['incomes'] += float(ref[DBRefundsColumns.REFUND_AMOUNT.value])

        # 4. Calcola gli outcomes (NET_AMOUNT + AMOUNT)
        for exp in expenses:
            month = extract_month(exp[DBExpensesColumns.DATE.value])
            monthly_data[month]['outcomes'] += float(exp[DBExpensesColumns.NET_AMOUNT.value])

        for sal in salaries:
            month = extract_month(sal[DBSalariesColumns.DATE.value])
            monthly_data[month]['outcomes'] += float(sal[DBSalariesColumns.AMOUNT.value])

        # Calcola le medie mensili (solo per i mesi passati se la funzione è chiamata per retrievare i dati dell'esercizio corrente, altrimenti di tutti i mesi)
        if year == datetime.now().year or year is None:
            current_month = datetime.now().month
        else:
            current_month = 12

        passed_months = [m for m in range(1, current_month + 1)]

        # Calcola i totali per i mesi passati
        totals = {k: 0.0 for k in ['fatturato', 'spese', 'incomes', 'outcomes']}
        for month in passed_months:
            for key in totals:
                totals[key] += monthly_data[month][key]

        # Calcola le medie
        averages = {
            key: (totals[key] / len(passed_months)) if passed_months else 0.0
            for key in totals
        }

        # Costruisci il risultato finale con deviazioni
        result = {}
        for month in range(1, 13):
            month_data = monthly_data[month]
            deviations = {}

            if month in passed_months:
                for key, value in month_data.items():
                    avg = averages[key]
                    if avg != 0:
                        deviations[key] = round(((value - avg) / avg) * 100, 2)
                    else:
                        deviations[key] = 0.0
            else:
                deviations = {k: None for k in month_data}

            result[month] = {
                'values': {k: round(v, 2) for k, v in month_data.items()},
                'averages': {k: round(v, 2) for k, v in averages.items()},
                'deviations': deviations
            }

        return result



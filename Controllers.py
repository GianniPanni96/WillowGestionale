import re
from datetime import datetime, timedelta, date
from Gestionale_Enums import*
from enum import Enum

import hashlib, secrets, hmac

from Controllerss.Account_controller import AccountController
from Analyzers.Salary_analyzer_service import SalaryAnalyzerService
from Analyzers.Transfer_analyzer_service import TransferAnalyzerService
from Controllerss.Salary_controller import SalaryController
from Controllerss.Transfer_controller import TransferController
from Model import DatabaseModel, DBUsersColumns, DBClientsColumns, DBInvoicesColumns, \
DBPaymentsColumns, DBProductionsColumns, DBAccountsColumns, DBExpensesColumns, \
DBSuppliersColumns, DBTransfersColumns, DBSalariesColumns, DBRefundsColumns
from QueryServices.Transfers_query_service import TransferQueryService
from QueryServices.Salaries_query_service import SalaryQueryService
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


class Analyzer:
    def __init__(self,
                 user_controller,
                 user_query_service,
                 user_analyzer_service,
                 client_controller,
                 account_controller,
                 accounts_query_service,
                 invoice_controller,
                 invoices_query_service,
                 transfer_query_service,
                 transfer_analyzer_service,
                 supplier_controller,
                 production_controller,
                 payment_controller,
                 payments_analyzer_service,
                 payments_query_service,
                 refunds_query_service,
                 expenses_query_service,
                 expenses_analyzer_service,
                 salary_query_service,
                 salary_analyzer_service,
                 refunds_analyzer_service,
                 fiscal_settings,
                 recurring_expenses_settings
                 ):
        self.user_controller = user_controller
        self.user_query_service = user_query_service
        self.user_analyzer_service = user_analyzer_service
        self.client_controller = client_controller
        self.account_controller = account_controller
        self.accounts_query_service = accounts_query_service
        self.invoice_controller = invoice_controller
        self.invoices_query_service = invoices_query_service
        self.transfer_query_service = transfer_query_service
        self.transfer_analyzer_service = transfer_analyzer_service
        self.supplier_controller = supplier_controller
        self.production_controller = production_controller
        self.payment_controller = payment_controller
        self.payments_analyzer_service = payments_analyzer_service
        self.refunds_query_service = refunds_query_service
        self.payments_query_service = payments_query_service
        self.expenses_query_service = expenses_query_service
        self.expenses_analyzer_service = expenses_analyzer_service
        self.salary_query_service = salary_query_service
        self.salary_analyzer_service = salary_analyzer_service
        self.refunds_analyzer_service = refunds_analyzer_service
        self.fiscal_settings = fiscal_settings
        self.recurring_expenses_settings = recurring_expenses_settings

    def calculate_account_balance_by_account_id(self, account_id, year:int = None, init_balance_arg:str = ""):
        account = self.accounts_query_service.retrieve_account_map_by_id(account_id)
        balance = 0.0
        if account:
            init_balance = float(account[DBAccountsColumns.INIT_BALANCE.value]) if init_balance_arg == "" else float(init_balance_arg)

            tot_payments = self.payments_analyzer_service.sum_payments_for_account(account_id, year = year)
            tot_expenses = self.expenses_analyzer_service.sum_expenses_for_account(account_id, year=year)
            tot_rec_transf = self.transfer_analyzer_service.calculate_tot_amount_received_transfers_by_account(account_id, year = year)
            tot_sent_transf = self.transfer_analyzer_service.calculate_tot_amount_sent_transfers_by_account(account_id, year = year)
            tot_salaries = self.salary_analyzer_service.sum_salaries_for_account(account_id, year = year)
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
        deducted_expenses = self.user_query_service.retrieve_user_with_deducted_expenses_map_list(account_id, year=year)
        invoices = self.user_query_service.retrieve_user_with_invoices_map_list(account_id, include_unpaid_invoices=False, year=year)
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

        for user in self.user_query_service.retrieve_users_map_list():
            if user[DBUsersColumns.REGIME_FISCALE.value] == RegimeFiscale.ORDINARIO.value:
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
        expenses = self.expenses_query_service.retrieve_expenses_map_list(year=year)
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
        salaries = self.salary_query_service.retrieve_salaries_map_list(year = year)
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
        transfers = self.transfer_query_service.retrieve_transfers_map_list(year = year)

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
        user = self.user_query_service.retrieve_user_map_by_id(user_id)
        reddito_esterno = 0.0
        fatturato_willow = 0.0
        if user:
            reddito_esterno = float(user[DBUsersColumns.REDDITO_ESTERNO.value])
            fatturato_willow = self.user_analyzer_service.calcola_tot_fatturato_utente(user_id, year = year)
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
        aliquota_irpef = float(self.user_analyzer_service.calcola_aliquota_tax_forfettaria(
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
        user = self.user_query_service.retrieve_user_map_by_id(user_id)
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
        list_of_users = self.user_query_service.retrieve_users_map_list()
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
        payments = self.payments_query_service.retrieve_payments_map_list(year = year, include_unpaid_invoice_payments= False)
        expenses = self.expenses_query_service.retrieve_expenses_map_list(year=year)
        salaries = self.salary_query_service.retrieve_salaries_map_list(year = year)
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



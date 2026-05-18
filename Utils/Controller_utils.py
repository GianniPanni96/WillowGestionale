from datetime import datetime, timedelta
from Gestionale_Enums import*
import re
from Utils.Validation_utils import ValidationUtils
import hashlib, secrets, hmac


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
                ControllerUtils.row_to_map(inv, DBInvoicesColumns)
                for inv in invoices
            )
        }

        # -------------------------
        # Pagamenti raggruppati per fattura
        # -------------------------
        all_payments = db_model.fetch_payments()
        payments_by_invoice = {}

        for p in all_payments:
            p_map = ControllerUtils.row_to_map(p, DBPaymentsColumns)
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

        invoices_map = [ControllerUtils.row_to_map(inv, DBInvoicesColumns) for inv in invoices]
        payments_map = [ControllerUtils.row_to_map(p, DBPaymentsColumns) for p in payments]

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

    # Alfabeto Crockford base32 senza I, L, O, U (no caratteri ambigui).
    _RECOVERY_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

    @staticmethod
    def generate_recovery_code() -> str:
        """16 caratteri random (Crockford base32) in 4 gruppi separati
        da trattino: XXXX-XXXX-XXXX-XXXX. ~80 bit di entropia."""
        chars = "".join(
            secrets.choice(ControllerUtils._RECOVERY_ALPHABET) for _ in range(16)
        )
        return f"{chars[0:4]}-{chars[4:8]}-{chars[8:12]}-{chars[12:16]}"

    @staticmethod
    def normalize_recovery_code(code: str) -> str:
        """Rimuove spazi/trattini e uppercase. Tollera input dell'utente
        in qualsiasi forma (con o senza dashes, lower/upper case)."""
        return "".join(ch for ch in code.upper() if ch.isalnum())

    @staticmethod
    def hash_recovery_code(code: str) -> str:
        """Riusa lo stesso formato/iterazioni di hash_password."""
        return ControllerUtils.hash_password(ControllerUtils.normalize_recovery_code(code))

    @staticmethod
    def verify_recovery_code(code: str, stored_hash: str) -> bool:
        if not stored_hash:
            return False
        return ControllerUtils.verify_password(
            ControllerUtils.normalize_recovery_code(code), stored_hash
        )

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
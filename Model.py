import sqlite3
import os
from enum import Enum
import shutil
from datetime import datetime, timedelta

# Nome della variabile d'ambiente
DB_PATH_ENV_VAR = "GESTIONALE_DB_PATH"

# Ottieni il percorso del database dalla variabile d'ambiente
db_path = os.environ.get(DB_PATH_ENV_VAR)

if not db_path:
    raise EnvironmentError(f"La variabile d'ambiente {DB_PATH_ENV_VAR} non è stata configurata.")

db_path = os.path.join(db_path, "gestionale.db")



class DBUsersColumns(Enum):
    """ SE MODIFICHI QUESTO ENUM DEVI MODIFICARE ANCHE LO SCRIPT DI CREAZIONE DELLA TABELLA E LA FUNZIONE SAVE UTENTE DELLA VIEW"""
    ID = "id"
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    PARTITA_IVA = "partita_iva"
    CODICE_FISCALE = "codice_fiscale"
    TELEFONO = "telefono"
    EMAIL = "email"
    REGIME_FISCALE = "regime_fiscale"
    ANNO_APERTURA_PIVA = "anno_apertura_piva"
    REDDITO_ESTERNO = "reddito_esterno"
    CONTO_CORRENTE_ID = "conto_corrente_id"
    PROVIDER_FATTURE = "provider_fatture"
    USERNAME_PROVIDER = "username_provider"
    PASSWORD_PROVIDER = "password_provider"
    STATUS = "status"
    PHOTO_PATH = "photo_path"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"

class DBClientsColumns(Enum):
    """ SE MODIFICHI QUESTO ENUM DEVI MODIFICARE ANCHE LO SCRIPT DI CREAZIONE DELLA TABELLA E LA FUNZIONE SAVE CLIENTE DELLA VIEW"""
    ID = "id"
    NAME = "name"
    PARTITA_IVA = "partita_iva"
    EMAIL = "email"
    SEDE_LEGALE = "sede_legale"
    SETTORE = "settore"
    TIPOLOGIA = "tipologia"
    REFERENTE = "referente"
    CONTATTO_REFERENTE = "contatto_referente"
    NOTE = "note"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"

class DBInvoicesColumns(Enum):
    """ SE MODIFICHI QUESTO ENUM DEVI MODIFICARE ANCHE LO SCRIPT DI CREAZIONE DELLA TABELLA E LA FUNZIONE SAVE INVOICE DELLA VIEW"""

    ID = "id" #db
    NUMERO_FATTURA = "numero_fattura" #view
    DATA_CREAZIONE = "creation_date" #view
    DATA_SCADENZA_1 = "expiration_date_1" #controller -> funzione di rate
    DATA_SCADENZA_2 = "expiration_date_2"
    DATA_SCADENZA_3 = "expiration_date_3"
    ID_UTENTE = "invoicer_id" #controller(view)
    ID_CLIENTE = "client_id" #controller(view)
    ID_CONTO = "ID_CONTO"
    NOTE = "note" #view
    SERVIZI = "importo_servizi" #view (comprensivo di rivalsa)
    CASSA_INPS = "cassa_inps" #controller -> servizi*coeff redditività*aliquota INPS
    IMPONIBILE = "imponibile" #controller -> servizi*coeff redditività
    IVA = "iva" #controller = 0
    RIMBORSI = "rimborsi" #view
    RIVALSA_INPS = "rivalsa_inps"
    TOT_DOCUMENTO = "tot_documento"
    RITENUTA = "ritenuta" #controller = 0
    NETTO_A_PAGARE = "netto_a_pagare" #controller = 0
    STATUS = "status" #controller -> default: emessa
    METODO_PAGAMENTO = "metodo_pagamento" #view
    NUMERO_RATE = "rate_totali" #view
    TIPO = "tipo"  # se è nota di credito #view
    ID_FATTURA_ASSOCIATA = "id_fattura_associata"  #view (a comparsa)
    ID_PRODUZIONE_ASSOCIATA = "id_produzione_associata"
    CREATED_AT = "created_at" #db
    UPDATED_AT = "updated_at" #db

class DBPaymentsColumns(Enum):
    """ SE MODIFICHI QUESTO ENUM DEVI MODIFICARE ANCHE LO SCRIPT DI CREAZIONE DELLA TABELLA E LA FUNZIONE SAVE PAYMENT DELLA VIEW"""

    ID = "ID"
    PAYMENT_NAME = "PAYMENT_NAME" #NomeCliente_NomeProduzione_NomeFattura_1/2/3
    PAYMENT_AMOUNT = "PAYMENT_AMOUNT"
    PAYMENT_DATE = "PAYMENT_DATE"
    LINKED_RATA = "LINKED_RATA" # 1, 2, 3
    INVOICE_ID = "INVOICE_ID"
    CONTO_ID = "CONTO_ID"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"

class DBProductionsColumns(Enum):
    ID = "ID"
    NAME = "NAME"
    CLIENT_ID = "CLIENT_ID"
    HOURS = "HOURS"
    TIPOLOGIA_PRODUZIONE = "TIPOLOGIA_PRODUZIONE"
    TIPOLOGIA_OUTPUT = "TIPOLOGIA_OUTPUT"
    STATO = "STATO"
    END_DATE = "END_DATE"
    TOTALE_PREVENTIVO = "TOTALE_PREVENTIVO"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"

class DBAccountsColumns(Enum):
    ID = "ID"
    NAME = "NAME"
    INIT_BALANCE = "INIT_BALANCE"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"

class DBTransfersColumns(Enum):
    ID = "ID"
    DESCRIPTION = "CAUSALE"
    AMOUNT = "IMPORTO"
    SENDER_ACCOUNT_ID = "ID_CONTO_MITTENTE"
    RECEIVER_ACCOUNT_ID = "ID_CONTO_RICEVENTE"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


class DBExpensesColumns(Enum):
    ID = "ID"
    NAME = "NOME"
    USER_ID = "ID_UTENTE"
    SUPPLIER_ID = "ID_FORNITORE"
    CATEGORY = "CATEGORIA"
    NET_AMOUNT = "IMPORTO_NETTO"
    IVA_AMOUNT = "IMPORTO_IVA"
    TOT_AMOUNT = "IMPORTO_LORDO"
    DATE = "DATA_PAGAMENTO"
    DEDUCIBILE = "DEDUCIBILE"
    ACCOUNT_ID = "ID_CONTO"
    LINKED_INVOICE_ID = "ID_FATTURA_COLLEGATA"
    created_at = "created_at"
    updated_at = "updated_at"

class DBSuppliersColumns(Enum):
    ID = "ID"
    NAME = "NOME"
    PARTITA_IVA = "PARTITA_IVA"
    SEDE = "SEDE"
    CONTATTO = "CONTATTO_REFERENTE"
    CATEGORIA = "CATEGORIA"
    NOTE = "NOTE"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"




class DatabaseModel:
    def __init__(self, db_path):
        """ Inizializza il percorso al database """
        self.db_path = db_path

    def _connect(self):
        """ Crea una nuova connessione al database """
        return sqlite3.connect(self.db_path)

    # Funzioni generali
    def delete_row(self, table_name, primary_key_column, primary_key_value):
        """ Elimina una riga dalla tabella specificata """
        query = f"DELETE FROM {table_name} WHERE {primary_key_column} = ?"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (primary_key_value,))
            conn.commit()

    def update_row(self, table_name, column_name, new_value, primary_key_column, primary_key_value):
        """ Aggiorna una colonna specifica in una riga della tabella """
        query = f"UPDATE {table_name} SET {column_name} = ? WHERE {primary_key_column} = ?"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (new_value, primary_key_value))
            conn.commit()

    def fetch_table(self, table_name):
        query = f"SELECT * FROM {table_name}"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()




    # Funzioni per gli utenti (users)
    def fetch_users(self):
        """ Recupera tutti gli utenti dal database """
        query = "SELECT * FROM users"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def fetch_user_by_id(self, user_id):
        """Recupera uno specifico utente"""
        query = "SELECT * FROM users WHERE id = ?"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id,))
            return cursor.fetchone()

    def fetch_user_by_fullname(self, user_first_name, user_last_name):
        """Recupera uno specifico utente"""
        query = "SELECT * FROM users WHERE first_name = ? AND last_name = ?"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_first_name, user_last_name))
            return cursor.fetchone()

    def add_user(self, **kwargs):
        """
        Aggiungi un nuovo utente nella tabella `users`.
        I campi da aggiungere devono essere passati come keyword arguments.
        """
        # Estrarre le colonne valide dall'Enum
        valid_columns = {column.value for column in DBUsersColumns}
        insert_fields = {key: value for key, value in kwargs.items() if key in valid_columns}

        if not insert_fields:
            raise ValueError("Nessun campo valido specificato per l'inserimento.")

        # Creazione dinamica della query SQL
        columns = ", ".join(insert_fields.keys())
        placeholders = ", ".join(["?"] * len(insert_fields))
        query = f"INSERT INTO users ({columns}) VALUES ({placeholders})"

        # Esecuzione della query
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(insert_fields.values()))
            conn.commit()

    def update_user(self, user_id, **kwargs):
        """
        Aggiorna i valori di un utente esistente nella tabella `users`.
        I campi da aggiornare devono essere passati come keyword arguments.

        :param user_id: ID dell'utente da aggiornare
        :param kwargs: Campi da aggiornare (anche `None` per settare `NULL`)
        :raises ValueError: Se non vengono specificati campi validi per l'aggiornamento
        """
        # Controllo che i campi passati siano validi
        valid_columns = {column.value for column in DBUsersColumns}
        update_fields = {key: value for key, value in kwargs.items() if key in valid_columns}

        if not update_fields:
            raise ValueError("Nessun campo valido specificato per l'aggiornamento.")

        # Creazione dinamica della query SQL senza COALESCE per permettere valori NULL
        set_clause = ", ".join([f"{field} = ?" for field in update_fields.keys()])
        query = f"UPDATE users SET {set_clause} WHERE {DBUsersColumns.ID.value} = ?"

        # Esecuzione della query
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (*update_fields.values(), user_id))
                conn.commit()
        except Exception as e:
            raise RuntimeError(f"Errore durante l'aggiornamento dell'utente: {str(e)}")

    def update_user_tax_rate(self, user_id, new_tax_rate):
        """
        Aggiorna l'aliquota fiscale di un utente.
        :param user_id: ID dell'utente.
        :param new_tax_rate: Nuova aliquota fiscale.
        """
        query = f"UPDATE Users SET {DBUsersColumns.ALIQUOTA_TAX.value} = ? WHERE {DBUsersColumns.ID.value} = ?"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (new_tax_rate, user_id))
            conn.commit()

    def fetch_user_with_invoices(self, user_id):
        """
        Recupera lo specifico user unito alle rispettive fatture.
        Utilizza un LEFT JOIN per includere tutti gli users anche se non hanno fatture.
        Ritorna una lista di tuple, in cui le colonne dei client compaiono per prime,
        seguite dalle colonne delle fatture (che possono essere NULL se non esistono).
        """
        # Costruzione dinamica delle colonne per clients e invoices
        user_columns = [f"u.{col.value}" for col in DBUsersColumns]
        invoice_columns = [f"i.{col.value}" for col in DBInvoicesColumns]
        all_columns = user_columns + invoice_columns

        query = f"""
        SELECT {', '.join(all_columns)}
        FROM users u
        LEFT JOIN invoices i ON i.{DBInvoicesColumns.ID_UTENTE.value} = u.{DBUsersColumns.ID.value}
        WHERE u.{DBUsersColumns.ID.value} = ?
        """

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id,))
            return cursor.fetchall()

    def fetch_user_with_expenses(self, user_id):
        """
        Recupera lo specifico user unito alle rispettive spese anticipate.
        Utilizza un LEFT JOIN per includere tutti gli users anche se non hanno spese.
        Ritorna una lista di tuple, in cui le colonne dello user compaiono per prime,
        seguite dalle colonne delle spese (che possono essere NULL se non esistono).
        """
        # Costruzione dinamica delle colonne per clients e invoices
        user_columns = [f"u.{col.value}" for col in DBUsersColumns]
        expenses_columns = [f"e.{col.value}" for col in DBExpensesColumns]
        all_columns = user_columns + expenses_columns

        query = f"""
        SELECT {', '.join(all_columns)}
        FROM users u
        LEFT JOIN expenses e ON e.{DBExpensesColumns.USER_ID.value} = u.{DBUsersColumns.ID.value}
        WHERE u.{DBUsersColumns.ID.value} = ?
        """

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id,))
            return cursor.fetchall()










    # Funzioni per i clienti (clients)
    def fetch_clients(self):
        """ Recupera tutti i clienti """
        query = "SELECT * FROM clients"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def add_client(self, **kwargs):
        """Aggiungi un nuovo cliente, utilizzando campi dinamici basati sull'Enum."""
        columns = [column.value for column in DBClientsColumns if column.value in kwargs]
        placeholders = ", ".join(["?"] * len(columns))
        query = f"INSERT INTO clients ({', '.join(columns)}) VALUES ({placeholders})"

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(kwargs[column] for column in columns))
            conn.commit()

    def fetch_client_by_id(self, client_id):
        """Recupera uno specifico cliente in modo dinamico."""
        columns = [column.value for column in DBClientsColumns]
        query = f"SELECT {', '.join(columns)} FROM clients WHERE {DBClientsColumns.ID.value} = ?"

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (client_id,))
            return cursor.fetchone()

    def fetch_client_by_name(self, client_name):
        """Recupera uno specifico cliente per nome."""
        query = "SELECT * FROM clients WHERE name = ?"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (client_name,))
            return cursor.fetchone()

    def fetch_clients_with_invoices(self):
        """
        Recupera tutti i client uniti alle rispettive fatture.
        Utilizza un LEFT JOIN per includere tutti i client anche se non hanno fatture.
        Ritorna una lista di tuple, in cui le colonne dei client compaiono per prime,
        seguite dalle colonne delle fatture (che possono essere NULL se non esistono).
        """
        # Costruzione dinamica delle colonne per clients e invoices
        client_columns = [f"c.{col.value}" for col in DBClientsColumns]
        invoice_columns = [f"i.{col.value}" for col in DBInvoicesColumns]
        all_columns = client_columns + invoice_columns

        query = f"""
        SELECT {', '.join(all_columns)}
        FROM clients c
        LEFT JOIN invoices i ON i.{DBInvoicesColumns.ID_CLIENTE.value} = c.{DBClientsColumns.ID.value}
        """

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def fetch_client_with_invoices(self, client_id):
        """
        Recupera lo specifico client unito alle rispettive fatture.
        Utilizza un LEFT JOIN per includere tutti i client anche se non hanno fatture.
        Ritorna una lista di tuple, in cui le colonne dei client compaiono per prime,
        seguite dalle colonne delle fatture (che possono essere NULL se non esistono).
        """
        # Costruzione dinamica delle colonne per clients e invoices
        client_columns = [f"c.{col.value}" for col in DBClientsColumns]
        invoice_columns = [f"i.{col.value}" for col in DBInvoicesColumns]
        all_columns = client_columns + invoice_columns

        query = f"""
        SELECT {', '.join(all_columns)}
        FROM clients c
        LEFT JOIN invoices i ON i.{DBInvoicesColumns.ID_CLIENTE.value} = c.{DBClientsColumns.ID.value}
        WHERE c.{DBClientsColumns.ID.value} = ?
        """

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (client_id,))
            return cursor.fetchall()

    def fetch_outstanding_by_client(self, client_id):
        """
        Ritorna un dizionario { invoice_id: remaining_due } per tutte le fatture
        del cliente specificato. Il restante da pagare è calcolato come
          netto_a_pagare - SUM(payment_amount)
        (con SUM=0 se non ci sono pagamenti).
        """
        # Nomi di colonna presi dagli enum
        inv_id_col = DBInvoicesColumns.ID.value
        netto_col = DBInvoicesColumns.NETTO_A_PAGARE.value
        pay_amt_col = DBPaymentsColumns.PAYMENT_AMOUNT.value
        pay_fk_col = DBPaymentsColumns.INVOICE_ID.value
        client_fk_col = DBInvoicesColumns.ID_CLIENTE.value

        query = f"""
        SELECT
          i.{inv_id_col}   AS invoice_id,
          i.{netto_col} - COALESCE(SUM(p.{pay_amt_col}), 0) AS remaining
        FROM invoices i
        LEFT JOIN payments p
          ON p.{pay_fk_col} = i.{inv_id_col}
        WHERE i.{client_fk_col} = ?
        GROUP BY i.{inv_id_col}, i.{netto_col}
        """

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(query, (client_id,))
            rows = cur.fetchall()

        # Costruisci il dizionario
        # Ogni row è (invoice_id, remaining)
        return {row[0]: float(row[1]) for row in rows}







    # Funzioni per le fatture (invoices)
    def fetch_invoices(self):
        """ Recupera tutte le fatture """
        query = "SELECT * FROM invoices"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def add_invoice(self, **kwargs):
        """
        Aggiungi una nuova fattura
        I campi da aggiungere devono essere passati come keyword arguments
        """
        # Estrarre le colonne valide dall'Enum
        valid_columns = {column.value for column in DBInvoicesColumns}
        insert_fields = {key: value for key, value in kwargs.items() if key in valid_columns}

        if not insert_fields:
            raise ValueError("Nessun campo valido specificato per l'inserimento.")

        # Creazione dinamica della query SQL
        columns = ", ".join(insert_fields.keys())
        placeholders = ", ".join(["?"] * len(insert_fields))
        query = f"INSERT INTO invoices ({columns}) VALUES ({placeholders})"

        # Esecuzione della query
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(insert_fields.values()))
            conn.commit()

    def fetch_invoice_by_id(self, invoice_id):
        """Recupera una specifica fattura in modo dinamico."""
        columns = [column.value for column in DBInvoicesColumns]
        query = f"SELECT {', '.join(columns)} FROM invoices WHERE {DBInvoicesColumns.ID.value} = ?"

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (invoice_id,))
            return cursor.fetchone()

    def fetch_invoice_by_name(self, invoice_name):
        """Recupera una specifica fattura in modo dinamico."""
        columns = [column.value for column in DBInvoicesColumns]
        query = f"SELECT {', '.join(columns)} FROM invoices WHERE {DBInvoicesColumns.NUMERO_FATTURA.value} = ?"

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (invoice_name,))
            return cursor.fetchone()

    def fetch_invoices_by_user_id(self, user_id):
        """Recupera una specifica fattura in modo dinamico."""
        columns = [column.value for column in DBInvoicesColumns]
        query = f"SELECT {', '.join(columns)} FROM invoices WHERE {DBInvoicesColumns.ID_UTENTE.value} = ?"

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id,))
            return cursor.fetchall()

    def fetch_invoices_by_client_id(self, client_id):
        """Recupera una specifica fattura in modo dinamico."""
        columns = [column.value for column in DBInvoicesColumns]
        query = f"SELECT {', '.join(columns)} FROM invoices WHERE {DBInvoicesColumns.ID_CLIENTE.value} = ?"

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (client_id,))
            return cursor.fetchall()

    def fetch_invoices_by_prod_id(self, prod_id):
        """Recupera una specifica fattura in modo dinamico."""
        columns = [column.value for column in DBInvoicesColumns]
        query = f"SELECT {', '.join(columns)} FROM invoices WHERE {DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value} = ?"

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (prod_id,))
            return cursor.fetchall()

    def fetch_last_invoice_insert(self):
        """
        Recupera l'ultima fattura inserita nel database, ordinando in base alla colonna CREATED_AT.
        :return: Un dizionario contenente i dati dell'ultima fattura oppure None se non viene trovata.
        """
        columns = [column.value for column in DBInvoicesColumns]
        query = f"SELECT {', '.join(columns)} FROM invoices ORDER BY {DBInvoicesColumns.CREATED_AT.value} DESC LIMIT 1"

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchone()

    def modify_invoice_datum(self, invoice_id, column, datum):
        """
        Modifica la specifica fattura inserendo il dato nella colonna passata come argomento.
        :param invoice_id: ID della fattura da modificare
        :param column: Colonna da modificare.
        :param datum: Dato da inserire.
        """
        query = f"UPDATE Invoices SET {column} = ? WHERE {DBInvoicesColumns.ID.value} = ?"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (datum, invoice_id))
            conn.commit()

    def fetch_invoices_with_payments(self):
        """
        Recupera tutte le fatture unite ai dati dei pagamenti associati.
        Utilizza un LEFT JOIN per includere tutte le fatture anche se non hanno pagamenti.

        Ritorna una lista di tuple, in cui le colonne delle fatture compaiono per prime,
        seguite dalle colonne dei pagamenti (che possono essere NULL se non esistono).
        """
        # Costruzione dinamica delle colonne per invoices e payments
        invoice_columns = [f"i.{col.value}" for col in DBInvoicesColumns]
        payment_columns = [f"p.{col.value}" for col in DBPaymentsColumns]
        all_columns = invoice_columns + payment_columns

        query = f"""
        SELECT {', '.join(all_columns)}
        FROM invoices i
        LEFT JOIN payments p ON i.{DBInvoicesColumns.ID.value} = p.{DBPaymentsColumns.INVOICE_ID.value}
        """

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def fetch_invoices_with_productions(self):
        """
        Recupera tutte le fatture unite ai dati delle produzioni associate.
        Utilizza un LEFT JOIN

        Ritorna una lista di tuple, in cui le colonne delle fatture compaiono per prime,
        seguite dalle colonne delle produzioni.
        """
        # Costruzione dinamica delle colonne per invoices e payments
        invoice_columns = [f"i.{col.value}" for col in DBInvoicesColumns]
        production_columns = [f"p.{col.value}" for col in DBProductionsColumns]
        all_columns = invoice_columns + production_columns

        query = f"""
        SELECT {', '.join(all_columns)}
        FROM invoices i
        LEFT JOIN productions p ON i.{DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value} = p.{DBProductionsColumns.ID.value}
        """

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def fetch_invoice_with_payments(self, invoice_id):
        """
        Recupera la specifca fattura unita ai rispetttivi pagamenti.
        Utilizza un LEFT JOIN.
        Ritorna una lista di tuple, in cui le colonne della fattura compaiono per prime,
        seguite dalle colonne dei pagamenti (che possono essere NULL se non esistono).
        """
        # Costruzione dinamica delle colonne per clients e invoices
        invoice_columns = [f"i.{col.value}" for col in DBInvoicesColumns]
        payment_columns = [f"p.{col.value}" for col in DBPaymentsColumns]
        all_columns = invoice_columns + payment_columns

        query = f"""
        SELECT {', '.join(all_columns)}
        FROM invoices i
        LEFT JOIN payments p ON p.{DBPaymentsColumns.INVOICE_ID.value} = i.{DBInvoicesColumns.ID.value}
        WHERE i.{DBInvoicesColumns.ID.value} = ?
        """

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (invoice_id,))
            return cursor.fetchall()

    def fetch_invoice_with_expenses(self, invoice_id):
        """
        Recupera la specifca fattura unita alle rispettive spese di produzione.
        Utilizza un LEFT JOIN.
        Ritorna una lista di tuple, in cui le colonne della fattura compaiono per prime,
        seguite dalle colonne delle spese (che possono essere NULL se non esistono).
        """
        # Costruzione dinamica delle colonne per expenses e invoices
        invoice_columns = [f"i.{col.value}" for col in DBInvoicesColumns]
        expense_columns = [f"e.{col.value}" for col in DBExpensesColumns]
        all_columns = invoice_columns + expense_columns

        query = f"""
        SELECT {', '.join(all_columns)}
        FROM invoices i
        LEFT JOIN expenses e ON e.{DBExpensesColumns.LINKED_INVOICE_ID.value} = i.{DBInvoicesColumns.ID.value}
        WHERE i.{DBInvoicesColumns.ID.value} = ?
        """

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (invoice_id,))
            return cursor.fetchall()

    def fetch_unpaid_invoices(self):
        """
        Recupera una lista di fatture a cui non è associato alcun pagamento.

        Utilizza una LEFT JOIN tra la tabella invoices e payments e filtra le fatture
        per cui non esiste corrispondenza (ovvero, la colonna ID di payments risulta NULL).

        Ritorna una lista di tuple contenenti i dati delle fatture.
        """
        query = f"""
        SELECT i.*
        FROM invoices i
        LEFT JOIN payments p ON i.{DBInvoicesColumns.ID.value} = p.{DBPaymentsColumns.INVOICE_ID.value}
        WHERE p.{DBPaymentsColumns.ID.value} IS NULL
        """
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()







    # Funzioni per i pagamenti (payments)
    def fetch_payments(self):
        """ Recupera tutti i pagamenti """
        query = "SELECT * FROM payments"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def add_payment(self, **kwargs):
        """
        Aggiungi un nuovo payment.
        I campi da aggiungere devono essere passati come keyword arguments.
        """
        # Estrarre le colonne valide dall'Enum dei payments
        valid_columns = {column.value for column in DBPaymentsColumns}
        insert_fields = {key: value for key, value in kwargs.items() if key in valid_columns}

        if not insert_fields:
            raise ValueError("Nessun campo valido specificato per l'inserimento.")

        # Creazione dinamica della query SQL per la tabella payments
        columns = ", ".join(insert_fields.keys())
        placeholders = ", ".join(["?"] * len(insert_fields))
        query = f"INSERT INTO payments ({columns}) VALUES ({placeholders})"

        # Esecuzione della query
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(insert_fields.values()))
            conn.commit()

    def fetch_payment_by_id(self, payment_id):
        """
        Recupera un payment specifico in modo dinamico.
        """
        # Creazione della lista delle colonne dal DBPaymentsColumns
        columns = [column.value for column in DBPaymentsColumns]
        query = f"SELECT {', '.join(columns)} FROM payments WHERE {DBPaymentsColumns.ID.value} = ?"

        # Esecuzione della query
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (payment_id,))
            return cursor.fetchone()

    def fetch_payments_by_invoice_id(self, invoice_id):
        """
        Recupera dei payments specifici in modo dinamico.
        """
        # Creazione della lista delle colonne dal DBPaymentsColumns
        columns = [column.value for column in DBPaymentsColumns]
        query = f"SELECT {', '.join(columns)} FROM payments WHERE {DBPaymentsColumns.INVOICE_ID.value} = ?"

        # Esecuzione della query
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (invoice_id,))
            return cursor.fetchall()

    def fetch_last_payment_insert(self):
        """
        Recupera l'ultimo pagamento inserito nel database, ordinando in base alla colonna PAYMENT_DATE.
        :return: Una tupla contenente i dati dell'ultimo pagamento oppure None se non viene trovato.
        """
        columns = [column.value for column in DBPaymentsColumns]
        query = f"SELECT {', '.join(columns)} FROM payments ORDER BY {DBPaymentsColumns.UPDATED_AT.value} DESC LIMIT 1"

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchone()

    def update_payment(self, payment_id, **kwargs):
        """
        Aggiorna i valori di un pagamento esistente nella tabella `payments`.
        I campi da aggiornare devono essere passati come keyword arguments.

        :param payment_id: ID del pagamento da aggiornare.
        :param kwargs: Campi da aggiornare (anche `None` per settare `NULL`).
        :raises ValueError: Se non vengono specificati campi validi per l'aggiornamento.
        """
        # Controllo che i campi passati siano validi per la tabella payments
        valid_columns = {column.value for column in DBPaymentsColumns}
        update_fields = {key: value for key, value in kwargs.items() if key in valid_columns}

        if not update_fields:
            raise ValueError("Nessun campo valido specificato per l'aggiornamento.")

        # Creazione dinamica della query SQL
        set_clause = ", ".join([f"{field} = ?" for field in update_fields.keys()])
        query = f"UPDATE payments SET {set_clause} WHERE {DBPaymentsColumns.ID.value} = ?"

        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (*update_fields.values(), payment_id))
                conn.commit()
        except Exception as e:
            raise RuntimeError(f"Errore durante l'aggiornamento del pagamento: {str(e)}")

    def fetch_payments_with_invoice(self):
        """
        Recupera i dati dei pagamenti uniti ai dati delle fatture tramite la foreign key INVOICE_ID.

        Ritorna una lista di tuple, in cui ogni tupla contiene i dati delle colonne della tabella
        payments seguiti dai dati delle colonne della tabella invoices.
        """
        # Costruzione dinamica della lista delle colonne da entrambe le tabelle
        payment_columns = [f"p.{col.value}" for col in DBPaymentsColumns]
        invoice_columns = [f"i.{col.value}" for col in DBInvoicesColumns]
        all_columns = payment_columns + invoice_columns

        query = f"""
        SELECT {', '.join(all_columns)}
        FROM payments p
        JOIN invoices i ON p.{DBPaymentsColumns.INVOICE_ID.value} = i.{DBInvoicesColumns.ID.value}
        """

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def sum_payments_by_account(self, account_id: int) -> float:
        """
        Restituisce la somma degli importi dei pagamenti effettuati su uno specifico conto.

        :param account_id: l'ID del conto (DBAccountsColumns.ID)
        :return: somma (float), 0.0 se non ci sono pagamenti
        """
        # Nome colonna importo e colonna conto
        amt_col = DBPaymentsColumns.PAYMENT_AMOUNT.value
        conto_col = DBPaymentsColumns.CONTO_ID.value

        query = f"""
        SELECT SUM({amt_col})
        FROM payments
        WHERE {conto_col} = ?
        """

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(query, (account_id,))
            result = cur.fetchone()[0]
            return result if result is not None else 0.0










    def fetch_expenses(self):
        """Recupera tutte le spese (expenses)."""
        query = "SELECT * FROM expenses"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def add_expense(self, **kwargs):
        """
        Aggiunge una nuova expense.
        I campi da inserire devono essere passati come keyword arguments.
        """
        # Estrae le colonne valide dall'enum DBExpensesColumns
        valid_columns = {column.value for column in DBExpensesColumns}
        insert_fields = {key: value for key, value in kwargs.items() if key in valid_columns}

        if not insert_fields:
            raise ValueError("Nessun campo valido specificato per l'inserimento.")

        # Costruisce dinamicamente la query SQL
        columns = ", ".join(insert_fields.keys())
        placeholders = ", ".join(["?"] * len(insert_fields))
        query = f"INSERT INTO expenses ({columns}) VALUES ({placeholders})"

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(insert_fields.values()))
            conn.commit()

    def fetch_expense_by_id(self, expense_id):
        """
        Recupera una expense specifica dato il suo id.
        """
        columns = [column.value for column in DBExpensesColumns]
        query = f"SELECT {', '.join(columns)} FROM expenses WHERE {DBExpensesColumns.ID.value} = ?"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (expense_id,))
            return cursor.fetchone()

    def fetch_expenses_by_account_id(self, account_id):
        """
        Recupera le expenses associate a un account specifico.
        (Puoi cambiare il criterio di ricerca in base alle tue esigenze.)
        """
        columns = [column.value for column in DBExpensesColumns]
        query = f"SELECT {', '.join(columns)} FROM expenses WHERE {DBExpensesColumns.ACCOUNT_ID.value} = ?"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (account_id,))
            return cursor.fetchall()

    def fetch_last_expense_insert(self):
        """
        Recupera l'ultima expense inserita, ordinando in base alla colonna updated_at.
        Ritorna una tupla con i dati dell'ultima expense oppure None se non viene trovata.
        """
        columns = [column.value for column in DBExpensesColumns]
        query = f"SELECT {', '.join(columns)} FROM expenses ORDER BY {DBExpensesColumns.updated_at.value} DESC LIMIT 1"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchone()

    def sum_expenses_by_account(self, account_id: int) -> float:
        """
        Restituisce la somma degli importi dei pagamenti effettuati su uno specifico conto.

        :param account_id: l'ID del conto (DBAccountsColumns.ID)
        :return: somma (float), 0.0 se non ci sono pagamenti
        """
        # Nome colonna importo e colonna conto
        amt_col = DBExpensesColumns.TOT_AMOUNT.value
        conto_col = DBExpensesColumns.ACCOUNT_ID.value

        query = f"""
        SELECT SUM({amt_col})
        FROM expenses
        WHERE {conto_col} = ?
        """

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(query, (account_id,))
            result = cur.fetchone()[0]
            return result if result is not None else 0.0






    def fetch_suppliers(self):
        """Recupera tutti i suppliers."""
        query = "SELECT * FROM suppliers"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def add_supplier(self, **kwargs):
        """
        Aggiunge un nuovo supplier utilizzando campi dinamici basati sull'Enum.

        I campi da inserire devono essere passati come keyword arguments.
        """
        # Estrae le colonne valide dall'enum DBSuppliersColumns
        columns = [column.value for column in DBSuppliersColumns if column.value in kwargs]
        if not columns:
            raise ValueError("Nessun campo valido specificato per l'inserimento.")
        placeholders = ", ".join(["?"] * len(columns))
        query = f"INSERT INTO suppliers ({', '.join(columns)}) VALUES ({placeholders})"

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(kwargs[column] for column in columns))
            conn.commit()

    def fetch_supplier_by_id(self, supplier_id):
        """
        Recupera uno specifico supplier in modo dinamico.
        :param supplier_id: ID del supplier.
        :return: Una tupla con i dati del supplier oppure None.
        """
        columns = [column.value for column in DBSuppliersColumns]
        query = f"SELECT {', '.join(columns)} FROM suppliers WHERE {DBSuppliersColumns.ID.value} = ?"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (supplier_id,))
            return cursor.fetchone()

    def fetch_supplier_by_name(self, supplier_name):
        """
        Recupera uno specifico supplier per nome.
        :param supplier_name: Nome del supplier.
        :return: Una tupla con i dati del supplier oppure None.
        """
        query = f"SELECT * FROM suppliers WHERE {DBSuppliersColumns.NAME.value} = ?"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (supplier_name,))
            return cursor.fetchone()

    def fetch_supplier_with_expenses(self, supplier_id):
        """
        Recupera lo specifico supplier unito alle rispettive spese.
        Utilizza un LEFT JOIN per includere tutti i client anche se non hanno spese.
        Ritorna una lista di tuple, in cui le colonne dei supplier compaiono per prime,
        seguite dalle colonne delle spese (che possono essere NULL se non esistono).
        """
        # Costruzione dinamica delle colonne per clients e invoices
        supplier_columns = [f"s.{col.value}" for col in DBSuppliersColumns]
        expense_columns = [f"e.{col.value}" for col in DBExpensesColumns]
        all_columns = supplier_columns + expense_columns

        query = f"""
        SELECT {', '.join(all_columns)}
        FROM suppliers s
        LEFT JOIN expenses e ON e.{DBExpensesColumns.SUPPLIER_ID.value} = s.{DBSuppliersColumns.ID.value}
        WHERE s.{DBSuppliersColumns.ID.value} = ?
        """

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (supplier_id,))
            return cursor.fetchall()

    def fetch_last_supplier_insert(self):
        """
        Recupera l'ultimo supplier inserito nel database, ordinando in base alla colonna CREATED_AT.
        :return: Un dizionario contenente i dati dell'ultimo supplier oppure None se non viene trovata.
        """
        columns = [column.value for column in DBSuppliersColumns]
        query = f"SELECT {', '.join(columns)} FROM suppliers ORDER BY {DBSuppliersColumns.CREATED_AT.value} DESC LIMIT 1"

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchone()








    def fetch_productions(self):
        """Recupera tutte le produzioni"""
        query = "SELECT * FROM productions"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def add_production(self, **kwargs):
        """
        Aggiungi una nuova production.
        I campi da aggiungere devono essere passati come keyword arguments.
        """
        # Estrarre le colonne valide dall'Enum dei productions
        valid_columns = {column.value for column in DBProductionsColumns}
        insert_fields = {key: value for key, value in kwargs.items() if key in valid_columns}

        if not insert_fields:
            raise ValueError("Nessun campo valido specificato per l'inserimento.")

        # Creazione dinamica della query SQL per la tabella productions
        columns = ", ".join(insert_fields.keys())
        placeholders = ", ".join(["?"] * len(insert_fields))
        query = f"INSERT INTO productions ({columns}) VALUES ({placeholders})"

        # Esecuzione della query
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(insert_fields.values()))
            conn.commit()

    def fetch_production_by_id(self, production_id):
        """
        Recupera una production specifica in modo dinamico.
        """
        # Creazione della lista delle colonne dal DBProductionsColumns
        columns = [column.value for column in DBProductionsColumns]
        query = f"SELECT {', '.join(columns)} FROM productions WHERE {DBProductionsColumns.ID.value} = ?"

        # Esecuzione della query
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (production_id,))
            return cursor.fetchone()

    def fetch_production_by_name(self, production_name):
        """
        Recupera una production specifica in modo dinamico.
        """
        # Creazione della lista delle colonne dal DBProductionsColumns
        columns = [column.value for column in DBProductionsColumns]
        query = f"SELECT {', '.join(columns)} FROM productions WHERE {DBProductionsColumns.NAME.value} = ?"

        # Esecuzione della query
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (production_name,))
            return cursor.fetchone()

    def fetch_productions_by_client_id(self, client_id):
        """
        Recupera delle productions specifiche in modo dinamico.
        """
        # Creazione della lista delle colonne dal DBProductionsColumns
        columns = [column.value for column in DBProductionsColumns]
        query = f"SELECT {', '.join(columns)} FROM productions WHERE {DBProductionsColumns.CLIENT_ID.value} = ?"

        # Esecuzione della query
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (client_id,))
            return cursor.fetchall()

    def fetch_last_production_insert(self):
        """
        Recupera l'ultima production inserita nel database, ordinando in base alla colonna CREATION_DATE.
        :return: Una tupla contenente i dati dell'ultima production oppure None se non viene trovata.
        """
        columns = [column.value for column in DBProductionsColumns]
        query = f"SELECT {', '.join(columns)} FROM productions ORDER BY {DBProductionsColumns.CREATED_AT.value} DESC LIMIT 1"

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchone()

    def update_production(self, production_id, **kwargs):
        """
        Aggiorna i valori di una produzione esistente nella tabella `productions`.
        I campi da aggiornare devono essere passati come keyword arguments.

        :param production_id: ID della produzione da aggiornare.
        :param kwargs: Campi da aggiornare (anche `None` per settare `NULL`).
        :raises ValueError: Se non vengono specificati campi validi per l'aggiornamento.
        """
        # Controllo che i campi passati siano validi per la tabella productions
        valid_columns = {column.value for column in DBProductionsColumns}
        update_fields = {key: value for key, value in kwargs.items() if key in valid_columns}

        if not update_fields:
            raise ValueError("Nessun campo valido specificato per l'aggiornamento.")

        # Creazione dinamica della query SQL
        set_clause = ", ".join([f"{field} = ?" for field in update_fields.keys()])
        query = f"UPDATE productions SET {set_clause} WHERE {DBProductionsColumns.ID.value} = ?"

        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (*update_fields.values(), production_id))
                conn.commit()
        except Exception as e:
            raise RuntimeError(f"Errore durante l'aggiornamento della produzione: {str(e)}")









    def fetch_accounts(self):
        """Recupera tutti gli account"""
        query = "SELECT * FROM accounts"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def add_account(self, **kwargs):
        """
        Aggiungi un nuovo account.
        I campi da aggiungere devono essere passati come keyword arguments.
        """
        # Estrarre le colonne valide dall'Enum dei accounts
        valid_columns = {column.value for column in DBAccountsColumns}
        insert_fields = {key: value for key, value in kwargs.items() if key in valid_columns}

        if not insert_fields:
            raise ValueError("Nessun campo valido specificato per l'inserimento.")

        # Creazione dinamica della query SQL per la tabella accounts
        columns = ", ".join(insert_fields.keys())
        placeholders = ", ".join(["?"] * len(insert_fields))
        query = f"INSERT INTO accounts ({columns}) VALUES ({placeholders})"

        # Esecuzione della query
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(insert_fields.values()))
            conn.commit()

    def fetch_account_by_id(self, account_id):
        """
        Recupera un account specifico in base all'ID.
        """
        # Creazione della lista delle colonne dall'enum DBAccountsColumns
        columns = [column.value for column in DBAccountsColumns]
        query = f"SELECT {', '.join(columns)} FROM accounts WHERE {DBAccountsColumns.ID.value} = ?"

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (account_id,))
            return cursor.fetchone()

    def fetch_account_by_name(self, account_name):
        """
        Recupera un account specifico in base al NAME.
        """
        # Creazione della lista delle colonne dall'enum DBAccountsColumns
        columns = [column.value for column in DBAccountsColumns]
        query = f"SELECT {', '.join(columns)} FROM accounts WHERE {DBAccountsColumns.NAME.value} = ?"

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (account_name,))
            return cursor.fetchone()

    def fetch_last_account_insert(self):
        """
        Recupera l'ultimo account inserito nel database, ordinando in base alla colonna CREATED_AT.
        :return: Una tupla contenente i dati dell'ultimo account oppure None se non viene trovato.
        """
        columns = [column.value for column in DBAccountsColumns]
        query = f"SELECT {', '.join(columns)} FROM accounts ORDER BY {DBAccountsColumns.CREATED_AT.value} DESC LIMIT 1"

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchone()








    def fetch_all_transfers(self):
        """Recupera tutti i bonifici"""
        columns = [column.value for column in DBTransfersColumns]
        query = f"SELECT {', '.join(columns)} FROM transfers"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def add_transfer(self, **kwargs):
        """
        Aggiungi un nuovo bonifico.
        I campi da aggiungere devono essere passati come keyword arguments.
        """
        # Estrazione colonne valide dall'enum
        valid_columns = {column.value for column in DBTransfersColumns if column != DBTransfersColumns.ID}
        insert_fields = {key: value for key, value in kwargs.items() if key in valid_columns}

        if not insert_fields:
            raise ValueError("Nessun campo valido specificato per l'inserimento.")

        # Costruzione query dinamica
        columns = ", ".join(insert_fields.keys())
        placeholders = ", ".join(["?"] * len(insert_fields))
        query = f"INSERT INTO transfers ({columns}) VALUES ({placeholders})"

        # Esecuzione
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(insert_fields.values()))
            conn.commit()

    def fetch_transfer_by_id(self, transfer_id):
        """
        Recupera un bonifico specifico per ID
        """
        columns = [column.value for column in DBTransfersColumns]
        query = f"SELECT {', '.join(columns)} FROM transfers WHERE {DBTransfersColumns.ID.value} = ?"

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (transfer_id,))
            return cursor.fetchone()

    def fetch_last_transfer_insert(self):
        """
        Recupera l'ultimo bonifico inserito
        """
        columns = [column.value for column in DBTransfersColumns]
        query = f"""
        SELECT {', '.join(columns)} 
        FROM transfers 
        ORDER BY {DBTransfersColumns.CREATED_AT.value} DESC 
        LIMIT 1
        """

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchone()

    def fetch_transfers_by_account(self, account_id):
        """
        Recupera tutti i bonifici associati a un conto (mittente o ricevente)
        """
        columns = [column.value for column in DBTransfersColumns]
        query = f"""
        SELECT {', '.join(columns)} 
        FROM transfers 
        WHERE {DBTransfersColumns.SENDER_ACCOUNT_ID.value} = ? 
        OR {DBTransfersColumns.RECEIVER_ACCOUNT_ID.value} = ?
        """

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (account_id, account_id))
            return cursor.fetchall()

    def fetch_received_transfers_by_account(self, account_id):
        """
        Recupera tutti i bonifici ricevuti da un conto specifico.

        Args:
            account_id (int): ID del conto ricevente

        Returns:
            list: Lista di tuple con i dati dei bonifici ricevuti
        """
        columns = [column.value for column in DBTransfersColumns]
        query = f"""
        SELECT {', '.join(columns)} 
        FROM transfers 
        WHERE {DBTransfersColumns.RECEIVER_ACCOUNT_ID.value} = ?
        ORDER BY {DBTransfersColumns.CREATED_AT.value} DESC
        """

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (account_id,))
            return cursor.fetchall()

    def fetch_sent_transfers_by_account(self, account_id):
        """
        Recupera tutti i bonifici inviati da un conto specifico.

        Args:
            account_id (int): ID del conto mittente

        Returns:
            list: Lista di tuple con i dati dei bonifici inviati
        """
        columns = [column.value for column in DBTransfersColumns]
        query = f"""
        SELECT {', '.join(columns)} 
        FROM transfers 
        WHERE {DBTransfersColumns.SENDER_ACCOUNT_ID.value} = ?
        ORDER BY {DBTransfersColumns.CREATED_AT.value} DESC
        """

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (account_id,))
            return cursor.fetchall()






    @staticmethod
    def backup_gestionale_db(n, backup_base_path, delta_days):
        """
        Esegue il backup del database gestionale con una logica FIFO per mantenere un numero massimo di n backup
        in cartelle organizzate per intervallo di tempo.

        :param n: Numero massimo di backup da conservare per intervallo.
        :param backup_base_path: Path base dove salvare i backup.
        :param delta_days: Intervallo di tempo in giorni per organizzare le cartelle dei backup.
        """

        # Recupera il percorso del DB tramite la variabile di ambiente
        db_path = os.getenv("GESTIONALE_DB_PATH")
        if not db_path:
            print("Errore: variabile di ambiente GESTIONALE_DB_PATH non definita.")
            return

        # Verifica che il file gestionale.db esista
        db_file = os.path.join(db_path, "gestionale.db")
        if not os.path.exists(db_file):
            print(f"Errore: Il file {db_file} non esiste.")
            return

        # Verifica o crea la cartella base dei backup
        if not os.path.exists(backup_base_path):
            os.makedirs(backup_base_path)

        # Determina l'intervallo di tempo corrente e il nome della sottocartella
        now = datetime.now()
        start_interval = now - timedelta(days=now.day % delta_days)
        folder_name = f"{start_interval.strftime('%Y%m%d')}_to_{(start_interval + timedelta(days=delta_days)).strftime('%Y%m%d')}"
        interval_folder = os.path.join(backup_base_path, folder_name)

        # Verifica o crea la cartella per l'intervallo corrente
        if not os.path.exists(interval_folder):
            os.makedirs(interval_folder)

        # Crea il nome del file di backup basato sulla data e ora correnti
        backup_filename = f"gestionale_data_{now.strftime('%Y%m%d_%H%M%S')}.db"
        backup_filepath = os.path.join(interval_folder, backup_filename)

        # Copia il database nella cartella dell'intervallo corrente
        shutil.copy2(db_file, backup_filepath)

        # Ottieni una lista dei file di backup nella cartella dell'intervallo corrente
        backups = [f for f in os.listdir(interval_folder) if f.endswith(".db")]
        backups.sort(
            key=lambda x: os.path.getctime(os.path.join(interval_folder, x)))  # Ordina i file per data di creazione

        # Se il numero di backup è maggiore o uguale a n, elimina i più vecchi
        while len(backups) > n:
            oldest_backup = backups.pop(0)
            os.remove(os.path.join(interval_folder, oldest_backup))  # Rimuove il backup più vecchio

        print(f"Backup creato: {backup_filepath}")


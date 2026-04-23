from datetime import datetime, timedelta

from Model import DatabaseModel
from Gestionale_Enums import *
from Utils.Controller_utils import ControllerUtils


class InvoiceQueryService:
    """
    Query service dedicato alle letture sul dominio Fatture.

    La classe concentra query, trasformazioni dei record e filtri temporali,
    cosi' view e analyzer possono lavorare con strutture gia' pronte senza
    incorporare logica di accesso al database.
    """

    def __init__(self, database_model: DatabaseModel):
        """Memorizza i collaboratori necessari alle query sui clienti."""
        self.db_model: DatabaseModel = database_model

    def retrieve_invoice_map_by_id(self, invoice_id):
        """
        Recupera una fattura specifica e la restituisce come dizionario, filtrando per l'anno corrente se specificato.
        :param invoice_id: ID della fattura.
        :return: Dizionario con i dati della fattura oppure None.
        """
        row = self.db_model.fetch_invoice_by_id(invoice_id)
        if not row:
            return None

        return ControllerUtils.row_to_map(row, DBInvoicesColumns)

    def retrieve_invoice_map_by_name(self, invoice_name):
        """
        Recupera una fattura in base al nome e la restituisce come dizionario,
        filtrando per l'anno corrente se specificato.

        :param invoice_name: Nome della fattura.
        :return: Dizionario con i dati della fattura oppure un dizionario vuoto.
        """
        row = self.db_model.fetch_invoice_by_name(invoice_name)

        if not row:
            return {}

        return ControllerUtils.row_to_map(row, DBInvoicesColumns)

    def retrieve_invoices_map_list_by_user(self, user_id, year: int = None):
        """
        Recupera tutte le fatture di un certo utente e le restituisce come lista di dizionari,
        filtrandole in base all'anno richiesto o mantenendo quelle con rate non pagate.

        :param user_id: ID dell'utente.
        :param year: Anno di riferimento (int). Default: anno corrente. -1 = nessun filtro
        :return: Lista di dizionari contenenti i dati delle fatture.
        """
        rows = self.db_model.fetch_invoices_by_user_id(user_id)
        if not rows:
            return []

        # 1️ Converti subito le tuple in mappe
        invoice_maps = [
            ControllerUtils.row_to_map(row, DBInvoicesColumns)
            for row in rows
        ]

        if rows:
            rows = ControllerUtils.filter_invoices(
                invoices=invoice_maps,
                db_model=self.db_model,
                year=year
            )

        return rows

    def retrieve_invoice_map_list_by_production(self, prod_id, year: int = None):
        """
        Recupera tutte le fatture di una produzione e le restituisce come lista di dizionari,
        filtrandole per l'anno corrente o mantenendo quelle con rate non pagate.

        :param prod_id: ID della produzione.
        :param year: Anno di riferimento per il retrieving.
        :return: Lista di dizionari contenenti i dati delle fatture.
        """
        rows = self.db_model.fetch_invoices_by_prod_id(prod_id)
        if not rows:
            return []

        # 1️ Converti subito le tuple in mappe
        invoice_maps = [
            ControllerUtils.row_to_map(row, DBInvoicesColumns)
            for row in rows
        ]

        if rows:
            rows = ControllerUtils.filter_invoices(
                invoices=invoice_maps,
                db_model=self.db_model,
                year=year
            )

        return rows

    def retrieve_invoice_map_list_by_client(self, client_id, year: int = None):
        """
        Recupera tutte le fatture di un cliente e le restituisce come lista di dizionari,
        filtrandole per l'anno corrente o mantenendo quelle con rate non pagate.

        :param client_id: ID del cliente.
        :param year: anno di riferimento per il retrieving
        :return: Lista di dizionari contenenti i dati delle fatture.
        """
        rows = self.db_model.fetch_invoices_by_client_id(client_id)
        if not rows:
            return []

        # 1️ Converti subito le tuple in mappe
        invoice_maps = [
            ControllerUtils.row_to_map(row, DBInvoicesColumns)
            for row in rows
        ]

        if rows:
            rows = ControllerUtils.filter_invoices(
                invoices=invoice_maps,
                db_model=self.db_model,
                year=year
            )

        return rows

    def retrieve_invoices_map_list(self, year: int = None, include_unpaid_invoices:bool = True):
        """
        Recupera tutte le fatture e le restituisce come lista di dizionari,
        filtrandole per l'anno richiesto e mantenendo quelle con rate non pagate.
        """
        rows = self.db_model.fetch_invoices()
        if not rows:
            return []

        # 1️ Converti subito le tuple in mappe
        invoice_maps = [
            ControllerUtils.row_to_map(row, DBInvoicesColumns)
            for row in rows
        ]

        # 2️ Applica il filtro (ora coerente)
        filtered_invoices = ControllerUtils.filter_invoices(
            invoices=invoice_maps,
            db_model=self.db_model,
            year=year,
            include_unpaid_invoices = include_unpaid_invoices
        )

        return filtered_invoices

    def retrieve_invoices_map_dictionary(self, keyIsName: bool = False):
        """
        Restituisce tutte le fatture in un dizionario indicizzato.

        Args:
            keyIsName: se ``True`` usa il nome cliente come chiave, altrimenti l'id.
        """
        invoices_list = self.retrieve_invoices_map_list(year=-1)
        dictionary = {}

        for row in invoices_list:
            dictionary[
                f"{row[DBInvoicesColumns.NUMERO_FATTURA.value]}" if keyIsName else f"{row[DBInvoicesColumns.ID.value]}"
            ] = row

        return dictionary

    def retrieve_last_invoice_insert_map(self):
        row = self.db_model.fetch_last_invoice_insert()
        return ControllerUtils.row_to_map(row, DBInvoicesColumns)

    def retrieve_invoice_with_payments_map_list(self, invoice_id):
        """
        Recupera la specifica fattura unita ai rispettivi pagamenti e
        li restituisce come lista di dizionari.

        """
        # Recupera le righe dal database per lo specifico client
        rows = self.db_model.fetch_invoice_with_payments(invoice_id)

        all_columns = list(DBInvoicesColumns) + list(DBPaymentsColumns)

        # Converte ogni riga in un dizionario
        return [ControllerUtils.row_to_map(row, all_columns) for row in rows]

    def retrieve_invoice_with_expenses_map_list(self, invoice_id):
        """
        Recupera la specifica fattura unita alle rispettive spese di produzione e
        li restituisce come lista di dizionari.

        """
        # Recupera le righe dal database per lo specifico client
        rows = self.db_model.fetch_invoice_with_expenses(invoice_id)

        all_columns = list(DBInvoicesColumns) + list(DBExpensesColumns)

        # Converte ogni riga in un dizionario
        return [ControllerUtils.row_to_map(row, all_columns) for row in rows]

    def get_invoices_for_days_window(self, days: int):
        """
        Restituisce le fatture emesse negli ultimi ``days`` giorni.

        Il retrieving parte dalle fatture dell'anno corrente e da quelle degli
        anni precedenti non completamente saldate, senza applicare controlli su
        altri domini.
        """
        start_date = datetime.now().date() - timedelta(days=days)
        invoices = self.retrieve_invoices_map_list(year=None, include_unpaid_invoices=True)

        return [
            invoice
            for invoice in invoices
            if (
                (invoice_date := ControllerUtils.parse_date(invoice.get(DBInvoicesColumns.DATA_CREAZIONE.value)))
                is not None
                and invoice_date >= start_date
            )
        ]

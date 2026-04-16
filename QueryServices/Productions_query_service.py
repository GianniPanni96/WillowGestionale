from Utils.Controller_utils import ControllerUtils
from Model import DatabaseModel
from Gestionale_Enums import *

class ProductionQueryService:
    """
    Query service dedicato alle letture sul dominio Produzioni.

    La classe concentra query, trasformazioni dei record e filtri temporali,
    cosi' view e analyzer possono lavorare con strutture gia' pronte senza
    incorporare logica di accesso al database.
    """

    def __init__(self, database_model:DatabaseModel):
        self.db_model:DatabaseModel = database_model

    def retrieve_production_by_id(self, production_id):
        """
        Recupera una production specifica per ID, opzionalmente filtrando per l'anno corrente.

        :param production_id: ID della production.
        :return: Una tupla con i dati della production oppure None.
        """
        row = self.db_model.fetch_production_by_id(production_id)
        return row

    def retrieve_production_map_by_name(self, production_name):
        """
        Recupera una production specifica per ID, opzionalmente filtrando per l'anno corrente.

        :param production_name: Nome della production.
        :return: Una tupla con i dati della production oppure None.
        """
        row = self.db_model.fetch_production_by_name(production_name)
        return ControllerUtils.row_to_map(row, DBProductionsColumns)

    def retrieve_production_map_by_id(self, production_id):
        """
        Recupera una production specifica e la restituisce come dizionario,
        filtrando per l'anno corrente se specificato.

        :param production_id: ID della production.
        :return: Dizionario con i dati della production oppure None.
        """
        row = self.db_model.fetch_production_by_id(production_id)
        return ControllerUtils.row_to_map(row, DBProductionsColumns)

    def retrieve_productions_map_list(self, year: int = None, include_prod_with_unpaid_invoices:bool = False):
        """
        Recupera tutte le productions e le restituisce come lista di dizionari,
        filtrandole per l'anno richiesto e mantenendo quelle con fatture non saldate.
        """
        rows = self.db_model.fetch_productions()

        # mapping tuple → dict
        productions = [
            ControllerUtils.row_to_map(row, DBProductionsColumns)
            for row in rows
        ] if rows else []

        # filtro corretto sul dominio productions
        if productions:
            productions = ControllerUtils.filter_productions(
                productions=productions,
                db_model=self.db_model,
                year=year,
                include_prod_with_unpaid_invoices=include_prod_with_unpaid_invoices
            )

        return productions

    def retrieve_productions_map_dictionary(self, keyIsName: bool = False):
        """
        Restituisce tutte le produzioni in un dizionario indicizzato.

        Args:
            keyIsName: se ``True`` usa il nome cliente come chiave, altrimenti l'id.
        """
        productions_list = self.retrieve_productions_map_list(year=-1)
        dictionary = {}

        for row in productions_list:
            dictionary[
                f"{row[DBProductionsColumns.NAME.value]}" if keyIsName else f"{row[DBProductionsColumns.ID.value]}"
            ] = row

        return dictionary

    def retrieve_production_with_invoices_map_list(self, production_id):
        invoices = self.db_model.fetch_production_with_invoices(production_id)
        all_columns = list(DBProductionsColumns) + list(DBInvoicesColumns)
        invoices_map = [ControllerUtils.row_to_map(invoice, all_columns) for invoice in invoices]

        return invoices_map

    def retrieve_last_production_insert_map(self):
        """
        Recupera l'ultima production inserita e la restituisce come dizionario.
        """
        row = self.db_model.fetch_last_production_insert()
        return ControllerUtils.row_to_map(row, DBProductionsColumns)

    def retrieve_productions_map_list_by_client_id(self, client_id, year: int = None, include_prod_with_unpaid_invoices:bool = False):
        """
        Recupera tutte le produzioni di un certo cliente e le restituisce come lista di dizionari,
        filtrandole per l'anno richiesto e mantenendo quelle collegate a fatture
        non completamente saldate, indipendentemente dall'anno.

        :param client_id: ID del cliente.
        :param year: Anno di riferimento per il retrieving.
                     - None → anno corrente
                     - -1   → nessun filtro per anno
        :return: Lista di dizionari contenenti i dati delle produzioni.
        """
        rows = self.db_model.fetch_productions_by_client_id(client_id)

        # Mapping tuple → dict
        productions = [
            ControllerUtils.row_to_map(row, DBProductionsColumns)
            for row in rows
        ] if rows else []

        if productions:
            productions = ControllerUtils.filter_productions(
                productions=productions,
                db_model=self.db_model,
                year=year,
                include_prod_with_unpaid_invoices=include_prod_with_unpaid_invoices
            )

        return productions

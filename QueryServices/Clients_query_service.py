from datetime import datetime, timedelta
from Controllers import ClientController, ControllerUtils, ProductionController

from Model import DBClientsColumns, DBProductionsColumns, DBInvoicesColumns, DatabaseModel


class ClientQueryService:
    """
    Query service dedicato alle liste dei Clienti che possono servire a View o analyzer
    Incapsula logica di lettura/filtro per non appesantire la View.
    """

    def __init__(self, client_controller:ClientController, production_controller:ProductionController, database_model:DatabaseModel):
        self.client_controller:ClientController = client_controller
        self.production_controller:ProductionController = production_controller
        self.db_model:DatabaseModel = database_model

    @staticmethod
    def _parse_production_datetime(date_str):
        if not date_str:
            return None

        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return None

    def get_clients_for_days_window(self, days):
        """
        Restituisce i clienti con almeno una produzione negli ultimi `days` giorni.
        """
        limit_date = datetime.now() - timedelta(days=days)

        all_clients = self.client_controller.retrieve_clients_map_list()
        filtered_clients = []

        for client in all_clients:
            client_id = client[DBClientsColumns.ID.value]
            client_productions = self.production_controller.retrieve_productions_map_list_by_client_id(
                client_id,
                year=-1
            )

            has_recent_production = False
            for production in client_productions:
                production_date = self._parse_production_datetime(
                    production.get(DBProductionsColumns.CREATED_AT.value)
                )
                if production_date and production_date >= limit_date:
                    has_recent_production = True
                    break

            #bypass last production if it's just created
            client_creation_date = datetime.strptime(client.get(DBClientsColumns.CREATED_AT.value), "%Y-%m-%d %H:%M:%S")
            is_just_created = False
            if datetime.now() - client_creation_date <= timedelta(days=30):
                is_just_created = True

            if has_recent_production or is_just_created:
                filtered_clients.append(client)

        return filtered_clients

    def retrieve_client_by_name(self, client_name):
        """Recupera un cliente specifico per nome."""
        return self.db_model.fetch_client_by_name(client_name)

    def retrieve_client_map_by_name(self, client_name):
        """Recupera un cliente specifico e lo restituisce come dizionario."""
        row = self.retrieve_client_by_name(client_name)
        return ControllerUtils.row_to_map(row, DBClientsColumns)

    def retrieve_client_map_by_id(self, client_id):
        """Recupera un cliente specifico e lo restituisce come dizionario."""
        row = self.db_model.fetch_client_by_id(client_id)
        return ControllerUtils.row_to_map(row, DBClientsColumns)

    def retrieve_clients_map_list(self):
        """Recupera tutti i clienti e li restituisce come lista di dizionari."""
        rows = self.db_model.fetch_clients()
        return [ControllerUtils.row_to_map(row, DBClientsColumns) for row in rows]

    def retrieve_clients_map_dictionary(self, keyIsName:bool = False):
        """Recupera tutti i clienti e li restituisce come un dizionario di dizionari in cui la chiave è l'ID.
        :param keyIsName: using ClientName as key instead of ID
        """
        list = self.retrieve_clients_map_list()
        dictionary = {}

        for row in list:
            dictionary[f"{row[DBClientsColumns.NAME.value]}" if keyIsName else f"{row[DBClientsColumns.ID.value]}"] = row

        return dictionary

    def retrieve_client_with_invoices_map_list(self, client_id, year:int = None, include_unpaid_invoices:bool = True):
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

        invoice_maps = [ControllerUtils.row_to_map(row, all_columns) for row in rows]

        if rows:
            rows = ControllerUtils.filter_invoices(
                invoices=invoice_maps,
                db_model=self.db_model,
                year=year,
                include_unpaid_invoices=include_unpaid_invoices
            )

        # Converte ogni riga in un dizionario
        return rows

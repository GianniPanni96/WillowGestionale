from datetime import datetime, timedelta
from Controllers import ProductionController, ClientController

from Model import DBClientsColumns, DBProductionsColumns


class ClientQueryService:
    """
    Query service dedicato alla lista Clienti.
    Incapsula logica di lettura/filtro per non appesantire la View.
    """

    def __init__(self, client_controller:ClientController, production_controller:ProductionController):
        self.client_controller:ClientController = client_controller
        self.production_controller:ProductionController = production_controller

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

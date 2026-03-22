from datetime import datetime, timedelta
from Controllers import ClientController, ControllerUtils, ProductionController

from Model import DatabaseModel
from Gestionale_Enums import *

import Utils.Date_utils as Date_utils


class ClientQueryService:
    """
    Query service dedicato alle letture sul dominio Clienti.

    La classe concentra query, trasformazioni dei record e filtri temporali,
    cosi' view e analyzer possono lavorare con strutture gia' pronte senza
    incorporare logica di accesso al database.
    """

    def __init__(self, client_controller: ClientController, production_controller: ProductionController,
                 database_model: DatabaseModel):
        """Memorizza i collaboratori necessari alle query sui clienti."""
        self.client_controller: ClientController = client_controller
        self.production_controller: ProductionController = production_controller
        self.db_model: DatabaseModel = database_model


    def get_clients_for_days_window(self, days):
        """
        Restituisce i clienti visibili nella finestra temporale selezionata.

        Un cliente viene incluso se possiede almeno una produzione recente
        oppure se e' stato creato di recente, cosi' resta visibile anche prima
        di avere produzioni collegate.
        """
        limit_date = datetime.now() - timedelta(days=days)

        all_clients = self.retrieve_clients_map_list()
        filtered_clients = []

        for client in all_clients:
            client_id = client[DBClientsColumns.ID.value]
            client_productions = self.production_controller.retrieve_productions_map_list_by_client_id(
                client_id,
                year=-1
            ) #todo: usare il retriever della query service e non del controller (eliminare la funzione dal controller se ancora non è stato fatto, ovviamente dopo la migrazione)

            has_recent_production = False
            for production in client_productions:
                production_date = Date_utils.parse_db_datetime(
                    production.get(DBProductionsColumns.CREATED_AT.value)
                )
                if production_date and production_date >= limit_date:
                    has_recent_production = True
                    break

            # Manteniamo visibile il cliente appena creato anche senza produzioni.
            client_creation_date = datetime.strptime(
                client.get(DBClientsColumns.CREATED_AT.value),
                "%Y-%m-%d %H:%M:%S"
            )
            is_just_created = False
            if datetime.now() - client_creation_date <= timedelta(days=30):
                is_just_created = True

            if has_recent_production or is_just_created:
                filtered_clients.append(client)

        return filtered_clients

    def retrieve_client_by_name(self, client_name):
        """Restituisce la riga raw del cliente cercato per nome."""
        return self.db_model.fetch_client_by_name(client_name)

    def retrieve_client_map_by_name(self, client_name):
        """Recupera un cliente per nome e lo converte in mappa chiave/valore."""
        row = self.retrieve_client_by_name(client_name)
        return ControllerUtils.row_to_map(row, DBClientsColumns)

    def retrieve_client_map_by_id(self, client_id):
        """Recupera un cliente per id e lo converte in mappa chiave/valore."""
        row = self.db_model.fetch_client_by_id(client_id)
        return ControllerUtils.row_to_map(row, DBClientsColumns)

    def retrieve_clients_map_list(self):
        """Recupera tutti i clienti e li converte in una lista di mappe."""
        rows = self.db_model.fetch_clients()
        return [ControllerUtils.row_to_map(row, DBClientsColumns) for row in rows]

    def retrieve_clients_map_dictionary(self, keyIsName: bool = False):
        """
        Restituisce tutti i clienti in un dizionario indicizzato.

        Args:
            keyIsName: se ``True`` usa il nome cliente come chiave, altrimenti l'id.
        """
        clients_list = self.retrieve_clients_map_list()
        dictionary = {}

        for row in clients_list:
            dictionary[
                f"{row[DBClientsColumns.NAME.value]}" if keyIsName else f"{row[DBClientsColumns.ID.value]}"
            ] = row

        return dictionary

    def retrieve_client_with_invoices_map_list(self, client_id, year: int = None,
                                               include_unpaid_invoices: bool = True):
        """
        Recupera il cliente unito alle relative fatture come lista di mappe.

        La query di origine restituisce righe composite contenenti prima le
        colonne del cliente e poi quelle delle fatture. Questo metodo ricostruisce
        le mappe applicando infine i filtri standard per anno e pagato/non pagato.
        """
        rows = self.db_model.fetch_client_with_invoices(client_id)
        all_columns = list(DBClientsColumns) + list(DBInvoicesColumns)

        invoice_maps = [ControllerUtils.row_to_map(row, all_columns) for row in rows]

        if rows:
            rows = ControllerUtils.filter_invoices(
                invoices=invoice_maps,
                db_model=self.db_model,
                year=year,
                include_unpaid_invoices=include_unpaid_invoices
            )

        return rows

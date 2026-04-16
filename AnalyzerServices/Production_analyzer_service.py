from Gestionale_Enums import *

from Model import DatabaseModel
from QueryServices.Productions_query_service import ProductionQueryService


class ProductionAnalyzerService:
    """
    Servizio applicativo che calcola gli aggregati economici delle produzioni.

    Questa classe lavora sopra ``ProductionQueryService`` e ``DatabaseModel``:
    non costruisce interfacce, ma espone metriche pronte per view e report,
    mantenendo fuori dalla UI la logica di analisi.
    """

    def __init__(self, production_query_service: ProductionQueryService, database_model: DatabaseModel):
        """Memorizza i servizi necessari per query e calcoli aggregati."""
        self.production_query_service: ProductionQueryService = production_query_service
        self.db_model: DatabaseModel = database_model

    def calculate_production_cost_per_hour(self, production_id):
        production_map = self.production_query_service.retrieve_production_map_by_id(production_id)
        hours = int(production_map[DBProductionsColumns.HOURS.value])
        tot_preventivo = float(production_map[DBProductionsColumns.TOTALE_PREVENTIVO.value])
        cost_per_hour = tot_preventivo/hours if hours != 0 and hours.is_integer() else -1

        return cost_per_hour

    def count_productions(self, year: int = None, include_prod_with_unpaid_invoices:bool = False):
        """
        Conta il numero di productions in base all'anno richiesto.

        :param year:
            - None → anno corrente
            - -1   → nessun filtro
            - altro int → anno specifico
        :return: Numero di productions (int).
        """
        productions = self.production_query_service.retrieve_productions_map_list(year=year, include_prod_with_unpaid_invoices = include_prod_with_unpaid_invoices)
        return len(productions)

    def count_productions_of_client(self, client_id, year: int = None, include_prod_with_unpaid_invoices:bool = False):
        """
        Conta il numero di productions di un cliente in base all'anno richiesto.
        """
        productions = self.production_query_service.retrieve_productions_map_list_by_client_id(
            client_id=client_id,
            year=year,
            include_prod_with_unpaid_invoices = include_prod_with_unpaid_invoices
        )
        return len(productions)

    def count_active_productions(self, include_prod_with_unpaid_invoices:bool = False, year: int = None):
        """
        Conta il numero di productions attive in base all'anno richiesto.
        """
        productions = self.production_query_service.retrieve_productions_map_list(year=year, include_prod_with_unpaid_invoices = include_prod_with_unpaid_invoices)

        active = [
            prod for prod in productions
            if prod[DBProductionsColumns.STATO.value] != ProductionStatus.CLOSED.value
        ]

        return len(active)

    def count_closed_productions(self, year: int = None, include_prod_with_unpaid_invoices:bool = False):
        """
        Conta il numero di productions chiuse in base all'anno richiesto.
        """
        productions = self.production_query_service.retrieve_productions_map_list(year=year, include_prod_with_unpaid_invoices = include_prod_with_unpaid_invoices)

        closed = [
            prod for prod in productions
            if prod[DBProductionsColumns.STATO.value] == ProductionStatus.CLOSED.value
        ]

        return len(closed)

    def mean_hours_for_production(self, year: int = None, include_prod_with_unpaid_invoices:bool = False):
        """
        Calcola la media delle ore per production.
        """
        productions = self.production_query_service.retrieve_productions_map_list(year=year, include_prod_with_unpaid_invoices = include_prod_with_unpaid_invoices)

        if not productions:
            return 0

        total_hours = sum(
            float(prod[DBProductionsColumns.HOURS.value])
            for prod in productions
        )

        return total_hours / len(productions)

    def mean_prezzo_orario(self, year: int = None, include_prod_with_unpaid_invoices:bool = False):
        """
        Calcola il prezzo orario medio delle productions.
        """
        productions = self.production_query_service.retrieve_productions_map_list(year=year, include_prod_with_unpaid_invoices = include_prod_with_unpaid_invoices)

        if not productions:
            return 0

        total = 0
        valid_count = 0

        for prod in productions:
            cost_per_hour = self.calculate_production_cost_per_hour(
                prod[DBProductionsColumns.ID.value]
            )
            if cost_per_hour != -1:
                total += cost_per_hour
                valid_count += 1

        return total / valid_count if valid_count > 0 else 0

    def calcola_totale_servizi_rimborsi_per_produzione(self, production_id):

        invoices_map = self.production_query_service.retrieve_production_with_invoices_map_list(production_id)

        tot = 0.0
        for invoice in invoices_map:
            tot += invoice[DBInvoicesColumns.SERVIZI.value] + invoice[DBInvoicesColumns.RIMBORSI.value] if invoice[DBInvoicesColumns.NUMERO_FATTURA.value] is not None else 0

        return tot

from datetime import datetime

from Gestionale_Enums import DBRefundsColumns, RefundsAggregateData
from Model import DatabaseModel
from QueryServices.Refunds_query_service import RefundQueryService


class RefundAnalyzerService:
    """
    Servizio applicativo che calcola aggregati e metriche del dominio rimborsi.
    """

    def __init__(self, refund_query_service: RefundQueryService, database_model: DatabaseModel):
        self.refund_query_service = refund_query_service
        self.db_model = database_model

    def count_refunds(self, year: int = None):
        refunds = self.refund_query_service.retrieve_refunds_map_list(year)
        return len(refunds)

    def calculate_tot_refunds(self, year: int = None):
        refund_list = self.refund_query_service.retrieve_refunds_map_list(year)
        return sum(float(refund[DBRefundsColumns.REFUND_AMOUNT.value]) for refund in refund_list)

    def calculate_tot_refunds_of_client(self, client_id, year: int = None):
        refund_list = self.refund_query_service.retrieve_refunds_map_list_by_client_id(client_id, year)
        return sum(float(refund[DBRefundsColumns.REFUND_AMOUNT.value]) for refund in refund_list)

    def sum_refunds_for_account(self, account_id, year: int = None):
        target_year = year if year is not None else datetime.now().year
        return self.db_model.sum_refunds_by_account(account_id, year=target_year)

    def build_aggregate_data(self, year: int = None):
        return {
            RefundsAggregateData.NUMERO_RIMBORSI.value: self.count_refunds(year),
            RefundsAggregateData.TOT_RIMBORSI.value: self.calculate_tot_refunds(year),
        }

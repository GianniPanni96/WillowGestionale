from datetime import datetime
from Gestionale_Enums import *

from Model import DatabaseModel
from QueryServices.Payments_query_service import PaymentQueryService


class PaymentAnalyzerService:
    """
    Servizio applicativo che calcola gli aggregati economici dei pagamenti.

    Questa classe lavora sopra ``PaymentQueryService`` e ``DatabaseModel``:
    non costruisce interfacce, ma espone metriche pronte per view e report,
    mantenendo fuori dalla UI la logica di analisi.
    """

    def __init__(self, payment_query_service: PaymentQueryService, database_model: DatabaseModel):
        """Memorizza i servizi necessari per query e calcoli aggregati."""
        self.payment_query_service: PaymentQueryService = payment_query_service
        self.db_model: DatabaseModel = database_model

    def count_payments(self, year: int = None, include_unpaid_invoice_payments:bool = False):
        """
        Conta il numero di pagamenti filtrati per anno.

        :param include_unpaid_invoice_payments:
        :param year:
            - None → anno corrente
            - -1   → nessun filtro
            - altro int → anno specifico
        :return: Numero di pagamenti
        """
        payments = self.payment_query_service.retrieve_payments_map_list(year=year, include_unpaid_invoice_payments=include_unpaid_invoice_payments)
        return len(payments)

    def calculate_tot_payments(self, year: int = None, include_unpaid_invoice_payments:bool = False):
        """
        Somma gli importi dei pagamenti filtrati per anno.

        :param include_unpaid_invoice_payments:
        :param year:
            - None → anno corrente
            - -1   → nessun filtro
            - altro int → anno specifico
        :return: Totale importi pagamenti (float)
        """
        payment_list = self.payment_query_service.retrieve_payments_map_list(year=year, include_unpaid_invoice_payments=include_unpaid_invoice_payments)
        tot = 0.0
        for payment in payment_list:
            try:
                tot += float(payment[DBPaymentsColumns.PAYMENT_AMOUNT.value])
            except (TypeError, ValueError):
                pass
        return tot

    def sum_payments_for_account(self, account_id, year:int = None):

        target_year = year if year is not None else datetime.now().year

        return self.db_model.sum_payments_by_account(account_id, year=target_year)

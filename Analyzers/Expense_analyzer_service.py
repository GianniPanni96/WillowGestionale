from datetime import datetime

from Gestionale_Enums import DBExpensesColumns
from Model import DatabaseModel
from QueryServices.Expenses_query_service import ExpenseQueryService


class ExpenseAnalyzerService:
    """
    Servizio applicativo per aggregati e metriche del dominio spese.
    """

    NUMERO_SPESE_KEY = "#SPESE"
    TOT_SPESE_KEY = "TOT. SPESE"

    def __init__(self, expense_query_service: ExpenseQueryService, db_model: DatabaseModel):
        self.expense_query_service = expense_query_service
        self.db_model = db_model

    def count_expenses(self, year: int = None):
        return len(self.expense_query_service.retrieve_expenses_map_list(year=year))

    def calculate_tot_expenses(self, year: int = None):
        expense_list = self.expense_query_service.retrieve_expenses_map_list(year=year)

        tot = 0.0
        for expense in expense_list:
            try:
                tot += float(expense[DBExpensesColumns.TOT_AMOUNT.value])
            except (TypeError, ValueError):
                pass

        return tot

    def sum_expenses_for_account(self, account_id, year: int = None):
        target_year = year if year is not None else datetime.now().year
        return self.db_model.sum_expenses_by_account(account_id, year=target_year)

    def build_aggregate_data(self, year: int = None):
        return {
            self.NUMERO_SPESE_KEY: self.count_expenses(year=year),
            self.TOT_SPESE_KEY: self.calculate_tot_expenses(year=year),
        }

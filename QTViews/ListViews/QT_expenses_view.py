"""
List view delle Spese, sottoclasse di QTBaseListView.

Replica in chiave Qt il dominio di Views/ListViews/Expenses_view_H.py
legacy: stessa time window (30/60/90/365 GG, default 60), stesse
colonne e stessi aggregati (#SPESE / TOT. SPESE).

Tutta l'ossatura UI vive nella base; qui si implementano solo gli
hook di dominio.
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from Gestionale_Enums import DBExpensesColumns, ExpensesAggregateData
from QTViews.Creators.QT_expense_create_view import QTExpenseCreateViewH
from QTViews.ListViews.QT_base_list_view import QTBaseListView
from QTViews.ListViews.QT_expenses_table_model import ExpensesTableModel

if TYPE_CHECKING:
    from App_context import AppContext


class QTExpensesViewH(QTBaseListView):
    """
    Implementazione concreta della list view Spese su QTBaseListView.
    """

    AGGREGATE_KEYS = (
        ExpensesAggregateData.NUMERO_SPESE.value,
        ExpensesAggregateData.TOT_SPESE.value,
    )
    AGGREGATE_TOGGLE_OPTIONS = None

    TIME_WINDOWS = (
        ("30 GG", 30),
        ("60 GG", 60),
        ("90 GG", 90),
        ("365 GG", 365),
    )
    DEFAULT_WINDOW_INDEX = 1  # 60 GG, come la legacy
    LIST_VIEW_KEY = "expenses"
    ADD_BUTTON_TEXT = "Aggiungi una spesa"
    ITEM_LABEL_PLURAL = "spese"
    SEARCH_PLACEHOLDER = "Cerca in tutte le colonne…"

    def __init__(
        self,
        app_context: "AppContext",
        initial_expense_id=None,
        on_open_detail=None,
        parent=None,
    ):
        super().__init__(
            app_context=app_context,
            initial_item_id=initial_expense_id,
            on_open_detail=on_open_detail,
            parent=parent,
        )

    # ------------------------------------------------------------------
    # Hook
    # ------------------------------------------------------------------

    # Warnings di dominio (cfr ExpenseWarningService).
    WARNING_SERVICE_ATTR = "expense_warning_service"
    WARNING_DOMAIN_KEY = "spese"
    AGGREGATE_TOOLTIP_BUILDER_ATTR = "expenses_aggregate_tooltip_builder"

    def _setup_services(self, app_context: "AppContext"):
        self.expenses_query_service = app_context.expenses_query_service
        self.expenses_analyzer_service = app_context.expenses_analyzer_service
        self.suppliers_query_service = app_context.suppliers_query_service
        self.user_query_service = app_context.user_query_service
        self.accounts_query_service = app_context.account_query_service
        self.expense_warning_service = app_context.expense_warning_service

    def fetch_items(self, window_days):
        all_expenses = self.expenses_query_service.retrieve_expenses_map_list()

        if window_days is None:
            return all_expenses

        # Filtro per DATA_PAGAMENTO — esattamente come show_last_cards
        # nella legacy.
        limit_date = datetime.now() - timedelta(days=window_days)
        filtered = []
        for expense in all_expenses:
            date_str = expense.get(DBExpensesColumns.DATE.value)
            if not date_str:
                continue
            expense_date = None
            for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    expense_date = datetime.strptime(date_str, pattern)
                    break
                except ValueError:
                    continue
            if expense_date is not None and expense_date >= limit_date:
                filtered.append(expense)
        return filtered

    def build_rows(self, items):
        return ExpensesTableModel.build_rows(
            items,
            self.suppliers_query_service,
            self.user_query_service,
            self.accounts_query_service,
        )

    def create_table_model(self, rows):
        return ExpensesTableModel(rows, self)

    def configure_table(self, table):
        table.setObjectName("ExpensesTable")
        table.verticalHeader().setDefaultSectionSize(36)
        table.horizontalHeader().setDefaultSectionSize(80)
        table.setStyleSheet(
            """
            #ExpensesTable {
                font-size: 11pt;
            }

            #ExpensesTable::item {
                padding-top: 6px;
                padding-bottom: 6px;
                padding-left: 6px;
                padding-right: 6px;
            }

            #ExpensesTable QHeaderView::section {
                font-size: 11pt;
                font-weight: bold;
                padding: 8px 6px;
            }
            """
        )

    def compute_aggregates(self, toggle_value):
        # Gli aggregati globali delle spese sono indipendenti dalla
        # time-window selezionata (come fa la legacy in
        # populate_global_infos).
        analyzer = self.expenses_analyzer_service
        n_expenses = analyzer.count_expenses()
        tot_expenses = analyzer.calculate_tot_expenses()
        return {
            ExpensesAggregateData.NUMERO_SPESE.value: str(n_expenses),
            ExpensesAggregateData.TOT_SPESE.value: f"{round(tot_expenses, 2)} €",
        }

    def id_for_index(self, source_index):
        return self._source_model.data(source_index, ExpensesTableModel.ROLE_EXPENSE_ID)

    def row_for_id(self, item_id):
        return self._source_model.find_row_by_expense_id(item_id)

    def open_creator_dialog(self):
        # Creator non modale: post-creazione gestito da ``_after_primary_create``.
        dialog = QTExpenseCreateViewH(
            app_context=self.app_context,
            parent=self,
            on_expense_created=self._after_primary_create,
        )
        self._launch_creator(dialog)

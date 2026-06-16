"""
List view dei Salari, sottoclasse di QTBaseListView.

Replica in chiave Qt il dominio di Views/ListViews/Salaries_view_H.py
legacy: stessa time window (30/60/90/365 GG, default 60), stesse
colonne e stessi aggregati (#SALARI / TOT. SALARI).

Tutta l'ossatura UI vive nella base; qui si implementano solo gli
hook di dominio.
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from Gestionale_Enums import DBSalariesColumns, SalariesAggregateData
from QTViews.Creators.QT_salary_create_view import QTSalaryCreateViewH
from QTViews.ListViews.QT_base_list_view import QTBaseListView
from QTViews.ListViews.QT_salaries_table_model import SalariesTableModel

if TYPE_CHECKING:
    from App_context import AppContext


class QTSalariesViewH(QTBaseListView):
    """
    Implementazione concreta della list view Salari su QTBaseListView.
    """

    AGGREGATE_KEYS = (
        SalariesAggregateData.NUMERO_SALARI.value,
        SalariesAggregateData.TOT_SALARI.value,
    )
    AGGREGATE_TOGGLE_OPTIONS = None

    TIME_WINDOWS = (
        ("30 GG", 30),
        ("60 GG", 60),
        ("90 GG", 90),
        ("365 GG", 365),
    )
    DEFAULT_WINDOW_INDEX = 1  # 60 GG, come la legacy
    LIST_VIEW_KEY = "salaries"
    ADD_BUTTON_TEXT = "Aggiungi un salario"
    ITEM_LABEL_PLURAL = "salari"
    SEARCH_PLACEHOLDER = "Cerca in tutte le colonne…"

    def __init__(
        self,
        app_context: "AppContext",
        initial_salary_id=None,
        on_open_detail=None,
        parent=None,
    ):
        super().__init__(
            app_context=app_context,
            initial_item_id=initial_salary_id,
            on_open_detail=on_open_detail,
            parent=parent,
        )

    # ------------------------------------------------------------------
    # Hook
    # ------------------------------------------------------------------

    # Warnings di dominio (cfr SalaryWarningService).
    WARNING_SERVICE_ATTR = "salary_warning_service"
    WARNING_DOMAIN_KEY = "salari"
    AGGREGATE_TOOLTIP_BUILDER_ATTR = "salaries_aggregate_tooltip_builder"

    def _setup_services(self, app_context: "AppContext"):
        self.salary_query_service = app_context.salary_query_service
        self.salary_analyzer_service = app_context.salary_analyzer_service
        self.user_query_service = app_context.user_query_service
        self.accounts_query_service = app_context.account_query_service
        self.salary_warning_service = app_context.salary_warning_service

    def fetch_items(self, window_days):
        all_salaries = self.salary_query_service.retrieve_salaries_map_list()

        if window_days is None:
            return all_salaries

        # Filtro per DATE — esattamente come show_last_cards della
        # legacy.
        limit_date = datetime.now() - timedelta(days=window_days)
        filtered = []
        for salary in all_salaries:
            date_str = salary.get(DBSalariesColumns.DATE.value)
            if not date_str:
                continue
            salary_date = None
            for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    salary_date = datetime.strptime(date_str, pattern)
                    break
                except ValueError:
                    continue
            if salary_date is not None and salary_date >= limit_date:
                filtered.append(salary)
        return filtered

    def build_rows(self, items):
        return SalariesTableModel.build_rows(
            items,
            self.user_query_service,
            self.accounts_query_service,
        )

    def create_table_model(self, rows):
        return SalariesTableModel(rows, self)

    def configure_table(self, table):
        table.setObjectName("SalariesTable")
        table.verticalHeader().setDefaultSectionSize(36)
        table.horizontalHeader().setDefaultSectionSize(80)
        table.setStyleSheet(
            """
            #SalariesTable {
                font-size: 11pt;
            }

            #SalariesTable::item {
                padding-top: 6px;
                padding-bottom: 6px;
                padding-left: 6px;
                padding-right: 6px;
            }

            #SalariesTable QHeaderView::section {
                font-size: 11pt;
                font-weight: bold;
                padding: 8px 6px;
            }
            """
        )

    def compute_aggregates(self, toggle_value):
        # Aggregati globali, indipendenti dalla time-window selezionata,
        # come fa la legacy in populate_global_infos.
        analyzer = self.salary_analyzer_service
        n_salaries = analyzer.count_salaries()
        tot_salaries = analyzer.calculate_tot_salaries()
        return {
            SalariesAggregateData.NUMERO_SALARI.value: str(n_salaries),
            SalariesAggregateData.TOT_SALARI.value: f"{tot_salaries:.2f} €",
        }

    def id_for_index(self, source_index):
        return self._source_model.data(source_index, SalariesTableModel.ROLE_SALARY_ID)

    def row_for_id(self, item_id):
        return self._source_model.find_row_by_salary_id(item_id)

    def open_creator_dialog(self):
        # Creator non modale: post-creazione gestito da ``_after_primary_create``.
        dialog = QTSalaryCreateViewH(
            app_context=self.app_context,
            parent=self,
            on_salary_created=self._after_primary_create,
        )
        self._launch_creator(dialog)

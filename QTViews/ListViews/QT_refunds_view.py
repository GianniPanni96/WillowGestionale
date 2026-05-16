"""
List view dei Rimborsi, sottoclasse di QTBaseListView.

Replica in chiave Qt il dominio di Views/ListViews/Refunds_view_H.py
legacy: stessa time window (30/60/90/365 GG, default 60), stesse
colonne e stessi aggregati (# rimborsi / TOT. rimborsi).

Tutta l'ossatura UI vive nella base; qui si implementano solo gli
hook di dominio: query/analyzer service, costruzione del
RefundsTableModel, formula degli aggregati globali, dialog di
creazione e mapping id ⇄ riga del source model.
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from Gestionale_Enums import DBRefundsColumns, RefundsAggregateData
from QTViews.Creators.QT_refund_create_view import QTRefundCreateViewH
from QTViews.ListViews.QT_base_list_view import QTBaseListView
from QTViews.ListViews.QT_refunds_table_model import RefundsTableModel

if TYPE_CHECKING:
    from App_context import AppContext


class QTRefundsViewH(QTBaseListView):
    """
    Implementazione concreta della list view Rimborsi su QTBaseListView.
    """

    AGGREGATE_KEYS = (
        RefundsAggregateData.NUMERO_RIMBORSI.value,
        RefundsAggregateData.TOT_RIMBORSI.value,
    )
    AGGREGATE_TOGGLE_OPTIONS = None

    TIME_WINDOWS = (
        ("30 GG", 30),
        ("60 GG", 60),
        ("90 GG", 90),
        ("365 GG", 365),
    )
    DEFAULT_WINDOW_INDEX = 1  # 60 GG, come la legacy
    ADD_BUTTON_TEXT = "Aggiungi un rimborso"
    ITEM_LABEL_PLURAL = "rimborsi"
    SEARCH_PLACEHOLDER = "Cerca in tutte le colonne…"

    def __init__(
        self,
        app_context: "AppContext",
        initial_refund_id=None,
        on_open_detail=None,
        parent=None,
    ):
        super().__init__(
            app_context=app_context,
            initial_item_id=initial_refund_id,
            on_open_detail=on_open_detail,
            parent=parent,
        )

    # ------------------------------------------------------------------
    # Hook
    # ------------------------------------------------------------------

    # Warnings di dominio (cfr RefundWarningService).
    WARNING_SERVICE_ATTR = "refund_warning_service"
    WARNING_DOMAIN_KEY = "rimborsi"
    AGGREGATE_TOOLTIP_BUILDER_ATTR = "refunds_aggregate_tooltip_builder"

    def _setup_services(self, app_context: "AppContext"):
        self.refunds_query_service = app_context.refunds_query_service
        self.refunds_analyzer_service = app_context.refunds_analyzer_service
        self.clients_query_service = app_context.clients_query_service
        self.accounts_query_service = app_context.account_query_service
        self.refund_warning_service = app_context.refund_warning_service

    def fetch_items(self, window_days):
        all_refunds = self.refunds_query_service.retrieve_refunds_map_list()

        if window_days is None:
            return all_refunds

        # Filtro per REFUND_DATE — esattamente come show_last_cards nella
        # legacy.
        limit_date = datetime.now() - timedelta(days=window_days)
        filtered = []
        for refund in all_refunds:
            date_str = refund.get(DBRefundsColumns.REFUND_DATE.value)
            if not date_str:
                continue
            refund_date = None
            for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    refund_date = datetime.strptime(date_str, pattern)
                    break
                except ValueError:
                    continue
            if refund_date is not None and refund_date >= limit_date:
                filtered.append(refund)
        return filtered

    def build_rows(self, items):
        return RefundsTableModel.build_rows(
            items,
            self.clients_query_service,
            self.accounts_query_service,
        )

    def create_table_model(self, rows):
        return RefundsTableModel(rows, self)

    def configure_table(self, table):
        table.setObjectName("RefundsTable")
        table.verticalHeader().setDefaultSectionSize(36)
        table.horizontalHeader().setDefaultSectionSize(80)
        table.setStyleSheet(
            """
            #RefundsTable {
                font-size: 11pt;
            }

            #RefundsTable::item {
                padding-top: 6px;
                padding-bottom: 6px;
                padding-left: 6px;
                padding-right: 6px;
            }

            #RefundsTable QHeaderView::section {
                font-size: 11pt;
                font-weight: bold;
                padding: 8px 6px;
            }
            """
        )

    def compute_aggregates(self, toggle_value):
        # Gli aggregati globali dei rimborsi sono indipendenti dalla
        # time-window selezionata, come fa la legacy in
        # populate_global_infos.
        analyzer = self.refunds_analyzer_service
        n_refunds = analyzer.count_refunds()
        tot_refunds = analyzer.calculate_tot_refunds()
        return {
            RefundsAggregateData.NUMERO_RIMBORSI.value: str(n_refunds),
            RefundsAggregateData.TOT_RIMBORSI.value: f"{round(tot_refunds, 2)} €",
        }

    def id_for_index(self, source_index):
        return self._source_model.data(source_index, RefundsTableModel.ROLE_REFUND_ID)

    def row_for_id(self, item_id):
        return self._source_model.find_row_by_refund_id(item_id)

    def open_creator_dialog(self):
        # Stesso pattern di QTPaymentsViewH / QTInvoicesViewH /
        # QTProductionsViewH.
        result = {"id": None}

        def _on_created(refund_id):
            result["id"] = refund_id

        dialog = QTRefundCreateViewH(
            app_context=self.app_context,
            parent=self,
            on_refund_created=_on_created,
        )
        dialog.exec()
        return result["id"]

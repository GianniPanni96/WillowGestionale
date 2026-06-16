"""
List view dei Pagamenti, sottoclasse di QTBaseListView.

Replica in chiave Qt il dominio della Views/ListViews/Payments_view_H.py
legacy: stessa time window (30/60/90/365 GG, default 60), stesse colonne
e stessi aggregati (# pagamenti / TOT. pagamenti).

Tutta l'ossatura UI (aggregati, time window, search, QTableView,
bottone aggiungi) vive nella base; qui si implementano solo gli hook
di dominio: query/analyzer service, costruzione del
PaymentsTableModel, formula degli aggregati globali, dialog di
creazione e mapping id ⇄ riga del source model.
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from Gestionale_Enums import DBPaymentsColumns
from QTViews.Creators.QT_payment_create_view import QTPaymentCreateViewH
from QTViews.ListViews.QT_base_list_view import QTBaseListView
from QTViews.ListViews.QT_payments_table_model import PaymentsTableModel

if TYPE_CHECKING:
    from App_context import AppContext


class QTPaymentsViewH(QTBaseListView):
    """
    Implementazione concreta della list view Pagamenti su QTBaseListView.
    """

    AGGREGATE_KEYS = ("# PAGAMENTI", "TOT. PAGAMENTI")
    AGGREGATE_TOGGLE_OPTIONS = None

    TIME_WINDOWS = (
        ("30 GG", 30),
        ("60 GG", 60),
        ("90 GG", 90),
        ("365 GG", 365),
    )
    DEFAULT_WINDOW_INDEX = 1  # 60 GG, come la legacy
    LIST_VIEW_KEY = "payments"
    ADD_BUTTON_TEXT = "Aggiungi un pagamento"
    ITEM_LABEL_PLURAL = "pagamenti"
    SEARCH_PLACEHOLDER = "Cerca in tutte le colonne…"

    def __init__(
        self,
        app_context: "AppContext",
        initial_payment_id=None,
        on_open_detail=None,
        parent=None,
    ):
        super().__init__(
            app_context=app_context,
            initial_item_id=initial_payment_id,
            on_open_detail=on_open_detail,
            parent=parent,
        )

    # ------------------------------------------------------------------
    # Hook
    # ------------------------------------------------------------------

    # Warnings di dominio (cfr PaymentWarningService).
    WARNING_SERVICE_ATTR = "payment_warning_service"
    WARNING_DOMAIN_KEY = "pagamenti"
    AGGREGATE_TOOLTIP_BUILDER_ATTR = "payments_aggregate_tooltip_builder"

    def _setup_services(self, app_context: "AppContext"):
        self.payments_query_service = app_context.payments_query_service
        self.payments_analyzer_service = app_context.payments_analyzer_service
        self.invoices_query_service = app_context.invoices_query_service
        self.clients_query_service = app_context.clients_query_service
        self.productions_query_service = app_context.productions_query_service
        self.accounts_query_service = app_context.account_query_service
        self.payment_warning_service = app_context.payment_warning_service

    def fetch_items(self, window_days):
        # La legacy include i pagamenti delle fatture non saldate quando
        # mostra la lista pagamenti — mantieniamo lo stesso criterio per
        # avere parita' di insieme tra le due tab.
        all_payments = self.payments_query_service.retrieve_payments_map_list(
            year=None, include_unpaid_invoice_payments=True
        )

        if window_days is None:
            return all_payments

        # Filtro per data di contabilizzazione del pagamento — esattamente
        # come show_last_cards nella legacy.
        limit_date = datetime.now() - timedelta(days=window_days)
        filtered = []
        for payment in all_payments:
            date_str = payment.get(DBPaymentsColumns.PAYMENT_DATE.value)
            if not date_str:
                continue
            payment_date = None
            for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    payment_date = datetime.strptime(date_str, pattern)
                    break
                except ValueError:
                    continue
            if payment_date is not None and payment_date >= limit_date:
                filtered.append(payment)
        return filtered

    def build_rows(self, items):
        return PaymentsTableModel.build_rows(
            items,
            self.invoices_query_service,
            self.clients_query_service,
            self.productions_query_service,
            self.accounts_query_service,
        )

    def create_table_model(self, rows):
        return PaymentsTableModel(rows, self)

    def configure_table(self, table):
        table.setObjectName("PaymentsTable")
        table.verticalHeader().setDefaultSectionSize(36)
        table.horizontalHeader().setDefaultSectionSize(80)
        table.setStyleSheet(
            """
            #PaymentsTable {
                font-size: 11pt;
            }

            #PaymentsTable::item {
                padding-top: 6px;
                padding-bottom: 6px;
                padding-left: 6px;
                padding-right: 6px;
            }

            #PaymentsTable QHeaderView::section {
                font-size: 11pt;
                font-weight: bold;
                padding: 8px 6px;
            }
            """
        )

    def compute_aggregates(self, toggle_value):
        # Gli aggregati globali dei pagamenti sono indipendenti dalla
        # time-window selezionata, esattamente come fa la legacy in
        # populate_global_infos.
        analyzer = self.payments_analyzer_service
        n_payments = analyzer.count_payments(include_unpaid_invoice_payments=False)
        tot_payments = analyzer.calculate_tot_payments(include_unpaid_invoice_payments=False)
        return {
            "# PAGAMENTI": str(n_payments),
            "TOT. PAGAMENTI": f"{tot_payments:.2f} €",
        }

    def id_for_index(self, source_index):
        return self._source_model.data(source_index, PaymentsTableModel.ROLE_PAYMENT_ID)

    def row_for_id(self, item_id):
        return self._source_model.find_row_by_payment_id(item_id)

    def open_creator_dialog(self):
        # Creator non modale: post-creazione gestito da ``_after_primary_create``.
        dialog = QTPaymentCreateViewH(
            app_context=self.app_context,
            parent=self,
            on_payment_created=self._after_primary_create,
        )
        self._launch_creator(dialog)

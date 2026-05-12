from typing import TYPE_CHECKING

from PySide6.QtWidgets import QTableView

from QTViews.Creators.QT_invoice_create_view import QTInvoiceCreateViewH
from QTViews.ListViews.QT_base_list_view import QTBaseListView
from QTViews.ListViews.QT_invoices_table_model import InvoicesTableModel, RateDelegate

if TYPE_CHECKING:
    from App_context import AppContext


class QTInvoicesViewH(QTBaseListView):
    """
    List view delle fatture, sottoclasse di QTBaseListView.

    Tutta l'ossatura UI (aggregati / time window / search / tabella /
    bottone aggiungi) e la pipeline fetch → build_rows → swap del source
    model vivono in QTBaseListView. Qui si lega solo la parte che dipende
    dal dominio Fatture: query/analyzer service, costruzione del model
    InvoicesTableModel, formula degli aggregati LORDI/NETTI, dialog di
    creazione e mapping id ⇄ riga del source model.
    """

    AGGREGATE_KEYS = ("# FATTURE", "FATTURATO", "CREDITI", "MEDIA FATTURE")
    AGGREGATE_TOGGLE_OPTIONS = ("LORDI", "NETTI")
    TIME_WINDOWS = (
        ("60 GG", 60),
        ("90 GG", 90),
        ("365 GG", 365),
        #("TUTTE", None),
    )
    DEFAULT_WINDOW_INDEX = 0
    ADD_BUTTON_TEXT = "Aggiungi una fattura"
    ITEM_LABEL_PLURAL = "fatture"

    def __init__(
        self,
        app_context: "AppContext",
        initial_invoice_id=None,
        on_open_detail=None,
        parent=None,
    ):
        super().__init__(
            app_context=app_context,
            initial_item_id=initial_invoice_id,
            on_open_detail=on_open_detail,
            parent=parent,
        )

    # ------------------------------------------------------------------
    # Hook
    # ------------------------------------------------------------------

    # Wiring del warning service di dominio: vedi
    # ``QTBaseListView.collect_warnings`` per la pipeline.
    WARNING_SERVICE_ATTR = "invoice_warning_service"
    WARNING_DOMAIN_KEY = "fatture"

    def _setup_services(self, app_context: "AppContext"):
        self.invoices_query_service = app_context.invoices_query_service
        self.invoices_analyzer_service = app_context.invoices_analyzer_service
        self.clients_query_service = app_context.clients_query_service
        self.user_query_service = app_context.user_query_service
        self.productions_query_service = app_context.productions_query_service
        self.invoice_warning_service = app_context.invoice_warning_service

    def fetch_items(self, window_days):
        if window_days is None:
            return self.invoices_query_service.retrieve_invoices_map_list(year=-1)
        return self.invoices_query_service.get_invoices_for_days_window(window_days)

    def build_rows(self, items):
        return InvoicesTableModel.build_rows(
            items,
            self.clients_query_service,
            self.user_query_service,
            self.productions_query_service,
            self.invoices_query_service,
        )

    def create_table_model(self, rows):
        return InvoicesTableModel(rows, self)

    def configure_table(self, table: QTableView):
        table.setObjectName("InvoicesTable")
        table.verticalHeader().setDefaultSectionSize(36)
        table.horizontalHeader().setDefaultSectionSize(50)
        table.setStyleSheet(
            """
            #InvoicesTable {
                font-size: 12pt;
            }

            #InvoicesTable::item {
                padding-top: 8px;
                padding-bottom: 8px;
                padding-left: 6px;
                padding-right: 6px;
            }

            #InvoicesTable QHeaderView::section {
                font-size: 12pt;
                font-weight: bold;
                padding: 8px 6px;
            }
            """
        )
        table.setItemDelegateForColumn(InvoicesTableModel.COL_RATE, RateDelegate(self))

    def compute_aggregates(self, toggle_value):
        netti = toggle_value == "NETTI"
        analyzer = self.invoices_analyzer_service

        count = analyzer.count_invoices(include_unpaid_invoices=False)
        if netti:
            fatturato = analyzer.calculate_FATT_NETTO_invoiced(include_unpaid_invoices=False)
            crediti = analyzer.calculate_CRED_NETTO_invoiced(include_unpaid_invoices=False)
            media = analyzer.calculate_MEDIA_FATTURA_NETTO_invoiced(include_unpaid_invoices=False)
        else:
            fatturato = analyzer.calculate_FATT_LORDO_invoiced(include_unpaid_invoices=False)
            crediti = analyzer.calculate_CRED_LORDO_invoiced(include_unpaid_invoices=False)
            media = analyzer.calculate_MEDIA_FATTURA_LORDO_invoiced(include_unpaid_invoices=False)

        if media is None or media < 0:
            media = 0

        return {
            "# FATTURE": str(count),
            "FATTURATO": f"{fatturato:.2f} €",
            "CREDITI": f"{crediti:.2f} €",
            "MEDIA FATTURE": f"{media:.2f} €",
        }

    def id_for_index(self, source_index):
        return self._source_model.data(source_index, InvoicesTableModel.ROLE_INVOICE_ID)

    def row_for_id(self, item_id):
        return self._source_model.find_row_by_invoice_id(item_id)

    def open_creator_dialog(self):
        # Il dialog notifica l'esito tramite callback. La salviamo in un
        # contenitore mutabile cosi' che il chiamante (la base) la legga
        # dopo che dialog.exec() e' tornato.
        result = {"id": None}

        def _on_created(invoice_id):
            result["id"] = invoice_id

        dialog = QTInvoiceCreateViewH(
            app_context=self.app_context,
            parent=self,
            on_invoice_created=_on_created,
        )
        dialog.exec()
        return result["id"]

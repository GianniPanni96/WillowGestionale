"""
List view dei Clienti, sottoclasse di QTBaseListView.

Replica in chiave Qt il dominio della Views/ListViews/Clients_view_H.py
legacy: stessa time window (30/60/90/365 GG, default 60), stessa lista
di colonne con i dati aggregati (TOT. ENTRATE, # FATTURE, …).

Rispetto al pattern QT, l'ossatura UI (aggregati, time window, search,
QTableView, bottone aggiungi) e' interamente nella base; qui si
implementano solo gli hook di dominio: query/analyzer service, costruzione
del ClientsTableModel, formula degli aggregati globali e mapping id ⇄
riga del source model.
"""

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QTableView

from QTViews.Creators.QT_client_create_view import QTClientCreateViewH
from QTViews.ListViews.QT_base_list_view import QTBaseListView
from QTViews.ListViews.QT_clients_table_model import ClientsTableModel

if TYPE_CHECKING:
    from App_context import AppContext


class QTClientsViewH(QTBaseListView):
    """
    Implementazione concreta della list view Clienti su QTBaseListView.
    """

    AGGREGATE_KEYS = ("# CLIENTI", "TOT. ENTRATE", "TOT. CREDITI", "FATTURA MEDIA")
    AGGREGATE_TOGGLE_OPTIONS = None  # niente toggle LORDI/NETTI per i clienti

    TIME_WINDOWS = (
        ("30 GG", 30),
        ("60 GG", 60),
        ("90 GG", 90),
        ("365 GG", 365),
    )
    DEFAULT_WINDOW_INDEX = 1  # 60 GG, come la legacy
    LIST_VIEW_KEY = "clients"
    ADD_BUTTON_TEXT = "Aggiungi un cliente"
    ITEM_LABEL_PLURAL = "clienti"
    SEARCH_PLACEHOLDER = "Cerca in tutte le colonne…"

    def __init__(
        self,
        app_context: "AppContext",
        initial_client_id=None,
        on_open_detail=None,
        parent=None,
    ):
        super().__init__(
            app_context=app_context,
            initial_item_id=initial_client_id,
            on_open_detail=on_open_detail,
            parent=parent,
        )

    # ------------------------------------------------------------------
    # Hook
    # ------------------------------------------------------------------

    def _setup_services(self, app_context: "AppContext"):
        self.clients_query_service = app_context.clients_query_service
        self.clients_analyzer_service = app_context.clients_analyzer_service

    def fetch_items(self, window_days):
        if window_days is None:
            return self.clients_query_service.retrieve_clients_map_list()
        return self.clients_query_service.get_clients_for_days_window(window_days)

    def build_rows(self, items):
        return ClientsTableModel.build_rows(items, self.clients_analyzer_service)

    def create_table_model(self, rows):
        model = ClientsTableModel(rows, self)
        # Tooltip descrittivi sugli header (statici, indipendenti dai
        # valori). Vengono letti dal builder per mantenere la
        # separazione MVC.
        builder = getattr(self.app_context, self.AGGREGATE_TOOLTIP_BUILDER_ATTR, None)
        if builder is not None and hasattr(builder, "build_header_tooltips"):
            try:
                model.set_header_tooltips(builder.build_header_tooltips() or {})
            except Exception:
                pass
        return model

    def configure_table(self, table: QTableView):
        table.setObjectName("ClientsTable")
        table.verticalHeader().setDefaultSectionSize(36)
        table.horizontalHeader().setDefaultSectionSize(80)
        table.setStyleSheet(
            """
            #ClientsTable {
                font-size: 11pt;
            }

            #ClientsTable::item {
                padding-top: 8px;
                padding-bottom: 8px;
                padding-left: 6px;
                padding-right: 6px;
            }

            #ClientsTable QHeaderView::section {
                font-size: 11pt;
                font-weight: bold;
                padding: 8px 6px;
            }
            """
        )

    # Tooltip builder degli aggregati: il dominio Clienti calcola i
    # valori sui rows del modello (non sull'analyzer), quindi facciamo
    # override di ``_refresh_aggregate_tooltips`` per passare al builder
    # la lista di righe correntemente esposta.
    AGGREGATE_TOOLTIP_BUILDER_ATTR = "clients_aggregate_tooltip_builder"

    def compute_aggregates(self, toggle_value):
        # I valori aggregati vengono calcolati dalle righe gia' caricate
        # per evitare un secondo passaggio sull'analyzer service: e'
        # esattamente l'insieme di clienti che la time-window espone.
        rows = self._source_model.rows() if self._source_model is not None else []

        n_clienti = len(rows)
        tot_entrate = sum(r["tot_entrate"] for r in rows)
        tot_crediti = sum(r["tot_crediti"] for r in rows)
        tot_fatture = sum(r["num_fatture"] for r in rows)
        media_fattura = (tot_entrate / tot_fatture) if tot_fatture else 0

        return {
            "# CLIENTI": str(n_clienti),
            "TOT. ENTRATE": f"{round(tot_entrate, 2)} €",
            "TOT. CREDITI": f"{round(tot_crediti, 2)} €",
            "FATTURA MEDIA": f"{round(media_fattura, 2)} €",
        }

    def _refresh_aggregate_tooltips(self, toggle_value):
        # Override: passiamo i rows correnti al builder, perche' qui gli
        # aggregati sono calcolati per riga (vedi compute_aggregates).
        if not self._aggregate_cards:
            return
        builder = getattr(self.app_context, self.AGGREGATE_TOOLTIP_BUILDER_ATTR, None)
        if builder is None:
            return
        rows = self._source_model.rows() if self._source_model is not None else []
        try:
            tooltips = builder.build_tooltips(toggle_value=toggle_value, rows=rows) or {}
        except Exception:
            tooltips = {}
        self._apply_aggregate_tooltips(tooltips)

    def id_for_index(self, source_index):
        return self._source_model.data(source_index, ClientsTableModel.ROLE_CLIENT_ID)

    def row_for_id(self, item_id):
        return self._source_model.find_row_by_client_id(item_id)

    def context_menu_actions(self, row_data: dict) -> list[tuple[str, callable]]:
        return [
            ("Aggiungi una produzione", lambda: self._open_production_create(row_data)),
            ("Aggiungi un rimborso",    lambda: self._open_refund_create(row_data)),
        ]

    def _open_production_create(self, row_data: dict):
        from QTViews.Creators.QT_production_create_view import QTProductionCreateViewH

        def _on_created(_id):
            idx = self.window_combo.currentIndex()
            _, days = self.TIME_WINDOWS[idx]
            self._reload_data(window_days=days)

        dialog = QTProductionCreateViewH(
            app_context=self.app_context, parent=self, on_production_created=_on_created
        )
        dialog.prefill_client(row_data.get("name", ""))
        dialog.exec()

    def _open_refund_create(self, row_data: dict):
        from QTViews.Creators.QT_refund_create_view import QTRefundCreateViewH

        def _on_created(_id):
            idx = self.window_combo.currentIndex()
            _, days = self.TIME_WINDOWS[idx]
            self._reload_data(window_days=days)

        dialog = QTRefundCreateViewH(
            app_context=self.app_context, parent=self, on_refund_created=_on_created
        )
        dialog.prefill_client(row_data.get("name", ""))
        dialog.exec()

    def open_creator_dialog(self):
        # Stesso pattern di QTInvoicesViewH.open_creator_dialog: passiamo
        # al dialog una callback che riempie un contenitore mutabile con
        # l'id del nuovo cliente, leggibile dopo che dialog.exec() ritorna.
        result = {"id": None}

        def _on_created(client_id):
            result["id"] = client_id

        dialog = QTClientCreateViewH(
            app_context=self.app_context,
            parent=self,
            on_client_created=_on_created,
        )
        dialog.exec()
        return result["id"]

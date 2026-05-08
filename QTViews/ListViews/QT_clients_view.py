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

from PySide6.QtWidgets import QMessageBox, QTableView

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
    ADD_BUTTON_TEXT = "Aggiungi un cliente"
    ITEM_LABEL_PLURAL = "clienti"
    SEARCH_PLACEHOLDER = "Cerca cliente…"

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
        return ClientsTableModel(rows, self)

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

    def id_for_index(self, source_index):
        return self._source_model.data(source_index, ClientsTableModel.ROLE_CLIENT_ID)

    def row_for_id(self, item_id):
        return self._source_model.find_row_by_client_id(item_id)

    def open_creator_dialog(self):
        # Il creator clienti non e' ancora stato portato su Qt: per ora
        # mostriamo un placeholder coerente con le altre tab in attesa
        # di porting, e non si crea nulla.
        QMessageBox.information(
            self,
            "Aggiunta cliente",
            "L'aggiunta di un cliente non è ancora stata portata su Qt.",
        )
        return None

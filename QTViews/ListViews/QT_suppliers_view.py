"""
List view dei Fornitori, sottoclasse di QTBaseListView.

Replica in chiave Qt il dominio della Views/ListViews/Suppliers_view_H.py
legacy: stessa time window (30/60/90/365 GG, default 60), stesse colonne
con i dati aggregati (TOT. SPESE, # SPESE, SPESA MEDIA, …).

Tutta l'ossatura UI (aggregati, time window, search, QTableView,
bottone aggiungi) e' nella base; qui si implementano solo gli hook di
dominio: query/analyzer service, costruzione del SuppliersTableModel,
formula degli aggregati globali, dialog di creazione e mapping id ⇄
riga del source model.
"""

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QTableView

from QTViews.Creators.QT_supplier_create_view import QTSupplierCreateViewH
from QTViews.ListViews.QT_base_list_view import QTBaseListView
from QTViews.ListViews.QT_suppliers_table_model import SuppliersTableModel

if TYPE_CHECKING:
    from App_context import AppContext


class QTSuppliersViewH(QTBaseListView):
    """
    Implementazione concreta della list view Fornitori su QTBaseListView.
    """

    AGGREGATE_KEYS = ("# FORNITORI", "TOT. SPESE", "SPESA MEDIA")
    AGGREGATE_TOGGLE_OPTIONS = None  # niente toggle LORDI/NETTI per i fornitori

    TIME_WINDOWS = (
        ("30 GG", 30),
        ("60 GG", 60),
        ("90 GG", 90),
        ("365 GG", 365),
    )
    DEFAULT_WINDOW_INDEX = 1  # 60 GG, come la legacy
    LIST_VIEW_KEY = "suppliers"
    ADD_BUTTON_TEXT = "Aggiungi un fornitore"
    ITEM_LABEL_PLURAL = "fornitori"
    SEARCH_PLACEHOLDER = "Cerca in tutte le colonne…"

    def __init__(
        self,
        app_context: "AppContext",
        initial_supplier_id=None,
        on_open_detail=None,
        parent=None,
    ):
        super().__init__(
            app_context=app_context,
            initial_item_id=initial_supplier_id,
            on_open_detail=on_open_detail,
            parent=parent,
        )

    # ------------------------------------------------------------------
    # Hook
    # ------------------------------------------------------------------

    def _setup_services(self, app_context: "AppContext"):
        self.suppliers_query_service = app_context.suppliers_query_service
        self.suppliers_analyzer_service = app_context.suppliers_analyzer_service

    def fetch_items(self, window_days):
        if window_days is None:
            return self.suppliers_query_service.retrieve_suppliers_map_list(year=-1)
        return self.suppliers_query_service.get_suppliers_for_days_window(window_days)

    def build_rows(self, items):
        return SuppliersTableModel.build_rows(items, self.suppliers_analyzer_service)

    def create_table_model(self, rows):
        model = SuppliersTableModel(rows, self)
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
        table.setObjectName("SuppliersTable")
        table.verticalHeader().setDefaultSectionSize(36)
        table.horizontalHeader().setDefaultSectionSize(80)
        table.setStyleSheet(
            """
            #SuppliersTable {
                font-size: 11pt;
            }

            #SuppliersTable::item {
                padding-top: 8px;
                padding-bottom: 8px;
                padding-left: 6px;
                padding-right: 6px;
            }

            #SuppliersTable QHeaderView::section {
                font-size: 11pt;
                font-weight: bold;
                padding: 8px 6px;
            }
            """
        )

    # Tooltip builder degli aggregati: come per i Clienti, qui i valori
    # sono calcolati dai rows del modello -> override per passare ``rows=``.
    AGGREGATE_TOOLTIP_BUILDER_ATTR = "suppliers_aggregate_tooltip_builder"

    def compute_aggregates(self, toggle_value):
        # Calcolo dagli stessi rows gia' caricati dal source model: e'
        # l'insieme di fornitori che la time-window espone, evita un
        # secondo giro sull'analyzer.
        rows = self._source_model.rows() if self._source_model is not None else []

        n_fornitori = len(rows)
        tot_spese = sum(r["tot_spese"] for r in rows)
        tot_num_spese = sum(r["num_spese"] for r in rows)
        spesa_media = (tot_spese / tot_num_spese) if tot_num_spese else 0

        return {
            "# FORNITORI": str(n_fornitori),
            "TOT. SPESE": f"{tot_spese:.2f} €",
            "SPESA MEDIA": f"{spesa_media:.2f} €",
        }

    def _refresh_aggregate_tooltips(self, toggle_value):
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
        return self._source_model.data(source_index, SuppliersTableModel.ROLE_SUPPLIER_ID)

    def row_for_id(self, item_id):
        return self._source_model.find_row_by_supplier_id(item_id)

    def context_menu_actions(self, row_data: dict) -> list[tuple[str, callable]]:
        return [
            ("Aggiungi una spesa", lambda: self._open_expense_create(row_data)),
        ]

    def _open_expense_create(self, row_data: dict):
        from QTViews.Creators.QT_expense_create_view import QTExpenseCreateViewH

        def _on_created(_id):
            idx = self.window_combo.currentIndex()
            _, days = self.TIME_WINDOWS[idx]
            self._reload_data(window_days=days)

        dialog = QTExpenseCreateViewH(
            app_context=self.app_context, parent=self, on_expense_created=_on_created
        )
        dialog.prefill_supplier(row_data.get("name", ""))
        self._launch_creator(dialog)

    def open_creator_dialog(self):
        # Creator non modale: post-creazione gestito da ``_after_primary_create``.
        dialog = QTSupplierCreateViewH(
            app_context=self.app_context,
            parent=self,
            on_supplier_created=self._after_primary_create,
        )
        self._launch_creator(dialog)

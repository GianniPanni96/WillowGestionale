"""
List view delle Produzioni, sottoclasse di QTBaseListView.

Replica in chiave Qt il dominio della Views/ListViews/Productions_view_H.py
legacy: stessa time window (30/60/90/365 GG, default 60), stesse colonne
e stessi aggregati (# attive / chiuse / media ore / media €/h).

Tutta l'ossatura UI (aggregati, time window, search, QTableView,
bottone aggiungi) vive nella base; qui si implementano solo gli hook
di dominio: query/analyzer service, costruzione del
ProductionsTableModel, formula degli aggregati globali, dialog di
creazione e mapping id ⇄ riga del source model.
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QTableView

from Model import DBProductionsColumns
from QTViews.Creators.QT_production_create_view import QTProductionCreateViewH
from QTViews.ListViews.QT_base_list_view import QTBaseListView
from QTViews.ListViews.QT_productions_table_model import (
    ProductionsTableModel,
    ProductionStatusDelegate,
)

if TYPE_CHECKING:
    from App_context import AppContext


class QTProductionsViewH(QTBaseListView):
    """
    Implementazione concreta della list view Produzioni su QTBaseListView.
    """

    AGGREGATE_KEYS = (
        "# PRODUZIONI ATTIVE",
        "# PRODUZIONI CHIUSE",
        "MEDIA ORE",
        "MEDIA €/h",
    )
    AGGREGATE_TOGGLE_OPTIONS = None

    TIME_WINDOWS = (
        ("30 GG", 30),
        ("60 GG", 60),
        ("90 GG", 90),
        ("365 GG", 365),
    )
    DEFAULT_WINDOW_INDEX = 1  # 60 GG, come la legacy
    LIST_VIEW_KEY = "productions"
    ADD_BUTTON_TEXT = "Aggiungi una produzione"
    ITEM_LABEL_PLURAL = "produzioni"
    SEARCH_PLACEHOLDER = "Cerca in tutte le colonne…"

    def __init__(
        self,
        app_context: "AppContext",
        initial_production_id=None,
        on_open_detail=None,
        parent=None,
    ):
        super().__init__(
            app_context=app_context,
            initial_item_id=initial_production_id,
            on_open_detail=on_open_detail,
            parent=parent,
        )

    # ------------------------------------------------------------------
    # Hook
    # ------------------------------------------------------------------

    # Warnings di dominio (cfr ProductionWarningService).
    WARNING_SERVICE_ATTR = "production_warning_service"
    WARNING_DOMAIN_KEY = "produzioni"
    AGGREGATE_TOOLTIP_BUILDER_ATTR = "productions_aggregate_tooltip_builder"

    def _setup_services(self, app_context: "AppContext"):
        self.productions_query_service = app_context.productions_query_service
        self.productions_analyzer_service = app_context.productions_analyzer_service
        self.clients_query_service = app_context.clients_query_service
        self.production_controller = app_context.production_controller
        self.production_warning_service = app_context.production_warning_service

    def fetch_items(self, window_days):
        all_productions = self.productions_query_service.retrieve_productions_map_list(
            year=-1, include_prod_with_unpaid_invoices=True
        )
        if window_days is None:
            return all_productions

        # La legacy filtra per created_at della produzione: manteniamo
        # esattamente lo stesso criterio cosi' che le due tab espongano
        # lo stesso insieme di item.
        limit_date = datetime.now() - timedelta(days=window_days)
        filtered = []
        for production in all_productions:
            date_str = production.get(DBProductionsColumns.CREATED_AT.value)
            if not date_str:
                continue
            production_date = None
            for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    production_date = datetime.strptime(date_str, pattern)
                    break
                except ValueError:
                    continue
            if production_date is not None and production_date >= limit_date:
                filtered.append(production)
        return filtered

    def build_rows(self, items):
        return ProductionsTableModel.build_rows(
            items,
            self.clients_query_service,
            self.productions_analyzer_service,
        )

    def create_table_model(self, rows):
        # Il controller viene passato al model per permettere il
        # salvataggio inline dello stato dal combobox della colonna STATO.
        return ProductionsTableModel(rows, self.production_controller, self)

    def configure_table(self, table: QTableView):
        table.setObjectName("ProductionsTable")
        table.verticalHeader().setDefaultSectionSize(40)
        table.horizontalHeader().setDefaultSectionSize(80)
        table.setStyleSheet(
            """
            #ProductionsTable {
                font-size: 11pt;
            }

            #ProductionsTable::item {
                padding-top: 8px;
                padding-bottom: 8px;
                padding-left: 6px;
                padding-right: 6px;
            }

            #ProductionsTable QHeaderView::section {
                font-size: 11pt;
                font-weight: bold;
                padding: 8px 6px;
            }
            """
        )
        # Delegate combobox sulla colonna STATO: e' il delegate ad
        # aprire un QComboBox come editor, ma e' la view a tenerlo
        # sempre visibile via openPersistentEditor (vedi
        # _install_status_editors / _reload_data).
        table.setItemDelegateForColumn(
            ProductionsTableModel.COL_STATO,
            ProductionStatusDelegate(self),
        )

    def compute_aggregates(self, toggle_value):
        # Gli aggregati globali delle produzioni dipendono dallo stato
        # (attiva/chiusa) e dal prezzo orario derivato: deleghiamo
        # all'analyzer come fa la legacy, senza ricalcolare sui rows.
        analyzer = self.productions_analyzer_service

        n_attive = analyzer.count_active_productions(include_prod_with_unpaid_invoices=True, year=-1)
        n_chiuse = analyzer.count_closed_productions(include_prod_with_unpaid_invoices=True, year=-1)
        media_ore = analyzer.mean_hours_for_production(include_prod_with_unpaid_invoices=True, year=-1)
        media_eur_h = analyzer.mean_prezzo_orario(include_prod_with_unpaid_invoices=True, year=-1)

        return {
            "# PRODUZIONI ATTIVE": str(n_attive),
            "# PRODUZIONI CHIUSE": str(n_chiuse),
            "MEDIA ORE": f"{round(media_ore, 2)} h",
            "MEDIA €/h": f"{round(media_eur_h, 2)} €/h",
        }

    def id_for_index(self, source_index):
        return self._source_model.data(source_index, ProductionsTableModel.ROLE_PRODUCTION_ID)

    def row_for_id(self, item_id):
        return self._source_model.find_row_by_production_id(item_id)

    # ------------------------------------------------------------------
    # Override pipeline reload — combobox di stato persistente
    # ------------------------------------------------------------------

    def _reload_data(self, window_days=None):
        # Il base ricrea source_model e proxy a ogni reload, quindi qui
        # ci agganciamo "subito dopo" per aprire i persistent editor
        # sulla colonna STATO e per ricollegare il segnale di commit.
        super()._reload_data(window_days)

        if self._source_model is not None:
            self._source_model.status_committed.connect(self._on_status_committed)

        if self._proxy is not None:
            # Riapertura editor dopo filtri/sort: il proxy emette
            # rowsInserted quando il filtro torna a includere righe e
            # layoutChanged dopo ogni sort/refilter.
            self._proxy.rowsInserted.connect(self._install_status_editors)
            self._proxy.layoutChanged.connect(self._install_status_editors)

        self._install_status_editors()

    def _install_status_editors(self, *args, **kwargs):
        if self._proxy is None or self.table.model() is not self._proxy:
            return
        for r in range(self._proxy.rowCount()):
            idx = self._proxy.index(r, ProductionsTableModel.COL_STATO)
            if idx.isValid() and not self.table.isPersistentEditorOpen(idx):
                self.table.openPersistentEditor(idx)

    def _on_status_committed(self, _production_id, _new_status):
        # Cambio stato → ricalcolo aggregati globali (# attive, # chiuse,
        # media ore, media €/h dipendono tutti dallo stato).
        self._refresh_aggregates()

    def context_menu_actions(self, row_data: dict) -> list[tuple[str, callable]]:
        return [
            ("Aggiungi una fattura", lambda: self._open_invoice_create(row_data)),
        ]

    def _open_invoice_create(self, row_data: dict):
        from QTViews.Creators.QT_invoice_create_view import QTInvoiceCreateViewH

        def _on_created(_id):
            idx = self.window_combo.currentIndex()
            _, days = self.TIME_WINDOWS[idx]
            self._reload_data(window_days=days)

        dialog = QTInvoiceCreateViewH(
            app_context=self.app_context, parent=self, on_invoice_created=_on_created
        )
        dialog.prefill_from_production(
            row_data.get("client_name", ""),
            row_data.get("name", ""),
        )
        self._launch_creator(dialog)

    def open_creator_dialog(self):
        # Creator non modale: post-creazione gestito da ``_after_primary_create``.
        dialog = QTProductionCreateViewH(
            app_context=self.app_context,
            parent=self,
            on_production_created=self._after_primary_create,
        )
        self._launch_creator(dialog)

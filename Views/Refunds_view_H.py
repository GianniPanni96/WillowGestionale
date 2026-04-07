from datetime import datetime, timedelta

import customtkinter as ctk

from App_context import AppContext
from Analyzers.Refund_analyzer_service import RefundAnalyzerService
from Controllerss.Refund_controller import RefundController
from Gestionale_Enums import DBRefundsColumns, RefundsAggregateData
from QueryServices.Clients_query_service import ClientQueryService
from QueryServices.Refunds_query_service import RefundQueryService
from Views.BaseList_view import BaseListView
from Views.Creators.Refund_create_view import RefundCreateView
from Views.Details.Refund_detail_view import RefundDetailView
from Views.View_utils import ViewUtils


class RefundsViewH(BaseListView):
    """
    Implementazione concreta della lista Rimborsi basata su ``BaseListView``.
    """

    TAB_NAME = "Rimborsi"
    CARDS_FRAME_NAME = "refunds_cards_frame"
    ADD_BUTTON_TEXT = "Aggiungi un rimborso"

    aggregate_UOM = {
        RefundsAggregateData.NUMERO_RIMBORSI.value: "",
        RefundsAggregateData.TOT_RIMBORSI.value: "EUR",
    }

    HEADERS = ["NOME", "CLIENTE", "TOTALE", "DATA\nEMISSIONE", "CONTO\nCORRENTE"]

    SEARCH_BAR_OPTIONS = {
        "NOME RIMBORSO": "NOME RIMBORSO",
        "NOME CLIENTE": "NOME CLIENTE",
        "CONTO": "CONTO",
    }

    FILTER_MAPPING = {
        "NOME RIMBORSO": (0, ctk.CTkButton),
        "NOME CLIENTE": (1, ctk.CTkLabel),
        "CONTO": (4, ctk.CTkLabel),
    }

    SORT_CONFIG = {
        "TOTALE": {
            "label": "TOTALE",
            "access": "direct",
            "index": 2,
            "converter": "currency",
        },
        "DATA EMISSIONE": {
            "label": "DATA EMISSIONE",
            "access": "direct",
            "index": 3,
            "converter": "date",
        },
        "DATA CREAZIONE": {
            "label": "DATA CREAZIONE",
            "access": "database",
            "db_column": "created_at",
            "converter": "datetime",
        },
        "ULTIMA MODIFICA": {
            "label": "ULTIMA MODIFICA",
            "access": "database",
            "db_column": "updated_at",
            "converter": "datetime",
        }
    }

    SHOW_LAST_CARDS_OPTIONS = {
        "30 GG": "30 GG",
        "60 GG": "60 GG",
        "90 GG": "90 GG",
        "365 GG": "365 GG"
    }

    def __init__(self, app_context: AppContext, tab, initial_refund_id=None):
        super().__init__(
            tab,
            db_retrieving_function=app_context.refunds_query_service.retrieve_refunds_map_dictionary
        )

        self.app_context = app_context
        self.refund_controller: RefundController = app_context.refund_controller
        self.refunds_query_service: RefundQueryService = app_context.refunds_query_service
        self.refunds_analyzer_service: RefundAnalyzerService = app_context.refunds_analyzer_service
        self.clients_query_service: ClientQueryService = app_context.clients_query_service
        self.client_controller = app_context.client_controller
        self.account_controller = app_context.account_controller
        self.accounts_query_service = app_context.account_query_service

        self.refunds_card_list = self.cards_list
        self.refund_create_view = None

        self.initialize_view()
        self.show_last_cards_optionMenu.set("60 GG")
        self.show_last_cards()

        self.refund_detail_view = RefundDetailView(
            parent=self,
            app_context=self.app_context,
            back_callback=self.show_main_view,
            on_refund_changed=self._on_refund_changed
        )

        if initial_refund_id is not None:
            self.after(100, lambda: self.open_refund_detail_tab(initial_refund_id))
        else:
            self.show_main_view()

    def populate_global_infos(self):
        self.global_infos[RefundsAggregateData.NUMERO_RIMBORSI.value] = self.refunds_analyzer_service.count_refunds()
        self.global_infos[RefundsAggregateData.TOT_RIMBORSI.value] = round(
            self.refunds_analyzer_service.calculate_tot_refunds(), 2
        )

    def open_add_window(self):
        if self.refund_create_view is not None and self.refund_create_view.winfo_exists():
            self.refund_create_view.focus()
            self.refund_create_view.lift()
            return

        self.refund_create_view = RefundCreateView(
            parent=self,
            app_context=self.app_context,
            on_refund_created=self._on_refund_created,
            on_close=self._clear_refund_create_view
        )

    def _on_refund_created(self, refund_id, refund_data):
        self._refresh_global_infos()
        self.show_last_cards()
        self.filter_cards(None)

    def _on_refund_changed(self):
        self._refresh_global_infos()
        self.show_last_cards()
        self.filter_cards(None)

    def _clear_refund_create_view(self):
        self.refund_create_view = None

    def _refresh_global_infos(self):
        self.global_infos.clear()
        self.populate_global_infos()
        for key, amount_label in self.amount_aggregate_labels.items():
            amount_label.configure(text=f"{self.global_infos.get(key, 0)} {self.aggregate_UOM.get(key, '')}".strip())

    def load_items_chunked(self, items_list):
        items_list.sort(key=self._parse_refund_updated_at, reverse=True)

        extractor = ViewUtils.create_extractor_for_refunds(
            self.clients_query_service,
            self.accounts_query_service
        )
        ViewUtils.process_items_in_chunks(
            widget=self,
            items_list=items_list,
            add_card_callback=self.add_item_card,
            extract_args_callback=extractor,
            cards_frame=self.refunds_cards_frame
        )

    def add_item_card(self, refund_id, refund_name, amount, refund_date, client_name, account_name):
        card = ctk.CTkFrame(self.refunds_cards_frame, fg_color="dimgray")
        card.pack(pady=10, padx=8, fill="x", expand=True)

        data = [client_name, round(float(amount), 2), ViewUtils.invert_data_string(refund_date), account_name]
        units = ["", "EUR", "", ""]

        for col in range(len(self.HEADERS)):
            card.grid_columnconfigure(col, weight=1, uniform="refundcol")
        card.grid_rowconfigure(0, weight=1)

        btn = ctk.CTkButton(
            card,
            text=refund_name,
            command=lambda rid=refund_id: self.open_refund_detail_tab(rid)
        )
        btn.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        for idx, value in enumerate(data, start=1):
            label = ctk.CTkLabel(card, text=f"{value} {units[idx - 1]}".strip(), font=("Arial", 14))
            label.grid(row=0, column=idx, sticky="nsew", padx=5, pady=10)

        self.finalize_item_card(card, refund_name, btn)

    def open_refund_detail_tab(self, refund_id):
        self.main_container.pack_forget()
        self.refund_detail_view.pack(fill="both", expand=True)
        self.refund_detail_view.create_detail_tab(refund_id)

    def show_last_cards(self):
        selected = self.show_last_cards_optionMenu.get()
        days_map = {
            "30 GG": 30,
            "60 GG": 60,
            "90 GG": 90,
            "365 GG": 365
        }
        limit_date = datetime.now() - timedelta(days=days_map.get(selected, 30))

        all_refunds = self.refunds_query_service.retrieve_refunds_map_list()
        filtered_refunds = []
        for refund in all_refunds:
            refund_date = self._parse_datetime_value(refund.get(DBRefundsColumns.REFUND_DATE.value))
            if refund_date is not None and refund_date >= limit_date:
                filtered_refunds.append(refund)

        self.reload_cards(filtered_refunds)

    def _parse_refund_updated_at(self, refund):
        return self._parse_datetime_value(refund.get(DBRefundsColumns.UPDATED_AT.value)) or datetime.min

    def _parse_datetime_value(self, value):
        if not value:
            return None

        for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, pattern)
            except ValueError:
                continue
        return None

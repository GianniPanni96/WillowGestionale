from datetime import datetime, timedelta

import customtkinter as ctk

from AnalyzerServices.Payment_analyzer_service import PaymentAnalyzerService
from App_context import AppContext
from Controllers import AccountController, UpdatesController
from Gestionale_Enums import DBPaymentsColumns
from QueryServices.Account_query_service import AccountQueryService
from QueryServices.Invoices_query_service import InvoiceQueryService
from Views.BaseList_view import BaseListView
from Views.Creators.Payment_create_view import PaymentCreateView
from Views.Details.Payment_detail_view import PaymentDetailView
from Views.View_utils import ViewUtils

from QueryServices.Productions_query_service import ProductionQueryService
from QueryServices.Clients_query_service import ClientQueryService


class PaymentsViewH(BaseListView):
    """
    Implementazione concreta della lista Pagamenti basata su ``BaseListView``.

    La view gestisce solo lista, filtri, ordinamento e apertura di creator/detail.
    La logica del singolo pagamento vive invece nei moduli dedicati.
    """

    TAB_NAME = "Pagamenti"
    CARDS_FRAME_NAME = "payments_cards_frame"
    ADD_BUTTON_TEXT = "Aggiungi un pagamento"

    aggregate_UOM = {
        "# PAGAMENTI": "",
        "TOT. PAGAMENTI": "€",
    }

    HEADERS = [
        "NOME", "CLIENTE", "PRODUZIONE", "FATTURA", "TOTALE",
        "DATA \nCONTABILIZZAZIONE", "RATA \nFATTURA", "CONTO \nCORRENTE"
    ]

    SEARCH_BAR_OPTIONS = {
        "NOME PAGAMENTO": "NOME PAGAMENTO",
        "NOME CLIENTE": "NOME CLIENTE",
        "NOME PRODUZIONE": "NOME PRODUZIONE",
        "NOME FATTURA": "NOME FATTURA",
        "CONTO": "CONTO",
    }

    FILTER_MAPPING = {
        "NOME PAGAMENTO": (0, ctk.CTkButton),
        "NOME CLIENTE": (1, ctk.CTkLabel),
        "NOME PRODUZIONE": (2, ctk.CTkLabel),
        "NOME FATTURA": (3, ctk.CTkLabel),
        "CONTO": (7, ctk.CTkLabel),
    }

    SORT_CONFIG = {
        "NOME": {
            "label": "NOME",
            "access": "direct",
            "index": 0,
            "converter": "text",
        },
        "TOTALE": {
            "label": "TOTALE",
            "access": "direct",
            "index": 4,
            "converter": "currency",
        },
        "DATA CONTABILIZZAZIONE": {
            "label": "DATA \nCONTABILIZZAZIONE",
            "access": "direct",
            "index": 5,
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
        },
    }

    SHOW_LAST_CARDS_OPTIONS = {
        "30 GG": "30 GG",
        "60 GG": "60 GG",
        "90 GG": "90 GG",
        "365 GG": "365 GG",
    }

    def __init__(self, app_context: AppContext, tab, initial_payment_id=None):
        self.app_context = app_context
        self.payment_query_service = app_context.payments_query_service
        self.payment_analyzer_service = PaymentAnalyzerService(self.payment_query_service, app_context.db_model)
        self.payment_warning_service = app_context.payment_warning_service

        super().__init__(tab, db_retrieving_function=self.payment_query_service.retrieve_payments_map_dictionary)

        self.clients_query_service: ClientQueryService = app_context.clients_query_service
        self.productions_query_service:ProductionQueryService = app_context.productions_query_service
        self.account_controller: AccountController = app_context.account_controller
        self.accounts_query_service:AccountQueryService = app_context.account_query_service
        self.invoices_query_service: InvoiceQueryService = app_context.invoices_query_service
        self.update_controller: UpdatesController = app_context.update_controller

        self.payments_card_list = self.cards_list
        self.payment_create_view = None

        self.update_controller.register_on_modify_invoice_view_cllbks(self.attach_warning_on_a_card)

        self.initialize_view()
        self.show_last_cards_optionMenu.set("60 GG")
        self.show_last_cards()

        self.payment_detail_view = PaymentDetailView(
            parent=self,
            app_context=self.app_context,
            back_callback=self.show_main_view,
            on_payment_changed=self._on_payment_changed
        )

        if initial_payment_id is not None:
            self.after(100, lambda: self.open_payment_detail_tab(initial_payment_id))

    def populate_global_infos(self):
        self.global_infos["# PAGAMENTI"] = self.payment_analyzer_service.count_payments(include_unpaid_invoice_payments=False)
        self.global_infos["TOT. PAGAMENTI"] = f"{self.payment_analyzer_service.calculate_tot_payments(include_unpaid_invoice_payments=False):.2f}"

    def open_add_window(self):
        if self.payment_create_view is not None and self.payment_create_view.winfo_exists():
            self.payment_create_view.focus()
            self.payment_create_view.lift()
            return

        self.payment_create_view = PaymentCreateView(
            parent=self,
            app_context=self.app_context,
            on_payment_created=self._on_payment_created,
            on_close=self._clear_payment_create_view
        )

    def _clear_payment_create_view(self):
        self.payment_create_view = None

    def _on_payment_created(self, payment_id, payment_data):
        self._refresh_global_infos()
        self.show_last_cards()
        self.filter_cards(None)

    def _on_payment_changed(self):
        self._refresh_global_infos()
        self.show_last_cards()

    def _refresh_global_infos(self):
        self.global_infos.clear()
        self.populate_global_infos()
        for key, amount_label in self.amount_aggregate_labels.items():
            amount_label.configure(text=f"{self.global_infos.get(key, 0)} {self.aggregate_UOM.get(key, '')}".strip())

    def load_items_chunked(self, items_list):
        items_list.sort(key=self._parse_payment_updated_at, reverse=True)

        extractor = ViewUtils.create_extractor_for_payments(
            self.invoices_query_service,
            self.clients_query_service,
            self.productions_query_service,
            self.accounts_query_service
        )

        ViewUtils.process_items_in_chunks(
            widget=self,
            items_list=items_list,
            add_card_callback=self.add_item_card,
            extract_args_callback=extractor,
            cards_frame=self.payments_cards_frame
        )

    def collect_card_warnings(self, items_list):
        return self.payment_warning_service.collect_warnings_for_list(items_list)

    def add_item_card(self, payment_id, payment_name, amount, payment_date, linked_rata, client_name, production_name, invoice_name, account_name):
        card = ctk.CTkFrame(self.payments_cards_frame, fg_color="dimgray")
        card.pack(pady=10, padx=8, fill="x", expand=True)

        data = [
            client_name,
            production_name,
            invoice_name,
            round(float(amount), 2),
            ViewUtils.invert_data_string(payment_date),
            linked_rata,
            account_name,
        ]
        units = ["", "", "", "EUR", "", "", ""]

        for col in range(1 + len(data)):
            card.grid_columnconfigure(col, weight=1, uniform="paymentcol")
        card.grid_rowconfigure(0, weight=1)

        btn = ctk.CTkButton(
            card,
            text=payment_name,
            command=lambda pid=payment_id: self.open_payment_detail_tab(pid)
        )
        btn.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        for idx, value in enumerate(data, start=1):
            text = f"{value} {units[idx - 1]}".strip()
            label = ctk.CTkLabel(card, text=text, font=("Arial", 14))
            label.grid(row=0, column=idx, sticky="nsew", padx=5, pady=10)

        self.finalize_item_card(card, payment_name, btn)

    def open_payment_detail_tab(self, payment_id):
        self.main_container.pack_forget()
        self.payment_detail_view.pack(fill="both", expand=True)
        self.payment_detail_view.create_detail_tab(payment_id)

    def show_last_cards(self):
        selected = self.show_last_cards_optionMenu.get()
        days_map = {"30 GG": 30, "60 GG": 60, "90 GG": 90, "365 GG": 365}
        limit_date = datetime.now() - timedelta(days=days_map.get(selected, 30))

        all_payments = self.payment_query_service.retrieve_payments_map_list(year=None, include_unpaid_invoice_payments=True)

        filtered_payments = []
        for payment in all_payments:
            payment_date = self._parse_date_value(payment.get(DBPaymentsColumns.PAYMENT_DATE.value))
            if payment_date is not None and payment_date >= limit_date:
                filtered_payments.append(payment)

        self.reload_cards(filtered_payments)

    def attach_warning_on_a_card(self, payment_name, warning):
        self.cards_warnings[payment_name] = warning
        card = self.payments_card_list.get(payment_name)
        if card is None:
            return

        ViewUtils.toggle_warning_on_card(card, self.cards_warnings)
        button = next((child for child in card.winfo_children() if isinstance(child, ctk.CTkButton)), None)
        if button is not None:
            ViewUtils.add_tooltip(button, warning)

    def _parse_payment_updated_at(self, payment):
        return self._parse_datetime_value(payment.get(DBPaymentsColumns.UPDATED_AT.value)) or datetime.min

    def _parse_datetime_value(self, value):
        if not value:
            return None

        for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, pattern)
            except ValueError:
                continue
        return None

    def _parse_date_value(self, value):
        parsed = self._parse_datetime_value(value)
        return parsed

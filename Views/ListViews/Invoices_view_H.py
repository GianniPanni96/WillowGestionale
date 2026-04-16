import tkinter as tk
from datetime import datetime

import customtkinter as ctk

from App_context import AppContext
from AnalyzerServices.Invoice_analyzer_service import InvoiceAnalyzerService
from Controllerss.User_controller import UserController
from Controllerss.Invoice_controller import InvoiceController
from Model import DBInvoicesColumns, DBPaymentsColumns
from QueryServices.Clients_query_service import ClientQueryService
from QueryServices.Invoices_query_service import InvoiceQueryService
from QueryServices.Productions_query_service import ProductionQueryService
from QueryServices.Users_query_service import UserQueryService
from Utils.Controller_utils import ControllerUtils
from Views.ListViews.BaseList_view import BaseListView
from Views.Creators.Invoice_create_view import InvoiceCreateView
from Views.Details.Invoice_detail_view import InvoiceDetailView
from Views.View_utils import ViewUtils
from Gestionale_Enums import*


class InvoicesViewH(BaseListView):
    """
    Implementazione concreta della lista Fatture basata su ``BaseListView``.

    La classe contiene solo la competenza della list view: card, filtri,
    aggregati e navigazione verso detail/creator.
    """

    class InvoicesStatusColors(Enum):
        CRITICAL = "#f52f2f"
        WARNING = "#e39e27"
        NORMAL = ctk.ThemeManager.theme["CTkLabel"]["text_color"]
        GOOD = "#2ca31c"
        STORNATA = "#2444d4"
        NOT_EXISTING = "#424242"

    TAB_NAME = "Fatture"
    CARDS_FRAME_NAME = "invoices_cards_frame"
    ADD_BUTTON_TEXT = "Aggiungi una fattura"

    aggregate_UOM = {
        "# FATTURE": "",
        "FATTURATO": "€",
        "CREDITI": "€",
        "MEDIA FATTURE": "€",
    }

    HEADERS = [
        "NOME",
        "CLIENTE",
        "UTENTE",
        "PRODUZIONE\nASSOCIATA",
        "DATA\nEMISSIONE",
        "STATO",
        "RATE",
        "NETTO A\nPAGARE",
        "TIPOLOGIA",
    ]

    SEARCH_BAR_OPTIONS = {
        "NOME FATTURA": "NOME FATTURA",
        "NOME CLIENTE": "NOME CLIENTE",
        "NOME UTENTE": "NOME UTENTE",
        "NOME PRODUZIONE": "NOME PRODUZIONE",
    }

    FILTER_MAPPING = {
        "NOME FATTURA": (0, ctk.CTkButton),
        "NOME CLIENTE": (1, ctk.CTkLabel),
        "NOME UTENTE": (2, ctk.CTkLabel),
        "NOME PRODUZIONE": (3, ctk.CTkLabel),
    }

    SORT_CONFIG = {
        "NOME": {
            "label": "NOME",
            "access": "direct",
            "index": 0,
            "converter": "text",
        },
        "NETTO A PAGARE": {
            "label": "NETTO A\nPAGARE",
            "access": "direct",
            "index": 7,
            "converter": "currency",
        },
        "DATA EMISSIONE": {
            "label": "DATA EMISSIONE",
            "access": "direct",
            "index": 4,
            "converter": "date",
        },
        "DATA CREAZIONE": {
            "label": "DATA CREAZIONE",
            "access": "database",
            "db_column": DBInvoicesColumns.CREATED_AT.value,
            "converter": "datetime",
        },
        "ULTIMA MODIFICA": {
            "label": "ULTIMA MODIFICA",
            "access": "database",
            "db_column": DBInvoicesColumns.UPDATED_AT.value,
            "converter": "datetime",
        },
    }

    SHOW_LAST_CARDS_OPTIONS = {
        "30 GG": "30 GG",
        "60 GG": "60 GG",
        "90 GG": "90 GG",
        "365 GG": "365 GG",
    }

    def __init__(self, app_context: AppContext, tab, initial_invoice_id=None):
        super().__init__(
            tab,
            db_retrieving_function=app_context.invoices_query_service.retrieve_invoices_map_dictionary,
        )

        self.app_context: AppContext = app_context
        self.invoice_controller: InvoiceController = app_context.invoice_controller
        self.invoices_analyzer_service: InvoiceAnalyzerService = app_context.invoices_analyzer_service
        self.clients_query_service: ClientQueryService = app_context.clients_query_service
        self.productions_query_service: ProductionQueryService = app_context.productions_query_service
        self.user_controller: UserController = app_context.user_controller
        self.user_query_service: UserQueryService = app_context.user_query_service
        self.update_controller = app_context.update_controller
        self.invoices_query_service: InvoiceQueryService = app_context.invoices_query_service
        self.invoice_warning_service = app_context.invoice_warning_service

        self.invoices_card_list = self.cards_list
        self.invoice_card_labels_status = {}
        self.invoice_card_rate_frames = {}
        self.global_infos_lordi = {}
        self.global_infos_netti = {}
        self.lordo_netto_switch_var = tk.BooleanVar(value=False)
        self.invoice_create_view = None

        self._create_lordo_netto_switch()
        self.initialize_view()
        self.switch_lordo_netto()

        self.show_last_cards_optionMenu.set("60 GG")
        self.show_last_cards()

        self.update_controller.register_on_delete_production_view_cllbks(self.attach_warning_on_a_card)

        self.invoice_detail_view = InvoiceDetailView(
            parent=self,
            app_context=self.app_context,
            back_callback=self.show_main_view,
        )

        if initial_invoice_id is not None:
            self.after(100, lambda: self.open_invoice_detail_tab(initial_invoice_id))
        else:
            self.show_main_view()

    def _create_lordo_netto_switch(self):
        self.switch_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.switch_frame.pack(fill="x", before=self.search_bar_frame)

        ctk.CTkLabel(
            self.switch_frame,
            text="LORDI   ",
            font=("Arial", 20),
        ).pack(pady=(10, 0), padx=(10, 0), anchor="w", side=ctk.LEFT)

        self.lordo_netto_switch = ctk.CTkSwitch(
            self.switch_frame,
            text="  NETTI",
            font=("Arial", 20),
            command=self.switch_lordo_netto,
            width=200,
            switch_width=60,
            height=48,
            switch_height=20,
            variable=self.lordo_netto_switch_var,
        )
        self.lordo_netto_switch.pack(pady=(10, 0), anchor="w")

    def populate_global_infos(self):
        self.global_infos_lordi.clear()
        self.global_infos_netti.clear()

        self.global_infos_lordi["# FATTURE"] = self.invoices_analyzer_service.count_invoices(
            include_unpaid_invoices=False
        )
        self.global_infos_lordi["FATTURATO"] = self.invoices_analyzer_service.calculate_FATT_LORDO_invoiced(
            include_unpaid_invoices=False
        )
        self.global_infos_lordi["CREDITI"] = self.invoices_analyzer_service.calculate_CRED_LORDO_invoiced(
            include_unpaid_invoices=False
        )
        media_fatture_lordo = self.invoices_analyzer_service.calculate_MEDIA_FATTURA_LORDO_invoiced(
            include_unpaid_invoices=False
        )
        self.global_infos_lordi["MEDIA FATTURE"] = media_fatture_lordo if media_fatture_lordo >= 0 else 0

        self.global_infos_netti["# FATTURE"] = self.invoices_analyzer_service.count_invoices(
            include_unpaid_invoices=False
        )
        self.global_infos_netti["FATTURATO"] = self.invoices_analyzer_service.calculate_FATT_NETTO_invoiced(
            include_unpaid_invoices=False
        )
        self.global_infos_netti["CREDITI"] = self.invoices_analyzer_service.calculate_CRED_NETTO_invoiced(
            include_unpaid_invoices=False
        )
        media_fatture_netto = self.invoices_analyzer_service.calculate_MEDIA_FATTURA_NETTO_invoiced(
            include_unpaid_invoices=False
        )
        self.global_infos_netti["MEDIA FATTURE"] = media_fatture_netto if media_fatture_netto >= 0 else 0

        self.global_infos = self.global_infos_lordi.copy()

    def toggle_aggregate_data(self):
        self.populate_global_infos()
        self.switch_lordo_netto()

    def switch_lordo_netto(self):
        current_infos = self.global_infos_netti if self.lordo_netto_switch_var.get() else self.global_infos_lordi

        for key, label in self.amount_aggregate_labels.items():
            uom = self.aggregate_UOM.get(key, "")
            suffix = f" {uom}" if uom else ""
            label.configure(text=f"{current_infos.get(key, 0)}{suffix}")

    def get_additional_ui_state(self):
        return {
            "lordo_netto_enabled": bool(self.lordo_netto_switch_var.get())
        }

    def apply_additional_ui_state(self, state):
        lordo_netto_enabled = state.get("lordo_netto_enabled")
        if lordo_netto_enabled is None:
            return

        self.lordo_netto_switch_var.set(bool(lordo_netto_enabled))
        self.switch_lordo_netto()

    def open_add_window(self):
        if self.invoice_create_view is not None and self.invoice_create_view.winfo_exists():
            self.invoice_create_view.focus()
            self.invoice_create_view.lift()
            return

        self.invoice_create_view = InvoiceCreateView(
            parent=self,
            app_context=self.app_context,
            on_invoice_created=self._on_invoice_created,
            on_close=self._clear_invoice_create_view,
        )

    def _on_invoice_created(self, invoice_id, invoice_data):
        self.toggle_aggregate_data()
        self.show_last_cards()
        self.filter_cards(None)

    def _clear_invoice_create_view(self):
        self.invoice_create_view = None

    def collect_card_warnings(self, items_list):
        return self.invoice_warning_service.collect_warnings_for_list(items_list)

    def load_items_chunked(self, items_list):
        extractor = ViewUtils.create_extractor_for_invoices(
            self.clients_query_service,
            self.user_query_service,
            self.productions_query_service,
        )
        ViewUtils.process_items_in_chunks(
            widget=self,
            items_list=items_list,
            add_card_callback=self.add_item_card,
            extract_args_callback=extractor,
            cards_frame=getattr(self, self.CARDS_FRAME_NAME),
        )

    def add_item_card(
        self,
        invoice_id,
        nome,
        cliente,
        utente,
        produzione,
        data_creazione,
        stato,
        rate,
        tot_documento,
        tipologia,
    ):
        card = ctk.CTkFrame(self.invoices_cards_frame, fg_color="dimgray")
        card.pack(pady=10, padx=5, fill="x", expand=True)

        data = [
            nome,
            cliente,
            utente,
            produzione,
            ViewUtils.invert_data_string(data_creazione),
            stato,
            rate,
            round(tot_documento, 2),
            tipologia,
        ]

        for col in range(len(data)):
            card.grid_columnconfigure(col, weight=1, uniform="cardcol")
        card.grid_rowconfigure(0, weight=1)

        btn = ctk.CTkButton(
            card,
            text=nome,
            command=lambda current_invoice_id=invoice_id: self.open_invoice_detail_tab(current_invoice_id),
        )
        btn.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        for idx, val in enumerate(data[1:], start=1):
            if idx != 6:
                text = f"{val}" if idx != 7 else f"{val}€"
                lbl = ctk.CTkLabel(card, text=text, font=("Arial", 14))
                lbl.grid(row=0, column=idx, sticky="nsew", padx=5, pady=10)

                if idx == 5:
                    self.invoice_card_labels_status[invoice_id] = lbl
            else:
                rate_frame = ctk.CTkFrame(card)
                rate_frame.grid(row=0, column=idx, sticky="nsew", padx=(10, 5), pady=10, ipadx=10)

                for rate_col in range(3):
                    rate_frame.grid_columnconfigure(rate_col, weight=1, uniform="ratecol")
                rate_frame.grid_rowconfigure(0, weight=1)

                for rate_col, txt in enumerate(["1", "2", "3"]):
                    rlbl = ctk.CTkLabel(rate_frame, text=txt, font=("Arial", 14))
                    rlbl.grid(row=0, column=rate_col, sticky="nsew", padx=2)

                self.invoice_card_rate_frames[invoice_id] = rate_frame

        self.finalize_item_card(card, nome, btn)
        self.toggle_specific_invoice_rate_color(invoice_id)
        self.toggle_specific_invoice_status_color(invoice_id)

    def open_invoice_detail_tab(self, invoice_id):
        self.main_container.pack_forget()
        self.invoice_detail_view.pack(fill="both", expand=True)
        self.invoice_detail_view.create_detail_tab(invoice_id)

    def show_last_cards(self):
        selected = self.show_last_cards_optionMenu.get()

        days_map = {
            "30 GG": 30,
            "60 GG": 60,
            "90 GG": 90,
            "365 GG": 365,
        }

        days = days_map.get(selected, 30)
        filtered_invoices = self.invoices_query_service.get_invoices_for_days_window(days)
        self.reload_cards(filtered_invoices)

    def toggle_specific_invoice_status_color(self, invoice_id):
        fattura = self.invoices_query_service.retrieve_invoice_map_by_id(invoice_id)
        label = self.invoice_card_labels_status.get(invoice_id)
        if not fattura or label is None:
            return

        stato = fattura[DBInvoicesColumns.STATUS.value]
        rateizzazione = fattura[DBInvoicesColumns.NUMERO_RATE.value]

        if rateizzazione == int(Rateizzazione.TRE.value):
            if stato == InvoiceRateizzSatus.PAGATA.value:
                label.configure(text_color=self.InvoicesStatusColors.GOOD.value)
            elif stato == InvoiceRateizzSatus.CRITICA.value:
                label.configure(text_color=self.InvoicesStatusColors.WARNING.value)
            elif stato == InvoiceRateizzSatus.SCADUTA.value:
                label.configure(text_color=self.InvoicesStatusColors.CRITICAL.value)
            elif stato == InvoiceSatus.STORNATA.value:
                label.configure(text_color=self.InvoicesStatusColors.STORNATA.value)
            else:
                label.configure(text_color=self.InvoicesStatusColors.NORMAL.value)
            return

        if stato in (InvoiceSatus.SALDATA.value, InvoiceRateizzSatus.PAGATA.value):
            label.configure(text_color=self.InvoicesStatusColors.GOOD.value)
        elif stato == InvoiceSatus.SCADUTA.value:
            label.configure(text_color=self.InvoicesStatusColors.CRITICAL.value)
        elif stato == InvoiceSatus.STORNATA.value:
            label.configure(text_color=self.InvoicesStatusColors.STORNATA.value)
        else:
            label.configure(text_color=self.InvoicesStatusColors.NORMAL.value)

    def toggle_specific_invoice_rate_color(self, invoice_id):
        today = datetime.today().date()
        invoice_with_payments = self.invoices_query_service.retrieve_invoice_with_payments_map_list(invoice_id)
        if not invoice_with_payments:
            return

        fattura = invoice_with_payments[0]
        frame = self.invoice_card_rate_frames.get(invoice_id)
        if frame is None:
            return

        scadenza_1 = fattura[DBInvoicesColumns.DATA_SCADENZA_1.value]
        scadenza_2 = fattura[DBInvoicesColumns.DATA_SCADENZA_2.value]
        scadenza_3 = fattura[DBInvoicesColumns.DATA_SCADENZA_3.value]

        try:
            netto = float(fattura[DBInvoicesColumns.NETTO_A_PAGARE.value])
            num_rate = int(fattura[DBInvoicesColumns.NUMERO_RATE.value])
            importo_per_rata = netto / num_rate
        except (TypeError, ValueError, ZeroDivisionError):
            return

        pagamenti_per_rata = {1: 0.0, 2: 0.0, 3: 0.0}
        for payment in invoice_with_payments:
            try:
                linked_rata = int(payment[DBPaymentsColumns.LINKED_RATA.value])
                payment_amount = float(payment[DBPaymentsColumns.PAYMENT_AMOUNT.value])
            except (TypeError, ValueError, KeyError):
                continue

            if linked_rata in pagamenti_per_rata:
                pagamenti_per_rata[linked_rata] += payment_amount

        labels = frame.winfo_children()
        if len(labels) < 3:
            return

        def configure_label(rate_idx, due_date_str, payment_sum):
            if payment_sum > 0:
                if payment_sum >= importo_per_rata or (importo_per_rata - payment_sum) < 5:
                    labels[rate_idx].configure(text_color=self.InvoicesStatusColors.GOOD.value)
                else:
                    labels[rate_idx].configure(text_color=self.InvoicesStatusColors.WARNING.value)
                return

            due_date = ControllerUtils.parse_date(due_date_str)
            if due_date is None:
                labels[rate_idx].configure(text_color=self.InvoicesStatusColors.NOT_EXISTING.value)
            elif today > due_date:
                labels[rate_idx].configure(text_color=self.InvoicesStatusColors.CRITICAL.value)
            elif today == due_date:
                labels[rate_idx].configure(text_color=self.InvoicesStatusColors.WARNING.value)
            else:
                labels[rate_idx].configure(text_color=self.InvoicesStatusColors.NORMAL.value)

        configure_label(0, scadenza_1, pagamenti_per_rata[1])

        if scadenza_2 is not None and scadenza_3 is not None:
            configure_label(1, scadenza_2, pagamenti_per_rata[2])
            configure_label(2, scadenza_3, pagamenti_per_rata[3])
        else:
            labels[1].configure(text_color=self.InvoicesStatusColors.NOT_EXISTING.value)
            labels[2].configure(text_color=self.InvoicesStatusColors.NOT_EXISTING.value)

    def attach_warning_on_a_card(self, invoice_name, warning):
        self.cards_warnings[invoice_name] = warning
        card = self.cards_list.get(invoice_name)
        if card is None:
            return

        ViewUtils.toggle_warning_on_card(card, self.cards_warnings)
        for child in card.winfo_children():
            if isinstance(child, ctk.CTkButton):
                ViewUtils.add_tooltip(child, warning)
                break

    def _cleanup_extra_references(self):
        if hasattr(self, "update_controller") and self.update_controller is not None:
            self.update_controller.unregister_on_delete_production_view_cllbk(self.attach_warning_on_a_card)

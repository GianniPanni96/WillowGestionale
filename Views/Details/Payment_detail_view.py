from datetime import datetime
import re

import customtkinter as ctk
from tkcalendar import Calendar

from App_context import AppContext
from Controllerss.Payment_controller import PaymentsController
from Gestionale_Enums import DBAccountsColumns, DBClientsColumns, DBInvoicesColumns, DBPaymentsColumns, DBProductionsColumns
from QueryServices.Account_query_service import AccountQueryService
from QueryServices.Clients_query_service import ClientQueryService
from QueryServices.Invoices_query_service import InvoiceQueryService
from QueryServices.Payments_query_service import PaymentQueryService
from QueryServices.Productions_query_service import ProductionQueryService
from Views.View_utils import ViewUtils
from Views.CustomWidgets.Filterable_combo_box import FilterableComboBox


class PaymentDetailView(ctk.CTkFrame):
    """
    Vista dettaglio pagamento separata dalla list view.

    Contiene la logica di modifica, warning e cancellazione del singolo
    pagamento, lasciando alla ``PaymentsViewH`` solo la gestione lista/tab.
    """

    ACCOUNT_FIELD = "CONTO"
    INVOICE_FIELD = "FATTURA ASSOCIATA"
    PRODUCTION_FIELD = "PRODUZIONE ASSOCIATA"

    def __init__(self, parent, app_context: AppContext, back_callback, on_payment_changed=None):
        super().__init__(parent)

        self.app_context = app_context
        self.parent = parent
        self.back_callback = back_callback
        self.on_payment_changed = on_payment_changed

        self.payment_controller:PaymentsController = app_context.payment_controller
        self.payment_query_service:PaymentQueryService = app_context.payments_query_service
        self.account_query_service:AccountQueryService = app_context.account_query_service
        self.clients_query_service:ClientQueryService = app_context.clients_query_service
        self.invoices_query_service:InvoiceQueryService = app_context.invoices_query_service
        self.productions_query_service:ProductionQueryService = app_context.productions_query_service
        self.update_controller = app_context.update_controller
        self.event_bus = app_context.event_bus

        self.current_payment_id = None
        self.payment = None
        self.payment_info_widgets = {}
        self.payment_info_labels = {}
        self.error_labels_payments = {}

        self.configure(fg_color="transparent")

        self.head_frame = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.back_button = ctk.CTkButton(
            self.head_frame,
            text="Elenco Pagamenti",
            command=self._cleanup_and_go_back
        )
        self.title_label = ctk.CTkLabel(self.head_frame, font=("Arial", 22, "bold"))
        self.switch_modify = ctk.CTkSwitch(
            self.head_frame,
            text="Abilita la modifica",
            command=lambda: self.toggle_edit(self.content_frame)
        )
        self.content_frame = ctk.CTkScrollableFrame(self)

        self._setup_base_layout()

    def _setup_base_layout(self):
        self.head_frame.pack(fill="x", pady=5, padx=5)
        self.back_button.pack(anchor="w", side="left", pady=10, padx=10)
        self.title_label.pack(anchor="c", side="left", fill="x", expand=True, pady=10)
        self.switch_modify.pack(anchor="e", side="left", pady=10, padx=10)
        self.content_frame.pack(fill="both", expand=True, pady=20, padx=20)

    def create_detail_tab(self, payment_id):
        self.current_payment_id = payment_id
        self._clear_content()

        payment = self.payment_query_service.retrieve_payment_map_by_id(payment_id)
        if not payment:
            return

        invoice = self.invoices_query_service.retrieve_invoice_map_by_id(payment[DBPaymentsColumns.INVOICE_ID.value])
        if invoice:
            account = self.account_query_service.retrieve_account_map_by_id(payment[DBPaymentsColumns.CONTO_ID.value])
            client = self.clients_query_service.retrieve_client_map_by_id(invoice[DBInvoicesColumns.ID_CLIENTE.value])
            production = self.productions_query_service.retrieve_production_map_by_id(invoice[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value])

            payment[self.ACCOUNT_FIELD] = account[DBAccountsColumns.NAME.value] if account else "Conto non trovato"
            payment[self.INVOICE_FIELD] = invoice[DBInvoicesColumns.NUMERO_FATTURA.value]
            payment[self.PRODUCTION_FIELD] = production[DBProductionsColumns.NAME.value] if production else "Produzione non trovata"
            payment[DBClientsColumns.NAME.value] = client[DBClientsColumns.NAME.value] if client else "Cliente non trovato"

        self.payment = payment
        self.title_label.configure(text=payment[DBPaymentsColumns.PAYMENT_NAME.value])

        self._create_payment_info_section(payment)
        self.toggle_edit(self.content_frame)

    def _create_payment_info_section(self, payment_data):
        self.entry_fields_payments = {
            DBPaymentsColumns.PAYMENT_DATE.value: {
                "type": Calendar,
                "label": "Data Pagamento",
                "section": "Dati Generali"
            },
            DBPaymentsColumns.PAYMENT_AMOUNT.value: {
                "type": ctk.CTkEntry,
                "label": "Importo Pagato (€)",
                "section": "Dati Fiscali"
            },
            self.INVOICE_FIELD: {
                "type": FilterableComboBox,
                "label": "Fattura Associata",
                "section": "Collegamenti",
                "values": [
                    invoice[DBInvoicesColumns.NUMERO_FATTURA.value]
                    for invoice in self.invoices_query_service.retrieve_invoices_map_list(year=-1, include_unpaid_invoices=True)
                ],
                "command": self._on_invoice_changed
            },
            DBPaymentsColumns.LINKED_RATA.value: {
                "type": ctk.CTkOptionMenu,
                "label": "Rata Associata",
                "section": "Collegamenti"
            },
            self.PRODUCTION_FIELD: {
                "type": ctk.CTkLabel,
                "label": "Produzione Associata",
                "section": "Collegamenti"
            },
            self.ACCOUNT_FIELD: {
                "type": ctk.CTkOptionMenu,
                "label": "Conto",
                "section": "Collegamenti",
                "values": [account[DBAccountsColumns.NAME.value] for account in self.account_query_service.retrieve_accounts_map_list()]
            },
            DBPaymentsColumns.CREATED_AT.value: {
                "type": ctk.CTkLabel,
                "label": "Data Creazione",
                "section": "Note"
            },
            DBPaymentsColumns.UPDATED_AT.value: {
                "type": ctk.CTkLabel,
                "label": "Ultimo Aggiornamento",
                "section": "Note"
            }
        }

        validation_rules = {
            DBPaymentsColumns.PAYMENT_AMOUNT.value: (
                lambda val: re.fullmatch(r"^\d+(\.\d{1,2})?$", val),
                "Formato valido: 1234.56"
            ),
            DBPaymentsColumns.PAYMENT_DATE.value: (
                lambda val: val.strip() != "",
                "Campo obbligatorio"
            )
        }

        warning = self.parent.cards_warnings.get(payment_data[DBPaymentsColumns.PAYMENT_NAME.value])
        border_color = "#2659ab" if warning is None else "#fcba03"

        self.warning_frame = ctk.CTkFrame(self.content_frame, border_width=2, border_color=border_color)
        self.toggle_warning_frame(payment_data[DBPaymentsColumns.PAYMENT_NAME.value])
        ctk.CTkLabel(self.warning_frame, text=warning if warning is not None else "", font=("Arial", 16)).pack(
            padx=30, pady=(20, 20), side="left"
        )
        self.remove_warning_btn = ctk.CTkButton(
            self.warning_frame,
            text="OK, e tutto in ordine",
            command=lambda: self.remove_warning(payment_data[DBPaymentsColumns.PAYMENT_NAME.value])
        )
        self.remove_warning_btn.pack(padx=30, pady=(20, 20), side="right")

        self.info_frame = ctk.CTkFrame(self.content_frame, border_width=2, border_color=border_color)
        self.info_frame.pack(fill="both", expand=True, pady=(5, 10), padx=(5, 25))
        self.info_frame.grid_columnconfigure(0, weight=1, uniform="col")
        self.info_frame.grid_columnconfigure(1, weight=1, uniform="col")

        self.payment_info_widgets = {}
        self.payment_info_labels = {}
        self.error_labels_payments = {}
        sections = {}

        sections_order = ["Dati Generali", "Dati Fiscali", "Collegamenti", "Note"]
        for i, section_name in enumerate(sections_order):
            frame = ctk.CTkFrame(self.info_frame)
            frame.grid(row=i // 2, column=i % 2, sticky="nsew", padx=15, pady=15)
            frame.grid_columnconfigure(1, weight=1)

            sections[section_name] = {"frame": frame, "row": 1}
            ctk.CTkLabel(frame, text=section_name, font=("Arial", 14, "bold")).grid(
                row=0, column=0, columnspan=2, sticky="w", padx=15, pady=5
            )

        for field, config in self.entry_fields_payments.items():
            section = sections[config["section"]]
            frame = section["frame"]
            row = section["row"]

            lbl = ctk.CTkLabel(frame, text=config["label"] + ":")
            lbl.grid(row=row, column=0, sticky="w", padx=(15, 5), pady=(5, 5))
            self.payment_info_labels[field] = lbl

            widget = self._build_widget_for_field(frame, field, config, payment_data)
            widget.grid(row=row, column=1, sticky="ew" if config["type"] != ctk.CTkLabel else "w", padx=(5, 15), pady=(5, 5))
            self.payment_info_widgets[field] = widget

            if field in validation_rules:
                validation_func, error_message = validation_rules[field]
                error_lbl = ctk.CTkLabel(frame, text="", text_color="#e8e5dc")
                error_lbl.grid(row=row + 1, column=1, sticky="w", padx=5, pady=(0, 10))
                self.error_labels_payments[field] = error_lbl

                widget.bind(
                    "<FocusOut>",
                    lambda e, w=widget, vl=validation_func, el=error_lbl, em=error_message: ViewUtils.validate_entry(w, vl, el, em)
                )
                section["row"] += 2
            else:
                section["row"] += 1

        self._populate_linked_fields()

        buttons_frame = ctk.CTkFrame(self.info_frame, fg_color="#2b2b2b")
        buttons_frame.grid(row=2, column=0, columnspan=2, pady=(5, 15), padx=20, sticky="we")

        self.save_payment_btn = ctk.CTkButton(buttons_frame, text="Salva Pagamento", command=self.save_payment_mod)
        self.save_payment_btn.pack(padx=(400, 10), pady=(20, 20), side="left")

        self.delete_btn = ctk.CTkButton(
            buttons_frame,
            text="Elimina Pagamento",
            fg_color="#8B0000",
            hover_color="#A52A2A",
            command=self.delete_payment
        )
        self.delete_btn.pack(padx=10, pady=(20, 20), side="right", anchor="e")

    def _build_widget_for_field(self, frame, field, config, payment_data):
        if config["type"] == ctk.CTkLabel:
            return config["type"](frame, text=str(payment_data.get(field, "")))

        if config["type"] == FilterableComboBox:
            values = config.get("values", [])
            widget = config["type"](
                frame,
                values=values,
                autofill=True,
                command=config.get("command")
            )
            initial_value = str(payment_data.get(field, values[0] if values else ""))
            widget.set_value(initial_value, safe_mode=False)
            return widget

        if config["type"] == ctk.CTkOptionMenu:
            values = config.get("values", [])
            widget = config["type"](frame, values=values)
            if "command" in config:
                widget.configure(command=config["command"])
            initial_value = str(payment_data.get(field, values[0] if values else ""))
            if values:
                widget.set(initial_value)
            return widget

        if config["type"] == Calendar:
            widget = config["type"](frame, date_pattern=ViewUtils.date_pattern)
            value = payment_data.get(field, "")
            widget.selection_set(str(value) if value else datetime.today())
            return widget

        widget = config["type"](frame)
        widget.insert(0, str(payment_data.get(field, "")))
        return widget

    def _on_invoice_changed(self, selected_invoice_name):
        invoice = self.invoices_query_service.retrieve_invoice_map_by_name(selected_invoice_name)
        if not invoice:
            return

        rate_count = int(invoice[DBInvoicesColumns.NUMERO_RATE.value])
        rata_widget = self.payment_info_widgets[DBPaymentsColumns.LINKED_RATA.value]
        if rate_count == 1:
            rata_widget.configure(values=["1"])
            rata_widget.set("1")
        else:
            rata_widget.configure(values=["1", "2", "3"])
            if rata_widget.get() not in {"1", "2", "3"}:
                rata_widget.set("1")

        self._populate_linked_fields()

    def _populate_linked_fields(self):
        invoice_name = self.payment_info_widgets[self.INVOICE_FIELD].get_value()
        invoice = self.invoices_query_service.retrieve_invoice_map_by_name(invoice_name)
        if not invoice:
            return

        production = self.productions_query_service.retrieve_production_map_by_id(invoice[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value])
        self.payment_info_widgets[self.PRODUCTION_FIELD].configure(
            text=production[DBProductionsColumns.NAME.value] if production else "Produzione non trovata"
        )

        current_rata = str(self.payment.get(DBPaymentsColumns.LINKED_RATA.value, "1")) if self.payment else "1"
        rate_count = int(invoice[DBInvoicesColumns.NUMERO_RATE.value])
        rata_widget = self.payment_info_widgets[DBPaymentsColumns.LINKED_RATA.value]
        rata_widget.configure(values=["1"] if rate_count == 1 else ["1", "2", "3"])
        rata_widget.set(current_rata if rate_count == 3 or current_rata == "1" else "1")

    def save_payment_mod(self):
        account_name = self.payment_info_widgets[self.ACCOUNT_FIELD].get()
        account = self.account_query_service.retrieve_account_map_by_name(account_name)
        invoice_name = self.payment_info_widgets[self.INVOICE_FIELD].get_value()
        invoice = self.invoices_query_service.retrieve_invoice_map_by_name(invoice_name)

        if not account or not invoice:
            ViewUtils.show_error_popup(self.content_frame, "ERRORE", "Conto o fattura non validi.")
            return

        payment_data = {
            DBPaymentsColumns.PAYMENT_NAME.value: self.payment[DBPaymentsColumns.PAYMENT_NAME.value],
            DBPaymentsColumns.PAYMENT_AMOUNT.value: self.payment_info_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].get().strip(),
            DBPaymentsColumns.PAYMENT_DATE.value: self.payment_info_widgets[DBPaymentsColumns.PAYMENT_DATE.value].get_date(),
            DBPaymentsColumns.LINKED_RATA.value: self.payment_info_widgets[DBPaymentsColumns.LINKED_RATA.value].get(),
            DBPaymentsColumns.INVOICE_ID.value: invoice[DBInvoicesColumns.ID.value],
            DBPaymentsColumns.CONTO_ID.value: account[DBAccountsColumns.ID.value],
        }

        success, message = self.payment_controller.update_payment(self.current_payment_id, payment_data)
        if not success:
            ViewUtils.show_error_popup(self.content_frame, "ERRORE", message)
            return

        self.update_controller.on_adding_payment()

        ViewUtils.show_confirm_popup_2(self.content_frame, "SALVATAGGIO COMPLETATO", message)
        self.switch_modify.deselect()
        self.toggle_edit(self.content_frame)

        if self.on_payment_changed:
            self.on_payment_changed()

        self.create_detail_tab(self.current_payment_id)

    def delete_payment(self):
        invoice_id = self.payment[DBPaymentsColumns.INVOICE_ID.value] if self.payment else None
        confirmation = ViewUtils.ask_confirmation_popup(
            self.content_frame,
            "Stai per eliminare questo pagamento.\nDesideri continuare ?",
            "ELIMINAZIONE PAGAMENTO"
        )
        if not confirmation:
            return

        success, message = self.payment_controller.delete_payment(self.current_payment_id)
        if not success:
            ViewUtils.show_error_popup(self.content_frame, "ERRORE", message)
            return

        if invoice_id is not None:
            self.update_controller.update_invoices(invoice_id)
            self.update_controller.on_adding_payment()

        ViewUtils.show_confirm_popup_2(self.content_frame, "PAGAMENTO ELIMINATO CON SUCCESSO", message)
        if self.on_payment_changed:
            self.on_payment_changed()
        self._cleanup_and_go_back()

    def toggle_edit(self, parent):
        state = ctk.NORMAL if self.switch_modify.get() else ctk.DISABLED

        self.save_payment_btn.configure(state=state)
        self.delete_btn.configure(state=state)
        self.remove_warning_btn.configure(state=state)

        for widget in parent.winfo_children():
            if isinstance(widget, ctk.CTkEntry):
                widget.configure(state=state, text_color="#636363" if state == ctk.DISABLED else "#c2c2c2")
            elif isinstance(widget, FilterableComboBox):
                widget.state = state
                widget._apply_state()
            elif isinstance(widget, ctk.CTkOptionMenu):
                widget.configure(state=state)
            elif isinstance(widget, Calendar):
                widget.configure(state=state)
            elif isinstance(widget, (ctk.CTkFrame, ctk.CTkScrollableFrame, ctk.CTkToplevel)):
                self.toggle_edit(widget)

    def toggle_warning_frame(self, payment_name):
        warning = self.parent.cards_warnings.get(payment_name)
        if warning is not None:
            self.warning_frame.pack(fill="both", expand=True, pady=10, padx=(5, 25))
        else:
            self.warning_frame.pack_forget()

    def remove_warning(self, payment_name):
        self.parent.cards_warnings.pop(payment_name, None)
        self.info_frame.configure(border_color="#2659ab")
        card = self.parent.payments_card_list.get(payment_name)
        if card is not None:
            ViewUtils.toggle_warning_on_card(card, self.parent.cards_warnings)
        self.toggle_warning_frame(payment_name)
        self.remove_warning_btn.configure(state=ctk.DISABLED)
        self.save_payment_mod()

    def _clear_content(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        self.switch_modify.deselect()

    def _cleanup_and_go_back(self):
        self._clear_content()
        self.pack_forget()
        self.back_callback()

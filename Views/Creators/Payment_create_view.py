import tkinter as tk
import re

import customtkinter as ctk
from tkcalendar import Calendar

from App_context import AppContext
from Controllerss.Payment_controller import PaymentsController
from Gestionale_Enums import DBAccountsColumns, DBClientsColumns, DBInvoicesColumns, DBPaymentsColumns, DBProductionsColumns, Rateizzazione
from QueryServices.Account_query_service import AccountQueryService
from QueryServices.Clients_query_service import ClientQueryService
from QueryServices.Invoices_query_service import InvoiceQueryService
from QueryServices.Payments_query_service import PaymentQueryService
from Views.View_utils import FilterableComboBox, ViewUtils


class PaymentCreateView(ctk.CTkToplevel):
    """
    Finestra modale per la creazione di un nuovo pagamento.

    Replica il workflow storico della view legacy ma lo isola in una creator
    dedicata, in linea con le altre ``*ViewH`` migrate.
    """

    INVOICE_FIELD = "NOME FATTURA"
    ACCOUNT_FIELD = "NOME CONTO"

    def __init__(self, parent, app_context: AppContext, on_payment_created=None, on_close=None):
        super().__init__(parent)

        self.app_context:AppContext = app_context
        self.payment_controller:PaymentsController = app_context.payment_controller
        self.update_controller = app_context.update_controller
        self.account_query_service:AccountQueryService = app_context.account_query_service
        self.clients_query_service:ClientQueryService = app_context.clients_query_service
        self.invoices_query_service:InvoiceQueryService = app_context.invoices_query_service
        self.payment_query_service:PaymentQueryService = app_context.payments_query_service

        self.on_payment_created = on_payment_created
        self.on_close = on_close

        self.entry_fields = {
            self.INVOICE_FIELD: FilterableComboBox,
            DBPaymentsColumns.LINKED_RATA.value: ctk.CTkOptionMenu,
            DBPaymentsColumns.PAYMENT_NAME.value: ctk.CTkEntry,
            DBPaymentsColumns.PAYMENT_AMOUNT.value: ctk.CTkEntry,
            DBPaymentsColumns.PAYMENT_DATE.value: Calendar,
            self.ACCOUNT_FIELD: ctk.CTkOptionMenu,
        }
        self.error_fields = {
            DBPaymentsColumns.PAYMENT_NAME.value: ctk.CTkLabel,
            DBPaymentsColumns.PAYMENT_AMOUNT.value: ctk.CTkLabel,
            DBPaymentsColumns.LINKED_RATA.value: ctk.CTkLabel,
        }

        self.payment_widgets = {}
        self.error_labels = {}
        self.payment_labels = {}

        self.title("Aggiungi Nuovo Pagamento")
        self.geometry("550x700")
        self.lift()
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.scrollable_frame = ctk.CTkScrollableFrame(self)
        self.scrollable_frame.pack(fill="both", expand=True)

        self._build_form()
        self._bind_validations()
        self._initialize_default_values()

    def _build_form(self):
        for i, (label_text, widget_class) in enumerate(self.entry_fields.items()):
            label = ctk.CTkLabel(self.scrollable_frame, text=label_text)
            label.pack(pady=5 if i == 0 else (35, 0))
            self.payment_labels[label_text] = label

            widget = self._create_field_widget(label_text, widget_class)
            widget.pack(pady=5, padx=10, fill="x", expand=True)
            self.payment_widgets[label_text] = widget

            if self.error_fields.get(label_text) is not None:
                error_label = ctk.CTkLabel(self.scrollable_frame, text="")
                error_label.pack(pady=(0, 15))
                self.error_labels[label_text] = error_label

        self.save_button = ctk.CTkButton(
            self.scrollable_frame,
            text="Salva Pagamento",
            command=self.save_payment_data
        )
        self.save_button.pack(pady=(35, 15))

    def _create_field_widget(self, label_text, widget_class):
        if label_text == self.INVOICE_FIELD:
            invoices = list(self._construct_invoices_list_view_friendly().values())[::-1]
            return widget_class(
                parent=self.scrollable_frame,
                placeholder="Cerca",
                autofill=True,
                values=invoices,
                command=self._on_invoice_selected
            )

        if label_text == self.ACCOUNT_FIELD:
            return widget_class(
                self.scrollable_frame,
                values=[item[DBAccountsColumns.NAME.value] for item in self.account_query_service.retrieve_accounts_map_list()]
            )

        if label_text == DBPaymentsColumns.LINKED_RATA.value:
            return widget_class(
                self.scrollable_frame,
                values=["1", "2", "3"],
                command=self.control_linked_rata
            )

        if label_text == DBPaymentsColumns.PAYMENT_DATE.value:
            return widget_class(self.scrollable_frame, date_pattern=ViewUtils.date_pattern)

        return widget_class(self.scrollable_frame)

    def _bind_validations(self):
        self.payment_widgets[DBPaymentsColumns.PAYMENT_NAME.value].bind(
            "<FocusOut>",
            lambda event: ViewUtils.validate_entry(
                self.payment_widgets[DBPaymentsColumns.PAYMENT_NAME.value],
                lambda val: val.strip() != "",
                self.error_labels[DBPaymentsColumns.PAYMENT_NAME.value],
                "Il campo non puo essere vuoto."
            )
        )

        self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].bind(
            "<FocusOut>",
            lambda event: ViewUtils.validate_entry(
                self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value],
                lambda val: re.fullmatch(r"^\d+(\.\d{2})?$", val.strip()) is not None,
                self.error_labels[DBPaymentsColumns.PAYMENT_AMOUNT.value],
                "Inserimento non valido: inserire un numero monetario con due cifre decimali (es. 123.45)"
            )
        )

    def _initialize_default_values(self):
        invoice_values = list(self._construct_invoices_list_view_friendly().values())[::-1]
        if invoice_values:
            self.payment_widgets[self.INVOICE_FIELD].set_value(invoice_values[0], safe_mode=False)
            self._on_invoice_selected(invoice_values[0])

        accounts = self.account_query_service.retrieve_accounts_map_list()
        if accounts:
            self.payment_widgets[self.ACCOUNT_FIELD].set(accounts[0][DBAccountsColumns.NAME.value])

    def _construct_invoices_list_view_friendly(self, year: int = None):
        invoices = {}

        for invoice in self.invoices_query_service.retrieve_invoices_map_list(year=year, include_unpaid_invoices=True):
            client = self.clients_query_service.retrieve_client_map_by_id(invoice[DBInvoicesColumns.ID_CLIENTE.value])
            client_name = client[DBClientsColumns.NAME.value] if client else "Cliente non trovato"
            invoices[invoice[DBInvoicesColumns.ID.value]] = f"{invoice[DBInvoicesColumns.NUMERO_FATTURA.value]} - {client_name}"

        return invoices

    def _extract_invoice_name_from_view_friendly(self, invoice_value):
        parts = invoice_value.split(" - ")
        if len(parts) >= 3:
            return " - ".join(parts[:3])
        return invoice_value.strip()

    def _get_selected_invoice_map(self):
        selected_value = self.payment_widgets[self.INVOICE_FIELD].get_value()
        if not selected_value:
            return None

        invoice_name = self._extract_invoice_name_from_view_friendly(selected_value)
        return self.invoices_query_service.retrieve_invoice_map_by_name(invoice_name)

    def _on_invoice_selected(self, selected_value):
        self.toggle_linked_rata(selected_value)
        self.autofill_payment_amount()
        self.control_linked_rata(self.payment_widgets[DBPaymentsColumns.LINKED_RATA.value].get())

    def toggle_linked_rata(self, selected_value):
        invoice = self._get_selected_invoice_map()
        if not invoice:
            return

        widget = self.payment_widgets[DBPaymentsColumns.LINKED_RATA.value]
        rateizzazione = int(invoice[DBInvoicesColumns.NUMERO_RATE.value])

        if rateizzazione == int(Rateizzazione.UNA.value):
            widget.configure(values=["1"], state=tk.DISABLED)
            widget.set("1")
        else:
            widget.configure(values=["1", "2", "3"], state=tk.NORMAL)
            if widget.get() not in {"1", "2", "3"}:
                widget.set("1")

    def autofill_payment_amount(self):
        invoice = self._get_selected_invoice_map()
        if not invoice:
            return

        invoice_amount = float(invoice[DBInvoicesColumns.NETTO_A_PAGARE.value])
        invoice_rateiz = int(invoice[DBInvoicesColumns.NUMERO_RATE.value])
        widget = self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value]

        widget.delete(0, tk.END)
        if invoice_rateiz == int(Rateizzazione.UNA.value):
            widget.insert(0, f"{invoice_amount:.2f}")
        else:
            widget.insert(0, f"{round(invoice_amount / 3, 2):.2f}")

    def control_linked_rata(self, selected_value):
        invoice = self._get_selected_invoice_map()
        if not invoice:
            return False

        netto_rate_fattura = {"1": 0.0, "2": 0.0, "3": 0.0}
        netto_rate_pagate = {"1": 0.0, "2": 0.0, "3": 0.0}
        rate_saldate = {"1": False, "2": False, "3": False}

        if int(invoice[DBInvoicesColumns.NUMERO_RATE.value]) == int(Rateizzazione.UNA.value):
            netto_rate_fattura["1"] = float(invoice[DBInvoicesColumns.NETTO_A_PAGARE.value])
        else:
            rata = float(invoice[DBInvoicesColumns.NETTO_A_PAGARE.value]) / 3
            netto_rate_fattura = {"1": rata, "2": rata, "3": rata}

        payments = self.payment_query_service.retrieve_payments_map_list_by_invoice_id(invoice[DBInvoicesColumns.ID.value], year=-1)
        for payment in payments:
            rata = str(payment[DBPaymentsColumns.LINKED_RATA.value])
            if rata in netto_rate_pagate:
                netto_rate_pagate[rata] += float(payment[DBPaymentsColumns.PAYMENT_AMOUNT.value])

        for rata in ("1", "2", "3"):
            tot_mancante = netto_rate_fattura[rata] - netto_rate_pagate[rata]
            if netto_rate_pagate[rata] >= netto_rate_fattura[rata] or (5 > tot_mancante > 0):
                rate_saldate[rata] = True

        selected_rata = str(selected_value)
        amount_widget = self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value]

        if rate_saldate.get(selected_rata):
            self.error_labels[DBPaymentsColumns.LINKED_RATA.value].configure(
                text=f"La rata {selected_rata} e gia interamente saldata ({round(netto_rate_pagate[selected_rata], 2)} EUR)",
                text_color="#e39e27"
            )
            amount_widget.delete(0, tk.END)
            amount_widget.insert(0, "0.00")
            amount_widget.configure(border_color="#e39e27")
            return True

        tot_mancante = netto_rate_fattura[selected_rata] - netto_rate_pagate[selected_rata]
        self.error_labels[DBPaymentsColumns.LINKED_RATA.value].configure(text="", text_color="#e39e27")
        amount_widget.configure(border_color="gray")
        amount_widget.delete(0, tk.END)
        amount_widget.insert(0, round(tot_mancante, 2))

        if netto_rate_pagate[selected_rata] > 0 and tot_mancante >= 5:
            self.error_labels[DBPaymentsColumns.LINKED_RATA.value].configure(
                text=f"Totale mancante da saldare della rata {selected_rata}: {round(tot_mancante, 2)} EUR",
                text_color="#e39e27"
            )

        return False

    def _collect_payment_data(self):
        payment_data = {}

        for label_text, widget in self.payment_widgets.items():
            if isinstance(widget, (ctk.CTkEntry, ctk.CTkOptionMenu)):
                payment_data[label_text] = widget.get().strip()
            elif isinstance(widget, Calendar):
                payment_data[label_text] = widget.get_date()
            elif isinstance(widget, FilterableComboBox):
                payment_data[label_text] = widget.get_value()

        return payment_data

    def save_payment_data(self):
        payment_data = self._collect_payment_data()
        invoice = self._get_selected_invoice_map()
        if not invoice:
            ViewUtils.show_error_popup(self, "ERRORE", "Fattura associata non valida.")
            return

        payment_data[DBPaymentsColumns.INVOICE_ID.value] = invoice[DBInvoicesColumns.ID.value]
        rata_gia_salda = self.control_linked_rata(payment_data[DBPaymentsColumns.LINKED_RATA.value])
        confirmation = True

        if rata_gia_salda:
            confirmation = ViewUtils.ask_confirmation_popup(
                self,
                "La rata selezionata presenta gia un pagamento associato\nsei sicuro di voler continuare?",
                "CONFERMA OPERAZIONE"
            )

        if not confirmation:
            return

        success, message = self.payment_controller.save_payment(payment_data)
        if not success:
            ViewUtils.show_error_popup(self, "ERRORE", message)
            return

        #self.update_controller.update_invoices(invoice[DBInvoicesColumns.ID.value])
        #self.update_controller.on_adding_payment()

        payment_map = self.payment_query_service.retrieve_last_payment_insert_map()
        payment_id = payment_map[DBPaymentsColumns.ID.value] if payment_map else None

        if self.on_payment_created:
            self.on_payment_created(payment_id, payment_map)

        self._on_close()

    def _on_close(self):
        try:
            self.grab_release()
        except Exception:
            pass

        if self.on_close:
            self.on_close()

        self.destroy()

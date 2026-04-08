import re
import tkinter as tk
from datetime import datetime

import customtkinter as ctk
from tkcalendar import Calendar

from App_context import AppContext
from Model import DBAccountsColumns, DBClientsColumns, DBInvoicesColumns, DBProductionsColumns, DBUsersColumns
from Views.View_utils import FilterableComboBox, ViewUtils
from Gestionale_Enums import*

from QueryServices.Clients_query_service import ClientQueryService
from QueryServices.Invoices_query_service import InvoiceQueryService
from QueryServices.Productions_query_service import ProductionQueryService

from Analyzers.Invoice_analyzer_service import InvoiceAnalyzerService

from Controllerss.Invoice_controller import InvoiceController

from Controllers import AccountController
from Controllerss.User_controller import UserController


class InvoiceCreateView(ctk.CTkToplevel):
    def __init__(self, parent, app_context: AppContext, on_invoice_created=None, on_close=None):
        super().__init__(parent)
        self.app_context = app_context
        self.invoice_controller: InvoiceController = app_context.invoice_controller
        self.user_controller: UserController = app_context.user_controller
        self.clients_query_service: ClientQueryService = app_context.clients_query_service
        self.productions_query_service: ProductionQueryService = app_context.productions_query_service
        self.invoices_query_service: InvoiceQueryService = app_context.invoices_query_service
        self.invoices_analyzer_service: InvoiceAnalyzerService = app_context.invoices_analyzer_service
        self.account_controller: AccountController = app_context.account_controller
        self.fiscal_settings = app_context.fiscal_settings
        self.on_invoice_created = on_invoice_created
        self.on_close = on_close

        self.nome_utente_string = "NOME UTENTE"
        self.nome_cliente_string = "NOME CLIENTE"
        self.nome_produzione_string = "NOME PRODUZIONE"
        self.nome_conto_string = "CONTO"

        self.invoices_list_of_user = self.invoices_query_service.retrieve_invoices_map_list_by_user(1, True)
        self.productions_list_of_client = {}
        clients = self.clients_query_service.retrieve_clients_map_list()
        if clients:
            self.populate_production_list_by_selected_client(clients[0][DBClientsColumns.NAME.value])

        self.entry_fields = {
            self.nome_utente_string: ctk.CTkOptionMenu,
            self.nome_cliente_string: FilterableComboBox,
            self.nome_produzione_string: ctk.CTkOptionMenu,
            DBInvoicesColumns.NUMERO_FATTURA.value: ctk.CTkEntry,
            DBInvoicesColumns.DATA_CREAZIONE.value: Calendar,
            DBInvoicesColumns.SERVIZI.value: ctk.CTkEntry,
            DBInvoicesColumns.RIMBORSI.value: ctk.CTkEntry,
            DBInvoicesColumns.RIVALSA_INPS.value: ctk.CTkEntry,
            DBInvoicesColumns.METODO_PAGAMENTO.value: ctk.CTkOptionMenu,
            DBInvoicesColumns.NUMERO_RATE.value: ctk.CTkOptionMenu,
            DBInvoicesColumns.TIPO.value: ctk.CTkOptionMenu,
            DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value: ctk.CTkOptionMenu,
            self.nome_conto_string: ctk.CTkOptionMenu,
            DBInvoicesColumns.NOTE.value: ctk.CTkTextbox,
        }
        self.error_fields = {
            self.nome_produzione_string: ctk.CTkLabel,
            DBInvoicesColumns.NUMERO_FATTURA.value: ctk.CTkLabel,
            DBInvoicesColumns.RIMBORSI.value: ctk.CTkLabel,
            DBInvoicesColumns.SERVIZI.value: ctk.CTkLabel,
            DBInvoicesColumns.RIVALSA_INPS.value: ctk.CTkLabel,
        }
        self.invoice_widgets = {}
        self.error_labels = {}
        self.invoice_labels = {}
        self.suggest_invoicer_window = None

        self.title("Aggiungi Nuova Fattura")
        self.geometry("550x700")
        self.lift()
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.invoice_window_scrollableFrame = ctk.CTkScrollableFrame(self)
        self.invoice_window_scrollableFrame.pack(fill="both", expand=True)
        self._build_form()

    def _build_form(self):
        for i, (label_text, widget_class) in enumerate(self.entry_fields.items()):
            label = ctk.CTkLabel(self.invoice_window_scrollableFrame, text=label_text)
            if label_text != DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value:
                label.pack(pady=5 if i == 0 else (35, 0))
            self.invoice_labels[label_text] = label

            if label_text == self.nome_utente_string:
                self.user_selection_frame = ctk.CTkFrame(self.invoice_window_scrollableFrame, fg_color="transparent")
                self.user_selection_frame.pack(pady=5, padx=10, fill="x", expand=True)

            widget = self._create_widget(label_text, widget_class)
            if label_text == self.nome_utente_string:
                widget.pack(side="left", fill="x", expand=True)

                self.suggest_user_button = ctk.CTkButton(
                    self.user_selection_frame,
                    text="Suggerisci partita iva",
                    command=self.open_suggest_user_window,
                )
                self.suggest_user_button.pack(side="left", padx=(10, 0))
            elif label_text != DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value:
                widget.pack(pady=5, padx=10, fill="x", expand=True)
            self.invoice_widgets[label_text] = widget

            if self.error_fields.get(label_text) is not None:
                error_label = ctk.CTkLabel(self.invoice_window_scrollableFrame, text="")
                error_label.pack(pady=(0, 15))
                self.error_labels[label_text] = error_label

        self.auto_compile_invoice_name(self.invoice_widgets[self.nome_utente_string].get())
        selected_client_name = self.invoice_widgets[self.nome_cliente_string].get_value()
        client_list = self.clients_query_service.retrieve_clients_map_list()
        matched_client = next((c for c in client_list if c[DBClientsColumns.NAME.value] == selected_client_name), None)
        if matched_client:
            self.update_productions_list(matched_client[DBClientsColumns.NAME.value])
        elif client_list:
            self.update_productions_list(client_list[0][DBClientsColumns.NAME.value])

        self.prod_already_invoiced_control(self.invoice_widgets[self.nome_produzione_string].get())
        self.selected_user = self.invoice_widgets[self.nome_utente_string].get()
        if self.get_regime_fiscale_from_view(self.selected_user) == self.user_controller.RegimeFiscale.ORDINARIO.value:
            self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].configure(
                state=ctk.DISABLED,
                border_color=ViewUtils.disabled_label_color,
                text_color=ViewUtils.disabled_label_color,
            )
            self.invoice_labels[DBInvoicesColumns.RIVALSA_INPS.value].configure(text_color=ViewUtils.disabled_label_color)

        if len(self.invoices_list_of_user) == 0:
            self.invoice_widgets[DBInvoicesColumns.TIPO.value].configure(state=ctk.DISABLED)
            self.invoice_widgets[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].configure(state=ctk.DISABLED)
            self.invoice_labels[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].configure(text_color=ViewUtils.disabled_label_color)

        self.save_button = ctk.CTkButton(self.invoice_window_scrollableFrame, text="Salva Fattura", command=self.save_invoice_data)
        self.save_button.pack(pady=(35, 15))
        self._bind_validations()

    def _create_widget(self, label_text, widget_class):
        if label_text == self.nome_utente_string:
            return widget_class(
                self.user_selection_frame,
                values=[f"{u[DBUsersColumns.FIRST_NAME.value]} {u[DBUsersColumns.LAST_NAME.value]}" for u in self.user_controller.retrieve_users_map_list()],
                command=lambda selected_value: self.update_entries_on_regime_fiscale(selected_value),
            )
        if label_text == self.nome_cliente_string:
            return widget_class(
                parent=self.invoice_window_scrollableFrame,
                placeholder="Cerca",
                autofill=True,
                values=[c[DBClientsColumns.NAME.value] for c in self.clients_query_service.retrieve_clients_map_list()],
                command=lambda selected_value: self.update_productions_list(selected_value),
            )
        if label_text == self.nome_produzione_string:
            return widget_class(
                self.invoice_window_scrollableFrame,
                values=[p[DBProductionsColumns.NAME.value] for p in self.productions_query_service.retrieve_productions_map_list(include_prod_with_unpaid_invoices=True)],
                command=lambda selected_value: self.prod_already_invoiced_control(selected_value),
            )
        if label_text == DBInvoicesColumns.NUMERO_FATTURA.value:
            self.name_frame = ctk.CTkFrame(self.invoice_window_scrollableFrame)
            self.name_frame.pack(pady=0, padx=0, fill="x", expand=True)
            self.last_part_name_label = ctk.CTkLabel(self.name_frame, text=f"{datetime.today().date().year}")
            self.last_part_name_label.pack(side=tk.RIGHT, pady=5, padx=(0, 40))
            return widget_class(self.name_frame)
        if label_text == DBInvoicesColumns.DATA_CREAZIONE.value:
            return widget_class(self.invoice_window_scrollableFrame, date_pattern=ViewUtils.date_pattern)
        if label_text == DBInvoicesColumns.METODO_PAGAMENTO.value:
            return widget_class(self.invoice_window_scrollableFrame, values=[item.value for item in PaymentsMethods])
        if label_text == DBInvoicesColumns.NUMERO_RATE.value:
            return widget_class(self.invoice_window_scrollableFrame, values=[item.value for item in Rateizzazione])
        if label_text == DBInvoicesColumns.TIPO.value:
            widget = widget_class(
                self.invoice_window_scrollableFrame,
                values=[item.value for item in TipologiaFattura],
                command=lambda selected_value, user_name=self.invoice_widgets[self.nome_utente_string].get(): self.toggle_id_fattura_associata(user_name, selected_value),
            )
            widget.set(TipologiaFattura.FATTURA.value)
            return widget
        if label_text == DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value:
            return widget_class(
                self.invoice_window_scrollableFrame,
                values=[item[DBInvoicesColumns.NUMERO_FATTURA.value] for item in self.invoices_list_of_user],
                command=lambda selected_value: self.auto_set_importi_for_nota_di_credito(selected_value),
            )
        if label_text == self.nome_conto_string:
            return widget_class(
                self.invoice_window_scrollableFrame,
                values=[a[DBAccountsColumns.NAME.value] for a in self.account_controller.retrieve_accounts_map_list()],
            )
        return widget_class(self.invoice_window_scrollableFrame)

    def _bind_validations(self):
        self.invoice_widgets[DBInvoicesColumns.NUMERO_FATTURA.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.invoice_widgets[DBInvoicesColumns.NUMERO_FATTURA.value], lambda val: val.strip() != "",
            self.error_labels[DBInvoicesColumns.NUMERO_FATTURA.value], "Il campo non puo essere vuoto."))
        self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.invoice_widgets[DBInvoicesColumns.SERVIZI.value], lambda val: re.fullmatch(r"^\d+(\.\d{2})?$", val.strip()) is not None,
            self.error_labels[DBInvoicesColumns.SERVIZI.value], "Inserimento non valido: inserire un numero monetario con due cifre decimali (es. 123.45)"))
        self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].bind("<KeyRelease>", lambda event: self.populate_rivalsa_INPS(), add="+")
        self.invoice_widgets[DBInvoicesColumns.RIMBORSI.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.invoice_widgets[DBInvoicesColumns.RIMBORSI.value], lambda val: re.fullmatch(r"^\d+(\.\d{2})?$", val.strip()) is not None,
            self.error_labels[DBInvoicesColumns.RIMBORSI.value], "Inserimento non valido: inserire un numero monetario con due cifre decimali (es. 123.45)"))
        self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value], lambda val: re.fullmatch(r"^\d+(\.\d{2})?$", val.strip()) is not None,
            self.error_labels[DBInvoicesColumns.RIVALSA_INPS.value], "Inserimento non valido: inserire un numero monetario con due cifre decimali (es. 123.45)"))
        self.invoice_widgets[DBInvoicesColumns.DATA_CREAZIONE.value].bind("<<CalendarSelected>>", self.on_calendar_date_selected)

    def save_invoice_data(self):
        invoice_data = {}
        for label_text, widget in self.invoice_widgets.items():
            if isinstance(widget, (ctk.CTkEntry, ctk.CTkOptionMenu)):
                invoice_data[label_text] = widget.get().strip() if isinstance(widget.get(), str) else widget.get()
            elif isinstance(widget, Calendar):
                invoice_data[label_text] = widget.get_date()
            elif isinstance(widget, ctk.CTkTextbox):
                invoice_data[label_text] = widget.get("1.0", "end-1c").strip()
            elif isinstance(widget, FilterableComboBox):
                invoice_data[label_text] = widget.get_value()

        invoice_data[DBInvoicesColumns.NUMERO_FATTURA.value] += " - " + str(datetime.today().date().year)
        if invoice_data[DBInvoicesColumns.TIPO.value] == TipologiaFattura.FATTURA.value:
            invoice_data.pop(DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value)

        success, message = self.invoice_controller.save_invoice(invoice_data)
        if not success:
            ViewUtils.show_error_popup(self, "ERRORE", message)
            return

        invoice_map = self.invoices_query_service.retrieve_last_invoice_insert_map()
        if self.on_invoice_created:
            self.on_invoice_created(invoice_map[DBInvoicesColumns.ID.value], invoice_map)
        self.clear_class_variable()
        self._on_close()

    def update_entries_on_regime_fiscale(self, selected_value=None):
        if selected_value == self.selected_user:
            return
        self.selected_user = self.invoice_widgets[self.nome_utente_string].get()
        self.populate_invoice_list_by_selected_user(selected_value)
        regime_fiscale = self.get_regime_fiscale_from_view(selected_value)

        if regime_fiscale == self.user_controller.RegimeFiscale.ORDINARIO.value:
            self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].delete(0, tk.END)
            self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].insert(0, "0")
            self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].configure(
                state=ctk.DISABLED, border_color=ViewUtils.disabled_label_color, text_color=ViewUtils.disabled_label_color
            )
            self.invoice_labels[DBInvoicesColumns.RIVALSA_INPS.value].configure(text_color=ViewUtils.disabled_label_color)
        elif regime_fiscale == self.user_controller.RegimeFiscale.FORFETTARIO.value:
            self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].delete(0, tk.END)
            self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].configure(state=ctk.NORMAL)
            self.invoice_labels[DBInvoicesColumns.RIVALSA_INPS.value].configure(text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"])
            self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].configure(text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"])
            self.populate_rivalsa_INPS()

        if len(self.invoices_list_of_user) == 0:
            self.invoice_widgets[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].pack_forget()
            self.invoice_labels[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].pack_forget()
            self.invoice_widgets[DBInvoicesColumns.TIPO.value].configure(state=ctk.DISABLED)
            self.invoice_widgets[DBInvoicesColumns.TIPO.value].set(TipologiaFattura.FATTURA.value)
        else:
            self.invoice_widgets[DBInvoicesColumns.TIPO.value].configure(state=ctk.ACTIVE)
            self.invoice_widgets[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].configure(state=ctk.ACTIVE)
            self.invoice_labels[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].configure(text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"])
            self.invoice_widgets[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].set(self.invoices_list_of_user[0][DBInvoicesColumns.NUMERO_FATTURA.value])

        self.invoice_widgets[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].configure(
            require_redraw=ctk.TRUE,
            values=[item[DBInvoicesColumns.NUMERO_FATTURA.value] for item in self.invoices_list_of_user],
        )
        self.auto_compile_invoice_name(selected_value)

    def update_productions_list(self, selected_value=None):
        self.populate_production_list_by_selected_client(selected_value)
        self.invoice_widgets[self.nome_produzione_string].configure(
            values=[item[DBProductionsColumns.NAME.value] for item in self.productions_list_of_client]
        )
        if len(self.productions_list_of_client) > 0:
            self.invoice_widgets[self.nome_produzione_string].set(self.productions_list_of_client[0][DBProductionsColumns.NAME.value])
            self.prod_already_invoiced_control(self.invoice_widgets[self.nome_produzione_string].get())
        else:
            self.invoice_widgets[self.nome_produzione_string].set(" - ")
            self.error_labels[self.nome_produzione_string].configure(
                text="IL CLIENTE SELEZIONATO NON HA ANCORA NESSUNA PRODUZIONE ASSOOCIATA",
                text_color="#d62929",
            )

    def populate_invoice_list_by_selected_user(self, user_full_name):
        self.invoices_list_of_user.clear()
        user_name = user_full_name.split(" ")
        if len(user_name) < 2:
            return
        user_id = self.user_controller.retrieve_user_by_fullname(user_name[0], user_name[1])[0]
        self.invoices_list_of_user = self.invoices_query_service.retrieve_invoices_map_list_by_user(user_id, True)

    def populate_production_list_by_selected_client(self, client_name):
        self.productions_list_of_client.clear()
        client = self.clients_query_service.retrieve_client_map_by_name(client_name)
        if not client:
            return
        client_id = client[DBClientsColumns.ID.value]
        self.productions_list_of_client = self.productions_query_service.retrieve_productions_map_list_by_client_id(
            client_id=client_id, include_prod_with_unpaid_invoices=True
        )

    def get_regime_fiscale_from_view(self, user_full_name):
        user_name = user_full_name.split(" ")
        if len(user_name) >= 2:
            return self.user_controller.get_regime_fiscale_by_full_name(user_name[0], user_name[1])
        return None

    def populate_rivalsa_INPS(self):
        importo_servizi = self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].get().strip()
        aliquota_rivalsa_inps = float(self.fiscal_settings.partita_iva_forfettaria.aliquota_rivalsa_inps)
        if importo_servizi == "":
            return
        try:
            rivalsa = float(importo_servizi) * aliquota_rivalsa_inps
        except ValueError:
            return
        self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].delete(0, tk.END)
        self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].insert(0, format(rivalsa, ".2f"))

    def toggle_id_fattura_associata(self, user_name, selected_value=None):
        if selected_value == TipologiaFattura.FATTURA.value:
            self.invoice_widgets[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].pack_forget()
            self.invoice_labels[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].pack_forget()
            self.invoice_widgets[DBInvoicesColumns.NUMERO_FATTURA.value].delete(0, tk.END)
            self.auto_compile_invoice_name(user_name)
            self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].delete(0, tk.END)
            self.invoice_widgets[DBInvoicesColumns.RIMBORSI.value].delete(0, tk.END)
            self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].delete(0, tk.END)
        elif selected_value == TipologiaFattura.NOTA_DI_CREDITO.value:
            self.invoice_widgets[DBInvoicesColumns.NOTE.value].pack_forget()
            self.invoice_labels[DBInvoicesColumns.NOTE.value].pack_forget()
            self.save_button.pack_forget()
            self.suggest_user_button.pack_forget()
            self.invoice_labels[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].pack(pady=(35, 15))
            self.invoice_widgets[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].pack(pady=5, padx=10, fill="x", expand=True)
            self.invoice_labels[DBInvoicesColumns.NOTE.value].pack(pady=(35, 0))
            self.invoice_widgets[DBInvoicesColumns.NOTE.value].pack(pady=5, padx=10, fill="x", expand=True)
            self.save_button.pack(pady=(35, 15))
            self.suggest_user_button.pack(pady=(0, 20))
            self.auto_set_importi_for_nota_di_credito(self.invoice_widgets[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].get())

    def on_calendar_date_selected(self, event):
        try:
            selected_date = event.widget.selection_get()
            if selected_date:
                self.toggle_year_label_in_numero_fattura(str(selected_date.year))
                self.auto_compile_invoice_name()
        except Exception as e:
            print(f"Errore durante l'aggiornamento dell'anno: {e}")

    def toggle_year_label_in_numero_fattura(self, year):
        self.last_part_name_label.configure(text=year)

    def auto_set_importi_for_nota_di_credito(self, selected_value=None):
        invoice = self.invoices_query_service.retrieve_invoice_map_by_name(selected_value)
        if not invoice:
            return
        nome_fattura_array = invoice[DBInvoicesColumns.NUMERO_FATTURA.value].split(" - ")
        self.invoice_widgets[DBInvoicesColumns.NUMERO_FATTURA.value].delete(0, tk.END)
        self.invoice_widgets[DBInvoicesColumns.NUMERO_FATTURA.value].insert(0, nome_fattura_array[0] + " - " + nome_fattura_array[1] + " - NDC")
        self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].delete(0, tk.END)
        self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].insert(0, invoice[DBInvoicesColumns.SERVIZI.value])
        self.invoice_widgets[DBInvoicesColumns.RIMBORSI.value].delete(0, tk.END)
        self.invoice_widgets[DBInvoicesColumns.RIMBORSI.value].insert(0, invoice[DBInvoicesColumns.RIMBORSI.value])
        self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].delete(0, tk.END)
        if invoice[DBInvoicesColumns.RIVALSA_INPS.value]:
            self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].insert(0, invoice[DBInvoicesColumns.RIVALSA_INPS.value])
        client = self.clients_query_service.retrieve_client_map_by_id(invoice[DBInvoicesColumns.ID_CLIENTE.value])
        production = self.productions_query_service.retrieve_production_map_by_id(invoice[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value])
        self.invoice_widgets[self.nome_cliente_string].set_value(client[DBClientsColumns.NAME.value])
        self.invoice_widgets[self.nome_produzione_string].set(production[DBProductionsColumns.NAME.value])
        self.invoice_widgets[DBInvoicesColumns.METODO_PAGAMENTO.value].set(invoice[DBInvoicesColumns.METODO_PAGAMENTO.value])
        self.invoice_widgets[DBInvoicesColumns.NUMERO_RATE.value].set(invoice[DBInvoicesColumns.NUMERO_RATE.value])

    def auto_compile_invoice_name(self, user_name=None):
        user_full_name = user_name.split(" ") if user_name else self.invoice_widgets.get(self.nome_utente_string).get().split(" ")
        user_id = self.user_controller.retrieve_user_map_by_fullname(user_full_name[0], user_full_name[1]).get(DBUsersColumns.ID.value)
        user_invoices = self.invoices_query_service.retrieve_invoices_map_list_by_user(user_id, year=-1)
        selected_year = datetime.strptime(self.invoice_widgets.get(DBInvoicesColumns.DATA_CREAZIONE.value).get_date(), "%Y-%m-%d").year
        user_invoice_numbers = {"": []}
        for invoice in user_invoices:
            parts = invoice[DBInvoicesColumns.NUMERO_FATTURA.value].split(" - ")
            invoice_number = parts[1].split("FPR")[1]
            invoice_year = int(parts[2])
            user_invoice_numbers.setdefault(str(invoice_year), []).append(int(invoice_number))
        selected_list = user_invoice_numbers.get(str(selected_year))
        last_invoice_number = max(selected_list) + 1 if selected_list else 1
        last_invoice_number_str = str(last_invoice_number).zfill(2)
        self.invoice_widgets[DBInvoicesColumns.NUMERO_FATTURA.value].delete(0, tk.END)
        if self.invoice_widgets[DBInvoicesColumns.TIPO.value].get() == TipologiaFattura.FATTURA.value:
            self.invoice_widgets[DBInvoicesColumns.NUMERO_FATTURA.value].insert(0, f"{user_full_name[1]} - FPR" + last_invoice_number_str)
        else:
            nome_fattura_array = self.invoice_widgets[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].get().split(" - ")
            self.invoice_widgets[DBInvoicesColumns.NUMERO_FATTURA.value].insert(0, nome_fattura_array[0] + " - " + nome_fattura_array[1] + " - NDC")

    def select_correct_invoice(self, invoice):
        self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].delete(0, tk.END)
        self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].insert(0, invoice[DBInvoicesColumns.SERVIZI.value])
        self.invoice_widgets[DBInvoicesColumns.RIMBORSI.value].delete(0, tk.END)
        self.invoice_widgets[DBInvoicesColumns.RIMBORSI.value].insert(0, invoice[DBInvoicesColumns.RIMBORSI.value])
        self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].delete(0, tk.END)
        if invoice[DBInvoicesColumns.RIVALSA_INPS.value]:
            self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].insert(0, invoice[DBInvoicesColumns.RIVALSA_INPS.value])

    def prod_already_invoiced_control(self, selected_value):
        production = self.productions_query_service.retrieve_production_map_by_name(selected_value)
        if not production:
            return
        fatture_associate = self.invoices_query_service.retrieve_invoice_map_list_by_production(production.get(DBProductionsColumns.ID.value))
        if len(fatture_associate) > 0:
            nomi_str = ", ".join(f[DBInvoicesColumns.NUMERO_FATTURA.value] for f in fatture_associate)
            self.error_labels[self.nome_produzione_string].configure(text=f"Questa produzione ha gia una o piu fatture associate: \n ({nomi_str})", text_color="#e39e27")
        else:
            self.error_labels[self.nome_produzione_string].configure(text="")

    def clear_class_variable(self):
        self.invoice_widgets.clear()
        self.invoice_labels.clear()

    def open_suggest_user_window(self):
        self.suggest_invoicer_window = ctk.CTkToplevel(self)
        self.suggest_invoicer_window.title("Suggeritore di fatturatore")
        self.suggest_invoicer_window.lift()
        self.suggest_invoicer_window.grab_set()
        self.suggest_invoicer_window_Frame = ctk.CTkFrame(self.suggest_invoicer_window)
        self.suggest_invoicer_window_Frame.pack(fill="x", expand=True)
        info_label = ctk.CTkLabel(self.suggest_invoicer_window_Frame, text="    i", font=("Arial", 16), bg_color="#4287f5")
        info_label.pack(padx=10, pady=10, anchor="w")
        ViewUtils.add_tooltip(info_label, "Questa funzionalita prevede che esista una singola partita iva ordinaria tra tante forfettarie.\nL'ordinaria e incaricata di dedurre le spese deducibili.\nIl suggeritore cerca di far fatturare l'ordinaria fino al raggiungimento delle spese deducibili effettuate finora,\nSe le spese deducibili sono gia coperte allora viene prediletta la forfettaria con minor fatturato.")
        self.new_invoice_import_label = ctk.CTkLabel(self.suggest_invoicer_window_Frame, text="IMPORTO DA FATTURARE")
        self.new_invoice_import_label.pack(padx=10, pady=(20, 5), fill="x")
        self.new_invoice_import_entry = ctk.CTkEntry(self.suggest_invoicer_window_Frame, width=520)
        self.new_invoice_import_entry.pack(padx=10, pady=(0, 5), fill="x")
        self.new_invoice_import_error = ctk.CTkLabel(self.suggest_invoicer_window_Frame, text="", text_color="red")
        self.new_invoice_import_error.pack(padx=10, pady=(0, 15), fill="x")
        self.show_suggestion_button = ctk.CTkButton(self.suggest_invoicer_window_Frame, text="SUGGERISCI", command=self.get_invoicer_suggestion)
        self.show_suggestion_button.pack(padx=10, pady=(20, 25))
        self.ranking_header_frame = ctk.CTkFrame(self.suggest_invoicer_window, fg_color="#2b2b2b")
        self.ranking_header_frame.pack(fill="x", expand=True, padx=10, pady=(25, 0))
        for idx, title in enumerate(("UTENTE", "PUNTEGGIO")):
            header = ctk.CTkFrame(self.ranking_header_frame, fg_color="#333333")
            header.grid(row=0, column=idx, sticky="nsew", padx=(5, 5) if idx == 0 else (0, 5), pady=5)
            self.ranking_header_frame.grid_columnconfigure(idx, weight=1, uniform="col")
            ctk.CTkLabel(header, text=title, font=("Arial", 12)).pack(fill="x", expand=True, padx=5, pady=15)
        self.invoicers_ranking_frame = ctk.CTkScrollableFrame(self.suggest_invoicer_window, height=100)
        self.invoicers_ranking_frame.pack(fill="both", expand=True, padx=10, pady=(0, 25))
        self.new_invoice_import_entry.bind("<KeyRelease>", lambda event: ViewUtils.validate_entry(
            self.new_invoice_import_entry, lambda val: len(val.strip()) >= 3 and re.fullmatch(r"^\d+(\.\d{2})?$", val.strip()) is not None,
            self.new_invoice_import_error, "Inserimento non valido: inserire un numero monetario con due cifre decimali (es. 123.45)"))

    def get_invoicer_suggestion(self):
        try:
            new_import = float(self.new_invoice_import_entry.get())
        except Exception:
            ViewUtils.show_error_popup(self.suggest_invoicer_window, "Errore", "Inserimento non valido")
            return
        try:
            users_rank = self.invoices_analyzer_service.select_best_invoicer(new_import)
            for widget in self.invoicers_ranking_frame.winfo_children():
                widget.destroy()
            for user_name, score in users_rank.items():
                user_card = ctk.CTkFrame(self.invoicers_ranking_frame)
                user_card.pack(padx=10, pady=5, fill="x", expand=True)
                name_frame = ctk.CTkFrame(user_card, fg_color="transparent")
                name_frame.pack(side="left", fill="x", expand=True, padx=5, pady=5)
                ctk.CTkButton(
                    name_frame,
                    text=f"{user_name}",
                    anchor="w",
                    fg_color="transparent",
                    hover_color="#3c60b5",
                    command=lambda selected_user=user_name, importo_servizi=new_import: self.select_suggested_invoicer(selected_user, str(importo_servizi)),
                ).pack(fill="x", expand=True, padx=10, pady=5)
                score_frame = ctk.CTkFrame(user_card, fg_color="transparent")
                score_frame.pack(side="right", fill="x", expand=True, padx=5, pady=5)
                ctk.CTkLabel(score_frame, text=f"{score}", anchor="e").pack(fill="x", expand=True, padx=10, pady=5)
            if self.invoicers_ranking_frame.winfo_children():
                self.invoicers_ranking_frame.winfo_children()[0].configure(border_width=2, border_color="#3c60b5")
        except ValueError as ve:
            ViewUtils.show_error_popup(self.suggest_invoicer_window, "Errore", f"Predizione non possibile: {str(ve)}")

    def select_suggested_invoicer(self, user_full_name, importo_servizi):
        self.invoice_widgets[self.nome_utente_string].set(user_full_name)
        self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].delete(0, ctk.END)
        self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].insert(0, importo_servizi)
        self.populate_rivalsa_INPS()
        self.update_entries_on_regime_fiscale(user_full_name)

        if self.suggest_invoicer_window is not None and self.suggest_invoicer_window.winfo_exists():
            try:
                self.suggest_invoicer_window.grab_release()
            except Exception:
                pass
            self.suggest_invoicer_window.destroy()
            self.suggest_invoicer_window = None

        if self.winfo_exists():
            self.grab_set()

    def _on_close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        if self.on_close:
            self.on_close()
        self.destroy()

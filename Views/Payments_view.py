import customtkinter as ctk
import tkinter as tk
from tkcalendar import Calendar
from Views.View_utils import ViewUtils
from Controllers import PaymentsController, InvoiceController, UserController, ControllerUtils
from Model import DBInvoicesColumns, DBUsersColumns, DBClientsColumns, DBPaymentsColumns, DBProductionsColumns, DBAccountsColumns
from datetime import datetime
import re
from enum import Enum

class PaymentsView(ctk.CTk):

    def __init__(self, db_model, payment_controller, invoice_controller, user_controller, client_controller, production_controller, account_controller, update_controller, tab):
        super().__init__()

        self.db_model = db_model
        self.invoice_controller = invoice_controller
        self.user_controller = user_controller
        self.client_controller = client_controller
        self.payment_controller = payment_controller
        self.production_controller = production_controller
        self.account_controller = account_controller
        self.update_controller = update_controller
        self.tab = tab

        self.global_infos = {}
        self.amount_aggregate_labels = {}

        self.VF_invoice_list = {}
        self.construct_invoices_list_view_friendly()

        self.payment_card_list = {}
        self.payment_card_labels_status = {}

    def create_payments_tab(self):
        self.global_info_frame = ctk.CTkFrame(self.tab)
        self.global_info_frame.pack(pady=(5, 10), fill="x", anchor="n")

        self.populate_global_infos()

        for (key, info) in self.global_infos.items():
            card = ctk.CTkFrame(self.global_info_frame)

            if key == PaymentsController.PaymentsAggregateData.NUMERO_PAGAMENTI.value:
                global_info_unità_di_misura = ""
            elif key == PaymentsController.PaymentsAggregateData.TOT_PAGAMENTI.value:
                global_info_unità_di_misura = "€"

            title = ctk.CTkLabel(card, text=f"{key}", font=("Arial", 12), bg_color="#1F6AA5")
            amount = ctk.CTkLabel(card, text=f"{info} {global_info_unità_di_misura}", font=("Arial", 16))

            card.pack(side="left", anchor="w", padx=10, pady=(10, 5))
            title.pack(anchor="n", padx=10, pady=(10, 5), ipadx=7, ipady=5)
            amount.pack(anchor="s", padx=10, pady=5)

            #salvo i dati che potrebbero avere bisogno di configure successivamente
            self.amount_aggregate_labels[f"{key}"] = amount

        self.payments_table_frame = ctk.CTkFrame(self.tab)
        self.payments_table_frame.pack(pady=(20, 0), padx=(10, 15), fill="x", anchor="n")

        self.table_headers = ["NOME", "CLIENTE", "PRODUZIONE", "TOTALE", "DATA", "RATA", "CONTO\nCORRENTE"]

        for i, header in enumerate(self.table_headers):
            column = ctk.CTkFrame(self.payments_table_frame)
            label = ctk.CTkLabel(column, text=f"{header}", font=("Arial", 14), width=250)
            column.pack(padx=(0, 5), pady=5, fill="y", expand=True, side="left")
            label.pack(padx=5, pady=15, anchor="n")

        # Creazione del frame delle cards
        self.payments_cards_frame = ctk.CTkScrollableFrame(self.tab)
        self.payments_cards_frame.pack(padx=0, pady=10, fill="both", expand=True)

        self.add_payment_frame = ctk.CTkFrame(self.tab)
        self.add_payment_frame.pack(padx=0, pady=(5, 20), fill="x")

        self.save_button = ctk.CTkButton(self.add_payment_frame, text="Aggiungi un pagamento",
                                         command=self.open_add_payment_window)
        self.save_button.pack()

        for payment in self.payment_controller.CY_payment_list:
            payment_id = payment[DBPaymentsColumns.ID.value]
            name = payment[DBPaymentsColumns.PAYMENT_NAME.value]
            amount = payment[DBPaymentsColumns.PAYMENT_AMOUNT.value]
            payment_date = payment[DBPaymentsColumns.PAYMENT_DATE.value]
            linked_rata = payment[DBPaymentsColumns.LINKED_RATA.value]
            invoice_id = payment[DBPaymentsColumns.INVOICE_ID.value]
            invoice = self.invoice_controller.retrieve_invoice_map_by_id(invoice_id)
            cliente_id = invoice[DBInvoicesColumns.ID_CLIENTE.value]
            client = self.client_controller.retrieve_client_map_by_id(cliente_id)
            client_name = client[DBClientsColumns.NAME.value]
            production_id = invoice[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value]
            production = self.production_controller.retrieve_production_map_by_id(production_id)
            production_name = production[DBProductionsColumns.NAME.value]
            conto = self.account_controller.retrieve_account_map_by_id(payment[DBPaymentsColumns.CONTO_ID.value])
            nome_conto = conto[DBAccountsColumns.NAME.value]

            self.add_payment_card(payment_id, name, amount, payment_date, linked_rata, client_name, production_name, nome_conto)

    def populate_global_infos(self):
        numero_pagamenti = self.payment_controller.CY_payments_aggregated_data[PaymentsController.PaymentsAggregateData.NUMERO_PAGAMENTI.value]
        totale_pagamenti = round(self.payment_controller.CY_payments_aggregated_data[PaymentsController.PaymentsAggregateData.TOT_PAGAMENTI.value], 2)
        self.global_infos[f"{PaymentsController.PaymentsAggregateData.NUMERO_PAGAMENTI.value}"] = numero_pagamenti
        self.global_infos[f"{PaymentsController.PaymentsAggregateData.TOT_PAGAMENTI.value}"] = f"{totale_pagamenti:.2f}"

    def open_add_payment_window(self):
        self.add_payment_window = ctk.CTkToplevel(self)
        self.add_payment_window.title("Aggiungi Nuovo Pagamento")

        # Assicurati che la finestra rimanga sopra
        self.add_payment_window.lift()  # Porta la finestra sopra quella principale
        self.add_payment_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

        self.add_payment_window.geometry("550x700")

        self.payment_window_scrollableFrame = ctk.CTkScrollableFrame(self.add_payment_window)
        self.payment_window_scrollableFrame.pack(fill="both", expand=True)

        self.nome_fattura_string = "NOME FATTURA"
        self.nome_conto_string = "NOME CONTO"

        self.entry_fields = {
            self.nome_fattura_string: ctk.CTkOptionMenu,
            DBPaymentsColumns.LINKED_RATA.value: ctk.CTkOptionMenu,
            DBPaymentsColumns.PAYMENT_NAME.value: ctk.CTkEntry,
            DBPaymentsColumns.PAYMENT_AMOUNT.value: ctk.CTkEntry,
            DBPaymentsColumns.PAYMENT_DATE.value: Calendar,
            self.nome_conto_string: ctk.CTkOptionMenu,
        }

        self.error_fields = {
            DBPaymentsColumns.PAYMENT_NAME.value: ctk.CTkLabel,
            DBPaymentsColumns.PAYMENT_AMOUNT.value: ctk.CTkLabel,
            DBPaymentsColumns.LINKED_RATA.value: ctk.CTkLabel
        }

        self.payment_widgets = {}
        self.error_labels = {}
        self.payment_labels = {}

        # Creo i labels e i widgets
        for i, (label_text, widget_class) in enumerate(self.entry_fields.items()):
            # Etichetta
            label = ctk.CTkLabel(self.payment_window_scrollableFrame, text=label_text)
            # disegno i labels
            if i == 0:
                label.pack(pady=5)
            else:
                label.pack(pady=(35, 0))

            self.payment_labels[label_text] = label

            # creo i widgets
            if label_text == self.nome_fattura_string:
                reversed_invoices = list(self.VF_invoice_list.values())[::-1]
                widget = widget_class(self.payment_window_scrollableFrame,
                                      values=reversed_invoices, command=lambda selected_value: self.toggle_linked_rata(selected_value))
            elif label_text == self.nome_conto_string:
                widget = widget_class(self.payment_window_scrollableFrame,
                                      values=[f"{item[DBAccountsColumns.NAME.value]}" for item in
                                              self.account_controller.account_list])
            elif label_text == DBPaymentsColumns.LINKED_RATA.value:
                widget = widget_class(self.payment_window_scrollableFrame,
                                      values=["1", "2", "3"],
                                      command = lambda selected_value: self.control_linked_rata(selected_value))
            elif label_text == DBPaymentsColumns.PAYMENT_DATE.value:
                widget = widget_class(self.payment_window_scrollableFrame, date_pattern=ViewUtils.date_pattern)
            else:
                widget = widget_class(self.payment_window_scrollableFrame)

            widget.pack(pady=5, padx=10, fill="x", expand=True)

            self.payment_widgets[label_text] = widget

            if self.error_fields.get(label_text) is not None:
                error_label = ctk.CTkLabel(self.payment_window_scrollableFrame, text="")
                error_label.pack(pady=(0, 15))
                self.error_labels[label_text] = error_label

        self.autofill_payment_amount()
        self.control_linked_rata("1")

        # Bottone per salvare
        self.save_button = ctk.CTkButton(
            self.payment_window_scrollableFrame,
            text="Salva Pagamento",
            command=self.save_payment_data
        )
        self.save_button.pack(pady=(35, 15))

        self.toggle_linked_rata(self.payment_widgets[self.nome_fattura_string].get())

        # Aggiungi validazione agli eventi di perdita del focus
        self.payment_widgets[DBPaymentsColumns.PAYMENT_NAME.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.payment_widgets[DBPaymentsColumns.PAYMENT_NAME.value],
            lambda val: val.strip() != "",
            self.error_labels[DBPaymentsColumns.PAYMENT_NAME.value],
            "Il campo non può essere vuoto."
        ))

        self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value],
            lambda val: re.fullmatch(r"^\d+(\.\d{2})?$", val.strip()) is not None,
            self.error_labels[DBPaymentsColumns.PAYMENT_AMOUNT.value],
            "Inserimento non valido: inserire un numero monetario con due cifre decimali (es. 123.45)"
        ))

    def add_payment_card(self, payment_id, payment_name, amount, payment_date, linked_rata, client_name, production_name, nome_conto):
        """
        Aggiunge una card di pagamento alla scrollable frame con i dati specificati.

        :param payment_id: ID univoco del pagamento nel database.
        :param payment_name: Nome del pagamento.
        :param amount: Importo del pagamento.
        :param payment_date: Data in cui è stato effettuato il pagamento.
        :param linked_rata: Identificativo o numero della rata collegata, se applicabile.
        :param client_name: Nome del cliente associato al pagamento.
        :param production_name: Nome della produzione correlata al pagamento.
        :param nome_conto: Nome del conto bancario associato al pagamento.
        """
        # Creazione della card
        card = ctk.CTkFrame(self.payments_cards_frame, fg_color="dimgray")
        card.pack(pady=10, padx=8, fill="x", expand=True)  # Spaziatura tra le card

        ctk.CTkButton(card, text=f"{payment_name}", width=245,
                      command=lambda: self.open_modify_payment(payment_id)).pack(
            padx=(10), pady=10, fill="both", side="left")

        # Dati da visualizzare nella card
        data = [client_name, production_name, round(amount, 2), ViewUtils.invert_data_string(payment_date), linked_rata, nome_conto]
        units = ["", "", "€", "", "", ""]
        i = 0
        # Aggiunta dei dati alla card
        for value in data:
            label = ctk.CTkLabel(card, text=f"{value} {units[i]}", font=("Arial", 14), width=245)
            label.pack(padx=(10), pady=5, fill="both", expand=True, side="left")

        self.payment_card_list[production_name] = card

        """child_list = self.payment_card_list[production_name].winfo_children()
        child_list[1].configure(bg_color="red")
        child_list[3].configure(bg_color="red")
        child_list[5].configure(bg_color="red")"""

    def auto_compile_name_entry(self, selected_value):
        return

    def save_payment_data(self):
        payment_data = {}

        # riempi il dizionario con i dati dei widgets primari
        for label_text, widget in self.payment_widgets.items():
            if isinstance(widget, ctk.CTkEntry) or isinstance(widget, ctk.CTkOptionMenu):
                payment_data[label_text] = widget.get()
            elif isinstance(widget, Calendar):
                payment_data[label_text] = widget.get_date()
            elif isinstance(widget, ctk.CTkTextbox):
                payment_data[label_text] = widget.get("1.0", "end-1c").strip()  # Recupera il testo dal Textbox

        #sistemo il nome della fattura che è ViewFriendly:
        nome_fattura_array = payment_data[self.nome_fattura_string].split(" - ")
        nome_fattura_ricostruito = nome_fattura_array[0] + " - " + nome_fattura_array[1]
        invoice_id = self.invoice_controller.retrieve_invoice_map_by_name(nome_fattura_ricostruito)[DBInvoicesColumns.ID.value]
        payment_data[DBPaymentsColumns.INVOICE_ID.value] = invoice_id

        ctrl_linked_rata = self.control_linked_rata(payment_data[DBPaymentsColumns.LINKED_RATA.value])
        confirmation = True

        if ctrl_linked_rata:
            confirmation = ViewUtils.ask_confirmation_popup(self.add_payment_window, "La rata selezionata presenta già un pagamento associato\nsei sicuro di voler continuare?", "CONFERMA OPERAZIONE")

        if confirmation:
            # chiamata al controller per salvare i dati
            success, message = self.payment_controller.save_payment(payment_data)

        if success:
            #aggiorno il controller delle fatture
            self.update_controller.update_invoices(invoice_id)

            # prendo l'ID della fattura appena creata
            payment_map = self.payment_controller.retrieve_last_payment_insert_map()
            print(f"Pagamento {payment_data[DBPaymentsColumns.PAYMENT_NAME.value]} salvato con successo")

            invoice = self.invoice_controller.retrieve_invoice_map_by_id(payment_map[DBPaymentsColumns.INVOICE_ID.value])
            client = self.client_controller.retrieve_client_map_by_id(invoice[DBInvoicesColumns.ID_CLIENTE.value])
            client_name = client[DBClientsColumns.NAME.value]
            production = self.production_controller.retrieve_production_map_by_id(invoice[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value])
            production_name = production[DBProductionsColumns.NAME.value]
            conto = self.account_controller.retrieve_account_map_by_id(payment_map[DBPaymentsColumns.CONTO_ID.value])
            nome_conto = conto[DBAccountsColumns.NAME.value]

            self.add_payment_card(
                payment_map[DBPaymentsColumns.ID.value],
                payment_map[DBPaymentsColumns.PAYMENT_NAME.value],
                payment_map[DBPaymentsColumns.PAYMENT_AMOUNT.value],
                payment_map[DBPaymentsColumns.PAYMENT_DATE.value],
                payment_map[DBPaymentsColumns.LINKED_RATA.value],
                client_name,
                production_name,
                nome_conto
            )

            self.clear_class_variable()
            self.add_payment_window.destroy()
        else:
            print(message)
            ViewUtils.show_error_popup(self.add_payment_window, "ERRORE", message)

    def construct_invoices_list_view_friendly(self):
        for invoice in self.invoice_controller.current_year_invoices_list:
            #invoicer_first_name = self.user_controller.retrieve_user_map_by_id(invoice[DBInvoicesColumns.ID_UTENTE.value])[DBUsersColumns.FIRST_NAME.value]
            invoicer_second_name = self.user_controller.retrieve_user_map_by_id(invoice[DBInvoicesColumns.ID_UTENTE.value])[DBUsersColumns.LAST_NAME.value]
            client_name = self.client_controller.retrieve_client_map_by_id(invoice[DBInvoicesColumns.ID_CLIENTE.value])[DBClientsColumns.NAME.value]
            self.VF_invoice_list[invoice[DBInvoicesColumns.ID.value]] =  invoice[DBInvoicesColumns.NUMERO_FATTURA.value] + " - " + client_name

    def toggle_linked_rata(self, selected_value):
        invoice_name = selected_value.split(" - ")
        invoice_name_reconstructed = invoice_name[0] + " - " + invoice_name[1]
        invoice = self.invoice_controller.retrieve_invoice_map_by_name(invoice_name_reconstructed)
        rateizzazione = int(invoice[DBInvoicesColumns.NUMERO_RATE.value])
        widget = self.payment_widgets[DBPaymentsColumns.LINKED_RATA.value]
        if rateizzazione == int(InvoiceController.Rateizzazione.UNA.value):
            widget.set("1")
            widget.configure(state=tk.DISABLED)
        if rateizzazione == int(InvoiceController.Rateizzazione.TRE.value):
            widget.configure(values=["1", "2", "3"], state=tk.NORMAL)

        self.autofill_payment_amount()
        selected_rata = self.payment_widgets[DBPaymentsColumns.LINKED_RATA.value].get()
        self.control_linked_rata(selected_rata)

    def clear_class_variable(self):  #potrebbe non servire in quanto vengono inizializzate all'apertura della funzione
        self.payment_widgets.clear()
        self.payment_widgets.clear()

    def autofill_payment_amount(self):
        # prendo la fattura di riferimento del pagamento
        VF_invoice_name = self.payment_widgets[self.nome_fattura_string].get()
        invoice_name_array = VF_invoice_name.split(" - ")
        invoice_name = invoice_name_array[0] + " - " + invoice_name_array[1]
        invoice = self.invoice_controller.retrieve_invoice_map_by_name(invoice_name)
        invoice_amount = float(invoice[DBInvoicesColumns.NETTO_A_PAGARE.value])
        invoice_rateiz = invoice[DBInvoicesColumns.NUMERO_RATE.value]

        self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].delete(0, tk.END)
        if int(invoice_rateiz) == int(InvoiceController.Rateizzazione.UNA.value):
            self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].insert(0, f"{invoice_amount:.2f}")
        elif int(invoice_rateiz) == int(InvoiceController.Rateizzazione.TRE.value):
            amount = round(invoice_amount/3, 2)
            self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].insert(0, f"{amount:.2f}")

    def control_linked_rata(self, selected_value):

        # prendo la fattura di riferimento del pagamento
        VF_invoice_name = self.payment_widgets[self.nome_fattura_string].get()
        invoice_name_array = VF_invoice_name.split(" - ")
        invoice_name = invoice_name_array[0] + " - " + invoice_name_array[1]
        invoice = self.invoice_controller.retrieve_invoice_map_by_name(invoice_name)

        rate_pagate = {
            "1" : False,
            "2" : False,
            "3" : False
        }

        payments = self.payment_controller.retrieve_payments_map_list_by_invoice_id(invoice[DBInvoicesColumns.ID.value])
        for payment in payments:
            if int(payment[DBPaymentsColumns.LINKED_RATA.value]) == 1:
                rate_pagate["1"] = True
            elif int(payment[DBPaymentsColumns.LINKED_RATA.value]) == 2:
                rate_pagate["2"] = True
            elif int(payment[DBPaymentsColumns.LINKED_RATA.value]) == 3:
                rate_pagate["3"] = True

        if rate_pagate[str(selected_value)]:
            self.error_labels[DBPaymentsColumns.LINKED_RATA.value].configure(text=f"Esiste già un pagamento relativo alla rata {selected_value}", text_color="#e39e27")
            return True
        else:
            self.error_labels[DBPaymentsColumns.LINKED_RATA.value].configure(text="", text_color="#e39e27")

    def open_modify_payment(self, payment_id):

        #prendo i dati della produzione
        payment = self.payment_controller.retrieve_payment_map_by_id(payment_id, True)
        invoice = self.invoice_controller.retrieve_invoice_map_by_id(payment[DBPaymentsColumns.INVOICE_ID.value])
        invoice_name = invoice[DBInvoicesColumns.NUMERO_FATTURA.value]
        client_name = self.client_controller.retrieve_client_map_by_id(invoice[DBInvoicesColumns.ID_CLIENTE.value])[DBClientsColumns.NAME.value]
        invoice_name = invoice_name + " - " + client_name
        conto_name = self.account_controller.retrieve_account_map_by_id(payment[DBPaymentsColumns.CONTO_ID.value])[DBAccountsColumns.NAME.value]

        self.open_add_payment_window()

        #configuro la finestra
        #self.add_production_window.configure(title=f"Modifica i dati della produzione {production[DBProductionsColumns.NAME.value]}")
        self.add_payment_window.title(f"Modifica i dati del pagamento {payment[DBPaymentsColumns.PAYMENT_NAME.value]}")
        self.save_button.configure(text="Salva Modifiche", command=self.modify_payment_data)
        self.payment_widgets[DBPaymentsColumns.PAYMENT_NAME.value].delete(0, tk.END)
        self.payment_widgets[DBPaymentsColumns.PAYMENT_NAME.value].insert(0, payment[DBPaymentsColumns.PAYMENT_NAME.value])
        self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].delete(0, tk.END)
        self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].insert(0, payment[DBPaymentsColumns.PAYMENT_AMOUNT.value])
        self.payment_widgets[DBPaymentsColumns.PAYMENT_DATE.value].selection_set(payment[DBPaymentsColumns.PAYMENT_DATE.value])
        self.payment_widgets[self.nome_fattura_string].set(invoice_name)
        self.payment_widgets[DBPaymentsColumns.LINKED_RATA.value].set(payment[DBPaymentsColumns.LINKED_RATA.value])
        self.payment_widgets[self.nome_conto_string].set(conto_name)

    def modify_payment_data(self):
        return

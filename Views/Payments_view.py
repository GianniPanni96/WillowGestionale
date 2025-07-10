import customtkinter as ctk
import tkinter as tk
from tkcalendar import Calendar
from Views.View_utils import ViewUtils
from Controllers import PaymentsController, InvoiceController, UserController, ControllerUtils
from Model import DBInvoicesColumns, DBUsersColumns, DBClientsColumns, DBPaymentsColumns, DBProductionsColumns, DBAccountsColumns
from datetime import datetime
import re
from enum import Enum

class PaymentsView(ctk.CTkFrame):

    def __init__(self, db_model, payment_controller, invoice_controller, user_controller, client_controller, production_controller, account_controller, update_controller, tab, event_bus):
        super().__init__(tab)

        self.db_model = db_model
        self.invoice_controller = invoice_controller
        self.user_controller = user_controller
        self.client_controller = client_controller
        self.payment_controller = payment_controller
        self.production_controller = production_controller
        self.account_controller = account_controller
        self.update_controller = update_controller
        self.tab = tab
        self.event_bus = event_bus

        self.global_infos = {}
        self.amount_aggregate_labels = {}

        #self.VF_invoice_list = {}
        #self.construct_invoices_list_view_friendly()

        self.payment_card_list = {}
        self.payment_card_labels_status = {}
        self.cards_warnings = {}

        self.update_controller.register_on_modify_invoice_view_cllbks(self.attach_warning_on_a_card)

        # Container principale
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.detail_container = ctk.CTkFrame(self, fg_color="transparent")

        # Vista dettaglio
        self.payment_detail_view = PaymentDetailView(
            parent=self,
            invoice_controller=self.invoice_controller,
            payment_controller=self.payment_controller,
            back_callback=self.show_main_view,
            account_controller=account_controller,
            client_controller=self.client_controller,
            production_controller=self.production_controller,
            update_controller=self.update_controller,
            db_model=db_model,
            event_bus = self.event_bus
        )

        self.create_payments_tab()
        self.show_main_view()

    def show_main_view(self):
        """Torna alla vista principale"""
        self.payment_detail_view.pack_forget()
        self.main_container.pack(fill='both', expand=True)

    def open_payment_detail_tab(self, invoice_id):
        """Mostra la vista dettaglio utente"""
        self.main_container.pack_forget()
        self.payment_detail_view.pack(fill='both', expand=True)
        self.payment_detail_view.create_detail_tab(invoice_id)  # Ricrea i contenuti ogni volta

    def create_payments_tab(self):

        self.search_bar_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.search_bar_frame.pack(pady=(5, 10), fill="x", anchor="s")
        self.search_bar = ctk.CTkEntry(self.search_bar_frame)
        self.search_bar.pack(padx=(5, 35), anchor="s", side="right")
        self.search_bar_option_menu_values = {"NOME PAGAM.": "NOME PAGAM.", "NOME CLIENTE": "NOME CLIENTE",
                                              "NOME PRODUZIONE": "NOME PRODUZIONE", "CONTO": "CONTO"}
        self.search_bar_optionMenu = ctk.CTkOptionMenu(self.search_bar_frame,
                                                       values=list(self.search_bar_option_menu_values.values()))
        self.search_bar_optionMenu.pack(padx=5, anchor="s", side="right")
        self.search_bar_label = ctk.CTkLabel(self.search_bar_frame, text="Filtra per ", font=("Arial", 14))
        self.search_bar_label.pack(padx=5, anchor="s", side="right")

        # Aggiungi evento alla barra di ricerca
        self.search_bar.bind("<KeyRelease>", self.filter_cards)

        self.populate_global_infos()

        for (key, info) in self.global_infos.items():
            card = ctk.CTkFrame(self.search_bar_frame, fg_color="#333333")

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

        self.payments_table_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.payments_table_frame.pack(pady=(20, 0), padx=(10, 15), fill="x", anchor="n")

        self.table_headers = ["NOME", "CLIENTE", "PRODUZIONE", "FATTURA", "TOTALE", "DATA", "RATA", "CONTO\nCORRENTE"]

        for i, header in enumerate(self.table_headers):
            # crea il container
            column = ctk.CTkFrame(self.payments_table_frame, fg_color="#333333")
            column.grid(row=0, column=i, sticky="nsew", padx=(0, 5), pady=5)

            # imposta peso e uniformità: tutte le colonne "col" si dividono equamente
            self.payments_table_frame.grid_columnconfigure(i, weight=1, uniform="col")

            # la label riempie il suo container
            label = ctk.CTkLabel(column,
                                 text=header,
                                 font=("Arial", 14))
            label.pack(fill="both", expand=True, padx=5, pady=15)

        # Creazione del frame delle cards
        self.payments_cards_frame = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")
        self.payments_cards_frame.pack(padx=0, pady=10, fill="both", expand=True)

        self.add_payment_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.add_payment_frame.pack(padx=0, pady=(5, 20), fill="x")

        self.save_button = ctk.CTkButton(self.add_payment_frame, text="Aggiungi un pagamento",
                                         command=self.open_add_payment_window)
        self.save_button.pack()

        #aggiungo una tab per ogni fattura presente nel database
        payments_map_list = self.payment_controller.retrieve_payments_map_list(current_year=True)
        # Ordina la lista in ordine decrescente (dal più recente al più vecchio)
        payments_map_list.sort(
            key=lambda x: datetime.strptime(
                x[DBPaymentsColumns.UPDATED_AT.value],
                "%Y-%m-%d %H:%M:%S"
            ) if " " in x[DBPaymentsColumns.UPDATED_AT.value] else datetime.strptime(
                x[DBPaymentsColumns.UPDATED_AT.value],
                "%Y-%m-%d"
            ),
            reverse=True
        )

        for payment in payments_map_list:
            if payment:
                payment_id = payment[DBPaymentsColumns.ID.value]
                name = payment[DBPaymentsColumns.PAYMENT_NAME.value]
                amount = payment[DBPaymentsColumns.PAYMENT_AMOUNT.value]
                payment_date = payment[DBPaymentsColumns.PAYMENT_DATE.value]
                linked_rata = payment[DBPaymentsColumns.LINKED_RATA.value]
                invoice_id = payment[DBPaymentsColumns.INVOICE_ID.value]
                invoice = self.invoice_controller.retrieve_invoice_map_by_id(invoice_id)
                invoice_name = invoice[DBInvoicesColumns.NUMERO_FATTURA.value]
                cliente_id = invoice[DBInvoicesColumns.ID_CLIENTE.value]
                client = self.client_controller.retrieve_client_map_by_id(cliente_id)
                client_name = client[DBClientsColumns.NAME.value]
                production_id = invoice[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value]
                production = self.production_controller.retrieve_production_map_by_id(production_id)
                production_name = production[DBProductionsColumns.NAME.value]
                conto = self.account_controller.retrieve_account_map_by_id(payment[DBPaymentsColumns.CONTO_ID.value])
                nome_conto = conto[DBAccountsColumns.NAME.value] if conto else "conto non trovato"

                #warnings attachments
                if invoice[DBInvoicesColumns.STATUS.value] == InvoiceController.InvoiceSatus.STORNATA.value:
                    self.cards_warnings[name] = "Questo pagamento fa riferimento ad una fattura stornata,\n"\
                                                "modificare i dati del pagamento per mantenere la consistenza dei dati.\n"\
                                                "Si consiglia di eliminare questo pagamento o collegarlo alla fattura corretta."

                invoice_update_date = datetime.strptime(invoice[DBInvoicesColumns.UPDATED_AT.value], "%Y-%m-%d %H:%M:%S")
                payment_update_date = datetime.strptime(payment[DBPaymentsColumns.UPDATED_AT.value], "%Y-%m-%d %H:%M:%S")

                if invoice_update_date > payment_update_date and invoice[DBInvoicesColumns.STATUS.value] != InvoiceController.InvoiceSatus.STORNATA.value:
                    self.cards_warnings[name] = (
                        "Questo pagamento fa riferimento ad una fattura i cui dati sono stati modificati.\n"
                        "Controllare la consistenza dei dati di questo pagamento.\n"
                    )

                self.add_payment_card(payment_id, name, amount, payment_date, linked_rata, client_name, production_name, invoice_name, nome_conto)

        #warnings launch
        for card in self.payment_card_list.values():
            ViewUtils.toggle_warning_on_card(card, self.cards_warnings)

    def populate_global_infos(self):
        numero_pagamenti = self.payment_controller.CY_payments_aggregated_data[PaymentsController.PaymentsAggregateData.NUMERO_PAGAMENTI.value]
        totale_pagamenti = round(self.payment_controller.CY_payments_aggregated_data[PaymentsController.PaymentsAggregateData.TOT_PAGAMENTI.value], 2)
        self.global_infos[f"{PaymentsController.PaymentsAggregateData.NUMERO_PAGAMENTI.value}"] = numero_pagamenti
        self.global_infos[f"{PaymentsController.PaymentsAggregateData.TOT_PAGAMENTI.value}"] = f"{totale_pagamenti:.2f}"

    def filter_cards(self, event):
        """Filtra le card in base al testo della barra di ricerca e al tipo di filtro scelto."""
        search_text = self.search_bar.get().lower()
        search_type = self.search_bar_optionMenu.get()

        # Mappatura: ogni chiave associa una tupla (indice, classe_attesa) del widget da cui prelevare il testo
        filter_mapping = {
            "NOME PAGAM.": (0, ctk.CTkButton),  # Bottone
            "NOME CLIENTE": (1, ctk.CTkLabel),
            "NOME PRODUZIONE": (2, ctk.CTkLabel),
            "CONTO": (3, ctk.CTkLabel),
        }

        mapping = filter_mapping.get(search_type)

        # Prima rimuovo tutte le card dal container per avere un layout pulito
        for card in self.payment_card_list.values():
            card.pack_forget()

        # Se il tipo di ricerca non è riconosciuto, riposiziona tutte le card nell'ordine originale
        if mapping is None:
            for card in self.payment_card_list.values():
                card.pack(pady=10, padx=10, fill="x", expand=True)
            return

        idx, expected_class = mapping

        # Itera sulle card nell’ordine originale (grazie al dizionario ordinato)
        for key, card in self.payment_card_list.items():
            children = card.winfo_children()  # Lista dei widget figli
            widget_text = ""
            if len(children) > idx and isinstance(children[idx], expected_class):
                widget_text = children[idx].cget("text")
            # Se il testo (in lowercase) contiene il testo di ricerca, riposiziona la card
            if search_text in widget_text.lower():
                card.pack(pady=10, padx=10, fill="x", expand=True)

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
                VF_invoice_list = self.construct_invoices_list_view_friendly()
                reversed_invoices = list(VF_invoice_list.values())[::-1]
                widget = widget_class(self.payment_window_scrollableFrame,
                                      values=reversed_invoices, command=lambda selected_value: self.toggle_linked_rata(selected_value))
            elif label_text == self.nome_conto_string:
                widget = widget_class(self.payment_window_scrollableFrame,
                                      values=[f"{item[DBAccountsColumns.NAME.value]}" for item in
                                              self.account_controller.retrieve_accounts_map_list()])
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

    def add_payment_card(self, payment_id, payment_name, amount, payment_date, linked_rata, client_name, production_name, invoice_name, nome_conto):
        """
        Aggiunge una card di pagamento alla scrollable frame con i dati specificati.

        :param payment_id: ID univoco del pagamento nel database.
        :param payment_name: Nome del pagamento.
        :param amount: Importo del pagamento.
        :param payment_date: Data in cui è stato effettuato il pagamento.
        :param linked_rata: Identificativo o numero della rata collegata, se applicabile.
        :param client_name: Nome del cliente associato al pagamento.
        :param production_name: Nome della produzione correlata al pagamento.
        :param invoice_name: Nome della fattura correlata al pagamento.
        :param nome_conto: Nome del conto bancario associato al pagamento.
        """
        # Creazione della card
        card = ctk.CTkFrame(self.payments_cards_frame, fg_color="dimgray")
        card.pack(pady=10, padx=8, fill="x", expand=True)  # Spaziatura tra le card

        # Dati da visualizzare nella card
        data = [payment_name, client_name, production_name, invoice_name, round(amount, 2), ViewUtils.invert_data_string(payment_date), linked_rata, nome_conto]
        units = ["", "", "", "", "€", "", "", ""]
        n_cols = len(data)  # 8 colonne totali

        # Configura il grid della card: 1 riga, n_cols colonne uguali
        for c in range(n_cols):
            card.grid_columnconfigure(c, weight=1, uniform="clientcol")
        card.grid_rowconfigure(0, weight=1)

        # 0) Bottone "nome"
        btn = ctk.CTkButton(
            card,
            text=payment_name,
            command=lambda pid=payment_id: self.open_payment_detail_tab(pid)
        )
        btn.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        # 1..7) Le altre colonne
        for idx, val in enumerate(data[1:], start=1):
            text = f"{val} {units[idx]}"
            lbl = ctk.CTkLabel(card, text=text, font=("Arial", 14))
            lbl.grid(row=0, column=idx, sticky="nsew", padx=5, pady=10)

        # Salva la card per eventuale successivo accesso
        self.payment_card_list[payment_name] = card

        # Se esiste un warning associato al nome del pagamento, aggiungi il tooltip
        if payment_name in self.cards_warnings:
            ViewUtils.add_tooltip(btn, self.cards_warnings[payment_name])

    def auto_compile_name_entry(self, selected_value):
        return

    def save_payment_data(self):
        payment_data = {}

        # riempi il dizionario con i dati dei widgets primari
        for label_text, widget in self.payment_widgets.items():
            if isinstance(widget, ctk.CTkEntry) or isinstance(widget, ctk.CTkOptionMenu):
                payment_data[label_text] = widget.get().strip()
            elif isinstance(widget, Calendar):
                payment_data[label_text] = widget.get_date()
            elif isinstance(widget, ctk.CTkTextbox):
                payment_data[label_text] = widget.get("1.0", "end-1c").strip()  # Recupera il testo dal Textbox

        #sistemo il nome della fattura che è ViewFriendly:
        nome_fattura_array = payment_data[self.nome_fattura_string].strip().split(" - ")
        nome_fattura_ricostruito = nome_fattura_array[0] + " - " + nome_fattura_array[1] + " - " + nome_fattura_array[2]
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
            self.update_controller.on_adding_payment()

            # prendo l'ID della fattura appena creata
            payment_map = self.payment_controller.retrieve_last_payment_insert_map()
            print(f"Pagamento {payment_data[DBPaymentsColumns.PAYMENT_NAME.value]} salvato con successo")

            invoice = self.invoice_controller.retrieve_invoice_map_by_id(payment_map[DBPaymentsColumns.INVOICE_ID.value])
            invoice_name = invoice[DBInvoicesColumns.NUMERO_FATTURA.value]
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
                invoice_name,
                nome_conto
            )

            self.clear_class_variable()
            self.add_payment_window.destroy()
        else:
            print(message)
            ViewUtils.show_error_popup(self.add_payment_window, "ERRORE", message)

    def construct_invoices_list_view_friendly(self):
        VF_invoice_list = {}

        for invoice in self.invoice_controller.retrieve_invoices_map_list(True):
            invoicer_second_name = self.user_controller.retrieve_user_map_by_id(invoice[DBInvoicesColumns.ID_UTENTE.value])[DBUsersColumns.LAST_NAME.value]
            client_name = self.client_controller.retrieve_client_map_by_id(invoice[DBInvoicesColumns.ID_CLIENTE.value])[DBClientsColumns.NAME.value]

            VF_invoice_list[invoice[DBInvoicesColumns.ID.value]] =  invoice[DBInvoicesColumns.NUMERO_FATTURA.value] + " - " + client_name

        return VF_invoice_list

    def toggle_linked_rata(self, selected_value):
        invoice_name = selected_value.split(" - ")
        invoice_name_reconstructed = invoice_name[0] + " - " + invoice_name[1] + " - " + invoice_name[2]
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
        invoice_name = invoice_name_array[0] + " - " + invoice_name_array[1] + " - " + invoice_name_array[2] if len(invoice_name_array) == 4 else invoice_name_array[0] + " - " + invoice_name_array[1]
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
        invoice_name = invoice_name_array[0] + " - " + invoice_name_array[1] + " - " + invoice_name_array[2]
        invoice = self.invoice_controller.retrieve_invoice_map_by_name(invoice_name)

        netto_rate_fattura = {
            "1" : 0.0,
            "2" : 0.0,
            "3" : 0.0
        }

        netto_rate_pagate = {
            "1": 0.0,
            "2": 0.0,
            "3": 0.0
        }

        if int(invoice[DBInvoicesColumns.NUMERO_RATE.value]) == int(InvoiceController.Rateizzazione.UNA.value):
            netto_rate_fattura["1"] = float(invoice[DBInvoicesColumns.NETTO_A_PAGARE.value])
            netto_rate_fattura["2"] = 0.0
            netto_rate_fattura["3"] = 0.0
        elif int(invoice[DBInvoicesColumns.NUMERO_RATE.value]) == int(InvoiceController.Rateizzazione.TRE.value):
            rata = float(invoice[DBInvoicesColumns.NETTO_A_PAGARE.value]) / 3
            netto_rate_fattura["1"] = rata
            netto_rate_fattura["2"] = rata
            netto_rate_fattura["3"] = rata

        rate_saldate = {
            "1" : False,
            "2" : False,
            "3" : False
        }

        #calcolo il totale dei pagamenti per rata
        payments = self.payment_controller.retrieve_payments_map_list_by_invoice_id(invoice[DBInvoicesColumns.ID.value])
        for payment in payments:
            if int(payment[DBPaymentsColumns.LINKED_RATA.value]) == 1:
                netto_rate_pagate["1"] = netto_rate_pagate["1"] + float(payment[DBPaymentsColumns.PAYMENT_AMOUNT.value])
            elif int(payment[DBPaymentsColumns.LINKED_RATA.value]) == 2:
                netto_rate_pagate["2"] = netto_rate_pagate["2"] + float(payment[DBPaymentsColumns.PAYMENT_AMOUNT.value])
            elif int(payment[DBPaymentsColumns.LINKED_RATA.value]) == 3:
                netto_rate_pagate["3"] = netto_rate_pagate["3"] + float(payment[DBPaymentsColumns.PAYMENT_AMOUNT.value])

        for i in ["1", "2", "3"]:
            tot_mancante = netto_rate_fattura[i] - netto_rate_pagate[i]
            if netto_rate_pagate[i] >= netto_rate_fattura[i] or (5 > tot_mancante > 0):
                rate_saldate[i] = True

        if rate_saldate[str(selected_value)]:
            self.error_labels[DBPaymentsColumns.LINKED_RATA.value].configure(
                text=f"La rata {selected_value} è già interamente saldata ({round(netto_rate_pagate[str(selected_value)], 2)}€)", text_color="#e39e27")
            self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].delete(0, tk.END)
            self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].insert(0, "0.00")
            self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].configure(border_color="#e39e27")
            return True
        else:
            tot_mancante = (netto_rate_fattura[str(selected_value)] - netto_rate_pagate[str(selected_value)])
            self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].configure(border_color="gray")
            if netto_rate_pagate[str(selected_value)] > 0 and tot_mancante >= 5:
                self.error_labels[DBPaymentsColumns.LINKED_RATA.value].configure(
                    text=f"Totale mancante da saldare della rata {selected_value}: {round(tot_mancante, 2)}€", text_color="#e39e27")
                self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].delete(0, tk.END)
                self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].insert(0, round(tot_mancante, 2))
            else:
                self.error_labels[DBPaymentsColumns.LINKED_RATA.value].configure(text="", text_color="#e39e27")
                self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].configure(border_color="gray")
                self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].delete(0, tk.END)
                self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].insert(0, round(tot_mancante, 2))

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

    # funzione da passare all'updater come callback
    def attach_warning_on_a_card(self, payment_name, warning):
        #cerco tra le cards quella che mi interessa
        for card in self.payment_card_list.values():
            children = card.winfo_children()
            for child in children:
                if isinstance(child, ctk.CTkButton):
                    button_text = child.cget("text")  # oppure child["text"]
                    if button_text == payment_name:
                        self.cards_warnings[payment_name] = warning
                        card = card
                        continue

        ViewUtils.toggle_warning_on_card(card, self.cards_warnings)



class PaymentDetailView(ctk.CTkFrame):
    def __init__(self, parent, back_callback, invoice_controller, payment_controller, account_controller, client_controller, production_controller, update_controller, db_model, event_bus):
        super().__init__(parent)
        self.invoice_controller = invoice_controller
        self.payment_controller = payment_controller
        self.account_controller = account_controller
        self.client_controller = client_controller
        self.production_controller = production_controller
        self.db_model = db_model
        self.back_callback = back_callback
        self.update_controller = update_controller
        self.event_bus = event_bus
        self.current_invoice_id = None

        self.configure(fg_color="transparent")

        # Widgets persistenti (vanno creati una volta sola)
        self.head_frame = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.back_button = ctk.CTkButton(
            self.head_frame,
            text="Elenco Pagamenti",
            command=self._cleanup_and_go_back
        )
        self.title_label = ctk.CTkLabel(self.head_frame, font=("Arial", 22, "bold"))

        self.payment_info_widgets: dict[str, ctk.CTkEntry | ctk.CTkOptionMenu] = {}

        self.nome_conto_string = "CONTO"
        self.nome_cliente_string = "CLIENTE"
        self.nome_user_string = "UTENTE"
        self.nome_fattura_string = "FATTURA ASSOCIATA"
        self.nome_produzione_associata_string = "PRODUZIONE ASSOCIATA"

        # Container per i contenuti dinamici
        self.content_frame = ctk.CTkScrollableFrame(self)

        self.switch_modify = ctk.CTkSwitch(self.head_frame, text="Abilita la modifica", command=lambda: self.toggle_edit(self.content_frame))

        # Layout iniziale
        self._setup_base_layout()

        #self.update_controller.register_on_adding_payment_view_cllbks(self.toggle_warning_global_info_payments)



    def _setup_base_layout(self):
        """Inizializza la struttura base del layout"""
        self.head_frame.pack(fill="x", pady=5, padx=5)
        self.back_button.pack(anchor="w", side="left", pady=10, padx=10)
        self.title_label.pack(anchor="c", side="left", fill="x", expand=True, pady=10)
        self.switch_modify.pack(anchor="e", side="left", pady=10, padx=10)
        self.content_frame.pack(fill="both", expand=True, pady=20, padx=20)

    def create_detail_tab(self, payment_id):
        """Ricrea la vista dettaglio per un pagamento specifico"""
        self.current_payment_id = payment_id

        # 1. Pulizia dei widget precedenti
        self._clear_content()

        # 2. Caricamento dati
        payment = self.payment_controller.retrieve_payment_map_by_id(payment_id)

        #prendo i dati della fattura associata
        invoice = self.invoice_controller.retrieve_invoice_map_by_id(payment[DBPaymentsColumns.INVOICE_ID.ID])

        # prendo il nome del conto:
        id_conto = payment[DBPaymentsColumns.CONTO_ID.value]
        conto = self.account_controller.retrieve_account_map_by_id(id_conto)
        nome_conto = conto[DBAccountsColumns.NAME.value] if conto else "Conto non trovato"
        payment[self.nome_conto_string] = nome_conto

        # prendo il nome del cliente
        id_cliente = invoice[DBInvoicesColumns.ID_CLIENTE.value]
        cliente = self.client_controller.retrieve_client_map_by_id(id_cliente)
        nome_cliente = cliente[DBClientsColumns.NAME.value] if cliente else "Cliente non trovato"
        invoice[self.nome_cliente_string] = nome_cliente

        # prendo il nome della produzione associata
        id_prod = invoice[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value]
        prod = self.production_controller.retrieve_production_map_by_id(id_prod)
        nome_produzione = prod[DBProductionsColumns.NAME.value] if prod else "Produzione non trovata"
        invoice[self.nome_produzione_associata_string] = nome_produzione

        # 3. Aggiornamento elementi persistenti
        self.title_label.configure(
            text=f"{payment[DBPaymentsColumns.PAYMENT_NAME.value]}")

        # 4. Creazione contenuti dinamici
        self._create_payment_info_section(payment)
        self.toggle_edit(self.content_frame)

        self.wrapper_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.wrapper_frame.pack(padx=15, pady=(90, 0), fill="both", expand=True)
        self.wrapper_frame2 = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.wrapper_frame2.pack(padx=15, pady=(90, 90), fill="both", expand=True)

        #self._create_payments_history()
        #self._create_production_expenses_history()

    def _create_payment_info_section(self, payment_data):
        # Campi derivati per i pagamenti (se necessario)
        self.derived_fields_payments = {
            # Potresti aggiungere campi calcolati qui se necessario
        }

        self.entry_fields_payments = {
            # Dati Generali
            DBPaymentsColumns.PAYMENT_NAME.value: {
                "type": ctk.CTkLabel,
                "label": "Nome Pagamento",
                "section": "Dati Generali"
            },
            DBPaymentsColumns.PAYMENT_DATE.value: {
                "type": Calendar,
                "label": "Data Pagamento",
                "section": "Dati Generali"
            },
            DBPaymentsColumns.LINKED_RATA.value: {
                "type": ctk.CTkOptionMenu,
                "label": "Rata Associata",
                "section": "Dati Generali",
                "values": ["1", "2", "3"]
            },

            # Dati Fiscali
            DBPaymentsColumns.PAYMENT_AMOUNT.value: {
                "type": ctk.CTkEntry,
                "label": "Importo Pagato (€)",
                "section": "Dati Fiscali"
            },

            # Collegamenti
            self.nome_fattura_string: {
                "type": ctk.CTkOptionMenu,
                "label": "Fattura Associata",
                "section": "Collegamenti",
                "values": [f"{i[DBInvoicesColumns.NUMERO_FATTURA.value]} - {i[DBInvoicesColumns.ID_CLIENTE.value]}"
                           for i in self.invoice_controller.retrieve_invoices_map_list()]
            },
            self.nome_conto_string: {
                "type": ctk.CTkOptionMenu,
                "label": "Conto",
                "section": "Collegamenti",
                "values": [c[DBAccountsColumns.NAME.value] for c in
                           self.account_controller.retrieve_accounts_map_list()]
            },

            # Campi statici
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

        self.error_fields_payments = {
            DBPaymentsColumns.PAYMENT_AMOUNT.value: "Valore numerico con massimo 2 decimali",
            DBPaymentsColumns.PAYMENT_DATE.value: "Data obbligatoria"
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

        # Inizializzazione strutture dati
        self.payment_info_widgets = {}
        self.payment_info_labels = {}
        self.error_labels_payments = {}
        sections = {}

        # Creazione frame principale
        info_frame = ctk.CTkFrame(self.content_frame, border_width=2, border_color="#2659ab")
        info_frame.pack(fill="both", expand=True, pady=10, padx=25)

        # Configurazione griglia a 2 colonne (meno campi)
        info_frame.grid_columnconfigure(0, weight=1, uniform="col")
        info_frame.grid_columnconfigure(1, weight=1, uniform="col")

        # Sezioni organizzate per colonne
        sections_order = [
            "Dati Generali",
            "Dati Fiscali",
            "Collegamenti",
            "Note"
        ]

        # Creazione frame sezioni
        for i, section_name in enumerate(sections_order):
            frame = ctk.CTkFrame(info_frame)
            column = i % 2  # Solo 2 colonne
            row = i // 2  # Calcola la riga in base all'indice

            frame.grid(row=row, column=column, sticky="nsew", padx=15, pady=15)
            frame.grid_columnconfigure(1, weight=1)

            sections[section_name] = {
                "frame": frame,
                "row": 0
            }

            ctk.CTkLabel(frame, text=section_name, font=("Arial", 14, "bold")).grid(
                row=0, column=0, columnspan=2, sticky="w", padx=15, pady=5
            )
            sections[section_name]["row"] += 1

        # Popolamento sezioni
        for field, config in self.entry_fields_payments.items():
            section = sections[config["section"]]
            frame = section["frame"]
            row = section["row"]

            # Creazione label
            lbl = ctk.CTkLabel(frame, text=config["label"] + ":")
            self.payment_info_labels[field] = lbl

            lbl.grid(row=row, column=0, sticky="w", padx=(15, 5), pady=(5, 5))

            # Creazione widget
            if config["type"] == ctk.CTkLabel:
                value = str(payment_data.get(field, ""))
                widget = config["type"](frame, text=value)
            else:
                if config["type"] == ctk.CTkOptionMenu:
                    widget = config["type"](frame, values=config.get("values", []))
                    widget.set(payment_data.get(field, config.get("values", [""])[0]))

                elif config["type"] == Calendar:
                    widget = config["type"](frame, date_pattern=ViewUtils.date_pattern)
                    value = payment_data.get(field, "")
                    widget.selection_set(str(value)) if value else widget.selection_set(datetime.today())
                else:
                    widget = config["type"](frame)
                    value = str(payment_data.get(field, ""))
                    widget.insert(0, value)

            widget.grid(row=row, column=1, sticky="ew", padx=(5, 15), pady=(5, 5))
            self.payment_info_widgets[field] = widget

            # Gestione validazione
            if field in validation_rules:
                validation_func, error_message = validation_rules[field]

                error_lbl = ctk.CTkLabel(frame, text="", text_color="#e8e5dc")
                error_lbl.grid(row=row + 1, column=1, sticky="w", padx=5, pady=(0, 10))
                self.error_labels_payments[field] = error_lbl

                widget.bind("<FocusOut>",
                            lambda e, w=widget, vl=validation_func, el=error_lbl, em=error_message:
                            ViewUtils.validate_entry(w, vl, el, em))

                section["row"] += 2
            else:
                section["row"] += 1

        # Binding per calcoli automatici (se necessario)
        # self.payment_info_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].bind("<FocusOut>", self.calcola_totale_pagamento)

        buttons_frame = ctk.CTkFrame(info_frame, fg_color="#2b2b2b")
        buttons_frame.grid(row=2, column=0, columnspan=2, pady=(5, 15), padx=20, sticky="WE")

        # Bottone Salva
        self.save_payment_btn = ctk.CTkButton(buttons_frame, text="Salva Pagamento", command=self.save_payment_mod)
        self.save_payment_btn.pack(padx=(400, 10), pady=(20, 20), side="left")

        # Bottone Elimina
        self.delete_btn = ctk.CTkButton(buttons_frame, text="Elimina Pagamento",
                                        fg_color="#8B0000", hover_color="#A52A2A",
                                        command=self.delete_payment)
        self.delete_btn.pack(padx=10, pady=(20, 20), side="right", anchor="e")



    def toggle_edit(self, parent):
        """
        Abilita o disabilita la modifica dei widget nella finestra di modifica utente.
        I campi derivati e il campo RIVAlSA_INPS per utenti con regime ordinario restano disabilitati.
        """
        state = ctk.NORMAL if self.switch_modify.get() else ctk.DISABLED

        # Stato del pulsante Salva
        self.save_payment_btn.configure(state=state)
        self.delete_btn.configure(state=state)

        # Recupera il regime fiscale dell'utente corrente
        invoice = self.invoice_controller.retrieve_invoice_map_by_id(self.current_invoice_id)
        user_map = self.user_controller.retrieve_user_map_by_id(invoice[DBInvoicesColumns.ID_UTENTE.value])
        is_ordinario = user_map[
                           DBUsersColumns.REGIME_FISCALE.value] == self.user_controller.RegimeFiscale.ORDINARIO.value

        for w in parent.winfo_children():
            # Ottieni il campo associato a questo widget, se esiste
            widget_field = next((k for k, v in self.invoice_info_widgets.items() if v == w), None)

            # Verifica se campo derivato
            is_derived = widget_field in self.derived_fields if widget_field else False
            # Verifica se è il campo Rivalsa INPS con utente ordinario
            is_rivalsa_locked = widget_field == DBInvoicesColumns.RIVALSA_INPS.value and is_ordinario

            # Imposta stato finale
            widget_state = ctk.DISABLED if is_derived or is_rivalsa_locked else state

            if isinstance(w, ctk.CTkEntry):
                w.configure(state=widget_state, text_color="#636363" if widget_state == ctk.DISABLED else "#c2c2c2")
            elif isinstance(w, ctk.CTkOptionMenu):
                w.configure(state=widget_state)
            elif isinstance(w, Calendar):
                w.configure(state=widget_state)
            elif isinstance(w, (ctk.CTkFrame, ctk.CTkScrollableFrame, ctk.CTkToplevel)):
                self.toggle_edit(w)

    def _clear_content(self):
        """Distrugge tutti i widget dinamici"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        self.switch_modify.deselect()

    def _cleanup_and_go_back(self):
        """Pulizia completa prima di tornare indietro"""
        self._clear_content()
        self.pack_forget()
        self.back_callback()
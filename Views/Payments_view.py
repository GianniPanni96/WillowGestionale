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

    def __init__(self, db_model, payment_controller, invoice_controller, user_controller, client_controller, production_controller, account_controller, update_controller, tab, event_bus):
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
        self.event_bus = event_bus

        self.global_infos = {}
        self.amount_aggregate_labels = {}

        #self.VF_invoice_list = {}
        #self.construct_invoices_list_view_friendly()

        self.payment_card_list = {}
        self.payment_card_labels_status = {}
        self.cards_warnings = {}

        self.update_controller.register_on_modify_invoice_view_cllbks(self.attach_warning_on_a_card)

        self.create_payments_tab()

    def create_payments_tab(self):

        self.search_bar_frame = ctk.CTkFrame(self.tab)
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
            card = ctk.CTkFrame(self.search_bar_frame)

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

        self.table_headers = ["NOME", "CLIENTE", "PRODUZIONE", "FATTURA", "TOTALE", "DATA", "RATA", "CONTO\nCORRENTE"]

        for i, header in enumerate(self.table_headers):
            # crea il container
            column = ctk.CTkFrame(self.payments_table_frame)
            column.grid(row=0, column=i, sticky="nsew", padx=(0, 5), pady=5)

            # imposta peso e uniformità: tutte le colonne "col" si dividono equamente
            self.payments_table_frame.grid_columnconfigure(i, weight=1, uniform="col")

            # la label riempie il suo container
            label = ctk.CTkLabel(column,
                                 text=header,
                                 font=("Arial", 14))
            label.pack(fill="both", expand=True, padx=5, pady=15)

        # Creazione del frame delle cards
        self.payments_cards_frame = ctk.CTkScrollableFrame(self.tab)
        self.payments_cards_frame.pack(padx=0, pady=10, fill="both", expand=True)

        self.add_payment_frame = ctk.CTkFrame(self.tab)
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
            command=lambda pid=payment_id: self.open_modify_payment(pid)
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

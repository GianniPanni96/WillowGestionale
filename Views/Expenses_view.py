import customtkinter as ctk
import tkinter as tk
from tkcalendar import Calendar
from Views.View_utils import ViewUtils
from Controllers import PaymentsController, ExpenseController, InvoiceController, UserController, ControllerUtils
from Model import DBInvoicesColumns, DBUsersColumns, DBClientsColumns, DBPaymentsColumns, DBProductionsColumns, DBAccountsColumns, DBExpensesColumns, DBSuppliersColumns
import re
from enum import Enum
from dataclasses import fields
from datetime import datetime, timedelta, date


class ExpensesView(ctk.CTkFrame):

    def __init__(self, db_model, expense_controller, user_controller, account_controller, supplier_controller, invoice_controller, update_controller, analyzer, fiscal_settings, catalogo_elenchi, config_manager, tab, event_bus):
        super().__init__(tab)

        self.db_model = db_model
        self.expense_controller = expense_controller
        self.user_controller = user_controller
        self.account_controller = account_controller
        self.supplier_controller = supplier_controller
        self.invoice_controller = invoice_controller
        self.update_controller = update_controller
        self.analyzer = analyzer
        self.fiscal_settings = fiscal_settings
        self.catalogo_elenchi = catalogo_elenchi
        self.config_manager = config_manager
        self.tab = tab
        self.event_bus = event_bus

        self.global_infos = {}
        self.amount_aggregate_labels = {}
        self.aggregate_UOM = {
            ExpenseController.ExpensesAggregateData.NUMERO_SPESE.value: "",
            ExpenseController.ExpensesAggregateData.TOT_SPESE.value: "€"
        }

        self.expenses_card_list = {}
        self.expense_card_labels_status = {}
        self.cards_warnings = {}

        # Container principale
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.detail_container = ctk.CTkFrame(self, fg_color="transparent")

        # Vista dettaglio
        self.expense_detail_view = ExpenseDetailView(
            parent=self,
            invoice_controller=self.invoice_controller,
            supplier_controller=self.supplier_controller,
            back_callback=self.show_main_view,
            account_controller=account_controller,
            user_controller=self.user_controller,
            expense_controller=self.expense_controller,
            update_controller=self.update_controller,
            db_model=db_model,
            event_bus = self.event_bus,
            catalogo_elenchi=self.catalogo_elenchi
        )

        self.create_expenses_tab()
        self.show_main_view()

    def show_main_view(self):
        """Torna alla vista principale"""
        self.expense_detail_view.pack_forget()
        self.main_container.pack(fill='both', expand=True)

    def open_expense_detail_tab(self, expense_id):
        """Mostra la vista dettaglio utente"""
        self.main_container.pack_forget()
        self.expense_detail_view.pack(fill='both', expand=True)
        self.expense_detail_view.create_detail_tab(expense_id)  # Ricrea i contenuti ogni volta

    def create_expenses_tab(self):
        self.search_bar_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.search_bar_frame.pack(pady=(5, 10), fill="x", anchor="s")
        self.search_bar = ctk.CTkEntry(self.search_bar_frame)
        self.search_bar.pack(padx=(5, 35), anchor="s", side="right")
        self.search_bar_option_menu_values = {"NOME SPESA": "NOME SPESA", "NOME FORNITORE" : "NOME FORNITORE", "CATEGORIA": "CATEGORIA",
                                              "NOME UTENTE": "NOME UTENTE", "CONTO": "CONTO"}
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

            if key == ExpenseController.ExpensesAggregateData.NUMERO_SPESE.value:
                global_info_unità_di_misura = ""
            elif key == ExpenseController.ExpensesAggregateData.TOT_SPESE.value:
                global_info_unità_di_misura = "€"

            title = ctk.CTkLabel(card, text=f"{key}", font=("Arial", 12), bg_color="#1F6AA5")
            amount = ctk.CTkLabel(card, text=f"{info} {global_info_unità_di_misura}", font=("Arial", 16))

            card.pack(side="left", anchor="w", padx=10, pady=(10, 5))
            title.pack(anchor="n", padx=10, pady=(10, 5), ipadx=7, ipady=5)
            amount.pack(anchor="s", padx=10, pady=5)

            # salvo i dati che potrebbero avere bisogno di configure successivamente
            self.amount_aggregate_labels[f"{key}"] = amount

        self.expenses_table_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.expenses_table_frame.pack(pady=(20, 0), padx=(10, 15), fill="x", anchor="n")

        self.table_headers = ["NOME", "FORNITORE", "NETTO", "LORDO", "CATEGORIA", "DATA", "DEDUCIBILE", "DEDUZIONE A\nCARICO DI", "CONTO\nCORRENTE"]

        for i, header in enumerate(self.table_headers):
            # crea il container
            column = ctk.CTkFrame(self.expenses_table_frame, fg_color="#333333")
            column.grid(row=0, column=i, sticky="nsew", padx=(0, 5), pady=5)

            # imposta peso e uniformità: tutte le colonne "col" si dividono equamente
            self.expenses_table_frame.grid_columnconfigure(i, weight=1, uniform="col")

            # la label riempie il suo container
            label = ctk.CTkLabel(column,
                                 text=header,
                                 font=("Arial", 14))
            label.pack(fill="both", expand=True, padx=5, pady=15)

        # Creazione del frame delle cards
        self.cards_frame = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")
        self.cards_frame.pack(padx=0, pady=10, fill="both", expand=True)

        self.add_expense_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.add_expense_frame.pack(padx=0, pady=(5, 20), fill="x")

        self.save_button = ctk.CTkButton(self.add_expense_frame, text="Aggiungi una spesa",
                                         command=self.open_add_expense_window)
        self.save_button.pack()

        for expense in self.expense_controller.retrieve_expenses_map_list(True):
            if expense:
                expense_id = expense[DBExpensesColumns.ID.value]
                name = expense[DBExpensesColumns.NAME.value]
                net_amount = expense[DBExpensesColumns.NET_AMOUNT.value]
                amount = expense[DBExpensesColumns.TOT_AMOUNT.value]
                supplier_id = expense[DBExpensesColumns.SUPPLIER_ID.value]
                supplier = self.supplier_controller.retrieve_supplier_map_by_id(supplier_id)
                supplier_name = supplier[DBSuppliersColumns.NAME.value]
                date = expense[DBExpensesColumns.DATE.value]
                category = expense[DBExpensesColumns.CATEGORY.value]
                deducibile = expense[DBExpensesColumns.DEDUCIBILE.value]
                user_id = expense[DBExpensesColumns.USER_ID_DEDUZIONE.value]
                if user_id:
                    user = self.user_controller.retrieve_user_map_by_id(user_id)
                    user_first = user[DBUsersColumns.FIRST_NAME.value]
                    user_second = user[DBUsersColumns.LAST_NAME.value]
                    user_name = user_first + " " + user_second
                else:
                    user_name = " ---- "
                account = self.account_controller.retrieve_account_map_by_id(expense[DBExpensesColumns.ACCOUNT_ID.value])
                account_name = account[DBAccountsColumns.NAME.value] if account else "conto non trovato"

                self.add_expense_card(expense_id, name, supplier_name, net_amount, amount, category, date, deducibile, user_name, account_name)

    def open_add_expense_window(self):
        self.add_expense_window = ctk.CTkToplevel(self)
        self.add_expense_window.title("Aggiungi Nuova Spesa")

        # Assicurati che la finestra rimanga sopra
        self.add_expense_window.lift()  # Porta la finestra sopra quella principale
        self.add_expense_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

        self.add_expense_window.geometry("550x700")

        self.expense_window_scrollableFrame = ctk.CTkScrollableFrame(self.add_expense_window)
        self.expense_window_scrollableFrame.pack(fill="both", expand=True)

        self.nome_spesa_string = "NOME SPESA"
        self.nome_conto_string = "CONTO"
        self.nome_utente_string = "QUALCUNO HA ANTICIPATO?"
        self.nome_fornitore_string = "NOME FORNITORE"
        self.aliquota_iva_string = "ALIQUOTA IVA"
        self.nome_fattura_string = "FATTURA ASSOCIATA"
        self.nome_utente_deduz_string = "DEDUZIONE A CARICO"

        self.entry_fields = {
            self.nome_fornitore_string: ctk.CTkOptionMenu,
            DBExpensesColumns.CATEGORY.value: ctk.CTkOptionMenu,
            DBExpensesColumns.NAME.value : ctk.CTkEntry,
            DBExpensesColumns.DATE.value: Calendar,
            DBExpensesColumns.DEDUCIBILE.value: ctk.CTkOptionMenu,
            self.nome_utente_deduz_string : ctk.CTkOptionMenu,
            self.aliquota_iva_string : ctk.CTkOptionMenu,
            DBExpensesColumns.TOT_AMOUNT.value: ctk.CTkEntry,
            self.nome_utente_string : ctk.CTkOptionMenu,
            self.nome_fattura_string : ctk.CTkOptionMenu,
            self.nome_conto_string: ctk.CTkOptionMenu,
        }

        self.error_fields = {
            DBExpensesColumns.NAME.value: ctk.CTkLabel,
            DBExpensesColumns.TOT_AMOUNT.value: ctk.CTkLabel,
        }

        self.expenses_widgets = {}
        self.error_labels = {}
        self.expenses_labels = {}

        # Creo i labels e i widgets
        for i, (label_text, widget_class) in enumerate(self.entry_fields.items()):
            # Etichetta
            label = ctk.CTkLabel(self.expense_window_scrollableFrame, text=label_text)
            # disegno i labels
            if i == 0 and label_text != self.nome_fattura_string and label_text != self.nome_utente_deduz_string:
                label.pack(pady=5)
            elif i != 0 and label_text != self.nome_fattura_string and label_text != self.nome_utente_deduz_string:
                label.pack(pady=(35, 0))

            self.expenses_labels[label_text] = label

            # creo i widgets
            if label_text == self.nome_fornitore_string:
                suppliers_map_list = self.supplier_controller.retrieve_suppliers_map_list()
                suppliers_name_list = [supplier[DBSuppliersColumns.NAME.value] for supplier in suppliers_map_list]
                reversed_suppliers = suppliers_name_list[::-1]
                widget = widget_class(self.expense_window_scrollableFrame,
                                      values=reversed_suppliers,
                                      command=lambda selected_value: self.autofill_expense_name(selected_value))

            elif label_text == self.aliquota_iva_string:
                #ottengo una lista di aliquote
                aliquote_list = [
                    self.fiscal_settings.aliquota_iva.aliquota_iva_ordinaria,
                    self.fiscal_settings.aliquota_iva.aliquota_iva_ridotta_1,
                    self.fiscal_settings.aliquota_iva.aliquota_iva_ridotta_2,
                    self.fiscal_settings.aliquota_iva.aliquota_iva_minima
                ]

                widget = widget_class(self.expense_window_scrollableFrame, values=[str(aliquota) for aliquota in aliquote_list])

            elif label_text == DBExpensesColumns.CATEGORY.value:
                widget = widget_class(self.expense_window_scrollableFrame,
                                      values=[value for key, value in self.catalogo_elenchi["expenses_category"]],
                                      command = lambda selected_value : self.expense_category_optionMenu_behaviour(selected_value))

            elif label_text == DBExpensesColumns.NAME.value:
                self.name_frame = ctk.CTkFrame(self.expense_window_scrollableFrame)
                self.name_frame.pack(pady=0, padx=0, fill="x", expand=True)
                first_part_name_label = ctk.CTkLabel(self.name_frame, text="bandur")
                first_part_name_label.pack(side=tk.LEFT, pady=5, padx=(10, 0))
                widget = widget_class(self.name_frame)

            elif label_text == DBExpensesColumns.DATE.value:
                widget = widget_class(self.expense_window_scrollableFrame, date_pattern=ViewUtils.date_pattern)

            elif label_text == DBExpensesColumns.DEDUCIBILE.value:
                widget = widget_class(self.expense_window_scrollableFrame,
                                      values=["Sì", "No"],
                                      command=lambda selected_value: self.toggle_user_deduzione(selected_value))
                widget.set("No")

            elif label_text == self.nome_utente_string:
                #recupero gli utenti
                users = self.user_controller.retrieve_users_map_list()
                widget = widget_class(self.expense_window_scrollableFrame,
                                      values=[" ----- "] + [user[DBUsersColumns.FIRST_NAME.value] + " " + user[DBUsersColumns.LAST_NAME.value] for user in users])

                widget.set(" ----- ")

            elif label_text == self.nome_utente_deduz_string:
                #recupero gli utenti
                users = self.user_controller.retrieve_users_map_list()
                widget = widget_class(self.expense_window_scrollableFrame,
                                      values=[user[DBUsersColumns.FIRST_NAME.value] + " " + user[DBUsersColumns.LAST_NAME.value] for user in users
                                              if user[DBUsersColumns.REGIME_FISCALE.value] == UserController.RegimeFiscale.ORDINARIO.value])

            elif label_text == self.nome_fattura_string:
                #recupero le fatture
                invoices = self.invoice_controller.retrieve_invoices_map_list()
                widget = widget_class(self.expense_window_scrollableFrame,
                                      values=["Fattura non ancora emessa"] + [invoice[DBInvoicesColumns.NUMERO_FATTURA.value] for invoice in invoices],
                                      command = lambda selected_value : self.linked_invoice_optionMenu_behaviour(selected_value))

                widget.set("Fattura non ancora emessa")

            elif label_text == self.nome_conto_string:
                # recupero i conti
                accounts = self.account_controller.retrieve_accounts_map_list()
                widget = widget_class(self.expense_window_scrollableFrame,
                                      values=[account[DBAccountsColumns.NAME.value] for account in accounts])

            else:
                widget = widget_class(self.expense_window_scrollableFrame)

            if label_text != self.nome_fattura_string and label_text != self.nome_utente_deduz_string:
                widget.pack(pady=5, padx=10, fill="x", expand=True)

            self.expenses_widgets[label_text] = widget

            if self.error_fields.get(label_text) is not None:
                error_label = ctk.CTkLabel(self.expense_window_scrollableFrame, text="")
                error_label.pack(pady=(0, 15))
                self.error_labels[label_text] = error_label

        self.linked_invoice_warning_label = ctk.CTkLabel(self.expense_window_scrollableFrame, text="")

        # Bottone per salvare
        self.save_button = ctk.CTkButton(
            self.expense_window_scrollableFrame,
            text="Salva Spesa",
            command=self.save_expense_data
        )
        self.save_button.pack(pady=(50, 15))

        suppliers_list = self.supplier_controller.retrieve_suppliers_map_list()
        self.autofill_expense_name(suppliers_list[len(suppliers_list) - 1][DBSuppliersColumns.NAME.value] if
                                   len(suppliers_list) > 0 else "    ")

        # Aggiungi validazione agli eventi di perdita del focus
        self.expenses_widgets[DBExpensesColumns.NAME.value].bind("<FocusOut>",
            lambda event: ViewUtils.validate_entry(
                self.expenses_widgets[
                    DBExpensesColumns.NAME.value],
                lambda val: val.strip() != "",
                self.error_labels[
                    DBExpensesColumns.NAME.value],
                "Il campo non può essere vuoto."
            ))

        self.expenses_widgets[DBExpensesColumns.TOT_AMOUNT.value].bind("<FocusOut>",
            lambda event: ViewUtils.validate_entry(
              self.expenses_widgets[
                  DBExpensesColumns.TOT_AMOUNT.value],
              lambda val: re.fullmatch(
                  r"^\d+(\.\d{2})?$",
                  val.strip()) is not None,
              self.error_labels[
                  DBExpensesColumns.TOT_AMOUNT.value],
              "Inserimento non valido: inserire un numero monetario con due cifre decimali (es. 123.45)"
            ))

    def save_expense_data(self):
        expense_data = {}

        # riempi il dizionario con i dati dei widgets primari
        for label_text, widget in self.expenses_widgets.items():
            if isinstance(widget, ctk.CTkEntry) or isinstance(widget, ctk.CTkOptionMenu):
                expense_data[label_text] = widget.get().strip()
            elif isinstance(widget, Calendar):
                expense_data[label_text] = widget.get_date()
            elif isinstance(widget, ctk.CTkTextbox):
                expense_data[label_text] = widget.get("1.0", "end-1c").strip()  # Recupera il testo dal Textbox

        #filtro i dati
        category_dict = dict(self.catalogo_elenchi["expenses_category"])
        if str(self.expenses_widgets[DBExpensesColumns.CATEGORY.value].get()) != str(category_dict.get("PRODUCTION_EXPENSE")):
            expense_data.pop(self.nome_fattura_string)

        if self.expenses_widgets[DBExpensesColumns.DEDUCIBILE.value].get() == "No":
            expense_data[self.nome_utente_deduz_string] = None

        # chiamata al controller per salvare i dati
        success, message = self.expense_controller.save_expense(expense_data)

        if success:
            self.update_controller.on_adding_expense()

            # prendo l'ID della sesa appena creata
            expense_map = self.expense_controller.retrieve_last_expense_insert_map()
            print(f"Spesa {expense_data[DBExpensesColumns.NAME.value]} salvata con successo")

            supplier_name = self.supplier_controller.retrieve_supplier_map_by_id(expense_map[DBExpensesColumns.SUPPLIER_ID.value])[
                DBSuppliersColumns.NAME.value]

            user= self.user_controller.retrieve_user_map_by_id(expense_map[DBExpensesColumns.USER_ID_DEDUZIONE.value])
            if user is not None:
                user_first = user[DBUsersColumns.FIRST_NAME.value]
                user_last = user[DBUsersColumns.LAST_NAME.value]
                user_full = user_first + " " + user_last
            else:
                user_full = "----"

            account_name = self.account_controller.retrieve_account_map_by_id(expense_map[DBExpensesColumns.ACCOUNT_ID.value])[
                DBAccountsColumns.NAME.value]


            self.add_expense_card(
                expense_map[DBExpensesColumns.ID.value],
                expense_map[DBExpensesColumns.NAME.value],
                supplier_name,
                expense_map[DBExpensesColumns.NET_AMOUNT.value],
                expense_map[DBExpensesColumns.TOT_AMOUNT.value],
                expense_map[DBExpensesColumns.CATEGORY.value],
                expense_map[DBExpensesColumns.DATE.value],
                expense_map[DBExpensesColumns.DEDUCIBILE.value],
                user_full,
                account_name
            )

            self.clear_class_variable()
            self.add_expense_window.destroy()
            self.update_global_infos()
        else:
            print(message)
            ViewUtils.show_error_popup(self.add_expense_window, "ERRORE", message)

    def filter_cards(self, event):
        """Filtra le card in base al testo della barra di ricerca e al tipo di filtro scelto."""
        search_text = self.search_bar.get().lower()
        search_type = self.search_bar_optionMenu.get()

        # Mappatura: ogni chiave associa una tupla (indice, classe_attesa) del widget da cui prelevare il testo
        filter_mapping = {
            "NOME SPESA": (0, ctk.CTkButton),  # Bottone
            "NOME FORNITORE": (1, ctk.CTkLabel),
            "CATEGORIA": (4, ctk.CTkLabel),
            "NOME UTENTE": (7, ctk.CTkLabel),
            "CONTO": (8, ctk.CTkLabel)
        }

        mapping = filter_mapping.get(search_type)

        # Prima rimuovo tutte le card dal container per avere un layout pulito
        for card in self.expenses_card_list.values():
            card.pack_forget()

        # Se il tipo di ricerca non è riconosciuto, riposiziona tutte le card nell'ordine originale
        if mapping is None:
            for card in self.expenses_card_list.values():
                card.pack(pady=10, padx=10, fill="x", expand=True)
            return

        idx, expected_class = mapping

        # Itera sulle card nell’ordine originale (grazie al dizionario ordinato)
        for key, card in self.expenses_card_list.items():
            children = card.winfo_children()  # Lista dei widget figli
            widget_text = ""
            if len(children) > idx and isinstance(children[idx], expected_class):
                widget_text = children[idx].cget("text")
            # Se il testo (in lowercase) contiene il testo di ricerca, riposiziona la card
            if search_text in widget_text.lower():
                card.pack(pady=10, padx=10, fill="x", expand=True)

    def add_expense_card(self, expense_id, name, supplier_name, net_amount, amount, category, date, deducibile, user_name, account_name):
        card = ctk.CTkFrame(self.cards_frame, fg_color="dimgray")
        card.pack(pady=10, padx=8, fill="x", expand=True)  # Spaziatura tra le card

        # Dati da visualizzare nella card
        data = [name, supplier_name, round(net_amount, 2), round(amount, 2), ViewUtils.split_string_by_length(category, 15),  ViewUtils.invert_data_string(date), deducibile,
                user_name, account_name]
        units = ["", "", "€", "€", "", "", "", "", ""]
        n_cols = len(data)  # 8 colonne totali

        # Configura il grid della card: 1 riga, n_cols colonne uguali
        for c in range(n_cols):
            card.grid_columnconfigure(c, weight=1, uniform="clientcol")

        card.grid_rowconfigure(0, weight=1)

        # 0) Bottone "nome"
        btn = ctk.CTkButton(
            card,
            text=name,
            command=lambda eid=expense_id: self.open_expense_detail_tab(eid)
        )
        btn.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        # 1..7) Le altre colonne
        for idx, val in enumerate(data[1:], start=1):
            text = f"{val} {units[idx]}"
            lbl = ctk.CTkLabel(card, text=text, font=("Arial", 14))
            lbl.grid(row=0, column=idx, sticky="nsew", padx=5, pady=10)

        # Salva la card per eventuale successivo accesso
        self.expenses_card_list[name] = card

    def populate_global_infos(self):
        numero_spese = self.expense_controller.count_expenses(True)
        totale_spese = round(self.expense_controller.calculate_tot_expenses(), 2)
        self.global_infos[f"{ExpenseController.ExpensesAggregateData.NUMERO_SPESE.value}"] = numero_spese
        self.global_infos[f"{ExpenseController.ExpensesAggregateData.TOT_SPESE.value}"] = f"{totale_spese:.2f}"

    def update_global_infos(self):
        self.populate_global_infos()
        for key, label in self.amount_aggregate_labels.items():
            new_value = self.global_infos.get(key, "")
            label.configure(text=str(new_value) + " " + self.aggregate_UOM[key])

    def autofill_expense_name(self, selected_value):
        self.name_frame.winfo_children()[0].configure(
            text=f"{selected_value} - ")

    def expense_category_optionMenu_behaviour(self, selected_value):
        sector_dict = dict(self.catalogo_elenchi["expenses_category"])
        if selected_value == sector_dict.get("ADD_CATEGORY"):
            self.open_add_expenses_category()
        self.toggle_linked_invoice_selection(selected_value, sector_dict)

    def open_add_expenses_category(self):
        self.add_category_window = ctk.CTkToplevel(self)
        self.add_category_window.title("Aggiungi una nuova categoria di spesa")

        # Assicurati che la finestra rimanga sopra
        self.add_category_window.lift()  # Porta la finestra sopra quella principale
        self.add_category_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

        self.add_category_window.geometry("400x300")

        self.expenses_category_window_Frame = ctk.CTkFrame(self.add_category_window)
        self.expenses_category_window_Frame.pack(fill="both", expand=True)

        ctk.CTkLabel(self.expenses_category_window_Frame, text="Aggiungi una categoria di spesa alla lista\nsepara parole diverse solo tramite spazio").pack(padx=10, pady=(25, 0))

        self.add_category_entry = ctk.CTkEntry(self.expenses_category_window_Frame)
        self.add_category_entry.pack(padx=10, pady=5, fill="x", expand=True)

        ctk.CTkButton(self.expenses_category_window_Frame, text="Aggiungi settore", command=self.save_expenses_category).pack(padx=10, pady=(15, 10))

    def toggle_linked_invoice_selection(self, selected_value, dictionary):
        if selected_value == dictionary.get("PRODUCTION_EXPENSE"):
            self.save_button.pack_forget()
            self.expenses_widgets[self.nome_conto_string].pack_forget()
            self.expenses_labels[self.nome_conto_string].pack_forget()
            self.expenses_widgets[self.nome_utente_string].pack_forget()
            self.expenses_labels[self.nome_utente_string].pack_forget()
            self.expenses_widgets[DBExpensesColumns.TOT_AMOUNT.value].pack_forget()
            self.expenses_labels[DBExpensesColumns.TOT_AMOUNT.value].pack_forget()

            self.expenses_labels[self.nome_fattura_string].pack(pady=(35, 0))
            self.expenses_widgets[self.nome_fattura_string].pack(pady=5, padx=10, fill="x", expand=True)
            self.linked_invoice_warning_label.pack(pady=(0, 15))
            self.expenses_labels[DBExpensesColumns.TOT_AMOUNT.value].pack(pady=(35, 0))
            self.expenses_widgets[DBExpensesColumns.TOT_AMOUNT.value].pack(pady=5, padx=10, fill="x", expand=True)
            self.expenses_labels[self.nome_utente_string].pack(pady=(35, 0))
            self.expenses_widgets[self.nome_utente_string].pack(pady=5, padx=10, fill="x", expand=True)
            self.expenses_labels[self.nome_conto_string].pack(pady=(35, 0))
            self.expenses_widgets[self.nome_conto_string].pack(pady=5, padx=10, fill="x", expand=True)
            self.save_button.pack(pady=(50, 15))

        else:
            self.expenses_labels[self.nome_fattura_string].pack_forget()
            self.expenses_widgets[self.nome_fattura_string].pack_forget()
            self.linked_invoice_warning_label.pack_forget()

    def toggle_user_deduzione(self, selected_value):
        # Manteniamo una lista separata per l'ordine delle chiavi
        if not hasattr(self, 'ordered_expenses_keys'):
            self.ordered_expenses_keys = list(self.expenses_widgets.keys())

        # Indice di partenza (n=6)
        n = 6

        if selected_value == "Sì":
            try:
                # Prendiamo le chiavi dall'indice n in poi
                keys_to_manage = self.ordered_expenses_keys[n:]
            except IndexError:
                keys_to_manage = []

            # Nascondi i widget
            for key in reversed(keys_to_manage):
                self.expenses_labels[key].pack_forget()
                self.expenses_widgets[key].pack_forget()
            self.error_labels[DBExpensesColumns.TOT_AMOUNT.value].pack_forget()
            self.save_button.pack_forget()


            # Mostra il widget specifico della deduzione
            ded_key = self.nome_utente_deduz_string
            self.expenses_labels[ded_key].pack(pady=(35, 0))
            self.expenses_widgets[ded_key].pack(pady=5, padx=10, fill="x", expand=True)

            # Ripristina gli altri widget nell'ordine originale
            for key in keys_to_manage:
                self.expenses_labels[key].pack(pady=(35, 0))
                self.expenses_widgets[key].pack(pady=5, padx=10, fill="x", expand=True)
                if key == DBExpensesColumns.TOT_AMOUNT.value:
                    self.error_labels[DBExpensesColumns.TOT_AMOUNT.value].pack(pady=(0, 15))
                a = self.expenses_widgets[DBExpensesColumns.CATEGORY.value].get()
                b = dict(self.catalogo_elenchi["expenses_category"])
                if key == self.nome_fattura_string and a != b["PRODUCTION_EXPENSE"]:
                    self.expenses_labels[key].pack_forget()
                    self.expenses_widgets[key].pack_forget()
            self.save_button.pack(pady=(50, 15))

        elif selected_value == "No":
            # Nascondi solo il widget della deduzione
            ded_key = self.nome_utente_deduz_string
            self.expenses_labels[ded_key].pack_forget()
            self.expenses_widgets[ded_key].pack_forget()

    def linked_invoice_optionMenu_behaviour(self, selected_value):
        invoice = self.invoice_controller.retrieve_invoice_map_by_name(selected_value)
        if invoice:
            invoice_id = invoice[DBInvoicesColumns.ID.value]
            rimborso = invoice[DBInvoicesColumns.RIMBORSI.value]

            self.autofill_tot_amount(rimborso)
            self.invoice_production_expense_amount_check(invoice_id)
        else:
            self.expenses_widgets[DBExpensesColumns.TOT_AMOUNT.value].delete(0, tk.END)
            self.linked_invoice_warning_label.configure(text="")

    def autofill_tot_amount(self, amount):
        self.expenses_widgets[DBExpensesColumns.TOT_AMOUNT.value].delete(0, tk.END)
        self.expenses_widgets[DBExpensesColumns.TOT_AMOUNT.value].insert(0, f"{amount:.2f}")

    def invoice_production_expense_amount_check(self, invoice_id):
        check, linked_expenses_tot = self.invoice_controller.check_linked_tot_expenses(invoice_id)
        if check:
            if linked_expenses_tot > 0:
                self.linked_invoice_warning_label.configure(text="Per questa fattura risultano già emesse spese di produzione pari al totale dei rimborsi", text_color="#e39e27")
            else:
                self.linked_invoice_warning_label.configure(text="Questa fattura presenta totale rimborsi pari a 0€", text_color="#e39e27")
        else:
            self.linked_invoice_warning_label.configure(text="")

    def save_expenses_category(self):
        new_category = self.add_category_entry.get()
        new_category_key = ControllerUtils.normalize_string_for_key(new_category)
        try:
            self.config_manager.update_list_field("expenses_category", new_category_key, new_category, "update")
        except Exception as e:
            ViewUtils.show_error_popup(self.add_category_window, "Errore",
                                       f"Impossibile aggiungere la nuova categoria: {str(e)}")
            return

        self.expenses_widgets[DBExpensesColumns.CATEGORY.value].set(new_category)
        self.add_category_window.destroy()

    def clear_class_variable(self):
        self.expenses_widgets.clear()
        self.expenses_labels.clear()

    def open_modify_expense(self, expense_id):
        return





class ExpenseDetailView(ctk.CTkFrame):
    def __init__(self, parent, back_callback, invoice_controller, user_controller, account_controller, expense_controller, supplier_controller, update_controller, db_model, event_bus, catalogo_elenchi):
        super().__init__(parent)
        self.invoice_controller = invoice_controller
        self.user_controller = user_controller
        self.account_controller = account_controller
        self.expense_controller = expense_controller
        self.supplier_controller = supplier_controller
        self.db_model = db_model
        self.back_callback = back_callback
        self.update_controller = update_controller
        self.event_bus = event_bus
        self.current_expense_id = None
        self.catalogo_elenchi = catalogo_elenchi
        self.parent = parent

        self.configure(fg_color="transparent")



        # Widgets persistenti (vanno creati una volta sola)
        self.head_frame = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.back_button = ctk.CTkButton(
            self.head_frame,
            text="Elenco Spese",
            command=self._cleanup_and_go_back
        )
        self.title_label = ctk.CTkLabel(self.head_frame, font=("Arial", 22, "bold"))

        self.expense_info_widgets: dict[str, ctk.CTkEntry | ctk.CTkOptionMenu] = {}

        self.nome_conto_string = "CONTO"
        self.nome_user_deduzione_string = "UTENTE DEDUZIONE"
        self.nome_user_anticipo_string = "UTENTE ANTICIPO"
        self.nome_fattura_string = "FATTURA ASSOCIATA"
        self.nome_fornitore_string = "FORNITORE"

        # Container per i contenuti dinamici
        self.content_frame = ctk.CTkScrollableFrame(self)

        self.switch_modify = ctk.CTkSwitch(self.head_frame, text="Abilita la modifica", command=lambda: self.toggle_edit(self.content_frame))

        # Layout iniziale
        self._setup_base_layout()

    def _setup_base_layout(self):
        """Inizializza la struttura base del layout"""
        self.head_frame.pack(fill="x", pady=5, padx=5)
        self.back_button.pack(anchor="w", side="left", pady=10, padx=10)
        self.title_label.pack(anchor="c", side="left", fill="x", expand=True, pady=10)
        self.switch_modify.pack(anchor="e", side="left", pady=10, padx=10)
        self.content_frame.pack(fill="both", expand=True, pady=20, padx=20)

    def create_detail_tab(self, expense_id):
        """Ricrea la vista dettaglio per una spesa specifica"""
        self.current_expense_id = expense_id

        # 1. Pulizia dei widget precedenti
        self._clear_content()

        # 2. Caricamento dati
        self.expense = self.expense_controller.retrieve_expense_map_by_id(expense_id)

        # prendo il nome del conto:
        id_conto = self.expense[DBExpensesColumns.ACCOUNT_ID.value]
        conto = self.account_controller.retrieve_account_map_by_id(id_conto)
        if conto is not None:
            nome_conto = conto[DBAccountsColumns.NAME.value]
            self.expense[self.nome_conto_string] = nome_conto

        # prendo il nome del fornitore
        id_supplier = self.expense[DBExpensesColumns.SUPPLIER_ID.value]
        supplier = self.supplier_controller.retrieve_supplier_map_by_id(id_supplier)
        if supplier is not None:
            nome_supplier = supplier[DBSuppliersColumns.NAME.value]
            self.expense[self.nome_fornitore_string] = nome_supplier

        # prendo il nome dell'utente che deduce
        id_user = self.expense[DBExpensesColumns.USER_ID_DEDUZIONE.value]
        user = self.user_controller.retrieve_user_map_by_id(id_user)
        if user is not None:
            nome_user = user[DBUsersColumns.FIRST_NAME.value] + " " + user[DBUsersColumns.LAST_NAME.value]
            self.expense[self.nome_user_deduzione_string] = nome_user
        else:
            self.expense[self.nome_user_deduzione_string] = None

        # prendo il nome dell'utente che anticipa
        id_user = self.expense[DBExpensesColumns.USER_ID_ANTICIPO.value]
        user = self.user_controller.retrieve_user_map_by_id(id_user)
        if user is not None:
            nome_user = user[DBUsersColumns.FIRST_NAME.value] + " " + user[DBUsersColumns.LAST_NAME.value]
            self.expense[self.nome_user_anticipo_string] = nome_user

        # prendo il nome della fattura associata
        id_fattura = self.expense[DBExpensesColumns.LINKED_INVOICE_ID.value]
        fattura = self.invoice_controller.retrieve_invoice_map_by_id(id_fattura)
        if fattura is not None:
            nome_fattura = fattura[DBInvoicesColumns.NUMERO_FATTURA.value]
            self.expense[self.nome_fattura_string] = nome_fattura

        # 3. Aggiornamento elementi persistenti
        self.title_label.configure(
            text=f"{self.expense[DBExpensesColumns.NAME.value]}")

        # 4. Creazione contenuti dinamici
        self._create_expense_info_section(self.expense)
        self.toggle_edit(self.content_frame)

        self.wrapper_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.wrapper_frame.pack(padx=15, pady=(90, 0), fill="both", expand=True)
        self.wrapper_frame2 = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.wrapper_frame2.pack(padx=15, pady=(90, 90), fill="both", expand=True)

        #self._create_payments_history()
        #self._create_production_expenses_history()

    def _create_expense_info_section(self, expense_data):
        # Campi derivati per le spese
        self.derived_fields_expenses = {
            # Potresti aggiungere campi calcolati qui se necessario
        }

        self.entry_fields_expenses = {
            # Dati Generali
            DBExpensesColumns.NAME.value: {
                "type": ctk.CTkEntry,
                "label": "Nome Spesa",
                "section": "Dati Generali"
            },
            DBExpensesColumns.DATE.value: {
                "type": Calendar,
                "label": "Data Spesa",
                "section": "Dati Generali"
            },

            # Dati Fiscali
            DBExpensesColumns.CATEGORY.value: {
                "type": ctk.CTkOptionMenu,
                "label": "Categoria",
                "section": "Dati Fiscali",
                "values": [item[1] for item in self.catalogo_elenchi["expenses_category"]]
            },
            DBExpensesColumns.NET_AMOUNT.value: {
                "type": ctk.CTkEntry,
                "label": "Importo Netto (€)",
                "section": "Dati Fiscali"
            },
            DBExpensesColumns.IVA_AMOUNT.value: {
                "type": ctk.CTkEntry,
                "label": "Importo IVA (€)",
                "section": "Dati Fiscali"
            },
            DBExpensesColumns.TOT_AMOUNT.value: {
                "type": ctk.CTkEntry,
                "label": "Importo Totale (€)",
                "section": "Dati Fiscali"
            },
            DBExpensesColumns.DEDUCIBILE.value: {
                "type": ctk.CTkOptionMenu,
                "label": "Deducibile",
                "section": "Dati Fiscali",
                "values": ["Sì", "No", "Parziale"]
            },

            # Collegamenti
            self.nome_fornitore_string: {
                "type": ctk.CTkOptionMenu,
                "label": "Fornitore",
                "section": "Collegamenti",
                "values": [s[DBSuppliersColumns.NAME.value] for s in
                           self.supplier_controller.retrieve_suppliers_map_list()]
            },
            self.nome_user_deduzione_string: {
                "type": ctk.CTkOptionMenu,
                "label": "Utente Deduzione",
                "section": "Collegamenti",
                "values": [f"{u[DBUsersColumns.FIRST_NAME.value]} {u[DBUsersColumns.LAST_NAME.value]}"
                           for u in self.user_controller.retrieve_users_map_list()]
            },
            self.nome_user_anticipo_string: {
                "type": ctk.CTkOptionMenu,
                "label": "Utente Anticipo",
                "section": "Collegamenti",
                "values": [f"{u[DBUsersColumns.FIRST_NAME.value]} {u[DBUsersColumns.LAST_NAME.value]}"
                           for u in self.user_controller.retrieve_users_map_list()]
            },
            self.nome_fattura_string: {
                "type": ctk.CTkOptionMenu,
                "label": "Fattura Associata",
                "section": "Collegamenti",
                "values": [f"{i[DBInvoicesColumns.NUMERO_FATTURA.value]}"
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
            DBExpensesColumns.created_at.value: {
                "type": ctk.CTkLabel,
                "label": "Data Creazione",
                "section": "Note"
            },
            DBExpensesColumns.updated_at.value: {
                "type": ctk.CTkLabel,
                "label": "Ultimo Aggiornamento",
                "section": "Note"
            }
        }

        self.error_fields_expenses = {
            DBExpensesColumns.NET_AMOUNT.value: "Valore numerico con massimo 2 decimali",
            DBExpensesColumns.IVA_AMOUNT.value: "Valore numerico con massimo 2 decimali",
            DBExpensesColumns.TOT_AMOUNT.value: "Valore numerico con massimo 2 decimali",
            DBExpensesColumns.DATE.value: "Data obbligatoria",
            DBExpensesColumns.NAME.value: "Nome obbligatorio"

        }

        validation_rules = {
            DBExpensesColumns.NET_AMOUNT.value: (
                lambda val: re.fullmatch(r"^\d+(\.\d{1,2})?$", val),
                "Formato valido: 1234.56"
            ),
            DBExpensesColumns.IVA_AMOUNT.value: (
                lambda val: re.fullmatch(r"^\d+(\.\d{1,2})?$", val),
                "Formato valido: 1234.56"
            ),
            DBExpensesColumns.TOT_AMOUNT.value: (
                lambda val: re.fullmatch(r"^\d+(\.\d{1,2})?$", val),
                "Formato valido: 1234.56"
            ),
            DBExpensesColumns.DATE.value: (
                lambda val: val.strip() != "",
                "Campo obbligatorio"
            ),
            DBExpensesColumns.NAME.value: (
                lambda val: val.strip() != "",
                "Campo obbligatorio"
            )
        }

        # Inizializzazione strutture dati
        self.expense_info_widgets = {}
        self.expense_info_labels = {}
        self.error_labels_expenses = {}
        sections = {}

        if expense_data[DBExpensesColumns.RICORRENTE.value]:
            self.entry_fields_expenses.pop(DBExpensesColumns.NAME.value)

        expense_name = expense_data[DBExpensesColumns.NAME.value]
        warning = self.parent.cards_warnings.get(expense_name)
        border_color = "#2659ab" if warning is None else "#fcba03"

        # Warning frame
        self.warning_frame = ctk.CTkFrame(self.content_frame, border_width=2, border_color=border_color)
        self.toggle_warning_frame(expense_data[DBExpensesColumns.NAME.value])
        ctk.CTkLabel(self.warning_frame, text=warning if warning is not None else "", font=("Arial", 16)).pack(padx=30,
                                                                                                               pady=(
                                                                                                               20, 20),
                                                                                                               side="left")
        self.remove_warning_btn = ctk.CTkButton(self.warning_frame, text="OK, è tutto in ordine",
                                                command=lambda: self.remove_warning(expense_name))
        self.remove_warning_btn.pack(padx=30, pady=(20, 20), side="right")

        # Creazione frame principale
        self.info_frame = ctk.CTkFrame(self.content_frame, border_width=2, border_color=border_color)
        self.info_frame.pack(fill="both", expand=True, pady=(5, 10), padx=(5, 25))

        # Configurazione griglia a 2 colonne
        self.info_frame.grid_columnconfigure(0, weight=1, uniform="col")
        self.info_frame.grid_columnconfigure(1, weight=1, uniform="col")

        # Sezioni organizzate per colonne
        sections_order = [
            "Dati Generali",
            "Dati Fiscali",
            "Collegamenti",
            "Note"
        ]

        # Creazione frame sezioni
        for i, section_name in enumerate(sections_order):
            frame = ctk.CTkFrame(self.info_frame)
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
        for field, config in self.entry_fields_expenses.items():
            section = sections[config["section"]]
            frame = section["frame"]
            row = section["row"]

            # Creazione label
            lbl = ctk.CTkLabel(frame, text=config["label"] + ":")
            self.expense_info_labels[field] = lbl
            lbl.grid(row=row, column=0, sticky="w", padx=(15, 5), pady=(5, 5))

            # Creazione widget
            if config["type"] == ctk.CTkLabel:
                value = str(expense_data.get(field, ""))
                widget = config["type"](frame, text=value)
                widget.grid(row=row, column=1, sticky="w", padx=(5, 15), pady=(5, 5))
            else:
                if config["type"] == ctk.CTkOptionMenu:
                    widget = config["type"](frame, values=config.get("values", []))

                    # Imposta il valore corrente per il fornitore
                    if field == self.nome_fornitore_string:
                        widget.set(expense_data.get(self.nome_fornitore_string, ""))

                    # Imposta il valore corrente per l'utente che deduce
                    elif field == self.nome_user_deduzione_string:
                        name = expense_data.get(self.nome_user_deduzione_string, "")
                        widget.set(name)

                    # Imposta il valore corrente per l'utente che ha anticipato
                    elif field == self.nome_user_anticipo_string:
                        widget.set(expense_data.get(self.nome_user_anticipo_string, ""))

                    # Imposta il valore corrente per la fattura associata
                    elif field == self.nome_fattura_string:
                        widget.set(expense_data.get(self.nome_fattura_string, ""))

                    # Imposta il valore corrente per il conto
                    elif field == self.nome_conto_string:
                        widget.set(expense_data.get(self.nome_conto_string, ""))

                    # Imposta il valore corrente per la categoria
                    elif field == DBExpensesColumns.CATEGORY.value:
                        # Trova la descrizione corrispondente alla chiave
                        category_key = expense_data.get(field, "")
                        category_desc = next(
                            (desc for key, desc in self.catalogo_elenchi["expenses_category"] if key == category_key),
                            category_key)
                        widget.set(category_desc)

                    else:
                        value = expense_data.get(field, config.get("values", [""])[0])
                        try:
                            value = round(float(value), 2)
                        except ValueError:
                            value = value
                        widget.set(value)

                elif config["type"] == Calendar:
                    widget = config["type"](frame, date_pattern=ViewUtils.date_pattern)
                    value = expense_data.get(field, "")
                    widget.selection_set(str(value)) if value else widget.selection_set(datetime.today())
                else:
                    widget = config["type"](frame)
                    value = str(expense_data.get(field, ""))
                    widget.insert(0, value)

                widget.grid(row=row, column=1, sticky="ew", padx=(5, 15), pady=(5, 5))

            self.expense_info_widgets[field] = widget

            # Gestione validazione
            if field in validation_rules:
                validation_func, error_message = validation_rules[field]

                error_lbl = ctk.CTkLabel(frame, text="", text_color="#e8e5dc")
                error_lbl.grid(row=row + 1, column=1, sticky="w", padx=5, pady=(0, 10))
                self.error_labels_expenses[field] = error_lbl

                widget.bind("<FocusOut>",
                            lambda e, w=widget, vl=validation_func, el=error_lbl, em=error_message:
                            ViewUtils.validate_entry(w, vl, el, em))

                section["row"] += 2
            else:
                section["row"] += 1


        #aggiungo le callback toggle agli optionMenu
        self.expense_info_widgets[DBExpensesColumns.CATEGORY.value].configure(command=lambda selected_value : self.expense_category_optionMenu_behaviour(selected_value))
        self.expense_info_widgets[DBExpensesColumns.DEDUCIBILE.value].configure(command=lambda selected_value : self.toggle_user_deduzione(selected_value))

        if self.expense_info_widgets[DBExpensesColumns.DEDUCIBILE.value].get() == "No":
            self.expense_info_widgets[self.nome_user_deduzione_string].set("")

        # Frame per i bottoni
        buttons_frame = ctk.CTkFrame(self.info_frame, fg_color="#2b2b2b")
        buttons_frame.grid(row=2, column=0, columnspan=2, pady=(5, 15), padx=20, sticky="WE")

        # Bottone Salva
        self.save_info_btn = ctk.CTkButton(buttons_frame, text="Salva Spesa", command=self.save_expense_mod)
        self.save_info_btn.pack(padx=(400, 10), pady=(20, 20), side="left")

        # Bottone Elimina
        self.delete_btn = ctk.CTkButton(buttons_frame, text="Elimina Spesa",
                                        fg_color="#8B0000", hover_color="#A52A2A",
                                        command=self.delete_expense)
        self.delete_btn.pack(padx=10, pady=(20, 20), side="right", anchor="e")

    def delete_expense(self):
        return

    def save_expense_mod(self):
        return

    def toggle_warning_frame(self, expense_name):
        return

    def remove_warning(self):
        return

    def toggle_edit(self, parent):
        """
        Abilita o disabilita la modifica dei widget nella finestra di modifica utente.
        """
        # Determina lo stato (abilitato/disabilitato) in base al valore dello switch
        state = ctk.NORMAL if self.switch_modify.get() else ctk.DISABLED

        # Cambia anche lo stato del pulsante Salva
        self.save_info_btn.configure(state=state)
        self.delete_btn.configure(state=state)
        self.remove_warning_btn.configure(state=state)

        expense_category = self.expense_info_widgets[DBExpensesColumns.CATEGORY.value].get()

        for w in parent.winfo_children():
            # se è un Entry
            if isinstance(w, ctk.CTkEntry):
                w.configure(state=state, text_color="#636363" if state == ctk.DISABLED else "#c2c2c2")
            # se è un OptionMenu
            elif isinstance(w, ctk.CTkOptionMenu):
                w.configure(state=state)
                if w == self.expense_info_widgets[self.nome_fattura_string] and expense_category != dict(self.catalogo_elenchi["expenses_category"]).get("PRODUCTION_EXPENSE"):
                    w.configure(state=tk.DISABLED)
            elif isinstance(w, Calendar):
                w.configure(state=state)
            # se è un Frame/container, scendi ricorsivamente
            elif isinstance(w, (ctk.CTkFrame, ctk.CTkScrollableFrame, ctk.CTkToplevel)):
                self.toggle_edit(w)

    def expense_category_optionMenu_behaviour(self, selected_value):
        sector_dict = dict(self.catalogo_elenchi["expenses_category"])
        if selected_value == sector_dict.get("ADD_CATEGORY"):
            self.open_add_expenses_category()
        self.toggle_linked_invoice_selection(selected_value, sector_dict)

    def toggle_linked_invoice_selection(self, selected_value, dictionary):
        if selected_value == dictionary.get("PRODUCTION_EXPENSE"):
            self.expense_info_widgets[self.nome_fattura_string].configure(state=tk.NORMAL)
        else:
            self.expense_info_widgets[self.nome_fattura_string].configure(state=tk.DISABLED)

    def toggle_user_deduzione(self, selected_value):
        user_deduzione = self.expense[self.nome_user_deduzione_string]
        if selected_value == "Sì":
            self.expense_info_widgets[self.nome_user_deduzione_string].configure(state=tk.NORMAL)
            if user_deduzione is not None:
                self.expense_info_widgets[self.nome_user_deduzione_string].set(user_deduzione)
            else:
                primo_utente = self.user_controller.retrieve_users_map_list()[0]
                nuovo_nome_utente = primo_utente[DBUsersColumns.FIRST_NAME.value] + " " + primo_utente[DBUsersColumns.LAST_NAME.value]
                self.expense_info_widgets[self.nome_user_deduzione_string].set(nuovo_nome_utente)

        elif selected_value == "No":
            self.expense_info_widgets[self.nome_user_deduzione_string].configure(state=tk.DISABLED)
            self.expense_info_widgets[self.nome_user_deduzione_string].set("")


    def open_add_expenses_category(self):
        self.add_category_window = ctk.CTkToplevel(self)
        self.add_category_window.title("Aggiungi una nuova categoria di spesa")

        # Assicurati che la finestra rimanga sopra
        self.add_category_window.lift()  # Porta la finestra sopra quella principale
        self.add_category_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

        self.add_category_window.geometry("400x300")

        self.expenses_category_window_Frame = ctk.CTkFrame(self.add_category_window)
        self.expenses_category_window_Frame.pack(fill="both", expand=True)

        ctk.CTkLabel(self.expenses_category_window_Frame, text="Aggiungi una categoria di spesa alla lista\nsepara parole diverse solo tramite spazio").pack(padx=10, pady=(25, 0))

        self.add_category_entry = ctk.CTkEntry(self.expenses_category_window_Frame)
        self.add_category_entry.pack(padx=10, pady=5, fill="x", expand=True)

        ctk.CTkButton(self.expenses_category_window_Frame, text="Aggiungi settore", command=self.save_expenses_category).pack(padx=10, pady=(15, 10))

    def save_expenses_category(self):
        new_category = self.add_category_entry.get()
        new_category_key = ControllerUtils.normalize_string_for_key(new_category)
        try:
            self.parent.config_manager.update_list_field("expenses_category", new_category_key, new_category, "update")
        except Exception as e:
            ViewUtils.show_error_popup(self.add_category_window, "Errore",
                                       f"Impossibile aggiungere la nuova categoria: {str(e)}")
            return

        self.expense_info_widgets[DBExpensesColumns.CATEGORY.value].set(new_category)
        self.add_category_window.destroy()

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

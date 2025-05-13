import customtkinter as ctk
import tkinter as tk
from tkcalendar import Calendar
from Views.View_utils import ViewUtils
from Controllers import PaymentsController, ExpenseController, InvoiceController, UserController, ControllerUtils, SalaryController
from Model import DBInvoicesColumns, DBUsersColumns, DBClientsColumns, DBPaymentsColumns, DBProductionsColumns, DBAccountsColumns, DBExpensesColumns, DBSuppliersColumns, DBSalariesColumns
import re
from datetime import datetime
from enum import Enum
from dataclasses import fields

class SalariesView(ctk.CTk):

    def __init__(self, db_model, salary_controller, user_controller, account_controller, update_controller, analyzer, fiscal_settings, catalogo_elenchi, config_manager, tab):
        super().__init__()

        self.db_model = db_model
        self.salary_controller = salary_controller
        self.user_controller = user_controller
        self.account_controller = account_controller
        self.update_controller = update_controller
        self.analyzer = analyzer
        self.fiscal_settings = fiscal_settings
        self.catalogo_elenchi = catalogo_elenchi
        self.config_manager = config_manager
        self.tab = tab

        self.global_infos = {}
        self.amount_aggregate_labels = {}
        self.aggregate_UOM = {
            ExpenseController.ExpensesAggregateData.NUMERO_SPESE.value: "",
            ExpenseController.ExpensesAggregateData.TOT_SPESE.value: "€"
        }

        self.today = datetime.now()

        self.salaries_card_list = {}
        self.salary_card_labels_status = {}

    def create_salaries_tab(self):
        self.search_bar_frame = ctk.CTkFrame(self.tab)
        self.search_bar_frame.pack(pady=(5, 10), fill="x", anchor="s")
        self.search_bar = ctk.CTkEntry(self.search_bar_frame)
        self.search_bar.pack(padx=(5, 35), anchor="s", side="right")
        self.search_bar_option_menu_values = {"NOME SALARIO": "NOME SALARIO", "NOME UTENTE" : "NOME UTENTE", "CONTO": "CONTO"}
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

            if key == SalaryController.SalariesAggregateData.NUMERO_SALARI.value:
                global_info_unità_di_misura = ""
            elif key == SalaryController.SalariesAggregateData.TOT_SALARI.value:
                global_info_unità_di_misura = "€"

            title = ctk.CTkLabel(card, text=f"{key}", font=("Arial", 12), bg_color="#1F6AA5")
            amount = ctk.CTkLabel(card, text=f"{info} {global_info_unità_di_misura}", font=("Arial", 16))

            card.pack(side="left", anchor="w", padx=10, pady=(10, 5))
            title.pack(anchor="n", padx=10, pady=(10, 5), ipadx=7, ipady=5)
            amount.pack(anchor="s", padx=10, pady=5)

            # salvo i dati che potrebbero avere bisogno di configure successivamente
            self.amount_aggregate_labels[f"{key}"] = amount

        self.salaries_table_frame = ctk.CTkFrame(self.tab)
        self.salaries_table_frame.pack(pady=(20, 0), padx=(10, 15), fill="x", anchor="n")

        self.table_headers = ["NOME", "UTENTE", "IMPORTO", "DATA", "CONTO\nCORRENTE"]

        for i, header in enumerate(self.table_headers):
            # crea il container
            column = ctk.CTkFrame(self.salaries_table_frame)
            column.grid(row=0, column=i, sticky="nsew", padx=(0, 5), pady=5)

            # imposta peso e uniformità: tutte le colonne "col" si dividono equamente
            self.salaries_table_frame.grid_columnconfigure(i, weight=1, uniform="col")

            # la label riempie il suo container
            label = ctk.CTkLabel(column,
                                 text=header,
                                 font=("Arial", 14))
            label.pack(fill="both", expand=True, padx=5, pady=15)

        # Creazione del frame delle cards
        self.cards_frame = ctk.CTkScrollableFrame(self.tab)
        self.cards_frame.pack(padx=0, pady=10, fill="both", expand=True)

        self.add_salary_frame = ctk.CTkFrame(self.tab)
        self.add_salary_frame.pack(padx=0, pady=(5, 20), fill="x")

        self.save_button = ctk.CTkButton(self.add_salary_frame, text="Aggiungi un salario",
                                         command=self.open_add_salary_window)
        self.save_button.pack()

        for salary in self.salary_controller.retrieve_salaries_map_list(True):
            if salary:
                salary_id = salary[DBSalariesColumns.ID.value]
                salary_name = salary[DBSalariesColumns.NAME.value]
                amount = salary[DBSalariesColumns.AMOUNT.value]
                date = salary[DBSalariesColumns.DATE.value]
                user_id = salary[DBSalariesColumns.USER_ID.value]
                if user_id:
                    user = self.user_controller.retrieve_user_map_by_id(user_id)
                    user_first = user[DBUsersColumns.FIRST_NAME.value]
                    user_second = user[DBUsersColumns.LAST_NAME.value]
                    user_name = user_first + " " + user_second
                else:
                    user_name = " ---- "
                account = self.account_controller.retrieve_account_map_by_id(salary[DBSalariesColumns.ACCOUNT_ID.value])
                account_name = account[DBAccountsColumns.NAME.value] if account else "conto non trovato"

                self.add_salary_card(salary_id, salary_name, user_name, amount, date, account_name)

    def filter_cards(self, event):
        """Filtra le card in base al testo della barra di ricerca e al tipo di filtro scelto."""
        search_text = self.search_bar.get().lower()
        search_type = self.search_bar_optionMenu.get()

        # Mappatura: ogni chiave associa una tupla (indice, classe_attesa) del widget da cui prelevare il testo
        filter_mapping = {
            "NOME SALARIO": (0, ctk.CTkButton),  # Bottone
            "NOME UTENTE": (1, ctk.CTkLabel),
            "CONTO": (4, ctk.CTkLabel)
        }

        mapping = filter_mapping.get(search_type)

        # Prima rimuovo tutte le card dal container per avere un layout pulito
        for card in self.salaries_card_list.values():
            card.pack_forget()

        # Se il tipo di ricerca non è riconosciuto, riposiziona tutte le card nell'ordine originale
        if mapping is None:
            for card in self.salaries_card_list.values():
                card.pack(pady=10, padx=10, fill="x", expand=True)
            return

        idx, expected_class = mapping

        # Itera sulle card nell’ordine originale (grazie al dizionario ordinato)
        for key, card in self.salaries_card_list.items():
            children = card.winfo_children()  # Lista dei widget figli
            widget_text = ""
            if len(children) > idx and isinstance(children[idx], expected_class):
                widget_text = children[idx].cget("text")
            # Se il testo (in lowercase) contiene il testo di ricerca, riposiziona la card
            if search_text in widget_text.lower():
                card.pack(pady=10, padx=10, fill="x", expand=True)

    def populate_global_infos(self):
        numero_salari = self.salary_controller.count_salaries(True)
        totale_salari = round(self.salary_controller.calculate_tot_salaries(), 2)
        self.global_infos[f"{SalaryController.SalariesAggregateData.NUMERO_SALARI.value}"] = numero_salari
        self.global_infos[f"{SalaryController.SalariesAggregateData.TOT_SALARI.value}"] = f"{totale_salari:.2f}"

    def add_salary_card(self, salary_id, salary_name, user_name, amount, date, account_name):
        card = ctk.CTkFrame(self.cards_frame, fg_color="dimgray")
        card.pack(pady=10, padx=8, fill="x", expand=True)  # Spaziatura tra le card

        # Dati da visualizzare nella card
        data = [salary_name, user_name, round(amount, 2), ViewUtils.invert_data_string(date), account_name]
        units = ["", "", "€", "", ""]
        n_cols = len(data)  # 8 colonne totali

        # Configura il grid della card: 1 riga, n_cols colonne uguali
        for c in range(n_cols):
            card.grid_columnconfigure(c, weight=1, uniform="clientcol")

        card.grid_rowconfigure(0, weight=1)

        # 0) Bottone "nome"
        btn = ctk.CTkButton(
            card,
            text=salary_name,
            command=lambda sid=salary_id: self.open_modify_salary(sid)
        )
        btn.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        # 1..7) Le altre colonne
        for idx, val in enumerate(data[1:], start=1):
            text = f"{val} {units[idx]}"
            lbl = ctk.CTkLabel(card, text=text, font=("Arial", 14))
            lbl.grid(row=0, column=idx, sticky="nsew", padx=5, pady=10)

        # Salva la card per eventuale successivo accesso
        self.salaries_card_list[salary_name] = card

    def open_add_salary_window(self):
        self.add_salary_window = ctk.CTkToplevel(self)
        self.add_salary_window.title("Aggiungi Nuovo Salario")

        # Assicurati che la finestra rimanga sopra
        self.add_salary_window.lift()  # Porta la finestra sopra quella principale
        self.add_salary_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

        self.add_salary_window.geometry("550x700")

        self.salary_window_scrollableFrame = ctk.CTkScrollableFrame(self.add_salary_window)
        self.salary_window_scrollableFrame.pack(fill="both", expand=True)

        self.nome_conto_string = "CONTO"
        self.nome_utente_string = "NOME UTENTE"

        self.entry_fields = {
            self.nome_utente_string: ctk.CTkOptionMenu,
            DBSalariesColumns.NAME.value: ctk.CTkEntry,
            DBSalariesColumns.DATE.value: Calendar,
            DBSalariesColumns.AMOUNT.value: ctk.CTkEntry,
            self.nome_conto_string: ctk.CTkOptionMenu,
        }

        self.error_fields = {
            DBSalariesColumns.NAME.value: ctk.CTkLabel,
            DBSalariesColumns.AMOUNT.value: ctk.CTkLabel,
        }

        self.salaries_widgets = {}
        self.error_labels = {}
        self.salaries_labels = {}

        # Creo i labels e i widgets
        for i, (label_text, widget_class) in enumerate(self.entry_fields.items()):
            # Etichetta
            label = ctk.CTkLabel(self.salary_window_scrollableFrame, text=label_text)
            # disegno i labels
            if i == 0:
                label.pack(pady=5)
            elif i != 0 :
                label.pack(pady=(35, 0))

            self.salaries_labels[label_text] = label

            # creo i widgets
            if label_text == self.nome_utente_string:
                # recupero gli utenti
                users = self.user_controller.retrieve_users_map_list()
                widget = widget_class(self.salary_window_scrollableFrame,
                                      values=[user[DBUsersColumns.FIRST_NAME.value] + " " + user[
                                          DBUsersColumns.LAST_NAME.value] for user in users],
                                      command=lambda selected_value: self.toggle_widgets_on_user_selection(selected_value))


            elif label_text == DBSalariesColumns.DATE.value:
                widget = widget_class(self.salary_window_scrollableFrame, date_pattern=ViewUtils.date_pattern)


            elif label_text == self.nome_conto_string:
                # recupero i conti
                accounts = self.account_controller.retrieve_accounts_map_list()
                widget = widget_class(self.salary_window_scrollableFrame,
                                      values=[account[DBAccountsColumns.NAME.value] for account in accounts])

            else:
                widget = widget_class(self.salary_window_scrollableFrame)


            #packing widget
            widget.pack(pady=5, padx=10, fill="x", expand=True)

            self.salaries_widgets[label_text] = widget

            if self.error_fields.get(label_text) is not None:
                error_label = ctk.CTkLabel(self.salary_window_scrollableFrame, text="")
                error_label.pack(pady=(0, 15))
                self.error_labels[label_text] = error_label

        user_name_at_window_opening = self.salaries_widgets[self.nome_utente_string].get()
        self.toggle_widgets_on_user_selection(user_name_at_window_opening)

        # Bottone per salvare
        self.save_button = ctk.CTkButton(
            self.salary_window_scrollableFrame,
            text="Salva Salario",
            command=self.save_salary_data
        )
        self.save_button.pack(pady=(50, 15))



        # Aggiungi validazione agli eventi di perdita del focus
        self.salaries_widgets[DBSalariesColumns.NAME.value].bind("<FocusOut>",
             lambda event: ViewUtils.validate_entry(
                 self.salaries_widgets[
                     DBSalariesColumns.NAME.value],
                 lambda val: val.strip() != "",
                 self.error_labels[
                     DBSalariesColumns.NAME.value],
                 "Il campo non può essere vuoto."
             ))

        self.salaries_widgets[DBSalariesColumns.AMOUNT.value].bind("<FocusOut>",
            lambda event: ViewUtils.validate_entry(
                self.salaries_widgets[
                   DBSalariesColumns.AMOUNT.value],
                lambda val: re.fullmatch(
                   r"^\d+(\.\d{2})?$",
                   val.strip()) is not None,
                self.error_labels[
                   DBSalariesColumns.AMOUNT.value],
                "Inserimento non valido: inserire un numero monetario con due cifre decimali (es. 123.45)"
            ))

    def toggle_widgets_on_user_selection(self, selected_value):
        user = self.user_controller.retrieve_user_map_by_extended_name(selected_value.strip())
        if user:
            account = self.account_controller.retrieve_account_map_by_id(user[DBUsersColumns.CONTO_CORRENTE_ID.value])
            self.salaries_widgets[DBSalariesColumns.NAME.value].delete(0, tk.END)
            self.salaries_widgets[DBSalariesColumns.NAME.value].insert(0, f"{selected_value.strip()} - {self.today.strftime("%m/%Y")}")
            self.salaries_widgets[self.nome_conto_string].set(account[DBAccountsColumns.NAME.value])

    def save_salary_data(self):
        salary_data = {}

        # riempi il dizionario con i dati dei widgets primari
        for label_text, widget in self.salaries_widgets.items():
            if isinstance(widget, ctk.CTkEntry) or isinstance(widget, ctk.CTkOptionMenu):
                salary_data[label_text] = widget.get().strip()
            elif isinstance(widget, Calendar):
                salary_data[label_text] = widget.get_date()
            elif isinstance(widget, ctk.CTkTextbox):
                salary_data[label_text] = widget.get("1.0", "end-1c").strip()  # Recupera il testo dal Textbox

        # chiamata al controller per salvare i dati
        success, message = self.salary_controller.save_salary(salary_data)

        if success:

            # prendo l'ID della sesa appena creata
            salary_map = self.salary_controller.retrieve_last_salary_insert_map()
            print(f"Salario {salary_data[DBSalariesColumns.NAME.value]} salvato con successo")

            user = self.user_controller.retrieve_user_map_by_id(salary_map[DBSalariesColumns.USER_ID.value])
            user_first = user[DBUsersColumns.FIRST_NAME.value]
            user_last = user[DBUsersColumns.LAST_NAME.value]
            user_full = user_first + " " + user_last

            account_name = \
            self.account_controller.retrieve_account_map_by_id(salary_map[DBExpensesColumns.ACCOUNT_ID.value])[
                DBAccountsColumns.NAME.value]

            self.add_salary_card(
                salary_map[DBSalariesColumns.ID.value],
                salary_map[DBSalariesColumns.NAME.value],
                user_full,
                salary_map[DBSalariesColumns.AMOUNT.value],
                salary_map[DBSalariesColumns.DATE.value],
                account_name
            )

            self.clear_class_variable()
            self.add_salary_window.destroy()
            self.update_global_infos()
        else:
            print(message)
            ViewUtils.show_error_popup(self.add_salary_window, "ERRORE", message)

    def open_modify_salary(self, salary_id):
        return

    def clear_class_variable(self):
        self.salaries_widgets.clear()
        self.salaries_labels.clear()

    def update_global_infos(self):
        return

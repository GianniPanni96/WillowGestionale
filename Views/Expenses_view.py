import customtkinter as ctk
import tkinter as tk
from tkcalendar import Calendar
from Views.View_utils import ViewUtils
from Controllers import PaymentsController, ExpenseController, InvoiceController, UserController, ControllerUtils
from Model import DBInvoicesColumns, DBUsersColumns, DBClientsColumns, DBPaymentsColumns, DBProductionsColumns, DBAccountsColumns, DBExpensesColumns, DBSuppliersColumns
import re
from enum import Enum
from dataclasses import fields

class ExpensesView(ctk.CTk):

    def __init__(self, db_model, expense_controller, user_controller, account_controller, supplier_controller, invoice_controller, update_controller, fiscal_settings, catalogo_elenchi, config_manager, tab):
        super().__init__()

        self.db_model = db_model
        self.expense_controller = expense_controller
        self.user_controller = user_controller
        self.account_controller = account_controller
        self.supplier_controller = supplier_controller
        self.invoice_controller = invoice_controller
        self.update_controller = update_controller
        self.fiscal_settings = fiscal_settings
        self.catalogo_elenchi = catalogo_elenchi
        self.config_manager = config_manager
        self.tab = tab

        self.global_infos = {}
        self.amount_aggregate_labels = {}

        self.expenses_card_list = {}
        self.expense_card_labels_status = {}

    def create_expenses_tab(self):
        self.search_bar_frame = ctk.CTkFrame(self.tab)
        self.search_bar_frame.pack(pady=(5, 10), fill="x", anchor="s")
        self.search_bar = ctk.CTkEntry(self.search_bar_frame)
        self.search_bar.pack(padx=(5, 35), anchor="s", side="right")
        self.search_bar_option_menu_values = {"NOME SPESA": "NOME SPESA", "NOME FORNITORE" : "NOME FORNITORE", "NOME UTENTE": "NOME UTENTE",
                                              "CATEGORIA": "CATEGORIA", "CONTO": "CONTO"}
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

        self.payments_table_frame = ctk.CTkFrame(self.tab)
        self.payments_table_frame.pack(pady=(20, 0), padx=(10, 15), fill="x", anchor="n")

        self.table_headers = ["NOME", "FORNITORE", "NETTO", "LORDO", "CATEGORIA", "DATA", "DEDUCIBILE", "UTENTE\nASSOCIATO", "CONTO\nCORRENTE"]

        for i, header in enumerate(self.table_headers):
            column = ctk.CTkFrame(self.payments_table_frame)
            label = ctk.CTkLabel(column, text=f"{header}", font=("Arial", 14), width=190)
            column.pack(padx=(0, 5), pady=5, fill="y", expand=True, side="left")
            label.pack(padx=5, pady=15, anchor="n")

        # Creazione del frame delle cards
        self.cards_frame = ctk.CTkScrollableFrame(self.tab)
        self.cards_frame.pack(padx=0, pady=10, fill="both", expand=True)

        self.add_expense_frame = ctk.CTkFrame(self.tab)
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
                user_id = expense[DBExpensesColumns.USER_ID.value]
                user = self.user_controller.retrieve_user_map_by_id(user_id)
                user_first = user[DBUsersColumns.FIRST_NAME.value]
                user_second = user[DBUsersColumns.LAST_NAME.value]
                user_name = user_first + " " + user_second
                account = self.account_controller.retrieve_account_map_by_id(expense[DBExpensesColumns.ACCOUNT_ID.value])
                account_name = account[DBAccountsColumns.NAME.value]

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

        self.entry_fields = {
            self.nome_fornitore_string: ctk.CTkOptionMenu,
            DBExpensesColumns.CATEGORY.value: ctk.CTkOptionMenu,
            DBExpensesColumns.NAME.value : ctk.CTkEntry,
            DBExpensesColumns.DATE.value: Calendar,
            DBExpensesColumns.DEDUCIBILE.value: ctk.CTkOptionMenu,
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
            if i == 0:
                label.pack(pady=5)
            else:
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
                                      values=["Sì", "No"])

            elif label_text == self.nome_utente_string:
                #recupero gli utenti
                users = self.user_controller.retrieve_users_map_list()
                widget = widget_class(self.expense_window_scrollableFrame,
                                      values=[" ----- "] + [user[DBUsersColumns.FIRST_NAME.value] + " " + user[DBUsersColumns.LAST_NAME.value] for user in users])

                widget.set(" ----- ")

            elif label_text == self.nome_fattura_string:
                #recupero le fatture
                invoices = self.invoice_controller.retrieve_invoices_map_list()
                widget = widget_class(self.expense_window_scrollableFrame,
                                      values=["Fattura non ancora emessa"] + [invoice[DBInvoicesColumns.NUMERO_FATTURA.value] for invoice in invoices])

                widget.set("Fattura non ancora emessa")

            elif label_text == self.nome_conto_string:
                # recupero i conti
                accounts = self.account_controller.retrieve_accounts_map_list()
                widget = widget_class(self.expense_window_scrollableFrame,
                                      values=[account[DBAccountsColumns.NAME.value] for account in accounts])

            else:
                widget = widget_class(self.expense_window_scrollableFrame)

            widget.pack(pady=5, padx=10, fill="x", expand=True)

            self.expenses_widgets[label_text] = widget

            if self.error_fields.get(label_text) is not None:
                error_label = ctk.CTkLabel(self.expense_window_scrollableFrame, text="")
                error_label.pack(pady=(0, 15))
                self.error_labels[label_text] = error_label


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
        return

    def filter_cards(self):
        return

    def add_expense_card(self, expense_id, name, supplier_name, net_amount, amount, category, date, deducibile, user_name, account_name):
        return

    def populate_global_infos(self):
        numero_spese = self.expense_controller.count_expenses(True)
        totale_spese = round(self.expense_controller.calculate_tot_expenses(), 2)
        self.global_infos[f"{ExpenseController.ExpensesAggregateData.NUMERO_SPESE.value}"] = numero_spese
        self.global_infos[f"{ExpenseController.ExpensesAggregateData.TOT_SPESE.value}"] = f"{totale_spese:.2f}"

    def autofill_expense_name(self, selected_value):
        self.name_frame.winfo_children()[0].configure(
            text=f"{selected_value} - ")

    def expense_category_optionMenu_behaviour(self, selected_value):
        sector_dict = dict(self.catalogo_elenchi["expenses_category"])
        if selected_value == sector_dict.get("ADD_CATEGORY"):
            self.open_add_expenses_category()
        elif selected_value == sector_dict.get("PRODUCTION_EXPENSE"):
            self.toggle_linked_invoice_selection()

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

    def toggle_linked_invoice_selection(self):
        return

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

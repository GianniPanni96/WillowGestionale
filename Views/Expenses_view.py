import customtkinter as ctk
import tkinter as tk
from tkcalendar import Calendar
from Views.View_utils import ViewUtils
from Controllers import PaymentsController, ExpenseController, InvoiceController, UserController, ControllerUtils
from Model import DBInvoicesColumns, DBUsersColumns, DBClientsColumns, DBPaymentsColumns, DBProductionsColumns, DBAccountsColumns, DBExpensesColumns, DBSuppliersColumns
from datetime import datetime
import re
from enum import Enum

class ExpensesView(ctk.CTk):

    def __init__(self, db_model, expense_controller, user_controller, account_controller, supplier_controller, update_controller, tab):
        super().__init__()

        self.db_model = db_model
        self.expense_controller = expense_controller
        self.user_controller = user_controller
        self.account_controller = account_controller
        self.supplier_controller = supplier_controller
        self.update_controller = update_controller
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

        self.nome_utente_string = "NOME UTENTE"
        self.nome_fornitore_string = "NOME FORNITORE"

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
                                      values=reversed_invoices,
                                      command=lambda selected_value: self.toggle_linked_rata(selected_value))
            elif label_text == self.nome_conto_string:
                widget = widget_class(self.payment_window_scrollableFrame,
                                      values=[f"{item[DBAccountsColumns.NAME.value]}" for item in
                                              self.account_controller.account_list])
            elif label_text == DBPaymentsColumns.LINKED_RATA.value:
                widget = widget_class(self.payment_window_scrollableFrame,
                                      values=["1", "2", "3"],
                                      command=lambda selected_value: self.control_linked_rata(selected_value))
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
        self.payment_widgets[DBPaymentsColumns.PAYMENT_NAME.value].bind("<FocusOut>",
            lambda event: ViewUtils.validate_entry(
                self.payment_widgets[
                    DBPaymentsColumns.PAYMENT_NAME.value],
                lambda val: val.strip() != "",
                self.error_labels[
                    DBPaymentsColumns.PAYMENT_NAME.value],
                "Il campo non può essere vuoto."
            ))

        self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].bind("<FocusOut>",
            lambda event: ViewUtils.validate_entry(
              self.payment_widgets[
                  DBPaymentsColumns.PAYMENT_AMOUNT.value],
              lambda val: re.fullmatch(
                  r"^\d+(\.\d{2})?$",
                  val.strip()) is not None,
              self.error_labels[
                  DBPaymentsColumns.PAYMENT_AMOUNT.value],
              "Inserimento non valido: inserire un numero monetario con due cifre decimali (es. 123.45)"
            ))

    def filter_cards(self):
        return

    def add_expense_card(self, expense_id, name, supplier_name, net_amount, amount, category, date, deducibile, user_name, account_name):
        return

    def populate_global_infos(self):
        numero_spese = self.expense_controller.count_expenses(True)
        totale_spese = round(self.expense_controller.calculate_tot_expenses(), 2)
        self.global_infos[f"{ExpenseController.ExpensesAggregateData.NUMERO_SPESE.value}"] = numero_spese
        self.global_infos[f"{ExpenseController.ExpensesAggregateData.TOT_SPESE.value}"] = f"{totale_spese:.2f}"

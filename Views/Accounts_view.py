import customtkinter as ctk
import tkinter as tk
from tkcalendar import Calendar
from Views.View_utils import ViewUtils
from Controllers import PaymentsController, InvoiceController, UserController, ControllerUtils, SupplierController
from Model import DBInvoicesColumns, DBUsersColumns, DBClientsColumns, DBPaymentsColumns, DBProductionsColumns, DBAccountsColumns, DBSuppliersColumns
from datetime import datetime
import re
from enum import Enum

class AccountsView(ctk.CTk):

    def __init__(self, db_model, account_controller, update_controller,  config_manager, catalogo_elenchi, analyzer, tab):
        super().__init__()

        self.db_model = db_model
        self.account_controller = account_controller
        self.update_controller = update_controller
        self.config_manager = config_manager
        self.catalogo_elenchi = catalogo_elenchi
        self.analyzer = analyzer
        self.tab = tab

        self.global_infos = {}
        self.amount_aggregate_labels = {}
        self.balance_labels = {}
        self.number_of_account_cards = 0
        self.account_cards = {}

        self.update_controller.register_on_adding_payment_view_cllbks(self.update_accounts_balances)

    def create_accounts_tab(self):
        """Crea la UI per la gestione dei conti bancari"""
        self.account_description = ctk.CTkLabel(self.tab, text="Gestisci i conti correnti", font=("Arial", 14))
        self.account_description.pack(pady=(70, 45))

        # Bottone per aggiungere un nuovo utente
        self.add_account_button = ctk.CTkButton(self.tab, text="Aggiungi Nuovo Conto", font=("Arial", 15, "bold"),
                                             command=self.open_add_account_window)
        self.add_account_button.configure(width=200, height=50)
        self.add_account_button.pack(pady=20)

        # Area per le cards degli utenti (simulata qui per ora)
        self.account_card_area = ctk.CTkFrame(self.tab)
        self.account_card_area.pack(pady=20)

        self.account_card_area1 = ctk.CTkFrame(self.tab)
        self.account_card_area1.pack(pady=20)

        # aggiungo una card per ogni utente
        for account in self.account_controller.retrieve_accounts_map_list():
            id =  account[DBAccountsColumns.ID.value]
            name = account[DBAccountsColumns.NAME.value]
            balance = self.analyzer.calculate_account_balance_by_account_id(id)

            self.add_account_card(id, name, balance)

    def open_add_account_window(self):
        return

    def add_account_card(self, id, name, balance):
        """Aggiungi una card per un conto alla lista"""

        account_card = ctk.CTkFrame(self.account_card_area if self.number_of_account_cards < 4 else self.account_card_area1)
        account_card.pack(side="left", pady=5, padx=25)
        self.account_cards[id] = account_card

        info_frame = ctk.CTkFrame(account_card)
        info_frame.pack(padx=10, pady=(10, 0))

        # Nome, balance
        detail_info_frame = ctk.CTkFrame(info_frame)
        detail_info_frame.pack(side="left", anchor="n", fill="both", expand=True, padx=(0, 10), pady=10)
        user_info_name = ctk.CTkLabel(detail_info_frame, text=f"{name}")
        user_info_name.pack(anchor="w", padx=10, pady=10)
        user_info_balance = ctk.CTkLabel(detail_info_frame, text=f"Saldo: {balance}")
        user_info_balance.pack(anchor="w", padx=10, pady=10)

        self.balance_labels[id] = user_info_balance

        self.modify_button = ctk.CTkButton(account_card, text="Modifica",
                                           command=lambda: self.open_modify_account_window(id))
        self.modify_button.pack(side="left", pady=10, padx=28)

        self.delete_button = ctk.CTkButton(account_card, text="Elimina", command=lambda: self.open_confirm_popup(id,
                                                                                                              ViewUtils.InterfaceOperations.ELIMINAZIONE_UTENTE.value))
        self.delete_button.pack(pady=10)

        self.number_of_account_cards += 1

    def open_modify_account_window(self, account_id):
        return

    def open_confirm_popup(self, id, operation):
        self.confirm_window = ctk.CTkToplevel(self)
        self.confirm_window.title(
            f"Pop-up di conferma")

        # Assicurati che la finestra rimanga sopra
        self.confirm_window.lift()  # Porta la finestra sopra quella principale
        self.confirm_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

        self.confirm_window.geometry("400x150")

        confirm_label = ctk.CTkLabel(self.confirm_window, text=f"{operation}\nSei sicuro di voler proseguire con l'operazione?")
        confirm_label.pack(pady=20, padx=5)

        self.confirm_window_Frame = ctk.CTkFrame(self.confirm_window)
        self.confirm_window_Frame.pack(pady=15)

        confirm_button = ctk.CTkButton(self.confirm_window_Frame, text="conferma", command= lambda: self.delete_account(id))
        confirm_button.pack(pady=10, padx=5, side="left")

        cancel_button = ctk.CTkButton(self.confirm_window_Frame, text="cancella", command=lambda: self.confirm_window.destroy())
        cancel_button.pack(pady=10, padx=5)

    def delete_account(self, account_id):
        success, message = self.account_controller.delete_account_by_ID(account_id)
        if success and account_id in self.account_cards:
            self.account_cards[account_id].destroy()  # Rimuovi la card dalla UI
            del self.account_cards[account_id]  # Rimuovi dal dizionario
            self.number_of_account_cards -= 1
        else:
            print(f"impossibile eliminare il conto: {message}")
            ViewUtils.show_error_popup("ERRORE", message)

    def update_accounts_balances(self):
        for account_id, label in self.balance_labels.items():
            new_balance = self.analyzer.calculate_account_balance_by_account_id(account_id)
            label.configure(text=f"Saldo: {new_balance}")

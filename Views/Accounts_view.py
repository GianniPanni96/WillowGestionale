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

        self.account_widgets = {}
        self.account_labels = {}

        self.update_controller.register_on_adding_payment_view_cllbks(self.update_accounts_balances)
        self.update_controller.register_on_adding_expense_view_cllbks(self.update_accounts_balances)

    def create_accounts_tab(self):
        """Crea la UI per la gestione dei conti bancari"""
        self.account_description = ctk.CTkLabel(self.tab, text="Gestisci i conti correnti", font=("Arial", 14))
        self.account_description.pack(pady=(70, 45))

        # Area per le cards degli utenti (simulata qui per ora)
        self.account_card_area = ctk.CTkFrame(self.tab)
        self.account_card_area.pack(fill= "y", expand=True, pady=20)

        self.account_card_area1 = ctk.CTkFrame(self.tab)
        self.account_card_area1.pack(fill= "y", expand=True, pady=20)

        # Bottone per aggiungere un nuovo utente
        self.add_account_button = ctk.CTkButton(self.tab, text="Aggiungi Nuovo Conto", font=("Arial", 15, "bold"),
                                             command=self.open_add_account_window)
        self.add_account_button.configure(width=200, height=50)
        self.add_account_button.pack(anchor="s", pady=20)

        # aggiungo una card per ogni utente
        for account in self.account_controller.retrieve_accounts_map_list():
            id =  account[DBAccountsColumns.ID.value]
            name = account[DBAccountsColumns.NAME.value]
            balance = self.analyzer.calculate_account_balance_by_account_id(id)

            self.add_account_card(id, name, balance)

    def open_add_account_window(self):
        """Apre una finestra per aggiungere un nuovo conto"""

        self.add_account_window = ctk.CTkToplevel(self)
        self.add_account_window.title("Aggiungi Nuova Produzione")

        # Assicurati che la finestra rimanga sopra
        self.add_account_window.lift()  # Porta la finestra sopra quella principale
        self.add_account_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

        self.add_account_window.geometry("350x400")

        self.account_window_scrollableFrame = ctk.CTkScrollableFrame(self.add_account_window)
        self.account_window_scrollableFrame.pack(fill="both", expand=True)

        self.entry_fields = {
            DBAccountsColumns.NAME.value: ctk.CTkEntry,
            DBAccountsColumns.INIT_BALANCE.value: ctk.CTkEntry,
        }

        self.error_fields = {
            DBAccountsColumns.NAME.value: ctk.CTkLabel,
            DBAccountsColumns.INIT_BALANCE.value: ctk.CTkLabel,
        }

        self.error_labels = {}

        for i, (label_text, widget_class) in enumerate(self.entry_fields.items()):
            # Etichetta
            label = ctk.CTkLabel(self.account_window_scrollableFrame, text=label_text)
            #disegno i labels
            if i == 0:
                label.pack(pady=5)
            else:
                label.pack(pady=(35, 0))

            self.account_labels[label_text] = label

            #creo i widgets
            widget = widget_class(self.account_window_scrollableFrame)

            widget.pack(pady=5, padx=(0, 10), fill="x", expand=True)

            self.account_widgets[label_text] = widget

            if self.error_fields.get(label_text) is not None:
                error_label = ctk.CTkLabel(self.account_window_scrollableFrame, text="")
                error_label.pack(pady=(0,15))
                self.error_labels[label_text] = error_label

        # Bottone per salvare
        self.save_button = ctk.CTkButton(
            self.account_window_scrollableFrame,
            text="Salva Conto Corrente",
            command=self.save_account_data
        )
        self.save_button.pack(pady=(35, 15))

        # Aggiungi validazione agli eventi di perdita del focus
        self.account_widgets[DBAccountsColumns.NAME.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.account_widgets[DBAccountsColumns.NAME.value],
            lambda val: val.strip() != "",
            self.error_labels[DBAccountsColumns.NAME.value],
            "Il campo non può essere vuoto."
        ))

        self.account_widgets[DBAccountsColumns.INIT_BALANCE.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.account_widgets[DBAccountsColumns.INIT_BALANCE.value],
            lambda val: re.fullmatch(r"^\d+(\.\d{2})?$", val.strip()) is not None,
            self.error_labels[DBAccountsColumns.INIT_BALANCE.value],
            "Inserimento non valido: inserire un numero monetario con due cifre decimali (es. 123.45)"
        ))

    def add_account_card(self, id, name, balance):
        """Aggiungi una card per un conto alla lista"""

        account_card = ctk.CTkFrame(self.account_card_area if self.number_of_account_cards < 4 else self.account_card_area1)
        account_card.pack(side="left", pady=5, padx=25)
        self.account_cards[id] = account_card

        info_frame = ctk.CTkFrame(account_card)
        info_frame.pack(fill= "y", expand=True, side="left", padx=10, pady=10)

        # Nome, balance
        user_info_name = ctk.CTkLabel(info_frame, text=f"{name}", font=("Arial", 20))
        user_info_name.pack(anchor="n", expand=True, padx=10, pady=5)
        user_info_balance = ctk.CTkLabel(info_frame, text=f"{balance:.2f} €", font=("Arial", 16))
        user_info_balance.pack(anchor="s", padx=10, pady=10)

        buttons_frame = ctk.CTkFrame(account_card)
        buttons_frame.pack(padx=10, pady=(10, 10))

        self.balance_labels[id] = user_info_balance

        self.modify_button = ctk.CTkButton(buttons_frame, text="Modifica", command=lambda: self.open_modify_account_window(id))
        self.modify_button.pack(pady=10, padx=10)

        self.bonifico_button = ctk.CTkButton(buttons_frame, text="Esegui Bonifico", command=lambda: self.esegui_bonifico)
        self.bonifico_button.pack(pady=10)

        self.delete_button = ctk.CTkButton(buttons_frame, text="Disattiva", command=lambda: self.open_confirm_popup(id, ViewUtils.InterfaceOperations.ELIMINAZIONE_UTENTE.value))
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
            label.configure(text=f"{new_balance:.2f} €")

    def esegui_bonifico(self):
        return

    def save_account_data(self):
        account_data = {}

        # riempi il dizionario con i dati dei widgets primari
        for label_text, widget in self.account_widgets.items():
            if isinstance(widget, ctk.CTkEntry) or isinstance(widget, ctk.CTkOptionMenu):
                account_data[label_text] = widget.get().strip()
            elif isinstance(widget, Calendar):
                account_data[label_text] = widget.get_date()
            elif isinstance(widget, ctk.CTkTextbox):
                account_data[label_text] = widget.get("1.0", "end-1c").strip()  # Recupera il testo dal Textbox

        # chiamata al controller per salvare i dati
        success, message = self.account_controller.save_account(account_data)

        if success:
            #prendo l'ID del conto appena creato
            account_map = self.account_controller.retrieve_last_account_insert_map()
            print(f"Conto {account_data[DBAccountsColumns.NAME.value]} salvato con successo")

            self.add_account_card(
                account_map[DBAccountsColumns.ID.value],
                account_map[DBAccountsColumns.NAME.value],
                account_map[DBAccountsColumns.INIT_BALANCE.value]
            )

            self.clear_class_variable()
            self.add_account_window.destroy()
            self.update_global_infos()
        else:
            print(message)
            ViewUtils.show_error_popup(self.add_account_window, "ERRORE", message)

    def clear_class_variable(self):
        self.account_widgets.clear()
        self.account_labels.clear()

    def update_global_infos(self):
        return


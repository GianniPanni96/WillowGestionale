import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
from datetime import datetime
import os, re
from Views.View_utils import ViewUtils
#from screeninfo import get_monitors


from Controllers import ValidationUtils, UserController, AccountController, ClientController, InvoiceController, \
    PaymentsController, ProductionController, ExpenseController, SupplierController, UpdatesController, ControllerUtils
from Model import DatabaseModel, db_path, DBUsersColumns, DBSuppliersColumns, DBAccountsColumns
from Fatturazione_elettronica_API import FatturazioneElettronicaProvider

from Views.Clients_view import ClientsView
from Views.Invoices_view import InvoicesView
from Views.Payments_view import PaymentsView
from Views.Productions_view import ProductionsView
from Views.Expenses_view import ExpensesView
from Views.Suppliers_view import SuppliersView


class MainWindow(ctk.CTk):
    def __init__(self, config_manager, fiscal_settings, catalogo_elenchi, recurring_expenses_settings):
        super().__init__()

        # inizializzatori oggetti controllers e model
        self.db_model = DatabaseModel(db_path)  # Istanzia il modello
        self.user_controller = UserController(self.db_model, fiscal_settings)  # Crea il controller per gli utenti
        self.account_controller = AccountController(self.db_model, self.user_controller)
        self.client_controller = ClientController(self.db_model)
        self.supplier_controller = SupplierController(self.db_model)
        self.payment_controller = PaymentsController(self.db_model, self.account_controller)
        self.production_controller = ProductionController(self.db_model, self.client_controller)
        self.invoice_controller = InvoiceController(self.db_model, self.user_controller, self.client_controller, self.production_controller, self.payment_controller, fiscal_settings)
        self.expense_controller = ExpenseController(self.db_model, self.user_controller, self.account_controller, self.invoice_controller, self.supplier_controller)
        self.update_controller = UpdatesController(self.user_controller, self.client_controller, self.invoice_controller, self.payment_controller, self.account_controller, self.production_controller)

        self.fiscal_settings = fiscal_settings
        self.catalogo_elenchi = catalogo_elenchi
        self.recurring_expenses_settings = recurring_expenses_settings

        # ConfigManager per la gestione della configurazione
        self.config_manager = config_manager

        #solo per debug
        #self.user_controller.print_utenti()

        #tool variables
        self.no_data_string = "no data"
        self.current_year = datetime.now().year

        #construct users list
        self.users_list = self.user_controller.retrieve_users_map_list()
        self.number_of_users_cards = 0
        self.user_cards = {}  # Dizionario per associare user_id alle card


        #construct accounts_names list
        self.accounts_mapping = AccountController.get_accounts_mapping(self.db_model)
        if self.accounts_mapping == {}:
            self.accounts_list = [self.no_data_string]
        else:
            self.accounts_list = list(self.accounts_mapping.keys())

        self.title("Gestionale Willow")
        #self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
        #self.attributes("-fullscreen", True)
        # Massimizza dopo che tutto è stato inizializzato
        self.after(3000, lambda: self.state("zoomed"))

        # Toolbar simulata con pulsanti
        self.toolbar_frame = ctk.CTkFrame(self)
        self.toolbar_frame.pack(side="top", fill="x")

        # Menu "File" personalizzato
        self.file_menu_button = ctk.CTkButton(self.toolbar_frame, text="Gestione Backups", command=self.open_backups_window)
        self.file_menu_button.pack(side="left", padx=15, pady=15)

        # Menu "File" personalizzato
        self.fiscal_settings_menu_button = ctk.CTkButton(self.toolbar_frame, text="Gestione Dati Fiscali", command=self.open_fiscal_settings_window)
        self.fiscal_settings_menu_button.pack(side="left", padx=15, pady=15)

        # Menu "File" personalizzato
        self.recurring_expenses_menu_button = ctk.CTkButton(self.toolbar_frame, text="Gestione Spese Ricorrenti", command=self.open_recurring_expenses_window)
        self.recurring_expenses_menu_button.pack(side="left", padx=15, pady=15)

        # Creazione di un popup menu simulato
        self.file_menu_frame = None

        # Creazione delle tabs (frame)
        self.tabview = ctk.CTkTabview(self, width=500, height=500)
        self.tabview.pack(padx=20, pady=20, fill="both", expand=True)

        self.tabview.add("Utenti")
        self.tabview.add("Clienti")
        self.tabview.add("Fatture")
        self.tabview.add("Pagamenti")
        self.tabview.add("Produzioni")
        self.tabview.add("Spese")
        self.tabview.add("Fornitori")
        self.tabview.add("Conti")
        self.tabview.add("Iva")
        self.tabview.add("Salario")
        self.tabview.add("Tasse")
        self.tabview.add("Report")


        self.custom_font = ctk.CTkFont("Arial", 20)
        self.tabview._segmented_button.configure(font=self.custom_font)

        # Aggiorna le aliquote fiscali in base al controllo sull'anno di apertura della partita iva
        success, message = self.user_controller.update_tax_rates()
        print(message)
        if not success:
            print(message)

        # Aggiungi widget alla tab "Utenti"
        self.user_tab()

        #Aggiungi widget alla tab clienti tramite la classe ClientsView
        self.client_tab = ClientsView(self.db_model, self.client_controller, self.catalogo_elenchi, self.config_manager, self.tabview.tab("Clienti"))
        self.client_tab.create_client_tab()
        self.invoice_tab = InvoicesView(self.db_model, self.invoice_controller, self.user_controller, self.client_controller, self.production_controller, self.payment_controller, self.tabview.tab("Fatture"), fiscal_settings)
        self.invoice_tab.create_invoices_tab()
        self.payment_tab = PaymentsView(self.db_model, self.payment_controller, self.invoice_controller, self.user_controller, self.client_controller, self.production_controller, self.account_controller, self.update_controller, self.tabview.tab("Pagamenti"))
        self.payment_tab.create_payments_tab()
        self.production_tab = ProductionsView(self.db_model, self.production_controller, self.payment_controller, self.invoice_controller, self.user_controller, self.client_controller, self.catalogo_elenchi, self.config_manager, self.tabview.tab("Produzioni"))
        self.production_tab.create_productions_tab()
        self.expense_tab = ExpensesView(self.db_model, self.expense_controller, self.user_controller, self.account_controller, self.supplier_controller, self.invoice_controller, self.update_controller, fiscal_settings, catalogo_elenchi, self.config_manager, self.tabview.tab("Spese"))
        self.expense_tab.create_expenses_tab()
        self.supplier_tab = SuppliersView(self.db_model, self.supplier_controller, self.update_controller, self.config_manager, catalogo_elenchi, self.tabview.tab("Fornitori"))
        self.supplier_tab.create_suppliers_tab()

    def user_tab(self):
        """Crea la UI per la gestione degli utenti"""
        tab = self.tabview.tab("Utenti")

        self.user_description = ctk.CTkLabel(tab, text="Gestisci gli utenti del sistema", font=("Arial", 14))
        self.user_description.pack(pady=(70,45))

        # Bottone per aggiungere un nuovo utente
        self.add_user_button = ctk.CTkButton(tab, text="Aggiungi Nuovo Utente", font=("Arial", 15, "bold"),  command=self.open_add_user_window)
        self.add_user_button.configure(width=200, height=50)
        self.add_user_button.pack(pady=20)

        # Area per le cards degli utenti (simulata qui per ora)
        self.user_card_area = ctk.CTkFrame(tab)
        self.user_card_area.pack(pady=20)


        self.user_card_area1 = ctk.CTkFrame(tab)
        self.user_card_area1.pack(pady=20)


        #aggiungo una card per ogni utente
        for user in self.users_list:
            self.add_user_card(user[f"{DBUsersColumns.ID.value}"], user[f"{DBUsersColumns.FIRST_NAME.value}"], user[f"{DBUsersColumns.LAST_NAME.value}"], user[f"{DBUsersColumns.PARTITA_IVA.value}"], user[DBUsersColumns.PHOTO_PATH.value], user[f"{DBUsersColumns.EMAIL.value}"])

    def open_add_user_window(self):
        """Apre una finestra per aggiungere un nuovo utente"""

        self.add_user_window = ctk.CTkToplevel(self)
        self.add_user_window.title("Aggiungi Nuovo Utente")

        # Assicurati che la finestra rimanga sopra
        self.add_user_window.lift()  # Porta la finestra sopra quella principale
        self.add_user_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

        self.add_user_window.geometry("400x700")

        self.user_window_scrollableFrame = ctk.CTkScrollableFrame(self.add_user_window)
        self.user_window_scrollableFrame.pack(fill="both", expand=True)

        #entry del path della immagine di profilo
        self.image_label = ctk.CTkLabel(self.user_window_scrollableFrame, text="Immagine Profilo:")
        self.image_label.pack(pady=(5, 0))
        self.image_path = tk.StringVar()  # Variabile per memorizzare il percorso dell'immagine
        self.image_button = ctk.CTkButton(
            self.user_window_scrollableFrame,
            text="Scegli Immagine",
            command=self.choose_image
        )
        self.image_button.pack(pady=(5, 20))
        self.image_preview = ctk.CTkLabel(self.user_window_scrollableFrame, text="Anteprima Immagine", width=150, height=150, corner_radius=8, fg_color="lightgrey")
        self.image_preview.pack(pady=(5, 15))

        # Etichette e Entry
        self.first_name_label = ctk.CTkLabel(self.user_window_scrollableFrame, text="Nome:")
        self.first_name_label.pack(pady=(5, 0))
        self.first_name_entry = ctk.CTkEntry(self.user_window_scrollableFrame)
        self.first_name_entry.pack(pady=(5, 5))
        self.first_name_error = ctk.CTkLabel(self.user_window_scrollableFrame, text="")
        self.first_name_error.pack(pady=(0, 15))

        self.last_name_label = ctk.CTkLabel(self.user_window_scrollableFrame, text="Cognome:")
        self.last_name_label.pack(pady=(5, 0))
        self.last_name_entry = ctk.CTkEntry(self.user_window_scrollableFrame)
        self.last_name_entry.pack(pady=(5, 5))
        self.last_name_error = ctk.CTkLabel(self.user_window_scrollableFrame, text="")
        self.last_name_error.pack(pady=(0, 15))

        self.partita_iva_label = ctk.CTkLabel(self.user_window_scrollableFrame, text="Partita IVA:")
        self.partita_iva_label.pack(pady=(5, 0))
        self.partita_iva_entry = ctk.CTkEntry(self.user_window_scrollableFrame)
        self.partita_iva_entry.pack(pady=(5, 5))
        self.partita_iva_error = ctk.CTkLabel(self.user_window_scrollableFrame, text="")
        self.partita_iva_error.pack(pady=(0, 15))

        self.codice_fiscale_label = ctk.CTkLabel(self.user_window_scrollableFrame, text="Codice Fiscale:")
        self.codice_fiscale_label.pack(pady=(5, 0))
        self.codice_fiscale_entry = ctk.CTkEntry(self.user_window_scrollableFrame)
        self.codice_fiscale_entry.pack(pady=(5, 35))

        self.telefono_label = ctk.CTkLabel(self.user_window_scrollableFrame, text="Telefono:")
        self.telefono_label.pack(pady=(5, 0))
        self.telefono_entry = ctk.CTkEntry(self.user_window_scrollableFrame)
        self.telefono_entry.pack(pady=(5, 35))

        self.email_label = ctk.CTkLabel(self.user_window_scrollableFrame, text="Email:")
        self.email_label.pack(pady=(5, 0))
        self.email_entry = ctk.CTkEntry(self.user_window_scrollableFrame)
        self.email_entry.pack(pady=(5, 5))
        self.email_error = ctk.CTkLabel(self.user_window_scrollableFrame, text="")
        self.email_error.pack(pady=(0, 15))

        self.conto_corrente_label = ctk.CTkLabel(self.user_window_scrollableFrame, text="Conto Corrente:")
        self.conto_corrente_label.pack(pady=(5, 0))
        self.conto_corrente_combobox = ctk.CTkOptionMenu(self.user_window_scrollableFrame, values=self.accounts_list)
        self.conto_corrente_combobox.pack(pady=(5, 15))

        self.regime_fiscale_label = ctk.CTkLabel(self.user_window_scrollableFrame, text="Regime Fiscale:")
        self.regime_fiscale_label.pack(pady=(35, 0))
        self.regime_fiscale_combobox = ctk.CTkOptionMenu(self.user_window_scrollableFrame, values=[item.value for item in self.user_controller.RegimeFiscale])
        self.regime_fiscale_combobox.pack(pady=(5, 5))

        years = [str(year) for year in range(2000, self.current_year + 1)]  # Elenco anni fino all'anno corrente
        self.anno_apertura_piva_label = ctk.CTkLabel(self.user_window_scrollableFrame, text="Anno di apertura p. iva:")
        self.anno_apertura_piva_label.pack(pady=(35, 0))
        self.anno_apertura_piva_combobox = ctk.CTkOptionMenu(self.user_window_scrollableFrame, values=years)
        self.anno_apertura_piva_combobox.pack(pady=(5, 5))

        self.provider_FattElett_label = ctk.CTkLabel(self.user_window_scrollableFrame, text="Provider fatturazione elettronica:")
        self.provider_FattElett_label.pack(pady=(35, 0))
        self.provider_FattElett_combobox = ctk.CTkOptionMenu(self.user_window_scrollableFrame, values=[item.value for item in FatturazioneElettronicaProvider], command=self.provider_login_toggle_edit)
        self.provider_FattElett_combobox.pack(pady=(5, 5))

        self.provider_username_label = ctk.CTkLabel(self.user_window_scrollableFrame,
                                                    text="Username (login Fatturazione Elettronica):")
        self.provider_login_username_frame = ctk.CTkFrame(self.user_window_scrollableFrame)
        self.provider_username_entry = ctk.CTkEntry(self.provider_login_username_frame, show="*")
        self.show_provider_username_button = ctk.CTkButton(self.provider_login_username_frame, text="👁️",
                                                           command=lambda: self.toggle_visibility_entry_widget(
                                                               self.provider_username_entry,
                                                               self.show_provider_username_button),
                                                           width=30)

        self.provider_password_label = ctk.CTkLabel(self.user_window_scrollableFrame,
                                                    text="Password (login Fatturazione Elettronica):")
        self.provider_login_password_frame = ctk.CTkFrame(self.user_window_scrollableFrame)
        self.provider_password_entry = ctk.CTkEntry(self.provider_login_password_frame, show="*")
        self.show_provider_password_button = ctk.CTkButton(self.provider_login_password_frame, text="👁️",
                                                           command=lambda: self.toggle_visibility_entry_widget(
                                                               self.provider_password_entry,
                                                               self.show_provider_password_button), width=30)

        # Bottoni per salvare e annullare
        self.save_button = ctk.CTkButton(self.user_window_scrollableFrame, text="Salva", command=self.save_user_data)

        self.provider_login_toggle_edit()


        # Aggiungi validazione agli eventi di perdita del focus
        self.first_name_entry.bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.first_name_entry,
            lambda val: val.strip() != "",
            self.first_name_error,
            "Il nome non può essere vuoto."
        ))
        self.last_name_entry.bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.last_name_entry,
            lambda val: val.strip() != "",
            self.last_name_error,
            "Il cognome non può essere vuoto."
        ))
        self.partita_iva_entry.bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.partita_iva_entry,
            lambda val: val.isdigit() and ValidationUtils.validate_partita_iva(val),
            self.partita_iva_error,
            "La partita IVA deve essere un numero di 11 cifre."
        ))
        self.email_entry.bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.email_entry,
            lambda val: ValidationUtils.validate_email(val),
            self.email_error,
            "Inserisci una e-mail valida."
        ))

    def save_user_data(self):
        """Salva i dati dell'utente tramite il controller"""

        user_data = {
            DBUsersColumns.FIRST_NAME.value: self.first_name_entry.get().strip(),
            DBUsersColumns.LAST_NAME.value: self.last_name_entry.get().strip(),
            DBUsersColumns.PARTITA_IVA.value: self.partita_iva_entry.get().strip(),
            DBUsersColumns.CODICE_FISCALE.value: self.codice_fiscale_entry.get().strip(),
            DBUsersColumns.TELEFONO.value: self.telefono_entry.get().strip(),
            DBUsersColumns.EMAIL.value: self.email_entry.get().strip(),
            DBUsersColumns.PROVIDER_FATTURE.value: self.provider_FattElett_combobox.get(),
            DBUsersColumns.USERNAME_PROVIDER.value: self.provider_username_entry.get().strip(),
            DBUsersColumns.PASSWORD_PROVIDER.value: self.provider_password_entry.get().strip(),
            DBUsersColumns.REGIME_FISCALE.value: self.regime_fiscale_combobox.get(),
            DBUsersColumns.PHOTO_PATH.value: self.image_path.get(),
            DBUsersColumns.CONTO_CORRENTE_ID.value: self.conto_corrente_combobox.get(),  # Da aggiornare se necessario
            DBUsersColumns.ANNO_APERTURA_PIVA.value: self.anno_apertura_piva_combobox.get(),
            DBUsersColumns.STATUS.value: self.user_controller.UserStatus.ATTIVO.value,
        }

        # Chiamata al controller per salvare i dati
        success, message = self.user_controller.save_user(user_data)
        if success:
            user_id = self.user_controller.retrieve_user_by_fullname(user_data[DBUsersColumns.FIRST_NAME.value], user_data[DBUsersColumns.LAST_NAME.value])[0] #recupero l'ID dell'utente
            print(f"User {user_data[DBUsersColumns.FIRST_NAME.value]} {user_data[DBUsersColumns.LAST_NAME.value]} salvato con successo")
            # Aggiungi la card dell'utente nella UI
            self.add_user_card(
                user_id,
                user_data[DBUsersColumns.FIRST_NAME.value],
                user_data[DBUsersColumns.LAST_NAME.value],
                user_data[DBUsersColumns.PARTITA_IVA.value],
                user_data[DBUsersColumns.PHOTO_PATH.value],
                user_data[DBUsersColumns.EMAIL.value]
            )

            self.users_list.append(self.user_controller.retrieve_user_map_by_id(user_id))
            self.user_controller.print_utenti()

            # Chiudi la finestra di aggiunta
            self.add_user_window.destroy()
        else:
            # Mostra il messaggio d'errore
            print(message)
            ViewUtils.show_error_popup("ERRORE", message)

    def open_modify_user_window(self, user_id):
        """Apre una finestra per aggiungere un nuovo utente"""

        def toggle_edit():
            """
            Abilita o disabilita la modifica dei widget nella finestra di modifica utente.
            """
            # Determina lo stato (abilitato/disabilitato) in base al valore dello switch
            state = ctk.NORMAL if self.enable_modifications_switch.get() else ctk.DISABLED

            # Cambia anche lo stato del pulsante Salva
            self.save_button.configure(state=state)
            self.show_provider_username_button.configure(state=state)
            self.show_provider_password_button.configure(state=state)

            # Aggiorna lo stato dei widget
            for widget in widgets_to_toggle:
                widget.configure(state=state)

        #prima retrivo i dati dell'utente
        user = self.user_controller.retrieve_user_map_by_id(user_id)
        #print(f"{user[DBUsersColumns.FIRST_NAME.value]}")

        self.modify_user_window = ctk.CTkToplevel(self)
        self.modify_user_window.title(f"Modifica i dati dell'utente: {user[DBUsersColumns.FIRST_NAME.value]} {user[DBUsersColumns.LAST_NAME.value]}")

        # Assicurati che la finestra rimanga sopra
        self.modify_user_window.lift()  # Porta la finestra sopra quella principale
        self.modify_user_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

        self.modify_user_window.geometry("400x700")

        self.modify_window_scrollableFrame = ctk.CTkScrollableFrame(self.modify_user_window)
        self.modify_window_scrollableFrame.pack(fill="both", expand=True)

        self.enable_modifications_switch = ctk.CTkSwitch(self.modify_window_scrollableFrame, text="Abilita la modifica", command=toggle_edit)
        self.enable_modifications_switch.pack(pady=5)

        # entry del path della immagine di profilo
        self.image_label = ctk.CTkLabel(self.modify_window_scrollableFrame, text="Immagine Profilo:")
        self.image_label.pack(pady=(5, 0))
        self.image_path = tk.StringVar()  # Variabile per memorizzare il percorso dell'immagine
        self.image_button = ctk.CTkButton(
            self.modify_window_scrollableFrame,
            text="Scegli Immagine",
            command=self.choose_image
        )
        self.image_button.pack(pady=(5, 20))
        self.image_preview = ctk.CTkLabel(self.modify_window_scrollableFrame, text="", width=150,
                                          height=150, corner_radius=8, fg_color="lightgrey")
        self.image_preview.pack(pady=(5, 15))

        # Etichette e Entry
        self.first_name_label = ctk.CTkLabel(self.modify_window_scrollableFrame, text="Nome:")
        self.first_name_label.pack(pady=(5, 0))
        self.first_name_entry = ctk.CTkEntry(self.modify_window_scrollableFrame)
        self.first_name_entry.pack(pady=(5, 5))
        self.first_name_error = ctk.CTkLabel(self.modify_window_scrollableFrame, text="")
        self.first_name_error.pack(pady=(0, 15))

        self.last_name_label = ctk.CTkLabel(self.modify_window_scrollableFrame, text="Cognome:")
        self.last_name_label.pack(pady=(5, 0))
        self.last_name_entry = ctk.CTkEntry(self.modify_window_scrollableFrame)
        self.last_name_entry.pack(pady=(5, 5))
        self.last_name_error = ctk.CTkLabel(self.modify_window_scrollableFrame, text="")
        self.last_name_error.pack(pady=(0, 15))

        self.partita_iva_label = ctk.CTkLabel(self.modify_window_scrollableFrame, text="Partita IVA:")
        self.partita_iva_label.pack(pady=(5, 0))
        self.partita_iva_entry = ctk.CTkEntry(self.modify_window_scrollableFrame)
        self.partita_iva_entry.pack(pady=(5, 5))
        self.partita_iva_error = ctk.CTkLabel(self.modify_window_scrollableFrame, text="")
        self.partita_iva_error.pack(pady=(0, 15))

        self.codice_fiscale_label = ctk.CTkLabel(self.modify_window_scrollableFrame, text="Codice Fiscale:")
        self.codice_fiscale_label.pack(pady=(5, 0))
        self.codice_fiscale_entry = ctk.CTkEntry(self.modify_window_scrollableFrame)
        self.codice_fiscale_entry.pack(pady=(5, 35))

        self.telefono_label = ctk.CTkLabel(self.modify_window_scrollableFrame, text="Telefono:")
        self.telefono_label.pack(pady=(5, 0))
        self.telefono_entry = ctk.CTkEntry(self.modify_window_scrollableFrame)
        self.telefono_entry.pack(pady=(5, 35))

        self.email_label = ctk.CTkLabel(self.modify_window_scrollableFrame, text="Email:")
        self.email_label.pack(pady=(5, 0))
        self.email_entry = ctk.CTkEntry(self.modify_window_scrollableFrame)
        self.email_entry.pack(pady=(5, 5))
        self.email_error = ctk.CTkLabel(self.modify_window_scrollableFrame, text="")
        self.email_error.pack(pady=(0, 15))

        self.conto_corrente_label = ctk.CTkLabel(self.modify_window_scrollableFrame, text="Conto Corrente:")
        self.conto_corrente_label.pack(pady=(5, 0))
        self.conto_corrente_combobox = ctk.CTkOptionMenu(self.modify_window_scrollableFrame, values=self.accounts_list)
        self.conto_corrente_combobox.pack(pady=(5, 15))

        self.regime_fiscale_label = ctk.CTkLabel(self.modify_window_scrollableFrame, text="Regime Fiscale:")
        self.regime_fiscale_label.pack(pady=(35, 0))
        self.regime_fiscale_combobox = ctk.CTkOptionMenu(self.modify_window_scrollableFrame, values=[item.value for item in
                                                                                                 self.user_controller.RegimeFiscale])
        self.regime_fiscale_combobox.pack(pady=(5, 5))

        years = [str(year) for year in range(2000, self.current_year + 1)]  # Elenco anni fino all'anno corrente
        self.anno_apertura_piva_label = ctk.CTkLabel(self.modify_window_scrollableFrame, text="Anno di apertura p. iva:")
        self.anno_apertura_piva_label.pack(pady=(35, 0))
        self.anno_apertura_piva_combobox = ctk.CTkOptionMenu(self.modify_window_scrollableFrame, values=years)
        self.anno_apertura_piva_combobox.pack(pady=(5, 5))

        self.provider_FattElett_label = ctk.CTkLabel(self.modify_window_scrollableFrame, text="Provider fatturazione elettronica:")
        self.provider_FattElett_label.pack(pady=(35, 0))
        self.provider_FattElett_combobox = ctk.CTkOptionMenu(self.modify_window_scrollableFrame, values=[item.value for item in FatturazioneElettronicaProvider], command=self.provider_login_toggle_edit)
        self.provider_FattElett_combobox.pack(pady=(5, 5))

        self.provider_username_label = ctk.CTkLabel(self.modify_window_scrollableFrame, text="Username (login Fatturazione Elettronica):")
        self.provider_login_username_frame = ctk.CTkFrame(self.modify_window_scrollableFrame)
        self.provider_username_entry = ctk.CTkEntry(self.provider_login_username_frame, show="*")
        self.show_provider_username_button = ctk.CTkButton(self.provider_login_username_frame, text="👁️",
                                                           command= lambda: self.toggle_visibility_entry_widget(self.provider_username_entry, self.show_provider_username_button),
                                                           width=30)

        self.provider_password_label = ctk.CTkLabel(self.modify_window_scrollableFrame, text="Password (login Fatturazione Elettronica):")
        self.provider_login_password_frame = ctk.CTkFrame(self.modify_window_scrollableFrame)
        self.provider_password_entry = ctk.CTkEntry(self.provider_login_password_frame, show="*")
        self.show_provider_password_button = ctk.CTkButton(self.provider_login_password_frame, text="👁️",
                                                           command=lambda: self.toggle_visibility_entry_widget(
                                                               self.provider_password_entry, self.show_provider_password_button), width=30)



        #riempio i campi con i dati retrievati dall'utente
        # Riempimento delle entry e combobox con i dati di user
        self.first_name_entry.insert(0, user[DBUsersColumns.FIRST_NAME.value])
        self.last_name_entry.insert(0, user[DBUsersColumns.LAST_NAME.value])
        self.partita_iva_entry.insert(0, user[DBUsersColumns.PARTITA_IVA.value])
        self.codice_fiscale_entry.insert(0, user[DBUsersColumns.CODICE_FISCALE.value])
        self.telefono_entry.insert(0, user[DBUsersColumns.TELEFONO.value])
        self.email_entry.insert(0, user[DBUsersColumns.EMAIL.value])

        # Imposta il valore del combobox del conto corrente
        if user[DBUsersColumns.CONTO_CORRENTE_ID.value] in self.accounts_list:
            self.conto_corrente_combobox.set(user[DBUsersColumns.CONTO_CORRENTE_ID.value])

        # Imposta il valore del combobox del regime fiscale
        if user[DBUsersColumns.REGIME_FISCALE.value] in [item.value for item in self.user_controller.RegimeFiscale]:
            self.regime_fiscale_combobox.set(user[DBUsersColumns.REGIME_FISCALE.value])

        # Imposta il valore del combobox dell'anno di apertura p. iva
        if user[DBUsersColumns.ANNO_APERTURA_PIVA.value]:
            self.anno_apertura_piva_combobox.set(user[DBUsersColumns.ANNO_APERTURA_PIVA.value])

        # Imposta il valore del combobox del provider delle fatture elettroniche
        if user[DBUsersColumns.PROVIDER_FATTURE.value]:
            self.provider_FattElett_combobox.set(user[DBUsersColumns.PROVIDER_FATTURE.value])

        decrypted_username = self.user_controller.decrypt_string(user[DBUsersColumns.USERNAME_PROVIDER.value])
        # Imposta il valore della entry dello username per il login sul provider FE
        if user[DBUsersColumns.USERNAME_PROVIDER.value]:
            self.provider_username_entry.insert(0, decrypted_username)

        decrypted_password = self.user_controller.decrypt_string(user[DBUsersColumns.PASSWORD_PROVIDER.value])
        # Imposta il valore della entry della password per il login sul provider FE
        if user[DBUsersColumns.PASSWORD_PROVIDER.value]:
            self.provider_password_entry.insert(0, decrypted_password)

        # Imposta l'immagine di profilo
        photo_path = user[DBUsersColumns.PHOTO_PATH.value]
        if photo_path and os.path.exists(photo_path):
            photo = Image.open(photo_path)
            image = ctk.CTkImage(dark_image=photo, size=(150, 150))
            self.image_preview.configure(image=image)
            self.image_path.set(photo_path)  # Memorizza il percorso dell'immagine



        # Aggiungi validazione agli eventi di perdita del focus
        self.first_name_entry.bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
           self.first_name_entry,
            lambda val: val.strip() != "",
            self.first_name_error,
            "Il nome non può essere vuoto."
        ))
        self.last_name_entry.bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.last_name_entry,
            lambda val: val.strip() != "",
            self.last_name_error,
            "Il cognome non può essere vuoto."
        ))
        self.partita_iva_entry.bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.partita_iva_entry,
            lambda val: val.isdigit() and ValidationUtils.validate_partita_iva(val),
            self.partita_iva_error,
            "La partita IVA deve essere un numero di 11 cifre."
        ))
        self.email_entry.bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.email_entry,
            lambda val: ValidationUtils.validate_email(val),
            self.email_error,
            "Inserisci una e-mail valida."
        ))

        # Bottoni per salvare e annullare
        self.save_button = ctk.CTkButton(self.modify_window_scrollableFrame, text="Salva modifiche", command=lambda: self.update_user_data(user[DBUsersColumns.ID.value]))


        # Elenco dei widget da abilitare/disabilitare
        widgets_to_toggle = [
            self.first_name_entry,
            self.last_name_entry,
            self.partita_iva_entry,
            self.codice_fiscale_entry,
            self.telefono_entry,
            self.email_entry,
            self.conto_corrente_combobox,
            self.regime_fiscale_combobox,
            self.anno_apertura_piva_combobox,
            self.image_button,
            self.provider_FattElett_combobox,
            self.provider_username_entry,
            self.provider_password_entry,


        ]

        self.provider_login_toggle_edit()

        #setto i campi delle entry come non modificabili di default all'apertura della finestra, così da evitare modifiche non volute
        for widget in widgets_to_toggle:
            widget.configure(state=ctk.DISABLED)

        self.save_button.configure(state=ctk.DISABLED)
        self.show_provider_password_button.configure(state=ctk.DISABLED)
        self.show_provider_username_button.configure(state=ctk.DISABLED)

    def update_user_data(self, user_id):
        """Aggiorna i dati di un utente tramite il controller"""

        # Recupera i dati dall'interfaccia utente
        user_data = {
            DBUsersColumns.FIRST_NAME.value: self.first_name_entry.get().strip(),
            DBUsersColumns.LAST_NAME.value: self.last_name_entry.get().strip(),
            DBUsersColumns.PARTITA_IVA.value: self.partita_iva_entry.get().strip(),
            DBUsersColumns.CODICE_FISCALE.value: self.codice_fiscale_entry.get().strip(),
            DBUsersColumns.TELEFONO.value: self.telefono_entry.get().strip(),
            DBUsersColumns.EMAIL.value: self.email_entry.get().strip(),
            DBUsersColumns.PROVIDER_FATTURE.value: self.provider_FattElett_combobox.get(),
            DBUsersColumns.USERNAME_PROVIDER.value: self.provider_username_entry.get().strip(),
            DBUsersColumns.PASSWORD_PROVIDER.value: self.provider_password_entry.get().strip(),
            DBUsersColumns.REGIME_FISCALE.value: self.regime_fiscale_combobox.get(),
            DBUsersColumns.PHOTO_PATH.value: self.image_path.get(),
            DBUsersColumns.CONTO_CORRENTE_ID.value: self.conto_corrente_combobox.get(),  # Da aggiornare se necessario
            DBUsersColumns.ANNO_APERTURA_PIVA.value: self.anno_apertura_piva_combobox.get(),
            DBUsersColumns.STATUS.value: self.user_controller.UserStatus.ATTIVO.value,
        }

        # Chiamata al controller per aggiornare i dati
        success, message = self.user_controller.update_user(user_id, user_data)
        if success:
            # Aggiorna la card dell'utente nella UI
            self.update_user_card(
                user_id,
                user_data.get(DBUsersColumns.FIRST_NAME.value),
                user_data.get(DBUsersColumns.LAST_NAME.value),
                user_data.get(DBUsersColumns.PARTITA_IVA.value),
                user_data.get(DBUsersColumns.PHOTO_PATH.value),
                user_data.get(DBUsersColumns.EMAIL.value)
            )

            # Aggiorna l'utente nella lista
            updated_user = self.user_controller.retrieve_user_map_by_id(user_id)
            self.users_list = [u if u['id'] != user_id else updated_user for u in self.users_list]
            self.user_controller.print_utenti()

            # Chiudi la finestra di aggiornamento
            self.modify_user_window.destroy()
        else:
            # Mostra il messaggio d'errore
            print(message)
            ViewUtils.show_error_popup("ERRORE", message)

    def add_user_card(self, user_id, first_name, last_name, partita_iva, image_path, email):
        """Aggiungi una card per un utente alla lista"""

        user_card = ctk.CTkFrame(self.user_card_area if self.number_of_users_cards < 4 else self.user_card_area1)
        user_card.pack(side="left", pady=5, padx=25)
        self.user_cards[user_id] = user_card

        info_frame = ctk.CTkFrame(user_card)
        info_frame.pack(padx=10, pady=(10, 0))

        # Carica e ridimensiona l'immagine se presente
        if image_path:
            try:
                img = Image.open(image_path)
                photo = ctk.CTkImage(img, size=(180, 180))
                user_image = ctk.CTkLabel(info_frame, image=photo, text="")
                user_image.image = photo  # Associa l'immagine per evitare il garbage collection
            except Exception as e:
                user_image = ctk.CTkLabel(info_frame, text="Errore Immagine")
        else:
            user_image = ctk.CTkLabel(info_frame, text="Nessuna Immagine")
        user_image.pack(side="left", padx=10, pady=10)

        # Nome, Cognome e Partita IVA
        detail_info_frame = ctk.CTkFrame(info_frame)
        detail_info_frame.pack(side="left", anchor="n", fill="both", expand=True, padx=(0, 10), pady=10)
        user_info_name = ctk.CTkLabel(detail_info_frame, text=f"{first_name} {last_name}")
        user_info_name.pack(anchor="w",padx=10, pady=10)
        user_info_partita_iva = ctk.CTkLabel(detail_info_frame, text=f"Partita IVA: {partita_iva}")
        user_info_partita_iva.pack(anchor="w", padx=10, pady=10)
        user_info_email = ctk.CTkLabel(detail_info_frame, text=f"e-mail: {email}")
        user_info_email.pack(anchor="w",padx=10, pady=10)

        self.modify_button = ctk.CTkButton(user_card, text="Modifica", command=lambda: self.open_modify_user_window(user_id))
        self.modify_button.pack(side="left",  pady=10, padx=28)

        self.delete_button = ctk.CTkButton(user_card, text="Elimina", command=lambda: self.open_confirm_popup(user_id, ViewUtils.InterfaceOperations.ELIMINAZIONE_UTENTE.value))
        self.delete_button.pack(pady=10)

        print(f"numero di user cards: {self.number_of_users_cards}")
        self.number_of_users_cards += 1

    def update_user_card(self, user_id, first_name, last_name, partita_iva, image_path, email):
        """Aggiorna una card esistente per un utente"""

        # Recupera la card esistente dell'utente
        user_card = self.user_cards.get(user_id)
        if not user_card:
            print(f"Card non trovata per l'utente con ID {user_id}")
            return

        # Aggiorna le informazioni nella card
        info_frame = user_card.winfo_children()[0]  # Recupera il frame info
        detail_info_frame = info_frame.winfo_children()[1]  # Recupera il frame dei dettagli

        # Aggiorna il nome e cognome
        name_label = detail_info_frame.winfo_children()[0]  # Recupera la label del nome
        name_label.configure(text=f"{first_name} {last_name}")

        # Aggiorna la partita IVA
        partita_iva_label = detail_info_frame.winfo_children()[1]  # Recupera la label della partita IVA
        partita_iva_label.configure(text=f"Partita IVA: {partita_iva}")

        # Aggiorna l'e-mail
        email_label = detail_info_frame.winfo_children()[2]  # Recupera la label del'email
        email_label.configure(text=f"E-mail: {email}")

        # Aggiorna l'immagine dell'utente se presente
        user_image = info_frame.winfo_children()[0]  # Recupera l'immagine dell'utente
        if image_path:
            try:
                img = Image.open(image_path)
                photo = ctk.CTkImage(img, size=(180, 180))
                user_image.configure(image=photo)
                user_image.image = photo  # Associa l'immagine per evitare il garbage collection
            except Exception as e:
                user_image.configure(text="Errore Immagine")
        else:
            user_image.configure(text="Nessuna Immagine")

        # Riaffaccia la card aggiornata
        user_card.pack(side="left", pady=5, padx=25)

        print(f"Card dell'utente {first_name} {last_name} aggiornata con successo.")

    def choose_image(self):
        """Apre una finestra di dialogo per scegliere un'immagine e la mostra come anteprima."""
        filetypes = [("Immagini", "*.png *.jpg *.jpeg *.gif")]
        path = filedialog.askopenfilename(title="Seleziona un'immagine", filetypes=filetypes)
        if path:
            self.image_path.set(path)  # Memorizza il percorso dell'immagine
            try:
                # Carica e ridimensiona l'immagine per l'anteprima
                img = Image.open(path)
                img.thumbnail((150, 150))  # Ridimensiona mantenendo le proporzioni
                self.image_preview_photo = ImageTk.PhotoImage(
                    img)  # Mantieni un riferimento per evitare garbage collection
                self.image_preview.configure(image=self.image_preview_photo, text="")  # Mostra l'immagine
            except Exception as e:
                self.image_preview.configure(text="Errore nel caricamento dell'immagine")
                print(f"Errore nel caricamento dell'immagine: {e}")

    def delete_user(self, user_id):
        success, message = self.user_controller.delete_user_by_ID(user_id)
        if success and user_id in self.user_cards:
            self.user_cards[user_id].destroy()  # Rimuovi la card dalla UI
            del self.user_cards[user_id]  # Rimuovi dal dizionario
            self.number_of_users_cards -= 1
        else:
            print(f"impossibile eliminare l'utente: {message}")
            ViewUtils.show_error_popup("ERRORE", message)

    def open_confirm_popup(self, user_id, operation):
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

        confirm_button = ctk.CTkButton(self.confirm_window_Frame, text="conferma", command= lambda: self.delete_user(user_id))
        confirm_button.pack(pady=10, padx=5, side="left")

        cancel_button = ctk.CTkButton(self.confirm_window_Frame, text="cancella", command=lambda: self.confirm_window.destroy())
        cancel_button.pack(pady=10, padx=5)

    def toggle_visibility_entry_widget(self, widget, button):
        if widget.cget("show") == "":  # Se il testo è visibile
            # Sostituisci con asterischi della stessa lunghezza
            widget.configure(show="*")
            button.configure(text="👁️", width=30)  # Cambia icona
        else:
            # Rendi il testo visibile
            widget.configure(show="")
            button.configure(text="🔒", width=30)  # Cambia icona

    def provider_login_toggle_edit(self, selected_value=None):
        state = ctk.NORMAL if self.provider_FattElett_combobox.get() != FatturazioneElettronicaProvider.NESSUNO.value else ctk.DISABLED
        if self.provider_FattElett_combobox.get() != FatturazioneElettronicaProvider.NESSUNO.value:
            self.save_button.pack_forget()
            self.provider_username_label.pack(pady=(35, 0))
            self.provider_login_username_frame.pack(pady=5)
            self.provider_username_entry.pack(side="left")
            self.show_provider_username_button.pack(anchor="w")
            self.provider_password_label.pack(pady=(35, 0))
            self.provider_login_password_frame.pack(pady=5)
            self.provider_password_entry.pack(side="left")
            self.show_provider_password_button.pack(anchor="w")
            self.save_button.pack(pady=(30, 10))
        else:
            self.provider_username_label.pack_forget()
            self.provider_login_username_frame.forget()
            self.provider_login_password_frame.forget()
            self.provider_password_label.pack_forget()
            self.save_button.pack(pady=(45, 10))



    # Funzioni per la gestione dei backups
    def open_backups_window(self):
        """Apre una finestra per gestire i backup."""
        # Finestra di dialogo
        self.backup_window = ctk.CTkToplevel(self)
        self.backup_window.title("Impostazioni di backup")
        self.backup_window.geometry("500x420")
        self.backup_window.lift()
        self.backup_window.grab_set()

        # Leggi la configurazione attuale
        current_config = self.config_manager.load_config()
        backup_settings = current_config.get("backup_settings", {})

        # Titolo
        title = ctk.CTkLabel(self.backup_window, text="Modifica Impostazioni di Backup", font=("Arial", 18))
        title.pack(pady=20)

        # Campi per ogni impostazione
        self.entries = {}

        # Backup base path
        self.add_field(
            label="Percorso base backup",
            default_value=backup_settings.get("backup_base_path", {}).get("value", ""),
            key="backup_base_path",
            parent=self.backup_window,
            tooltip="Cartella principale dove verranno archiviati tutti i backup."
        )

        # Interval in minuti
        self.add_slider_field(
            label="Frequenza esecuzione backup (minuti)",
            default_value=backup_settings.get("interval_minutes", {}).get("value", 15),
            key="interval_minutes",
            parent=self.backup_window,
            tooltip="Imposta l'intervallo di tempo (in minuti) tra ogni backup.",
            min_val=1,
            max_val=120
        )

        # Numero massimo di backup
        self.add_slider_field(
            label="Numero massimo di backup per cartella",
            default_value=backup_settings.get("max_backups", {}).get("value", 35),
            key="max_backups",
            parent=self.backup_window,
            tooltip="Specifica il numero massimo di backup da conservare.",
            min_val=1,
            max_val=100
        )

        # Delta giorni
        self.add_slider_field(
            label="Frequenza generazione nuova cartella (giorni)",
            default_value=backup_settings.get("delta_days", {}).get("value", 7),
            key="delta_days",
            parent=self.backup_window,
            tooltip="Indica quanti giorni di differenza tra i backup da mantenere.",
            min_val=1,
            max_val=30
        )

        # Pulsante Salva
        save_button = ctk.CTkButton(self.backup_window, text="Salva Impostazioni", command=self.save_backup_settings)
        save_button.pack(pady=20)

    def add_field(self, label, default_value, key, parent, tooltip):
        """Crea un campo di input per una configurazione."""
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", pady=5, padx=10)

        label_widget = ctk.CTkLabel(frame, text=label, anchor="w")
        label_widget.pack(side="top", fill="x")

        entry = ctk.CTkEntry(frame)
        entry.insert(0, default_value)
        entry.pack(fill="x", pady=2)
        self.entries[key] = entry

    def add_slider_field(self, label, default_value, key, parent, tooltip, min_val, max_val):
        """Crea un campo slider per una configurazione numerica con una scala visibile."""
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", pady=5, padx=10)

        # Label per il titolo
        label_widget = ctk.CTkLabel(frame, text=label, anchor="w")
        label_widget.pack(side="top", fill="x")

        # Frame per slider e valore numerico
        slider_frame = ctk.CTkFrame(frame)
        slider_frame.pack(fill="x", pady=2)

        # Slider
        slider = ctk.CTkSlider(
            slider_frame,
            from_=min_val,
            to=max_val,
            number_of_steps=max_val - min_val,
            command=lambda value: self.update_slider_label(value, value_label)
        )
        slider.set(default_value)
        slider.pack(side="left", fill="x", expand=True)

        # Valore numerico accanto allo slider
        value_label = ctk.CTkLabel(slider_frame, text=f"{int(default_value)}")
        value_label.pack(side="right", padx=10)
        self.entries[key] = slider

    def update_slider_label(self, value, label_widget):
        """Aggiorna la label con il valore attuale dello slider."""
        label_widget.configure(text=f"{int(float(value))}")

    def save_backup_settings(self):
        """Salva le impostazioni di backup aggiornate nel file di configurazione."""
        new_backup_settings = {}

        # Raccogli i nuovi valori dai widget (CTkEntry e CTkSlider)
        for key, widget in self.entries.items():
            if isinstance(widget, ctk.CTkEntry):
                new_backup_settings[key] = widget.get()
            elif isinstance(widget, ctk.CTkSlider):
                new_backup_settings[key] = int(widget.get())

        try:
            # Prova ad aggiornare la sezione "backup_settings" del file di configurazione
            self.config_manager.update_config_section("backup_settings", new_backup_settings)

            # Se l'aggiornamento ha successo, chiudi la finestra e notifica l'utente
            self.backup_window.destroy()
            ViewUtils.show_error_popup(
                self,
                "Salvataggio configurazione",
                "La configurazione è stata salvata con successo.\nLe nuove impostazioni saranno ricaricate al prossimo avvio dell'app."
            )

        except Exception as e:
            # In caso di errore (es. file bloccato da un'altra applicazione), mostra un popup con il messaggio d'errore
            ViewUtils.show_error_popup(
                self,
                "Errore salvataggio configurazione",
                f"Impossibile salvare la configurazione: {str(e)}"
            )



    # Funzioni per la gestione dei dati fiscali
    def open_fiscal_settings_window(self):
        """Apre una finestra per gestire i dati fiscali."""
        # Crea la finestra di dialogo
        self.fiscal_settings_window = ctk.CTkToplevel(self)
        self.fiscal_settings_window.title("Dati Fiscali")
        self.fiscal_settings_window.geometry("850x950+0+0")
        self.fiscal_settings_window.lift()
        self.fiscal_settings_window.grab_set()

        # Inizializza i dizionari per salvare i riferimenti ai widget
        self.iva_labels = {}
        self.iva_entries = {}
        self.forfettaria_labels = {}
        self.forfettaria_entries = {}
        self.ordinaria_labels = {}
        self.ordinaria_entries = {}
        self.ordinaria_irpef_entries = {}  # per gli scaglioni dinamici "aliquota_irpef_..."
        self.ordinaria_imponibili_entries = {}
        self.scaglioni_containers = {}
        self.title_frames = {}

        # Carica la configurazione corrente e prendi la sezione "fiscal_settings"
        current_config = self.config_manager.load_config()
        fiscal_settings = current_config.get("fiscal_settings", {})

        # Titolo principale
        title = ctk.CTkLabel(
            self.fiscal_settings_window,
            text="Modifica i dati fiscali in base alla legge vigente",
            font=("Arial", 22)
        )
        title.pack(pady=20)

        # Crea le tabs
        tabview = ctk.CTkTabview(self.fiscal_settings_window, width=500, height=500)
        tabview.pack(padx=20, pady=20, fill="both", expand=True)
        tabview.add("FORFETTARIA")
        tabview.add("ORDINARIA")
        tabview.add("IVA")
        tabview._segmented_button.configure(font=ctk.CTkFont("Arial", 16))

        # Crea i container scrollabili per ciascuna tab
        container_forfettaria = ctk.CTkScrollableFrame(tabview.tab("FORFETTARIA"))
        container_forfettaria.pack(fill="both", expand=True, padx=20, pady=10)
        container_ordinaria = ctk.CTkScrollableFrame(tabview.tab("ORDINARIA"))
        container_ordinaria.pack(fill="both", expand=True, padx=20, pady=10)
        container_iva = ctk.CTkScrollableFrame(tabview.tab("IVA"))
        container_iva.pack(fill="both", expand=True, padx=20, pady=10)

        # --- Sezione IVA ---
        iva_data = fiscal_settings.get("iva", {})  # Ora la sezione si chiama "iva"
        section_iva = ctk.CTkFrame(container_iva)
        section_iva.pack(fill="x", pady=(5, 70), padx=10)

        # Titolo della sezione IVA
        self.iva_labels["title"] = ctk.CTkLabel(section_iva, text="Aliquote IVA", font=("Arial", 18, "bold"))
        self.iva_labels["title"].pack(anchor="w", padx=10)

        # Lista delle chiavi in ordine desiderato
        iva_keys = [
            "aliquota_iva_ordinaria",
            "aliquota_iva_ridotta_1",
            "aliquota_iva_ridotta_2",
            "aliquota_iva_minima"
        ]

        # Per ogni aliquota IVA si crea una label e un entry
        for key in iva_keys:
            # Crea una label per il titolo dell'aliquota con un testo leggibile
            label_text = key.replace("_", " ").capitalize()
            label = ctk.CTkLabel(section_iva, text=label_text, font=("Arial", 14))
            label.pack(anchor="w", padx=10, pady=(15, 5) if key == "aliquota_iva_ordinaria" else 5)

            # Crea l'entry e inserisce il valore della chiave (se esistente)
            entry = ctk.CTkEntry(section_iva)
            entry.insert(0, str(iva_data.get(key, {}).get("value", "")))
            entry.pack(anchor="w", fill="x", padx=10, pady=(5, 2))
            self.iva_entries[key] = entry

            # Aggiungi una label per la descrizione corrispondente
            description = iva_data.get(key, {}).get("description", "")
            desc_label = ctk.CTkLabel(section_iva, text=description, font=("Arial", 12, "italic"), text_color="gray")
            desc_label.pack(anchor="w", padx=10, pady=(0, 15))

        # --- Sezione Forfettaria ---
        piva_forf_data = fiscal_settings.get("partita_iva_forfettaria", {})
        section_forf = ctk.CTkFrame(container_forfettaria)
        section_forf.pack(fill="x", pady=(5, 70), padx=10)
        self.forfettaria_labels["title"] = ctk.CTkLabel(section_forf, text="Partita IVA Forfettaria",
                                                        font=("Arial", 18, "bold"))
        self.forfettaria_labels["title"].pack(anchor="w", pady=(0, 5), padx=10)

        # Sottosezione: Aliquote & Parametri
        frame_forf_aliquote = ctk.CTkFrame(section_forf, corner_radius=2)
        frame_forf_aliquote.pack(fill="x", pady=(5, 5), padx=(0, 10))
        self.forfettaria_labels["aliquote_title"] = ctk.CTkLabel(frame_forf_aliquote, text="Aliquote & Parametri",
                                                                 font=("Arial", 16, "bold"))
        self.forfettaria_labels["aliquote_title"].pack(anchor="w", pady=(5, 15), padx=10)
        for key in ["aliquota_irpef_min", "aliquota_irpef_max", "anni_agevolazione", "aliquota_inps", "aliquota_rivalsa_inps"]:
            data = piva_forf_data.get(key, {})
            value = data.get("value", "")
            description = data.get("description", key)
            lbl = ctk.CTkLabel(frame_forf_aliquote, text=description, font=("Arial", 16))
            lbl.pack(anchor="w", padx=10, pady=5)
            self.forfettaria_labels[key] = lbl
            ent = ctk.CTkEntry(frame_forf_aliquote)
            ent.insert(0, str(value))
            ent.pack(anchor="w", fill="x", pady=(5, 15), padx=10)
            self.forfettaria_entries[key] = ent

        # Sottosezione: Imponibile
        frame_forf_imponibili = ctk.CTkFrame(section_forf, corner_radius=2)
        frame_forf_imponibili.pack(fill="x", pady=(35, 5), padx=(0, 10))
        self.forfettaria_labels["imponibile_title"] = ctk.CTkLabel(frame_forf_imponibili, text="Imponibile",
                                                                   font=("Arial", 16, "bold"))
        self.forfettaria_labels["imponibile_title"].pack(anchor="w", pady=(5, 15), padx=10)
        data = piva_forf_data.get("imponibile", {})
        value = data.get("value", "")
        description = data.get("description", "Imponibile")
        self.forfettaria_labels["imponibile_desc"] = ctk.CTkLabel(frame_forf_imponibili, text=description,
                                                                  font=("Arial", 16))
        self.forfettaria_labels["imponibile_desc"].pack(anchor="w", padx=10, pady=5)
        self.forfettaria_entries["imponibile"] = ctk.CTkEntry(frame_forf_imponibili)
        self.forfettaria_entries["imponibile"].insert(0, str(value))
        self.forfettaria_entries["imponibile"].pack(anchor="w", fill="x", pady=(5, 15), padx=10)

        # --- Sezione Ordinaria ---
        piva_ord_data = fiscal_settings.get("partita_iva_ordinaria", {})
        section_ord = ctk.CTkFrame(container_ordinaria)
        section_ord.pack(fill="x", pady=(5, 70), padx=10)
        self.ordinaria_labels["title"] = ctk.CTkLabel(section_ord, text="Partita IVA Ordinaria",
                                                      font=("Arial", 18, "bold"))
        self.ordinaria_labels["title"].pack(anchor="w", pady=(0, 5), padx=10)

        # Sottosezione: Aliquote
        frame_ord_aliquote = ctk.CTkFrame(section_ord, corner_radius=2)
        frame_ord_aliquote.pack(fill="x", pady=(5, 5), padx=(0, 10))
        self.ordinaria_labels["aliquote_title"] = ctk.CTkLabel(frame_ord_aliquote, text="Aliquote",
                                                               font=("Arial", 16, "bold"))
        self.ordinaria_labels["aliquote_title"].pack(anchor="w", pady=(5, 15), padx=10)
        # Frame dedicato agli scaglioni IRPEF (dinamici)
        self.frame_ord_aliquote_irpef = ctk.CTkFrame(frame_ord_aliquote, corner_radius=2)
        self.frame_ord_aliquote_irpef.pack(anchor="w", pady=(5, 15), padx=10, fill="x")
        # Itera in modo dinamico per gli scaglioni "aliquota_irpef_..."
        pattern = re.compile(r'^aliquota_irpef_(\d+)$')
        aliquote_keys = []
        for key in piva_ord_data.keys():
            match = pattern.match(key)
            if match:
                idx = int(match.group(1))
                aliquote_keys.append((idx, key))
        aliquote_keys.sort(key=lambda x: x[0])
        for idx_scaglione, key_scaglione in aliquote_keys:
            data = piva_ord_data.get(key_scaglione, {})
            value = data.get("value", "")
            reddito_min = data.get("reddito_min", "")
            reddito_max = data.get("reddito_max", "")
            description = data.get("description", key_scaglione)

            # Crea un container per questo scaglione
            scaglione_container = ctk.CTkFrame(self.frame_ord_aliquote_irpef, corner_radius=2)
            scaglione_container.pack(pady=5, fill="x", expand=True, padx=10)
            title_frame = ctk.CTkFrame(scaglione_container)
            title_frame.pack(fill="x", expand=True)
            lbl = ctk.CTkLabel(title_frame, text=description, font=("Arial", 16))
            lbl.pack(side=ctk.LEFT, anchor="w", padx=10, pady=5)

            #Aggiungo il container alla lista dei containers degli scaglioni
            self.scaglioni_containers[key_scaglione] = scaglione_container

            # Bottone per cancellare l'ultimo scaglione
            if idx_scaglione == len(aliquote_keys):
                self.delete_scaglione_button = ctk.CTkButton(title_frame, text="Cancella",
                                            command=lambda key=key_scaglione: self.delete_scaglione_irpef(key))

                self.delete_scaglione_button.pack(side=ctk.RIGHT, anchor="e", padx=10, pady=5)


            # Salva il riferimento al label
            self.ordinaria_labels[key_scaglione] = lbl
            self.title_frames[key_scaglione] = title_frame

            entries_frame = ctk.CTkFrame(scaglione_container)
            entries_frame.pack(pady=(0, 35), fill="x", expand=True)
            # Entry per "value"
            value_lbl = ctk.CTkLabel(entries_frame, text="Valore:")
            value_lbl.pack(side=ctk.LEFT, fill="x", expand=True)
            value_ent = ctk.CTkEntry(entries_frame)
            value_ent.insert(0, str(value))
            value_ent.pack(pady=(5, 15), padx=(5, 20), side=ctk.LEFT, fill="x", expand=True)
            # Entry per "reddito_min"
            min_lbl = ctk.CTkLabel(entries_frame, text="Reddito\nMinimo:")
            min_lbl.pack(side=ctk.LEFT, fill="x", expand=True)
            min_ent = ctk.CTkEntry(entries_frame)
            min_ent.insert(0, str(reddito_min))
            min_ent.pack(pady=(5, 15), padx=(5, 20), side=ctk.LEFT, fill="x", expand=True)
            # Entry per "reddito_max"
            max_lbl = ctk.CTkLabel(entries_frame, text="Reddito\nMassimo:")
            max_lbl.pack(side=ctk.LEFT, fill="x", expand=True)
            max_ent = ctk.CTkEntry(entries_frame)
            max_ent.insert(0, str(reddito_max))
            max_ent.pack(pady=(5, 15), padx=(5, 20), side=ctk.LEFT, fill="x", expand=True)
            # Salva i riferimenti in un dizionario usando la chiave dello scaglione
            self.ordinaria_irpef_entries[key_scaglione] = {
                "value": value_ent,
                "reddito_min": min_ent,
                "reddito_max": max_ent,
                "description": description
            }
        # Bottone per aggiungere un nuovo scaglione IRPEF
        self.add_scaglione_button = ctk.CTkButton(self.frame_ord_aliquote_irpef, text="Aggiungi Scaglione",
                                             command=lambda: self.add_scaglione_irpef())
        self.add_scaglione_button.pack(pady=(0, 20))

        # Sottosezione: Altri parametri (es. aliquota_inps, aliquota_cassa_inps, aliquota_ritenuta)
        for key in ["aliquota_inps", "aliquota_cassa_inps", "aliquota_ritenuta"]:
            if key in piva_ord_data:
                data = piva_ord_data.get(key, {})
                value = data.get("value", "")
                description = data.get("description", key)
                lbl = ctk.CTkLabel(frame_ord_aliquote, text=description, font=("Arial", 16))
                lbl.pack(anchor="w", padx=10, pady=5)
                self.ordinaria_labels[key] = lbl
                ent = ctk.CTkEntry(frame_ord_aliquote)
                ent.insert(0, str(value))
                ent.pack(anchor="w", fill="x", pady=(5, 15), padx=10)
                self.ordinaria_entries[key] = ent

        # Sottosezione: Imponibili
        frame_ord_imponibili = ctk.CTkFrame(section_ord, corner_radius=2)
        frame_ord_imponibili.pack(fill="x", pady=(35, 5), padx=(0, 10))
        self.ordinaria_labels["imponibili_title"] = ctk.CTkLabel(frame_ord_imponibili, text="Imponibili",
                                                                 font=("Arial", 16, "bold"))
        self.ordinaria_labels["imponibili_title"].pack(anchor="w", pady=(5, 15), padx=10)
        for key in ["imponibile_iva", "imponibile_ritenuta_acconto", "imponibile_cassa_inps", "imponibile_inps",
                    "imponibile_irpef"]:
            if key in piva_ord_data:
                data = piva_ord_data.get(key, {})
                value = data.get("value", "")
                description = data.get("description", key)
                lbl = ctk.CTkLabel(frame_ord_imponibili, text=description, font=("Arial", 16))
                lbl.pack(anchor="w", padx=10, pady=5)
                self.ordinaria_labels[key] = lbl
                ent = ctk.CTkEntry(frame_ord_imponibili)
                ent.insert(0, str(value))
                ent.pack(anchor="w", fill="x", pady=(5, 15), padx=10)
                self.ordinaria_imponibili_entries[key] = ent

        # Pulsante per salvare (command vuoto per ora)
        self.save_button = ctk.CTkButton(self.fiscal_settings_window, text="Salva Dati Fiscali", command=lambda: self.save_fiscal_settings())
        self.save_button.pack(pady=20)

    def add_scaglione_irpef(self):
        self.add_scaglione_button.pack_forget()
        description = ""
        key_scaglione = ""
        if len(self.scaglioni_containers) == 0:
            description = "Aliquota IRPEF per il primo scaglione di reddito"
            key_scaglione = "aliquota_irpef_1"
        elif len(self.scaglioni_containers) == 1:
            description = "Aliquota IRPEF per il secondo scaglione di reddito"
            key_scaglione = "aliquota_irpef_2"
        elif len(self.scaglioni_containers) == 2:
            description = "Aliquota IRPEF per il terzo scaglione di reddito"
            key_scaglione = "aliquota_irpef_3"
        elif len(self.scaglioni_containers) == 3:
            description = "Aliquota IRPEF per il quarto scaglione di reddito"
            key_scaglione = "aliquota_irpef_4"
        elif len(self.scaglioni_containers) == 4:
            description = "Aliquota IRPEF per il quinto scaglione di reddito"
            key_scaglione = "aliquota_irpef_5"
        elif len(self.scaglioni_containers) == 5:
            description = "Aliquota IRPEF per il sesto scaglione di reddito"
            key_scaglione = "aliquota_irpef_6"
        elif len(self.scaglioni_containers) == 6:
            ViewUtils.show_error_popup(self, "ERRORE", "Raggiunto numero massimo di scaglioni inseribili")
            self.add_scaglione_button.pack(pady=(0, 20))
            self.add_scaglione_button.configure(state=ctk.DISABLED)
            return

        # Crea un container per questo scaglione
        scaglione_container = ctk.CTkFrame(self.frame_ord_aliquote_irpef, corner_radius=2)
        scaglione_container.pack(pady=5, fill="x", expand=True, padx=10)
        title_frame = ctk.CTkFrame(scaglione_container)
        title_frame.pack(fill="x", expand=True)
        lbl = ctk.CTkLabel(title_frame, text=description, font=("Arial", 16))
        lbl.pack(side=ctk.LEFT, anchor="w", padx=10, pady=5)

        # Aggiungo il container alla lista dei containers degli scaglioni
        self.scaglioni_containers[key_scaglione] = scaglione_container

        # Salva il riferimento al label e al titolo
        self.ordinaria_labels[key_scaglione] = lbl
        self.title_frames[key_scaglione] = title_frame

        entries_frame = ctk.CTkFrame(scaglione_container)
        entries_frame.pack(pady=(0, 35), fill="x", expand=True)
        # Entry per "value"
        value_lbl = ctk.CTkLabel(entries_frame, text="Valore:")
        value_lbl.pack(side=ctk.LEFT, fill="x", expand=True)
        value_ent = ctk.CTkEntry(entries_frame)
        value_ent.insert(0, str(0))
        value_ent.pack(pady=(5, 15), padx=(5, 20), side=ctk.LEFT, fill="x", expand=True)
        # Entry per "reddito_min"
        min_lbl = ctk.CTkLabel(entries_frame, text="Reddito\nMinimo:")
        min_lbl.pack(side=ctk.LEFT, fill="x", expand=True)
        min_ent = ctk.CTkEntry(entries_frame)
        min_ent.insert(0, str(0))
        min_ent.pack(pady=(5, 15), padx=(5, 20), side=ctk.LEFT, fill="x", expand=True)
        # Entry per "reddito_max"
        max_lbl = ctk.CTkLabel(entries_frame, text="Reddito\nMassimo:")
        max_lbl.pack(side=ctk.LEFT, fill="x", expand=True)
        max_ent = ctk.CTkEntry(entries_frame)
        max_ent.insert(0, str(0))
        max_ent.pack(pady=(5, 15), padx=(5, 20), side=ctk.LEFT, fill="x", expand=True)
        # Salva i riferimenti in un dizionario usando la chiave dello scaglione
        self.ordinaria_irpef_entries[key_scaglione] = {
            "value": value_ent,
            "reddito_min": min_ent,
            "reddito_max": max_ent,
            "description": description
        }

        self.add_scaglione_button.pack(pady=(0, 20))
        self.delete_scaglione_button.pack_forget()
        self.delete_scaglione_button = ctk.CTkButton(self.title_frames[key_scaglione], text="Cancella", command=lambda: self.delete_scaglione_irpef(key_scaglione))
        self.delete_scaglione_button.pack(side=ctk.RIGHT, anchor="e", padx=10, pady=5)

    def delete_scaglione_irpef(self, key):
        self.scaglioni_containers[key].pack_forget()
        self.scaglioni_containers.pop(key)
        self.title_frames.pop(key)
        self.ordinaria_irpef_entries.pop(key)
        last_key = list(self.scaglioni_containers)[-1]

        self.delete_scaglione_button = ctk.CTkButton(self.title_frames[last_key], text="Cancella", command=lambda: self.delete_scaglione_irpef(last_key))
        self.delete_scaglione_button.pack(side=ctk.RIGHT, anchor="e", padx=10, pady=5)

        if len(self.scaglioni_containers) < 7:
            self.add_scaglione_button.configure(state=ctk.ACTIVE)

    def save_fiscal_settings(self):
        """
        Raccoglie tutti i valori presenti nelle entry delle tre tab (IVA, Forfettaria e Ordinaria)
        e li organizza in un dizionario strutturato in modo da poterlo passare al ConfigManager.

        La struttura restituita sarà simile a:
        {
          "iva": {
               "aliquota_iva_ordinaria": {"value": ..., "description": ...},
               "aliquota_iva_ridotta_1": {"value": ..., "description": ...},
               "aliquota_iva_ridotta_2": {"value": ..., "description": ...},
               "aliquota_iva_minima": {"value": ..., "description": ...}
          },
          "partita_iva_forfettaria": {
                "aliquota_irpef_min": {"value": ...},
                "aliquota_irpef_max": {"value": ...},
                "anni_agevolazione": {"value": ...},
                "aliquota_inps": {"value": ...},
                "aliquota_rivalsa_inps": {"value": ...},
                "imponibile": {"value": ...}
          },
          "partita_iva_ordinaria": {
                // Scaglioni dinamici IRPEF:
                "aliquota_irpef_1": {"value": ..., "reddito_min": ..., "reddito_max": ..., "description": ...},
                "aliquota_irpef_2": {"value": ..., "reddito_min": ..., "reddito_max": ..., "description": ...},
                // Altri parametri:
                "aliquota_inps": {"value": ...},
                "aliquota_cassa_inps": {"value": ...},
                "aliquota_ritenuta": {"value": ...},
                // Imponibili:
                "imponibile_iva": {"value": ...},
                "imponibile_ritenuta_acconto": {"value": ...},
                "imponibile_cassa_inps": {"value": ...},
                "imponibile_inps": {"value": ...},
                "imponibile_irpef": {"value": ...}
          }
        }
        """
        fiscal_data = {}

        # --- Sezione IVA ---
        iva_data = {}
        iva_keys = [
            "aliquota_iva_ordinaria",
            "aliquota_iva_ridotta_1",
            "aliquota_iva_ridotta_2",
            "aliquota_iva_minima"
        ]
        for key in iva_keys:
            if key in self.iva_entries:
                value = self.iva_entries[key].get()
                iva_data[key] = {"value": value}
            else:
                iva_data[key] = {"value": ""}
        fiscal_data["iva"] = iva_data


        # --- Sezione Partita IVA Forfettaria ---
        forf_data = {}
        for key in ["aliquota_irpef_min", "aliquota_irpef_max", "anni_agevolazione", "aliquota_inps",
                    "aliquota_rivalsa_inps", "imponibile"]:
            if key in self.forfettaria_entries:
                forf_data[key] = {"value": self.forfettaria_entries[key].get()}
            else:
                forf_data[key] = {"value": ""}
        fiscal_data["partita_iva_forfettaria"] = forf_data

        # --- Sezione Partita IVA Ordinaria ---
        ord_data = {}
        # Scaglioni IRPEF (dinamici)
        for key, widgets in self.ordinaria_irpef_entries.items():
            ord_data[key] = {
                "value": widgets["value"].get(),
                "reddito_min": widgets["reddito_min"].get(),
                "reddito_max": widgets["reddito_max"].get(),
                "description": widgets.get("description", "")
            }
        # Altri parametri fissi (es. aliquota_inps, aliquota_cassa_inps, aliquota_ritenuta)
        for key, widget in self.ordinaria_entries.items():
            ord_data[key] = {"value": widget.get()}
        # Imponibili
        for key, widget in self.ordinaria_imponibili_entries.items():
            ord_data[key] = {"value": widget.get()}
        fiscal_data["partita_iva_ordinaria"] = ord_data

        try:
            self.config_manager.update_fiscal_settings(fiscal_data)
            ViewUtils.show_confirm_popup(self.fiscal_settings_window, "INFO", "Dati fiscali aggiornati con successo")
        except Exception as e:
            ViewUtils.show_error_popup(self.fiscal_settings_window, "ERRORE",
                                       f"Impossibile aggiornare i dati fiscali: {str(e)}")


    #funzioni per la gestione delle spese ricorrenti
    def open_recurring_expenses_window(self):
        """Apre una finestra per gestire le spese ricorrenti."""
        # Crea la finestra di dialogo
        self.recurring_expenses_window = ctk.CTkToplevel(self)
        self.recurring_expenses_window.title("Gestione Spese Ricorrenti")
        self.recurring_expenses_window.geometry("1000x800+0+0")
        self.recurring_expenses_window.lift()
        self.recurring_expenses_window.grab_set()

        # Configurazione font
        self.label_font = ctk.CTkFont("Arial", size=16)  # Font più grande per i labels
        self.entry_font = ctk.CTkFont("Arial", size=14)
        self.button_font = ctk.CTkFont("Arial", size=16, weight="bold")

        # Dizionario per memorizzare i widget
        self.expense_widgets = {}

        # Bottone di salvataggio unico
        add_expense_button = ctk.CTkButton(
            self.recurring_expenses_window,
            text="Aggiungi una spesa ricorrente",
            command=self.add_recurring_expenses,
            font=self.button_font
        )
        add_expense_button.pack(pady=20)

        # Crea le tabs per ogni spesa
        self.expenses_tabview = ctk.CTkTabview(self.recurring_expenses_window)
        self.expenses_tabview.pack(padx=20, pady=20, fill="both", expand=True)

        # Aggiungi una tab per ogni spesa esistente
        for expense_key, expense in self.recurring_expenses_settings.items():
            tab_name = expense.description
            self.expenses_tabview.add(tab_name)
            tab = self.expenses_tabview.tab(tab_name)
            self.expenses_tabview._segmented_button.configure(font=self.button_font)

            # Crea il container scrollabile
            container = ctk.CTkScrollableFrame(tab)
            container.pack(fill="both", expand=True, padx=20, pady=10)

            # Memorizza i widget in un dizionario annidato
            self.expense_widgets[expense_key] = {}

            suppliers_map_list = self.supplier_controller.retrieve_suppliers_map_list()

            aliquote_list = [
                self.fiscal_settings.aliquota_iva.aliquota_iva_ordinaria,
                self.fiscal_settings.aliquota_iva.aliquota_iva_ridotta_1,
                self.fiscal_settings.aliquota_iva.aliquota_iva_ridotta_2,
                self.fiscal_settings.aliquota_iva.aliquota_iva_minima
            ]

            accounts = self.account_controller.retrieve_accounts_map_list()

            # Campi modificabili
            fields = [
                ('amount', 'Importo:', 'entry', float),
                ('supplier', 'Fornitore:', 'dropdown', [supplier[DBSuppliersColumns.NAME.value] for supplier in suppliers_map_list]),
                ('category', 'Categoria:', 'dropdown', [value for key, value in self.catalogo_elenchi["expenses_category"]]),
                ('iva', 'IVA:', 'dropdown', [str(aliquota) for aliquota in aliquote_list]),
                ('account', 'Conto:', 'dropdown', [account[DBAccountsColumns.NAME.value] for account in accounts]),
                ('frequency', 'Frequenza:', 'dropdown', [freq.value for freq in ExpenseController.RecurringExpensesFrequencies])
            ]

            for field, label_text, field_type, options in fields:
                frame = ctk.CTkFrame(container)
                frame.pack(fill="x", pady=15)

                lbl = ctk.CTkLabel(frame, text=label_text, width=120, font=self.label_font)
                lbl.pack(side="left", padx=5)

                if field_type == 'entry':
                    widget = ctk.CTkEntry(frame, font=self.entry_font)
                    widget.insert(0, str(getattr(expense, field)))
                elif field_type == 'dropdown':
                    # per la categoria, aggiungo l'opzione ADD e il command
                    if field == 'category':
                        widget = ctk.CTkOptionMenu(
                            master=frame,
                            values=options,
                            font=self.entry_font,
                            dropdown_font=self.entry_font,
                            command=lambda sel, ek=expense_key: self.open_add_expense_category(ek, sel)
                        )
                        # imposto valore corrente
                        current = getattr(expense, field)
                        widget.set(current if current in options else options[0])
                    else:
                        widget = ctk.CTkOptionMenu(
                            master=frame,
                            values=options,
                            font=self.entry_font,
                            dropdown_font=self.entry_font
                        )
                        current = getattr(expense, field)
                        widget.set(current if current in options else options[0])

                widget.pack(fill="x", expand=True, padx=5)
                self.expense_widgets[expense_key][field] = widget

            # Campi booleani con radio button
            for field, label_text in [('deductible', 'Deduzione:')]:
                frame = ctk.CTkFrame(container)
                frame.pack(fill="x", pady=15)

                lbl = ctk.CTkLabel(frame, text=label_text, width=120, font=self.label_font)
                lbl.pack(side="left", padx=5)

                radio_frame = ctk.CTkFrame(frame)
                radio_frame.pack(side="left", fill="x", expand=True)

                var = ctk.StringVar(value="Sì" if getattr(expense,field) else "No")

                for option in ["Sì", "No"]:
                    rb = ctk.CTkRadioButton(
                        radio_frame,
                        text=option,
                        variable=var,
                        value=option,
                        font=self.entry_font
                    )
                    rb.pack(side="left", padx=10)

                self.expense_widgets[expense_key][field] = var


            for field, label_text in [('status', 'Stato:')]:
                frame = ctk.CTkFrame(container)
                frame.pack(fill="x", pady=15)

                lbl = ctk.CTkLabel(frame, text=label_text, width=120, font=self.label_font)
                lbl.pack(side="left", padx=5)

                radio_frame = ctk.CTkFrame(frame)
                radio_frame.pack(side="left", fill="x", expand=True)

                var = ctk.StringVar(value=ExpenseController.RecurringExpensesStatus.ATTIVA.value if getattr(expense, field) else ExpenseController.RecurringExpensesStatus.SOSPESA.value)

                for option in [stati.value for stati in ExpenseController.RecurringExpensesStatus]:
                    rb = ctk.CTkRadioButton(
                        radio_frame,
                        text=option,
                        variable=var,
                        value=option,
                        font=self.entry_font
                    )
                    rb.pack(side="left", padx=10)

                self.expense_widgets[expense_key][field] = var

        # Bottone di salvataggio unico
        save_button = ctk.CTkButton(
            self.recurring_expenses_window,
            text="Salva Tutte le Modifiche",
            command=self.save_recurring_expenses,
            font=self.button_font
        )
        save_button.pack(pady=20)

    def save_recurring_expenses(self):
        """Salva tutte le modifiche, comprese le nuove spese ricorrenti."""
        new_data = {}

        for expense_key, widgets in self.expense_widgets.items():
            # Se è la tab “Nuova Spesa”, creo un nuovo key
            if expense_key == "Nuova Spesa":
                raw_name = widgets["name"].get().strip()
                if not raw_name:
                    continue  # nulla da salvare se non c'è nome

                # description scalare in uppercase
                description = raw_name.upper()

                # chiave normalizzata per il JSON
                new_key = raw_name.lower().replace(" ", "_")

                # campi basati sui widget della nuova tab
                fields = {
                    "description": description,
                    "amount": widgets["amount"].get(),
                    "supplier": widgets["supplier"].get(),
                    "deductible": widgets["deductible"].get(),
                    "category": widgets["category"].get(),
                    "iva": widgets["iva"].get(),
                    "account": widgets["account"].get(),
                    "frequency": widgets["frequency"].get(),
                    "status": widgets["status"].get(),
                }
                new_data[new_key] = fields

            else:
                # Spesa già esistente: mantengo la chiave e la description
                desc = self.recurring_expenses_settings[expense_key].description
                fields = {
                    "description": desc,
                    "amount": widgets["amount"].get(),
                    "supplier": widgets["supplier"].get(),
                    "deductible": widgets["deductible"].get(),
                    "category": widgets["category"].get(),
                    "iva": widgets["iva"].get(),
                    "account": widgets["account"].get(),
                    "frequency": widgets["frequency"].get(),
                    "status": widgets["status"].get(),
                }
                new_data[expense_key] = fields

        try:
            # usa la funzione ad hoc che gestisce description scalar e value dict
            self.config_manager.update_recurring_expenses(new_data)
            ViewUtils.show_confirm_popup(
                self.recurring_expenses_window,
                title="Successo",
                message="Modifiche salvate correttamente!"
            )
        except Exception as e:
            ViewUtils.show_error_popup(
                self.recurring_expenses_window,
                title="Errore",
                message=f"Salvataggio fallito: {str(e)}"
            )

    def open_add_expense_category(self, expense_key, selected_value):
        sector_dict = dict(self.catalogo_elenchi["expenses_category"])
        if selected_value == sector_dict.get("ADD_CATEGORY"):
            self.current_expense_for_category = expense_key
            self.add_category_window = ctk.CTkToplevel(self)
            self.add_category_window.title("Aggiungi una nuova categoria di spesa")

            # Assicurati che la finestra rimanga sopra
            self.add_category_window.lift()  # Porta la finestra sopra quella principale
            self.add_category_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

            self.add_category_window.geometry("400x300")

            self.expense_category_window_Frame = ctk.CTkFrame(self.add_category_window)
            self.expense_category_window_Frame.pack(fill="both", expand=True)

            ctk.CTkLabel(self.expense_category_window_Frame, text="Aggiungi una caategoria di spesa alla lista\nsepara parole diverse solo tramite spazio").pack(padx=10, pady=(25, 0))

            self.add_category_entry = ctk.CTkEntry(self.expense_category_window_Frame)
            self.add_category_entry.pack(padx=10, pady=5, fill="x", expand=True)

            ctk.CTkButton(self.expense_category_window_Frame, text="Aggiungi una categoria", command=self.save_expense_category).pack(padx=10, pady=(15, 10))

        else: return

    def save_expense_category(self):
        new_category = self.add_category_entry.get()
        new_category_key = ControllerUtils.normalize_string_for_key(new_category)
        try:
            self.config_manager.update_list_field("expenses_category", new_category_key, new_category, "update")
        except Exception as e:
            ViewUtils.show_error_popup(self.add_category_window, "Errore", f"Impossibile aggiungere il nuovo settore: {str(e)}")
            return

        widget = self.expense_widgets[self.current_expense_for_category]["category"]
        widget.configure(values=widget._values + [new_category])  # aggiorno la lista delle opzioni
        widget.set(new_category)
        self.add_category_window.destroy()

    def add_recurring_expenses(self):
        tab_name = "Nuova Spesa"
        self.expenses_tabview.add(tab_name)
        tab = self.expenses_tabview.tab(tab_name)

        # Container scrollabile
        container = ctk.CTkScrollableFrame(tab)
        container.pack(fill="both", expand=True, padx=20, pady=10)

        # Creiamo un expense_key unico per questa nuova spesa
        expense_key = tab_name
        self.expense_widgets[expense_key] = {}

        # Prepara i valori per dropdown
        suppliers_map_list = self.supplier_controller.retrieve_suppliers_map_list()
        suppliers_opts = [s[DBSuppliersColumns.NAME.value] for s in suppliers_map_list]

        aliquote_list = [
            self.fiscal_settings.aliquota_iva.aliquota_iva_ordinaria,
            self.fiscal_settings.aliquota_iva.aliquota_iva_ridotta_1,
            self.fiscal_settings.aliquota_iva.aliquota_iva_ridotta_2,
            self.fiscal_settings.aliquota_iva.aliquota_iva_minima
        ]
        iva_opts = [str(a) for a in aliquote_list]

        accounts = self.account_controller.retrieve_accounts_map_list()
        account_opts = [a[DBAccountsColumns.NAME.value] for a in accounts]

        category_opts = [v for _, v in self.catalogo_elenchi["expenses_category"]]
        freq_opts = [f.value for f in ExpenseController.RecurringExpensesFrequencies]

        # Definizione dei campi, con type e options
        fields = [
            ('name', 'Nome Spesa:', 'entry', None),
            ('amount', 'Importo:', 'entry', None),
            ('supplier', 'Fornitore:', 'dropdown', suppliers_opts),
            ('category', 'Categoria:', 'dropdown', category_opts),
            ('iva', 'IVA:', 'dropdown', iva_opts),
            ('account', 'Conto:', 'dropdown', account_opts),
            ('frequency', 'Frequenza:', 'dropdown', freq_opts),
            ('deductible', 'Deducibile:', 'radio', ["Sì", "No"]),
            ('status', 'Stato:', 'radio', [st.value for st in ExpenseController.RecurringExpensesStatus]),
        ]

        for field, label_text, field_type, options in fields:
            frame = ctk.CTkFrame(container)
            frame.pack(fill="x", pady=10)

            lbl = ctk.CTkLabel(frame, text=label_text, width=140, font=self.label_font)
            lbl.pack(side="left", padx=5)

            # Entry
            if field_type == 'entry':
                widget = ctk.CTkEntry(frame, font=self.entry_font)
                # vuoto di default
            # Dropdown
            elif field_type == 'dropdown':
                widget = ctk.CTkOptionMenu(
                    master=frame,
                    values=options,
                    font=self.entry_font,
                    dropdown_font=self.entry_font
                )
                widget.set(options[0] if options else "")
            # Radio
            else:  # 'radio'
                var = ctk.StringVar(value=options[0] if options else "")
                radio_frame = ctk.CTkFrame(frame)
                radio_frame.pack(side="left", fill="x", expand=True)
                for opt in options:
                    rb = ctk.CTkRadioButton(
                        radio_frame, text=opt,
                        variable=var, value=opt,
                        font=self.entry_font
                    )
                    rb.pack(side="left", padx=10)
                widget = var

            # Pack widget (entry or dropdown)
            if field_type in ('entry', 'dropdown'):
                widget.pack(fill="x", expand=True, padx=5)

            self.expense_widgets[expense_key][field] = widget

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
from datetime import datetime
import os, re

from customtkinter import CTkFrame

from Views.View_utils import ViewUtils

from Controllers import AccountController, ValidationUtils, UserController
from Model import DBUsersColumns, DBAccountsColumns, DBInvoicesColumns, DBExpensesColumns, DBProductionsColumns, \
    DBSalariesColumns
from Fatturazione_elettronica_API import FatturazioneElettronicaProvider

class UsersView(ctk.CTkFrame):
    def __init__(self, db_model, user_controller, account_controller, production_controller, fiscal_settings, tab, analyzer, event_bus):
        super().__init__(tab)

        self.db_model = db_model
        self.user_controller = user_controller
        self.account_controller = account_controller
        self.production_controller = production_controller
        self.tab = tab
        self.fiscal_settings = fiscal_settings
        self.analyzer = analyzer
        self.event_bus = event_bus

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

        # Container principale
        self.main_container = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.detail_container = ctk.CTkFrame(self, fg_color="#2b2b2b")

        # Vista dettaglio
        self.user_detail_view = UserDetailView(
            parent=self,
            back_callback=self.show_main_view,
            user_controller=user_controller,
            account_controller=account_controller,
            production_controller=production_controller,
            db_model=db_model,
            fiscal_settings=self.fiscal_settings,
            analyzer=self.analyzer,
            event_bus = self.event_bus
        )

        self.configure(fg_color="#333333")

        # Inizializza la vista principale
        self.create_user_tab()
        self.show_main_view()

    def create_user_tab(self):
        """Crea la UI principale nella main_container"""

        self.user_description = ctk.CTkLabel(self.main_container, text="Gestisci gli utenti", font=("Arial", 14))
        self.user_description.pack(pady=(50, 25))

        # Area per le cards degli utenti (simulata qui per ora)
        self.user_card_area = ctk.CTkFrame(self.main_container, fg_color="#2b2b2b")
        self.user_card_area.pack(fill= "y", expand=True, pady=20)


        self.user_card_area1 = ctk.CTkFrame(self.main_container, fg_color="#2b2b2b")
        self.user_card_area1.pack(fill= "y", expand=True, pady=20)


        # Bottone per aggiungere un nuovo utente
        self.add_user_button = ctk.CTkButton(self.main_container, text="Aggiungi Nuovo Utente", font=("Arial", 15, "bold"),  command=self.open_add_user_window)
        self.add_user_button.configure(width=200, height=50)
        self.add_user_button.pack(anchor="s", pady=20)


        #aggiungo una card per ogni utente
        for user in self.users_list:
            self.add_user_card(user[f"{DBUsersColumns.ID.value}"], user[f"{DBUsersColumns.FIRST_NAME.value}"], user[f"{DBUsersColumns.LAST_NAME.value}"], user[f"{DBUsersColumns.PARTITA_IVA.value}"], user[DBUsersColumns.PHOTO_PATH.value], user[f"{DBUsersColumns.EMAIL.value}"])

    def show_main_view(self):
        """Torna alla vista principale"""
        self.user_detail_view.pack_forget()
        self.main_container.pack(fill='both', expand=True)

    def open_user_detail_tab(self, user_id):
        """Mostra la vista dettaglio utente"""
        self.main_container.pack_forget()
        self.user_detail_view.pack(fill='both', expand=True)
        self.user_detail_view.create_detail_tab(user_id)  # Ricrea i contenuti ogni volta

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
        self.image_name = ctk.CTkLabel(self.user_window_scrollableFrame, text="ancora nessuna immagine selezionata")
        self.image_name.pack(pady=(5, 15))

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
        accounts_map_list = self.account_controller.retrieve_accounts_map_list()
        self.conto_corrente_combobox = ctk.CTkOptionMenu(self.user_window_scrollableFrame, values=[account[DBAccountsColumns.NAME.value] for account in accounts_map_list])
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

        #prendo l'id del conto
        conto = self.account_controller.retrieve_account_map_by_name(self.conto_corrente_combobox.get().strip())
        conto_id = conto[DBAccountsColumns.ID.value]

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
            DBUsersColumns.CONTO_CORRENTE_ID.value: conto_id,  # Da aggiornare se necessario
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
        self.image_name = ctk.CTkLabel(self.modify_window_scrollableFrame, text="ancora nessuna immagine selezionata")
        self.image_name.pack(pady=(5, 15))

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
            self.image_path.set(photo_path)  # Memorizza il percorso dell'immagine
            self.image_name.configure(text=f"{os.path.basename(photo_path)}")

            """try:
                # Carica e ridimensiona l'immagine per l'anteprima
                img = Image.open(path)
                img.thumbnail((150, 150))  # Ridimensiona mantenendo le proporzioni
                self.image_preview_photo = ImageTk.PhotoImage(
                    img)  # Mantieni un riferimento per evitare garbage collection
                self.image_preview.configure(image=self.image_preview_photo, text="")  # Mostra l'immagine
            except Exception as e:
                self.image_preview.configure(text="Errore nel caricamento dell'immagine")
                print(f"Errore nel caricamento dell'immagine: {e}")"""
        else:
            self.image_name.configure(text=f"percorso all'immagine non valido")



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
        user_card.pack(side="left", pady=0, padx=25)
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

        self.detail_button = ctk.CTkButton(user_card, text="Dettaglio", command=lambda uid=user_id: self.open_user_detail_tab(uid))
        self.detail_button.pack(pady=10)

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
            self.image_name.configure(text=f"{os.path.basename(path)}")

            """try:
                # Carica e ridimensiona l'immagine per l'anteprima
                img = Image.open(path)
                img.thumbnail((150, 150))  # Ridimensiona mantenendo le proporzioni
                self.image_preview_photo = ImageTk.PhotoImage(
                    img)  # Mantieni un riferimento per evitare garbage collection
                self.image_preview.configure(image=self.image_preview_photo, text="")  # Mostra l'immagine
            except Exception as e:
                self.image_preview.configure(text="Errore nel caricamento dell'immagine")
                print(f"Errore nel caricamento dell'immagine: {e}")"""
        else:
            self.image_name.configure(text=f"percorso all'immagine non valido")

        # Assicurati che la finestra rimanga sopra
        self.add_user_window.lift()  # Porta la finestra sopra quella principale
        self.add_user_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

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






class UserDetailView(ctk.CTkFrame):
    def __init__(self, parent, back_callback, user_controller, account_controller, production_controller, db_model, fiscal_settings, analyzer, event_bus):
        super().__init__(parent)
        self.user_controller = user_controller
        self.account_controller = account_controller
        self.db_model = db_model
        self.back_callback = back_callback
        self.production_controller = production_controller
        self.fiscal_settings = fiscal_settings
        self.event_bus = event_bus
        self.current_user_id = None
        self.analyzer = analyzer

        # Widgets persistenti (vanno creati una volta sola)
        self.head_frame = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.back_button = ctk.CTkButton(
            self.head_frame,
            text="Elenco Utenti",
            command=self._cleanup_and_go_back
        )
        self.title_label = ctk.CTkLabel(self.head_frame, font=("Arial", 22, "bold"))

        self.user_info_widgets: dict[str, ctk.CTkEntry | ctk.CTkOptionMenu] = {}

        self.nome_conto_string = "CONTO"

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

    def create_detail_tab(self, user_id):
        """Ricrea la vista dettaglio per un utente specifico"""
        self.current_user_id = user_id

        # 1. Pulizia dei widget precedenti
        self._clear_content()

        # 2. Caricamento dati
        user = self.user_controller.retrieve_user_map_by_id(user_id)

        #prendo il nome del conto:
        id_conto = user[DBUsersColumns.CONTO_CORRENTE_ID.value]
        conto = self.account_controller.retrieve_account_map_by_id(id_conto)
        nome_conto = conto[DBAccountsColumns.NAME.value] if conto else "Conto non trovato"

        regime = user[DBUsersColumns.REGIME_FISCALE.value]

        user[self.nome_conto_string] = nome_conto

        # 3. Aggiornamento elementi persistenti
        self.title_label.configure(
            text=f"{user[DBUsersColumns.FIRST_NAME.value]} {user[DBUsersColumns.LAST_NAME.value]}")

        # 4. Creazione contenuti dinamici
        self._create_user_info_section(user)
        self.toggle_edit(self.content_frame)

        self.wrapper_frame = ctk.CTkFrame(self.content_frame, fg_color="#333333")
        self.wrapper_frame.pack(padx=25, pady=(90, 0), fill="both", expand=True)
        self.wrapper_frame2 = ctk.CTkFrame(self.content_frame, fg_color="#333333")
        self.wrapper_frame2.pack(padx=25, pady=(90, 90), fill="both", expand=True)
        self._create_invoices_history()
        self._create_salary_history()
        self._create_anticipated_expenses_history()
        if regime == UserController.RegimeFiscale.ORDINARIO.value:
            self._create_deduz_expenses_history()

        self._create_fiscal_data_section()
        self._create_taxes_section()
        if regime == UserController.RegimeFiscale.ORDINARIO.value:
            self._create_iva_section()

    def _clear_content(self):
        """Distrugge tutti i widget dinamici"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def _create_user_info_section(self, user_data):
        # Dizionari per la configurazione

        self.entry_fields = {
            # Sezione Anagrafica
            DBUsersColumns.FIRST_NAME.value: {
                "type": ctk.CTkEntry,
                "label": "Nome",
                "section": "Dati Anagrafici"
            },
            DBUsersColumns.LAST_NAME.value: {
                "type": ctk.CTkEntry,
                "label": "Cognome",
                "section": "Dati Anagrafici"
            },
            DBUsersColumns.EMAIL.value: {
                "type": ctk.CTkEntry,
                "label": "Email",
                "section": "Dati Anagrafici"
            },
            DBUsersColumns.TELEFONO.value: {
                "type": ctk.CTkEntry,
                "label": "Telefono",
                "section": "Dati Anagrafici"
            },

            # Sezione Fiscale
            DBUsersColumns.PARTITA_IVA.value: {
                "type": ctk.CTkEntry,
                "label": "Partita IVA",
                "section": "Dati Fiscali"
            },
            DBUsersColumns.CODICE_FISCALE.value: {
                "type": ctk.CTkEntry,
                "label": "Codice Fiscale",
                "section": "Dati Fiscali"
            },
            DBUsersColumns.REGIME_FISCALE.value: {
                "type": ctk.CTkOptionMenu,
                "label": "Regime Fiscale",
                "section": "Dati Fiscali",
                "values": [item.value for item in self.user_controller.RegimeFiscale]
            },
            DBUsersColumns.ANNO_APERTURA_PIVA.value: {
                "type": ctk.CTkOptionMenu,
                "label": "Anno Apertura P.IVA",
                "section": "Dati Fiscali",
                "values": [str(y) for y in range(2000, datetime.now().year + 1)]
            },
            DBUsersColumns.REDDITO_ESTERNO.value: {
                "type": ctk.CTkEntry,
                "label": "Reddito Esterno",
                "section": "Dati Fiscali"
            },
            DBUsersColumns.SPESE_DEDOTTE_ESTERNE.value: {
                "type": ctk.CTkEntry,
                "label": "Spese Dedotte Esterne",
                "section": "Dati Fiscali"
            },
            DBUsersColumns.LAST_YEAR_IRPEF_ACCONTO.value: {
                "type": ctk.CTkEntry,
                "label": "Acconto IRPEF anno scorso",
                "section": "Dati Fiscali"
            },
            DBUsersColumns.LAST_YEAR_INPS_ACCONTO.value: {
                "type": ctk.CTkEntry,
                "label": "Acconto INPS anno scorso",
                "section": "Dati Fiscali"
            },

            # Sezione Provider
            DBUsersColumns.PROVIDER_FATTURE.value: {
                "type": ctk.CTkOptionMenu,
                "label": "Provider FE",
                "section": "Fatturazione Elettronica",
                "values": [item.value for item in FatturazioneElettronicaProvider]
            },
            DBUsersColumns.USERNAME_PROVIDER.value: {
                "type": ctk.CTkEntry,
                "label": "Username FE",
                "section": "Fatturazione Elettronica",
                "password": True
            },
            DBUsersColumns.PASSWORD_PROVIDER.value: {
                "type": ctk.CTkEntry,
                "label": "Password FE",
                "section": "Fatturazione Elettronica",
                "password": True
            },

            # Sezione Conto Corrente
            self.nome_conto_string: {
                "type": ctk.CTkOptionMenu,
                "label": "Conto Associato",
                "section": "Conto Corrente",
                "values": [acc[DBAccountsColumns.NAME.value] for acc in
                           self.account_controller.retrieve_accounts_map_list()]
            },

            # Immagine Profilo
            DBUsersColumns.PHOTO_PATH.value: {
                "type": ctk.CTkEntry,
                "label": "Percorso Immagine",
                "section": "Immagine Profilo"
            },

            # status
            DBUsersColumns.STATUS.value: {
                "type": ctk.CTkOptionMenu,
                "label": "Status",
                "section": "Status",
                "values": [item.value for item in self.user_controller.UserStatus]
            }
        }

        self.error_fields = {
            DBUsersColumns.FIRST_NAME.value: "Il nome non può essere vuoto",
            DBUsersColumns.LAST_NAME.value: "Il cognome non può essere vuoto",
            DBUsersColumns.PARTITA_IVA.value: "Partita IVA non valida (11 cifre)",
            DBUsersColumns.REDDITO_ESTERNO.value: "Inserire cifra numerica con due cifre decimali seprate da \".\" ",
            DBUsersColumns.SPESE_DEDOTTE_ESTERNE.value: "Inserire cifra numerica con due cifre decimali seprate da \".\" ",
            DBUsersColumns.LAST_YEAR_IRPEF_ACCONTO.value: "Inserire cifra numerica con due cifre decimali seprate da \".\" ",
            DBUsersColumns.LAST_YEAR_INPS_ACCONTO.value: "Inserire cifra numerica con due cifre decimali seprate da \".\" ",
            DBUsersColumns.EMAIL.value: "Formato email non valido"
        }

        validation_rules = {
            DBUsersColumns.FIRST_NAME.value: (
                lambda val: val.strip() != "",
                "Il nome non può essere vuoto"
            ),
            DBUsersColumns.LAST_NAME.value: (
                lambda val: val.strip() != "",
                "Il cognome non può essere vuoto"
            ),
            DBUsersColumns.PARTITA_IVA.value: (
                lambda val: len(val) == 11 and val.isdigit(),
                "Partita IVA non valida (11 cifre)"
            ),
            DBUsersColumns.EMAIL.value: (
                lambda val: re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", val),
                "Formato email non valido"
            ),
            DBUsersColumns.LAST_YEAR_IRPEF_ACCONTO.value: (
                lambda val: re.fullmatch(r"^\d+(\.\d{2})?$", val),
                "Inserire cifra numerica con due cifre decimali seprate da \".\" "
            ),
            DBUsersColumns.LAST_YEAR_INPS_ACCONTO.value: (
                lambda val: re.fullmatch(r"^\d+(\.\d{2})?$", val),
                "Inserire cifra numerica con due cifre decimali seprate da \".\" "
            ),
            DBUsersColumns.REDDITO_ESTERNO.value: (
                lambda val: re.fullmatch(r"^\d+(\.\d{2})?$", val),
                "Inserire cifra numerica con due cifre decimali seprate da \".\" "
            ),
            DBUsersColumns.SPESE_DEDOTTE_ESTERNE.value: (
                lambda val: re.fullmatch(r"^\d+(\.\d{2})?$", val),
                "Inserire cifra numerica con due cifre decimali seprate da \".\" "
            )
        }

        # Inizializzazione strutture dati
        self.user_info_widgets = {}
        self.error_labels = {}
        sections = {}

        # Creazione frame principale
        info_frame = ctk.CTkFrame(self.content_frame, border_width=2, border_color="#2659ab")
        info_frame.pack(fill="both", expand=True, pady=10, padx=25)

        # Configurazione griglia
        info_frame.grid_columnconfigure(0, weight=1, uniform="col")
        info_frame.grid_columnconfigure(1, weight=1, uniform="col")
        info_frame.grid_columnconfigure(2, weight=1, uniform="col")

        # Creazione sezioni
        sections_order = [
            "Dati Anagrafici",
            "Dati Fiscali",
            "Fatturazione Elettronica",
            "Conto Corrente",
            "Immagine Profilo",
            "Status"
        ]

        # Crea i frame per ogni sezione
        for i, section_name in enumerate(sections_order):
            frame = ctk.CTkFrame(info_frame)
            column = i if i <= 2 else i-3
            frame.grid(row=0 if i <= 2 else 1 , column=column, sticky="nsew", padx=(15, 7) if column != 2 else 15, pady=(15, 10))
            frame.grid_columnconfigure(1, weight=1)
            sections[section_name] = {
                "frame": frame,
                "row": 0
            }
            ctk.CTkLabel(frame, text=section_name, font=("Arial", 14, "bold")).grid(
                row=0, column=0, columnspan=2, sticky="w", padx=15, pady=5
            )
            sections[section_name]["row"] += 1


        # Popolamento delle sezioni
        for field, config in self.entry_fields.items():
            if (str(user_data[DBUsersColumns.REGIME_FISCALE.value]) == str(self.user_controller.RegimeFiscale.FORFETTARIO.value) and field == DBUsersColumns.SPESE_DEDOTTE_ESTERNE.value):
                continue

            section = sections[config["section"]]
            frame = section["frame"]
            row = section["row"]

            # Creazione label
            lbl = ctk.CTkLabel(frame, text=config["label"] + ":")
            lbl.grid(row=row, column=0, sticky="w", padx=(15, 5), pady=(2, 5) if field in validation_rules.keys() else (2, 25))

            # Creazione widget
            if config["type"] == ctk.CTkOptionMenu:
                widget = config["type"](frame, values=config.get("values", []))
                widget.set(user_data.get(field, config.get("values", [""])[0]))
            else:
                widget = config["type"](frame, show="*" if config.get("password", False) else "")
                # Converti esplicitamente a stringa prima dell'inserimento
                value = str(user_data.get(field, ""))
                widget.insert(0, value)


            widget.grid(row=row, column=1, sticky="ew", padx=(5, 15), pady=(2, 5) if field in validation_rules.keys() else (2, 35))
            self.user_info_widgets[field] = widget

            if field in validation_rules:
                validation_func, error_message = validation_rules[field]

                error_lbl = ctk.CTkLabel(frame, text="", text_color="#e8e5dc")
                error_lbl.grid(row=row + 1, column=1, sticky="w", padx=5, pady=(0, 10))
                self.error_labels[field] = error_lbl

                widget.bind("<FocusOut>",
                            lambda e, w=widget, vl=validation_func, el=error_lbl, em=error_message:
                            ViewUtils.validate_entry(w, vl, el, em)
                            )

                section["row"] += 2
            else:
                section["row"] += 1


        # Bottone Salva
        self.save_info_btn = ctk.CTkButton(info_frame, text="Salva Modifiche", command=self.save_info_mod)
        self.save_info_btn.grid(row=2, column=1, pady=(10, 30))

    def toggle_edit(self, parent):
        """
        Abilita o disabilita la modifica dei widget nella finestra di modifica utente.
        """
        # Determina lo stato (abilitato/disabilitato) in base al valore dello switch
        state = ctk.NORMAL if self.switch_modify.get() else ctk.DISABLED

        # Cambia anche lo stato del pulsante Salva
        self.save_info_btn.configure(state=state)

        for w in parent.winfo_children():
            # se è un Entry
            if isinstance(w, ctk.CTkEntry):
                w.configure(state=state, text_color="#636363" if state == ctk.DISABLED else "#c2c2c2")
            # se è un OptionMenu
            elif isinstance(w, ctk.CTkOptionMenu):
                w.configure(state=state)
            # se è un Frame/container, scendi ricorsivamente
            elif isinstance(w, (ctk.CTkFrame, ctk.CTkScrollableFrame, ctk.CTkToplevel)):
                self.toggle_edit(w)

    def save_info_mod(self):
        """Salva i dati dell'utente tramite il controller"""

        nome_conto = self.user_info_widgets[self.nome_conto_string].get()
        conto = self.account_controller.retrieve_account_map_by_name(nome_conto)
        id_conto = conto[DBAccountsColumns.ID.value] if conto else None

        user_data = {
            DBUsersColumns.FIRST_NAME.value: self.user_info_widgets[DBUsersColumns.FIRST_NAME.value].get().strip(),
            DBUsersColumns.LAST_NAME.value: self.user_info_widgets[DBUsersColumns.LAST_NAME.value].get().strip(),
            DBUsersColumns.PARTITA_IVA.value: self.user_info_widgets[DBUsersColumns.PARTITA_IVA.value].get().strip(),
            DBUsersColumns.CODICE_FISCALE.value: self.user_info_widgets[DBUsersColumns.CODICE_FISCALE.value].get().strip(),
            DBUsersColumns.TELEFONO.value: self.user_info_widgets[DBUsersColumns.TELEFONO.value].get().strip(),
            DBUsersColumns.EMAIL.value: self.user_info_widgets[DBUsersColumns.EMAIL.value].get().strip(),
            DBUsersColumns.REDDITO_ESTERNO.value: self.user_info_widgets[DBUsersColumns.REDDITO_ESTERNO.value].get().strip(),
            DBUsersColumns.SPESE_DEDOTTE_ESTERNE.value: self.user_info_widgets[DBUsersColumns.SPESE_DEDOTTE_ESTERNE.value].get().strip(),
            DBUsersColumns.PROVIDER_FATTURE.value: self.user_info_widgets[DBUsersColumns.PROVIDER_FATTURE.value].get(),
            DBUsersColumns.USERNAME_PROVIDER.value: self.user_info_widgets[DBUsersColumns.USERNAME_PROVIDER.value].get().strip(),
            DBUsersColumns.PASSWORD_PROVIDER.value: self.user_info_widgets[DBUsersColumns.PASSWORD_PROVIDER.value].get().strip(),
            DBUsersColumns.REGIME_FISCALE.value: self.user_info_widgets[DBUsersColumns.REGIME_FISCALE.value].get(),
            DBUsersColumns.PHOTO_PATH.value: self.user_info_widgets[DBUsersColumns.PHOTO_PATH.value].get().strip(),
            DBUsersColumns.CONTO_CORRENTE_ID.value: id_conto,  # Da aggiornare se necessario
            DBUsersColumns.ANNO_APERTURA_PIVA.value: self.user_info_widgets[DBUsersColumns.ANNO_APERTURA_PIVA.value].get(),
            DBUsersColumns.STATUS.value: self.user_info_widgets[DBUsersColumns.STATUS.value].get(),
        }

        # Chiamata al controller per salvare i dati
        success, message = self.user_controller.update_user(self.current_user_id, user_data)
        if success:
            print(f"User {user_data[DBUsersColumns.FIRST_NAME.value]} {user_data[DBUsersColumns.LAST_NAME.value]} salvato con successo")
            ViewUtils.show_confirm_popup_2(self.content_frame, "SALVATAGGIO COMPLETATO", message)
            self.switch_modify.deselect()
            self.toggle_edit(self.content_frame)
            self.toggle_taxes()
        else:
            # Mostra il messaggio d'errore
            print(message)
            ViewUtils.show_error_popup(self.content_frame, "ERRORE", message)

    def _create_invoices_history(self):
        """Crea la sezione storico fatture"""
        section_frame = ctk.CTkFrame(self.wrapper_frame, border_width=2, border_color="#2659ab")
        section_frame.pack(fill="both", side="left", expand=True, pady=0, padx=(0, 30))

        ctk.CTkLabel(section_frame, text="FATTURE WILLOW", font=("Arial", 14, "bold")).pack(anchor="w", pady=(10, 10), padx=10)

        global_infos = {
            "TOTALE FATTURATO WILLOW" : {
                "value" : self.user_controller.calcola_tot_fatturato_utente(self.current_user_id),
                "uom" : "€"
            }
        }

        self.global_infos_invoices_widgets = ViewUtils.construct_global_infos_cards(section_frame, global_infos)

        # tabella invoices
        invoices_frame = ctk.CTkScrollableFrame(section_frame, height=300)
        invoices_frame.pack(fill="both", expand=True, padx=(10, 20), pady=(10, 20))

        # popolo gli invoices
        invoices = self.user_controller.retrieve_user_with_invoices_map_list(self.current_user_id)
        for invoice in invoices:
            if invoice[DBInvoicesColumns.NUMERO_FATTURA.value] is not None:
                nome_fattura = invoice[DBInvoicesColumns.NUMERO_FATTURA.value]
                id_fattura = invoice[DBInvoicesColumns.ID.value]
                id_produzione = invoice[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value]
                produzione = self.production_controller.retrieve_production_map_by_id(id_produzione)
                nome_prod = produzione[DBProductionsColumns.NAME.value] if produzione else "Produzione non trovata"
                fattura_button = ctk.CTkButton(invoices_frame,
                                               text=f"{nome_fattura} - {nome_prod}",
                                               command=lambda id=id_fattura: self.show_invoice_detail(id))
                fattura_button.pack(padx=10, pady=10, fill="x", expand=True)

    def show_invoice_detail(self, invoice_id):
        self.event_bus.publish(ViewUtils.EventBusKeys.SHOW_INVOICE_DETAIL, invoice_id)

    def show_salary_detail(self, invoice_id):
        self.event_bus.publish(ViewUtils.EventBusKeys.SHOW_SALARY_DETAIL, invoice_id)

    def _create_anticipated_expenses_history(self):
        """Crea la sezione storico delle spese anticipate"""
        section_frame = ctk.CTkFrame(self.wrapper_frame, border_width=2, border_color="#2659ab")
        section_frame.pack(fill="both", side="left", expand=True, pady=0, padx=(0, 30))

        ctk.CTkLabel(section_frame, text="SPESE ANTICIPATE", font=("Arial", 14, "bold")).pack(anchor="w", pady=(10, 10), padx=10)

        global_infos = {
            "TOTALE SPESE ANTICIPATE" : {
                "value" : self.user_controller.calcola_tot_spese_utente_anticipate(self.current_user_id),
                "uom" : "€"
            }
        }

        self.global_infos_invoices_widgets = ViewUtils.construct_global_infos_cards(section_frame, global_infos)

        # tabella invoices
        expenses_frame = ctk.CTkScrollableFrame(section_frame, height=300)
        expenses_frame.pack(fill="both", expand=True, padx=(10, 20), pady=(10, 20))

        # popolo gli invoices
        expenses = self.user_controller.retrieve_user_with_anticipated_expenses_map_list(self.current_user_id)
        for expense in expenses:
            if expense[DBExpensesColumns.NAME.value] is not None:
                nome_spesa = expense[DBExpensesColumns.NAME.value]
                id_spesa = expense[DBExpensesColumns.ID.value]
                spesa_button = ctk.CTkButton(expenses_frame, text=f"{nome_spesa}")
                spesa_button.pack(padx=10, pady=10, fill="x", expand=True)

    def _create_deduz_expenses_history(self):
        """Crea la sezione storico delle spese messe in deduzione"""
        section_frame = ctk.CTkFrame(self.wrapper_frame, border_width=2, border_color="#2659ab")
        section_frame.pack(fill="both", side="left", expand=True, pady=0, padx=0)

        ctk.CTkLabel(section_frame, text="SPESE IN DEDUZIONE", font=("Arial", 14, "bold")).pack(anchor="w", pady=(10, 10), padx=10)

        global_infos = {
            "TOTALE SPESE IN DEDUZIONE" : {
                "value" : self.user_controller.calcola_tot_spese_utente_dedotte(self.current_user_id),
                "uom" : "€"
            }
        }

        self.global_infos_invoices_widgets = ViewUtils.construct_global_infos_cards(section_frame, global_infos)

        # tabella invoices
        expenses_frame = ctk.CTkScrollableFrame(section_frame, height=300)
        expenses_frame.pack(fill="both", expand=True, padx=(10, 20), pady=(10, 20))

        # popolo gli invoices
        expenses = self.user_controller.retrieve_user_with_deducted_expenses_map_list(self.current_user_id)
        for expense in expenses:
            if expense[DBExpensesColumns.NAME.value] is not None:
                nome_spesa = expense[DBExpensesColumns.NAME.value]
                id_spesa = expense[DBExpensesColumns.ID.value]
                spesa_button = ctk.CTkButton(expenses_frame, text=f"{nome_spesa}")
                spesa_button.pack(padx=10, pady=10, fill="x", expand=True)

    def _create_salary_history(self):
        """Crea la sezione storico dei salari"""
        section_frame = ctk.CTkFrame(self.wrapper_frame, border_width=2, border_color="#2659ab")
        section_frame.pack(fill="both", side="left", expand=True, pady=0, padx=(0, 30))

        ctk.CTkLabel(section_frame, text="PAGAMENTI SALARIO", font=("Arial", 14, "bold")).pack(anchor="w", pady=(10, 10), padx=10)

        global_infos = {
            "TOTALE SALARI" : {
                "value" : self.user_controller.calcola_tot_salari_utente(self.current_user_id),
                "uom" : "€"
            }
        }

        self.global_infos_invoices_widgets = ViewUtils.construct_global_infos_cards(section_frame, global_infos)

        # tabella invoices
        salary_frame = ctk.CTkScrollableFrame(section_frame, height=300)
        salary_frame.pack(fill="both", expand=True, padx=(10, 20), pady=(10, 20))

        # popolo gli invoices
        salaries = self.user_controller.retrieve_user_with_salaries_map_list(self.current_user_id)
        for salary in salaries:
            if salary[DBSalariesColumns.NAME.value] is not None:
                nome_salario = salary[DBSalariesColumns.NAME.value]
                id_salario = salary[DBSalariesColumns.ID.value]
                spesa_button = ctk.CTkButton(salary_frame,
                                             text=f"{nome_salario}",
                                             command=lambda id=id_salario: self.show_salary_detail(id))
                spesa_button.pack(padx=10, pady=10, fill="x", expand=True)

    def _create_fiscal_data_section(self):
        # Creazione frame principale
        dati_fiscali_frame = ctk.CTkFrame(self.wrapper_frame2, border_width=2, border_color="#2659ab")
        dati_fiscali_frame.pack(fill="both", expand=True, pady=0, padx=(0, 10), ipady=20, side="left")

        ctk.CTkLabel(dati_fiscali_frame, text="DATI FISCALI", font=("Arial", 14, "bold")).pack(anchor="w", pady=(10, 10), padx=10)

        aliquote_frame = ctk.CTkFrame(dati_fiscali_frame)
        aliquote_frame.pack(fill="both", expand=True, pady=20, padx=(20, 20), side="left")
        ctk.CTkLabel(aliquote_frame, text="Aliquote", font=("Arial", 12, "bold")).pack(anchor="w", pady=(10, 10), padx=20)

        imponibili_frame = ctk.CTkFrame(dati_fiscali_frame)
        imponibili_frame.pack(fill="both", expand=True, pady=20, padx=(20, 20), side="left")
        ctk.CTkLabel(imponibili_frame, text="Imponibili", font=("Arial", 12, "bold")).pack(anchor="w", pady=(10, 10), padx=20)

        user_fiscal_data = self.user_controller.pick_fiscal_data_by_user_id(self.current_user_id)

        # Prendo i dati suddivisi da controller
        user_fiscal_data = self.user_controller.pick_fiscal_data_by_user_id(self.current_user_id)
        aliquote = user_fiscal_data.get("aliquote", {})
        imponibili = user_fiscal_data.get("imponibili", {})

        # Popolo Aliquote
        for titolo, valore in aliquote.items():
            row = ctk.CTkFrame(aliquote_frame)
            row.pack(fill="x", padx=20, pady=5)
            ctk.CTkLabel(row, text=f"{titolo}:", anchor="w").pack(side="left", pady=5, padx=10)
            ctk.CTkLabel(row, text=valore, anchor="e").pack(side="left", pady=5, padx=10)

        # Popolo Imponibili
        for titolo, valore in imponibili.items():
            row = ctk.CTkFrame(imponibili_frame)
            row.pack(fill="x", padx=20, pady=5)
            ctk.CTkLabel(row, text=f"{titolo}:", anchor="w").pack(side="left", pady=5, padx=10)
            ctk.CTkLabel(row, text=valore, anchor="e").pack(side="left", pady=5, padx=10)

    def _create_taxes_section(self):
        # Creazione frame principale
        self.tax_frame = ctk.CTkFrame(self.wrapper_frame2, border_width=2, border_color="#2659ab")
        self.tax_frame.pack(fill="both", expand=True, pady=0, padx=(10, 10), ipady=20, side="left")

        ctk.CTkLabel(self.tax_frame, text="PREVISIONE TASSE", font=("Arial", 14, "bold")).pack(anchor="w",
                                                                                               pady=(10, 5),
                                                                                               padx=15)

        regime_fiscale = self.user_controller.get_regime_fiscale_by_id(self.current_user_id)
        if str(regime_fiscale) == str(self.user_controller.RegimeFiscale.FORFETTARIO.value):
            tasse = self.analyzer.calculate_previsione_tasse_forfettaria(self.current_user_id)
            global_infos = {}
            for k, v in tasse.items():
                global_infos[k] = {
                    "value": v,
                    "uom": "€"
                }

            self.tasse_infos_user_widgets = ViewUtils.construct_tasse_infos_cards(self.tax_frame, global_infos)
        elif str(regime_fiscale) == str(self.user_controller.RegimeFiscale.ORDINARIO.value):
            tasse_view, versamenti, tasse_total = self.analyzer.calculate_previsione_tasse_ordinaria(self.current_user_id)
            global_infos = {}
            versamenti_infos = {}
            for k, v in tasse_view.items():
                global_infos[k] = {
                    "value": v,
                    "uom": "€"
                }
            for k, v in versamenti.items():
                versamenti_infos[ViewUtils.split_string_by_length(k, 8)] = {
                    "value": v,
                    "uom": "€"
                }
            ctk.CTkLabel(self.tax_frame, text="TOTALI", font=("Arial", 12)).pack(anchor="w",
                                                                                                   pady=(0, 10),
                                                                                                   padx=15)
            self.tasse_infos_user_widgets = ViewUtils.construct_tasse_infos_cards(self.tax_frame, global_infos)
            ctk.CTkLabel(self.tax_frame, text="VERSAMENTI", font=("Arial", 12)).pack(anchor="w",
                                                                                                   pady=(10, 0),
                                                                                                   padx=15)
            self.versamenti_infos_user_widgets = ViewUtils.construct_tasse_infos_cards(self.tax_frame, versamenti_infos)

            for key, widget_info in self.tasse_infos_user_widgets.items():
                card = widget_info["card"]

                if key == "INPS":
                    tooltip_text = (
                        f"Calcolo contributi INPS complessivi:\n\n"
                        f"1. Ricavi totali = Fatturato Willow + Reddito esterno\n"
                        f"   = {tasse_total['FATTURATO_WILLOW']} + {tasse_total['REDDITO_ESTERNO']}\n"
                        f"   = {tasse_total['RICAVI_TOTALI']} €\n\n"
                        f"2. Spese totali = Spese Willow + Spese esterne\n"
                        f"   = {tasse_total['SPESE_WILLOW']} + {tasse_total['SPESE_ESTERNE']}\n"
                        f"   = {tasse_total['SPESE_TOTALI']} €\n\n"
                        f"3. Reddito netto imponibile = Ricavi totali - Spese totali\n"
                        f"   = {tasse_total['RICAVI_TOTALI']} - {tasse_total['SPESE_TOTALI']}\n"
                        f"   = {tasse_total['REDDITO_NETTO']} €\n\n"
                        f"4. Contributi INPS = Reddito netto × Aliquota INPS ({tasse_total['ALIQUOTA_INPS']}%)\n"
                        f"   = {tasse_total['REDDITO_NETTO']} × {tasse_total['ALIQUOTA_INPS']}%\n"
                        f"   = {tasse_total['INPS']} €"
                    )

                elif key == "IRPEF NETTA":
                    tooltip_text = (
                        f"Calcolo IRPEF netta dovuta:\n\n"
                        f"1. Base imponibile IRPEF = Reddito netto - Contributi INPS\n"
                        f"   = {tasse_total['REDDITO_NETTO']} - {tasse_total['INPS']}\n"
                        f"   = {tasse_total['BASE_IRPEF']} €\n\n"
                        f"2. IRPEF lorda (calcolata a scaglioni)\n"
                        f"   = {tasse_total['IRPEF_LORDA']} €\n\n"
                        f"3. Ritenuta d'acconto versata\n"
                        f"   = {tasse_total['RITENUTA']} €\n\n"
                        f"4. IRPEF netta = IRPEF lorda - Ritenuta\n"
                        f"   = {tasse_total['IRPEF_LORDA']} - {tasse_total['RITENUTA']}\n"
                        f"   = {tasse_total['IRPEF_NETTA']} €"
                    )

                elif key == "WILLOW INPS":
                    tooltip_text = (
                        f"Quota INPS attribuibile a Willow:\n\n"
                        f"1. Reddito netto Willow = Fatturato Willow - Spese Willow\n"
                        f"   = {tasse_total['FATTURATO_WILLOW']} - {tasse_total['SPESE_WILLOW']}\n"
                        f"   = {tasse_total['REDDITO_NETTO_WILLOW']} €\n\n"
                        f"2. Quota proporzionale = Reddito Willow / Reddito totale\n"
                        f"   = {tasse_total['REDDITO_NETTO_WILLOW']} / {tasse_total['REDDITO_NETTO']}\n"
                        f"   = {tasse_total['QUOTA_WILLOW_BASE']}\n\n"
                        f"3. INPS Willow = INPS totale × Quota proporzionale\n"
                        f"   = {tasse_total['INPS']} × {tasse_total['QUOTA_WILLOW_BASE']}\n"
                        f"   = {tasse_total['WILLOW_INPS']} €"
                    )

                elif key == "WILLOW IRPEF":
                    tooltip_text = (
                        f"IRPEF netta attribuibile a Willow:\n\n"
                        f"A. PARTE NELLO SCAGLIONE BASE:\n"
                        f"1. Reddito netto senza Willow\n"
                        f"   = {tasse_total['SENZA_WILLOW_REDDITO']} €\n\n"
                        f"2. Quota Willow nella base comune\n"
                        f"   = (Reddito Willow / Reddito totale)\n"
                        f"   = {tasse_total['QUOTA_WILLOW_BASE']}\n\n"
                        f"3. IRPEF base Willow = IRPEF comune × Quota\n"
                        f"   = {tasse_total['IRPEF_COMUNE']} × {tasse_total['QUOTA_WILLOW_BASE']}\n"
                        f"   = {tasse_total['WILLOW_IRPEF_BASE']} €\n\n"
                        f"B. PARTE PER SCAGLIONE AGGIUNTIVO:\n"
                        f"1. Base IRPEF aggiuntiva = Base totale - Base senza Willow\n"
                        f"   = {tasse_total['BASE_IRPEF']} - {tasse_total['SENZA_WILLOW_BASE_IRPEF']}\n"
                        f"   = {tasse_total['BASE_AGGIUNTIVA']} €\n\n"
                        f"2. IRPEF aggiuntiva = IRPEF totale - IRPEF senza Willow\n"
                        f"   = {tasse_total['IRPEF_LORDA']} - {tasse_total['SENZA_WILLOW_IRPEF']}\n"
                        f"   = {tasse_total['WILLOW_IRPEF_AGGIUNTIVA']} €\n\n"
                        f"C. TOTALE LORDO:\n"
                        f"IRPEF lorda Willow = Parte base + Parte aggiuntiva\n"
                        f"= {tasse_total['WILLOW_IRPEF_BASE']} + {tasse_total['WILLOW_IRPEF_AGGIUNTIVA']}\n"
                        f"= {tasse_total['WILLOW_IRPEF_TOT']} €\n\n"
                        f"D. NETTO DOPO RITENUTA:\n"
                        f"IRPEF netta Willow = Lordo - Ritenuta\n"
                        f"= {tasse_total['WILLOW_IRPEF_TOT']} - {tasse_total['WILLOW_RITENUTA']}\n"
                        f"= {tasse_total['WILLOW_IRPEF_NETTA']} €"
                    )

                else:
                    tooltip_text = "Informazioni non disponibili"

                ViewUtils.add_tooltip(card.winfo_children()[0], tooltip_text)

                # Tooltip per le carte dei versamenti
            for key, widget_info in self.versamenti_infos_user_widgets.items():
                card = widget_info["card"]
                title_label = card.winfo_children()[0]  # La label del titolo è il primo figlio

                if key == "SALDO\nTOTALE":
                    tooltip_text = (
                        f"Saldo tasse correnti:\n\n"
                        f"1. Tasse totali (INPS + IRPEF netta) = {tasse_total['TOTALE_TASSE']} €\n"
                        f"2. Acconto versato per l'anno precedente = {tasse_total['ACCONTO_ANNO_PRECEDENTE']} €\n"
                        f"3. Saldo = Tasse totali - Acconto anno precedente\n"
                        f"   = {tasse_total['TOTALE_TASSE']} - {tasse_total['ACCONTO_ANNO_PRECEDENTE']}\n"
                        f"   = {tasse_total['SALDO_TOTALE']} €"
                    )

                elif key == "ACCONTO\nTOTALE":
                    tooltip_text = (
                        f"Acconto totale per l'anno successivo:\n\n"
                        f"1. Acconto INPS = INPS totale × {tasse_total['PERC_ACCONTO_INPS'] * 100}%\n"
                        f"   = {tasse_total['INPS']} × {tasse_total['PERC_ACCONTO_INPS']}\n"
                        f"   = {tasse_total['INPS'] * tasse_total['PERC_ACCONTO_INPS']} €\n"
                        f"2. Acconto IRPEF = IRPEF netta × 100%\n"
                        f"   = {tasse_total['IRPEF_NETTA']} × 1.00\n"
                        f"   = {tasse_total['IRPEF_NETTA']} €\n\n"
                        f"Totale acconto = Acconto INPS + Acconto IRPEF\n"
                        f"   = {tasse_total['INPS'] * tasse_total['PERC_ACCONTO_INPS']} + {tasse_total['IRPEF_NETTA']}\n"
                        f"   = {tasse_total['ACCONTO_TOTALE']} €"
                    )

                elif key == "SALDO\nWILLOW":
                    tooltip_text = (
                        f"Quota del saldo corrente attribuita a Willow:\n\n"
                        f"1. Saldo totale = {tasse_total['SALDO_TOTALE']} €\n"
                        f"2. Proporzione Willow = Tasse Willow / Tasse totali\n"
                        f"   = {tasse_total['WILLOW_TASSE_TOT']} / {tasse_total['TOTALE_TASSE']}\n"
                        f"   = {tasse_total['PROP_WILLOW']}\n"
                        f"3. Saldo Willow = Saldo totale × Proporzione Willow\n"
                        f"   = {tasse_total['SALDO_TOTALE']} × {tasse_total['PROP_WILLOW']}\n"
                        f"   = {tasse_total['SALDO_WILLOW']} €"
                    )

                elif key == "ACCONTO\nWILLOW":
                    tooltip_text = (
                        f"Quota dell'acconto per l'anno successivo attribuita a Willow:\n\n"
                        f"1. Acconto totale = {tasse_total['ACCONTO_TOTALE']} €\n"
                        f"2. Proporzione Willow = {tasse_total['PROP_WILLOW']}\n"
                        f"3. Acconto Willow = Acconto totale × Proporzione Willow\n"
                        f"   = {tasse_total['ACCONTO_TOTALE']} × {tasse_total['PROP_WILLOW']}\n"
                        f"   = {tasse_total['ACCONTO_WILLOW']} €"
                    )

                else:
                    tooltip_text = "Informazioni non disponibili"

                ViewUtils.add_tooltip(title_label, tooltip_text)


    def _create_iva_section(self):
        # Creazione frame principale
        iva_frame = ctk.CTkFrame(self.wrapper_frame2, border_width=2, border_color="#2659ab")
        iva_frame.pack(fill="both", expand=True, pady=0, padx=(10, 0), ipady=20, side="left")

        ctk.CTkLabel(iva_frame, text="IVA TRIMESTRALE", font=("Arial", 14, "bold")).pack(anchor="w", pady=(10, 10), padx=10)

        self.iva_header_frame = ctk.CTkFrame(iva_frame, fg_color="#2b2b2b")
        self.iva_header_frame.pack(fill="x", expand=True, padx=(10, 10), pady=(15, 0))

        header0 = ctk.CTkFrame(self.iva_header_frame, fg_color="#333333")
        header0.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=5)
        header1 = ctk.CTkFrame(self.iva_header_frame, fg_color="#333333")
        header1.grid(row=0, column=1, sticky="nsew", padx=(0, 5), pady=5)
        header2 = ctk.CTkFrame(self.iva_header_frame, fg_color="#333333")
        header2.grid(row=0, column=2, sticky="nsew", padx=(0, 5), pady=5)
        header3 = ctk.CTkFrame(self.iva_header_frame, fg_color="#333333")
        header3.grid(row=0, column=3, sticky="nsew", padx=(0, 5), pady=5)

        self.iva_header_frame.grid_columnconfigure(0, weight=1, uniform="col")
        self.iva_header_frame.grid_columnconfigure(1, weight=1, uniform="col")
        self.iva_header_frame.grid_columnconfigure(2, weight=1, uniform="col")
        self.iva_header_frame.grid_columnconfigure(3, weight=1, uniform="col")

        ctk.CTkLabel(header0, text="TRIMESTRE", font=("Arial", 12)).pack(fill="x", expand=True, padx=5, pady=15)
        ctk.CTkLabel(header1, text="CREDITO", font=("Arial", 12)).pack(fill="x", expand=True, padx=5, pady=15)
        ctk.CTkLabel(header2, text="DEBITO", font=("Arial", 12)).pack(fill="x", expand=True, padx=5, pady=15)
        ctk.CTkLabel(header3, text="DA PAGARE", font=("Arial", 12)).pack(fill="x", expand=True, padx=5, pady=15)

        self.trimestral_list_frame = ctk.CTkFrame(iva_frame)
        self.trimestral_list_frame.pack(fill="x", expand=True, padx=10, pady=(0, 25))

        # Ottieni i dati IVA trimestrali
        iva_data = self.analyzer.calculate_trimestral_iva_by_account_id(self.current_user_id)

        # Ordina i trimestri nell'ordine corretto
        quarters_order = ["Gen-Marz", "Apr-Giu", "Lug-Sett", "Ott-Dic"]

        for quarter in quarters_order:
            data = iva_data.get(quarter, {"debito": 0.0, "credito": 0.0, "da_pagare": 0.0})

            # Crea il frame per la riga
            row_frame = ctk.CTkFrame(self.trimestral_list_frame)
            row_frame.pack(fill="x", pady=(0, 5))

            # Configura le colonne con peso uniforme
            for col in range(4):
                row_frame.grid_columnconfigure(col, weight=1, uniform="col")

            # Colonna 1: Nome trimestre
            quarter_frame = ctk.CTkFrame(row_frame)
            quarter_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
            ctk.CTkLabel(quarter_frame, text=quarter).pack(padx=5, pady=5)

            # Colonna 2: Credito IVA
            credito_frame = ctk.CTkFrame(row_frame)
            credito_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 5))
            ctk.CTkLabel(credito_frame, text=f"{data['credito']:.2f} €").pack(padx=5, pady=5)

            # Colonna 3: Debito IVA
            debito_frame = ctk.CTkFrame(row_frame)
            debito_frame.grid(row=0, column=2, sticky="nsew", padx=(0, 5))
            ctk.CTkLabel(debito_frame, text=f"{data['debito']:.2f} €").pack(padx=5, pady=5)

            # Colonna 4: Saldo da pagare (con colorazione condizionale)
            saldo_frame = ctk.CTkFrame(row_frame)
            saldo_frame.grid(row=0, column=3, sticky="nsew")

            # Determina il colore in base al saldo
            saldo = data['da_pagare']
            if saldo > 0:
                fg_color = "#f52f2f"  # rosso per importi positivi (da pagare)
            elif saldo < 0:
                fg_color = "#2ca31c"  # verde per crediti
            else:
                fg_color = "#b0b0b0"  # grigio per saldo zero

            # Crea label con colore di sfondo appropriato
            ctk.CTkLabel(
                saldo_frame,
                text=f"{saldo:.2f} €",
                fg_color=fg_color,
                corner_radius=4
            ).pack(padx=5, pady=5, fill="both", expand=True)

    def toggle_taxes(self):
        """Ricalcola e aggiorna i valori delle tasse visualizzate nelle cards"""
        # Ricalcola le tasse con i nuovi parametri
        tasse = self.analyzer.calculate_previsione_tasse_forfettaria(self.current_user_id)

        # Aggiorna le labels nelle cards esistenti
        for name, value in tasse.items():
            if name in self.tasse_infos_user_widgets:
                # Formatta il nuovo valore con l'unità di misura
                new_text = f"{value} €"

                # Aggiorna il testo della label
                self.tasse_infos_user_widgets[name]["label"].configure(text=new_text)





    def _cleanup_and_go_back(self):
        """Pulizia completa prima di tornare indietro"""
        self._clear_content()
        self.pack_forget()
        self.back_callback()

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
from PIL import Image
from datetime import datetime
import os

from App_context import AppContext
from Event_bus import EventBus
from QueryServices.Account_query_service import AccountQueryService
from QueryServices.Users_query_service import UserQueryService
from OtherServices.User_crypto_service import UserCryptoService
from Views.Details.User_detail_view import UserDetailView

from Views.View_utils import ViewUtils

from Controllerss.User_controller import UserController
from Utils.Validation_utils import ValidationUtils
from Model import DatabaseModel
from Fatturazione_elettronica_API import FatturazioneElettronicaProvider
from Gestionale_Enums import*
from Controllerss.Production_controller import ProductionController

class UsersView(ctk.CTkFrame):
    def __init__(self, app_context:AppContext, tab, logged_user_id, login_status):
        super().__init__(tab)

        self.app_context:AppContext = app_context
        self.db_model:DatabaseModel = app_context.db_model
        self.user_controller:UserController = app_context.user_controller
        self.user_query_service: UserQueryService = app_context.user_query_service
        self.user_crypto_service:UserCryptoService = app_context.user_crypto_service
        self.accounts_query_service: AccountQueryService = app_context.account_query_service
        self.production_controller:ProductionController = app_context.production_controller
        self.tab = tab
        self.fiscal_settings = app_context.fiscal_settings
        self.event_bus:EventBus = app_context.event_bus

        #tool variables
        self.no_data_string = "no data"
        self.current_year = datetime.now().year

        #construct users list
        self.users_list = self.user_query_service.retrieve_users_map_list()
        self.number_of_users_cards = 0
        self.user_cards = {}  # Dizionario per associare user_id alle card

        self.login_status = login_status
        self.logged_user_id = logged_user_id

        self.event_bus.subscribe(ViewUtils.EventBusKeys.LOGIN_STATUS_CHANGED.value, self._on_login_changed)

        #construct accounts_names list
        self.accounts_mapping = self.accounts_query_service.get_accounts_mapping(self.db_model)
        if self.accounts_mapping == {}:
            self.accounts_list = [self.no_data_string]
        else:
            self.accounts_list = list(self.accounts_mapping.keys())

        # Container principale
        self.main_container = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.detail_container = ctk.CTkFrame(self, fg_color="#2b2b2b")

        # Vista dettaglio
        self.user_detail_view = UserDetailView(
            app_context=self.app_context,
            parent=self,
            back_callback=self.show_main_view
        )

        self.configure(fg_color="#333333")

        # Sistema per tracciare gli after()
        self._after_ids = set()
        self._orig_after = self.after
        self.after = self._track_after

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
        accounts_map_list = self.accounts_query_service.retrieve_accounts_map_list()
        self.conto_corrente_combobox = ctk.CTkOptionMenu(self.user_window_scrollableFrame, values=[account[DBAccountsColumns.NAME.value] for account in accounts_map_list])
        self.conto_corrente_combobox.pack(pady=(5, 15))

        self.regime_fiscale_label = ctk.CTkLabel(self.user_window_scrollableFrame, text="Regime Fiscale:")
        self.regime_fiscale_label.pack(pady=(35, 0))
        self.regime_fiscale_combobox = ctk.CTkOptionMenu(self.user_window_scrollableFrame, values=[item.value for item in RegimeFiscale])
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
        conto = self.accounts_query_service.retrieve_account_map_by_name(self.conto_corrente_combobox.get().strip())
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
            DBUsersColumns.STATUS.value: UserStatus.ATTIVO.value,
        }

        # Chiamata al controller per salvare i dati
        success, message = self.user_controller.save_user(user_data)
        if success:
            user_id = self.user_query_service.retrieve_user_by_fullname(user_data[DBUsersColumns.FIRST_NAME.value], user_data[DBUsersColumns.LAST_NAME.value])[0] #recupero l'ID dell'utente
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

            self.users_list.append(self.user_query_service.retrieve_user_map_by_id(user_id))
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
        user = self.user_query_service.retrieve_user_map_by_id(user_id)

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
                                                                                                 RegimeFiscale])
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
        if user[DBUsersColumns.REGIME_FISCALE.value] in [item.value for item in RegimeFiscale]:
            self.regime_fiscale_combobox.set(user[DBUsersColumns.REGIME_FISCALE.value])

        # Imposta il valore del combobox dell'anno di apertura p. iva
        if user[DBUsersColumns.ANNO_APERTURA_PIVA.value]:
            self.anno_apertura_piva_combobox.set(user[DBUsersColumns.ANNO_APERTURA_PIVA.value])

        # Imposta il valore del combobox del provider delle fatture elettroniche
        if user[DBUsersColumns.PROVIDER_FATTURE.value]:
            self.provider_FattElett_combobox.set(user[DBUsersColumns.PROVIDER_FATTURE.value])

        decrypted_username = self.user_crypto_service.decrypt_string(user[DBUsersColumns.USERNAME_PROVIDER.value])
        # Imposta il valore della entry dello username per il login sul provider FE
        if user[DBUsersColumns.USERNAME_PROVIDER.value]:
            self.provider_username_entry.insert(0, decrypted_username)

        decrypted_password = self.user_crypto_service.decrypt_string(user[DBUsersColumns.PASSWORD_PROVIDER.value])
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
            DBUsersColumns.STATUS.value: UserStatus.ATTIVO.value,
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
            updated_user = self.user_query_service.retrieve_user_map_by_id(user_id)
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

    def _on_login_changed(self, data):
        self.login_status = data["login_status"]
        self.logged_user_id = data["logged_user_id"]


    def cleanup(self):
        """Pulizia completa per liberare memoria - DA AGGIUNGERE IN OGNI VIEW"""
        try:
            print(f"Cleanup di {self.__class__.__name__}")

            self.event_bus.unsubscribe(ViewUtils.EventBusKeys.LOGIN_STATUS_CHANGED.value, self._on_login_changed)

            if hasattr(self, "user_detail_view") and self.user_detail_view is not None:
                self.user_detail_view.cleanup()

            # 1. Cancella tutti gli after scheduled
            if hasattr(self, '_after_ids'):
                for after_id in self._after_ids:
                    try:
                        self.after_cancel(after_id)
                    except:
                        pass
                self._after_ids.clear()

            # 2. Distruggi tutte le card e widget dinamici
            card_lists = [
                'payment_card_list', 'invoice_card_list', 'client_card_list',
                'supplier_card_list', 'production_card_list', 'expenses_card_list',
                'salaries_card_list', 'refund_card_list', 'account_card_list'
            ]

            for card_attr in card_lists:
                if hasattr(self, card_attr):
                    card_dict = getattr(self, card_attr)
                    for card_name, card in card_dict.items():
                        try:
                            card.destroy()
                        except:
                            pass
                    card_dict.clear()

            # 3. Pulisci dizionari e liste
            data_attrs = [
                'cards_warnings', 'global_infos', 'amount_aggregate_labels',
                'payment_card_labels_status', 'invoice_card_labels_status',
                'production_card_labels_status'
            ]

            for attr in data_attrs:
                if hasattr(self, attr):
                    getattr(self, attr).clear()

            # 4. Distruggi i container principali se esistono
            container_attrs = [
                'main_container', 'detail_container', 'payments_cards_frame',
                'invoices_cards_frame', 'clients_cards_frame', 'suppliers_cards_frame',
                'productions_cards_frame', 'expenses_cards_frame', 'refunds_cards_frame',
                'accounts_cards_frame', 'salaries_cards_frame'
            ]

            for attr in container_attrs:
                if hasattr(self, attr):
                    container = getattr(self, attr)
                    try:
                        # Distruggi solo se il container esiste ancora
                        if container.winfo_exists():
                            for widget in container.winfo_children():
                                try:
                                    widget.destroy()
                                except:
                                    pass
                    except:
                        pass

            # 5. Pulisci i riferimenti ai controller (opzionale)
            if hasattr(self, 'db_model'):
                self.db_model = None

        except Exception as e:
            print(f"Errore durante il cleanup di {self.__class__.__name__}: {e}")

    def _track_after(self, ms, func, *args):
        """Versione tracciata di after()"""
        after_id = self._orig_after(ms, func, *args)
        self._after_ids.add(after_id)
        return after_id




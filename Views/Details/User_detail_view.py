import os
import re

import customtkinter as ctk
from datetime import datetime
from tkinter import filedialog

from AnalyzerServices.Account_analyzer_service import AccountAnalyzerService
from AnalyzerServices.Iva_analyzer_service import IvaAnalyzerService
from AnalyzerServices.User_analyzer_service import UserAnalyzerService
from App_context import AppContext
from Fatturazione_elettronica_API import FatturazioneElettronicaProvider
from QueryServices.Account_query_service import AccountQueryService
from QueryServices.Productions_query_service import ProductionQueryService
from QueryServices.Users_query_service import UserQueryService
from Views.View_utils import ViewUtils

from Gestionale_Enums import*


class UserDetailView(ctk.CTkFrame):
    def __init__(self, parent, app_context:AppContext, back_callback):
        super().__init__(parent)
        self.iva_analyzer_service:IvaAnalyzerService = app_context.iva_analyzer_service
        self.app_context:AppContext = app_context
        self.parent = parent
        self.user_controller = app_context.user_controller
        self.user_query_service: UserQueryService = app_context.user_query_service
        self.user_analyzer_service: UserAnalyzerService = app_context.user_analyzer_service
        self.accounts_query_service: AccountQueryService = app_context.account_query_service
        self.account_analyzer_service:AccountAnalyzerService = app_context.account_analyzer_service
        self.db_model = app_context.db_model
        self.back_callback = back_callback
        self.productions_query_service: ProductionQueryService = app_context.productions_query_service
        self.fiscal_settings = app_context.fiscal_settings
        self.event_bus = app_context.event_bus
        self.current_user_id = None

        # Widgets persistenti (vanno creati una volta sola)
        self.head_frame = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.back_button = ctk.CTkButton(
            self.head_frame,
            text="Elenco Utenti",
            command=self._cleanup_and_go_back
        )
        self.title_label = ctk.CTkLabel(self.head_frame, font=("Arial", 22, "bold"))

        self.user_info_widgets: dict[str, ctk.CTkEntry | ctk.CTkOptionMenu | ctk.CTkButton] = {}
        self.selected_photo_path = ""
        self.photo_path_button = None
        self.photo_path_label = None

        self.nome_conto_string = "CONTO"

        # Container per i contenuti dinamici
        self.content_frame = ctk.CTkScrollableFrame(self)

        self.event_bus.subscribe(ViewUtils.EventBusKeys.LOGIN_STATUS_CHANGED.value, self._on_login_changed_detail)
        self.login_password_is_present = False

        self.switch_modify = ctk.CTkSwitch(self.head_frame, text="Abilita la modifica", command=lambda: self.toggle_widget_container_function(self.content_frame))

        # Layout iniziale
        self._setup_base_layout()

        self.eye_buttons = []  # Aggiungi questa lista per memorizzare i bottoni occhio

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
        user = self.user_query_service.retrieve_user_map_by_id(user_id)

        #prendo il nome del conto:
        id_conto = user[DBUsersColumns.CONTO_CORRENTE_ID.value]
        conto = self.accounts_query_service.retrieve_account_map_by_id(id_conto)
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
        if regime == RegimeFiscale.ORDINARIO.value:
            self._create_deduz_expenses_history()

        self._create_fiscal_data_section()
        self._create_taxes_section()
        if regime == RegimeFiscale.ORDINARIO.value:
            self._create_iva_section()

    def cleanup(self):
        try:
            self.event_bus.unsubscribe(ViewUtils.EventBusKeys.LOGIN_STATUS_CHANGED.value, self._on_login_changed_detail)
        except Exception:
            pass

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
            DBUsersColumns.PASSWORD_LOGIN.value: {
                "type": ctk.CTkEntry,
                "label": "Nuova Login Password",
                "section": "Dati Anagrafici",
                "password": True
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
                "values": [item.value for item in RegimeFiscale]
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
                "section": "Dati Fiscali",
                "password": True
            },
            DBUsersColumns.SPESE_DEDOTTE_ESTERNE.value: {
                "type": ctk.CTkEntry,
                "label": "Spese Dedotte Esterne",
                "section": "Dati Fiscali",
                "password": True
            },
            DBUsersColumns.LAST_YEAR_IRPEF_ACCONTO.value: {
                "type": ctk.CTkEntry,
                "label": "Acconto IRPEF anno scorso",
                "section": "Dati Fiscali",
                "password": True
            },
            DBUsersColumns.LAST_YEAR_INPS_ACCONTO.value: {
                "type": ctk.CTkEntry,
                "label": "Acconto INPS anno scorso",
                "section": "Dati Fiscali",
                "password": True
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
                           self.accounts_query_service.retrieve_accounts_map_list()]
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
                "values": [item.value for item in UserStatus]
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
            DBUsersColumns.EMAIL.value: "Formato email non valido",
            DBUsersColumns.PASSWORD_LOGIN.value: "Password non valida, digitare almeno 8 caratteri"
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
            ),
            DBUsersColumns.PASSWORD_LOGIN.value: (
                lambda val: len(val) >= 8,
                "Digitare almeno 8 caratteri se vuoi modificare la password\n Altrimenti lasciare il campo vuoto"
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
            if (str(user_data[DBUsersColumns.REGIME_FISCALE.value]) == str(
                    RegimeFiscale.FORFETTARIO.value) and field == DBUsersColumns.SPESE_DEDOTTE_ESTERNE.value):
                continue

            section = sections[config["section"]]
            frame = section["frame"]
            row = section["row"]

            # Creazione label
            lbl = ctk.CTkLabel(frame, text=config["label"] + ":")
            lbl.grid(row=row, column=0, sticky="w", padx=(15, 5),
                     pady=(2, 5) if field in validation_rules.keys() else (2, 25))

            # Creazione widget
            if config["type"] == ctk.CTkOptionMenu:
                widget = config["type"](frame, values=config.get("values", []))
                widget.set(user_data.get(field, config.get("values", [""])[0]))
                widget.grid(row=row, column=1, sticky="ew", padx=(5, 15),
                            pady=(2, 5) if field in validation_rules.keys() else (2, 35))
                self.user_info_widgets[field] = widget
            elif field == DBUsersColumns.PHOTO_PATH.value:
                selector_frame = ctk.CTkFrame(frame, fg_color="transparent")
                selector_frame.grid(row=row, column=1, sticky="ew", padx=(5, 15), pady=(2, 35))
                selector_frame.grid_columnconfigure(1, weight=1)

                self.selected_photo_path = str(user_data.get(field, "") or "")
                self.photo_path_button = ctk.CTkButton(
                    selector_frame,
                    text="Scegli Immagine",
                    command=self.choose_photo_path
                )
                self.photo_path_button.grid(row=0, column=0, padx=(0, 10), sticky="w")

                self.photo_path_label = ctk.CTkLabel(selector_frame, text="", anchor="w", justify="left")
                self.photo_path_label.grid(row=0, column=1, sticky="ew")
                self._refresh_photo_path_label()

                self.user_info_widgets[field] = self.photo_path_button
            else:
                # Per i campi che vogliamo con il bottone occhio, creiamo un frame contenitore
                if field in [DBUsersColumns.PASSWORD_LOGIN.value,
                             DBUsersColumns.REDDITO_ESTERNO.value,
                             DBUsersColumns.SPESE_DEDOTTE_ESTERNE.value,
                             DBUsersColumns.LAST_YEAR_IRPEF_ACCONTO.value,
                             DBUsersColumns.LAST_YEAR_INPS_ACCONTO.value]:

                    # Creiamo un frame per contenere entry e bottone
                    entry_frame = ctk.CTkFrame(frame, fg_color="transparent")
                    entry_frame.grid(row=row, column=1, sticky="ew", padx=(5, 15),
                                     pady=(2, 5) if field in validation_rules.keys() else (2, 35))

                    # Configurazione griglia del frame
                    entry_frame.grid_columnconfigure(0, weight=1)  # Entry si espande
                    entry_frame.grid_columnconfigure(1, weight=0)  # Bottone dimensione fissa

                    # Creazione entry
                    widget = config["type"](entry_frame, show="*" if config.get("password", False) else "")

                    # PER IL CAMPO PASSWORD_LOGIN: mostra sempre stringa vuota invece dell'hash
                    if field == DBUsersColumns.PASSWORD_LOGIN.value:
                        # Controlla se nel database è presente un hash valido
                        stored_hash = user_data.get(field, "")
                        # Considera l'hash presente se non è None, non è stringa vuota e ha lunghezza sufficiente
                        # (un hash PBKDF2 con salt di 32 byte + hash di 32 byte sarà di 128 caratteri esadecimali)
                        self.login_password_is_present = (stored_hash is not None and
                                                          stored_hash != "" and
                                                          len(stored_hash) >= 128)
                        value = ""  # Non mostrare l'hash, campo vuoto
                    else:
                        value = str(user_data.get(field, ""))

                    widget.insert(0, value)
                    widget.grid(row=0, column=0, sticky="ew", padx=(0, 5))

                    # Creazione bottone occhio
                    eye_button = ctk.CTkButton(
                        entry_frame,
                        text="👁",
                        width=30,
                        command=lambda w=widget: ViewUtils.toggle_entry_visibility(w)
                    )
                    eye_button.grid(row=0, column=1, sticky="e")

                    # Aggiungi il bottone alla lista
                    self.eye_buttons.append(eye_button)
                    self.user_info_widgets[field] = widget

                else:
                    # Per gli altri campi, creazione normale
                    widget = config["type"](frame, show="*" if config.get("password", False) else "")
                    value = str(user_data.get(field, ""))

                    widget.insert(0, value)
                    widget.grid(row=row, column=1, sticky="ew", padx=(5, 15),
                                pady=(2, 5) if field in validation_rules.keys() else (2, 35))
                    self.user_info_widgets[field] = widget

            # Gestione validazione (rimane invariata)
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

    def _refresh_photo_path_label(self):
        if self.photo_path_label is None:
            return

        if self.selected_photo_path:
            if os.path.exists(self.selected_photo_path):
                text = os.path.basename(self.selected_photo_path)
                text_color = "#c2c2c2"
            else:
                text = f"Percorso immagine non valido: {os.path.basename(self.selected_photo_path)}"
                text_color = "#e8a23a"
        else:
            text = "ancora nessuna immagine selezionata"
            text_color = "#c2c2c2"

        self.photo_path_label.configure(text=text, text_color=text_color)

    def choose_photo_path(self):
        filetypes = [("Immagini", "*.png *.jpg *.jpeg *.gif")]
        path = filedialog.askopenfilename(title="Seleziona un'immagine", filetypes=filetypes)

        if path:
            self.selected_photo_path = path
            self._refresh_photo_path_label()

            top_level = self.winfo_toplevel()
            top_level.lift()
            top_level.focus_force()

    def toggle_edit(self, parent_widget):
        """
        Abilita o disabilita la modifica dei widget nella finestra di modifica utente.
        """
        # Determina lo stato (abilitato/disabilitato) in base al valore dello switch
        state = ctk.NORMAL if self.switch_modify.get() else ctk.DISABLED

        # Cambia anche lo stato del pulsante Salva
        self.save_info_btn.configure(state=state)

        for w in parent_widget.winfo_children():
            # se è un Entry
            if isinstance(w, ctk.CTkEntry):
                w.configure(state=state, text_color="#636363" if state == ctk.DISABLED else "#c2c2c2")
            # se è un OptionMenu
            elif isinstance(w, ctk.CTkOptionMenu):
                w.configure(state=state)
            # se è un Frame/container, scendi ricorsivamente
            elif isinstance(w, (ctk.CTkFrame, ctk.CTkScrollableFrame, ctk.CTkToplevel)):
                self.toggle_edit(w)

        # Gestione specifica dei bottoni occhio
        for eye_button in self.eye_buttons:
            eye_button.configure(state=state)

        if self.photo_path_button is not None:
            self.photo_path_button.configure(state=state)

    def toggle_sensible_data(self):
        # Determina lo stato (abilitato/disabilitato) in base al valore dello switch
        state = ctk.NORMAL if self.switch_modify.get() else ctk.DISABLED

        if self.parent.login_status and self.parent.logged_user_id == self.current_user_id:
            self.user_info_widgets.get(DBUsersColumns.PASSWORD_LOGIN.value).configure(state=state, text_color="#636363" if state == ctk.DISABLED else "#c2c2c2")
            self.user_info_widgets.get(DBUsersColumns.REDDITO_ESTERNO.value).configure(state=state, text_color="#636363" if state == ctk.DISABLED else "#c2c2c2")
            self.user_info_widgets.get(DBUsersColumns.LAST_YEAR_INPS_ACCONTO.value).configure(state=state, text_color="#636363" if state == ctk.DISABLED else "#c2c2c2")
            self.user_info_widgets.get(DBUsersColumns.LAST_YEAR_IRPEF_ACCONTO.value).configure(state=state, text_color="#636363" if state == ctk.DISABLED else "#c2c2c2")
            spese_dedotte_esterne = self.user_info_widgets.get(DBUsersColumns.SPESE_DEDOTTE_ESTERNE.value)
            if spese_dedotte_esterne is not None:
                spese_dedotte_esterne.configure(state=state, text_color="#636363" if state == ctk.DISABLED else "#c2c2c2")
            for button in self.eye_buttons:
                button.configure(state=state)

        else:
            self.user_info_widgets.get(DBUsersColumns.PASSWORD_LOGIN.value).configure(state=ctk.DISABLED, text_color="#636363", show="*") \
                if self.login_password_is_present \
                else self.user_info_widgets.get(DBUsersColumns.PASSWORD_LOGIN.value).configure(state=state, text_color="#636363" if state == ctk.DISABLED else "#c2c2c2")

            self.user_info_widgets.get(DBUsersColumns.REDDITO_ESTERNO.value).configure(state=ctk.DISABLED, text_color="#636363", show="*" )
            self.user_info_widgets.get(DBUsersColumns.LAST_YEAR_INPS_ACCONTO.value).configure(state=ctk.DISABLED, text_color="#636363", show="*")
            self.user_info_widgets.get(DBUsersColumns.LAST_YEAR_IRPEF_ACCONTO.value).configure(state=ctk.DISABLED, text_color="#636363", show="*")
            spese_dedotte_esterne =  self.user_info_widgets.get(DBUsersColumns.SPESE_DEDOTTE_ESTERNE.value)
            if spese_dedotte_esterne is not None:
                spese_dedotte_esterne.configure(state=ctk.DISABLED, text_color="#636363", show="*")
            for i, button in enumerate(self.eye_buttons):
                if i == 0 and not self.login_password_is_present:
                    # Se non è presente la password, il primo bottone (password login) segue lo stato generale
                    button.configure(state=state)
                else:
                    # Altrimenti, tutti i bottoni sono disabilitati
                    button.configure(state=ctk.DISABLED)

    def toggle_widget_container_function(self, parent_widget):
        self.toggle_edit(parent_widget)
        self.toggle_sensible_data()

    def save_info_mod(self):
        """Salva i dati dell'utente tramite il controller"""

        nome_conto = self.user_info_widgets[self.nome_conto_string].get()
        conto = self.accounts_query_service.retrieve_account_map_by_name(nome_conto)
        id_conto = conto[DBAccountsColumns.ID.value] if conto else None

        user_data = {
            DBUsersColumns.FIRST_NAME.value: self.user_info_widgets[DBUsersColumns.FIRST_NAME.value].get().strip(),
            DBUsersColumns.LAST_NAME.value: self.user_info_widgets[DBUsersColumns.LAST_NAME.value].get().strip(),
            DBUsersColumns.PARTITA_IVA.value: self.user_info_widgets[DBUsersColumns.PARTITA_IVA.value].get().strip(),
            DBUsersColumns.CODICE_FISCALE.value: self.user_info_widgets[DBUsersColumns.CODICE_FISCALE.value].get().strip(),
            DBUsersColumns.TELEFONO.value: self.user_info_widgets[DBUsersColumns.TELEFONO.value].get().strip(),
            DBUsersColumns.EMAIL.value: self.user_info_widgets[DBUsersColumns.EMAIL.value].get().strip(),
            DBUsersColumns.REDDITO_ESTERNO.value: self.user_info_widgets[DBUsersColumns.REDDITO_ESTERNO.value].get().strip(),
            DBUsersColumns.SPESE_DEDOTTE_ESTERNE.value: self.user_info_widgets[DBUsersColumns.SPESE_DEDOTTE_ESTERNE.value].get().strip() if DBUsersColumns.SPESE_DEDOTTE_ESTERNE.value in self.user_info_widgets else 0,
            DBUsersColumns.PROVIDER_FATTURE.value: self.user_info_widgets[DBUsersColumns.PROVIDER_FATTURE.value].get(),
            DBUsersColumns.USERNAME_PROVIDER.value: self.user_info_widgets[DBUsersColumns.USERNAME_PROVIDER.value].get().strip(),
            DBUsersColumns.PASSWORD_PROVIDER.value: self.user_info_widgets[DBUsersColumns.PASSWORD_PROVIDER.value].get().strip(),
            DBUsersColumns.REGIME_FISCALE.value: self.user_info_widgets[DBUsersColumns.REGIME_FISCALE.value].get(),
            DBUsersColumns.PHOTO_PATH.value: self.selected_photo_path.strip(),
            DBUsersColumns.CONTO_CORRENTE_ID.value: id_conto,  # Da aggiornare se necessario
            DBUsersColumns.ANNO_APERTURA_PIVA.value: self.user_info_widgets[DBUsersColumns.ANNO_APERTURA_PIVA.value].get(),
            DBUsersColumns.STATUS.value: self.user_info_widgets[DBUsersColumns.STATUS.value].get(),
        }

        #mando i dati della nuova password al controller per il salvataggio, solo se una nuova password è stata inserita
        password_value = self.user_info_widgets[DBUsersColumns.PASSWORD_LOGIN.value].get().strip()
        if password_value:
            user_data[DBUsersColumns.PASSWORD_LOGIN.value] = password_value

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
                "value" : self.user_analyzer_service.calcola_tot_fatturato_utente(self.current_user_id),
                "uom" : "€"
            }
        }

        self.global_infos_invoices_widgets = ViewUtils.construct_global_infos_cards(section_frame, global_infos)

        # tabella invoices
        invoices_frame = ctk.CTkScrollableFrame(section_frame, height=300)
        invoices_frame.pack(fill="both", expand=True, padx=(10, 20), pady=(10, 20))

        # popolo gli invoices
        invoices = self.user_query_service.retrieve_user_with_invoices_map_list(self.current_user_id)
        for invoice in invoices:
            if invoice[DBInvoicesColumns.NUMERO_FATTURA.value] is not None:
                nome_fattura = invoice[DBInvoicesColumns.NUMERO_FATTURA.value]
                id_fattura = invoice[DBInvoicesColumns.ID.value]
                id_produzione = invoice[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value]
                produzione = self.productions_query_service.retrieve_production_map_by_id(id_produzione)
                nome_prod = produzione[DBProductionsColumns.NAME.value] if produzione else "Produzione non trovata"
                fattura_button = ctk.CTkButton(invoices_frame,
                                               text=f"{nome_fattura} - {nome_prod}",
                                               command=lambda id=id_fattura: self.show_invoice_detail(id))
                fattura_button.pack(padx=10, pady=10, fill="x", expand=True)

    def show_invoice_detail(self, invoice_id):
        self.event_bus.publish(ViewUtils.EventBusKeys.SHOW_INVOICE_DETAIL, invoice_id)

    def show_salary_detail(self, invoice_id):
        self.event_bus.publish(ViewUtils.EventBusKeys.SHOW_SALARY_DETAIL, invoice_id)

    def show_expense_detail(self, expense_id):
        self.event_bus.publish(ViewUtils.EventBusKeys.SHOW_EXPENSE_DETAIL, expense_id)

    def _create_anticipated_expenses_history(self):
        """Crea la sezione storico delle spese anticipate"""
        section_frame = ctk.CTkFrame(self.wrapper_frame, border_width=2, border_color="#2659ab")
        section_frame.pack(fill="both", side="left", expand=True, pady=0, padx=(0, 30))

        ctk.CTkLabel(section_frame, text="SPESE ANTICIPATE", font=("Arial", 14, "bold")).pack(anchor="w", pady=(10, 10), padx=10)

        global_infos = {
            "TOTALE SPESE ANTICIPATE" : {
                "value" : self.user_analyzer_service.calcola_tot_spese_utente_anticipate(self.current_user_id),
                "uom" : "€"
            }
        }

        self.global_infos_invoices_widgets = ViewUtils.construct_global_infos_cards(section_frame, global_infos)

        # tabella invoices
        expenses_frame = ctk.CTkScrollableFrame(section_frame, height=300)
        expenses_frame.pack(fill="both", expand=True, padx=(10, 20), pady=(10, 20))

        # popolo gli invoices
        expenses = self.user_query_service.retrieve_user_with_anticipated_expenses_map_list(self.current_user_id)
        for expense in expenses:
            if expense[DBExpensesColumns.NAME.value] is not None:
                nome_spesa = expense[DBExpensesColumns.NAME.value]
                id_spesa = expense[DBExpensesColumns.ID.value]
                spesa_button = ctk.CTkButton(expenses_frame,
                                             text=f"{nome_spesa}",
                                             command=lambda id=id_spesa: self.show_expense_detail(id))
                spesa_button.pack(padx=10, pady=10, fill="x", expand=True)

    def _create_deduz_expenses_history(self):
        """Crea la sezione storico delle spese messe in deduzione"""
        section_frame = ctk.CTkFrame(self.wrapper_frame, border_width=2, border_color="#2659ab")
        section_frame.pack(fill="both", side="left", expand=True, pady=0, padx=0)

        ctk.CTkLabel(section_frame, text="SPESE IN DEDUZIONE", font=("Arial", 14, "bold")).pack(anchor="w", pady=(10, 10), padx=10)

        global_infos = {
            "TOTALE SPESE IN DEDUZIONE" : {
                "value" : self.user_analyzer_service.calcola_tot_spese_utente_dedotte(self.current_user_id),
                "uom" : "€"
            }
        }

        self.global_infos_invoices_widgets = ViewUtils.construct_global_infos_cards(section_frame, global_infos)

        # tabella invoices
        expenses_frame = ctk.CTkScrollableFrame(section_frame, height=300)
        expenses_frame.pack(fill="both", expand=True, padx=(10, 20), pady=(10, 20))

        # popolo gli invoices
        expenses = self.user_query_service.retrieve_user_with_deducted_expenses_map_list(self.current_user_id)
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
                "value" : self.user_analyzer_service.calcola_tot_salari_utente(self.current_user_id),
                "uom" : "€"
            }
        }

        self.global_infos_invoices_widgets = ViewUtils.construct_global_infos_cards(section_frame, global_infos)

        # tabella invoices
        salary_frame = ctk.CTkScrollableFrame(section_frame, height=300)
        salary_frame.pack(fill="both", expand=True, padx=(10, 20), pady=(10, 20))

        # popolo gli invoices
        salaries = self.user_query_service.retrieve_user_with_salaries_map_list(self.current_user_id)
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

        user_fiscal_data = self.user_analyzer_service.pick_fiscal_data_by_user_id(self.current_user_id)

        # Prendo i dati suddivisi da controller
        user_fiscal_data = self.user_analyzer_service.pick_fiscal_data_by_user_id(self.current_user_id)
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

        regime_fiscale = self.user_query_service.get_regime_fiscale_by_id(self.current_user_id)
        if str(regime_fiscale) == str(RegimeFiscale.FORFETTARIO.value):
            tasse, versamenti, total = self.user_analyzer_service.calculate_previsione_tasse_forfettaria(self.current_user_id)
            global_infos = {}
            versamenti_infos = {}

            # Costruzione dei dati per i totali
            for k, v in tasse.items():
                global_infos[k] = {
                    "value": v,
                    "uom": "€"
                }

            # Costruzione dei dati per i versamenti
            for k, v in versamenti.items():
                # Usiamo direttamente il nome della chiave formattato per multi-riga
                display_name = ViewUtils.split_string_by_length(k, 8)
                versamenti_infos[display_name] = {
                    "value": v,
                    "uom": "€"
                }

            # Visualizzazione dei totali
            ctk.CTkLabel(self.tax_frame, text="TOTALI", font=("Arial", 12)).pack(anchor="w", pady=(0, 10), padx=15)
            self.tasse_infos_user_widgets = ViewUtils.construct_tasse_infos_cards(self.tax_frame, global_infos)

            # Visualizzazione dei versamenti
            ctk.CTkLabel(self.tax_frame, text="VERSAMENTI", font=("Arial", 12)).pack(anchor="w", pady=(10, 0), padx=15)
            self.versamenti_infos_user_widgets = ViewUtils.construct_tasse_infos_cards(self.tax_frame, versamenti_infos)

            # Formattatore numerico
            def fmt(num):
                return f"{num:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")

            # Tooltip per le carte dei totali
            for key, widget_info in self.tasse_infos_user_widgets.items():
                card = widget_info["card"]
                title_label = card.winfo_children()[0]

                if key == "INPS":
                    tooltip_text = (
                        f"Calcolo contributi INPS complessivi:\n\n"
                        f"1. Fatturato totale = Fatturato Willow + Reddito esterno\n"
                        f"   = {fmt(total['FATTURATO_WILLOW'])} + {fmt(total['REDDITO_ESTERNO'])}\n"
                        f"   = {fmt(total['FATTURATO_WILLOW'] + total['REDDITO_ESTERNO'])} €\n\n"
                        f"2. Reddito imponibile = Fatturato totale × Coefficiente di redditività ({total['COEFFICIENTE_IMPONIBILE'] * 100:.2f}%)\n"
                        f"   = {fmt(total['FATTURATO_WILLOW'] + total['REDDITO_ESTERNO'])} × {total['COEFFICIENTE_IMPONIBILE']:.4f}\n"
                        f"   = {fmt(total['REDDITO_TOT'])} €\n\n"
                        f"3. Contributi INPS = Reddito imponibile × Aliquota INPS ({total['ALIQUOTA_INPS'] * 100:.2f}%)\n"
                        f"   = {fmt(total['REDDITO_TOT'])} × {total['ALIQUOTA_INPS']:.4f}\n"
                        f"   = {fmt(total['INPS'])} €"
                    )

                elif key == "IRPEF":
                    tooltip_text = (
                        f"Calcolo imposta sostitutiva IRPEF:\n\n"
                        f"1. Reddito imponibile = {fmt(total['REDDITO_TOT'])} €\n"
                        f"2. Aliquota IRPEF = {total['ALIQUOTA_IRPEF'] * 100:.2f}%\n"
                        f"3. Imposta sostitutiva = Reddito imponibile × Aliquota IRPEF\n"
                        f"   = {fmt(total['REDDITO_TOT'])} × {total['ALIQUOTA_IRPEF']:.4f}\n"
                        f"   = {fmt(total['IRPEF'])} €"
                    )

                elif key == "IRPEF WILLOW":
                    tooltip_text = (
                        f"Quota IRPEF attribuibile a Willow:\n\n"
                        f"1. Quota proporzionale Willow = {total['QUOTA_WILLOW']:.4f}\n"
                        f"2. IRPEF Willow = IRPEF totale × Quota proporzionale\n"
                        f"   = {fmt(total['IRPEF'])} × {total['QUOTA_WILLOW']:.4f}\n"
                        f"   = {fmt(total['IRPEF WILLOW'])} €"
                    )

                elif key == "INPS WILLOW":
                    tooltip_text = (
                        f"Quota INPS attribuibile a Willow:\n\n"
                        f"1. Fatturato Willow = {fmt(total['FATTURATO_WILLOW'])} €\n"
                        f"2. Reddito imponibile Willow = Fatturato Willow × Coefficiente di redditività\n"
                        f"   = {fmt(total['FATTURATO_WILLOW'])} × {total['COEFFICIENTE_IMPONIBILE']:.4f}\n"
                        f"   = {fmt(total['REDDITO_WILLOW'])} €\n"
                        f"3. Quota proporzionale Willow = Reddito imponibile Willow / Reddito imponibile totale\n"
                        f"   = {fmt(total['REDDITO_WILLOW'])} / {fmt(total['REDDITO_TOT'])}\n"
                        f"   = {total['QUOTA_WILLOW']:.4f}\n"
                        f"4. INPS Willow = INPS totale × Quota proporzionale\n"
                        f"   = {fmt(total['INPS'])} × {total['QUOTA_WILLOW']:.4f}\n"
                        f"   = {fmt(total['INPS WILLOW'])} €"
                    )

                else:
                    tooltip_text = "Informazioni non disponibili"

                ViewUtils.add_tooltip(title_label, tooltip_text)

            # Tooltip per le carte dei versamenti
            for key, widget_info in self.versamenti_infos_user_widgets.items():
                card = widget_info["card"]
                title_label = card.winfo_children()[0]

                if key == "SALDO\nTOTALE":
                    tooltip_text = (
                        f"Calcolo saldo totale:\n\n"
                        f"1. Tasse totali (INPS + IRPEF) = {fmt(total['TOTALE_TASSE'])} €\n"
                        f"2. Acconto versato per l'anno precedente = {fmt(total['ACCONTO_ANNO_PRECEDENTE'])} €\n"
                        f"3. Saldo = Tasse totali - Acconto anno precedente\n"
                        f"   = {fmt(total['TOTALE_TASSE'])} - {fmt(total['ACCONTO_ANNO_PRECEDENTE'])}\n"
                        f"   = {fmt(total['SALDO_CORRENTE'])} €"
                    )

                elif key == "ACCONTO\nTOTALE":
                    tooltip_text = (
                        f"Calcolo acconto totale per l'anno successivo:\n\n"
                        f"1. Acconto IRPEF = IRPEF totale × ({total['PERC_ACC_IMP_PRIMO'] * 100:.2f}% + {total['PERC_ACC_IMP_SECONDO'] * 100:.2f}%)\n"
                        f"   = {fmt(total['IRPEF'])} × {total['PERC_ACC_IMP_PRIMO'] + total['PERC_ACC_IMP_SECONDO']:.4f}\n"
                        f"   = {fmt(total['PRIMO_ACCONTO_IRPEF'] + total['SECONDO_ACCONTO_IRPEF'])} €\n\n"
                        f"2. Acconto INPS = INPS totale × {total['PERC_ACC_INPS'] * 100:.2f}%\n"
                        f"   = {fmt(total['INPS'])} × {total['PERC_ACC_INPS']:.4f}\n"
                        f"   = {fmt(total['PRIMO_ACCONTO_INPS'] + total['SECONDO_ACCONTO_INPS'])} €\n\n"
                        f"3. Totale acconto = Acconto IRPEF + Acconto INPS\n"
                        f"   = {fmt(total['PRIMO_ACCONTO_IRPEF'] + total['SECONDO_ACCONTO_IRPEF'])} + {fmt(total['PRIMO_ACCONTO_INPS'] + total['SECONDO_ACCONTO_INPS'])}\n"
                        f"   = {fmt(total['ACCONTO_TOTALE'])} €"
                    )

                elif key == "SALDO\nWILLOW":
                    tooltip_text = (
                        f"Quota del saldo corrente attribuita a Willow:\n\n"
                        f"1. Saldo totale = {fmt(total['SALDO_CORRENTE'])} €\n"
                        f"2. Quota proporzionale Willow = {total['QUOTA_WILLOW']:.4f}\n"
                        f"3. Saldo Willow = Saldo totale × Quota proporzionale\n"
                        f"   = {fmt(total['SALDO_CORRENTE'])} × {total['QUOTA_WILLOW']:.4f}\n"
                        f"   = {fmt(total['SALDO_WILLOW'])} €"
                    )

                elif key == "ACCONTO\nWILLOW":
                    tooltip_text = (
                        f"Quota dell'acconto per l'anno successivo attribuita a Willow:\n\n"
                        f"1. Acconto totale = {fmt(total['ACCONTO_TOTALE'])} €\n"
                        f"2. Quota proporzionale Willow = {total['QUOTA_WILLOW']:.4f}\n"
                        f"3. Acconto Willow = Acconto totale × Quota proporzionale\n"
                        f"   = {fmt(total['ACCONTO_TOTALE'])} × {total['QUOTA_WILLOW']:.4f}\n"
                        f"   = {fmt(total['ACCONTO_WILLOW'])} €"
                    )

                else:
                    tooltip_text = "Informazioni non disponibili"

                ViewUtils.add_tooltip(title_label, tooltip_text)

        elif str(regime_fiscale) == str(RegimeFiscale.ORDINARIO.value):
            tasse_view, versamenti, tasse_total = self.user_analyzer_service.calculate_previsione_tasse_ordinaria(self.current_user_id)
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
        iva_data = self.iva_analyzer_service.calculate_trimestral_iva_by_user_id(self.current_user_id)

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
        tasse, versamenti, output_map = self.user_analyzer_service.calculate_previsione_tasse_forfettaria(self.current_user_id)

        # Aggiorna le labels nelle cards esistenti
        for name, value in tasse.items():
            if name in self.tasse_infos_user_widgets:
                # Formatta il nuovo valore con l'unità di misura
                new_text = f"{value} €"

                # Aggiorna il testo della label
                self.tasse_infos_user_widgets[name]["label"].configure(text=new_text)

    def _cleanup_and_go_back(self):
        """Pulizia completa prima di tornare indietro"""
        self.switch_modify.deselect()
        self.toggle_widget_container_function(self.content_frame)

        self._clear_content()
        self.pack_forget()
        self.back_callback()

        self.eye_buttons.clear()
        self.user_info_widgets.clear()
        self.login_password_is_present = False
        self.selected_photo_path = ""
        self.photo_path_button = None
        self.photo_path_label = None

    def _on_login_changed_detail(self, data):
        self.toggle_sensible_data()

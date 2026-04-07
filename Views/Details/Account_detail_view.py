import customtkinter as ctk
from datetime import datetime

from App_context import AppContext
from Views.View_utils import ViewUtils

from QueryServices.Account_query_service import AccountQueryService

from Gestionale_Enums import*

class AccountDetailView(ctk.CTkFrame):
    def __init__(self, parent, back_callback, app_context:AppContext):
        super().__init__(parent)
        self.account_controller = app_context.account_controller
        self.accounts_query_service:AccountQueryService = app_context.account_query_service
        self.analyzer = app_context.analyzer
        self.db_model = app_context.db_model
        self.back_callback = back_callback
        self.update_controller = app_context.update_controller
        self.event_bus = app_context.event_bus
        self.current_expense_id = None
        self.catalogo_elenchi = app_context.catalogo_elenchi
        self.parent = parent

        self.configure(fg_color="transparent")



        # Widgets persistenti (vanno creati una volta sola)
        self.head_frame = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.back_button = ctk.CTkButton(
            self.head_frame,
            text="Torna ai conti",
            command=self._cleanup_and_go_back
        )
        self.title_label = ctk.CTkLabel(self.head_frame, font=("Arial", 22, "bold"))

        self.expense_info_widgets: dict[str, ctk.CTkEntry | ctk.CTkOptionMenu] = {}

        # Container per i contenuti dinamici
        self.content_frame = ctk.CTkFrame(self)

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

    def create_detail_tab(self, account_id):
        """Ricrea la vista dettaglio per un conto specifico"""
        self.current_account_id = account_id

        # 1. Pulizia dei widget precedenti
        self._clear_content()

        # 2. Caricamento dati
        self.account = self.accounts_query_service.retrieve_account_map_by_id(account_id)

        # 3. Aggiornamento elementi persistenti
        self.title_label.configure(
            text=f"{self.account[DBAccountsColumns.NAME.value]}")

        # 4. Creazione contenuti dinamici
        self._create_account_info_section(self.account)
        self.toggle_edit(self.content_frame)

    def _create_account_info_section(self, account_data):
        # Recupera i movimenti del conto
        movements = self.analyzer.retrieve_account_movements_by_account_id(self.current_account_id)

        # Calcola il saldo corrente
        current_balance = float(account_data[DBAccountsColumns.INIT_BALANCE.value])
        for mov in movements:
            if mov['sign'] == '+':
                current_balance += mov['amount']
            else:
                current_balance -= mov['amount']

        # Dizionari per la configurazione
        self.entry_fields = {
            # Sezione Dati Conto
            DBAccountsColumns.NAME.value: {
                "type": ctk.CTkEntry,
                "label": "Nome Conto",
                "section": "Dati Conto"
            },
            DBAccountsColumns.INIT_BALANCE.value: {
                "type": ctk.CTkEntry,
                "label": f"Saldo Iniziale\n(31-12-{datetime.now().year - 1})",
                "section": "Dati Conto"
            },
            "current_balance": {
                "type": ctk.CTkLabel,
                "label": "Saldo Corrente",
                "section": "Dati Conto"
            }
        }

        # Formatta i saldi per la visualizzazione
        account_data[
            DBAccountsColumns.INIT_BALANCE.value] = f"{float(account_data[DBAccountsColumns.INIT_BALANCE.value]):.2f} "
        account_data["current_balance"] = f"{current_balance:.2f} €"

        # Regole di validazione
        validation_rules = {
            DBAccountsColumns.NAME.value: (
                lambda val: val.strip() != "",
                "Il nome del conto non può essere vuoto"
            )
        }

        # Inizializzazione strutture dati
        self.account_info_widgets = {}
        self.error_labels = {}
        sections = {}

        # Creazione frame principale
        self.info_frame = ctk.CTkFrame(self.content_frame, border_width=2, border_color="#2659ab")
        self.info_frame.pack(pady=10, padx=10, side="left", anchor="n", fill="y", expand=False)

        # Non serve più configurare la griglia poiché useremo pack
        # sections_order rimane lo stesso
        sections_order = ["Dati Conto"]

        sections = {}
        container_frame = ctk.CTkFrame(self.info_frame, fg_color="transparent")
        container_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Crea i frame per ogni sezione
        for section_name in sections_order:
            # Frame principale per la sezione
            section_frame = ctk.CTkFrame(container_frame)
            section_frame.pack(fill="x", padx=5, pady=5, side="top")

            # Titolo della sezione
            ctk.CTkLabel(section_frame, text=section_name, font=("Arial", 14, "bold")).pack(
                anchor="w", padx=15, pady=(5, 10)
            )

            # Frame per i campi
            fields_frame = ctk.CTkFrame(section_frame)
            fields_frame.pack(fill="x", padx=10, pady=5)

            sections[section_name] = {
                "frame": fields_frame,
                "row": 0
            }

        # Popolamento delle sezioni
        for field, config in self.entry_fields.items():
            section = sections[config["section"]]
            frame = section["frame"]

            # Frame per ogni campo
            field_frame = ctk.CTkFrame(frame, fg_color="transparent")
            field_frame.pack(fill="x", pady=3)

            # Creazione label
            lbl = ctk.CTkLabel(field_frame, text=config["label"] + ":", width=150, anchor="nw")
            lbl.pack(side="left", padx=(15, 5), pady=2)

            # Frame per widget e errori
            widget_frame = ctk.CTkFrame(field_frame, fg_color="transparent")
            widget_frame.pack(side="right", fill="x", expand=True, padx=(0, 15))

            # Creazione widget
            value = str(account_data.get(field, ""))

            if config["type"] == ctk.CTkOptionMenu:
                widget = config["type"](widget_frame, values=config.get("values", []))
                widget.set(value if value else config.get("values", [""])[0])
            elif config["type"] == ctk.CTkTextbox:
                widget = config["type"](widget_frame, height=config.get("height", 50))
                widget.insert("1.0", value)
            elif config["type"] == ctk.CTkLabel:
                widget = config["type"](widget_frame, text=value)
            else:
                widget = config["type"](widget_frame)
                if value:
                    widget.insert(0, value)

            widget.pack(fill="x", padx=(5, 0), pady=2)

            # Gestione errori
            if field in validation_rules:
                error_frame = ctk.CTkFrame(widget_frame, fg_color="transparent")
                error_frame.pack(fill="x", pady=(0, 5))

                # Spaziatore vuoto per allineamento
                ctk.CTkLabel(error_frame, text="", width=150).pack(side="left")

                error_lbl = ctk.CTkLabel(error_frame, text="", text_color="#e8e5dc", anchor="w")
                error_lbl.pack(side="left", fill="x", expand=True)
                self.error_labels[field] = error_lbl

                # Binding per validazione
                if config["type"] != ctk.CTkTextbox:
                    widget.bind("<FocusOut>",
                                lambda e, w=widget,
                                       vl=validation_rules[field][0],
                                       el=error_lbl,
                                       em=validation_rules[field][1]:
                                ViewUtils.validate_entry(w, vl, el, em))
                else:
                    widget.bind("<FocusOut>",
                                lambda e, w=widget,
                                       vl=validation_rules[field][0],
                                       el=error_lbl,
                                       em=validation_rules[field][1]:
                                ViewUtils.validate_textbox(w, vl, el, em))

            self.account_info_widgets[field] = widget

        # Frame per i bottoni
        buttons_frame = ctk.CTkFrame(container_frame, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=20, pady=(15, 5), side="bottom")

        # Bottone Salva
        self.save_info_btn = ctk.CTkButton(buttons_frame, text="Salva Conto", command=self.save_account_mod)
        self.save_info_btn.pack(side="left", padx=(0, 10), pady=5)

        # Sezione Storico Movimenti (non editabile)
        movements_frame = ctk.CTkFrame(self.content_frame, border_width=2, border_color="#2659ab")
        movements_frame.pack(fill="both", expand=True, pady=10, padx=25)

        # Configura il grid per espandere la riga dello scrollable frame
        movements_frame.grid_columnconfigure(0, weight=1)
        movements_frame.grid_rowconfigure(2, weight=1)  # IMPORTANTE: rende la riga espandibile

        # Titolo sezione
        ctk.CTkLabel(movements_frame, text="Storico Movimenti", font=("Arial", 14, "bold")).grid(
            row=0, column=0, sticky="nw", padx=15, pady=10
        )

        # Frame per l'intestazione
        header_frame = ctk.CTkFrame(movements_frame, fg_color="#3b3b3b")
        header_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 5))

        # Intestazioni
        headers = ["Data", "Descrizione", "Tipo", "Importo"]
        header_widths = [300, 400, 300, 300]
        for col, (header, width) in enumerate(zip(headers, header_widths)):
            ctk.CTkLabel(header_frame, text=header, font=("Arial", 12, "bold"),
                         width=width).grid(row=0, column=col, padx=5, pady=5)

        # Frame scrollabile per i movimenti - RIMOSSO L'ALTEZZA FISSA
        scrollable_frame = ctk.CTkScrollableFrame(movements_frame)
        scrollable_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        scrollable_frame.grid_columnconfigure(1, weight=1)

        # Aggiungi i movimenti
        for row, mov in enumerate(movements):
            # Crea un frame per ogni riga
            row_frame = ctk.CTkFrame(scrollable_frame)
            row_frame.grid(row=row, column=0, sticky="ew", pady=2)

            # Alterna il colore di sfondo per migliorare la leggibilità
            if row % 2 == 0:
                row_frame.configure(fg_color="#2a2d2e")
            else:
                row_frame.configure(fg_color="#333333")

            # Data
            date_label = ctk.CTkLabel(row_frame, text=mov["date"], width=header_widths[0])
            date_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

            # Descrizione
            desc_label = ctk.CTkLabel(row_frame, text=mov["name"], width=header_widths[1], anchor="center")
            desc_label.grid(row=0, column=1, padx=5, pady=5, sticky="w")

            # Tipo
            type_label = ctk.CTkLabel(row_frame, text=mov["type"], width=header_widths[2])
            type_label.grid(row=0, column=2, padx=5, pady=5, sticky="w")

            # Importo
            amount_text = f"{mov['sign']}{mov['amount']:.2f} €"
            amount_color = "#2ECC71" if mov['sign'] == '+' else "#E74C3C"
            amount_label = ctk.CTkLabel(row_frame, text=amount_text, width=header_widths[3],
                                        text_color=amount_color)
            amount_label.grid(row=0, column=3, padx=5, pady=5, sticky="e")

            # Configura le colonne
            for col in range(4):
                row_frame.grid_columnconfigure(col, weight=1 if col == 1 else 0)

    def save_account_mod(self):
        account_data = {
            DBAccountsColumns.NAME.value: self.account_info_widgets[
                DBAccountsColumns.NAME.value].get().strip(),
            DBAccountsColumns.INIT_BALANCE.value: self.account_info_widgets[
                DBAccountsColumns.INIT_BALANCE.value].get().strip()
        }

        # Chiamata al controller per salvare i dati
        success, message = self.account_controller.update_account(self.current_account_id, account_data)
        if success:
            print(
                f"Conto {self.accounts_query_service.retrieve_account_map_by_id(self.current_account_id)[DBAccountsColumns.NAME.value]} salvato con successo")
            ViewUtils.show_confirm_popup_2(self.content_frame, "SALVATAGGIO COMPLETATO", message)
            self.switch_modify.deselect()
            self.toggle_edit(self.content_frame)
        else:
            # Mostra il messaggio d'errore
            print(message)
            ViewUtils.show_error_popup(self.content_frame, "ERRORE", message)

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
            if isinstance(w, (ctk.CTkEntry, ctk.CTkTextbox)):
                w.configure(state=state, text_color="#636363" if state == ctk.DISABLED else "#c2c2c2")
            # se è un OptionMenu
            elif isinstance(w, ctk.CTkOptionMenu):
                w.configure(state=state)
            # se è un Frame/container, scendi ricorsivamente
            elif isinstance(w, (ctk.CTkFrame, ctk.CTkScrollableFrame, ctk.CTkToplevel)):
                self.toggle_edit(w)

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
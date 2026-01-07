import customtkinter as ctk
import re
from Views.View_utils import ViewUtils, FilterableComboBox
from Controllers import ControllerUtils, ClientController
from Model import DBClientsColumns, DBInvoicesColumns, DBProductionsColumns, DBRefundsColumns


class ClientsView(ctk.CTkFrame):
    def __init__(self, db_model, client_controller, production_controller, invoice_controller, refund_controller, catalogo_elenchi, config_manager, tab, event_bus, analyzer):
        super().__init__(tab)

        self.db_model = db_model
        self.client_controller = client_controller
        self.tab = tab
        self.catalogo_elenchi = catalogo_elenchi
        self.config_manager = config_manager
        self.production_controller = production_controller
        self.invoice_controller = invoice_controller
        self.refund_controller = refund_controller
        self.event_bus = event_bus
        self.analyzer = analyzer

        self.clients_card_list = {}

        # Container principale
        self.main_container = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.detail_container = ctk.CTkFrame(self, fg_color="#2b2b2b")

        # Vista dettaglio
        self.client_detail_view = ClientDetailView(
            parent=self,
            back_callback=self.show_main_view,
            client_controller=self.client_controller,
            production_controller=production_controller,
            invoice_controller=invoice_controller,
            refund_controller=refund_controller,
            db_model=db_model,
            analyzer=self.analyzer,
            event_bus = self.event_bus,
            catalogo_elenchi=catalogo_elenchi
        )

        # Inizializza la vista principale
        self.create_client_tab()
        self.show_main_view()

    def create_client_tab(self):

        self.search_bar_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.search_bar_frame.pack(pady=30, fill="x", anchor="n")
        self.search_bar = ctk.CTkEntry(self.search_bar_frame)
        self.search_bar.pack(padx=(5,35), anchor="e", side="right")
        self.search_bar_label = ctk.CTkLabel(self.search_bar_frame, text="Filtra per nome:", font=("Arial", 14))
        self.search_bar_label.pack(padx=5, anchor="s", side="right")

        self.show_last_cards_optionMenu_values = {
            "30 GG": "30 GG",
            "60 GG": "60 GG",
            "90 GG": "90 GG",
            "365 GG": "365 GG"
        }
        self.show_last_cards_optionMenu = ctk.CTkOptionMenu(self.search_bar_frame,
                                                       values=list(self.show_last_cards_optionMenu_values.values()))
        self.show_last_cards_optionMenu.set("60 GG")
        self.show_last_cards_optionMenu.pack(padx=(5, 200), anchor="s", side="right")
        self.show_last_cards_label = ctk.CTkLabel(self.search_bar_frame, text="Mostra gli ultimi ", font=("Arial", 14))
        self.show_last_cards_label.pack(padx=5, anchor="s", side="right")

        self.show_last_cards_optionMenu.configure(command=lambda _: self.show_last_cards())


        # Aggiungi evento alla barra di ricerca
        self.search_bar.bind("<KeyRelease>", self.filter_cards)


        self.clients_table_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.clients_table_frame.pack(pady=(20, 0), padx=(10,15), fill="x", anchor="n")

        self.headers = ["NOME", "TOT. ENTRATE", "# FATTURE", "FATTURA MEDIA", "TOT. CREDITI", "TOT. RIMBORSI",
                   "PAGAMENTO \n ORARIO MEDIO", "TOT. GIORNI \n RITARDO", "MEDIA RITARDO"]

        for i, header in enumerate(self.headers):
            # crea il container
            column = ctk.CTkFrame(self.clients_table_frame, fg_color="#333333")
            column.grid(row=0, column=i, sticky="nsew", padx=(0, 5), pady=5)

            # imposta peso e uniformità: tutte le colonne "col" si dividono equamente
            self.clients_table_frame.grid_columnconfigure(i, weight=1, uniform="col")

            # la label riempie il suo container
            label = ctk.CTkLabel(column,
                                 text=header,
                                 font=("Arial", 14))
            label.pack(fill="both", expand=True, padx=5, pady=15)

        # Creazione del frame delle cards
        self.clients_cards_frame = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")
        self.clients_cards_frame.pack(padx=0, pady=10, fill="both", expand=True)

        self.add_client_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.add_client_frame.pack(padx=0, pady=(5, 20), fill="x")

        self.save_button = ctk.CTkButton(self.add_client_frame, text="Aggiungi Cliente", command=self.open_add_client_window)
        self.save_button.pack()

        self.show_last_cards()

    def show_last_cards(self):
        """Mostra solo i clienti con almeno una produzione negli ultimi giorni selezionati"""
        # Ottieni il valore selezionato dal menu
        selected = self.show_last_cards_optionMenu.get()

        # Mappa la selezione al numero di giorni
        days_map = {
            "30 GG": 30,
            "60 GG": 60,
            "90 GG": 90,
            "365 GG": 365
        }
        days = days_map.get(selected, 30)

        # Calcola la data limite (oggi - giorni)
        from datetime import datetime, timedelta
        limit_date = datetime.now() - timedelta(days=days)

        # Recupera tutti i clienti
        all_clients = self.client_controller.retrieve_clients_map_list()

        # Filtra i clienti: solo quelli con almeno una produzione >= limit_date
        filtered_clients = []
        for client in all_clients:
            client_id = client[DBClientsColumns.ID.value]

            # Recupera tutte le produzioni di questo cliente
            client_productions = self.production_controller.retrieve_productions_map_list_by_client_id(client_id, year=-1)

            # Verifica se almeno una produzione è nell'intervallo temporale
            has_recent_production = False
            for production in client_productions:
                date_str = production.get(DBProductionsColumns.CREATED_AT.value)
                if date_str:
                    try:
                        # Prova a parsare la data in formato yyyy-mm-dd o yyyy-mm-dd hh:mm:ss
                        try:
                            production_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            production_date = datetime.strptime(date_str, "%Y-%m-%d")

                        if production_date >= limit_date:
                            has_recent_production = True
                            break  # Basta una produzione recente
                    except Exception as e:
                        print(f"Errore nel parsare la data {date_str}: {e}")

            if has_recent_production:
                filtered_clients.append(client)

        # Svuota le cards attuali
        for card in self.clients_card_list.values():
            card.destroy()
        self.clients_card_list.clear()

        # Ricarica le cards con i clienti filtrati
        self.load_clients_chunked(filtered_clients)

    def show_main_view(self):
        """Torna alla vista principale"""
        self.client_detail_view.pack_forget()
        self.main_container.pack(fill='both', expand=True)

    def open_client_detail_tab(self, client_id):
        """Mostra la vista dettaglio utente"""
        self.main_container.pack_forget()
        self.client_detail_view.pack(fill='both', expand=True)
        self.client_detail_view.create_detail_tab(client_id)  # Ricrea i contenuti ogni volta

    def load_clients_chunked(self, clients_list):

        extractor = ViewUtils.create_extractor_for_clients(self.client_controller)

        ViewUtils.process_items_in_chunks(
            widget=self,
            items_list=clients_list,
            add_card_callback=self.add_client_card,
            extract_args_callback=extractor,
            cards_frame=self.clients_cards_frame
        )

    def add_client_card(self, client_id, nome, tot_entrate, num_fatture, fattura_media, tot_crediti, tot_rimborsi, pagam_orario, giorni_rit, media_rit):
        """
        Aggiunge una singola card con i dati forniti alla scrollable frame,
        disponendo i widget in colonne di ugual larghezza.
        """
        # Creazione della card
        card = ctk.CTkFrame(self.clients_cards_frame, fg_color="dimgray")
        card.pack(pady=10, padx=10, fill="x", expand=True)

        # Dati da visualizzare: bottone + 7 colonne di dati
        data = [
            nome,
            f"{tot_entrate:.2f}",
            num_fatture,
            f"{fattura_media:.2f}",
            f"{tot_crediti:.2f}",
            f"{tot_rimborsi:.2f}",
            f"{pagam_orario:.2f}",
            giorni_rit,
            f"{media_rit:.2f}"
        ]
        units = ["", "€", "", "€", "€", "€", "€/h", "gg", "gg"]

        n_cols = len(data)  # 8 colonne totali

        # Configura il grid della card: 1 riga, n_cols colonne uguali
        for c in range(n_cols):
            card.grid_columnconfigure(c, weight=1, uniform="clientcol")
        card.grid_rowconfigure(0, weight=1)

        # 0) Bottone "nome"
        btn = ctk.CTkButton(
            card,
            text=nome,
            command=lambda cid=client_id: self.open_client_detail_tab(cid)
        )
        btn.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        # 1..7) Le altre colonne
        for idx, val in enumerate(data[1:], start=1):
            text = f"{val} {units[idx]}"
            lbl = ctk.CTkLabel(card, text=text, font=("Arial", 14))
            lbl.grid(row=0, column=idx, sticky="nsew", padx=5, pady=10)

        # Salva la card per eventuale successivo accesso
        self.clients_card_list[nome] = card

    def filter_cards(self, event):
        """Filtra le card in base al testo della barra di ricerca."""
        search_text = self.search_bar.get().lower()

        # Cicla attraverso tutte le card dei clienti
        for nome, card in self.clients_card_list.items():
            # Se il nome del cliente contiene il testo della ricerca (ignorando maiuscole/minuscole)
            if search_text in nome.lower():
                # Rendi visibile la card
                card.pack(pady=10, padx=10, fill="x", expand=True)
            else:
                # Nascondi la card
                card.pack_forget()

    def open_add_client_window(self):
        """Apre una finestra per aggiungere un nuovo cliente"""

        self.add_client_window = ctk.CTkToplevel(self)
        self.add_client_window.title("Aggiungi Nuovo Cliente")

        # Assicurati che la finestra rimanga sopra
        self.add_client_window.lift()  # Porta la finestra sopra quella principale
        self.add_client_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

        self.add_client_window.geometry("400x700")

        self.client_window_scrollableFrame = ctk.CTkScrollableFrame(self.add_client_window)
        self.client_window_scrollableFrame.pack(fill="both", expand=True)

        # Campi per il form
        self.entry_fields = {
            DBClientsColumns.NAME.value: ctk.CTkEntry,
            DBClientsColumns.TIPOLOGIA.value: ctk.CTkOptionMenu,
            DBClientsColumns.PARTITA_IVA.value: ctk.CTkEntry,
            DBClientsColumns.EMAIL.value: ctk.CTkEntry,
            DBClientsColumns.SEDE_LEGALE.value: ctk.CTkEntry,
            DBClientsColumns.SETTORE.value: FilterableComboBox,
            DBClientsColumns.REFERENTE.value: ctk.CTkEntry,
            DBClientsColumns.CONTATTO_REFERENTE.value: ctk.CTkEntry,
            DBClientsColumns.NOTE.value: ctk.CTkTextbox,
        }

        self.error_fields = {
            DBClientsColumns.NAME.value: ctk.CTkLabel,
            DBClientsColumns.PARTITA_IVA.value: ctk.CTkLabel,
            DBClientsColumns.EMAIL.value: ctk.CTkLabel,
            DBClientsColumns.SEDE_LEGALE.value: ctk.CTkLabel,
            DBClientsColumns.SETTORE.value: ctk.CTkLabel
        }

        # Dizionario per conservare i riferimenti ai widget
        self.client_widgets = {}
        self.error_labels = {}

        # Creazione dei widget
        for i, (label_text, widget_class) in enumerate(self.entry_fields.items()):
            # Etichetta
            label = ctk.CTkLabel(self.client_window_scrollableFrame, text=label_text)
            if i == 0:
                label.pack(pady=5)
            else:
                label.pack(pady=(35, 0))

            # Widget
            if label_text == DBClientsColumns.TIPOLOGIA.value:
                widget = widget_class(self.client_window_scrollableFrame,
                                      values=[item.value for item in self.client_controller.TipologiaCliente])
                widget.set(self.client_controller.TipologiaCliente.PRIVATO.value)  # Imposta valore predefinito
            elif label_text == DBClientsColumns.SETTORE.value:
                widget = widget_class(parent=self.client_window_scrollableFrame, placeholder="Cerca", autofill=True,
                                      values=[value for key, value in self.catalogo_elenchi["clients_business_sectors"]],
                                      command = lambda selected_value : self.open_add_business_sector(selected_value))
                widget.set_value(self.client_controller.BusinessSector.CREATIVE_AGENCY.value)  # Imposta valore predefinito
            else:
                widget = widget_class(self.client_window_scrollableFrame)

            if widget_class == ctk.CTkTextbox:
                widget.pack(pady=5, padx=10, fill="x", expand=True)
            else:
                widget.pack(pady=5, padx=10, fill="x", expand=True)

            if self.error_fields.get(label_text) is not None:
                error_label = ctk.CTkLabel(self.client_window_scrollableFrame, text="")
                error_label.pack(pady=(0,15))
                self.error_labels[label_text] = error_label

            self.client_widgets[label_text] = widget


        # Bottone per salvare
        save_button = ctk.CTkButton(
            self.client_window_scrollableFrame,
            text="Salva Cliente",
            command=self.save_client_data
        )
        save_button.pack(pady=(35, 15))

        # Aggiungi validazione agli eventi di perdita del focus
        self.client_widgets[DBClientsColumns.NAME.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.client_widgets[DBClientsColumns.NAME.value],
            lambda val: val.strip() != "",
            self.error_labels[DBClientsColumns.NAME.value],
            "Il nome non può essere vuoto."
        ))

        """self.client_widgets[DBClientsColumns.PARTITA_IVA.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.client_widgets[DBClientsColumns.PARTITA_IVA.value],
            lambda val: val.isdigit() and ValidationUtils.validate_partita_iva(val),
            self.error_labels[DBClientsColumns.PARTITA_IVA.value],
            "La partita IVA deve essere un numero di 11 cifre."
        ))"""

        """self.client_widgets[DBClientsColumns.EMAIL.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.client_widgets[DBClientsColumns.EMAIL.value],
            lambda val: ValidationUtils.validate_email(val),
            self.error_labels[DBClientsColumns.EMAIL.value],
            "Inserisci una e-mail valida."
        ))"""

    def save_client_data(self):
        client_data = {}

        #controllo sul settore
        if self.client_widgets[DBClientsColumns.SETTORE.value].get_value() == dict(self.catalogo_elenchi["clients_business_sectors"]).get("ADD_SECTOR"):
            ViewUtils.show_error_popup(self.add_client_window, "SALVATAGGIO NON RIUSCITO", "Settore di business non valido")
            return

        # Riempi il dizionario con i dati dai widget
        for label_text, widget in self.client_widgets.items():
            if isinstance(widget, ctk.CTkEntry) or isinstance(widget, ctk.CTkOptionMenu):
                client_data[label_text] = widget.get().strip()  # Recupera il testo o il valore selezionato
            elif isinstance(widget, ctk.CTkTextbox):
                client_data[label_text] = widget.get("1.0", "end-1c").strip()  # Recupera il testo dal Textbox
            elif isinstance(widget, FilterableComboBox):
                client_data[label_text] = widget.get_value()

        print("Dati cliente:", client_data)

        client_id  = -1

        #chiamata al controller per salvare i dati
        success, message = self.client_controller.save_client(client_data)
        if success:
            client_id = self.client_controller.retrieve_client_by_name(client_data[DBClientsColumns.NAME.value])[0]
            print(f"Client {client_data[DBClientsColumns.NAME.value]} salvato con successo")
            self.add_client_card(
                client_id,
                client_data[DBClientsColumns.NAME.value],
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0
            )
            #self.clients_list.append(self.client_controller.retrieve_client_map_by_id(client_id))
            self.client_controller.print_clienti()

            self.add_client_window.destroy()
            self.show_last_cards()
        else:
            print(message)
            ViewUtils.show_error_popup(self.add_client_window, "ERRORE", message)

    def open_client_detail(self, client_id):
        self.client_details_window = ctk.CTkToplevel(self)
        client_db_info = self.client_controller.retrieve_client_map_by_id(client_id)
        self.client_details_window.title(f"Dettaglio del cliente: {client_db_info[DBClientsColumns.NAME.value]}")

        # Assicurati che la finestra rimanga sopra
        self.client_details_window.lift()  # Porta la finestra sopra quella principale
        self.client_details_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

        self.client_details_window.geometry("700x700")

    def open_add_business_sector(self, selected_value):
        sector_dict = dict(self.catalogo_elenchi["clients_business_sectors"])
        if selected_value == sector_dict.get("ADD_SECTOR"):

            self.add_sector_window = ctk.CTkToplevel(self)
            self.add_sector_window.title("Aggiungi un nuovo settore di business")

            # Assicurati che la finestra rimanga sopra
            self.add_sector_window.lift()  # Porta la finestra sopra quella principale
            self.add_sector_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

            self.add_sector_window.geometry("400x300")

            self.business_sector_window_Frame = ctk.CTkFrame(self.add_sector_window)
            self.business_sector_window_Frame.pack(fill="both", expand=True)

            ctk.CTkLabel(self.business_sector_window_Frame, text="Aggiungi un settore di business alla lista\nsepara parole diverse solo tramite spazio").pack(padx=10, pady=(25, 0))

            self.add_sector_entry = ctk.CTkEntry(self.business_sector_window_Frame)
            self.add_sector_entry.pack(padx=10, pady=5, fill="x", expand=True)

            ctk.CTkButton(self.business_sector_window_Frame, text="Aggiungi settore", command=self.save_business_sector).pack(padx=10, pady=(15, 10))


        else: return

    def save_business_sector(self):
        new_sector = self.add_sector_entry.get()
        new_sector_key = ControllerUtils.normalize_string_for_key(new_sector)
        try:
            self.config_manager.update_list_field("clients_business_sectors", new_sector_key, new_sector, "update")
        except Exception as e:
            ViewUtils.show_error_popup(self.add_sector_window, "Errore", f"Impossibile aggiungere il nuovo settore: {str(e)}")
            return

        self.client_widgets[DBClientsColumns.SETTORE.value].set_value(new_sector, safe_mode=False)
        self.add_sector_window.destroy()




class ClientDetailView(ctk.CTkFrame):
    def __init__(self, parent, back_callback, client_controller, production_controller, invoice_controller, refund_controller, db_model, analyzer, event_bus, catalogo_elenchi):
        super().__init__(parent)
        self.invoice_controller = invoice_controller
        self.refund_controller = refund_controller
        self.db_model = db_model
        self.back_callback = back_callback
        self.client_controller = client_controller
        self.production_controller = production_controller
        self.event_bus = event_bus
        self.current_client_id = None
        self.analyzer = analyzer
        self.catalogo_elenchi = catalogo_elenchi

        self.configure(fg_color="transparent")

        # Widgets persistenti (vanno creati una volta sola)
        self.head_frame = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.back_button = ctk.CTkButton(
            self.head_frame,
            text="Elenco Clienti",
            command=self._cleanup_and_go_back
        )
        self.title_label = ctk.CTkLabel(self.head_frame, font=("Arial", 22, "bold"))

        self.user_info_widgets: dict[str, ctk.CTkEntry | ctk.CTkOptionMenu] = {}

        self.nome_fattura_string = "FATTURA ASSOCIATA"
        self.nome_produzione_string = "PRODUZIONE ASSOCIATA"
        self.nome_rimborso_string = "RIMBORSO ASSOCIATO"


        # Container per i contenuti dinamici
        self.content_frame = ctk.CTkScrollableFrame(self)

        self.switch_modify = ctk.CTkSwitch(self.head_frame, text="Abilita la modifica", command=lambda: self.toggle_edit(self.content_frame))

        # Layout iniziale
        self._setup_base_layout()

        # Sistema per tracciare gli after()
        self._after_ids = set()
        self._orig_after = self.after
        self.after = self._track_after

    def _setup_base_layout(self):
        """Inizializza la struttura base del layout"""
        self.head_frame.pack(fill="x", pady=5, padx=5)
        self.back_button.pack(anchor="w", side="left", pady=10, padx=10)
        self.title_label.pack(anchor="c", side="left", fill="x", expand=True, pady=10)
        self.switch_modify.pack(anchor="e", side="left", pady=10, padx=10)
        self.content_frame.pack(fill="both", expand=True, pady=20, padx=20)

    def create_detail_tab(self, client_id):
        """Ricrea la vista dettaglio per un cliente specifico"""
        self.current_client_id = client_id

        # 1. Pulizia dei widget precedenti
        self._clear_content()

        # 2. Caricamento dati
        self.client = self.client_controller.retrieve_client_map_by_id(client_id)

        # 3. Aggiornamento elementi persistenti
        self.title_label.configure(
            text=f"{self.client[DBClientsColumns.NAME.value]}")

        # 4. Creazione contenuti dinamici
        self._create_client_info_section(self.client)
        self.toggle_edit(self.content_frame)

        self.wrapper_frame = ctk.CTkFrame(self.content_frame, fg_color="#333333")
        self.wrapper_frame.pack(padx=25, pady=(90, 0), fill="both", expand=True)
        #self.wrapper_frame2 = ctk.CTkFrame(self.content_frame, fg_color="#333333")
        #self.wrapper_frame2.pack(padx=25, pady=(90, 90), fill="both", expand=True)
        self._create_invoices_history()
        self._create_refunds_history()
        self._create_productions_history()

    def _create_client_info_section(self, client_data):
        # Dizionari per la configurazione
        self.entry_fields = {
            # Sezione Dati Anagrafici
            DBClientsColumns.NAME.value: {
                "type": ctk.CTkEntry,
                "label": "Nome Cliente",
                "section": "Dati Anagrafici"
            },
            DBClientsColumns.PARTITA_IVA.value: {
                "type": ctk.CTkEntry,
                "label": "Partita IVA",
                "section": "Dati Anagrafici"
            },
            DBClientsColumns.EMAIL.value: {
                "type": ctk.CTkEntry,
                "label": "Email",
                "section": "Dati Anagrafici"
            },
            DBClientsColumns.SEDE_LEGALE.value: {
                "type": ctk.CTkEntry,
                "label": "Sede Legale",
                "section": "Dati Anagrafici"
            },

            # Sezione Settore e Tipologia
            DBClientsColumns.SETTORE.value: {
                "type": ctk.CTkOptionMenu,
                "label": "Settore",
                "section": "Settore & Tipologia",
                "values": [item[1] for item in self.catalogo_elenchi["clients_business_sectors"]]
            },
            DBClientsColumns.TIPOLOGIA.value: {
                "type": ctk.CTkOptionMenu,
                "label": "Tipologia",
                "section": "Settore & Tipologia",
                "values": [item.value for item in self.client_controller.TipologiaCliente]
            },

            # Sezione Referente
            DBClientsColumns.REFERENTE.value: {
                "type": ctk.CTkEntry,
                "label": "Referente",
                "section": "Referente"
            },
            DBClientsColumns.CONTATTO_REFERENTE.value: {
                "type": ctk.CTkEntry,
                "label": "Contatto Referente",
                "section": "Referente"
            },

            # Sezione Note
            DBClientsColumns.NOTE.value: {
                "type": ctk.CTkTextbox,  # Usiamo Textbox per note più lunghe
                "label": "Note",
                "section": "Note",
                "height": 100
            }
        }

        # Regole di validazione
        validation_rules = {
            DBClientsColumns.NAME.value: (
                lambda val: val.strip() != "",
                "Il nome del cliente non può essere vuoto"
            ),
            DBClientsColumns.PARTITA_IVA.value: (
                lambda val: val == "" or (len(val) == 11 and val.isdigit()),
                "Partita IVA non valida (11 cifre)"
            ),
            DBClientsColumns.EMAIL.value: (
                lambda val: val == "" or re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", val),
                "Formato email non valido"
            )
        }

        # Inizializzazione strutture dati
        self.client_info_widgets = {}
        self.error_labels = {}
        sections = {}

        # Creazione frame principale
        self.info_frame = ctk.CTkFrame(self.content_frame, border_width=2, border_color="#2659ab")
        self.info_frame.pack(fill="both", expand=True, pady=10, padx=25)

        # Configurazione griglia
        self.info_frame.grid_columnconfigure(0, weight=1, uniform="col")
        self.info_frame.grid_columnconfigure(1, weight=1, uniform="col")

        # Creazione sezioni
        sections_order = [
            "Dati Anagrafici",
            "Settore & Tipologia",
            "Referente",
            "Note"
        ]

        # Crea i frame per ogni sezione
        for i, section_name in enumerate(sections_order):
            frame = ctk.CTkFrame(self.info_frame)
            column = 0 if i % 2 == 0 else 1
            row = i // 2
            frame.grid(row=row, column=column, sticky="nsew", padx=15, pady=15)
            frame.grid_columnconfigure(1, weight=1)
            sections[section_name] = {
                "frame": frame,
                "row": 0
            }

            # Titolo della sezione
            ctk.CTkLabel(frame, text=section_name, font=("Arial", 14, "bold")).grid(
                row=0, column=0, columnspan=2, sticky="w", padx=15, pady=5
            )
            sections[section_name]["row"] += 1

        # Popolamento delle sezioni
        for field, config in self.entry_fields.items():
            section = sections[config["section"]]
            frame = section["frame"]
            row = section["row"]

            # Creazione label
            lbl = ctk.CTkLabel(frame, text=config["label"] + ":")
            lbl.grid(row=row, column=0, sticky="w", padx=(15, 5), pady=(2, 5))

            # Creazione widget
            value = str(client_data.get(field, ""))

            if config["type"] == ctk.CTkOptionMenu:
                widget = config["type"](frame, values=config.get("values", []))

                # Converti il valore del DB nella descrizione corrispondente
                if field == DBClientsColumns.SETTORE.value:
                    # Trova la descrizione corrispondente al valore
                    current_value = next(
                        (desc for key, desc in self.catalogo_elenchi["clients_business_sectors"] if key == value),
                        value)
                    widget.set(current_value)
                else:
                    widget.set(value if value else config.get("values", [""])[0])

            elif config["type"] == ctk.CTkTextbox:
                widget = config["type"](frame, height=config.get("height", 50))
                widget.insert("1.0", value)
            else:
                widget = config["type"](frame)
                widget.insert(0, value)

            widget.grid(
                row=row,
                column=1,
                sticky="ew",
                padx=(5, 15),
                pady=(2, 5),
                rowspan=2 if config["type"] == ctk.CTkTextbox else 1
            )
            self.client_info_widgets[field] = widget

            # Gestione validazione
            if field in validation_rules:
                validation_func, error_message = validation_rules[field]

                error_lbl = ctk.CTkLabel(frame, text="", text_color="#e8e5dc")
                error_lbl.grid(
                    row=row + (2 if config["type"] == ctk.CTkTextbox else 1),
                    column=1,
                    sticky="w",
                    padx=5,
                    pady=(0, 10)
                )
                self.error_labels[field] = error_lbl

                if config["type"] != ctk.CTkTextbox:
                    widget.bind("<FocusOut>",
                                lambda e, w=widget, vl=validation_func, el=error_lbl, em=error_message:
                                ViewUtils.validate_entry(w, vl, el, em))
                else:
                    widget.bind("<FocusOut>",
                                lambda e, w=widget, vl=validation_func, el=error_lbl, em=error_message:
                                ViewUtils.validate_textbox(w, vl, el, em))

            # Aggiorna contatore righe
            section["row"] += 3 if config["type"] == ctk.CTkTextbox else 2

        buttons_frame = ctk.CTkFrame(self.info_frame, fg_color="#2b2b2b")
        buttons_frame.grid(row=2, column=0, columnspan=2, pady=(5, 15), padx=20, sticky="WE")

        # Bottone Salva
        self.save_info_btn = ctk.CTkButton(buttons_frame, text="Salva Cliente", command=self.save_client_mod)
        self.save_info_btn.pack(padx=(400, 10), pady=(20, 20), side="left")

        # Bottone Elimina
        self.delete_btn = ctk.CTkButton(buttons_frame, text="Elimina Cliente",
                                        fg_color="#8B0000", hover_color="#A52A2A",
                                        command=self.delete_client)
        self.delete_btn.pack(padx=10, pady=(20, 20), side="right", anchor="e")

    def save_client_mod(self):
        client_data = {
            DBClientsColumns.NAME.value: self.client_info_widgets[
                DBClientsColumns.NAME.value].get().strip(),
            DBClientsColumns.PARTITA_IVA.value: self.client_info_widgets[
                DBClientsColumns.PARTITA_IVA.value].get().strip(),
            DBClientsColumns.EMAIL.value: self.client_info_widgets[
                DBClientsColumns.EMAIL.value].get().strip(),
            DBClientsColumns.SEDE_LEGALE.value: self.client_info_widgets[
                DBClientsColumns.SEDE_LEGALE.value].get().strip(),
            DBClientsColumns.REFERENTE.value: self.client_info_widgets[
                DBClientsColumns.REFERENTE.value].get().strip(),
            DBClientsColumns.CONTATTO_REFERENTE.value: self.client_info_widgets[
                DBClientsColumns.CONTATTO_REFERENTE.value].get().strip(),
            DBClientsColumns.NOTE.value: self.client_info_widgets[
                DBClientsColumns.NOTE.value].get("1.0", "end-1c").strip(),
            DBClientsColumns.SETTORE.value: self.client_info_widgets[
                DBClientsColumns.SETTORE.value].get(),
            DBClientsColumns.TIPOLOGIA.value: self.client_info_widgets[
                DBClientsColumns.TIPOLOGIA.value].get()
        }

        # Chiamata al controller per salvare i dati
        success, message = self.client_controller.update_client(self.current_client_id, client_data)
        if success:
            print(
                f"Cliente {self.client_controller.retrieve_client_map_by_id(self.current_client_id)[DBClientsColumns.NAME.value]} salvato con successo")
            ViewUtils.show_confirm_popup_2(self.content_frame, "SALVATAGGIO COMPLETATO", message)
            self.switch_modify.deselect()
            self.toggle_edit(self.content_frame)

        else:
            # Mostra il messaggio d'errore
            print(message)
            ViewUtils.show_error_popup(self.content_frame, "ERRORE", message)

    def delete_client(self):
        confirmation = ViewUtils.ask_confirmation_popup(self.content_frame, "Stai per eliminare questo cliente.\nDesideri continuare ?", "ELIMINAZIONE CLIENTE" )
        if confirmation:
            #check if something link to this client
            invoices = self.invoice_controller.retrieve_invoice_map_list_by_client(self.current_client_id)
            productions = self.production_controller.retrieve_productions_map_list_by_client_id(self.current_client_id)
            refunds = self.refund_controller.retrieve_refunds_map_list_by_client_id(self.current_client_id)

            if len(invoices) == 0 and len(productions) == 0 and len(refunds) == 0 :
                success, message = self.client_controller.delete_client(self.current_client_id)
                if success:
                    print(message)
                    ViewUtils.show_confirm_popup_simple(self.content_frame, "CONFERMA ELIMINAZIONE", message)
                else:
                    # Mostra il messaggio d'errore
                    print(message)
                    ViewUtils.show_error_popup(self.content_frame, "ERRORE", message)
            else:
                ViewUtils.show_error_popup(self.info_frame, message="Impossibile eliminare il cliente.\n\n"
                                                                    "Esiste un item collegato a questo cliente.\n"
                                                                    "Eliminare ogni riferimento a questo cliente per poterlo eliminare dal database.")

    def toggle_edit(self, parent):
        """
        Abilita o disabilita la modifica dei widget nella finestra di modifica utente.
        """
        # Determina lo stato (abilitato/disabilitato) in base al valore dello switch
        state = ctk.NORMAL if self.switch_modify.get() else ctk.DISABLED

        # Cambia anche lo stato del pulsante Salva
        self.save_info_btn.configure(state=state)
        self.delete_btn.configure(state=state)

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

    def _create_invoices_history(self):
        """Crea la sezione storico fatture"""
        section_frame = ctk.CTkFrame(self.wrapper_frame, border_width=2, border_color="#2659ab")
        section_frame.pack(fill="both", side="left", expand=True, pady=0, padx=(0, 30))

        ctk.CTkLabel(section_frame, text="FATTURE", font=("Arial", 14, "bold")).pack(anchor="w", pady=(10, 10),
                                                                                            padx=10)

        global_infos = {
            "TOTALE FATTURATO": {
                "value": self.client_controller.calcola_tot_entrate_cliente(self.current_client_id),
                "uom": "€"
            }
        }

        self.global_infos_invoices_widgets = ViewUtils.construct_global_infos_cards(section_frame, global_infos)

        # tabella invoices
        invoices_frame = ctk.CTkScrollableFrame(section_frame, height=300)
        invoices_frame.pack(fill="both", expand=True, padx=(10, 20), pady=(10, 20))

        # popolo gli invoices
        invoices = self.client_controller.retrieve_client_with_invoices_map_list(self.current_client_id)
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

    def _create_refunds_history(self):
        """Crea la sezione storico rimborsi"""
        section_frame = ctk.CTkFrame(self.wrapper_frame, border_width=2, border_color="#2659ab")
        section_frame.pack(fill="both", side="left", expand=True, pady=0, padx=(0, 30))

        ctk.CTkLabel(section_frame, text="RIMBORSI", font=("Arial", 14, "bold")).pack(anchor="w", pady=(10, 10),
                                                                                        padx=10)

        global_infos = {
            "TOT RIMBORSI": {
                "value": self.refund_controller.calculate_tot_refunds_of_client(self.current_client_id),
                "uom": "€"
            }
        }

        self.global_infos_refunds_widgets = ViewUtils.construct_global_infos_cards(section_frame, global_infos)

        # tabella invoices
        refunds_frame = ctk.CTkScrollableFrame(section_frame, height=300)
        refunds_frame.pack(fill="both", expand=True, padx=(10, 20), pady=(10, 20))

        # popolo gli invoices
        refunds = self.refund_controller.retrieve_refunds_map_list_by_client_id(self.current_client_id)
        for ref in refunds:
            if ref[DBRefundsColumns.REFUND_NAME.value] is not None:
                nome_refund = ref[DBRefundsColumns.REFUND_NAME.value]
                id_refund = ref[DBRefundsColumns.ID.value]
                refund_button = ctk.CTkButton(refunds_frame,
                                                  text=f"{nome_refund}",
                                                  command=lambda id=id_refund: self.show_refund_detail(id))
                refund_button.pack(padx=10, pady=10, fill="x", expand=True)

    def show_refund_detail(self, refund_id):
        self.event_bus.publish(ViewUtils.EventBusKeys.SHOW_REFUND_DETAIL, refund_id)

    def _create_productions_history(self):
        """Crea la sezione storico fatture"""
        section_frame = ctk.CTkFrame(self.wrapper_frame, border_width=2, border_color="#2659ab")
        section_frame.pack(fill="both", side="left", expand=True, pady=0, padx=(0, 30))

        ctk.CTkLabel(section_frame, text="PRODUZIONI", font=("Arial", 14, "bold")).pack(anchor="w", pady=(10, 10),
                                                                                     padx=10)

        global_infos = {
            "# PRODUZIONI": {
                "value": self.production_controller.count_productions_of_client(self.current_client_id),
                "uom": ""
            }
        }

        self.global_infos_productions_widgets = ViewUtils.construct_global_infos_cards(section_frame, global_infos)

        # tabella invoices
        productions_frame = ctk.CTkScrollableFrame(section_frame, height=300)
        productions_frame.pack(fill="both", expand=True, padx=(10, 20), pady=(10, 20))

        # popolo gli invoices
        productions = self.production_controller.retrieve_productions_map_list_by_client_id(self.current_client_id)
        for production in productions:
            if production[DBProductionsColumns.NAME.value] is not None:
                nome_produzione = production[DBProductionsColumns.NAME.value]
                id_produzione = production[DBProductionsColumns.ID.value]
                produzione_button = ctk.CTkButton(productions_frame,
                                               text=f"{nome_produzione}",
                                               command=lambda id=id_produzione: self.show_production_detail(id))
                produzione_button.pack(padx=10, pady=10, fill="x", expand=True)

    def show_production_detail(self, production_id):
        self.event_bus.publish(ViewUtils.EventBusKeys.SHOW_PRODUCTION_DETAIL, production_id)

    def _clear_content(self):
        """Distrugge tutti i widget dinamici"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def _cleanup_and_go_back(self):
        """Pulizia completa prima di tornare indietro"""
        self._clear_content()
        self.pack_forget()
        self.back_callback()

    def cleanup(self):
        """Pulizia completa per liberare memoria - DA AGGIUNGERE IN OGNI VIEW"""
        try:
            print(f"Cleanup di {self.__class__.__name__}")

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
import customtkinter as ctk
import re
from Views.View_utils import ViewUtils, FilterableComboBox
from Controllers import ControllerUtils, ClientController, ProductionController, InvoiceController, RefundController, DatabaseModel, Analyzer
from Model import DBClientsColumns, DBInvoicesColumns, DBProductionsColumns, DBRefundsColumns
from datetime import datetime, timedelta
from Views.Details.Client_detail_view import ClientDetailView


from App_context import AppContext

class ClientsView(ctk.CTkFrame):
    def __init__(self, app_context:AppContext, tab):
        super().__init__(tab)


        self.app_context:AppContext = app_context
        self.db_model:DatabaseModel = app_context.db_model
        self.client_controller:ClientController = app_context.client_controller
        self.tab = tab
        self.catalogo_elenchi = app_context.catalogo_elenchi
        self.config_manager = app_context.config_manager
        self.production_controller:ProductionController = app_context.production_controller
        self.invoice_controller:InvoiceController = app_context.invoice_controller
        self.refund_controller:RefundController = app_context.refund_controller
        self.event_bus = app_context.event_bus
        self.analyzer:Analyzer = app_context.analyzer

        self.clients_card_list = {}

        # Container principale
        self.main_container = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.detail_container = ctk.CTkFrame(self, fg_color="#2b2b2b")

        # Vista dettaglio
        self.client_detail_view = ClientDetailView(
            parent=self,
            app_context = self.app_context,
            back_callback=self.show_main_view
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

            # Verifico se è stato appena inserito (quindi è normale che non abbia ancora produzioni attive)
            update_date = datetime.strptime(client.get(DBClientsColumns.UPDATED_AT.value), "%Y-%m-%d %H:%M:%S")
            just_insert = (datetime.now() - update_date).total_seconds() <= 432000 #5 giorni


            if has_recent_production or just_insert:
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

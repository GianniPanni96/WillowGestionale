import customtkinter as ctk
from Views.Details.Client_detail_view import ClientDetailView

from Views.BaseList_view import BaseListView
from Controllers import ClientController

from App_context import AppContext

from QueryServices.Clients_query_service import ClientQueryService
from Model import DBClientsColumns



class ClientsViewH(BaseListView):
    # --- CONFIGURAZIONE SPECIFICA (Passo 1: Definizione) ---
    TAB_NAME = "Clienti"
    CARDS_FRAME_NAME = 'clients_cards_frame'
    ADD_BUTTON_TEXT = "Aggiungi un cliente"

    # Configurazione Global Infos (Recuperate dal Controller)
    # NOTA: I nomi delle chiavi sono inventati per coerenza, ma nella fonte
    # sono impliciti tramite l'extractor [47, 48]. Qui si assumono valori aggregati.
    #GLOBAL_INFOS_CONFIG = {
    #    "TOT. ENTRATE": "TOT_ENTRATE",
    #    "# FATTURE": "NUM_FATTURE",
    #}
    #aggregate_UOM = {
    #    "TOT. ENTRATE": "€",
    #    "# FATTURE": ""
    #}

    # Configurazione Intestazioni (Headers) [23]
    HEADERS = ["NOME", "TOT. ENTRATE", "# FATTURE", "FATTURA MEDIA", "TOT. CREDITI",
               "TOT. RIMBORSI", "PAGAMENTO \n ORARIO MEDIO", "TOT. GIORNI \n RITARDO",
               "MEDIA RITARDO"]

    # Configurazione Filtri (per search_bar_optionMenu)
    SEARCH_BAR_OPTIONS = {"NOME CLIENTE": "NOME CLIENTE"}

    # Mappatura Filtri (per filter_cards) [49]
    FILTER_MAPPING = {
        "NOME CLIENTE": (0, ctk.CTkButton)
    }

    # Opzioni di Ordinamento
    SORT_CONFIG = {
        "NOME": {
            "label": "NOME",
            "access": "direct",
            "index": 0,
            "converter": "text"
        },
        "TOT. ENTRATE": {
            "label": "TOT. ENTRATE",
            "access": "direct",
            "index": 1,
            "converter": "currency"
        },
        "DATA CREAZIONE": {
            "label": "DATA CREAZIONE",
            "access": "database",
            "db_column": "created_at",
            "converter": "datetime"
        },
        "ULTIMA MODIFICA": {
            "label": "ULTIMA MODIFICA",
            "access": "database",
            "db_column": "updated_at",
            "converter": "datetime"
        }
    }

    # 5. Configurazione filtro temporale (come in Clients_view.txt [1])
    SHOW_LAST_CARDS_OPTIONS = {
        "30 GG": "30 GG",
        "60 GG": "60 GG",
        "90 GG": "90 GG",
        "365 GG": "365 GG"
    }

    VIRTUALIZATION_ENABLED = True
    INITIAL_POOL_SIZE = 25
    VIRTUALIZATION_BUFFER = 6

    def __init__(self, app_context:AppContext, tab):
        # Chiama l'__init__ della classe Base
        super().__init__(tab, db_retrieving_function=app_context.client_controller.retrieve_clients_map_dictionary)

        # Inizializzazione dei controller e del bus [4, 12]
        self.app_context:AppContext = app_context
        self.client_controller:ClientController = app_context.client_controller
        #self.analyzer:Analyzer = app_context.analyzer
        #self.production_controller:ProductionController = app_context.production_controller
        #self.invoice_controller:InvoiceController = app_context.invoice_controller
        #self.refund_controller:RefundController = app_context.refund_controller
        #self.catalogo_elenchi = app_context.catalogo_elenchi
        #self.config_manager:ConfigManager = app_context.config_manager
        #self.event_bus:EventBus = app_context.event_bus
        self.clients_card_list = self.cards_list  # mappa dinamica delle card visibili
        self.client_query_service: ClientQueryService = app_context.clients_query_service

        self.show_last_cards_optionMenu.set("60 GG")

        # Carica i dati iniziali (altrimenti la tab sarebbe vuota)
        self.show_last_cards() # Assumendo un metodo di caricamento

        self.client_detail_view = ClientDetailView(
            parent=self,
            app_context = self.app_context,
            back_callback=self.show_main_view
        )

    # --- Metodi Obbligatori Implementati (Passo 2: Logica) ---

    def populate_global_infos(self):
        """Logica di business per popolare i global infos del cliente (mock)"""
        # Nella classe reale, recupererebbe dati aggregati dal self.analyzer

        # Esempio: questa logica deve simulare il recupero di dati aggregati
        # self.global_infos["TOT. ENTRATE"] = self.analyzer.calculate_total_revenue()
        # self.global_infos["# FATTURE"] = self.analyzer.count_invoices()

        # Poiché non abbiamo la logica dell'analyzer, useremo un mock
        self.global_infos["TOT. ENTRATE"] = 12345.67
        self.global_infos["# FATTURE"] = 42

    def open_add_window(self):
        """Implementa l'apertura della finestra modale per aggiungere un cliente."""
        # Logica esistente in ClientsView.open_add_client_window [50]
        print("Apertura finestra modale Aggiungi Cliente...")
        # (Qui andrebbe il codice per CTkToplevel, entry_fields, error_fields, etc.)
        pass

    def load_items_chunked(self, items_list):
        """Compatibilità con la base: in questa view la virtualizzazione usa set_items."""
        self.set_items(items_list)

    def add_item_card(self, client_id, nome, tot_entrate, num_fatture, fattura_media, tot_crediti, tot_rimborsi,
                      pagam_orario, giorni_rit, media_rit):
        """Implementazione di add_client_card [49] (Ora è add_item_card)."""

        # Creazione della card (logica interna che prima era in add_client_card)
        card = ctk.CTkFrame(getattr(self, self.CARDS_FRAME_NAME), fg_color="dimgray")
        card.pack(pady=10, padx=5, fill="x", expand=True)

        # 9 colonne uniformi (definite in self.HEADERS)
        n_cols = len(self.HEADERS)
        for col in range(n_cols):
            card.grid_columnconfigure(col, weight=1, uniform="col")
            card.grid_rowconfigure(0, weight=1)

        data = [nome, tot_entrate, num_fatture, fattura_media, tot_crediti, tot_rimborsi, pagam_orario, giorni_rit,
                media_rit]

        # 0) Bottone con il nome del cliente (necessario per il filtraggio e l'apertura del dettaglio)
        btn = ctk.CTkButton(card, text=nome, command=lambda cid=client_id: self.open_client_detail_tab(cid))
        btn.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        # 1..8) Le altre colonne (Label)
        for idx, val in enumerate(data[1:], start=1):
            lbl = ctk.CTkLabel(card, text=f"{val}")
            lbl.grid(row=0, column=idx, sticky="nsew", padx=5, pady=10)

        self.cards_list[nome] = card

    def create_virtual_card_widget(self, parent):
        card = ctk.CTkFrame(parent, fg_color="dimgray")

        n_cols = len(self.HEADERS)
        for col in range(n_cols):
            card.grid_columnconfigure(col, weight=1, uniform="col")
            card.grid_rowconfigure(0, weight=1)

        name_button = ctk.CTkButton(card, text="", command=lambda: None)
        name_button.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        labels = []
        for idx in range(1, n_cols):
            lbl = ctk.CTkLabel(card, text="")
            lbl.grid(row=0, column=idx, sticky="nsew", padx=5, pady=10)
            labels.append(lbl)

        card._name_button = name_button
        card._value_labels = labels
        return card

    def bind_virtual_card_widget(self, card, item):
        client_id = item["client_id"]
        card._name_button.configure(
            text=item["nome"],
            command=lambda cid=client_id: self.open_client_detail_tab(cid)
        )

        values = [
            item["tot_entrate"],
            item["num_fatture"],
            item["fattura_media"],
            item["tot_crediti"],
            item["tot_rimborsi"],
            item["pagam_orario"],
            item["giorni_rit"],
            item["media_rit"],
        ]
        for lbl, value in zip(card._value_labels, values):
            lbl.configure(text=f"{value}")

    def get_item_key(self, item):
        return item["client_id"]

    def get_item_search_text(self, item, search_type):
        if search_type == "NOME CLIENTE":
            return item["nome"]
        return ""

    def get_item_sort_value(self, item, sort_cfg, temp_dictionary_of_maps):
        if sort_cfg["access"] == "direct":
            key_map = {
                0: "nome",
                1: "tot_entrate",
            }
            key = key_map.get(sort_cfg.get("index"))
            return item.get(key)

        if sort_cfg["access"] == "database":
            db_column = sort_cfg["db_column"]
            client_id = item["client_id"]
            return temp_dictionary_of_maps.get(str(client_id), {}).get(db_column)

        return None

    def open_client_detail_tab(self, client_id):
        """Metodo per la navigazione specifica (non è generico, ma usa la struttura Base)"""
        self.main_container.pack_forget()
        self.client_detail_view.pack(fill='both', expand=True)
        self.client_detail_view.create_detail_tab(client_id)

    def show_last_cards(self):
        """Implementazione della logica di filtraggio per i Clienti."""

        selected = self.show_last_cards_optionMenu.get()  # Ottiene il valore selezionato [5]

        days_map = {
            "30 GG": 30,
            "60 GG": 60,
            "90 GG": 90,
            "365 GG": 365
        }

        days = days_map.get(selected, 30)  # Mappa il valore ai giorni [6]

        filtered_clients = self.client_query_service.get_clients_for_days_window(days)
        cards_data = self._build_clients_cards_data(filtered_clients)

        self.set_items(cards_data)
        self.sort_cards()

    def _build_clients_cards_data(self, filtered_clients):
        cards_data = []
        for client in filtered_clients:
            client_id = client[DBClientsColumns.ID.value]
            nome = client[DBClientsColumns.NAME.value]
            aggregate_data = self.client_controller.construct_client_map_aggregate_data(client_id, year=-1)

            cards_data.append({
                "client_id": client_id,
                "nome": nome,
                "tot_entrate": round(aggregate_data[self.client_controller.Aggregate_data.TOT_ENTRATE.value], 2),
                "num_fatture": aggregate_data[self.client_controller.Aggregate_data.NUM_FATTURE.value],
                "fattura_media": round(aggregate_data[self.client_controller.Aggregate_data.MEDIA_FATTURE.value], 2),
                "tot_crediti": round(aggregate_data[self.client_controller.Aggregate_data.TOT_CREDITI.value], 2),
                "tot_rimborsi": round(self.client_controller.calcola_tot_rimborsi_by_client(client_id)),
                "pagam_orario": round(aggregate_data[self.client_controller.Aggregate_data.PAGAM_ORARIO_MEDIO.value], 2),
                "giorni_rit": aggregate_data[self.client_controller.Aggregate_data.TOT_GIORNI_RIT.value],
                "media_rit": round(aggregate_data[self.client_controller.Aggregate_data.MEDIA_RITARDO.value], 2),
            })

        return cards_data

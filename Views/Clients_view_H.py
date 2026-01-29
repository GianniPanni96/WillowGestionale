import customtkinter as ctk
from Views.Details.Client_detail_view import ClientDetailView

from Controllers import InvoiceController
from Views.BaseList_view import BaseListView
from Views.View_utils import ViewUtils
from Model import DBClientsColumns, DBProductionsColumns
from App_context import AppContext

from Controllers import ClientController, RefundController, Analyzer, ProductionController
from Model import DatabaseModel, DBUsersColumns, DBAccountsColumns, DBInvoicesColumns, DBExpensesColumns, DBProductionsColumns, \
    DBSalariesColumns
from Event_bus import EventBus
from Config import ConfigManager
from datetime import datetime, timedelta

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
            "converter": None
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

    def __init__(self, app_context:AppContext, tab):
        # Chiama l'__init__ della classe Base
        super().__init__(tab)

        # Inizializzazione dei controller e del bus [4, 12]
        self.app_context:AppContext = app_context
        self.client_controller:ClientController = app_context.client_controller
        self.db_model:DatabaseModel = app_context.db_model
        self.analyzer:Analyzer = app_context.analyzer
        self.production_controller:ProductionController = app_context.production_controller
        self.invoice_controller:InvoiceController = app_context.invoice_controller
        self.refund_controller:RefundController = app_context.refund_controller
        self.catalogo_elenchi = app_context.catalogo_elenchi
        self.config_manager:ConfigManager = app_context.config_manager
        self.event_bus:EventBus = app_context.event_bus
        self.clients_card_list = self.cards_list  # self.cards_list è l'attributo generico della BaseListView

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
        """Implementazione del caricamento a blocchi, usando l'extractor specifico."""
        # Logica esistente in ClientsView.load_clients_chunked [49, 51]
        extractor = ViewUtils.create_extractor_for_clients(self.client_controller)
        ViewUtils.process_items_in_chunks(
            widget=self,
            items_list=items_list,
            add_card_callback=self.add_item_card,  # Usa add_item_card come callback
            extract_args_callback=extractor,
            cards_frame=getattr(self, self.CARDS_FRAME_NAME)
        )

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

        limit_date = datetime.now() - timedelta(days=days)  # Calcola la data limite [6]

        all_clients = self.client_controller.retrieve_clients_map_list()

        filtered_clients = []
        for client in all_clients:
            client_id = client[DBClientsColumns.ID.value]
            client_productions = self.production_controller.retrieve_productions_map_list_by_client_id(client_id, year=-1)

            has_recent_production = False
            for production in client_productions:
                date_str = production.get(DBProductionsColumns.CREATED_AT.value)
                if date_str:
                    try:
                        try:
                            production_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            production_date = datetime.strptime(date_str, "%Y-%m-%d")

                        if production_date >= limit_date:
                            has_recent_production = True
                            break
                    except Exception as e:
                        print(f"Errore nel parsare la data {date_str}: {e}")

            if has_recent_production:
                filtered_clients.append(client)

        # Svuota e ricarica le cards
        for card in self.clients_card_list.values():
            card.destroy()
        self.clients_card_list.clear()

        self.load_items_chunked(filtered_clients)
        self.sort_cards() # Chiamata opzionale se l'ordinamento è desiderato dopo il filtro

import customtkinter as ctk
from Views.Details.Client_detail_view import ClientDetailView
from Views.Creators.Client_create_view import ClientCreateView

from Views.BaseList_view import BaseListView
from Views.View_utils import ViewUtils

from Controllerss.Client_controller import ClientController

from App_context import AppContext

from QueryServices.Clients_query_service import ClientQueryService
from Analyzers.Client_analyzer_service import ClientAnalyzerService


class ClientsViewH(BaseListView):
    """
    Implementazione concreta della lista Clienti basata su ``BaseListView``.

    La classe dichiara la configurazione statica della tab e collega la struttura
    generica della base ai servizi specifici del dominio clienti: query service,
    analyzer service, dettaglio cliente e creator view.
    """

    TAB_NAME = "Clienti"
    CARDS_FRAME_NAME = "clients_cards_frame"
    ADD_BUTTON_TEXT = "Aggiungi un cliente"

    #GLOBAL_INFOS_CONFIG = {
    #    "TOT. ENTRATE": "TOT_ENTRATE",
    #    "# FATTURE": "NUM_FATTURE",
    #}
    aggregate_UOM = {
        "TOT. ENTRATE": "€",
        "# FATTURE": ""
    }

    HEADERS = ["NOME", "TOT. ENTRATE", "# FATTURE", "FATTURA MEDIA", "TOT. CREDITI",
               "TOT. RIMBORSI", "PAGAMENTO \n ORARIO MEDIO", "TOT. GIORNI \n RITARDO",
               "MEDIA RITARDO"]

    SEARCH_BAR_OPTIONS = {"NOME CLIENTE": "NOME CLIENTE"}

    FILTER_MAPPING = {
        "NOME CLIENTE": (0, ctk.CTkButton)
    }

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

    SHOW_LAST_CARDS_OPTIONS = {
        "30 GG": "30 GG",
        "60 GG": "60 GG",
        "90 GG": "90 GG",
        "365 GG": "365 GG"
    }

    def __init__(self, app_context: AppContext, tab):
        """
        Inizializza la tab clienti e carica immediatamente le card iniziali.

        Args:
            app_context: contesto condiviso dell'applicazione.
            tab: contenitore grafico della tab.
        """
        super().__init__(tab, db_retrieving_function=app_context.clients_query_service.retrieve_clients_map_dictionary)

        self.app_context: AppContext = app_context
        self.client_controller: ClientController = app_context.client_controller
        self.clients_card_list = self.cards_list
        self.clients_query_service: ClientQueryService = app_context.clients_query_service
        self.clients_analyzer_service: ClientAnalyzerService = app_context.clients_analyzer_service

        self.initialize_view()

        self.show_last_cards_optionMenu.set("60 GG")
        self.client_create_view = None

        self.show_last_cards()

        self.client_detail_view = ClientDetailView(
            parent=self,
            app_context=self.app_context,
            back_callback=self.show_main_view
        )

    def populate_global_infos(self):
        """
        Popola le metriche aggregate mostrate nella barra superiore.

        Al momento il metodo usa valori placeholder. Quando la migrazione sara'
        completa, qui andranno agganciati i calcoli reali dell'analyzer.
        """
        return

    def open_add_window(self):
        """
        Apre la creator view del cliente assicurando una sola istanza attiva.

        Se la finestra e' gia' aperta, viene semplicemente riportata in primo piano.
        """
        if self.client_create_view is not None and self.client_create_view.winfo_exists():
            self.client_create_view.focus()
            self.client_create_view.lift()
            return

        self.client_create_view = ClientCreateView(
            parent=self,
            app_context=self.app_context,
            on_client_created=self._on_client_created,
            on_close=self._clear_client_create_view
        )

    def _on_client_created(self, client_id, client_data):
        """Aggiorna la lista dopo il salvataggio di un nuovo cliente."""
        self.show_last_cards()
        self.filter_cards(None)

    def _clear_client_create_view(self):
        """Pulisce il riferimento alla creator view quando la finestra viene chiusa."""
        self.client_create_view = None

    def load_items_chunked(self, items_list):
        """
        Delega a ``ViewUtils`` il rendering progressivo delle card cliente.

        L'approccio chunked evita di bloccare il thread UI quando la lista e'
        numerosa.
        """
        extractor = ViewUtils.create_extractor_for_clients(self.clients_analyzer_service)
        ViewUtils.process_items_in_chunks(
            widget=self,
            items_list=items_list,
            add_card_callback=self.add_item_card,
            extract_args_callback=extractor,
            cards_frame=getattr(self, self.CARDS_FRAME_NAME)
        )

    def add_item_card(self, client_id, nome, tot_entrate, num_fatture, fattura_media, tot_crediti, tot_rimborsi,
                      pagam_orario, giorni_rit, media_rit):
        """
        Crea e registra una card cliente nella lista scrollabile.

        La prima colonna e' un bottone per accedere al dettaglio, mentre le altre
        colonne mostrano gli aggregati gia' calcolati dall'analyzer service.
        """
        card = ctk.CTkFrame(getattr(self, self.CARDS_FRAME_NAME), fg_color="dimgray")
        card.pack(pady=10, padx=5, fill="x", expand=True)

        n_cols = len(self.HEADERS)
        for col in range(n_cols):
            card.grid_columnconfigure(col, weight=1, uniform="col")
            card.grid_rowconfigure(0, weight=1)

        data = [nome, tot_entrate, num_fatture, fattura_media, tot_crediti, tot_rimborsi, pagam_orario, giorni_rit,
                media_rit]

        btn = ctk.CTkButton(card, text=nome, command=lambda cid=client_id: self.open_client_detail_tab(cid))
        btn.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        for idx, val in enumerate(data[1:], start=1):
            lbl = ctk.CTkLabel(card, text=f"{val}")
            lbl.grid(row=0, column=idx, sticky="nsew", padx=5, pady=10)

        self.finalize_item_card(card, nome, btn)

    def open_client_detail_tab(self, client_id):
        """Nasconde la lista e mostra il dettaglio del cliente selezionato."""
        self.main_container.pack_forget()
        self.client_detail_view.pack(fill="both", expand=True)
        self.client_detail_view.create_detail_tab(client_id)

    def show_last_cards(self):
        """
        Filtra i clienti in base alla finestra temporale selezionata e ricarica la lista.

        Il criterio effettivo di inclusione e' delegato al ``ClientQueryService``.
        """
        selected = self.show_last_cards_optionMenu.get()

        days_map = {
            "30 GG": 30,
            "60 GG": 60,
            "90 GG": 90,
            "365 GG": 365
        }

        days = days_map.get(selected, 30)
        filtered_clients = self.clients_query_service.get_clients_for_days_window(days)

        self.reload_cards(filtered_clients)

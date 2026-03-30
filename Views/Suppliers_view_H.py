import customtkinter as ctk
from Views.Details.Supplier_detail_view import SupplierDetailView
from Views.Creators.Supplier_create_view import SupplierCreateView

from Views.BaseList_view import BaseListView
from Views.View_utils import ViewUtils

from Controllerss.Supplier_controller import SupplierController

from App_context import AppContext

from QueryServices.Suppliers_query_service import SupplierQueryService
from Analyzers.Supplier_analyzer_service import SupplierAnalyzerService


class SuppliersViewH(BaseListView):
    """
    Implementazione concreta della lista Fornitori basata su ``BaseListView``.

    La classe dichiara la configurazione statica della tab e collega la struttura
    generica della base ai servizi specifici del dominio fornitori: query service,
    analyzer service, dettaglio fornitore e creator view.
    """

    TAB_NAME = "Fornitori"
    CARDS_FRAME_NAME = "suppliers_cards_frame"
    ADD_BUTTON_TEXT = "Aggiungi un fornitore"

    ##GLOBAL_INFOS_CONFIG = {
    ##    "TOT. ENTRATE": "TOT_ENTRATE",
    ##    "# FATTURE": "NUM_FATTURE",
    ##}
    ##aggregate_UOM = {
    ##    "TOT. ENTRATE": "€",
    ##    "# FATTURE": ""
    ##}

    HEADERS = ["NOME", "PARTITA IVA", "TOT. SPESE", "# SPESE", "SPESA MEDIA",
               "NOTE", "CONTATTO"]

    SEARCH_BAR_OPTIONS = {"NOME FORNITORE": "NOME FORNITORE"}

    FILTER_MAPPING = {
        "NOME FORNITORE": (0, ctk.CTkButton)
    }

    SORT_CONFIG = {
        "NOME": {
            "label": "NOME",
            "access": "direct",
            "index": 0,
            "converter": "text"
        },
        "TOT. SPESE": {
            "label": "TOT. SPESE",
            "access": "direct",
            "index": 2,
            "converter": "currency"
        },
        "SPESA MEDIA": {
            "label": "SPESA MEDIA",
            "access": "direct",
            "index": 4,
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
        Inizializza la tab FORNITORI e carica immediatamente le card iniziali.

        Args:
            app_context: contesto condiviso dell'applicazione.
            tab: contenitore grafico della tab.
        """
        super().__init__(tab, db_retrieving_function=app_context.suppliers_query_service.retrieve_suppliers_map_dictionary)

        self.app_context: AppContext = app_context
        self.supplier_controller: SupplierController = app_context.supplier_controller
        self.suppliers_card_list = self.cards_list
        self.suppliers_query_service: SupplierQueryService = app_context.suppliers_query_service
        self.suppliers_analyzer_service: SupplierAnalyzerService = app_context.suppliers_analyzer_service

        self.initialize_view()

        self.show_last_cards_optionMenu.set("60 GG")
        self.supplier_create_view = None

        self.show_last_cards()

        self.supplier_detail_view = SupplierDetailView(
            parent=self,
            app_context=self.app_context,
            back_callback=self.show_main_view
        )

    def open_add_window(self):
        """
        Apre la creator view del fornitore assicurando una sola istanza attiva.

        Se la finestra e' gia' aperta, viene semplicemente riportata in primo piano.
        """
        if self.supplier_create_view is not None and self.supplier_create_view.winfo_exists():
            self.supplier_create_view.focus()
            self.supplier_create_view.lift()
            return

        self.supplier_create_view = SupplierCreateView(
            parent=self,
            app_context=self.app_context,
            on_supplier_created=self._on_supplier_created,
            on_close=self._clear_supplier_create_view
        )

    def populate_global_infos(self):
        """
        Popola le metriche aggregate mostrate nella barra superiore.
        """
        return

    def load_items_chunked(self, items_list):
        """
        Delega a ``ViewUtils`` il rendering progressivo delle card fornitore.

        L'approccio chunked evita di bloccare il thread UI quando la lista e'
        numerosa.
        """
        extractor = ViewUtils.create_extractor_for_suppliers(self.suppliers_analyzer_service)
        ViewUtils.process_items_in_chunks(
            widget=self,
            items_list=items_list,
            add_card_callback=self.add_item_card,
            extract_args_callback=extractor,
            cards_frame=getattr(self, self.CARDS_FRAME_NAME)
        )

    def _on_supplier_created(self, supplier_id, supplier_data):
        """Aggiorna la lista dopo il salvataggio di un nuovo fornitore."""
        self.show_last_cards()
        self.filter_cards(None)

    def _clear_supplier_create_view(self):
        """Pulisce il riferimento alla creator view quando la finestra viene chiusa."""
        self.supplier_create_view = None

    def add_item_card(self, supplier_id, supplier_name, partita_iva, num_spese, spesa_media, tot_spese, note, contatto):
        # Creazione della card
        card = ctk.CTkFrame(getattr(self, self.CARDS_FRAME_NAME), fg_color="dimgray")
        card.pack(pady=10, padx=10, fill="x", expand=True)  # Spaziatura tra le card

        # Dati da visualizzare nella card
        data = [supplier_name, partita_iva, f"{tot_spese:.2f}", num_spese, f"{spesa_media:.2f}", note, contatto]
        units = ["","", "€", "", "€", "", ""]
        n_cols = len(data)  # 8 colonne totali

        # Configura il grid della card: 1 riga, n_cols colonne uguali
        for c in range(n_cols):
            card.grid_columnconfigure(c, weight=1, uniform="clientcol")
        card.grid_rowconfigure(0, weight=1)

        # 0) Bottone "nome"
        btn = ctk.CTkButton(
            card,
            text=supplier_name,
            command=lambda sid=supplier_id: self.open_supplier_detail_tab(sid)
        )
        btn.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        # 1..7) Le altre colonne
        for idx, val in enumerate(data[1:], start=1):
            text = f"{val} {units[idx]}"
            lbl = ctk.CTkLabel(card, text=text, font=("Arial", 14))
            lbl.grid(row=0, column=idx, sticky="nsew", padx=5, pady=10)

        # Salva la card per eventuale successivo accesso
        self.finalize_item_card(card, supplier_name, btn)

    def open_supplier_detail_tab(self, supplier_id):
        """Nasconde la lista e mostra il dettaglio del cliente selezionato."""
        self.main_container.pack_forget()
        self.supplier_detail_view.pack(fill="both", expand=True)
        self.supplier_detail_view.create_detail_tab(supplier_id)

    def show_last_cards(self):
        """
        Filtra i fornitori in base alla finestra temporale selezionata e ricarica la lista.

        Il criterio effettivo di inclusione è delegato al ``SupplierQueryService``.
        """
        selected = self.show_last_cards_optionMenu.get()

        days_map = {
            "30 GG": 30,
            "60 GG": 60,
            "90 GG": 90,
            "365 GG": 365
        }

        days = days_map.get(selected, 30)
        filtered_suppliers = self.suppliers_query_service.get_suppliers_for_days_window(days)

        self.reload_cards(filtered_suppliers)

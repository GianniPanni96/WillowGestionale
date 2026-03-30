from datetime import datetime, timedelta

import customtkinter as ctk

from Views.View_utils import ViewUtils
from Views.BaseList_view import BaseListView
from App_context import AppContext
from Views.Creators.Production_create_view import ProductionCreateView

from QueryServices.Productions_query_service import ProductionQueryService
from QueryServices.Clients_query_service import ClientQueryService
from Analyzers.Production_analyzer_service import ProductionAnalyzerService
from Gestionale_Enums import DBProductionsColumns, ProductionStatus
from WarningServices.Production_warning_service import ProductionWarningService

from Views.Details.Production_detail_view import ProductionDetailView



class ProductionsViewH(BaseListView):
    """
    Implementazione concreta della lista Produzioni basata su ``BaseListView``.

    La classe dichiara la configurazione statica della tab e collega la struttura
    generica della base ai servizi specifici del dominio produzioni: query service,
    analyzer service, dettaglio produzione e creator view.
    """

    TAB_NAME = "Produzioni"
    CARDS_FRAME_NAME = "productions_cards_frame"
    ADD_BUTTON_TEXT = "Aggiungi una produzione"

    GLOBAL_INFOS_CONFIG = {
        "# PRODUZIONI\nATTIVE": "TOT_ATTIVE",
        "# PRODUZIONI\nCHIUSE": "TOT_CHIUSE",
        "MEDIA ORE PER\nPRODUZIONE": "ORE_PROD",
        "MEDIA PERZZO PER\nORA DI PRODUZIONE": "PREZZO_ORA",
    }
    aggregate_UOM = {
        "# PRODUZIONI\nATTIVE": "",
        "# PRODUZIONI\nCHIUSE": "",
        "MEDIA ORE PER\nPRODUZIONE": "h",
        "MEDIA PERZZO PER\nORA DI PRODUZIONE": "€/h",
    }

    HEADERS = ["NOME", "CLIENTE", "TIPOLOGIA \nDI PRODUZIONE", "TIPOLOGIA \nDI OUTPUT", "STATO",
               "DATA \nDI CONSEGNA", "TOTALE \nPREVENTIVO", "DURATA \nPRODUZIONE",
               "PREZZO \nORARIO"]

    SEARCH_BAR_OPTIONS = {
        "NOME PRODUZIONE": "NOME PRODUZIONE",
        "NOME CLIENTE": "NOME CLIENTE",
        "TIPO PRODUZIONE": "TIPO PRODUZIONE",
        "TIPO OUTPUT": "TIPO OUTPUT",
        "STATO": "STATO"
    }

    FILTER_MAPPING = {
        "NOME PRODUZIONE": (0, ctk.CTkButton),
        "NOME CLIENTE": (1, ctk.CTkLabel),
        "TIPO PRODUZIONE": (2, ctk.CTkLabel),
        "TIPO OUTPUT": (3, ctk.CTkLabel),
        "STATO": (4, ctk.CTkOptionMenu)
    }

    SORT_CONFIG = {
        "NOME": {
            "label": "NOME",
            "access": "direct",
            "index": 0,
            "converter": "text"
        },
        "TOTALE PREVENTIVO": {
            "label": "TOTALE \nPREVENTIVO",
            "access": "direct",
            "index": 6,
            "converter": "currency"
        },
        "DURATA PRODUZIONE": {
            "label": "DURATA \nPRODUZIONE",
            "access": "direct",
            "index": 7,
            "converter": "currency"
        },
        "PREZZO ORARIO": {
            "label": "PREZZO \nORARIO",
            "access": "direct",
            "index": 8,
            "converter": "currency"
        },
        "DATA DI CONSEGNA": {
            "label": "DATA \nDI CONSEGNA",
            "access": "direct",
            "index": 5,
            "converter": "date"
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

    def __init__(self, app_context: AppContext, tab, initial_production_id=None):
        """
        Inizializza la tab produzioni e carica immediatamente le card iniziali.

        Args:
            app_context: contesto condiviso dell'applicazione.
            tab: contenitore grafico della tab.
        """
        super().__init__(tab, db_retrieving_function=app_context.productions_query_service.retrieve_productions_map_dictionary)

        self.app_context: AppContext = app_context
        self.clients_query_service: ClientQueryService = app_context.clients_query_service
        self.productions_card_list = self.cards_list
        self.productions_query_service: ProductionQueryService = app_context.productions_query_service
        self.productions_analyzer_service: ProductionAnalyzerService = app_context.productions_analyzer_service
        self.production_warning_service: ProductionWarningService = app_context.production_warning_service

        self.show_last_cards_optionMenu.set("60 GG")
        self.production_create_view = None

        self.show_last_cards()

        self.production_detail_view = ProductionDetailView(
            parent=self,
            app_context=self.app_context,
            back_callback=self.show_main_view
        )

        if initial_production_id is not None:
            self.after(100, lambda: self.open_production_detail_tab(initial_production_id))
        else:
            self.show_main_view()

    def populate_global_infos(self):
        """
        Popola le metriche aggregate mostrate nella barra superiore.

        Al momento il metodo usa valori placeholder. Quando la migrazione sara'
        completa, qui andranno agganciati i calcoli reali dell'analyzer.
        """
        self.global_infos["TOT. ENTRATE"] = 12345.67
        self.global_infos["# FATTURE"] = 42

    def open_add_window(self):
        """
        Apre la creator view della produzione assicurando una sola istanza attiva.

        Se la finestra è gia' aperta, viene semplicemente riportata in primo piano.
        """
        if self.production_create_view is not None and self.production_create_view.winfo_exists():
            self.production_create_view.focus()
            self.production_create_view.lift()
            return

        self.production_create_view = ProductionCreateView(
            parent=self,
            app_context=self.app_context,
            on_production_created=self._on_production_created,
            on_close=self._clear_production_create_view
        )

    def _on_production_created(self, production_id, production_data):
        """Aggiorna la lista dopo il salvataggio di un nuova produzione."""
        self.show_last_cards()
        self.filter_cards(None)

    def _clear_production_create_view(self):
        """Pulisce il riferimento alla creator view quando la finestra viene chiusa."""
        self.production_create_view = None

    def load_items_chunked(self, items_list):
        """
        Delega a ``ViewUtils`` il rendering progressivo delle card produzione.

        L'approccio chunked evita di bloccare il thread UI quando la lista è
        numerosa.
        """
        extractor = ViewUtils.create_extractor_for_productions(self.productions_analyzer_service, self.clients_query_service)
        ViewUtils.process_items_in_chunks(
            widget=self,
            items_list=items_list,
            add_card_callback=self.add_item_card,
            extract_args_callback=extractor,
            cards_frame=getattr(self, self.CARDS_FRAME_NAME)
        )

    def collect_card_warnings(self, items_list):
        """Delega al warning service la costruzione dei warning lista produzione."""
        return self.production_warning_service.collect_warnings_for_list(items_list)

    def add_item_card(self, production_id, production_name, client_name,
                      tipologia_produzione, tipologia_output, produzione_stato,
                      data_di_consegna, totale_preventivo, durata_produzione,
                      prezzo_orario):
        """
        Crea e registra una card produzione nella lista scrollabile.

        La prima colonna è un bottone per accedere al dettaglio, mentre le altre
        colonne mostrano gli aggregati gia' calcolati dall'analyzer service.
        """
        card = ctk.CTkFrame(getattr(self, self.CARDS_FRAME_NAME), fg_color="dimgray")
        card.pack(pady=10, padx=8, fill="x", expand=True)

        data = [
            client_name,
            tipologia_produzione,
            tipologia_output,
            produzione_stato,
            ViewUtils.invert_data_string(data_di_consegna),
            round(totale_preventivo, 2),
            durata_produzione,
            round(prezzo_orario, 2),
        ]
        units = ["", "", "", "", "", "EUR", "h", "EUR/h"]

        n_cols = 1 + len(data)
        for col in range(n_cols):
            card.grid_columnconfigure(col, weight=1, uniform="prodcol")
        card.grid_rowconfigure(0, weight=1)

        btn = ctk.CTkButton(
            card,
            text=production_name,
            command=lambda pid=production_id: self.open_production_detail_tab(pid)
        )
        btn.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        for idx, value in enumerate(data, start=1):
            if idx == 4:
                status_menu = ctk.CTkOptionMenu(
                    card,
                    values=[status.value for status in ProductionStatus]
                )
                status_menu.set(produzione_stato)
                status_menu.grid(row=0, column=idx, sticky="nsew", padx=5, pady=10)
            else:
                text = f"{value} {units[idx - 1]}".strip()
                label = ctk.CTkLabel(card, text=text, font=("Arial", 14))
                label.grid(row=0, column=idx, sticky="nsew", padx=5, pady=10)

        self.finalize_item_card(card, production_name, btn)

    def open_production_detail_tab(self, production_id):
        """Nasconde la lista e mostra il dettaglio della produzione selezionata."""
        self.main_container.pack_forget()
        self.production_detail_view.pack(fill="both", expand=True)
        self.production_detail_view.create_detail_tab(production_id)

    def show_last_cards(self):
        """
        Filtra le produzioni in base alla finestra temporale selezionata e ricarica la lista.

        Il criterio di inclusione replica ``ProductionsView``: usa ``created_at``
        della produzione e mantiene solo gli elementi compresi nella finestra.
        """
        selected = self.show_last_cards_optionMenu.get()

        days_map = {
            "30 GG": 30,
            "60 GG": 60,
            "90 GG": 90,
            "365 GG": 365
        }
        days = days_map.get(selected, 30)
        limit_date = datetime.now() - timedelta(days=days)

        all_productions = self.productions_query_service.retrieve_productions_map_list(
            include_prod_with_unpaid_invoices=True
        )

        filtered_productions = []
        for production in all_productions:
            date_str = production.get(DBProductionsColumns.CREATED_AT.value)
            if not date_str:
                continue

            production_date = None
            for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    production_date = datetime.strptime(date_str, pattern)
                    break
                except ValueError:
                    continue

            if production_date is not None and production_date >= limit_date:
                filtered_productions.append(production)

        self.reload_cards(filtered_productions)



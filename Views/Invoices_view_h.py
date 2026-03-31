import customtkinter as ctk
from enum import Enum

from App_context import AppContext
from Model import DatabaseModel
from Views.BaseList_view import BaseListView
from QueryServices.Clients_query_service import ClientQueryService
from QueryServices.Productions_query_service import ProductionQueryService

class InvoicesViewH(BaseListView):
    """
    Implementazione concreta della lista Fatture basata su ``BaseListView``.

    La classe dichiara la configurazione statica della tab e collega la struttura
    generica della base ai servizi specifici del dominio clienti: query service,
    analyzer service, dettaglio fattura e creator view.
    """
    class InvoicesStatusColors(Enum):
        CRITICAL = "#f52f2f"
        WARNING = "#e39e27"
        NORMAL = ctk.ThemeManager.theme["CTkLabel"]["text_color"]
        GOOD = "#2ca31c"
        STORNATA = "#2444d4"
        NOT_EXISTING = "#424242"

    TAB_NAME = "Fatture"
    CARDS_FRAME_NAME = "invoices_cards_frame"
    ADD_BUTTON_TEXT = "Aggiungi una fattura"

    #GLOBAL_INFOS_CONFIG = {
    #    "TOT. ENTRATE": "TOT_ENTRATE",
    #    "# FATTURE": "NUM_FATTURE",
    #}
    aggregate_UOM = {
        "# FATTURE": "",
        "FATTURATO": "€",
        "CREDITI": "€",
        "MEDIA FATTURE": "€",
    }

    HEADERS = ["NOME", "CLIENTE", "UTENTE", "PRODUZIONE\nASSOCIATA", "DATA\nEMISSIONE",
               "STATO", "RATE", "NETTO A\nPAGARE", "TIPOLOGIA"]

    SEARCH_BAR_OPTIONS = {
        "NOME FATTURA": "NOME FATTURA",
        "NOME CLIENTE": "NOME CLIENTE",
        "NOME UTENTE": "NOME UTENTE",
        "NOME PRODUZIONE": "NOME PRODUZIONE"
        }

    FILTER_MAPPING = {
        "NOME FATTURA": (0, ctk.CTkButton),
        "NOME CLIENTE": (1, ctk.CTkLabel),
        "NOME UTENTE": (2, ctk.CTkLabel),
        "NOME PRODUZIONE": (3, ctk.CTkLabel)
    }

    SORT_CONFIG = {
        "NOME": {
            "label": "NOME",
            "access": "direct",
            "index": 0,
            "converter": "text"
        },
        "NETTO A PAGARE": {
            "label": "NETTO A\nPAGARE",
            "access": "direct",
            "index": 7,
            "converter": "currency"
        },
        "DATA EMISSIONE": {
            "label": "DATA EMISSIONE",
            "access": "direct",
            "index": 4,
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

    def __init__(self, app_context: AppContext, tab):
        """
        Inizializza la tab fatture e carica immediatamente le card iniziali.

        Args:
            app_context: contesto condiviso dell'applicazione.
            tab: contenitore grafico della tab.
        """
        super().__init__(tab, db_retrieving_function=app_context.invoices_query_service.retrieve_invoices_map_dictionary)

        self.app_context: AppContext = app_context
        self.invoice_controller: InvoiceController = app_context.client_controller
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
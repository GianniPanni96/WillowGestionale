import customtkinter as ctk



# --- Classe Base ---
class BaseListView(ctk.CTkFrame):
    # Questi attributi DEVONO essere definiti nelle classi figlie (Concrete View)
    # per configurare l'interfaccia in modo specifico.

    # 1. Configurazione delle informazioni aggregate (Global Infos)
    # Esempio: {"# FATTURE": {"value_key": "NUMERO_FATTURE", "uom": ""}, ...}
    GLOBAL_INFOS_CONFIG = {}

    # 2. Configurazione delle intestazioni della tabella (Card Headers)
    HEADERS = []

    # 3. Configurazione dei filtri di ricerca (Search Bar Options)
    # Esempio: {"NOME FATTURA": "NOME_FATTURA", ...}
    SEARCH_BAR_OPTIONS = {}

    # 4. Mappatura dei filtri per l'estrazione dalla card (per filter_cards)
    # Esempio: {"NOME FATTURA": (0, ctk.CTkButton), ...} [32-35]
    FILTER_MAPPING = {}

    SHOW_LAST_CARDS_OPTIONS = {}

    # 5. Nome del frame contenitore delle cards (per il cleanup)
    CARDS_FRAME_NAME = None  # Esempio: 'invoices_cards_frame' [36]

    # 6. Testo del bottone di aggiunta
    ADD_BUTTON_TEXT = "Aggiungi un elemento"

    # 7. Nome della tab (usato nel cleanup)
    TAB_NAME = "ELEMENTO"

    def __init__(self, tab_frame, **kwargs):
        super().__init__(tab_frame)
        self.tab = tab_frame

        # Dizionari dinamici comuni
        self.global_infos = {}
        self.amount_aggregate_labels = {}
        self.cards_list = {}  # Mappa delle card attive (es. self.invoices_card_list)

        # Variabili di stato
        self.order_bar_option_menu_values_types = {"DECRESCENTE": "DECRESCENTE", "CRESCENTE": "CRESCENTE"}

        # Containers principali (comuni a tutte le views)
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.detail_container = ctk.CTkFrame(self, fg_color="transparent")

        # Metodi di inizializzazione (chiamati dalla classe figlia)
        self.create_main_tab_ui()
        self.show_main_view()

    def create_main_tab_ui(self):
        """Crea la struttura UI principale (barra di ricerca, intestazioni, frame cards)"""
        self.main_container.pack(fill='both', expand=True)

        # 1. Crea la barra di ricerca e filtri
        self._create_search_and_filter_bar()

        # 2. Popola le Global Infos (se configurate)
        if self.GLOBAL_INFOS_CONFIG:
            self.populate_global_infos()  # La logica di popolamento deve essere definita nelle classi figlie
            self._display_global_infos_cards()

        # 3. Crea le intestazioni della tabella (se configurate)
        if self.HEADERS:
            self._create_table_headers()

        # 4. Crea il Frame delle Cards (Scrollable)
        self._create_cards_scrollable_frame()

        # 5. Crea il bottone di aggiunta
        self._create_add_button()

    def _create_search_and_filter_bar(self):
        """Crea la barra di ricerca, il menu di filtro e il menu di ordinamento."""
        self.search_bar_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.search_bar_frame.pack(pady=(25, 10), fill="x", anchor="s")

        # Filtra per testo
        self.search_bar = ctk.CTkEntry(self.search_bar_frame)
        self.search_bar.pack(padx=(5, 35), anchor="s", side="right")
        self.search_bar.bind("<KeyRelease>", self.filter_cards)

        # Menu per scegliere il tipo di filtro (es. "NOME FATTURA", "NOME CLIENTE")
        self.search_bar_optionMenu = ctk.CTkOptionMenu(self.search_bar_frame,
                                                       values=list(self.SEARCH_BAR_OPTIONS.values()))
        self.search_bar_optionMenu.pack(padx=5, anchor="s", side="right")
        self.search_bar_optionMenu.configure(command=lambda _: self.filter_cards(None))

        self.search_bar_label = ctk.CTkLabel(self.search_bar_frame, text="Filtra per ", font=("Arial", 14))
        self.search_bar_label.pack(padx=5, anchor="s", side="right")

        # Menu per ordinamento (tipologia: crescente/decrescente)
        self.order_bar_optionMenu_types = ctk.CTkOptionMenu(self.search_bar_frame,
                                                            values=list(
                                                                self.order_bar_option_menu_values_types.values()),
                                                            command=lambda _: self.sort_cards())
        self.order_bar_optionMenu_types.pack(padx=(5, 100), anchor="s", side="right")

        # Menu per ordinamento (campo)
        # N.B.: Le opzioni di ordinamento devono essere definite nella classe figlia tramite self.ORDER_OPTIONS
        if hasattr(self, 'ORDER_OPTIONS'):
            self.order_bar_optionMenu = ctk.CTkOptionMenu(self.search_bar_frame,
                                                          values=list(self.ORDER_OPTIONS.values()),
                                                          command=lambda _: self.sort_cards())
            self.order_bar_optionMenu.pack(padx=5, anchor="s", side="right")
            self.order_bar_label = ctk.CTkLabel(self.search_bar_frame, text="Ordina per ", font=("Arial", 14))
            self.order_bar_label.pack(padx=5, anchor="s", side="right")

        # Aggiunta: Filtro per periodo di tempo (Mostra gli ultimi...)
        if self.SHOW_LAST_CARDS_OPTIONS:
            self.show_last_cards_optionMenu = ctk.CTkOptionMenu(
                self.search_bar_frame,
                values=list(self.SHOW_LAST_CARDS_OPTIONS.keys())  # Usa le chiavi come etichette
            )

                # Posizionamento del widget (si assume un layout da destra a sinistra)
            self.show_last_cards_optionMenu.pack(padx=(5, 50), anchor="s", side="right")

            self.show_last_cards_label = ctk.CTkLabel(self.search_bar_frame, text="Mostra gli ultimi ",
                                                      font=("Arial", 14))
            self.show_last_cards_label.pack(padx=5, anchor="s", side="right")

            # Collega il comando al metodo astratto della classe base
            self.show_last_cards_optionMenu.configure(command=lambda _: self.show_last_cards())

    def _display_global_infos_cards(self):
        """Visualizza le card aggregate, usando la logica in ViewUtils."""
        # Nota: La logica di ViewUtils.construct_global_infos_cards [37, 38] è riutilizzata
        # Questa parte assumerà che `self.global_infos` sia stato popolato dalle classi figlie.
        # Poiché il frame di Cards viene creato qui, non serve re-implementare la sua logica complessa.

        if not self.global_infos:
            return

        # Utilizza l'implementazione ViewUtils per costruire le cards
        # La fonte mostra che le cards di Global Infos sono spesso collocate nel search_bar_frame [17, 39, 40]

        for (key, info) in self.global_infos.items():
            card = ctk.CTkFrame(self.search_bar_frame, fg_color="#333333")

            # Determina l'unità di misura (UOM) in base a una chiave o a una mappa specifica
            # L'UOM è fornita dalla classe figlia tramite self.aggregate_UOM (se esiste) [19, 21, 22]
            global_info_unità_di_misura = getattr(self, 'aggregate_UOM', {}).get(key, "")

            # ... (Logica di configurazione della card, semplificata per la base)

            title = ctk.CTkLabel(card, text=f"{key}", font=("Arial", 12))
            amount = ctk.CTkLabel(card, text=f"{info} {global_info_unità_di_misura}", font=("Arial", 16))

            title.pack(anchor="n", padx=10, pady=(10, 5))
            amount.pack(anchor="s", padx=10, pady=5)

            card.pack(side="left", anchor="w", padx=10, pady=(10, 5))
            self.amount_aggregate_labels[f"{key}"] = amount

    def _create_table_headers(self):
        """Crea le intestazioni delle card come una griglia uniforme."""

        self.table_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.table_frame.pack(pady=(20, 0), padx=(10, 15), fill="x", anchor="n")

        for i, header in enumerate(self.HEADERS):
            column = ctk.CTkFrame(self.table_frame, fg_color="#333333")
            column.grid(row=0, column=i, sticky="nsew", padx=(0, 5), pady=5)

            # Configurazione peso uniforme (necessario per allineare le card) [26, 29, 41]
            self.table_frame.grid_columnconfigure(i, weight=1, uniform="col")

            label = ctk.CTkLabel(column, text=header, font=("Arial", 14))
            label.pack(fill="both", expand=True, padx=5, pady=15)

    def _create_cards_scrollable_frame(self):
        """Crea il frame scrollable dove andranno inserite le card."""
        # Usa il nome dinamico per creare l'attributo richiesto per il cleanup [42-44]
        if self.CARDS_FRAME_NAME:
            cards_frame = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")
            cards_frame.pack(padx=0, pady=10, fill="both", expand=True)
            setattr(self, self.CARDS_FRAME_NAME, cards_frame)  # Assegna il frame all'attributo corretto

    def _create_add_button(self):
        """Crea il frame e il bottone di aggiunta."""
        self.add_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.add_frame.pack(padx=0, pady=(5, 20), fill="x")

        self.save_button = ctk.CTkButton(self.add_frame, text=self.ADD_BUTTON_TEXT,
                                         command=self.open_add_window)  # Metodo da definire nella figlia
        self.save_button.pack()

    # --- Metodi che DEVONO essere implementati dalle classi figlie ---

    def show_main_view(self):
        """Mostra la vista principale. Da chiamare dalla classe figlia."""
        self.detail_container.pack_forget()
        self.main_container.pack(fill='both', expand=True)

    def populate_global_infos(self):
        """Logica per popolare self.global_infos prima della visualizzazione."""
        # Esempio: self.global_infos["# FATTURE"] = self.invoice_controller.current_year_invoices_aggregated_data["NUMERO_FATTURE"]
        raise NotImplementedError(
            "La logica di popolamento delle info globali deve essere implementata nella classe figlia.")

    def open_add_window(self):
        """Logica per aprire la finestra modale di aggiunta."""
        raise NotImplementedError(
            "La logica di apertura della finestra di aggiunta deve essere implementata nella classe figlia.")

    def load_items_chunked(self, items_list):
        """Logica per caricare le card (spesso tramite ViewUtils.process_items_in_chunks)."""
        raise NotImplementedError("La logica di caricamento delle card deve essere implementata nella classe figlia.")

    def add_item_card(self, *args, **kwargs):
        """Logica specifica per disegnare una singola card con i suoi widget."""
        raise NotImplementedError(
            "La logica di disegno di una singola card deve essere implementata nella classe figlia.")

    def sort_cards(self):
        """Logica di ordinamento (varia a seconda dei dati/controller)."""
        pass  # Può essere opzionale o lasciata vuota se si utilizza solo il filtro predefinito

    def show_last_cards(self):
        """
        Logica per filtrare gli item per data (ultimi N giorni).
        DEVE ESSERE IMPLEMENTATA NELLA CLASSE FIGLIA.
        """
        # Questo metodo implementa il comportamento visibile in ClientsView.show_last_cards [5]
        raise NotImplementedError("La logica di filtraggio temporale 'show_last_cards' deve essere implementata nella classe figlia.")

        # --- Implementazione del Filtraggio (Meccanismo Comune) ---

    def filter_cards(self, event):
        """Filtra le card in base al testo e al tipo di filtro configurato."""
        search_text = self.search_bar.get().lower()
        search_type = self.search_bar_optionMenu.get()

        mapping = self.FILTER_MAPPING.get(search_type)

        # 1. Rimuovi tutte le card esistenti
        for card in self.cards_list.values():
            card.pack_forget()  # Rimuove dalla visualizzazione [33, 45]

        # 2. Se il mapping è nullo o la ricerca è vuota, mostra tutto nell'ordine originale
        if mapping is None or not search_text:
            for card in self.cards_list.values():
                card.pack(pady=10, padx=10, fill="x", expand=True)
            return

        idx, expected_class = mapping

        # 3. Itera e riposiziona solo quelle che corrispondono
        for key, card in self.cards_list.items():
            children = card.winfo_children()
            widget_text = ""

            if len(children) > idx and isinstance(children[idx], expected_class):
                # Gestione speciale per OptionMenu (es. STATO in Produzioni [46])
                widget = children[idx]
                if isinstance(widget, ctk.CTkOptionMenu):
                    widget_text = widget.get()
                else:
                    widget_text = widget.cget("text")

                if search_text in widget_text.lower():
                    card.pack(pady=10, padx=10, fill="x", expand=True)
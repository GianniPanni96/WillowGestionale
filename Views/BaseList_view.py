import customtkinter as ctk
from datetime import datetime



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

    SORT_CONFIG = {}

    SHOW_LAST_CARDS_OPTIONS = {}

    # 5. Nome del frame contenitore delle cards (per il cleanup)
    CARDS_FRAME_NAME = None  # Esempio: 'invoices_cards_frame' [36]

    # 6. Testo del bottone di aggiunta
    ADD_BUTTON_TEXT = "Aggiungi un elemento"

    # 7. Nome della tab (usato nel cleanup)
    TAB_NAME = "ELEMENTO"

    # Virtualizzazione lista/cards
    VIRTUALIZATION_ENABLED = False
    INITIAL_POOL_SIZE = 25
    VIRTUALIZATION_BUFFER = 4
    CARD_VERTICAL_SPACING = 20

    def __init__(self, tab_frame, db_retrieving_function = None, **kwargs):
        super().__init__(tab_frame)
        self.tab = tab_frame

        # Dizionari dinamici comuni
        self.global_infos = {}
        self.amount_aggregate_labels = {}
        self.cards_list = {}  # Mappa delle card attive (es. self.invoices_card_list)
        self._items_dataset = []
        self._filtered_dataset = []
        self._virtual_pool = []
        self._virtual_index_for_slot = {}
        self._slot_for_virtual_index = {}
        self._estimated_card_height = 90
        self._virtual_layout_job = None
        self._last_first_visible = -1
        self._virtual_data_epoch = 0
        self._last_render_epoch = -1

        # Variabili di stato
        self.order_bar_option_menu_values_types = {"DECRESCENTE": "DECRESCENTE", "CRESCENTE": "CRESCENTE"}

        # Containers principali (comuni a tutte le views)
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.detail_container = ctk.CTkFrame(self, fg_color="transparent")

        self.db_retrieving_function = db_retrieving_function

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
        # N.B.: Le opzioni di ordinamento devono essere definite nella classe figlia tramite self.SORT_CONFIG
        if hasattr(self, 'SORT_CONFIG'):
            self.order_bar_optionMenu = ctk.CTkOptionMenu(
                self.search_bar_frame,
                values=[cfg["label"] for cfg in self.SORT_CONFIG.values()],
                command=lambda _: self.sort_cards()
            )
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

            if self.VIRTUALIZATION_ENABLED:
                self._top_spacer = ctk.CTkFrame(cards_frame, fg_color="transparent", height=0)
                self._top_spacer.pack(fill="x")
                self._top_spacer.pack_propagate(False)

                self._pool_container = ctk.CTkFrame(cards_frame, fg_color="transparent")
                self._pool_container.pack(fill="x", expand=True)

                self._bottom_spacer = ctk.CTkFrame(cards_frame, fg_color="transparent", height=0)
                self._bottom_spacer.pack(fill="x")
                self._bottom_spacer.pack_propagate(False)

                self._bind_virtual_scroll_events(cards_frame)

    def _bind_virtual_scroll_events(self, cards_frame):
        cards_frame.bind("<Configure>", lambda _e: self._schedule_virtual_layout_update())

        canvas = getattr(cards_frame, "_parent_canvas", None)
        if canvas is not None:
            canvas.bind("<Configure>", lambda _e: (self._sync_virtual_width(), self._schedule_virtual_layout_update()))
            canvas.bind_all("<MouseWheel>", lambda _e: self._schedule_virtual_layout_update())
            canvas.bind_all("<Button-4>", lambda _e: self._schedule_virtual_layout_update())
            canvas.bind_all("<Button-5>", lambda _e: self._schedule_virtual_layout_update())

    def _sync_virtual_width(self):
        if not self.VIRTUALIZATION_ENABLED:
            return

        cards_frame = getattr(self, self.CARDS_FRAME_NAME, None)
        canvas = getattr(cards_frame, "_parent_canvas", None) if cards_frame else None
        if canvas is None:
            return

        target_width = max(1, canvas.winfo_width())

        if hasattr(cards_frame, "_create_window_id"):
            canvas.itemconfigure(cards_frame._create_window_id, width=target_width)

        if hasattr(self, "_pool_container"):
            self._pool_container.configure(width=target_width)

    def _schedule_virtual_layout_update(self):
        if not self.VIRTUALIZATION_ENABLED:
            return

        if self._virtual_layout_job is not None:
            self.after_cancel(self._virtual_layout_job)

        self._virtual_layout_job = self.after(16, self._refresh_virtualized_window)

    def _ensure_virtual_pool(self):
        if not self.VIRTUALIZATION_ENABLED:
            return

        target_pool_size = max(1, self.INITIAL_POOL_SIZE)
        while len(self._virtual_pool) < target_pool_size:
            card = self.create_virtual_card_widget(self._pool_container)
            self._virtual_pool.append(card)

    def _get_viewport_height(self):
        cards_frame = getattr(self, self.CARDS_FRAME_NAME, None)
        canvas = getattr(cards_frame, "_parent_canvas", None) if cards_frame else None
        if canvas is None:
            return 1

        height = canvas.winfo_height()
        return height if height > 1 else 1

    def _get_scroll_fraction(self):
        cards_frame = getattr(self, self.CARDS_FRAME_NAME, None)
        canvas = getattr(cards_frame, "_parent_canvas", None) if cards_frame else None
        if canvas is None:
            return 0.0

        yview = canvas.yview()
        return yview[0] if yview else 0.0

    def _refresh_virtualized_window(self):
        self._virtual_layout_job = None
        if not self.VIRTUALIZATION_ENABLED:
            return

        total_items = len(self._filtered_dataset)
        if total_items == 0:
            for card in self._virtual_pool:
                card.pack_forget()
            self._top_spacer.configure(height=0)
            self._bottom_spacer.configure(height=0)
            self.cards_list.clear()
            return

        self._ensure_virtual_pool()
        viewport_height = self._get_viewport_height()
        row_height = max(1, self._estimated_card_height + self.CARD_VERTICAL_SPACING)
        total_virtual_height = max(1, total_items * row_height)
        scroll_fraction = self._get_scroll_fraction()
        first_visible = int((scroll_fraction * total_virtual_height) / row_height)
        first_visible = max(0, min(first_visible, max(0, total_items - 1)))

        visible_count = max(1, int(viewport_height / row_height) + self.VIRTUALIZATION_BUFFER)
        max_pool_window = min(len(self._virtual_pool), total_items)
        visible_count = min(max_pool_window, visible_count)

        start_index = max(0, first_visible - self.VIRTUALIZATION_BUFFER // 2)
        max_start = max(0, total_items - visible_count)
        start_index = min(start_index, max_start)
        end_index = min(total_items, start_index + visible_count)

        if (
            start_index == self._last_first_visible
            and self.cards_list
            and self._last_render_epoch == self._virtual_data_epoch
        ):
            return

        self._last_first_visible = start_index
        self.cards_list.clear()
        self._slot_for_virtual_index.clear()

        top_height = start_index * row_height
        bottom_height = max(0, (total_items - end_index) * row_height)
        self._top_spacer.configure(height=top_height)
        self._bottom_spacer.configure(height=bottom_height)

        self._sync_virtual_width()

        for card in self._virtual_pool:
            card.pack_forget()

        for slot_idx, item_index in enumerate(range(start_index, end_index)):
            card = self._virtual_pool[slot_idx]
            item = self._filtered_dataset[item_index]
            self.bind_virtual_card_widget(card, item)
            card.pack(pady=10, padx=0, fill="x")

            key = self.get_item_key(item)
            self.cards_list[key] = card
            self._virtual_index_for_slot[slot_idx] = item_index
            self._slot_for_virtual_index[item_index] = slot_idx

            if slot_idx == 0:
                card.update_idletasks()
                self._estimated_card_height = max(1, card.winfo_height())

        self._last_render_epoch = self._virtual_data_epoch

        cards_frame = getattr(self, self.CARDS_FRAME_NAME, None)
        canvas = getattr(cards_frame, "_parent_canvas", None) if cards_frame else None
        if canvas is not None:
            canvas.configure(scrollregion=canvas.bbox("all"))

    def set_items(self, items_list):
        self._items_dataset = list(items_list or [])
        self._filtered_dataset = list(self._items_dataset)

        self._virtual_data_epoch += 1
        self._last_first_visible = -1

        if self.VIRTUALIZATION_ENABLED:
            self._ensure_virtual_pool()
            self._refresh_virtualized_window()
            return

        self.load_items_chunked(self._filtered_dataset)

    def _create_add_button(self):
        """Crea il frame e il bottone di aggiunta."""
        self.add_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.add_frame.pack(padx=0, pady=(5, 20), fill="x")

        self.save_button = ctk.CTkButton(self.add_frame, text=self.ADD_BUTTON_TEXT,
                                         command=self.open_add_window)  # Metodo da definire nella figlia
        self.save_button.pack()

    # Funzioni di supporto per la conversione dei valori
    def _convert_to_date(self, date_str):
        """Converte una stringa in formato dd-mm-yyyy in un oggetto date per l'ordinamento."""
        from datetime import datetime
        try:
            return datetime.strptime(date_str.strip(), "%d-%m-%Y")
        except (ValueError, TypeError):
            return None

    def _convert_to_currency(self, currency_str):
        """Converte una stringa di valuta in un numero float per l'ordinamento."""
        if not currency_str or not currency_str.strip():
            return None

        try:
            # Rimuovi il simbolo dell'euro e gli spazi
            cleaned = currency_str.strip().replace('€', '').replace(' ', '')

            # Gestione dei numeri negativi
            negative = False
            if cleaned.startswith('-'):
                negative = True
                cleaned = cleaned[1:]

            # Gestione di formati con separatori delle migliaia e decimali
            # Cerca l'ultimo separatore (potrebbe essere punto o virgola per i decimali)
            last_comma = cleaned.rfind(',')
            last_dot = cleaned.rfind('.')

            # Determina il separatore decimale (l'ultimo punto o virgola)
            if last_comma > last_dot:
                # Virgola come separatore decimale, punti come separatori delle migliaia
                cleaned = cleaned.replace('.', '').replace(',', '.')
            elif last_dot > last_comma:
                # Punto come separatore decimale, virgole come separatori delle migliaia
                cleaned = cleaned.replace(',', '').replace('.', '.')
            else:
                # Nessun separatore decimale, rimuovi tutti i separatori
                cleaned = cleaned.replace(',', '').replace('.', '')

            # Converti in float e gestisci il segno
            result = float(cleaned) * (-1 if negative else 1)
            return result

        except (ValueError, TypeError):
            return None

    def _convert_to_datetime(self, datetime_str):
        """Converte una stringa in formato yyyy-mm-dd hh:mm:ss in un oggetto datetime per l'ordinamento."""
        try:
            return datetime.strptime(datetime_str.strip(), "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return None

    def _convert_to_lowercase(self, text_str):
        if not text_str or not text_str.strip():
            return None

        return text_str.lower()

    def _get_converter(self, name):
        return {
            "text": self._convert_to_lowercase,
            "currency": self._convert_to_currency,
            "datetime": self._convert_to_datetime,
            "date": self._convert_to_date
        }.get(name)

    def sort_cards(self):
        if not hasattr(self, "SORT_CONFIG"):
            return

        selected_label = self.order_bar_optionMenu.get()
        sort_order = self.order_bar_optionMenu_types.get()
        reverse = (sort_order == "DECRESCENTE")

        # trova la config selezionata
        sort_cfg = next(
            (cfg for cfg in self.SORT_CONFIG.values() if cfg["label"] == selected_label),
            None
        )
        if not sort_cfg:
            return

        temp_dictionary_of_maps = None
        if sort_cfg.get("access") == "database" and self.db_retrieving_function:
            temp_dictionary_of_maps = self.db_retrieving_function(keyIsName=False)

        converter = self._get_converter(sort_cfg.get("converter"))

        if self.VIRTUALIZATION_ENABLED:
            sortable_items = [
                (item, self._get_item_sort_value(item, sort_cfg, converter, temp_dictionary_of_maps))
                for item in self._filtered_dataset
            ]
            sortable_items.sort(key=lambda x: (x[1] is None, x[1]), reverse=reverse)
            self._filtered_dataset = [item for item, _ in sortable_items]
            self._virtual_data_epoch += 1
            self._last_first_visible = -1
            self._refresh_virtualized_window()
            return

        cards_with_values = []
        for key, card in self.cards_list.items():
            value = self.get_legacy_card_sort_value(key, card, sort_cfg, temp_dictionary_of_maps)
            converted = converter(value) if converter and value else value
            cards_with_values.append((card, converted))

        cards_with_values.sort(key=lambda x: (x[1] is None, x[1]), reverse=reverse)
        for card, _ in cards_with_values:
            card.pack_forget()
        for card, _ in cards_with_values:
            card.pack(pady=10, padx=10, fill="x", expand=True)

    def _get_item_sort_value(self, item, sort_cfg, converter, temp_dictionary_of_maps):
        value = self.get_item_sort_value(item, sort_cfg, temp_dictionary_of_maps)
        return converter(value) if converter and value else value

    def get_legacy_card_sort_value(self, key, card, sort_cfg, temp_dictionary_of_maps):
        children = card.winfo_children()
        value = None

        if sort_cfg["access"] == "direct":
            idx = sort_cfg["index"]
            if len(children) > idx:
                value = children[idx].cget("text")
        elif sort_cfg["access"] == "database":
            db_column = sort_cfg["db_column"]
            value = temp_dictionary_of_maps[key][db_column]

        return value

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

    def create_virtual_card_widget(self, parent):
        raise NotImplementedError("Creare una card riciclabile nella classe figlia.")

    def bind_virtual_card_widget(self, card, item):
        raise NotImplementedError("Associare i dati alla card riciclata nella classe figlia.")

    def get_item_key(self, item):
        raise NotImplementedError("Restituire una chiave univoca item->card nella classe figlia.")

    def get_item_search_text(self, item, search_type):
        raise NotImplementedError("Restituire il testo usato per il filtro nella classe figlia.")

    def get_item_sort_value(self, item, sort_cfg, temp_dictionary_of_maps):
        raise NotImplementedError("Restituire il valore usato per l'ordinamento nella classe figlia.")

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

        if self.VIRTUALIZATION_ENABLED:
            if mapping is None or not search_text:
                self._filtered_dataset = list(self._items_dataset)
            else:
                self._filtered_dataset = [
                    item for item in self._items_dataset
                    if search_text in str(self.get_item_search_text(item, search_type)).lower()
                ]
            self._virtual_data_epoch += 1
            self._last_first_visible = -1
            self._refresh_virtualized_window()
            return

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

import customtkinter as ctk
from datetime import datetime
from Views.View_utils import ViewUtils


class BaseListView(ctk.CTkFrame):
    """
    Classe base per le view lista dell'applicazione.

    La classe fornisce la struttura comune della schermata:
    - barra ricerca e ordinamento;
    - eventuali card aggregate;
    - intestazioni tabellari;
    - area scrollabile con le card;
    - bottone di aggiunta.

    Le classi figlie devono dichiarare la configurazione statica del dominio e
    implementare i metodi astratti con la logica specifica.
    """

    GLOBAL_INFOS_CONFIG = {}
    HEADERS = []
    SEARCH_BAR_OPTIONS = {}
    FILTER_MAPPING = {}
    SORT_CONFIG = {}
    SHOW_LAST_CARDS_OPTIONS = {}
    CARDS_FRAME_NAME = None
    ADD_BUTTON_TEXT = "Aggiungi un elemento"
    TAB_NAME = "ELEMENTO"

    def __init__(self, tab_frame, db_retrieving_function=None, **kwargs):
        """
        Inizializza la view base e costruisce la UI principale.

        Args:
            tab_frame: contenitore Tk della tab corrente.
            db_retrieving_function: funzione richiamata per recuperare le mappe
                usate dalla logica di ordinamento.
        """
        super().__init__(tab_frame)
        self.tab = tab_frame

        self.global_infos = {}
        self.amount_aggregate_labels = {}
        self.cards_list = {}
        self.cards_warnings = {}

        self.order_bar_option_menu_values_types = {"DECRESCENTE": "DECRESCENTE", "CRESCENTE": "CRESCENTE"}

        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.detail_container = ctk.CTkFrame(self, fg_color="transparent")

        self.db_retrieving_function = db_retrieving_function

        self.create_main_tab_ui()
        self.show_main_view()

    def create_main_tab_ui(self):
        """
        Costruisce l'intera UI comune della lista.

        L'ordine di costruzione e' intenzionale: prima i controlli in alto,
        poi le metriche aggregate, poi intestazioni, lista e bottone finale.
        """
        self.main_container.pack(fill="both", expand=True)

        self._create_search_and_filter_bar()

        if self.GLOBAL_INFOS_CONFIG:
            self.populate_global_infos()
            self._display_global_infos_cards()

        if self.HEADERS:
            self._create_table_headers()

        self._create_cards_scrollable_frame()
        self._create_add_button()

    def _create_search_and_filter_bar(self):
        """Crea i controlli di ricerca, filtro, ordinamento e finestra temporale."""
        self.search_bar_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.search_bar_frame.pack(pady=(25, 10), fill="x", anchor="s")

        self.search_bar = ctk.CTkEntry(self.search_bar_frame)
        self.search_bar.pack(padx=(5, 35), anchor="s", side="right")
        self.search_bar.bind("<KeyRelease>", self.filter_cards)

        self.search_bar_optionMenu = ctk.CTkOptionMenu(
            self.search_bar_frame,
            values=list(self.SEARCH_BAR_OPTIONS.values())
        )
        self.search_bar_optionMenu.pack(padx=5, anchor="s", side="right")
        self.search_bar_optionMenu.configure(command=lambda _: self.filter_cards(None))

        self.search_bar_label = ctk.CTkLabel(self.search_bar_frame, text="Filtra per ", font=("Arial", 14))
        self.search_bar_label.pack(padx=5, anchor="s", side="right")

        self.order_bar_optionMenu_types = ctk.CTkOptionMenu(
            self.search_bar_frame,
            values=list(self.order_bar_option_menu_values_types.values()),
            command=lambda _: self.sort_cards()
        )
        self.order_bar_optionMenu_types.pack(padx=(5, 100), anchor="s", side="right")

        if hasattr(self, "SORT_CONFIG"):
            self.order_bar_optionMenu = ctk.CTkOptionMenu(
                self.search_bar_frame,
                values=[cfg["label"] for cfg in self.SORT_CONFIG.values()],
                command=lambda _: self.sort_cards()
            )
            self.order_bar_optionMenu.pack(padx=5, anchor="s", side="right")
            self.order_bar_label = ctk.CTkLabel(self.search_bar_frame, text="Ordina per ", font=("Arial", 14))
            self.order_bar_label.pack(padx=5, anchor="s", side="right")

        if self.SHOW_LAST_CARDS_OPTIONS:
            self.show_last_cards_optionMenu = ctk.CTkOptionMenu(
                self.search_bar_frame,
                values=list(self.SHOW_LAST_CARDS_OPTIONS.keys())
            )
            self.show_last_cards_optionMenu.pack(padx=(5, 50), anchor="s", side="right")

            self.show_last_cards_label = ctk.CTkLabel(
                self.search_bar_frame,
                text="Mostra gli ultimi ",
                font=("Arial", 14)
            )
            self.show_last_cards_label.pack(padx=5, anchor="s", side="right")

            self.show_last_cards_optionMenu.configure(command=lambda _: self.show_last_cards())

    def _display_global_infos_cards(self):
        """
        Disegna le card aggregate sopra la lista.

        Il contenuto numerico deve essere gia' stato popolato dalla classe figlia
        dentro ``self.global_infos`` prima dell'invocazione di questo metodo.
        """
        if not self.global_infos:
            return

        for key, info in self.global_infos.items():
            card = ctk.CTkFrame(self.search_bar_frame, fg_color="#333333")

            global_info_unita_di_misura = getattr(self, "aggregate_UOM", {}).get(key, "")

            title = ctk.CTkLabel(
                card,
                text=f"{key}",
                font=("Arial", 12),
                bg_color="#1F6AA5"
            )
            amount = ctk.CTkLabel(card, text=f"{info} {global_info_unita_di_misura}", font=("Arial", 16))

            title.pack(anchor="n", padx=10, pady=(10, 5), ipadx=5)
            amount.pack(anchor="s", padx=10, pady=5)

            card.pack(side="left", anchor="w", padx=10, pady=(5, 5))
            self.amount_aggregate_labels[f"{key}"] = amount

    def _create_table_headers(self):
        """Crea le intestazioni della tabella allineate con le card sottostanti."""
        self.table_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.table_frame.pack(pady=(20, 0), padx=(10, 15), fill="x", anchor="n")

        for i, header in enumerate(self.HEADERS):
            column = ctk.CTkFrame(self.table_frame, fg_color="#333333")
            column.grid(row=0, column=i, sticky="nsew", padx=(0, 5), pady=5)

            self.table_frame.grid_columnconfigure(i, weight=1, uniform="col")

            label = ctk.CTkLabel(column, text=header, font=("Arial", 14))
            label.pack(fill="both", expand=True, padx=5, pady=15)

    def _create_cards_scrollable_frame(self):
        """Crea il frame scrollabile che conterra' le card della lista."""
        if self.CARDS_FRAME_NAME:
            cards_frame = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")
            cards_frame.pack(padx=0, pady=10, fill="both", expand=True)
            setattr(self, self.CARDS_FRAME_NAME, cards_frame)

    def _create_add_button(self):
        """Crea il bottone finale che apre il flusso di creazione elemento."""
        self.add_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.add_frame.pack(padx=0, pady=(5, 20), fill="x")

        self.save_button = ctk.CTkButton(
            self.add_frame,
            text=self.ADD_BUTTON_TEXT,
            command=self.open_add_window
        )
        self.save_button.pack()

    def collect_card_warnings(self, items_list):
        """
        Restituisce la mappa ``warning_key -> warning_text`` per gli item correnti.

        Le classi figlie possono sovrascrivere il metodo quando il dominio
        necessita di warning sulle card; il comportamento di default non
        produce warning.
        """
        return {}

    def clear_cards(self):
        """Distrugge tutte le card correnti e pulisce il dizionario locale."""
        for card in self.cards_list.values():
            card.destroy()
        self.cards_list.clear()

    def reload_cards(self, items_list):
        """
        Ricalcola warning, ricrea le card della lista e riapplica l'ordinamento.

        Il metodo centralizza il flusso standard delle list view migrate.
        """
        self.cards_warnings = self.collect_card_warnings(items_list) or {}
        self.clear_cards()
        self.load_items_chunked(items_list)
        self.sort_cards()

    def finalize_item_card(self, card:ctk.CTkFrame, item_key, primary_widget:ctk.CTkButton=None):
        """
        Registra una card nella lista e applica l'eventuale warning visuale.

        Args:
            card: frame principale della card.
            name: nome presente nel button della card
            item_key: chiave univoca usata sia per ``cards_list`` sia per
                ``cards_warnings``.
            primary_widget: widget principale della card a cui agganciare il
                tooltip, tipicamente il bottone in prima colonna.
        """
        self.cards_list[item_key] = card
        ViewUtils.toggle_warning_on_card(card, self.cards_warnings)

        if primary_widget is not None and item_key in self.cards_warnings:
            ViewUtils.add_tooltip(primary_widget, self.cards_warnings[item_key])
        elif primary_widget is not None:
            ViewUtils.add_tooltip(primary_widget, item_key)

    def _convert_to_date(self, date_str):
        """Converte una stringa ``dd-mm-yyyy`` in ``datetime`` per l'ordinamento."""
        try:
            return datetime.strptime(date_str.strip(), "%d-%m-%Y")
        except (ValueError, TypeError):
            return None

    def _convert_to_currency(self, currency_str):
        """Converte una stringa di valuta in ``float`` per l'ordinamento."""
        if not currency_str or not currency_str.strip():
            return None

        try:
            cleaned = currency_str.strip()

            # Normalizza simboli valuta e artefatti di encoding frequenti.
            junk_tokens = ["€", "â‚¬", "Ã¢â€šÂ¬", "EUR", "eur", "\u00a0"]
            for token in junk_tokens:
                cleaned = cleaned.replace(token, "")

            cleaned = cleaned.replace(" ", "")

            negative = False
            if cleaned.startswith("-"):
                negative = True
                cleaned = cleaned[1:]

            # Mantiene solo cifre e separatori numerici, scartando testo spurio.
            cleaned = "".join(ch for ch in cleaned if ch.isdigit() or ch in ",.")
            if not cleaned:
                return None

            last_comma = cleaned.rfind(",")
            last_dot = cleaned.rfind(".")

            if last_comma > last_dot:
                cleaned = cleaned.replace(".", "").replace(",", ".")
            elif last_dot > last_comma:
                cleaned = cleaned.replace(",", "")
            else:
                if cleaned.count(",") == 1 and cleaned.count(".") == 0:
                    cleaned = cleaned.replace(",", ".")
                elif cleaned.count(".") <= 1 and cleaned.count(",") == 0:
                    pass
                else:
                    cleaned = cleaned.replace(",", "").replace(".", "")

            result = float(cleaned) * (-1 if negative else 1)
            return result

        except (ValueError, TypeError):
            return None

    def _convert_to_datetime(self, datetime_str):
        """Converte una stringa ``yyyy-mm-dd hh:mm:ss`` in ``datetime``."""
        try:
            return datetime.strptime(datetime_str.strip(), "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return None

    def _convert_to_lowercase(self, text_str):
        """Normalizza il testo per confronti e ordinamenti case-insensitive."""
        if not text_str or not text_str.strip():
            return None

        return text_str.lower()

    def _get_converter(self, name):
        """Restituisce la funzione di conversione associata al nome configurato."""
        return {
            "text": self._convert_to_lowercase,
            "currency": self._convert_to_currency,
            "datetime": self._convert_to_datetime,
            "date": self._convert_to_date
        }.get(name)

    def sort_cards(self):
        """
        Riordina visivamente le card in base alla configurazione attiva.

        Il valore usato per il confronto puo' arrivare:
        - direttamente dal testo di un widget nella card;
        - dal database, usando la funzione di retrieving passata al costruttore.
        """
        if not hasattr(self, "SORT_CONFIG"):
            return

        temp_dictionary_of_maps = self.db_retrieving_function(keyIsName=True)

        selected_label = self.order_bar_optionMenu.get()
        sort_order = self.order_bar_optionMenu_types.get()
        reverse = (sort_order == "DECRESCENTE")

        sort_cfg = next(
            (cfg for cfg in self.SORT_CONFIG.values() if cfg["label"] == selected_label),
            None
        )
        if not sort_cfg:
            return

        converter = self._get_converter(sort_cfg.get("converter"))
        cards_with_values = []

        for key, card in self.cards_list.items():
            children = card.winfo_children()
            value = None

            if sort_cfg["access"] == "direct":
                idx = sort_cfg["index"]
                if len(children) > idx:
                    value = children[idx].cget("text")
            elif sort_cfg["access"] == "database":
                db_column = sort_cfg["db_column"]
                entity_id = key
                value = temp_dictionary_of_maps[entity_id][db_column]

            converted = converter(value) if converter and value else value
            cards_with_values.append((card, converted))

        cards_with_values.sort(
            key=lambda x: (x[1] is None, x[1]),
            reverse=reverse
        )

        for card, _ in cards_with_values:
            card.pack_forget()

        for card, _ in cards_with_values:
            card.pack(pady=10, padx=10, fill="x", expand=True)

    def show_main_view(self):
        """Mostra il contenitore principale e nasconde l'eventuale dettaglio."""
        self.detail_container.pack_forget()
        self.main_container.pack(fill="both", expand=True)

    def populate_global_infos(self):
        """Popola ``self.global_infos`` prima della visualizzazione."""
        raise NotImplementedError(
            "La logica di popolamento delle info globali deve essere implementata nella classe figlia."
        )

    def open_add_window(self):
        """Apre la finestra modale di aggiunta specifica della classe figlia."""
        raise NotImplementedError(
            "La logica di apertura della finestra di aggiunta deve essere implementata nella classe figlia."
        )

    def load_items_chunked(self, items_list):
        """Carica le card della lista usando la strategia scelta dalla classe figlia."""
        raise NotImplementedError(
            "La logica di caricamento delle card deve essere implementata nella classe figlia."
        )

    def add_item_card(self, *args, **kwargs):
        """Disegna una singola card della lista."""
        raise NotImplementedError(
            "La logica di disegno di una singola card deve essere implementata nella classe figlia."
        )

    def show_last_cards(self):
        """Filtra gli elementi in base alla finestra temporale selezionata."""
        raise NotImplementedError(
            "La logica di filtraggio temporale 'show_last_cards' deve essere implementata nella classe figlia."
        )

    def filter_cards(self, event):
        """
        Filtra visivamente le card in base al testo digitato e al filtro selezionato.

        Il metodo non modifica i dati sorgente: agisce soltanto sul ``pack`` delle
        card gia' create.
        """
        search_text = self.search_bar.get().lower()
        search_type = self.search_bar_optionMenu.get()

        mapping = self.FILTER_MAPPING.get(search_type)

        for card in self.cards_list.values():
            card.pack_forget()

        if mapping is None or not search_text:
            for card in self.cards_list.values():
                card.pack(pady=10, padx=10, fill="x", expand=True)
            return

        idx, expected_class = mapping

        for key, card in self.cards_list.items():
            children = card.winfo_children()
            widget_text = ""

            if len(children) > idx and isinstance(children[idx], expected_class):
                widget = children[idx]
                if isinstance(widget, ctk.CTkOptionMenu):
                    widget_text = widget.get()
                else:
                    widget_text = widget.cget("text")

                if search_text in widget_text.lower():
                    card.pack(pady=10, padx=10, fill="x", expand=True)

import customtkinter as ctk

from BaseList_view import BaseListView
from Views.View_utils import ViewUtils
from Clients_view import ClientDetailView
from Model import DBClientsColumns, DBProductionsColumns

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
        "NOME CLIENTE": (0, ctk.CTkButton)  # Assume che il nome sia il primo widget (bottone)
    }

    # Opzioni di Ordinamento (non specificate in ClientsView.txt, ma richieste dalla base)
    ORDER_OPTIONS = {"NOME": "NOME", "TOT. ENTRATE": "TOT. ENTRATE"}

    # 5. Configurazione filtro temporale (come in Clients_view.txt [1])
    SHOW_LAST_CARDS_OPTIONS = {
        "30 GG": "30 GG",
        "60 GG": "60 GG",
        "90 GG": "90 GG",
        "365 GG": "365 GG"
    }

    def __init__(self, app_context, tab):
        # Chiama l'__init__ della classe Base
        super().__init__(tab)

        # Inizializzazione dei controller e del bus [4, 12]
        self.client_controller = app_context.client_controller
        self.db_model = app_context.db_model
        self.analyzer = app_context.analyzer
        self.production_controller = app_context.production_controller
        self.invoice_controller = app_context.invoice_controller
        self.refund_controller = app_context.refund_controller
        self.catalogo_elenchi = app_context.catalogo_elenchi
        self.config_manager = app_context.config_manager
        self.event_bus = app_context.event_bus
        self.clients_card_list = self.cards_list  # self.cards_list è l'attributo generico della BaseListView

        self.show_last_cards_optionMenu.set("60 GG")

        # Carica i dati iniziali (altrimenti la tab sarebbe vuota)
        self.show_last_cards() # Assumendo un metodo di caricamento

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
            client_productions = self.production_controller.retrieve_productions_map_list_by_client_id(client_id)

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

    def sort_cards(self):
        """Ordina le cards degli stipendi in base ai criteri selezionati nei menu di ordinamento."""

        # Funzioni di supporto per la conversione dei valori
        def _convert_to_date(date_str):
            """Converte una stringa in formato dd-mm-yyyy in un oggetto date per l'ordinamento."""
            from datetime import datetime
            try:
                return datetime.strptime(date_str.strip(), "%d-%m-%Y")
            except (ValueError, TypeError):
                return None

        def _convert_to_currency(currency_str):
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

        def _convert_to_datetime(datetime_str):
            """Converte una stringa in formato yyyy-mm-dd hh:mm:ss in un oggetto datetime per l'ordinamento."""
            from datetime import datetime
            try:
                return datetime.strptime(datetime_str.strip(), "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                return None

        # Ottieni i criteri di ordinamento
        sort_by = self.order_bar_optionMenu.get()
        sort_order = self.order_bar_optionMenu_types.get()

        # Mappatura: ogni criterio associa una tupla (tipo_di_accesso, parametro, funzione_di_conversione, colonna_db)
        sort_mapping = {
            "IMPORTO": ("direct", 2, _convert_to_currency, None),
            "DATA EMISSIONE": ("direct", 3, _convert_to_date, None),
            "DATA CREAZIONE": ("database", 0, _convert_to_datetime, "created_at"),
            "ULTIMA MODIFICA": ("database", 0, _convert_to_datetime, "updated_at")
        }

        mapping = sort_mapping.get(sort_by)

        # Se il tipo di ordinamento non è riconosciuto, non fare nulla
        if mapping is None:
            return

        access_type, param, converter, db_column = mapping
        reverse = (sort_order == "DECRESCENTE")

        # Raccogli tutte le cards e i loro valori di ordinamento
        cards_with_values = []
        for key, card in self.clients_card_list.items():  # Assumendo che la lista si chimi salaries_card_list
            children = card.winfo_children()
            sort_value = ""

            if access_type == "direct":
                # Accesso diretto al valore nella card
                if len(children) > param:
                    sort_value = children[param].cget("text")
            elif access_type == "database":
                # Accesso al valore tramite database
                if len(children) > 0:
                    salary_name = children[0].cget("text")  # Nome stipendio dal primo child
                    # Assumendo che esista un controller per gli stipendi con un metodo retrieve_salary_map_by_name
                    salary_map = self.salary_controller.retrieve_salary_map_by_name(salary_name)
                    if salary_map and db_column:
                        sort_value = salary_map.get(db_column, "")

            # Converti il valore nel tipo appropriato (applicando strip per rimuovere spazi)
            converted_value = None
            if sort_value and sort_value.strip():
                try:
                    converted_value = converter(sort_value)
                except Exception:
                    converted_value = None

            cards_with_values.append((key, card, converted_value))

        # Ordina le cards in base al valore convertito
        # Gestisci i valori None posizionandoli alla fine in entrambi i casi
        cards_with_values.sort(
            key=lambda x: (x[2] is not None, x[2]) if x[2] is not None else (False, None),
            reverse=reverse
        )

        # Nascondi temporaneamente tutte le cards
        for card in self.clients_card_list.values():
            card.pack_forget()

        # Riposiziona le cards nell'ordine ordinato
        for _, card, _ in cards_with_values:
            card.pack(pady=10, padx=10, fill="x", expand=True)

        # Forza l'aggiornamento dell'interfaccia
        self.update_idletasks()
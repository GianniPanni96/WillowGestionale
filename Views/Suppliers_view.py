import customtkinter as ctk
from Views.View_utils import ViewUtils, FilterableComboBox
from Controllers import ControllerUtils, SupplierController
from Model import DBExpensesColumns, DBSuppliersColumns


class SuppliersView(ctk.CTkFrame):

    def __init__(self, db_model, supplier_controller, expense_controller, update_controller,  config_manager, catalogo_elenchi, tab_view, event_bus, analyzer):
        super().__init__(tab_view.tab("Fornitori"))

        self.db_model = db_model
        self.update_controller = update_controller
        self.supplier_controller = supplier_controller
        self.config_manager = config_manager
        self.analyzer = analyzer
        self.expense_controller = expense_controller
        self.catalogo_elenchi = catalogo_elenchi
        self.tab_view = tab_view
        self.tab = tab_view.tab("Fornitori")
        self.event_bus = event_bus

        self.global_infos = {}
        self.amount_aggregate_labels = {}

        self.suppliers_card_list = {}
        self.supplier_card_labels_status = {}

        # Container principale
        self.main_container = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.detail_container = ctk.CTkFrame(self, fg_color="#2b2b2b")

        # Vista dettaglio
        self.supplier_detail_view = SupplierDetailView(
            parent=self,
            back_callback=self.show_main_view,
            supplier_controller=self.supplier_controller,
            expense_controller=self.expense_controller,
            db_model=db_model,
            analyzer=self.analyzer,
            event_bus = self.event_bus,
            catalogo_elenchi=catalogo_elenchi
        )


        # Sistema per tracciare gli after()
        self._after_ids = set()
        self._orig_after = self.after
        self.after = self._track_after

        # Inizializza la vista principale
        self.create_suppliers_tab()
        self.show_main_view()

    def create_suppliers_tab(self):

        self.search_bar_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.search_bar_frame.pack(pady=30, fill="x", anchor="n")
        self.search_bar = ctk.CTkEntry(self.search_bar_frame)
        self.search_bar.pack(padx=(5,35), anchor="e", side="right")
        self.search_bar_label = ctk.CTkLabel(self.search_bar_frame, text="Filtra per nome:", font=("Arial", 14))
        self.search_bar_label.pack(padx=5, anchor="s", side="right")

        self.show_last_cards_optionMenu_values = {
            "30 GG": "30 GG",
            "60 GG": "60 GG",
            "90 GG": "90 GG",
            "365 GG": "365 GG"
        }
        self.show_last_cards_optionMenu = ctk.CTkOptionMenu(self.search_bar_frame,
                                                       values=list(self.show_last_cards_optionMenu_values.values()))
        self.show_last_cards_optionMenu.pack(padx=(5, 200), anchor="s", side="right")
        self.show_last_cards_label = ctk.CTkLabel(self.search_bar_frame, text="Mostra gli ultimi ", font=("Arial", 14))
        self.show_last_cards_label.pack(padx=5, anchor="s", side="right")

        self.show_last_cards_optionMenu.configure(command=lambda _: self.show_last_cards())

        # Aggiungi evento alla barra di ricerca
        self.search_bar.bind("<KeyRelease>", self.filter_cards)


        self.suppliers_table_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.suppliers_table_frame.pack(pady=(20, 0), padx=(10,15), fill="x", anchor="n")

        self.headers = ["NOME", "PARTITA IVA", "TOT. SPESE", "# SPESE", "SPESA MEDIA", "NOTE", "CONTATTO"]

        for i, header in enumerate(self.headers):
            # crea il container
            column = ctk.CTkFrame(self.suppliers_table_frame, fg_color="#333333")
            column.grid(row=0, column=i, sticky="nsew", padx=(0, 5), pady=5)

            # imposta peso e uniformità: tutte le colonne "col" si dividono equamente
            self.suppliers_table_frame.grid_columnconfigure(i, weight=1, uniform="col")

            # la label riempie il suo container
            label = ctk.CTkLabel(column,
                                 text=header,
                                 font=("Arial", 14))
            label.pack(fill="both", expand=True, padx=5, pady=15)

        # Creazione del frame delle cards
        self.suppliers_cards_frame = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")
        self.suppliers_cards_frame.pack(padx=0, pady=10, fill="both", expand=True)

        self.add_supplier_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.add_supplier_frame.pack(padx=0, pady=(5, 20), fill="x")

        self.save_button = ctk.CTkButton(self.add_supplier_frame, text="Aggiungi Fornitore", command=self.open_add_supplier_window)
        self.save_button.pack()

        self.show_last_cards()

    def show_last_cards(self):
        """Mostra solo i supplier con almeno una spesa negli ultimi giorni selezionati"""
        # Ottieni il valore selezionato dal menu
        selected = self.show_last_cards_optionMenu.get()

        # Mappa la selezione al numero di giorni
        days_map = {
            "30 GG": 30,
            "60 GG": 60,
            "90 GG": 90,
            "365 GG": 365
        }
        days = days_map.get(selected, 30)

        # Calcola la data limite (oggi - giorni)
        from datetime import datetime, timedelta
        limit_date = datetime.now() - timedelta(days=days)

        # Recupera tutti i supplier
        all_suppliers = self.supplier_controller.retrieve_suppliers_map_list()

        # Filtra i supplier: solo quelli con almeno una spesa >= limit_date
        filtered_suppliers = []
        for supplier in all_suppliers:
            supplier_id = supplier[DBSuppliersColumns.ID.value]

            # Recupera tutte le spese di questo supplier
            supplier_expenses = self.supplier_controller.retrieve_supplier_with_expenses_map_list(supplier_id)

            # Verifica se almeno una spesa è nell'intervallo temporale
            has_recent_expense = False
            for expense in supplier_expenses:
                date_str = expense.get(DBExpensesColumns.DATE.value)
                if date_str:
                    try:
                        # Prova a parsare la data in formato yyyy-mm-dd o yyyy-mm-dd hh:mm:ss
                        try:
                            expense_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            expense_date = datetime.strptime(date_str, "%Y-%m-%d")

                        if expense_date >= limit_date:
                            has_recent_expense = True
                            break  # Basta una spesa recente
                    except Exception as e:
                        print(f"Errore nel parsare la data {date_str}: {e}")

            if has_recent_expense:
                filtered_suppliers.append(supplier)

        # Svuota le cards attuali
        for card in self.suppliers_card_list.values():
            card.destroy()
        self.suppliers_card_list.clear()

        # Ricarica le cards con i supplier filtrati
        self.load_suppliers_chunked(filtered_suppliers)

    def show_main_view(self):
        """Torna alla vista principale"""
        self.supplier_detail_view.pack_forget()
        self.main_container.pack(fill='both', expand=True)

    def open_add_supplier_window(self):
        """Apre una finestra per aggiungere un nuovo fornitore"""

        self.add_supplier_window = ctk.CTkToplevel(self)
        self.add_supplier_window.title("Aggiungi Nuovo Fornitore")

        # Assicurati che la finestra rimanga sopra
        self.add_supplier_window.lift()  # Porta la finestra sopra quella principale
        self.add_supplier_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

        self.add_supplier_window.geometry("400x700")

        self.supplier_window_scrollableFrame = ctk.CTkScrollableFrame(self.add_supplier_window)
        self.supplier_window_scrollableFrame.pack(fill="both", expand=True)

        # Campi per il form
        self.entry_fields = {
            DBSuppliersColumns.NAME.value: ctk.CTkEntry,
            DBSuppliersColumns.PARTITA_IVA.value: ctk.CTkEntry,
            DBSuppliersColumns.SEDE.value: ctk.CTkEntry,
            DBSuppliersColumns.CONTATTO.value: ctk.CTkEntry,
            DBSuppliersColumns.CATEGORIA.value: FilterableComboBox,
            DBSuppliersColumns.NOTE.value: ctk.CTkTextbox,
        }

        self.error_fields = {
            DBSuppliersColumns.NAME.value: ctk.CTkLabel,
        }

        # Dizionario per conservare i riferimenti ai widget
        self.suppliers_widgets = {}
        self.error_labels = {}

        # Creazione dei widget
        for i, (label_text, widget_class) in enumerate(self.entry_fields.items()):
            # Etichetta
            label = ctk.CTkLabel(self.supplier_window_scrollableFrame, text=label_text)
            if i == 0:
                label.pack(pady=5)
            else:
                label.pack(pady=(35, 0))

            # Widget
            if label_text == DBSuppliersColumns.CATEGORIA.value:
                widget = widget_class(parent=self.supplier_window_scrollableFrame, placeholder="Cerca", autofill=True,
                                      values=[value for key, value in
                                              self.catalogo_elenchi["clients_business_sectors"]],
                                      command=lambda selected_value: self.open_add_business_sector(selected_value))
                widget.set_value(dict(self.catalogo_elenchi["clients_business_sectors"])["ENERGY"])  # Imposta valore predefinito

            else:
                widget = widget_class(self.supplier_window_scrollableFrame)

            if widget_class == ctk.CTkTextbox:
                widget.pack(pady=5, padx=10, fill="x", expand=True)
            else:
                widget.pack(pady=5, padx=10, fill="x", expand=True)

            if self.error_fields.get(label_text) is not None:
                error_label = ctk.CTkLabel(self.supplier_window_scrollableFrame, text="")
                error_label.pack(pady=(0, 15))
                self.error_labels[label_text] = error_label

            self.suppliers_widgets[label_text] = widget

        # Bottone per salvare
        save_button = ctk.CTkButton(
            self.supplier_window_scrollableFrame,
            text="Salva Fornitore",
            command=self.save_supplier_data
        )
        save_button.pack(pady=(35, 15))

        # Aggiungi validazione agli eventi di perdita del focus
        self.suppliers_widgets[DBSuppliersColumns.NAME.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.suppliers_widgets[DBSuppliersColumns.NAME.value],
            lambda val: val.strip() != "",
            self.error_labels[DBSuppliersColumns.NAME.value],
            "Il nome non può essere vuoto."
        ))

    def load_suppliers_chunked(self, suppliers_list):

        extractor = ViewUtils.create_extractor_for_suppliers(
            self.supplier_controller
        )

        ViewUtils.process_items_in_chunks(
            widget=self,
            items_list=suppliers_list,
            add_card_callback=self.add_supplier_card,
            extract_args_callback=extractor,
            cards_frame=self.suppliers_cards_frame
        )

    def add_supplier_card(self, supplier_id, supplier_name, partita_iva, num_spese, spesa_media, tot_spese, note, contatto):
        # Creazione della card
        card = ctk.CTkFrame(self.suppliers_cards_frame, fg_color="dimgray")
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
        self.suppliers_card_list[supplier_name] = card

    def save_supplier_data(self):
        supplier_data = {}

        #controllo sulla categoria
        if self.suppliers_widgets[DBSuppliersColumns.CATEGORIA.value].get_value() == dict(self.catalogo_elenchi["clients_business_sectors"]).get("ADD_SECTOR"):
            ViewUtils.show_error_popup(self.add_supplier_window, "SALVATAGGIO NON RIUSCITO", "Categoria non valida")
            return

        # Riempi il dizionario con i dati dai widget
        for label_text, widget in self.suppliers_widgets.items():
            if isinstance(widget, ctk.CTkEntry) or isinstance(widget, ctk.CTkOptionMenu):
                supplier_data[label_text] = widget.get().strip()  # Recupera il testo o il valore selezionato
            elif isinstance(widget, ctk.CTkTextbox):
                supplier_data[label_text] = widget.get("1.0", "end-1c").strip()  # Recupera il testo dal Textbox

        print("Dati fornitore:", supplier_data)

        supplier_id  = -1

        #chiamata al controller per salvare i dati
        success, message = self.supplier_controller.save_supplier(supplier_data)
        if success:
            supplier_id = self.supplier_controller.retrieve_last_supplier_insert_map()[DBSuppliersColumns.ID.value]
            print(f"Supplier {supplier_data[DBSuppliersColumns.NAME.value]} salvato con successo")
            self.add_supplier_card(
                supplier_id,
                supplier_data[DBSuppliersColumns.NAME.value],
                supplier_data[DBSuppliersColumns.PARTITA_IVA.value],
                0,
                0,
                0,
                supplier_data[DBSuppliersColumns.NOTE.value],
                supplier_data[DBSuppliersColumns.CONTATTO.value],
            )
            self.add_supplier_window.destroy()
        else:
            print(message)
            ViewUtils.show_error_popup(self.add_supplier_window, "ERRORE", message)

    def filter_cards(self, event):
        """Filtra le card in base al testo della barra di ricerca."""
        search_text = self.search_bar.get().lower()

        # Cicla attraverso tutte le card dei clienti
        for nome, card in self.suppliers_card_list.items():
            # Se il nome del cliente contiene il testo della ricerca (ignorando maiuscole/minuscole)
            if search_text in nome.lower():
                # Rendi visibile la card
                card.pack(pady=10, padx=10, fill="x", expand=True)
            else:
                # Nascondi la card
                card.pack_forget()

    def open_supplier_detail_tab(self, supplier_id):
        """Mostra la vista dettaglio utente"""
        self.main_container.pack_forget()
        self.supplier_detail_view.pack(fill='both', expand=True)
        self.supplier_detail_view.create_detail_tab(supplier_id)  # Ricrea i contenuti ogni volta

    def open_add_business_sector(self, selected_value):
        sector_dict = dict(self.catalogo_elenchi["clients_business_sectors"])
        if selected_value == sector_dict.get("ADD_SECTOR"):
            self.add_sector_window = ctk.CTkToplevel(self)
            self.add_sector_window.title("Aggiungi un nuovo settore di business")

            # Assicurati che la finestra rimanga sopra
            self.add_sector_window.lift()  # Porta la finestra sopra quella principale
            self.add_sector_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

            self.add_sector_window.geometry("400x300")

            self.business_sector_window_Frame = ctk.CTkFrame(self.add_sector_window)
            self.business_sector_window_Frame.pack(fill="both", expand=True)

            ctk.CTkLabel(self.business_sector_window_Frame, text="Aggiungi un settore di business alla lista\nsepara parole diverse solo tramite spazio").pack(padx=10, pady=(25, 0))

            self.add_sector_entry = ctk.CTkEntry(self.business_sector_window_Frame)
            self.add_sector_entry.pack(padx=10, pady=5, fill="x", expand=True)

            ctk.CTkButton(self.business_sector_window_Frame, text="Aggiungi settore", command=self.save_business_sector).pack(padx=10, pady=(15, 10))

        else: return

    def save_business_sector(self):
        new_sector = self.add_sector_entry.get()
        new_sector_key = ControllerUtils.normalize_string_for_key(new_sector)
        try:
            self.config_manager.update_list_field("clients_business_sectors", new_sector_key, new_sector, "update")
        except Exception as e:
            ViewUtils.show_error_popup(self.add_sector_window, "Errore", f"Impossibile aggiungere il nuovo settore: {str(e)}")
            return

        self.suppliers_widgets[DBSuppliersColumns.CATEGORIA.value].set(new_sector)
        self.add_sector_window.destroy()

    def cleanup(self):
        """Pulizia completa per liberare memoria - DA AGGIUNGERE IN OGNI VIEW"""
        try:
            print(f"Cleanup di {self.__class__.__name__}")

            # 1. Cancella tutti gli after scheduled
            if hasattr(self, '_after_ids'):
                for after_id in self._after_ids:
                    try:
                        self.after_cancel(after_id)
                    except:
                        pass
                self._after_ids.clear()

            # 2. Distruggi tutte le card e widget dinamici
            card_lists = [
                'payment_card_list', 'invoice_card_list', 'client_card_list',
                'supplier_card_list', 'production_card_list', 'expenses_card_list',
                'salaries_card_list', 'refund_card_list', 'account_card_list'
            ]

            for card_attr in card_lists:
                if hasattr(self, card_attr):
                    card_dict = getattr(self, card_attr)
                    for card_name, card in card_dict.items():
                        try:
                            card.destroy()
                        except:
                            pass
                    card_dict.clear()

            # 3. Pulisci dizionari e liste
            data_attrs = [
                'cards_warnings', 'global_infos', 'amount_aggregate_labels',
                'payment_card_labels_status', 'invoice_card_labels_status',
                'production_card_labels_status'
            ]

            for attr in data_attrs:
                if hasattr(self, attr):
                    getattr(self, attr).clear()

            # 4. Distruggi i container principali se esistono
            container_attrs = [
                'main_container', 'detail_container', 'payments_cards_frame',
                'invoices_cards_frame', 'clients_cards_frame', 'suppliers_cards_frame',
                'productions_cards_frame', 'expenses_cards_frame', 'refunds_cards_frame',
                'accounts_cards_frame', 'salaries_cards_frame'
            ]

            for attr in container_attrs:
                if hasattr(self, attr):
                    container = getattr(self, attr)
                    try:
                        # Distruggi solo se il container esiste ancora
                        if container.winfo_exists():
                            for widget in container.winfo_children():
                                try:
                                    widget.destroy()
                                except:
                                    pass
                    except:
                        pass

            # 5. Pulisci i riferimenti ai controller (opzionale)
            if hasattr(self, 'db_model'):
                self.db_model = None

        except Exception as e:
            print(f"Errore durante il cleanup di {self.__class__.__name__}: {e}")

    def _track_after(self, ms, func, *args):
        """Versione tracciata di after()"""
        after_id = self._orig_after(ms, func, *args)
        self._after_ids.add(after_id)
        return after_id





class SupplierDetailView(ctk.CTkFrame):
    def __init__(self, parent, back_callback, supplier_controller, expense_controller, db_model, analyzer, event_bus, catalogo_elenchi):
        super().__init__(parent)
        self.supplier_controller = supplier_controller
        self.expense_controller = expense_controller
        self.db_model = db_model
        self.back_callback = back_callback
        self.event_bus = event_bus
        self.current_client_id = None
        self.analyzer = analyzer
        self.catalogo_elenchi = catalogo_elenchi

        self.configure(fg_color="transparent")

        # Widgets persistenti (vanno creati una volta sola)
        self.head_frame = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.back_button = ctk.CTkButton(
            self.head_frame,
            text="Elenco Fornitori",
            command=self._cleanup_and_go_back
        )
        self.title_label = ctk.CTkLabel(self.head_frame, font=("Arial", 22, "bold"))

        self.user_info_widgets: dict[str, ctk.CTkEntry | ctk.CTkOptionMenu] = {}

        self.nome_fattura_string = "FATTURA ASSOCIATA"
        self.nome_produzione_string = "PRODUZIONE ASSOCIATA"
        self.nome_rimborso_string = "RIMBORSO ASSOCIATO"


        # Container per i contenuti dinamici
        self.content_frame = ctk.CTkScrollableFrame(self)

        self.switch_modify = ctk.CTkSwitch(self.head_frame, text="Abilita la modifica", command=lambda: self.toggle_edit(self.content_frame))

        # Layout iniziale
        self._setup_base_layout()

    def _setup_base_layout(self):
        """Inizializza la struttura base del layout"""
        self.head_frame.pack(fill="x", pady=5, padx=5)
        self.back_button.pack(anchor="w", side="left", pady=10, padx=10)
        self.title_label.pack(anchor="c", side="left", fill="x", expand=True, pady=10)
        self.switch_modify.pack(anchor="e", side="left", pady=10, padx=10)
        self.content_frame.pack(fill="both", expand=True, pady=20, padx=20)

    def create_detail_tab(self, supplier_id):
        """Ricrea la vista dettaglio per un fornitore specifico"""
        self.current_supplier_id = supplier_id

        # 1. Pulizia dei widget precedenti
        self._clear_content()

        # 2. Caricamento dati
        self.supplier = self.supplier_controller.retrieve_supplier_map_by_id(supplier_id)

        # 3. Aggiornamento elementi persistenti
        self.title_label.configure(
            text=f"{self.supplier[DBSuppliersColumns.NAME.value]}")

        # 4. Creazione contenuti dinamici
        self._create_supplier_info_section(self.supplier)
        self.toggle_edit(self.content_frame)

        self.wrapper_frame = ctk.CTkFrame(self.content_frame, fg_color="#333333")
        self.wrapper_frame.pack(padx=25, pady=(90, 0), fill="both", expand=True)
        #self.wrapper_frame2 = ctk.CTkFrame(self.content_frame, fg_color="#333333")
        #self.wrapper_frame2.pack(padx=25, pady=(90, 90), fill="both", expand=True)
        self._create_expenses_history()

    def _create_supplier_info_section(self, supplier_data):
        # Dizionari per la configurazione
        self.entry_fields = {
            # Sezione Dati Anagrafici
            DBSuppliersColumns.NAME.value: {
                "type": ctk.CTkEntry,
                "label": "Nome Fornitore",
                "section": "Dati Anagrafici"
            },
            DBSuppliersColumns.PARTITA_IVA.value: {
                "type": ctk.CTkEntry,
                "label": "Partita IVA",
                "section": "Dati Anagrafici"
            },
            DBSuppliersColumns.SEDE.value: {
                "type": ctk.CTkEntry,
                "label": "Sede",
                "section": "Dati Anagrafici"
            },

            # Sezione Contatto
            DBSuppliersColumns.CONTATTO.value: {
                "type": ctk.CTkEntry,
                "label": "Contatto",
                "section": "Contatto"
            },

            # Sezione Categoria
            DBSuppliersColumns.CATEGORIA.value: {
                "type": ctk.CTkOptionMenu,
                "label": "Categoria",
                "section": "Categoria",
                "values": [item[1] for item in self.catalogo_elenchi["clients_business_sectors"]]
            },

            # Sezione Note
            DBSuppliersColumns.NOTE.value: {
                "type": ctk.CTkTextbox,
                "label": "Note",
                "section": "Note",
                "height": 100
            }
        }

        # Regole di validazione
        validation_rules = {
            DBSuppliersColumns.NAME.value: (
                lambda val: val.strip() != "",
                "Il nome del fornitore non può essere vuoto"
            ),
            DBSuppliersColumns.PARTITA_IVA.value: (
                lambda val: val == "" or (len(val) == 11 and val.isdigit()),
                "Partita IVA non valida (11 cifre)"
            )
        }

        # Inizializzazione strutture dati
        self.supplier_info_widgets = {}
        self.error_labels = {}
        sections = {}

        # Creazione frame principale
        self.info_frame = ctk.CTkFrame(self.content_frame, border_width=2, border_color="#2659ab")
        self.info_frame.pack(fill="both", expand=True, pady=10, padx=25)

        # Configurazione griglia
        self.info_frame.grid_columnconfigure(0, weight=1, uniform="col")
        self.info_frame.grid_columnconfigure(1, weight=1, uniform="col")

        # Creazione sezioni
        sections_order = [
            "Dati Anagrafici",
            "Contatto",
            "Categoria",
            "Note"
        ]

        # Crea i frame per ogni sezione
        for i, section_name in enumerate(sections_order):
            frame = ctk.CTkFrame(self.info_frame)
            column = 0 if i % 2 == 0 else 1
            row = i // 2
            frame.grid(row=row, column=column, sticky="nsew", padx=15, pady=15)
            frame.grid_columnconfigure(1, weight=1)
            sections[section_name] = {
                "frame": frame,
                "row": 0
            }

            # Titolo della sezione
            ctk.CTkLabel(frame, text=section_name, font=("Arial", 14, "bold")).grid(
                row=0, column=0, columnspan=2, sticky="w", padx=15, pady=5
            )
            sections[section_name]["row"] += 1

        # Popolamento delle sezioni
        for field, config in self.entry_fields.items():
            section = sections[config["section"]]
            frame = section["frame"]
            row = section["row"]

            # Creazione label
            lbl = ctk.CTkLabel(frame, text=config["label"] + ":")
            lbl.grid(row=row, column=0, sticky="w", padx=(15, 5), pady=(2, 5))

            # Creazione widget
            value = str(supplier_data.get(field, ""))

            if config["type"] == ctk.CTkOptionMenu:
                widget = config["type"](frame, values=config.get("values", []))

                # Conversione valore DB -> descrizione
                if field == DBSuppliersColumns.CATEGORIA.value:
                    current_value = next(
                        (desc for key, desc in self.catalogo_elenchi["clients_business_sectors"] if key == value),
                        value
                    )
                    widget.set(current_value)
                else:
                    widget.set(value if value else config.get("values", [""])[0])

            elif config["type"] == ctk.CTkTextbox:
                widget = config["type"](frame, height=config.get("height", 50))
                widget.insert("1.0", value)
            else:
                widget = config["type"](frame)
                widget.insert(0, value)

            widget.grid(
                row=row,
                column=1,
                sticky="ew",
                padx=(5, 15),
                pady=(2, 5),
                rowspan=2 if config["type"] == ctk.CTkTextbox else 1
            )
            self.supplier_info_widgets[field] = widget

            # Gestione validazione
            if field in validation_rules:
                validation_func, error_message = validation_rules[field]

                error_lbl = ctk.CTkLabel(frame, text="", text_color="#e8e5dc")
                error_lbl.grid(
                    row=row + (2 if config["type"] == ctk.CTkTextbox else 1),
                    column=1,
                    sticky="w",
                    padx=5,
                    pady=(0, 10)
                )
                self.error_labels[field] = error_lbl

                if config["type"] != ctk.CTkTextbox:
                    widget.bind("<FocusOut>",
                                lambda e, w=widget, vl=validation_func, el=error_lbl, em=error_message:
                                ViewUtils.validate_entry(w, vl, el, em))
                else:
                    widget.bind("<FocusOut>",
                                lambda e, w=widget, vl=validation_func, el=error_lbl, em=error_message:
                                ViewUtils.validate_textbox(w, vl, el, em))

            # Aggiorna contatore righe
            section["row"] += 3 if config["type"] == ctk.CTkTextbox else 2

        buttons_frame = ctk.CTkFrame(self.info_frame, fg_color="#2b2b2b")
        buttons_frame.grid(row=2, column=0, columnspan=2, pady=(5, 15), padx=20, sticky="WE")

        # Bottone Salva
        self.save_info_btn = ctk.CTkButton(buttons_frame, text="Salva Fornitore", command=self.save_supplier_mod)
        self.save_info_btn.pack(padx=(400, 10), pady=(20, 20), side="left")

        # Bottone Elimina
        self.delete_btn = ctk.CTkButton(buttons_frame, text="Elimina Fornitore",
                                        fg_color="#8B0000", hover_color="#A52A2A",
                                        command=self.delete_supplier)
        self.delete_btn.pack(padx=10, pady=(20, 20), side="right", anchor="e")

    def toggle_edit(self, parent):
        """
        Abilita o disabilita la modifica dei widget nella finestra di modifica utente.
        """
        # Determina lo stato (abilitato/disabilitato) in base al valore dello switch
        state = ctk.NORMAL if self.switch_modify.get() else ctk.DISABLED

        # Cambia anche lo stato del pulsante Salva
        self.save_info_btn.configure(state=state)
        self.delete_btn.configure(state=state)

        for w in parent.winfo_children():
            # se è un Entry
            if isinstance(w, (ctk.CTkEntry, ctk.CTkTextbox)):
                w.configure(state=state, text_color="#636363" if state == ctk.DISABLED else "#c2c2c2")
            # se è un OptionMenu
            elif isinstance(w, ctk.CTkOptionMenu):
                w.configure(state=state)
            # se è un Frame/container, scendi ricorsivamente
            elif isinstance(w, (ctk.CTkFrame, ctk.CTkScrollableFrame, ctk.CTkToplevel)):
                self.toggle_edit(w)

    def _create_expenses_history(self):
        """Crea la sezione storico delle spese """
        section_frame = ctk.CTkFrame(self.wrapper_frame, border_width=2, border_color="#2659ab")
        section_frame.pack(fill="both", side="left", expand=True, pady=0, padx=(0, 30))

        ctk.CTkLabel(section_frame, text="SPESE", font=("Arial", 14, "bold")).pack(anchor="w", pady=(10, 10),
                                                                                              padx=10)

        global_infos = {
            "TOTALE SPESE": {
                "value": self.supplier_controller.calcola_tot_spese_supplier(self.current_supplier_id),
                "uom": "€"
            }
        }

        self.global_infos_invoices_widgets = ViewUtils.construct_global_infos_cards(section_frame, global_infos)

        # tabella invoices
        expenses_frame = ctk.CTkScrollableFrame(section_frame, height=300)
        expenses_frame.pack(fill="both", expand=True, padx=(10, 20), pady=(10, 20))

        # popolo le spese
        expenses = self.supplier_controller.retrieve_supplier_with_expenses_map_list(self.current_supplier_id)
        for expense in expenses:
            if expense[DBExpensesColumns.NAME.value] is not None:
                nome_spesa = expense[DBExpensesColumns.NAME.value]
                id_spesa = expense[DBExpensesColumns.ID.value]
                spesa_button = ctk.CTkButton(expenses_frame,
                                             text=f"{nome_spesa}",
                                             command=lambda id=id_spesa: self.show_expense_detail(id))
                spesa_button.pack(padx=10, pady=10, fill="x", expand=True)

    def show_expense_detail(self, expense_id):
        self.event_bus.publish(ViewUtils.EventBusKeys.SHOW_EXPENSE_DETAIL, expense_id)

    def save_supplier_mod(self):
        # Costruzione dati fornitore
        supplier_data = {
            DBSuppliersColumns.NAME.value: self.supplier_info_widgets[
                DBSuppliersColumns.NAME.value].get().strip(),
            DBSuppliersColumns.PARTITA_IVA.value: self.supplier_info_widgets[
                DBSuppliersColumns.PARTITA_IVA.value].get().strip(),
            DBSuppliersColumns.SEDE.value: self.supplier_info_widgets[
                DBSuppliersColumns.SEDE.value].get().strip(),
            DBSuppliersColumns.CONTATTO.value: self.supplier_info_widgets[
                DBSuppliersColumns.CONTATTO.value].get().strip(),
            DBSuppliersColumns.CATEGORIA.value: self.supplier_info_widgets[
                DBSuppliersColumns.CATEGORIA.value].get(),
            DBSuppliersColumns.NOTE.value: self.supplier_info_widgets[
                DBSuppliersColumns.NOTE.value].get("1.0", "end-1c").strip()
        }

        # Chiamata al controller per salvare i dati
        success, message = self.supplier_controller.update_supplier(self.current_supplier_id, supplier_data)

        if success:
            supplier_name = self.supplier_controller.retrieve_supplier_map_by_id(
                self.current_supplier_id)[DBSuppliersColumns.NAME.value]
            print(f"Fornitore {supplier_name} salvato con successo")
            ViewUtils.show_confirm_popup_2(self.content_frame, "SALVATAGGIO COMPLETATO", message)
            self.switch_modify.deselect()
            self.toggle_edit(self.content_frame)
        else:
            print(f"{message}")
            ViewUtils.show_error_popup(self.content_frame, "ERRORE", message)

    def delete_supplier(self):
        confirmation = ViewUtils.ask_confirmation_popup(self.content_frame, "Stai per eliminare questo fornitore.\nDesideri continuare ?", "ELIMINAZIONE FORNITORE" )
        if confirmation:
            #check if something link to this client
            expenses = self.expense_controller.retrieve_expense_map_list_by_supplier(self.current_supplier_id)

            if len(expenses) == 0 :
                success, message = self.supplier_controller.delete_supplier(self.current_supplier_id)
                if success:
                    print(message)
                    ViewUtils.show_confirm_popup_simple(self.content_frame, "CONFERMA ELIMINAZIONE", message)
                else:
                    # Mostra il messaggio d'errore
                    print(message)
                    ViewUtils.show_error_popup(self.content_frame, "ERRORE", message)
            else:
                ViewUtils.show_error_popup(self.info_frame, message="Impossibile eliminare il fornitore.\n\n"
                                                                    "Esiste un item collegato a questo fornitore.\n"
                                                                    "Eliminare ogni riferimento a questo fornitore per poterlo eliminare dal database.")

    def _clear_content(self):
        """Distrugge tutti i widget dinamici"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def _cleanup_and_go_back(self):
        """Pulizia completa prima di tornare indietro"""
        self._clear_content()
        self.pack_forget()
        self.back_callback()

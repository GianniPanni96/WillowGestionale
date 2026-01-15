import customtkinter as ctk
from datetime import datetime
from Books_retriever import BooksRetriever


class TaxesView(ctk.CTkFrame):

    def __init__(self, app_context, tab_view):
        super().__init__(tab_view.tab("Tasse"))

        self.app_context = app_context
        self.books_retriever = app_context.books_retriever
        self.db_model = app_context.db_model
        self.update_controller = app_context.update_controller
        self.analyzer = app_context.analyzer
        self.config_manager = app_context.config_manager
        self.catalogo_elenchi = app_context.catalogo_elenchi
        self.tab_view = tab_view
        self.tab = tab_view.tab("Tasse")
        self.event_bus = app_context.event_bus

        self.header_font = ("Arial", 18)
        self.text_large = ("Arial", 16)
        self.text_med = ("Arial", 14)

        # Container principale
        self.main_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Variabile per lo switch
        self.show_current_year = ctk.BooleanVar(value=True)  # True = anno corrente, False = anno passato

        # Sistema per tracciare gli after()
        self._after_ids = set()
        self._orig_after = self.after
        self.after = self._track_after

        # Inizializza la vista principale
        self.create_controls()
        self.create_tax_tab()

    def create_controls(self):
        """Crea i controlli di selezione (switch) nella parte superiore"""
        controls_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        controls_frame.pack(fill="x", padx=10, pady=(10, 20))

        # Titolo
        title_label = ctk.CTkLabel(
            controls_frame,
            text="Previsione Tasse Willow",
            font=self.header_font
        )
        title_label.pack(side="left", padx=(0, 20))

        # Switch per selezione anno
        switch_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        switch_frame.pack(side="left")

        self.year_switch = ctk.CTkSwitch(
            switch_frame,
            text="",
            variable=self.show_current_year,
            command=self.on_year_switch_changed,
            font=self.text_med
        )
        self.year_switch.pack(side="left", padx=(0, 10))

        # Etichetta che mostra l'anno selezionato
        self.year_label = ctk.CTkLabel(
            switch_frame,
            text=f"Anno: {datetime.now().year}",
            font=self.text_large,
            text_color="#2d7acf"
        )
        self.year_label.pack(side="left")

        # Separatore
        separator = ctk.CTkFrame(self.main_container, height=2, fg_color="gray")
        separator.pack(fill="x", padx=10, pady=(0, 10))

    def on_year_switch_changed(self):
        """Gestisce il cambio dello switch"""
        if self.show_current_year.get():
            self.year_label.configure(text=f"Anno: {datetime.now().year}")
        else:
            self.year_label.configure(text=f"Anno: {datetime.now().year - 1}")

        # Ricrea la tabella con i dati appropriati
        self.create_tax_tab()

    def get_tax_data(self):
        """Recupera i dati delle tasse in base alla selezione dello switch"""
        if self.show_current_year.get():
            # Usa i dati calcolati in tempo reale per l'anno corrente
            return self.analyzer.calculate_previsione_tasse_willow()
        else:
            # Usa i dati dal CSV per l'anno passato
            last_year = datetime.now().year - 1
            taxes_summary = self.books_retriever.get_taxes_summary_for_year(last_year)

            if not taxes_summary:
                # Se non ci sono dati per l'anno passato, mostra un messaggio
                print(f"Nessun dato disponibile per l'anno {last_year}")
                return None

            # Converte il formato dei dati dal retriever al formato dell'analyzer
            return self.convert_retriever_to_analyzer_format(taxes_summary)

    def convert_retriever_to_analyzer_format(self, retriever_data):
        """Converte il formato dei dati dal BooksRetriever al formato dell'analyzer"""
        analyzer_format = {}

        # Aggiungi i dati degli utenti
        if "users" in retriever_data and retriever_data["users"]:
            for user_name, user_data in retriever_data["users"].items():
                analyzer_format[user_name] = {
                    "SALDO WILLOW": float(user_data.get("saldo_willow", 0)),
                    "ACCONTO WILLOW": float(user_data.get("acconto_willow", 0)),
                    "IRPEF WILLOW": float(user_data.get("irpef_willow", 0)),
                    "INPS WILLOW": float(user_data.get("inps_willow", 0))
                }

        # Aggiungi il totale
        if "totale" in retriever_data and retriever_data["totale"]:
            total_data = retriever_data["totale"]
            analyzer_format["TOTALE"] = {
                "SALDO WILLOW": float(total_data.get("saldo_willow", 0)),
                "ACCONTO WILLOW": float(total_data.get("acconto_willow", 0)),
                "IRPEF WILLOW": float(total_data.get("irpef_willow", 0)),
                "INPS WILLOW": float(total_data.get("inps_willow", 0))
            }
        else:
            # Se non c'è il totale nel CSV, calcolalo sommando i valori degli utenti
            total_saldo = sum(user_data.get("SALDO WILLOW", 0) for user_data in analyzer_format.values())
            total_acconto = sum(user_data.get("ACCONTO WILLOW", 0) for user_data in analyzer_format.values())
            total_irpef = sum(user_data.get("IRPEF WILLOW", 0) for user_data in analyzer_format.values())
            total_inps = sum(user_data.get("INPS WILLOW", 0) for user_data in analyzer_format.values())

            analyzer_format["TOTALE"] = {
                "SALDO WILLOW": total_saldo,
                "ACCONTO WILLOW": total_acconto,
                "IRPEF WILLOW": total_irpef,
                "INPS WILLOW": total_inps
            }

        return analyzer_format

    def create_tax_tab(self):
        """Crea la vista delle tasse con i dati appropriati"""
        # Recupera i dati in base alla selezione
        tasse_data = self.get_tax_data()

        if tasse_data is None:
            # Mostra un messaggio di errore se non ci sono dati
            self.show_no_data_message()
            return

        # Pulisci il contenitore principale (mantenendo solo i controlli)
        for widget in self.main_container.winfo_children():
            if widget not in [self.main_container.winfo_children()[0],
                              self.main_container.winfo_children()[1]]:  # Mantieni i controlli
                widget.destroy()

        # Determina l'anno da mostrare nel titolo
        if self.show_current_year.get():
            display_year = datetime.now().year
        else:
            display_year = datetime.now().year - 1

        # Titolo della sezione
        title_label = ctk.CTkLabel(
            self.main_container,
            text=f"Previsione Tasse Willow - Panoramica Generale {display_year}",
            font=self.header_font
        )
        title_label.pack(pady=(20, 20))

        # =======================================================================
        # Prima tabella: Saldi e Acconti
        # =======================================================================
        saldo_label = ctk.CTkLabel(
            self.main_container,
            text="Saldi e Acconti",
            font=self.header_font,
            text_color="#2d7acf"
        )
        saldo_label.pack(padx=15, pady=(10, 5), anchor="w")
        ctk.CTkLabel(self.main_container,
                     text="Previsione delle tasse da versare quest'anno, in funzione del saldo rispetto all'acconto dell'anno scorso e l'acconto per il prossimo anno",
                     font=self.text_large,
                     text_color="gray").pack(padx=15, pady=(0, 5), anchor="w")

        # Crea un frame per la prima tabella
        table_frame1 = ctk.CTkFrame(self.main_container)
        table_frame1.pack(fill="both", expand=True, padx=10, pady=(0, 20))

        current_year = display_year
        next_year = current_year + 1

        # Intestazioni della tabella
        headers1 = ["Utente", f"Saldo Willow - {current_year} (€)", f"Acconto Willow - {next_year} (€)"]

        # Crea le intestazioni
        for col, header in enumerate(headers1):
            header_label = ctk.CTkLabel(
                table_frame1,
                text=header,
                font=self.text_large,
                fg_color="#1F538D",  # Blu scuro
                corner_radius=6,
                width=180,
                height=40
            )
            header_label.grid(row=0, column=col, padx=5, pady=5, sticky="nsew")

        # Popola la tabella con i dati degli utenti
        row = 1
        for user_name, values in tasse_data.items():
            if user_name == "TOTALE":
                continue  # Gestiamo il totale separatamente

            # Nome utente
            name_label = ctk.CTkLabel(
                table_frame1,
                text=user_name,
                font=self.text_med,
                anchor="w",
                width=180,
                height=30
            )
            name_label.grid(row=row, column=0, padx=5, pady=2, sticky="w")

            # Saldo Willow
            saldo_label = ctk.CTkLabel(
                table_frame1,
                text=f"{values['SALDO WILLOW']:,.2f}".replace(",", " ").replace(".", ",").replace(" ", "."),
                font=self.text_med,
                anchor="e",
                width=180,
                height=30
            )
            saldo_label.grid(row=row, column=1, padx=5, pady=2, sticky="e")

            # Acconto Willow
            acconto_label = ctk.CTkLabel(
                table_frame1,
                text=f"{values['ACCONTO WILLOW']:,.2f}".replace(",", " ").replace(".", ",").replace(" ", "."),
                font=self.text_med,
                anchor="e",
                width=180,
                height=30
            )
            acconto_label.grid(row=row, column=2, padx=5, pady=2, sticky="e")

            row += 1

        # Riga del totale
        total_values = tasse_data["TOTALE"]

        # Separatore
        separator = ctk.CTkFrame(
            table_frame1,
            height=2,
            fg_color="gray"
        )
        separator.grid(row=row, column=0, columnspan=3, sticky="ew", pady=10)
        row += 1

        # Etichetta "TOTALE"
        total_label = ctk.CTkLabel(
            table_frame1,
            text="TOTALE",
            font=self.header_font,
            anchor="w",
            width=180,
            height=35
        )
        total_label.grid(row=row, column=0, padx=5, pady=2, sticky="w")

        # Totale Saldo
        total_saldo_label = ctk.CTkLabel(
            table_frame1,
            text=f"{total_values['SALDO WILLOW']:,.2f}".replace(",", " ").replace(".", ",").replace(" ", "."),
            font=self.header_font,
            anchor="e",
            width=180,
            height=35,
            fg_color="#1F538D",  # Blu scuro
            corner_radius=6
        )
        total_saldo_label.grid(row=row, column=1, padx=5, pady=2, sticky="e")

        # Totale Acconto
        total_acconto_label = ctk.CTkLabel(
            table_frame1,
            text=f"{total_values['ACCONTO WILLOW']:,.2f}".replace(",", " ").replace(".", ",").replace(" ", "."),
            font=self.header_font,
            anchor="e",
            width=180,
            height=35,
            fg_color="#1F538D",  # Blu scuro
            corner_radius=6
        )
        total_acconto_label.grid(row=row, column=2, padx=5, pady=2, sticky="e")

        # Configura il peso delle colonne per un'espansione uniforme
        for i in range(3):
            table_frame1.grid_columnconfigure(i, weight=1)

        # =======================================================================
        # Seconda tabella: Ripartizione IRPEF/INPS
        # =======================================================================
        ripartizione_label = ctk.CTkLabel(
            self.main_container,
            text="Ripartizione IRPEF/INPS",
            font=self.header_font,
            text_color="#2d7acf"
        )
        ripartizione_label.pack(padx=15, pady=(90, 5), anchor="w")
        ctk.CTkLabel(self.main_container,
                     text="Dettaglio delle tasse relative a quest'anno, differenziate tra IRPEF e INPS  -  Non tiene conto di acconti precedenti o futuri",
                     font=self.text_large,
                     text_color="gray").pack(padx=15, pady=(0, 5), anchor="w")

        # Crea un frame per la seconda tabella
        table_frame2 = ctk.CTkFrame(self.main_container)
        table_frame2.pack(fill="both", expand=True, padx=10, pady=(0, 20))

        # Intestazioni della tabella
        headers2 = ["Utente", "IRPEF Willow (€)", "INPS Willow (€)"]

        # Crea le intestazioni
        for col, header in enumerate(headers2):
            header_label = ctk.CTkLabel(
                table_frame2,
                text=header,
                font=self.text_large,
                fg_color="#1F538D",  # Blu scuro
                corner_radius=6,
                width=180,
                height=40
            )
            header_label.grid(row=0, column=col, padx=5, pady=5, sticky="nsew")

        # Popola la tabella con i dati degli utenti
        row = 1
        for user_name, values in tasse_data.items():
            if user_name == "TOTALE":
                continue  # Gestiamo il totale separatamente

            # Nome utente
            name_label = ctk.CTkLabel(
                table_frame2,
                text=user_name,
                font=self.text_med,
                anchor="w",
                width=180,
                height=30
            )
            name_label.grid(row=row, column=0, padx=5, pady=2, sticky="w")

            # IRPEF Willow
            irpef_label = ctk.CTkLabel(
                table_frame2,
                text=f"{values['IRPEF WILLOW']:,.2f}".replace(",", " ").replace(".", ",").replace(" ", "."),
                font=self.text_med,
                anchor="e",
                width=180,
                height=30
            )
            irpef_label.grid(row=row, column=1, padx=5, pady=2, sticky="e")

            # INPS Willow
            inps_label = ctk.CTkLabel(
                table_frame2,
                text=f"{values['INPS WILLOW']:,.2f}".replace(",", " ").replace(".", ",").replace(" ", "."),
                font=self.text_med,
                anchor="e",
                width=180,
                height=30
            )
            inps_label.grid(row=row, column=2, padx=5, pady=2, sticky="e")

            row += 1

        # Riga del totale
        # Separatore
        separator = ctk.CTkFrame(
            table_frame2,
            height=2,
            fg_color="gray"
        )
        separator.grid(row=row, column=0, columnspan=3, sticky="ew", pady=10)
        row += 1

        # Etichetta "TOTALE"
        total_label = ctk.CTkLabel(
            table_frame2,
            text="TOTALE",
            font=self.header_font,
            anchor="w",
            width=180,
            height=35
        )
        total_label.grid(row=row, column=0, padx=5, pady=2, sticky="w")

        # Totale IRPEF
        total_irpef_label = ctk.CTkLabel(
            table_frame2,
            text=f"{total_values['IRPEF WILLOW']:,.2f}".replace(",", " ").replace(".", ",").replace(" ", "."),
            font=self.header_font,
            anchor="e",
            width=180,
            height=35,
            fg_color="#1F538D",  # Blu scuro
            corner_radius=6
        )
        total_irpef_label.grid(row=row, column=1, padx=5, pady=2, sticky="e")

        # Totale INPS
        total_inps_label = ctk.CTkLabel(
            table_frame2,
            text=f"{total_values['INPS WILLOW']:,.2f}".replace(",", " ").replace(".", ",").replace(" ", "."),
            font=self.header_font,
            anchor="e",
            width=180,
            height=35,
            fg_color="#1F538D",  # Blu scuro
            corner_radius=6
        )
        total_inps_label.grid(row=row, column=2, padx=5, pady=2, sticky="e")

        # Configura il peso delle colonne per un'espansione uniforme
        for i in range(3):
            table_frame2.grid_columnconfigure(i, weight=1)

    def show_no_data_message(self):
        """Mostra un messaggio quando non ci sono dati disponibili per l'anno selezionato"""
        message_frame = ctk.CTkFrame(self.main_container)
        message_frame.pack(fill="both", expand=True, padx=50, pady=100)

        message_label = ctk.CTkLabel(
            message_frame,
            text="⚠️ Nessun dato disponibile per l'anno selezionato",
            font=self.header_font,
            text_color="orange"
        )
        message_label.pack(pady=20)

        help_label = ctk.CTkLabel(
            message_frame,
            text="Assicurati che il file taxes_aggregated_data.csv sia presente nella directory Books",
            font=self.text_med,
            text_color="gray"
        )
        help_label.pack(pady=10)

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
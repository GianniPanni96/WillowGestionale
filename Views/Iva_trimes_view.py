import customtkinter as ctk
from datetime import datetime



class IvaTrimesView(ctk.CTkFrame):
    def __init__(self, app_context, tabview):
        super().__init__(tabview.tab("Iva"))

        self.app_context = app_context
        self.db_model = app_context.db_model
        self.invoice_controller = app_context.invoice_controller
        self.user_controller = app_context.user_controller
        self.expense_controller = app_context.expense_controller
        self.update_controller = app_context.update_controller
        self.analyzer = app_context.analyzer
        self.tabview = tabview
        self.tab = tabview.tab("Iva")
        self.event_bus = app_context.event_bus

        self.header_font = ("Arial", 14)
        self.text_large = ("Arial", 14)
        self.text_med = ("Arial", 14)

        # Container principale
        self.main_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Inizializza la vista principale
        self.create_iva_trimes_tab()


        # Sistema per tracciare gli after()
        self._after_ids = set()
        self._orig_after = self.after
        self.after = self._track_after

    def create_iva_trimes_tab(self):
        # Creazione frame principale
        tab_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        tab_frame.pack(fill="both", expand=True, pady=(0, 80), padx=(10, 0), ipady=20)

        # Frame per l'header
        self.iva_header_frame = ctk.CTkFrame(tab_frame, fg_color="transparent") ##333333
        self.iva_header_frame.pack(fill="x", anchor="n", padx=(15), pady=(25, 0))

        # Configurazione header
        headers = [
            ("TRIMESTRE", 0),
            ("CREDITO", 1),
            ("DEBITO", 2),
            ("DA PAGARE", 3)
        ]

        for i, (text, col) in enumerate(headers):
            header = ctk.CTkFrame(self.iva_header_frame, fg_color="#3773b8")
            header.grid(row=0, column=col, sticky="nsew", padx=(2, 5) if col < 3 else (0, 0), pady=5)
            self.iva_header_frame.grid_columnconfigure(col, weight=1, uniform="col")
            ctk.CTkLabel(header, text=text, font=self.header_font).pack(fill="x", expand=True, padx=5, pady=15)

        # Frame principale per la lista trimestrale + totale annuale
        main_list_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        main_list_frame.pack(fill="x", anchor="n", padx=15, pady=(0, 25))

        # Frame per i trimestri (dove verranno aggiunti i container dei trimestri)
        self.trimestral_container = ctk.CTkFrame(main_list_frame, fg_color="transparent")
        self.trimestral_container.pack(fill="x", expand=True)

        # Ottieni i dati IVA trimestrali
        iva_data = self.analyzer.calculate_tot_trimestral_iva()

        # Calcola i totali aggregati per trimestre
        quarter_totals = {
            "Gen-Marz": {"debito": 0.0, "credito": 0.0, "da_pagare": 0.0},
            "Apr-Giu": {"debito": 0.0, "credito": 0.0, "da_pagare": 0.0},
            "Lug-Sett": {"debito": 0.0, "credito": 0.0, "da_pagare": 0.0},
            "Ott-Dic": {"debito": 0.0, "credito": 0.0, "da_pagare": 0.0}
        }

        # Calcola i totali annuali
        annual_totals = {"debito": 0.0, "credito": 0.0, "da_pagare": 0.0}

        # Aggrega i dati per trimestre
        for user_data in iva_data.values():
            for quarter, data in user_data.items():
                for key in ["debito", "credito", "da_pagare"]:
                    quarter_totals[quarter][key] += data[key]
                    annual_totals[key] += data[key]

        # Ordine dei trimestri
        quarters_order = ["Gen-Marz", "Apr-Giu", "Lug-Sett", "Ott-Dic"]
        self.expanded_states = {quarter: False for quarter in quarters_order}

        # Crea i container per ogni trimestre
        for quarter in quarters_order:
            data = quarter_totals[quarter]

            # Container principale per il trimestre (contiene riga + dettagli)
            quarter_container = ctk.CTkFrame(self.trimestral_container, border_width=2, border_color="#3773b8")
            quarter_container.pack(fill="x", padx=5, pady=5)

            # Riga di riepilogo del trimestre
            row_frame = ctk.CTkFrame(quarter_container)
            row_frame.pack(fill="x", padx=5, pady=5)

            # Configurazione colonne
            for col in range(4):
                row_frame.grid_columnconfigure(col, weight=1, uniform="col")

            # Colonna 1: Nome trimestre + pulsante
            quarter_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
            quarter_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

            quarter_header = ctk.CTkFrame(quarter_frame, fg_color="transparent")
            quarter_header.pack(fill="x", expand=True)

            ctk.CTkLabel(
                quarter_header,
                text=quarter,
                font=self.text_large
            ).pack(side="left", padx=10, pady=15)

            # Pulsante dropdown
            dropdown_btn = ctk.CTkButton(
                quarter_header,
                text=">",
                width=20,
                height=20,
                command=lambda q=quarter: self.toggle_quarter_details(q)
            )
            dropdown_btn.pack(side="right", padx=15, pady=15)

            # Colonna 2: Credito IVA
            credito_frame = ctk.CTkFrame(row_frame)
            credito_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 5))
            ctk.CTkLabel(
                credito_frame,
                font=self.text_med,
                text=f"{data['credito']:.2f} €"
            ).pack(padx=5, pady=5, anchor="center", fill="both", expand=True)

            # Colonna 3: Debito IVA
            debito_frame = ctk.CTkFrame(row_frame)
            debito_frame.grid(row=0, column=2, sticky="nsew", padx=(0, 5))
            ctk.CTkLabel(
                debito_frame,
                font=self.text_med,
                text=f"{data['debito']:.2f} €"
            ).pack(padx=5, pady=5, anchor="center", fill="both", expand=True)

            # Colonna 4: Saldo da pagare
            saldo_frame = ctk.CTkFrame(row_frame)
            saldo_frame.grid(row=0, column=3, sticky="nsew")

            saldo = data['da_pagare']
            fg_color = "#f52f2f" if saldo > 0 else "#2ca31c" if saldo < 0 else "#b0b0b0"

            ctk.CTkLabel(
                saldo_frame,
                text=f"{saldo:.2f} €",
                fg_color=fg_color,
                corner_radius=4
            ).pack(padx=5, pady=5, fill="both", expand=True)

            # Frame per i dettagli (inizialmente nascosto)
            details_frame = ctk.CTkFrame(quarter_container, fg_color="#1a1a1a")
            details_frame.pack(fill="x", pady=(0, 5))
            details_frame.pack_forget()  # Nascondi inizialmente

            # Popola i dettagli per le partite IVA
            self.populate_quarter_details(quarter, details_frame, iva_data)

            # Memorizza i riferimenti per il toggle
            setattr(self, f"{quarter}_details_frame", details_frame)
            setattr(self, f"{quarter}_dropdown_btn", dropdown_btn)

        # Aggiungi riga per il totale annuale (dopo tutti i trimestri)
        self.add_annual_total_row(main_list_frame, annual_totals)


        # ===============================
        # Riga ultimo trimestre anno precedente
        # ===============================
        ctk.CTkLabel(self.main_container, text=f"-  Ultimo trimestre {datetime.now().year - 1}  -", font=("Arial",14, "italic")
                     ).pack(padx=10, pady=(5, 0), fill="x", expand=True)
        # Recupero dati IVA ultimo trimestre anno precedente (CSV)
        previous_year = datetime.now().year - 1
        target_trimestre = "Ott-Dic"

        iva_rows = self.app_context.books_retriever.get_iva_data_for_year(previous_year)

        # Aggregati
        agg_credito = 0.0
        agg_debito = 0.0
        agg_saldo = 0.0

        # Dettaglio per utente
        per_user_data = {}

        for row in iva_rows:
            if row.get("nome_trimestre") != target_trimestre:
                continue

            credito = float(row.get("iva_credito", 0.0))
            debito = float(row.get("iva_debito", 0.0))
            saldo = float(row.get("iva_da_pagare", 0.0))
            user = row.get("utente", "N/D")

            # Aggregati
            agg_credito += credito
            agg_debito += debito
            agg_saldo += saldo

            # Dettaglio
            per_user_data[user] = {
                "credito": credito,
                "debito": debito,
                "da_pagare": saldo
            }

        past_quarter_container = ctk.CTkFrame(
            self.main_container,
            border_width=2,
            border_color="gray"
        )
        past_quarter_container.pack(fill="x", padx=5, pady=5)

        # Riga di riepilogo
        past_row_frame = ctk.CTkFrame(past_quarter_container)
        past_row_frame.pack(fill="x", padx=5, pady=5)

        # Configurazione colonne
        for col in range(4):
            past_row_frame.grid_columnconfigure(col, weight=1, uniform="col")

        # ---- Colonna 1: Etichetta trimestre ----
        past_quarter_frame = ctk.CTkFrame(past_row_frame, fg_color="transparent")
        past_quarter_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        ctk.CTkLabel(
            past_quarter_frame,
            text=f"Ott-Dec {datetime.now().year - 1}",
            font=self.text_large
        ).pack(side="left", padx=10, pady=15)

        # ---- Colonna 2: Credito IVA (placeholder) ----
        past_credito_frame = ctk.CTkFrame(past_row_frame)
        past_credito_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 5))

        ctk.CTkLabel(
            past_credito_frame,
            font=self.text_med,
            text=f"{agg_credito:,.2f} €"
        ).pack(padx=5, pady=5, anchor="center", fill="both", expand=True)

        # ---- Colonna 3: Debito IVA (placeholder) ----
        past_debito_frame = ctk.CTkFrame(past_row_frame)
        past_debito_frame.grid(row=0, column=2, sticky="nsew", padx=(0, 5))

        ctk.CTkLabel(
            past_debito_frame,
            font=self.text_med,
            text=f"{agg_debito:,.2f} €"
        ).pack(padx=5, pady=5, anchor="center", fill="both", expand=True)

        # ---- Colonna 4: Saldo da pagare (placeholder) ----
        past_saldo_frame = ctk.CTkFrame(past_row_frame)
        past_saldo_frame.grid(row=0, column=3, sticky="nsew")

        ctk.CTkLabel(
            past_saldo_frame,
            text=f"{agg_saldo:,.2f} €",
            fg_color="#b0b0b0",
            corner_radius=4
        ).pack(padx=5, pady=5, fill="both", expand=True)

        dropdown_btn = ctk.CTkButton(
            past_quarter_frame,
            text=">",
            width=20,
            height=20,
            command=lambda: self.toggle_past_quarter_details()
        )
        dropdown_btn.pack(side="right", padx=15, pady=15)

        past_details_frame = ctk.CTkFrame(past_quarter_container, fg_color="#1a1a1a")
        past_details_frame.pack(fill="x", pady=(0, 5))
        past_details_frame.pack_forget()

        self.populate_past_quarter_details(past_details_frame, per_user_data)

        self.past_details_frame = past_details_frame
        self.past_dropdown_btn = dropdown_btn

    def populate_quarter_details(self, quarter, details_frame, iva_data):
        """Popola il frame dei dettagli con i dati delle singole partite IVA"""
        # Ordina le partite IVA per nome
        sorted_users = sorted(iva_data.keys())

        for user in sorted_users:
            user_data = iva_data[user].get(quarter, {})
            if not user_data:
                continue

            # Frame per la riga dell'utente
            user_row = ctk.CTkFrame(details_frame)
            user_row.pack(fill="x", pady=(0, 2))

            # Configurazione colonne
            for col in range(4):
                user_row.grid_columnconfigure(col, weight=1, uniform="col")

            # Colonna 1: Nome utente (con indentazione)
            user_frame = ctk.CTkFrame(user_row)
            user_frame.grid(row=0, column=0, sticky="nsew", padx=(20, 5))
            ctk.CTkLabel(
                user_frame,
                text=user,
                font=self.text_med
            ).pack(padx=5, pady=2, anchor="center", fill="both", expand=True)

            # Colonna 2: Credito IVA
            credito_frame = ctk.CTkFrame(user_row)
            credito_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 5))
            ctk.CTkLabel(
                credito_frame,
                text=f"{user_data.get('credito', 0):.2f} €",
                font=self.text_med
            ).pack(padx=5, pady=2, anchor="center", fill="both", expand=True)

            # Colonna 3: Debito IVA
            debito_frame = ctk.CTkFrame(user_row)
            debito_frame.grid(row=0, column=2, sticky="nsew", padx=(0, 5))
            ctk.CTkLabel(
                debito_frame,
                text=f"{user_data.get('debito', 0):.2f} €",
                font=self.text_med
            ).pack(padx=5, pady=2, anchor="center", fill="both", expand=True)

            # Colonna 4: Saldo da pagare
            saldo_frame = ctk.CTkFrame(user_row)
            saldo_frame.grid(row=0, column=3, sticky="nsew")

            saldo = user_data.get('da_pagare', 0)
            fg_color = "#f52f2f" if saldo > 0 else "#2ca31c" if saldo < 0 else "#b0b0b0"

            ctk.CTkLabel(
                saldo_frame,
                text=f"{saldo:.2f} €",
                font=self.text_med,
                fg_color=fg_color,
                corner_radius=4
            ).pack(padx=5, pady=2, fill="both", expand=True)

    def populate_past_quarter_details(self, details_frame, per_user_data):
        for user in sorted(per_user_data.keys()):
            data = per_user_data[user]

            user_row = ctk.CTkFrame(details_frame)
            user_row.pack(fill="x", pady=(0, 2))

            for col in range(4):
                user_row.grid_columnconfigure(col, weight=1, uniform="col")

            # Nome utente
            ctk.CTkLabel(
                user_row,
                text=user,
                font=self.text_med
            ).grid(row=0, column=0, padx=(20, 5), sticky="nsew")

            # Credito
            ctk.CTkLabel(
                user_row,
                text=f"{data['credito']:.2f} €",
                font=self.text_med
            ).grid(row=0, column=1, sticky="nsew")

            # Debito
            ctk.CTkLabel(
                user_row,
                text=f"{data['debito']:.2f} €",
                font=self.text_med
            ).grid(row=0, column=2, sticky="nsew")

            saldo = data["da_pagare"]
            fg_color = "#f52f2f" if saldo > 0 else "#2ca31c" if saldo < 0 else "#b0b0b0"

            ctk.CTkLabel(
                user_row,
                text=f"{saldo:.2f} €",
                font=self.text_med,
                fg_color=fg_color,
                corner_radius=4
            ).grid(row=0, column=3, sticky="nsew")

    def add_annual_total_row(self, parent_frame, annual_totals):
        """Aggiunge la riga con i totali annuali"""
        # Separatore prima del totale annuale
        separator = ctk.CTkFrame(parent_frame, height=3, fg_color="#555555")
        separator.pack(fill="x", pady=(10, 10))

        # Frame per la riga annuale
        annual_row = ctk.CTkFrame(parent_frame, border_width=2, border_color="#3773b8")
        annual_row.pack(fill="x", pady=(0, 5))

        # Configurazione colonne
        for col in range(4):
            annual_row.grid_columnconfigure(col, weight=1, uniform="col")

        # Colonna 1: Etichetta
        label_frame = ctk.CTkFrame(annual_row)
        label_frame.grid(row=0, column=0, sticky="nsew", padx=(5, 5), pady=5)
        ctk.CTkLabel(
            label_frame,
            text="TOTALE ANNUALE",
            font=self.header_font
        ).pack(padx=5, pady=5)

        # Colonna 2: Credito totale
        credito_frame = ctk.CTkFrame(annual_row)
        credito_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 5), pady=5)
        ctk.CTkLabel(
            credito_frame,
            text=f"{annual_totals['credito']:.2f} €",
            font=self.header_font
        ).pack(padx=5, pady=5)

        # Colonna 3: Debito totale
        debito_frame = ctk.CTkFrame(annual_row)
        debito_frame.grid(row=0, column=2, sticky="nsew", padx=(5, 5), pady=5)
        ctk.CTkLabel(
            debito_frame,
            text=f"{annual_totals['debito']:.2f} €",
            font=self.header_font
        ).pack(padx=5, pady=5)

        # Colonna 4: Saldo annuale
        saldo_frame = ctk.CTkFrame(annual_row)
        saldo_frame.grid(row=0, column=3, sticky="nsew", padx=(5, 5), pady=5)

        saldo = annual_totals['da_pagare']
        fg_color = "#f52f2f" if saldo > 0 else "#2ca31c" if saldo < 0 else "#b0b0b0"

        ctk.CTkLabel(
            saldo_frame,
            text=f"{saldo:.2f} €",
            font=self.header_font,
            fg_color=fg_color,
            corner_radius=4
        ).pack(padx=5, pady=5, fill="both", expand=True)

    def toggle_quarter_details(self, quarter):
        """Mostra/nasconde i dettagli per un trimestre specifico"""
        details_frame = getattr(self, f"{quarter}_details_frame")
        dropdown_btn = getattr(self, f"{quarter}_dropdown_btn")

        if details_frame.winfo_ismapped():
            details_frame.pack_forget()
            dropdown_btn.configure(text=">")
        else:
            # Mostra i dettagli esattamente sotto la riga del trimestre
            details_frame.pack(fill="x", pady=(0, 5))
            dropdown_btn.configure(text="<")

    def toggle_past_quarter_details(self):
        if self.past_details_frame.winfo_ismapped():
            self.past_details_frame.pack_forget()
            self.past_dropdown_btn.configure(text=">")
        else:
            self.past_details_frame.pack(fill="x", pady=(0, 5))
            self.past_dropdown_btn.configure(text="v")

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

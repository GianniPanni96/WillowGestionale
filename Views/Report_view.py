import customtkinter as ctk
import tkinter.font as tkfont

from datetime import datetime


class ReportView (ctk.CTkFrame):
    def __init__(self, db_model, fiscal_settings, tabview, analyzer, event_bus, update_controller):
        super().__init__(tabview.tab("Report"))

        self.db_model = db_model
        self.update_controller = update_controller
        self.tabview = tabview
        self.tab = tabview.tab("Report")
        self.fiscal_settings = fiscal_settings
        self.analyzer = analyzer
        self.event_bus = event_bus

        # Container principale
        self.main_container = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.main_container.pack(fill='both', expand=True)
        #self.detail_container = ctk.CTkFrame(self, fg_color="#2b2b2b")

        # Inizializza la vista principale

        # Sistema per tracciare gli after()
        self._after_ids = set()
        self._orig_after = self.after
        self.after = self._track_after

        self.create_report_tab()

    def create_report_tab(self):

        monthly_data = self.analyzer.retrieve_monthly_data()

        # Titolo principale
        title_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        title_frame.pack(fill="x", padx=20, pady=(10, 5))

        ctk.CTkLabel(title_frame,
                     text="REPORT MENSILE",
                     font=("Arial", 18, "bold"),
                     text_color="#e8f4f8").pack(side="left")

        ctk.CTkLabel(title_frame,
                     text=f"Anno: {datetime.now().year}",
                     font=("Arial", 12, "italic"),
                     text_color="#7f8c8d").pack(side="right")

        # Frame per le medie
        averages_frame = ctk.CTkFrame(self.main_container, height=40)
        averages_frame.pack(fill="x", padx=20, pady=10)

        # Calcola medie globali
        current_month = datetime.now().month
        passed_months = [m for m in range(1, current_month + 1)]
        totals = {k: 0.0 for k in ['fatturato', 'spese', 'incomes', 'outcomes']}

        for month in passed_months:
            data = monthly_data[month]
            for key in totals:
                totals[key] += data['values'][key]

        averages = {}
        for key in totals:
            averages[key] = totals[key] / len(passed_months) if passed_months else 0.0

        # Mostra medie
        avg_labels = [
            ("Fatturato Medio", averages['fatturato']),
            ("Spese Medie", averages['spese']),
            ("Entrate Medie", averages['incomes']),
            ("Uscite Medie", averages['outcomes'])
        ]

        for i, (text, value) in enumerate(avg_labels):
            frame = ctk.CTkFrame(averages_frame, fg_color="#e8f4f8", corner_radius=8)
            frame.grid(row=0, column=i, padx=5, pady=5)

            ctk.CTkLabel(frame, text=text,
                         font=("Arial", 13),
                         text_color="#2c3e50").pack(padx=10, pady=(5, 0))

            ctk.CTkLabel(frame, text=f"{value:.2f} €",
                         font=("Arial", 15, "bold"),
                         text_color="#2980b9").pack(padx=10, pady=(0, 5))

        # Tabella principale
        table_container = ctk.CTkFrame(self.main_container, fg_color="transparent")
        table_container.pack(fill="both", expand=True, padx=20, pady=5)

        # Intestazioni tabella
        headers = ["Mese", "Fatturato", "Spese", "Entrate", "Uscite"]
        header_frame = ctk.CTkFrame(table_container, height=40)
        header_frame.pack(fill="x", pady=(0, 5))

        # ------ Calcolo dinamico larghezze colonne (misura i testi) ------
        # Font usati (stessa scelta che userai per i widget)
        header_font = tkfont.Font(font=("Arial", 16, "bold"))
        data_font = tkfont.Font(font=("Arial", 13))

        month_names = ["", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
                       "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]

        # Costruisci liste di testi per ogni colonna (header + valori)
        columns_texts = [[] for _ in headers]

        # Colonna 0 = mesi
        columns_texts[0].append(headers[0])
        for m in range(1, 13):
            columns_texts[0].append(month_names[m])

        # Colonne numeriche: crea stringhe formattate per ogni mese
        for col_index, metric in enumerate(['fatturato', 'spese', 'incomes', 'outcomes'], start=1):
            columns_texts[col_index].append(headers[col_index])
            for m in range(1, 13):
                v = monthly_data[m]['values'][metric]
                columns_texts[col_index].append(f"{v:.2f} €")

        # Misura larghezza massima per colonna (px). Usiamo header_font per l'header e data_font per i valori.
        column_width = (self.winfo_screenwidth()-100)/5
        column_widths = [column_width, column_width, column_width, column_width, column_width]

        # ---------- Applicazione dello scale factor ----------
        scale = 0.97  # 1.0 = uguale, >1 = più larga, <1 = più stretta
        min_width = 40  # evita colonne ridicolmente strette
        column_widths = [max(min_width, int(w * scale)) for w in column_widths]
        # -----------------------------------------------------

        # ----------------------------------------------------------------

        # Crea header impostando la larghezza calcolata
        for i, header in enumerate(headers):
            bg_color = "#1a5276" if i == 0 else "#2874a6"
            width = column_widths[i]

            header_label = ctk.CTkLabel(
                header_frame,
                text=header,
                width=width,
                height=40,
                corner_radius=2,
                fg_color=bg_color,
                text_color="white",
                font=("Arial", 16, "bold")
            )
            header_label.grid(row=0, column=i, padx=(0, 10) if i < len(headers) - 1 else 0, sticky="ew")

        # Dati tabella (scrollable frame)
        scroll_frame = ctk.CTkScrollableFrame(table_container)
        scroll_frame.pack(fill="both", expand=True)

        # Variabile per tracciare lo stato di espansione
        self.expanded_states = {month: False for month in range(1, 13)}

        # Per mantenere lo stile riga, mantengo row_frame per ogni riga ma imposto le width dei widget
        for month in range(1, 13):
            data = monthly_data[month]
            is_current = month == datetime.now().month

            # Frame principale riga (mantieni il colore di sfondo per la riga)
            row_frame = ctk.CTkFrame(scroll_frame,
                                     fg_color="#2c3e50" if datetime.now().month >= month else "transparent")
            if month == datetime.today().month:
                row_frame.configure(border_width=2, border_color="blue")
            row_frame.pack(fill="both", pady=(0, 4))

            # Colonna Mese
            month_label = ctk.CTkLabel(
                row_frame,
                text=month_names[month],
                width=column_widths[0]-20,
                anchor="w",
                font=("Arial", 16, "bold" if is_current else "normal"),
                text_color="white" if is_current else "#ecf0f1",
                fg_color="transparent"
            )
            month_label.grid(row=0, column=0, pady=9, padx=10)

            # Colonne dati (usa le width calcolate)
            metrics = ['fatturato', 'spese', 'incomes', 'outcomes']
            for col, metric in enumerate(metrics, start=1):
                value = data['values'][metric]
                value_label = ctk.CTkLabel(
                    row_frame,
                    text=f"{value:.2f} €",
                    width=column_widths[col],
                    anchor="e",
                    font=("Arial", 15, "bold" if is_current else "normal"),
                    text_color="white" if datetime.now().month >= month else "gray",
                    fg_color="transparent"
                )
                value_label.grid(row=0, column=col, pady=9, padx=(0, 10), sticky="e")

        # Footer
        footer_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        footer_frame.pack(fill="x", padx=20, pady=(5, 10))

        ctk.CTkLabel(footer_frame,
                     text="* Dati aggiornati al: " + datetime.now().strftime("%d/%m/%Y") + "\nFatturato e Spese esenti IVA",
                     font=("Arial", 10),
                     text_color="#7f8c8d").pack(side="left")

    def toggle_details(self, month):
        return

    def format_deviation(self, dev):
        if dev is None:
            return "N/A"
        if dev == float('inf'):
            return "∞"
        color = "#e74c3c" if dev < 0 else "#27ae60"
        prefix = "+" if dev > 0 else ""
        return f"{prefix}{dev:.2f}%"

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

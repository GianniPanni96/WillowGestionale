import customtkinter as ctk
import tkinter.font as tkfont
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
from datetime import datetime
import os, re

from customtkinter import CTkFrame

from Views.View_utils import ViewUtils

from Controllers import AccountController, ValidationUtils, UserController
from Model import DBUsersColumns, DBAccountsColumns, DBInvoicesColumns, DBExpensesColumns, DBProductionsColumns, \
    DBSalariesColumns


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
        column_width = (1920-100)/5
        column_widths = [column_width, column_width, column_width, column_width, column_width]
        """horizontal_padding_px = 24  # margine interno/padding aggiuntivo (regolabile)

        for idx, texts in enumerate(columns_texts):
            header_w = header_font.measure(texts[0])
            data_w = max((data_font.measure(t) for t in texts[1:]), default=0)
            max_w = max(header_w, data_w)
            column_widths.append(int(max_w + horizontal_padding_px))"""

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
                     text="* Dati aggiornati al: " + datetime.now().strftime("%d/%m/%Y"),
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

import customtkinter as ctk
import tkinter as tk
from tkcalendar import Calendar, DateEntry
from Views.View_utils import ViewUtils
from Controllers import ValidationUtils, InvoiceController, UserController, ControllerUtils
from Model import DBInvoicesColumns, DBUsersColumns, DBClientsColumns, DBProductionsColumns, DBPaymentsColumns, DBAccountsColumns, DBExpensesColumns
from datetime import datetime
import re
from enum import Enum


class IvaTrimesView(ctk.CTkFrame):
    def __init__(self, db_model, invoice_controller, user_controller, expense_controller, update_controller, analyzer, tabview, event_bus):
        super().__init__(tabview.tab("Iva"))

        self.db_model = db_model
        self.invoice_controller = invoice_controller
        self.user_controller = user_controller
        self.expense_controller = expense_controller
        self.update_controller = update_controller
        self.analyzer = analyzer
        self.tabview = tabview
        self.tab = tabview.tab("Iva")
        self.event_bus = event_bus

        self.header_font = ("Arial", 14)
        self.text_large = ("Arial", 14)
        self.text_med = ("Arial", 14)

        # Container principale
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Inizializza la vista principale
        self.create_iva_trimes_tab()

    def create_iva_trimes_tab(self):
        # Creazione frame principale
        tab_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        tab_frame.pack(fill="both", expand=True, pady=0, padx=(10, 0), ipady=20, side="left")

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
            ).pack(padx=5, pady=5)

            # Colonna 3: Debito IVA
            debito_frame = ctk.CTkFrame(row_frame)
            debito_frame.grid(row=0, column=2, sticky="nsew", padx=(0, 5))
            ctk.CTkLabel(
                debito_frame,
                font=self.text_med,
                text=f"{data['debito']:.2f} €"
            ).pack(padx=5, pady=5, anchor="center")

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
            ).pack(padx=5, pady=2)

            # Colonna 2: Credito IVA
            credito_frame = ctk.CTkFrame(user_row)
            credito_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 5))
            ctk.CTkLabel(
                credito_frame,
                text=f"{user_data.get('credito', 0):.2f} €",
                font=self.text_med
            ).pack(padx=5, pady=2)

            # Colonna 3: Debito IVA
            debito_frame = ctk.CTkFrame(user_row)
            debito_frame.grid(row=0, column=2, sticky="nsew", padx=(0, 5))
            ctk.CTkLabel(
                debito_frame,
                text=f"{user_data.get('debito', 0):.2f} €",
                font=self.text_med
            ).pack(padx=5, pady=2)

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

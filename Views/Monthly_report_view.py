import customtkinter as ctk
from datetime import datetime

from AnalyzerServices.Monthly_report_analyzer_service import MonthlyReportAnalyzerService
from App_context import AppContext


class MonthlyReportView(ctk.CTkFrame):
    def __init__(self, app_context: AppContext, parent):
        super().__init__(parent)

        self.app_context = app_context
        self.monthly_report_analyzer_service: MonthlyReportAnalyzerService = (
            app_context.monthly_report_analyzer_service
        )

        self.main_container = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.main_container.pack(fill="both", expand=True)

        self._build_view()

    def _build_view(self):
        monthly_data = self.monthly_report_analyzer_service.retrieve_monthly_data()
        averages = self._extract_averages(monthly_data)

        title_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        title_frame.pack(fill="x", padx=20, pady=(10, 5))

        ctk.CTkLabel(
            title_frame,
            text="REPORT MENSILE",
            font=("Arial", 18, "bold"),
            text_color="#e8f4f8",
        ).pack(side="left")

        ctk.CTkLabel(
            title_frame,
            text=f"Anno: {datetime.now().year}",
            font=("Arial", 12, "italic"),
            text_color="#7f8c8d",
        ).pack(side="right")

        self._build_averages_cards(averages)
        self._build_monthly_table(monthly_data)

        footer_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        footer_frame.pack(fill="x", padx=20, pady=(5, 10))

        ctk.CTkLabel(
            footer_frame,
            text=(
                "* Dati aggiornati al: "
                + datetime.now().strftime("%d/%m/%Y")
                + "\nFatturato e Spese esenti IVA"
            ),
            font=("Arial", 10),
            text_color="#7f8c8d",
        ).pack(side="left")

    def _build_averages_cards(self, averages: dict):
        averages_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        averages_frame.pack(fill="x", padx=20, pady=10)

        labels = [
            ("Fatturato Medio", averages["fatturato"]),
            ("Spese Medie", averages["spese"]),
            ("Entrate Medie", averages["incomes"]),
            ("Uscite Medie", averages["outcomes"]),
        ]

        for column_index in range(len(labels)):
            averages_frame.grid_columnconfigure(column_index, weight=1, uniform="avg-card")

        for index, (text, value) in enumerate(labels):
            card = ctk.CTkFrame(
                averages_frame,
                fg_color="#e8f4f8",
                corner_radius=10,
            )
            card.grid(row=0, column=index, padx=6, pady=5, sticky="ew")

            ctk.CTkLabel(
                card,
                text=text,
                font=("Arial", 13),
                text_color="#2c3e50",
            ).pack(padx=10, pady=(8, 2))

            ctk.CTkLabel(
                card,
                text=f"{value:.2f} €",
                font=("Arial", 16, "bold"),
                text_color="#1f6aa5",
            ).pack(padx=10, pady=(0, 8))

    def _build_monthly_table(self, monthly_data: dict):
        table_container = ctk.CTkFrame(self.main_container, fg_color="transparent")
        table_container.pack(fill="both", expand=True, padx=20, pady=5)

        headers = ["Mese", "Fatturato", "Spese", "Entrate", "Uscite"]
        header_frame = ctk.CTkFrame(table_container, height=40)
        header_frame.pack(fill="x", pady=(0, 5))

        column_width = max(40, int((self.winfo_screenwidth() - 100) / 5 * 0.97))
        column_widths = [column_width] * len(headers)

        for index, header in enumerate(headers):
            header_label = ctk.CTkLabel(
                header_frame,
                text=header,
                width=column_widths[index],
                height=40,
                corner_radius=2,
                fg_color="#1a5276" if index == 0 else "#2874a6",
                text_color="white",
                font=("Arial", 16, "bold"),
            )
            header_label.grid(
                row=0,
                column=index,
                padx=(0, 10) if index < len(headers) - 1 else 0,
                sticky="ew",
            )

        scroll_frame = ctk.CTkScrollableFrame(table_container)
        scroll_frame.pack(fill="both", expand=True)

        month_names = [
            "",
            "Gennaio",
            "Febbraio",
            "Marzo",
            "Aprile",
            "Maggio",
            "Giugno",
            "Luglio",
            "Agosto",
            "Settembre",
            "Ottobre",
            "Novembre",
            "Dicembre",
        ]

        for month in range(1, 13):
            data = monthly_data[month]
            is_current_month = month == datetime.now().month
            has_started = datetime.now().month >= month

            row_frame = ctk.CTkFrame(
                scroll_frame,
                fg_color="#2c3e50" if has_started else "transparent",
            )
            if is_current_month:
                row_frame.configure(border_width=2, border_color="#1f6aa5")
            row_frame.pack(fill="both", pady=(0, 4))

            ctk.CTkLabel(
                row_frame,
                text=month_names[month],
                width=column_widths[0] - 20,
                anchor="w",
                font=("Arial", 16, "bold" if is_current_month else "normal"),
                text_color="white" if is_current_month else "#ecf0f1",
                fg_color="transparent",
            ).grid(row=0, column=0, pady=9, padx=10)

            for column_index, metric in enumerate(["fatturato", "spese", "incomes", "outcomes"], start=1):
                value = data["values"][metric]
                ctk.CTkLabel(
                    row_frame,
                    text=f"{value:.2f} €",
                    width=column_widths[column_index],
                    anchor="e",
                    font=("Arial", 15, "bold" if is_current_month else "normal"),
                    text_color="white" if has_started else "gray",
                    fg_color="transparent",
                ).grid(row=0, column=column_index, pady=9, padx=0, sticky="e")

    @staticmethod
    def _extract_averages(monthly_data: dict) -> dict:
        sample_month = monthly_data.get(1, {})
        return sample_month.get(
            "averages",
            {"fatturato": 0.0, "spese": 0.0, "incomes": 0.0, "outcomes": 0.0},
        )

    def cleanup(self):
        try:
            if hasattr(self, "main_container") and self.main_container.winfo_exists():
                for widget in self.main_container.winfo_children():
                    widget.destroy()
        except Exception as exc:
            print(f"Errore durante il cleanup di {self.__class__.__name__}: {exc}")

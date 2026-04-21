import customtkinter as ctk
from datetime import datetime
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

from AnalyzerServices.Report_breakdown_analyzer_service import ReportBreakdownAnalyzerService
from App_context import AppContext
from Views.View_utils import ViewUtils


class AnnualReportChartsView(ctk.CTkFrame):
    PIE_COLORS = [
        "#45b7d1",
        "#4ecdc4",
        "#f7b267",
        "#f25f5c",
        "#7d8cc4",
        "#a1c181",
        "#f79d65",
        "#c77dff",
    ]

    def __init__(self, app_context: AppContext, parent):
        super().__init__(parent)

        self.app_context = app_context
        self.report_breakdown_analyzer_service: ReportBreakdownAnalyzerService = app_context.report_breakdown_analyzer_service
        self.chart_canvases = []
        self.figures = []

        self.main_container = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.main_container.pack(fill="both", expand=True)
        self.selected_year = datetime.today().year

        self.year_list = [str(y) for y in range(2023, datetime.today().year + 1)] + ["All Time"]

        self.year_selector_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.year_selector_frame.pack(fill="x")

        ctk.CTkLabel(
            self.year_selector_frame,
            text="Seleziona un anno da analizzare: "
        ).pack(padx=10, pady=10, side="left")

        self.year_selector = ctk.CTkOptionMenu(
            self.year_selector_frame,
            values=self.year_list,
            command=self._on_year_selection,
            height=20
        )
        self.year_selector.pack(padx=10, pady=10, side="left")
        self.year_selector.set(str(datetime.today().year))

        self.scroll_frame = ctk.CTkScrollableFrame(
            self.main_container,
            fg_color="transparent",
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=5, pady=(0, 20))

        self._build_view()

    def _on_year_selection(self, selected_value):
        if selected_value == "All Time":
            self.selected_year = -1
        else:
            self.selected_year = int(selected_value)

        self._update_view()

    def _update_view(self):
        for canvas in self.chart_canvases:
            try:
                canvas.get_tk_widget().destroy()
            except Exception:
                pass

        for figure in self.figures:
            try:
                plt.close(figure)
            except Exception:
                pass

        self.chart_canvases.clear()
        self.figures.clear()

        try:
            if hasattr(self, "scroll_frame") and self.scroll_frame.winfo_exists():
                for widget in self.scroll_frame.winfo_children():
                    widget.destroy()
        except Exception as exc:
            print(f"Errore durante il cleanup di {self.__class__.__name__}: {exc}")

        self._build_view()

    def _build_view(self):
        breakdown_data = self.report_breakdown_analyzer_service.retrieve_annual_breakdown_data(year=self.selected_year)

        self._build_financial_charts_section(
            parent=self.scroll_frame,
            data=breakdown_data["financial"]
        )

        self._build_section(
            parent=self.scroll_frame,
            title="SEZIONE FATTURATO",
            subtitle=f"Distribuzioni percentuali del fatturato - {self.year_selector.get()}.",
            charts=[
                (
                    "Per tipologia di produzione associata",
                    breakdown_data["revenue"]["by_production_type"],
                ),
                (
                    "Per tipologia di output associata",
                    breakdown_data["revenue"]["by_output_type"],
                ),
                (
                    "Per settore del cliente associato",
                    breakdown_data["revenue"]["by_client_sector"],
                ),
            ],
        )

        # Recuperiamo la soglia fiscale per il goal (1 - imponibile)
        imponibile = float(self.app_context.fiscal_settings.partita_iva_forfettaria.imponibile)
        soglia_spese_max_pct = round((1 - imponibile) * 100, 1)

        self._build_section(
            parent=self.scroll_frame,
            title="SEZIONE SPESE",
            subtitle=f"Distribuzioni percentuali del totale speso - {self.year_selector.get()}",
            charts=[
                (f"Spese vs Fatturato (Goal: < {soglia_spese_max_pct}%)", breakdown_data["expense_vs_revenue"]),
                ("Deducibile vs non deducibile", breakdown_data["expenses"]["by_deductibility"]),
                ("Per categoria di spesa", breakdown_data["expenses"]["by_category"]),
                ("Per fornitore", breakdown_data["expenses"]["by_supplier"])
            ],
            cols=4 # Aumentiamo le colonne a 4 per far spazio al nuovo chart
        )

    def _build_section(self, parent, title: str, subtitle: str, charts: list[tuple[str, list[dict]]], cols: int = 3):
        is_scrollable = cols > 3
        minsize = 580
        section_frame = ctk.CTkFrame(parent, fg_color="#23313f", corner_radius=16) if not is_scrollable else ctk.CTkScrollableFrame(parent, fg_color="#23313f", corner_radius=16, orientation="horizontal", height=550)
        section_frame.pack(fill="x", pady=(10, 16))

        ctk.CTkLabel(
            section_frame,
            text=title,
            font=("Arial", 18, "bold"),
            text_color="#e8f4f8",
        ).pack(anchor="w", padx=20, pady=(16, 4))

        ctk.CTkLabel(
            section_frame,
            text=subtitle,
            font=("Arial", 12),
            text_color="#9fb3c8",
        ).pack(anchor="w", padx=20, pady=(0, 12))

        charts_grid = ctk.CTkFrame(section_frame, fg_color="transparent")
        if is_scrollable:
            charts_grid.pack(padx=14, pady=(0, 16))
        else:
            charts_grid.pack(fill="x", padx=14, pady=(0, 16))

        for index in range(cols):
            charts_grid.grid_columnconfigure(
                index,
                weight=1,
                uniform="report-chart",
                minsize=minsize
            )

        for index, (chart_title, items) in enumerate(charts):
            card = ctk.CTkFrame(
                charts_grid,
                fg_color="#2f4253",
                corner_radius=14,
                width=minsize
            )
            card.grid(row=0, column=index, padx=8, pady=8, sticky="nsew")

            # Evidenzia il goal se superato (titolo rosso se soglia superata)
            title_color = "#e8f4f8"
            if "Goal:" in chart_title:
                try:
                    # Estraiamo la percentuale attuale dalle items
                    spese = items[0]["value"] if items else 0
                    restante = items[1]["value"] if len(items) > 1 else 0
                    totale = spese + restante
                    pct_attuale = (spese / totale * 100) if totale > 0 else 0

                    # Estraiamo la soglia dal titolo tramite regex o split
                    soglia = float(chart_title.split("< ")[1].split("%")[0])

                    if pct_attuale > soglia:
                        title_color = "#f25f5c" # Rosso errore
                except:
                    pass

            ctk.CTkLabel(
                card,
                text=chart_title,
                font=("Arial", 14, "bold"),
                text_color=title_color,
                wraplength=280,
                justify="left",
            ).pack(anchor="w", padx=16, pady=(14, 8))

            self._render_chart(card, items)

    def _build_financial_charts_section(self, parent, data: dict):
        section_frame = ctk.CTkFrame(parent, fg_color="#23313f", corner_radius=16)
        section_frame.pack(fill="x", pady=(10, 16))

        ctk.CTkLabel(
            section_frame,
            text="ANALISI FINANZIARIA",
            font=("Arial", 18, "bold"),
            text_color="#e8f4f8",
        ).pack(anchor="w", padx=20, pady=(16, 4))

        ctk.CTkLabel(
            section_frame,
            text=f"Distribuzioni di Patrimonio, Entrate e Uscite - {self.year_selector.get()}",
            font=("Arial", 12),
            text_color="#9fb3c8",
        ).pack(anchor="w", padx=20, pady=(0, 12))

        charts_grid = ctk.CTkFrame(section_frame, fg_color="transparent")
        charts_grid.pack(fill="x", padx=14, pady=(0, 16))

        for index in range(3):
            charts_grid.grid_columnconfigure(index, weight=1, uniform="fin-chart")

        financial_sections = [
            ("SEZIONE PATRIMONIO", data["patrimonio"]),
            ("SEZIONE ENTRATE", data["entrate"]),
            ("SEZIONE USCITE", data["uscite"]),
        ]

        for index, (chart_title, items) in enumerate(financial_sections):
            card = ctk.CTkFrame(charts_grid, fg_color="#2f4253", corner_radius=14)
            card.grid(row=0, column=index, padx=8, pady=8, sticky="nsew")

            ctk.CTkLabel(
                card,
                text=chart_title,
                font=("Arial", 14, "bold"),
                text_color="#e8f4f8",
                wraplength=280,
                justify="left",
            ).pack(anchor="w", padx=16, pady=(14, 8))

            # Controllo per la sezione Patrimonio: mostriamo il grafico solo per l'anno corrente
            if chart_title == "SEZIONE PATRIMONIO" and self.selected_year != datetime.today().year:
                ctk.CTkLabel(
                    card,
                    text="La suddivisione del patrimonio tra i conti è visualizzabile solo selezionando l'anno corrente, poiché rappresenta i saldi attuali in tempo reale.",
                    font=("Arial", 12),
                    text_color="#9fb3c8",
                    wraplength=250,
                    justify="center",
                ).pack(fill="both", expand=True, padx=20, pady=(20, 30))
            else:
                self._render_chart(card, items)

    def _render_chart(self, parent, items: list[dict]):
        compact_items = self._compact_items(items, max_items=6)

        if not compact_items:
            ctk.CTkLabel(
                parent,
                text="Nessun dato disponibile per il periodo selezionato.",
                font=("Arial", 12),
                text_color="#9fb3c8",
                wraplength=280,
                justify="left",
            ).pack(fill="x", padx=16, pady=(20, 24))
            return

        labels = [item["label"] for item in compact_items]
        values = [item["value"] for item in compact_items]
        colors = self.PIE_COLORS[: len(values)]

        figure = plt.Figure(figsize=(4.3, 3.6), facecolor="#2f4253")
        axis = figure.add_subplot(111)
        axis.set_facecolor("#2f4253")

        wedges, _, autotexts = axis.pie(
            values,
            colors=colors,
            startangle=90,
            autopct=lambda pct: f"{pct:.1f}%" if pct >= 5 else "",
            pctdistance=0.72,
            wedgeprops={"linewidth": 1.0, "edgecolor": "#2f4253"},
            textprops={"color": "#e8f4f8", "fontsize": 9},
        )

        for autotext in autotexts:
            autotext.set_color("#f8fafc")
            autotext.set_fontsize(9)
            autotext.set_weight("bold")

        axis.axis("equal")
        axis.legend(
            wedges,
            [f"{ViewUtils.split_string_by_length(label, 24)}" for label in labels],
            loc="center left",
            bbox_to_anchor=(0.9, 0.8),
            frameon=False,
            labelcolor="#d7e3f0",
            fontsize=9,
        )

        figure.subplots_adjust(left=-0.05, right=0.68, top=0.95, bottom=0.06)

        canvas = FigureCanvasTkAgg(figure, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.figures.append(figure)
        self.chart_canvases.append(canvas)

        # Tooltip manuale
        annotation = axis.annotate(
            "",
            xy=(0, 0),
            xytext=(10, 10),
            textcoords="offset points",
            bbox=dict(boxstyle="round", fc="#2b2b2b", ec="white", alpha=0.9),
            color="white",
            fontsize=9,
        )
        annotation.set_visible(False)

        current_wedge = {"index": None}

        def on_motion(event):
            if event.inaxes != axis:
                # reset tutto quando esci dal grafico
                for w in wedges:
                    w.set_alpha(1.0)
                annotation.set_visible(False)
                current_wedge["index"] = None
                canvas.draw_idle()
                return

            for i, wedge in enumerate(wedges):
                contains, _ = wedge.contains(event)
                if contains:
                    # reset precedente (se diversa)
                    if current_wedge["index"] is not None and current_wedge["index"] != i:
                        wedges[current_wedge["index"]].set_alpha(1.0)

                    current_wedge["index"] = i

                    value = values[i]
                    label = labels[i]
                    total = sum(values)
                    pct = (value / total) * 100

                    wedge.set_alpha(0.7)

                    annotation.xy = (event.xdata, event.ydata)
                    annotation.set_text(f"{label}\n{value:.2f} € ({pct:.1f}%)")
                    annotation.set_visible(True)
                    canvas.draw_idle()
                    return

            # Se non sei sopra nessuna fetta
            for w in wedges:
                w.set_alpha(1.0)

            current_wedge["index"] = None
            annotation.set_visible(False)
            canvas.draw_idle()

        # collega evento
        canvas.mpl_connect("motion_notify_event", on_motion)


    @staticmethod
    def _compact_items(items: list[dict], max_items: int) -> list[dict]:
        if len(items) <= max_items:
            return items

        visible_items = items[: max_items - 1]
        remaining_total = sum(item["value"] for item in items[max_items - 1 :])
        visible_items.append({"label": "Altro", "value": round(remaining_total, 2)})
        return visible_items

    def cleanup(self):
        for canvas in self.chart_canvases:
            try:
                canvas.get_tk_widget().destroy()
            except Exception:
                pass

        for figure in self.figures:
            try:
                plt.close(figure)
            except Exception:
                pass

        self.chart_canvases.clear()
        self.figures.clear()

        try:
            if hasattr(self, "main_container") and self.main_container.winfo_exists():
                for widget in self.main_container.winfo_children():
                    widget.destroy()
        except Exception as exc:
            print(f"Errore durante il cleanup di {self.__class__.__name__}: {exc}")

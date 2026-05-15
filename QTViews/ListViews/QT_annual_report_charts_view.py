"""
Sottoview "Analisi Annuale" del report, versione Qt.

Replica ``Views/Annual_report_charts_view.py`` (legacy CustomTkinter):
- selettore anno (combo) in alto con tutti gli anni dal 2023 ad oggi
  piu' la voce "All Time";
- sezione "ANALISI FLUSSI" (3 grafici: Patrimonio, Entrate, Uscite);
- sezione "SEZIONE FATTURATO" (4 grafici a torta, scrollabile
  orizzontalmente);
- sezione "SEZIONE SPESE" (4 grafici a torta, scrollabile
  orizzontalmente) con un primo grafico "Spese vs Fatturato (Goal:
  < X%)" il cui titolo diventa rosso se la soglia e' superata.

I grafici sono ``matplotlib`` come nella legacy, ma con il backend Qt
(``FigureCanvasQTAgg``). E' replicato anche il tooltip manuale che si
attiva al passaggio del mouse su una fetta della torta.

Per la "SEZIONE PATRIMONIO" se l'anno selezionato non e' quello
corrente, mostriamo lo stesso disclaimer della legacy: la suddivisione
del patrimonio fra i conti rappresenta i saldi attuali in tempo reale,
non un dato storico.
"""

from datetime import datetime
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from Views.View_utils import ViewUtils

if TYPE_CHECKING:
    from App_context import AppContext


PIE_COLORS = [
    "#45b7d1",
    "#7d8cc4",
    "#4ecdc4",
    "#f7b267",
    "#f25f5c",
    "#a1c181",
    "#f79d65",
    "#c77dff",
]

SECTION_BG = "#23313f"
CARD_BG = "#2f4253"
TITLE_FG = "#e8f4f8"
SUBTLE_FG = "#9fb3c8"
ERROR_FG = "#f25f5c"


class QTAnnualReportChartsViewH(QWidget):
    """Grafici a torta annuali (matplotlib + Qt backend)."""

    CHART_MIN_WIDTH = 480
    CHART_FIG_SIZE = (4.3, 3.6)

    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.report_breakdown_analyzer_service = app_context.report_breakdown_analyzer_service

        # Lista delle figures e dei canvas attivi, per cleanup ordinato.
        self._figures: list = []
        self._canvases: list = []

        self.selected_year: int = datetime.today().year
        self.year_list: list[str] = (
            [str(y) for y in range(2023, datetime.today().year + 1)] + ["All Time"]
        )

        self._build_ui()
        self._build_content()

    # ------------------------------------------------------------------
    # UI base
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Barra del selettore anno (sempre visibile).
        selector_frame = QFrame()
        sl = QHBoxLayout(selector_frame)
        sl.setContentsMargins(15, 10, 15, 10)
        sl.setSpacing(10)
        sl.addWidget(QLabel("Seleziona un anno da analizzare:"))

        self.year_selector = QComboBox()
        self.year_selector.addItems(self.year_list)
        self.year_selector.setCurrentText(str(datetime.today().year))
        self.year_selector.currentTextChanged.connect(self._on_year_selection)
        sl.addWidget(self.year_selector)
        sl.addStretch(1)
        root.addWidget(selector_frame)

        # Area scrollabile per le sezioni.
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        root.addWidget(self.scroll, stretch=1)

        self.content = QWidget()
        self.scroll.setWidget(self.content)
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(15, 10, 15, 20)
        self.content_layout.setSpacing(15)

    # ------------------------------------------------------------------
    # Pipeline dati
    # ------------------------------------------------------------------

    def _on_year_selection(self, selected_value: str):
        self.selected_year = -1 if selected_value == "All Time" else int(selected_value)
        self._rebuild_content()

    def _rebuild_content(self):
        self._cleanup_figures()
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._build_content()

    def _build_content(self):
        try:
            breakdown_data = self.report_breakdown_analyzer_service.retrieve_annual_breakdown_data(
                year=self.selected_year
            )
        except Exception as exc:
            print(f"Errore nel recupero dei dati annuali: {exc}")
            breakdown_data = {}

        self.content_layout.addWidget(self._build_financial_charts_section(breakdown_data.get("financial", {})))

        revenue = breakdown_data.get("revenue", {}) or {}
        self.content_layout.addWidget(
            self._build_section(
                title="SEZIONE FATTURATO",
                subtitle=f"Distribuzioni percentuali del fatturato - {self.year_selector.currentText()}.",
                charts=[
                    ("Per tipologia di produzione associata", revenue.get("by_production_type", [])),
                    ("Per tipologia di output associata", revenue.get("by_output_type", [])),
                    ("Per settore del cliente associato", revenue.get("by_client_sector", [])),
                    ("Crediti VS incassato", revenue.get("credits_vs_cached", [])),
                ],
                horizontal_scroll=True,
            )
        )

        # Soglia spese forfettario per goal del primo grafico.
        try:
            imponibile = float(self.app_context.fiscal_settings.partita_iva_forfettaria.imponibile)
        except Exception:
            imponibile = 1.0
        soglia_spese_max_pct = round((1 - imponibile) * 100, 1)

        expenses = breakdown_data.get("expenses", {}) or {}
        self.content_layout.addWidget(
            self._build_section(
                title="SEZIONE SPESE",
                subtitle=f"Distribuzioni percentuali del totale speso - {self.year_selector.currentText()}",
                charts=[
                    (
                        f"Spese vs Fatturato (Goal: < {soglia_spese_max_pct}%)",
                        breakdown_data.get("expense_vs_revenue", []),
                    ),
                    ("Deducibile vs non deducibile", expenses.get("by_deductibility", [])),
                    ("Per categoria di spesa", expenses.get("by_category", [])),
                    ("Per fornitore", expenses.get("by_supplier", [])),
                ],
                horizontal_scroll=True,
            )
        )

        self.content_layout.addStretch(1)

    # ------------------------------------------------------------------
    # Sezioni
    # ------------------------------------------------------------------

    def _build_financial_charts_section(self, data: dict) -> QWidget:
        wrapper = self._make_section_frame("ANALISI FLUSSI",
            f"Distribuzioni di Patrimonio, Entrate e Uscite - {self.year_selector.currentText()}",
        )
        v = wrapper.layout()

        grid_host = QFrame()
        grid_host.setStyleSheet("background-color: transparent;")
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)

        financial_sections = [
            ("SEZIONE PATRIMONIO", data.get("patrimonio", [])),
            ("SEZIONE ENTRATE", data.get("entrate", [])),
            ("SEZIONE USCITE", data.get("uscite", [])),
        ]

        for index, (chart_title, items) in enumerate(financial_sections):
            grid.setColumnStretch(index, 1)
            grid.addWidget(self._make_chart_card(chart_title, items), 0, index)

        v.addWidget(grid_host)
        return wrapper

    def _build_section(
        self,
        title: str,
        subtitle: str,
        charts: list[tuple[str, list]],
        horizontal_scroll: bool = False,
    ) -> QWidget:
        wrapper = self._make_section_frame(title, subtitle)
        v = wrapper.layout()

        host = QFrame()
        host.setStyleSheet("background-color: transparent;")
        grid = QGridLayout(host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)

        for index, (chart_title, items) in enumerate(charts):
            grid.setColumnStretch(index, 1)
            card = self._make_chart_card(chart_title, items)
            card.setMinimumWidth(self.CHART_MIN_WIDTH)
            grid.addWidget(card, 0, index)

        if horizontal_scroll:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setStyleSheet("QScrollArea { background-color: transparent; }")
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll.setMinimumHeight(560)
            scroll.setWidget(host)
            v.addWidget(scroll)
        else:
            v.addWidget(host)
        return wrapper

    def _make_section_frame(self, title: str, subtitle: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("ReportSection")
        frame.setStyleSheet(
            f"#ReportSection {{ background-color: {SECTION_BG};"
            " border-radius: 16px; }"
        )
        v = QVBoxLayout(frame)
        v.setContentsMargins(20, 14, 20, 14)
        v.setSpacing(6)

        title_lbl = QLabel(title)
        tf = title_lbl.font()
        tf.setBold(True)
        tf.setPointSize(15)
        title_lbl.setFont(tf)
        title_lbl.setStyleSheet(f"color: {TITLE_FG};")
        v.addWidget(title_lbl)

        sub_lbl = QLabel(subtitle)
        sub_lbl.setStyleSheet(f"color: {SUBTLE_FG};")
        sub_lbl.setWordWrap(True)
        v.addWidget(sub_lbl)

        return frame

    # ------------------------------------------------------------------
    # Card del grafico
    # ------------------------------------------------------------------

    def _make_chart_card(self, chart_title: str, items: list) -> QFrame:
        card = QFrame()
        card.setObjectName("ReportChartCard")
        card.setStyleSheet(
            f"#ReportChartCard {{ background-color: {CARD_BG};"
            " border-radius: 14px; }"
        )
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 12, 14, 10)
        v.setSpacing(6)

        # Goal check: titolo rosso se la soglia e' superata.
        title_color = TITLE_FG
        if "Goal:" in chart_title:
            try:
                spese = items[0]["value"] if items else 0
                restante = items[1]["value"] if len(items) > 1 else 0
                totale = spese + restante
                pct_attuale = (spese / totale * 100) if totale > 0 else 0
                soglia = float(chart_title.split("< ")[1].split("%")[0])
                if pct_attuale > soglia:
                    title_color = ERROR_FG
            except Exception:
                pass

        title_lbl = QLabel(chart_title)
        title_lbl.setWordWrap(True)
        tf = title_lbl.font()
        tf.setBold(True)
        tf.setPointSize(12)
        title_lbl.setFont(tf)
        title_lbl.setStyleSheet(f"color: {title_color};")
        v.addWidget(title_lbl)

        # Caso speciale del patrimonio: messaggio se anno != corrente.
        if chart_title == "SEZIONE PATRIMONIO" and self.selected_year != datetime.today().year:
            note = QLabel(
                "La suddivisione del patrimonio tra i conti è visualizzabile "
                "solo selezionando l'anno corrente, poiché rappresenta i saldi "
                "attuali in tempo reale."
            )
            note.setWordWrap(True)
            note.setAlignment(Qt.AlignCenter)
            note.setStyleSheet(f"color: {SUBTLE_FG};")
            v.addWidget(note, stretch=1)
            return card

        canvas = self._make_pie_canvas(items)
        if canvas is None:
            empty = QLabel("Nessun dato disponibile per il periodo selezionato.")
            empty.setStyleSheet(f"color: {SUBTLE_FG};")
            empty.setWordWrap(True)
            v.addWidget(empty, stretch=1)
        else:
            v.addWidget(canvas, stretch=1)
        return card

    # ------------------------------------------------------------------
    # Pie chart matplotlib
    # ------------------------------------------------------------------

    def _make_pie_canvas(self, items: list) -> FigureCanvasQTAgg | None:
        compact_items = self._compact_items(items or [], max_items=6)
        if not compact_items:
            return None

        labels = [item["label"] for item in compact_items]
        values = [float(item["value"] or 0) for item in compact_items]
        # Se tutti i valori sono nulli, evitiamo il pie (matplotlib alza warn).
        if sum(values) <= 0:
            return None
        colors = PIE_COLORS[: len(values)]

        figure = plt.Figure(figsize=self.CHART_FIG_SIZE, facecolor=CARD_BG)
        axis = figure.add_subplot(111)
        axis.set_facecolor(CARD_BG)

        wedges, _, autotexts = axis.pie(
            values,
            colors=colors,
            startangle=90,
            autopct=lambda pct: f"{pct:.1f}%" if pct >= 5 else "",
            pctdistance=0.72,
            wedgeprops={"linewidth": 1.0, "edgecolor": CARD_BG},
            textprops={"color": TITLE_FG, "fontsize": 9},
        )

        for autotext in autotexts:
            autotext.set_color("#f8fafc")
            autotext.set_fontsize(9)
            autotext.set_weight("bold")

        axis.axis("equal")
        axis.legend(
            wedges,
            [ViewUtils.split_string_by_length(label, 24) for label in labels],
            loc="center left",
            bbox_to_anchor=(0.9, 0.8),
            frameon=False,
            labelcolor="#d7e3f0",
            fontsize=9,
        )
        figure.subplots_adjust(left=-0.05, right=0.68, top=0.95, bottom=0.06)

        canvas = FigureCanvasQTAgg(figure)
        canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        canvas.setMinimumHeight(360)
        canvas.draw()

        self._figures.append(figure)
        self._canvases.append(canvas)

        # Tooltip al passaggio del mouse (stesso comportamento della
        # legacy: evidenzia la fetta + mostra un'annotation con valore e %).
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
                for w in wedges:
                    w.set_alpha(1.0)
                annotation.set_visible(False)
                current_wedge["index"] = None
                canvas.draw_idle()
                return
            for i, wedge in enumerate(wedges):
                contains, _ = wedge.contains(event)
                if contains:
                    if current_wedge["index"] is not None and current_wedge["index"] != i:
                        wedges[current_wedge["index"]].set_alpha(1.0)
                    current_wedge["index"] = i
                    value = values[i]
                    label = labels[i]
                    total = sum(values)
                    pct = (value / total) * 100 if total else 0
                    wedge.set_alpha(0.7)
                    annotation.xy = (event.xdata, event.ydata)
                    annotation.set_text(f"{label}\n{value:.2f} € ({pct:.1f}%)")
                    annotation.set_visible(True)
                    canvas.draw_idle()
                    return
            for w in wedges:
                w.set_alpha(1.0)
            current_wedge["index"] = None
            annotation.set_visible(False)
            canvas.draw_idle()

        canvas.mpl_connect("motion_notify_event", on_motion)
        return canvas

    @staticmethod
    def _compact_items(items: list, max_items: int) -> list:
        if len(items) <= max_items:
            return items
        visible_items = items[: max_items - 1]
        remaining_total = sum(item["value"] for item in items[max_items - 1:])
        visible_items.append({"label": "Altro", "value": round(remaining_total, 2)})
        return visible_items

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _cleanup_figures(self):
        for canvas in self._canvases:
            try:
                canvas.setParent(None)
                canvas.deleteLater()
            except Exception:
                pass
        for figure in self._figures:
            try:
                plt.close(figure)
            except Exception:
                pass
        self._canvases.clear()
        self._figures.clear()

    def cleanup(self):
        self._cleanup_figures()

    # ------------------------------------------------------------------
    # API esterna (refresh dalla parent view)
    # ------------------------------------------------------------------

    def refresh(self):
        self._rebuild_content()

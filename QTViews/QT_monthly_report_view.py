"""
Sottoview "Dati Mensili" del report, versione Qt.

Replica ``Views/Monthly_report_view.py`` (legacy CustomTkinter):
- header con titolo "REPORT MENSILE" e anno corrente;
- riga di 4 card con le medie annuali (fatturato, spese, entrate,
  uscite);
- tabella dei 12 mesi con le quattro metriche, dove il mese corrente
  e' evidenziato con un bordo e i mesi futuri sono renderizzati in
  un colore attenuato;
- footer con la data di aggiornamento e la nota "Fatturato e Spese
  esenti IVA".

I dati provengono da
``MonthlyReportAnalyzerService.retrieve_monthly_data()``: per ogni mese
restituisce ``{"values": {fatturato, spese, incomes, outcomes}, ...}``
e una chiave ``averages`` con le stesse 4 metriche aggregate.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from App_context import AppContext


MONTH_NAMES = [
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

# Palette legacy.
HEADER_BG = "#2874a6"
HEADER_BG_FIRST = "#1a5276"
ROW_PAST_BG = "#2c3e50"
ROW_CURRENT_BORDER = "#1f6aa5"
ROW_FUTURE_FG = "gray"
CARD_BG = "#e8f4f8"
CARD_TITLE_FG = "#2c3e50"
CARD_VALUE_FG = "#1f6aa5"
TITLE_FG = "#e8f4f8"
SUBTLE_FG = "#7f8c8d"


def _fmt_eur(value) -> str:
    try:
        n = float(value)
    except (TypeError, ValueError):
        n = 0.0
    return f"{n:.2f} €"


class QTMonthlyReportViewH(QWidget):
    """Tabella mensile + card delle medie per l'anno corrente."""

    METRICS = ("fatturato", "spese", "incomes", "outcomes")
    METRIC_LABELS = ("Fatturato", "Spese", "Entrate", "Uscite")

    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.monthly_report_analyzer_service = app_context.monthly_report_analyzer_service

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        root.addWidget(self.scroll, stretch=1)

        self.content = QWidget()
        self.scroll.setWidget(self.content)
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(20, 10, 20, 10)
        self.content_layout.setSpacing(10)

        self._populate()

    def _populate(self):
        monthly_data = self.monthly_report_analyzer_service.retrieve_monthly_data() or {}
        averages = self._extract_averages(monthly_data)

        self.content_layout.addWidget(self._build_title_row())
        self.content_layout.addWidget(self._build_averages_cards(averages))
        self.content_layout.addWidget(self._build_monthly_table(monthly_data), stretch=1)
        self.content_layout.addWidget(self._build_footer())

    # ------------------------------------------------------------------
    # Sezioni
    # ------------------------------------------------------------------

    def _build_title_row(self) -> QWidget:
        wrapper = QFrame()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 6, 0, 4)

        title = QLabel("REPORT MENSILE")
        tf = title.font()
        tf.setPointSize(16)
        tf.setBold(True)
        title.setFont(tf)
        title.setStyleSheet(f"color: {TITLE_FG};")
        layout.addWidget(title)

        layout.addStretch(1)

        year = QLabel(f"Anno: {datetime.now().year}")
        yf = year.font()
        yf.setItalic(True)
        yf.setPointSize(10)
        year.setFont(yf)
        year.setStyleSheet(f"color: {SUBTLE_FG};")
        layout.addWidget(year)
        return wrapper

    def _build_averages_cards(self, averages: dict) -> QWidget:
        wrapper = QFrame()
        grid = QGridLayout(wrapper)
        grid.setContentsMargins(0, 4, 0, 8)
        grid.setHorizontalSpacing(12)

        items = [
            ("Fatturato Medio", averages.get("fatturato", 0)),
            ("Spese Medie", averages.get("spese", 0)),
            ("Entrate Medie", averages.get("incomes", 0)),
            ("Uscite Medie", averages.get("outcomes", 0)),
        ]
        for col, (text, value) in enumerate(items):
            grid.setColumnStretch(col, 1)
            grid.addWidget(self._make_average_card(text, value), 0, col)
        return wrapper

    def _make_average_card(self, text: str, value: float) -> QFrame:
        card = QFrame()
        card.setObjectName("MonthlyAvgCard")
        card.setStyleSheet(
            f"#MonthlyAvgCard {{ background-color: {CARD_BG};"
            " border-radius: 10px; }"
        )
        v = QVBoxLayout(card)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(2)

        title_lbl = QLabel(text)
        title_lbl.setAlignment(Qt.AlignCenter)
        tf = title_lbl.font()
        tf.setPointSize(11)
        title_lbl.setFont(tf)
        title_lbl.setStyleSheet(f"color: {CARD_TITLE_FG};")
        v.addWidget(title_lbl)

        value_lbl = QLabel(_fmt_eur(value))
        value_lbl.setAlignment(Qt.AlignCenter)
        vf = value_lbl.font()
        vf.setBold(True)
        vf.setPointSize(14)
        value_lbl.setFont(vf)
        value_lbl.setStyleSheet(f"color: {CARD_VALUE_FG};")
        v.addWidget(value_lbl)
        return card

    def _build_monthly_table(self, monthly_data: dict) -> QWidget:
        wrapper = QFrame()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(4)

        # Header.
        header = QFrame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        headers = ["Mese", "Fatturato", "Spese", "Entrate", "Uscite"]
        for i, h in enumerate(headers):
            cell = QLabel(h)
            cell.setAlignment(Qt.AlignCenter)
            f = cell.font()
            f.setBold(True)
            f.setPointSize(12)
            cell.setFont(f)
            cell.setStyleSheet(
                f"background-color: {HEADER_BG_FIRST if i == 0 else HEADER_BG};"
                " color: white; padding: 10px; border-radius: 4px;"
            )
            header_layout.addWidget(cell, stretch=1)
        layout.addWidget(header)

        # Righe mesi scrollabili.
        rows_scroll = QScrollArea()
        rows_scroll.setWidgetResizable(True)
        rows_scroll.setFrameShape(QFrame.NoFrame)
        rows_container = QWidget()
        rows_scroll.setWidget(rows_container)
        rows_layout = QVBoxLayout(rows_container)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(4)

        current_month = datetime.now().month
        for month in range(1, 13):
            data = monthly_data.get(month, {}) or {}
            values = data.get("values", {}) or {}
            is_current = (month == current_month)
            has_started = (current_month >= month)
            rows_layout.addWidget(self._make_month_row(month, values, is_current, has_started))

        rows_layout.addStretch(1)
        layout.addWidget(rows_scroll, stretch=1)
        return wrapper

    def _make_month_row(self, month: int, values: dict, is_current: bool, has_started: bool) -> QWidget:
        row = QFrame()
        row.setObjectName("MonthlyRow")
        bg = ROW_PAST_BG if has_started else "transparent"
        border = (
            f" border: 2px solid {ROW_CURRENT_BORDER};"
            if is_current else " border: none;"
        )
        row.setStyleSheet(
            f"#MonthlyRow {{ background-color: {bg}; border-radius: 4px;{border} }}"
        )

        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        # Colonna mese.
        month_lbl = QLabel(MONTH_NAMES[month])
        month_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        mf = month_lbl.font()
        mf.setPointSize(13)
        mf.setBold(is_current)
        month_lbl.setFont(mf)
        month_lbl.setStyleSheet(
            "color: white;" if is_current else "color: #ecf0f1;"
        )
        layout.addWidget(month_lbl, stretch=1)

        # Colonne metriche.
        for metric in self.METRICS:
            value = values.get(metric, 0) or 0
            cell = QLabel(_fmt_eur(value))
            cell.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            cf = cell.font()
            cf.setPointSize(12)
            cf.setBold(is_current)
            cell.setFont(cf)
            cell.setStyleSheet(
                "color: white;" if has_started else f"color: {ROW_FUTURE_FG};"
            )
            layout.addWidget(cell, stretch=1)
        return row

    def _build_footer(self) -> QWidget:
        wrapper = QFrame()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 4, 0, 10)
        text = (
            "* Dati aggiornati al: "
            + datetime.now().strftime("%d/%m/%Y")
            + "\nFatturato e Spese esenti IVA"
        )
        lbl = QLabel(text)
        f = lbl.font()
        f.setPointSize(9)
        lbl.setFont(f)
        lbl.setStyleSheet(f"color: {SUBTLE_FG};")
        layout.addWidget(lbl)
        layout.addStretch(1)
        return wrapper

    # ------------------------------------------------------------------
    # Utils
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_averages(monthly_data: dict) -> dict:
        sample_month = monthly_data.get(1, {}) if monthly_data else {}
        return sample_month.get(
            "averages",
            {"fatturato": 0.0, "spese": 0.0, "incomes": 0.0, "outcomes": 0.0},
        )

    # ------------------------------------------------------------------
    # API esterna (refresh dalla parent view)
    # ------------------------------------------------------------------

    def refresh(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._populate()

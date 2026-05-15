"""
Vista IVA trimestrale, versione Qt.

Replica ``Views/Iva_trimes_view.py`` (legacy CustomTkinter):
- header con 4 colonne: TRIMESTRE / CREDITO / DEBITO / DA PAGARE;
- una riga di riepilogo per ognuno dei 4 trimestri dell'anno corrente,
  espandibile in dettaglio per partita IVA (un click sul bottone
  ``>`` / ``<`` apre/chiude la sezione dei dettagli);
- riga "TOTALE ANNUALE" con la somma dei trimestri;
- sezione separata "Ultimo trimestre <anno-1>" che legge i dati dai
  libri contabili archiviati (``books_retriever``), anche questa
  espandibile per utente.

I dati aggregati vengono calcolati esattamente come la legacy:
``IvaAnalyzerService.calculate_tot_trimestral_iva()`` restituisce un
dizionario ``{nome_utente: {trimestre: {debito, credito, da_pagare}}}``
e qui ne aggreghiamo gli importi sia a livello di trimestre sia a
livello annuale.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from App_context import AppContext


QUARTERS_ORDER = ("Gen-Marz", "Apr-Giu", "Lug-Sett", "Ott-Dic")

# Colori coerenti con la legacy.
ACCENT = "#3773b8"
COLOR_DEBITO = "#f52f2f"   # rosso: saldo da pagare > 0
COLOR_CREDITO = "#2ca31c"  # verde: saldo < 0 (credito)
COLOR_NEUTRAL = "#b0b0b0"


def _fmt_eur(value) -> str:
    try:
        n = float(value)
    except (TypeError, ValueError):
        n = 0.0
    s = f"{n:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    return f"{s} €"


def _saldo_color(saldo: float) -> str:
    if saldo > 0:
        return COLOR_DEBITO
    if saldo < 0:
        return COLOR_CREDITO
    return COLOR_NEUTRAL


class QTIvaViewH(QWidget):
    """Vista IVA trimestrale: aggregato + dettaglio per utente, con sezione
    dell'ultimo trimestre dell'anno precedente letto dai libri."""

    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.iva_analyzer_service = app_context.iva_analyzer_service
        self.books_retriever = app_context.books_retriever

        # Riferimenti per il toggle expand/collapse.
        self._quarter_details: dict[str, QWidget] = {}
        self._quarter_buttons: dict[str, QPushButton] = {}
        self._past_details: QWidget | None = None
        self._past_button: QPushButton | None = None

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

        content = QWidget()
        self.scroll.setWidget(content)
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(15, 80, 15, 70)
        self.content_layout.setSpacing(14)

        self._populate()

    def _populate(self):
        # --- Header colonne ---
        self.content_layout.addWidget(self._make_header_row())

        # --- Dati anno corrente ---
        iva_data = self.iva_analyzer_service.calculate_tot_trimestral_iva() or {}

        quarter_totals = {
            q: {"debito": 0.0, "credito": 0.0, "da_pagare": 0.0}
            for q in QUARTERS_ORDER
        }
        annual_totals = {"debito": 0.0, "credito": 0.0, "da_pagare": 0.0}

        for user_data in iva_data.values():
            for quarter, data in user_data.items():
                if quarter not in quarter_totals:
                    continue
                for key in ("debito", "credito", "da_pagare"):
                    quarter_totals[quarter][key] += float(data.get(key, 0) or 0)
                    annual_totals[key] += float(data.get(key, 0) or 0)

        for quarter in QUARTERS_ORDER:
            self.content_layout.addWidget(
                self._make_quarter_block(quarter, quarter_totals[quarter], iva_data)
            )

        # Separatore + riga totale annuale.
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: palette(mid);")
        self.content_layout.addWidget(sep)
        self.content_layout.addWidget(self._make_annual_total_row(annual_totals))

        # --- Sezione ultimo trimestre anno precedente ---
        previous_year = datetime.now().year - 1
        self.content_layout.addSpacing(20)
        past_title = QLabel(f"-  Ultimo trimestre {previous_year}  -")
        f = past_title.font()
        f.setItalic(True)
        f.setPointSize(11)
        past_title.setFont(f)
        past_title.setAlignment(Qt.AlignCenter)
        past_title.setContentsMargins(0, 40, 0, 8)
        self.content_layout.addWidget(past_title)

        past_block, past_data = self._compute_past_quarter_data(previous_year)
        self.content_layout.addWidget(self._make_past_quarter_block(previous_year, past_block, past_data))

        self.content_layout.addStretch(1)

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    def _make_header_row(self) -> QWidget:
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        for text in ("TRIMESTRE", "CREDITO", "DEBITO", "DA PAGARE"):
            cell = QLabel(text)
            cell.setAlignment(Qt.AlignCenter)
            cf = cell.font()
            cf.setBold(True)
            cf.setPointSize(11)
            cell.setFont(cf)
            cell.setStyleSheet(
                f"background-color: {ACCENT};"
                " color: palette(highlighted-text);"
                " padding: 14px; border-radius: 6px;"
            )
            layout.addWidget(cell, stretch=1)
        return wrapper

    # ------------------------------------------------------------------
    # Quarter block (anno corrente)
    # ------------------------------------------------------------------

    def _make_quarter_block(self, quarter: str, totals: dict, iva_data: dict) -> QWidget:
        container = QFrame()
        container.setObjectName("IvaQuarterBlock")
        container.setStyleSheet(
            f"#IvaQuarterBlock {{ border: 2px solid {ACCENT}; border-radius: 6px; }}"
        )
        v = QVBoxLayout(container)
        v.setContentsMargins(5, 5, 5, 5)
        v.setSpacing(4)

        # Riga di riepilogo.
        v.addWidget(self._make_summary_row(quarter, totals, with_dropdown=True))

        # Dettagli per utente (nascosti inizialmente).
        details = QWidget()
        details.setObjectName("IvaQuarterDetails")
        details.setStyleSheet(
            "#IvaQuarterDetails { background-color: palette(window); border-radius: 4px; }"
        )
        d_layout = QVBoxLayout(details)
        d_layout.setContentsMargins(4, 4, 4, 4)
        d_layout.setSpacing(2)

        for user_name in sorted(iva_data.keys()):
            user_quarter = iva_data[user_name].get(quarter)
            if not user_quarter:
                continue
            d_layout.addWidget(self._make_user_detail_row(user_name, user_quarter))

        details.setVisible(False)
        v.addWidget(details)

        self._quarter_details[quarter] = details
        return container

    def _make_summary_row(self, quarter: str, totals: dict, with_dropdown: bool) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Colonna 1: nome trimestre + dropdown.
        name_cell = QFrame()
        name_layout = QHBoxLayout(name_cell)
        name_layout.setContentsMargins(10, 8, 10, 8)
        name_layout.setSpacing(8)
        name_lbl = QLabel(quarter)
        nf = name_lbl.font()
        nf.setPointSize(12)
        name_lbl.setFont(nf)
        name_layout.addWidget(name_lbl, stretch=1)
        if with_dropdown:
            btn = QPushButton(">")
            btn.setFixedSize(28, 28)
            btn.clicked.connect(lambda _=False, q=quarter: self._toggle_quarter(q))
            name_layout.addWidget(btn)
            self._quarter_buttons[quarter] = btn
        layout.addWidget(name_cell, stretch=1)

        # Colonne 2, 3: credito, debito.
        layout.addWidget(self._make_amount_cell(_fmt_eur(totals.get("credito", 0))), stretch=1)
        layout.addWidget(self._make_amount_cell(_fmt_eur(totals.get("debito", 0))), stretch=1)

        # Colonna 4: saldo da pagare (colorata).
        saldo = float(totals.get("da_pagare", 0) or 0)
        layout.addWidget(
            self._make_amount_cell(_fmt_eur(saldo), bg=_saldo_color(saldo), bold=True),
            stretch=1,
        )
        return row

    def _make_user_detail_row(self, user_name: str, user_quarter: dict) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(20, 2, 4, 2)
        layout.setSpacing(6)

        layout.addWidget(self._make_amount_cell(user_name, align=Qt.AlignLeft), stretch=1)
        layout.addWidget(
            self._make_amount_cell(_fmt_eur(user_quarter.get("credito", 0))),
            stretch=1,
        )
        layout.addWidget(
            self._make_amount_cell(_fmt_eur(user_quarter.get("debito", 0))),
            stretch=1,
        )
        saldo = float(user_quarter.get("da_pagare", 0) or 0)
        layout.addWidget(
            self._make_amount_cell(_fmt_eur(saldo), bg=_saldo_color(saldo)),
            stretch=1,
        )
        return row

    def _make_amount_cell(
        self,
        text: str,
        bg: str | None = None,
        bold: bool = False,
        align=Qt.AlignCenter,
    ) -> QLabel:
        lbl = QLabel(text)
        lbl.setAlignment(align)
        if bold:
            f = lbl.font()
            f.setBold(True)
            lbl.setFont(f)
        style = "padding: 8px; border-radius: 4px;"
        if bg:
            style += (
                f" background-color: {bg};"
                " color: palette(highlighted-text);"
            )
        else:
            style += " background-color: palette(alternate-base);"
        lbl.setStyleSheet(style)
        return lbl

    # ------------------------------------------------------------------
    # Totale annuale
    # ------------------------------------------------------------------

    def _make_annual_total_row(self, totals: dict) -> QWidget:
        container = QFrame()
        container.setObjectName("IvaAnnualTotal")
        container.setStyleSheet(
            f"#IvaAnnualTotal {{ border: 2px solid {ACCENT}; border-radius: 6px; }}"
        )
        v = QVBoxLayout(container)
        v.setContentsMargins(5, 5, 5, 5)

        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        layout.addWidget(self._make_amount_cell("TOTALE ANNUALE", bold=True), stretch=1)
        layout.addWidget(
            self._make_amount_cell(_fmt_eur(totals.get("credito", 0)), bold=True),
            stretch=1,
        )
        layout.addWidget(
            self._make_amount_cell(_fmt_eur(totals.get("debito", 0)), bold=True),
            stretch=1,
        )
        saldo = float(totals.get("da_pagare", 0) or 0)
        layout.addWidget(
            self._make_amount_cell(_fmt_eur(saldo), bg=_saldo_color(saldo), bold=True),
            stretch=1,
        )
        v.addWidget(row)
        return container

    # ------------------------------------------------------------------
    # Ultimo trimestre anno precedente
    # ------------------------------------------------------------------

    def _compute_past_quarter_data(self, year: int):
        try:
            iva_rows = self.books_retriever.get_iva_data_for_year(year) or []
        except Exception:
            iva_rows = []

        target = "Ott-Dic"
        agg = {"credito": 0.0, "debito": 0.0, "da_pagare": 0.0}
        per_user: dict[str, dict] = {}

        for row in iva_rows:
            if row.get("nome_trimestre") != target:
                continue
            credito = float(row.get("iva_credito", 0.0) or 0.0)
            debito = float(row.get("iva_debito", 0.0) or 0.0)
            saldo = float(row.get("iva_da_pagare", 0.0) or 0.0)
            user = row.get("utente", "N/D")

            agg["credito"] += credito
            agg["debito"] += debito
            agg["da_pagare"] += saldo

            per_user[user] = {
                "credito": credito,
                "debito": debito,
                "da_pagare": saldo,
            }

        return agg, per_user

    def _make_past_quarter_block(self, year: int, totals: dict, per_user: dict) -> QWidget:
        container = QFrame()
        container.setObjectName("IvaPastQuarterBlock")
        container.setStyleSheet(
            "#IvaPastQuarterBlock { border: 2px solid palette(mid); border-radius: 6px; }"
        )
        v = QVBoxLayout(container)
        v.setContentsMargins(5, 5, 5, 5)
        v.setSpacing(4)

        # Riga di riepilogo: usa una label trimestre custom invece di
        # ``Ott-Dic`` per chiarire l'anno di riferimento. Il colore del
        # saldo qui resta neutrale come fa la legacy.
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        name_cell = QFrame()
        name_layout = QHBoxLayout(name_cell)
        name_layout.setContentsMargins(10, 8, 10, 8)
        name_layout.setSpacing(8)
        name_lbl = QLabel(f"Ott-Dic {year}")
        nf = name_lbl.font()
        nf.setPointSize(12)
        name_lbl.setFont(nf)
        name_layout.addWidget(name_lbl, stretch=1)
        btn = QPushButton(">")
        btn.setFixedSize(28, 28)
        btn.clicked.connect(self._toggle_past_quarter)
        name_layout.addWidget(btn)
        self._past_button = btn
        layout.addWidget(name_cell, stretch=1)

        layout.addWidget(self._make_amount_cell(_fmt_eur(totals.get("credito", 0))), stretch=1)
        layout.addWidget(self._make_amount_cell(_fmt_eur(totals.get("debito", 0))), stretch=1)
        layout.addWidget(
            self._make_amount_cell(_fmt_eur(totals.get("da_pagare", 0)), bg=COLOR_NEUTRAL),
            stretch=1,
        )
        v.addWidget(row)

        # Dettagli per utente (nascosti inizialmente).
        details = QWidget()
        details.setObjectName("IvaPastQuarterDetails")
        details.setStyleSheet(
            "#IvaPastQuarterDetails { background-color: palette(window); border-radius: 4px; }"
        )
        d_layout = QVBoxLayout(details)
        d_layout.setContentsMargins(4, 4, 4, 4)
        d_layout.setSpacing(2)
        for user_name in sorted(per_user.keys()):
            d_layout.addWidget(self._make_user_detail_row(user_name, per_user[user_name]))
        details.setVisible(False)
        v.addWidget(details)

        self._past_details = details
        return container

    # ------------------------------------------------------------------
    # Toggle expand/collapse
    # ------------------------------------------------------------------

    def _toggle_quarter(self, quarter: str):
        details = self._quarter_details.get(quarter)
        btn = self._quarter_buttons.get(quarter)
        if details is None or btn is None:
            return
        new_visible = not details.isVisible()
        details.setVisible(new_visible)
        btn.setText("<" if new_visible else ">")

    def _toggle_past_quarter(self):
        if self._past_details is None or self._past_button is None:
            return
        new_visible = not self._past_details.isVisible()
        self._past_details.setVisible(new_visible)
        self._past_button.setText("v" if new_visible else ">")

    # ------------------------------------------------------------------
    # API esterna (refresh dalla main view)
    # ------------------------------------------------------------------

    def refresh(self):
        """Ricostruisce la vista da zero leggendo nuovi dati."""
        # Pulisci.
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._quarter_details.clear()
        self._quarter_buttons.clear()
        self._past_details = None
        self._past_button = None
        self._populate()

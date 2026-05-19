"""
Vista "Tasse" (Previsione Tasse Willow), versione Qt.

Replica ``Views/Taxes_view.py`` (legacy CustomTkinter):
- switch in alto per scegliere tra ``anno corrente`` (dati calcolati a
  runtime tramite ``UserAnalyzerService.calculate_previsione_tasse_willow``)
  e ``anno precedente`` (dati letti dai libri archiviati via
  ``BooksRetriever.get_taxes_summary_for_year``);
- due tabelle:
    1. "Saldi e Acconti": saldo Willow dell'anno selezionato + acconto
       per l'anno successivo;
    2. "Ripartizione IRPEF/INPS": dettaglio IRPEF e INPS Willow per
       utente, senza tener conto degli acconti.
- riga finale "TOTALE" evidenziata in blu;
- se per l'anno precedente non ci sono dati nei libri, viene mostrato
  un messaggio dedicato.

I dati del retriever vengono convertiti nello stesso formato usato
dall'analyzer cosi' che la stessa funzione di rendering serva entrambe
le sorgenti, come fa la legacy in
``convert_retriever_to_analyzer_format``.
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

from QTViews.CustomWidgets.QT_toggle_switch import QTToggleSwitch

if TYPE_CHECKING:
    from App_context import AppContext


ACCENT = "#2d7acf"           # blu acceso (label di sezione)
TOTAL_BACKGROUND = "#1F538D"  # blu scuro (celle del totale)


def _fmt_eur(value) -> str:
    try:
        n = float(value)
    except (TypeError, ValueError):
        n = 0.0
    s = f"{n:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    return s


class QTTaxesViewH(QWidget):
    """Previsione tasse Willow per utente, anno corrente / anno precedente."""

    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.user_analyzer_service = app_context.user_analyzer_service
        self.books_retriever = app_context.books_retriever

        self._show_current_year: bool = True

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Barra di controllo (sempre visibile, fuori dallo scroll).
        controls = QFrame()
        c_layout = QHBoxLayout(controls)
        c_layout.setContentsMargins(20, 16, 20, 8)

        title = QLabel("Previsione Tasse Willow")
        tf = title.font()
        tf.setPointSize(15)
        tf.setBold(True)
        title.setFont(tf)
        c_layout.addWidget(title)

        c_layout.addSpacing(20)

        self.year_switch = QTToggleSwitch(
            on_change=self._on_year_switch_changed,
            initial=True,
        )
        c_layout.addWidget(self.year_switch)

        self.year_label = QLabel(f"Anno: {datetime.now().year}")
        yf = self.year_label.font()
        yf.setPointSize(13)
        self.year_label.setFont(yf)
        self.year_label.setStyleSheet(f"color: {ACCENT};")
        c_layout.addWidget(self.year_label)

        c_layout.addStretch(1)

        root.addWidget(controls)

        # Separatore.
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: palette(mid);")
        root.addWidget(sep)

        # Area scrollabile per le tabelle.
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        root.addWidget(self.scroll, stretch=1)

        self.content = QWidget()
        self.scroll.setWidget(self.content)
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(15, 15, 15, 15)
        self.content_layout.setSpacing(15)

        self._populate()

    # ------------------------------------------------------------------
    # Pipeline dati (anno corrente vs anno precedente)
    # ------------------------------------------------------------------

    def _get_tax_data(self):
        if self._show_current_year:
            return self.user_analyzer_service.calculate_previsione_tasse_willow()
        # Anno precedente: leggi dai libri archiviati.
        last_year = datetime.now().year - 1
        try:
            taxes_summary = self.books_retriever.get_taxes_summary_for_year(last_year)
        except Exception:
            taxes_summary = None
        if not taxes_summary:
            return None
        return self._convert_retriever_to_analyzer_format(taxes_summary)

    @staticmethod
    def _convert_retriever_to_analyzer_format(retriever_data: dict) -> dict:
        analyzer_format: dict = {}

        users = retriever_data.get("users") or {}
        for user_name, user_data in users.items():
            analyzer_format[user_name] = {
                "SALDO WILLOW": float(user_data.get("saldo_willow", 0) or 0),
                "ACCONTO WILLOW": float(user_data.get("acconto_willow", 0) or 0),
                "IRPEF WILLOW": float(user_data.get("irpef_willow", 0) or 0),
                "INPS WILLOW": float(user_data.get("inps_willow", 0) or 0),
            }

        totale = retriever_data.get("totale") or {}
        if totale:
            analyzer_format["TOTALE"] = {
                "SALDO WILLOW": float(totale.get("saldo_willow", 0) or 0),
                "ACCONTO WILLOW": float(totale.get("acconto_willow", 0) or 0),
                "IRPEF WILLOW": float(totale.get("irpef_willow", 0) or 0),
                "INPS WILLOW": float(totale.get("inps_willow", 0) or 0),
            }
        else:
            # Ricalcolo del totale come fa la legacy se il CSV non lo include.
            analyzer_format["TOTALE"] = {
                k: sum(v.get(k, 0) for v in analyzer_format.values())
                for k in ("SALDO WILLOW", "ACCONTO WILLOW", "IRPEF WILLOW", "INPS WILLOW")
            }
        return analyzer_format

    # ------------------------------------------------------------------
    # Eventi UI
    # ------------------------------------------------------------------

    def _on_year_switch_changed(self, checked: bool):
        self._show_current_year = checked
        self.year_label.setText(
            f"Anno: {datetime.now().year if checked else datetime.now().year - 1}"
        )
        self._populate()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _populate(self):
        # Pulisci i contenuti correnti.
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        tasse_data = self._get_tax_data()

        if tasse_data is None:
            self.content_layout.addWidget(self._make_no_data_message())
            self.content_layout.addStretch(1)
            return

        display_year = datetime.now().year if self._show_current_year else datetime.now().year - 1

        # Titolo della sezione.
        section_title = QLabel(
            f"Previsione Tasse Willow - Panoramica Generale {display_year}"
        )
        stf = section_title.font()
        stf.setPointSize(15)
        stf.setBold(True)
        section_title.setFont(stf)
        section_title.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(section_title)

        # Tabella 1: Saldi e Acconti.
        self._add_section_header(
            "Saldi e Acconti",
            "Previsione delle tasse da versare quest'anno, in funzione del "
            "saldo rispetto all'acconto dell'anno scorso e l'acconto per il "
            "prossimo anno",
        )
        next_year = display_year + 1
        self.content_layout.addWidget(
            self._make_table(
                tasse_data,
                headers=[
                    "Utente",
                    f"Saldo Willow - {display_year} (€)",
                    f"Acconto Willow - {next_year} (€)",
                ],
                value_keys=["SALDO WILLOW", "ACCONTO WILLOW"],
            )
        )

        # Tabella 2: Ripartizione IRPEF/INPS.
        self.content_layout.addSpacing(40)
        self._add_section_header(
            "Ripartizione IRPEF/INPS",
            "Dettaglio delle tasse relative a quest'anno, differenziate tra "
            "IRPEF e INPS  -  Non tiene conto di acconti precedenti o futuri",
        )
        self.content_layout.addWidget(
            self._make_table(
                tasse_data,
                headers=["Utente", "IRPEF Willow (€)", "INPS Willow (€)"],
                value_keys=["IRPEF WILLOW", "INPS WILLOW"],
            )
        )

        self.content_layout.addStretch(1)

    def _add_section_header(self, title: str, subtitle: str):
        title_lbl = QLabel(title)
        tf = title_lbl.font()
        tf.setPointSize(14)
        tf.setBold(True)
        title_lbl.setFont(tf)
        title_lbl.setStyleSheet(f"color: {ACCENT};")
        title_lbl.setContentsMargins(15, 8, 0, 0)
        self.content_layout.addWidget(title_lbl)

        sub_lbl = QLabel(subtitle)
        sub_lbl.setStyleSheet("color: palette(mid);")
        sub_lbl.setWordWrap(True)
        sub_lbl.setContentsMargins(15, 0, 0, 0)
        self.content_layout.addWidget(sub_lbl)

    def _make_table(self, tasse_data: dict, headers: list[str], value_keys: list[str]) -> QWidget:
        frame = QFrame()
        frame.setObjectName("TaxesTable")
        frame.setStyleSheet(
            "#TaxesTable { background-color: palette(alternate-base); border-radius: 6px; }"
        )
        grid = QGridLayout(frame)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)

        # Intestazioni.
        for col, header in enumerate(headers):
            grid.addWidget(self._make_header_cell(header), 0, col)
        for col in range(len(headers)):
            grid.setColumnStretch(col, 1)

        # Righe utenti.
        row = 1
        for user_name, values in tasse_data.items():
            if user_name == "TOTALE":
                continue
            grid.addWidget(self._make_text_cell(user_name, align=Qt.AlignLeft), row, 0)
            for col, key in enumerate(value_keys, start=1):
                grid.addWidget(
                    self._make_text_cell(_fmt_eur(values.get(key, 0)), align=Qt.AlignRight),
                    row,
                    col,
                )
            row += 1

        # Separatore.
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: palette(mid);")
        grid.addWidget(sep, row, 0, 1, len(headers))
        row += 1

        # Riga totale.
        total_values = tasse_data.get("TOTALE", {})
        grid.addWidget(self._make_total_cell("TOTALE", align=Qt.AlignLeft, fill=False), row, 0)
        for col, key in enumerate(value_keys, start=1):
            grid.addWidget(
                self._make_total_cell(_fmt_eur(total_values.get(key, 0)), align=Qt.AlignRight),
                row,
                col,
            )
        return frame

    # --- Cell helpers --------------------------------------------------

    def _make_header_cell(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        f = lbl.font()
        f.setBold(True)
        f.setPointSize(11)
        lbl.setFont(f)
        lbl.setStyleSheet(
            f"background-color: {TOTAL_BACKGROUND};"
            " color: palette(highlighted-text);"
            " padding: 10px; border-radius: 6px;"
        )
        return lbl

    def _make_text_cell(self, text: str, align=Qt.AlignCenter) -> QLabel:
        lbl = QLabel(text)
        lbl.setAlignment(align | Qt.AlignVCenter)
        lbl.setStyleSheet("padding: 6px;")
        return lbl

    def _make_total_cell(self, text: str, align=Qt.AlignCenter, fill: bool = True) -> QLabel:
        lbl = QLabel(text)
        lbl.setAlignment(align | Qt.AlignVCenter)
        f = lbl.font()
        f.setBold(True)
        f.setPointSize(12)
        lbl.setFont(f)
        if fill:
            lbl.setStyleSheet(
                f"background-color: {TOTAL_BACKGROUND};"
                " color: palette(highlighted-text);"
                " padding: 8px; border-radius: 6px;"
            )
        else:
            lbl.setStyleSheet("padding: 8px;")
        return lbl

    # ------------------------------------------------------------------
    # No-data placeholder
    # ------------------------------------------------------------------

    def _make_no_data_message(self) -> QWidget:
        wrapper = QFrame()
        wrapper.setObjectName("TaxesNoData")
        wrapper.setStyleSheet(
            "#TaxesNoData { background-color: palette(alternate-base); border-radius: 8px; }"
        )
        v = QVBoxLayout(wrapper)
        v.setContentsMargins(40, 40, 40, 40)
        v.setSpacing(10)

        message = QLabel("⚠️ Nessun dato disponibile per l'anno selezionato")
        message.setAlignment(Qt.AlignCenter)
        f = message.font()
        f.setPointSize(15)
        f.setBold(True)
        message.setFont(f)
        message.setStyleSheet("color: orange;")
        v.addWidget(message)

        hint = QLabel(
            "Assicurati che il file taxes_aggregated_data.csv sia presente "
            "nella directory Books"
        )
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color: palette(mid);")
        hint.setWordWrap(True)
        v.addWidget(hint)

        return wrapper

    # ------------------------------------------------------------------
    # API esterna (refresh dalla main view)
    # ------------------------------------------------------------------

    def refresh(self):
        self._populate()

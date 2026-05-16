"""
Dialog di configurazione della visibilita' dei warning.

Layout: una sezione per dominio (FATTURE, PAGAMENTI, …). Ogni sezione
elenca i warning del dominio raggruppati per severity (1 in alto, 3 in
basso) con:
- pallino colorato a sinistra (colore della severity);
- checkbox per i sev 2 e 3 (abilitabili / disabilitabili);
- checkbox lockata e checked per i sev 1 (non disabilitabili, sempre
  visibili finche' non risolti).

Lo stato viene letto da ``WarningsVisibilityManager`` all'apertura e
salvato su OK. Annulla scarta i cambi.

Il senso di gerarchia di severity viene trasmesso visivamente
(ordinamento + colore + etichetta "Sev 1 / 2 / 3") senza nascondere
nulla all'utente.
"""

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from WarningServices.Warning_types import (
    SEVERITY_COLORS,
    WARNING_CATALOG,
    WARNING_DOMAINS,
    WarningSeverity,
    color_for_severity,
)

if TYPE_CHECKING:
    from App_context import AppContext


SEVERITY_LABELS = {
    WarningSeverity.CONSISTENCY: "Severity 1 — Consistenza (sempre attivo)",
    WarningSeverity.INCONSISTENCY: "Severity 2 — Incoerenza dato",
    WarningSeverity.INFO: "Severity 3 — Informativo (anni passati)",
}


class QTWarningsSettingsDialog(QDialog):
    """Dialog di configurazione dei warning."""

    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.manager = app_context.warnings_visibility_manager

        self.setWindowTitle("Gestione Warnings")
        self.resize(720, 720)
        self.setModal(True)

        # Stato corrente (copia mutabile) — verra' salvato su OK.
        self._state = self.manager.snapshot()

        # Map (domain, type_key) -> QCheckBox per leggere lo stato finale.
        self._checkboxes: dict = {}

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Visibilità Warnings")
        f = title.font()
        f.setPointSize(15)
        f.setBold(True)
        title.setFont(f)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("padding: 12px;")
        root.addWidget(title)

        intro = QLabel(
            "Abilita o disabilita i warning mostrati sulle liste. "
            "I warning di gravità massima (Sev 1, consistenza database) "
            "non sono disabilitabili e restano visibili finché non vengono risolti."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("padding: 0 16px 8px 16px; color: palette(text);")
        root.addWidget(intro)

        legend = self._build_legend()
        root.addWidget(legend)

        # Scroll area con una sezione per dominio.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root.addWidget(scroll, stretch=1)

        container = QWidget()
        scroll.setWidget(container)
        body = QVBoxLayout(container)
        body.setContentsMargins(16, 8, 16, 16)
        body.setSpacing(12)

        for domain_key, domain_label in WARNING_DOMAINS:
            section = self._build_domain_section(domain_key, domain_label)
            body.addWidget(section)
        body.addStretch(1)

        # Bottoni OK / Annulla.
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _build_legend(self) -> QWidget:
        legend = QFrame()
        legend.setObjectName("WarningsLegend")
        legend.setStyleSheet(
            "#WarningsLegend { border: 1px solid palette(mid); border-radius: 6px; "
            "background-color: palette(alternate-base); }"
        )
        legend_layout = QHBoxLayout(legend)
        legend_layout.setContentsMargins(12, 6, 12, 6)
        legend_layout.setSpacing(20)
        for sev, label in SEVERITY_LABELS.items():
            entry = QHBoxLayout()
            entry.setSpacing(6)
            dot = QLabel()
            dot.setPixmap(self._severity_dot_pixmap(sev, size=12))
            entry.addWidget(dot)
            txt = QLabel(label)
            txt.setStyleSheet("color: palette(text);")
            entry.addWidget(txt)
            wrapper = QWidget()
            wrapper.setLayout(entry)
            legend_layout.addWidget(wrapper)
        legend_layout.addStretch(1)
        return legend

    def _build_domain_section(self, domain_key: str, domain_label: str) -> QWidget:
        frame = QFrame()
        frame.setObjectName("WarningsDomainFrame")
        frame.setStyleSheet(
            "#WarningsDomainFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 10, 14, 14)
        layout.setSpacing(8)

        title = QLabel(domain_label)
        f = title.font()
        f.setBold(True)
        f.setPointSize(13)
        title.setFont(f)
        layout.addWidget(title)

        warnings = WARNING_CATALOG.get(domain_key, [])
        # Ordina per severity crescente (1 in alto).
        warnings_sorted = sorted(warnings, key=lambda w: int(w[1]))

        for type_key, severity, label, description in warnings_sorted:
            row = self._build_warning_row(domain_key, type_key, severity, label, description)
            layout.addWidget(row)
        return frame

    def _build_warning_row(
        self,
        domain_key: str,
        type_key: str,
        severity: WarningSeverity,
        label: str,
        description: str,
    ) -> QWidget:
        row = QFrame()
        row.setObjectName("WarningRow")
        row.setStyleSheet("#WarningRow { padding: 4px; }")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(10)

        # Indicatore colore severity.
        dot = QLabel()
        dot.setPixmap(self._severity_dot_pixmap(severity, size=14))
        dot.setFixedWidth(20)
        row_layout.addWidget(dot, alignment=Qt.AlignTop)

        # Testo: label + descrizione.
        text_wrapper = QVBoxLayout()
        text_wrapper.setContentsMargins(0, 0, 0, 0)
        text_wrapper.setSpacing(2)
        label_lbl = QLabel(label)
        lf = label_lbl.font()
        lf.setBold(True)
        label_lbl.setFont(lf)
        text_wrapper.addWidget(label_lbl)
        desc_lbl = QLabel(description)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: palette(mid);")
        text_wrapper.addWidget(desc_lbl)
        text_widget = QWidget()
        text_widget.setLayout(text_wrapper)
        text_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row_layout.addWidget(text_widget, stretch=1)

        # Checkbox: lockata per i sev 1, abilitata altrimenti.
        checkbox = QCheckBox()
        if severity == WarningSeverity.CONSISTENCY:
            checkbox.setChecked(True)
            checkbox.setEnabled(False)
            checkbox.setToolTip(
                "Warning di consistenza database: sempre attivo, non disabilitabile."
            )
        else:
            initial = bool(
                (self._state.get(domain_key) or {}).get(type_key, True)
            )
            checkbox.setChecked(initial)
        row_layout.addWidget(checkbox, alignment=Qt.AlignTop | Qt.AlignRight)

        self._checkboxes[(domain_key, type_key)] = checkbox
        return row

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _severity_dot_pixmap(severity: WarningSeverity, size: int = 12) -> QPixmap:
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setBrush(QColor(color_for_severity(severity)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, size, size)
        painter.end()
        return pix

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _on_save(self):
        new_state: dict = {}
        for domain_key, _label in WARNING_DOMAINS:
            domain_data: dict = {}
            for type_key, severity, _l, _d in WARNING_CATALOG.get(domain_key, []):
                if severity == WarningSeverity.CONSISTENCY:
                    # Sev 1 non scritti: sempre attivi by design.
                    continue
                checkbox = self._checkboxes.get((domain_key, type_key))
                domain_data[type_key] = bool(checkbox.isChecked()) if checkbox else True
            new_state[domain_key] = domain_data

        self.manager.replace_all(new_state)
        self.accept()

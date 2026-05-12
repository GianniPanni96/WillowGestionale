"""
Banner di warning per i detail view.

Solo i warning di severity 1 (CONSISTENCY) vengono mostrati come banner
nel dettaglio: i sev 2/3 vivono unicamente nella list view (bordo
sinistro + tooltip).

Il banner non ha piu' un bottone "dismiss": un warning di severity 1
non e' dismissibile, sparisce solo quando l'utente risolve la causa
agendo sui campi del detail e salvando.

Il colore del bordo viene impostato dinamicamente per riflettere la
severity del warning passato (sempre rosso per i sev 1).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy

from WarningServices.Warning_types import (
    SEVERITY_COLORS,
    WarningInfo,
    WarningSeverity,
    color_for_severity,
)


class WarningBanner(QFrame):
    """Banner di warning senza bottone dismiss, con colore variabile."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("WarningBanner")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(15, 10, 15, 10)
        self._layout.setSpacing(15)

        self._text_label = QLabel("")
        self._text_label.setWordWrap(True)
        self._text_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._layout.addWidget(self._text_label, stretch=1, alignment=Qt.AlignVCenter)

        # Colore di default; verra' aggiornato in set_warning.
        self._apply_color(SEVERITY_COLORS[WarningSeverity.CONSISTENCY])

        # Inizialmente nascosto.
        self.setVisible(False)

    # ------------------------------------------------------------------
    # API pubblica
    # ------------------------------------------------------------------

    def set_warning(self, warning: "WarningInfo | str | None"):
        """Mostra il banner. Accetta un ``WarningInfo`` (caso normale)
        o una stringa (legacy). Se ``None`` o vuoto, il banner viene
        nascosto."""
        if warning is None or warning == "":
            self.hide_warning()
            return

        if isinstance(warning, WarningInfo):
            self._text_label.setText(warning.text)
            self._apply_color(warning.color)
        else:
            self._text_label.setText(str(warning))
            self._apply_color(SEVERITY_COLORS[WarningSeverity.CONSISTENCY])

        self.setVisible(True)

    def hide_warning(self):
        self._text_label.setText("")
        self.setVisible(False)

    # ------------------------------------------------------------------
    # Helper privati
    # ------------------------------------------------------------------

    def _apply_color(self, color_hex: str):
        self.setStyleSheet(
            "#WarningBanner { "
            f"border: 2px solid {color_hex}; "
            "border-radius: 6px; "
            "background-color: palette(midlight); "
            "}"
            "#WarningBanner QLabel { color: palette(shadow); }"
        )

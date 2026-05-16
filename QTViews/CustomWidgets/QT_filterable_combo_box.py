"""
Combo box filtrabile in chiave Qt.

Equivalente di Views/CustomWidgets/Filterable_combo_box.py: il widget e'
editabile per consentire la digitazione e il filtro inline (autocomplete
via QCompleter), ma vincola la selezione finale ad uno dei valori
presenti nella lista. Se al termine della digitazione il testo non
corrisponde ad alcuna voce esistente, il widget riconduce
automaticamente alla prima voce filtrata (o alla prima della lista
completa se il filtro e' vuoto) e mostra una segnalazione di warning
all'utente — bordo giallo + tooltip flash + tooltip permanente.

Cosi' la combo non puo' mai contenere un valore "libero" e quindi
nessun campo del DB rischia di ricevere stringhe non presenti negli
elenchi noti. L'unico modo per aggiungere una voce a un elenco resta la
sottoclasse QTCatalogFilterableComboBox per le sezioni del file
catalogs.json.

Subclassa QComboBox per restare drop-in con il resto del codice Qt
(currentText/findText/setCurrentIndex/etc. funzionano gia' come al
solito).
"""

from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QComboBox, QCompleter, QToolTip


class QTFilterableComboBox(QComboBox):
    """
    Combo editabile + autocomplete con commit forzato su valori validi.
    """

    WARNING_MESSAGE = (
        "Selezione dell'utente assente: valore selezionato in automatico dalla lista"
    )
    WARNING_COLOR = "#e39e27"
    DEFAULT_BORDER_QSS = ""
    WARNING_BORDER_QSS = "QLineEdit { border: 1px solid #e39e27; }"
    TOOLTIP_FLASH_DURATION_MS = 4000

    def __init__(
        self,
        parent=None,
        values: Optional[list] = None,
        autofill: bool = False,
        placeholder: str = "Seleziona…",
    ):
        super().__init__(parent)

        self._all_values: list = []
        self._autofill = autofill
        self._has_warning = False

        self.setEditable(True)
        # Evita che digitando un valore nuovo finisca nel modello: il
        # vincolo "valore della lista" lo garantiamo noi a fine commit.
        self.setInsertPolicy(QComboBox.NoInsert)

        line_edit = self.lineEdit()
        line_edit.setPlaceholderText(placeholder)
        line_edit.editingFinished.connect(self._validate_or_autofix)

        completer = self.completer()
        if completer is not None:
            completer.setCompletionMode(QCompleter.PopupCompletion)
            completer.setFilterMode(Qt.MatchContains)
            completer.setCaseSensitivity(Qt.CaseInsensitive)

        self.activated.connect(self._on_activated)

        self.set_values(values or [], preserve_current=False)
        if autofill and self._all_values:
            self.set_value(self._all_values[0])

    # ------------------------------------------------------------------
    # API "Filterable" coerente con il legacy
    # ------------------------------------------------------------------

    def value(self) -> str:
        text = self.currentText().strip()
        if text in self._selectable_values():
            return text
        return ""

    def set_value(self, value):
        if value is None:
            self.setCurrentIndex(-1)
            self.setEditText("")
            self._clear_warning()
            return
        text = str(value)
        idx = self.findText(text)
        if idx >= 0 and text in self._selectable_values():
            self.setCurrentIndex(idx)
            self._clear_warning()
        else:
            # Valore impostato programmaticamente ma non presente: lo
            # mostriamo nel line edit senza alzare un warning, sara' la
            # validazione su commit a riportarlo in linea se necessario.
            self.setEditText(text)

    def all_values(self) -> list:
        return list(self._all_values)

    def set_values(self, values, preserve_current: bool = True):
        current = self.currentText().strip() if preserve_current else None
        self._all_values = self._sort_values(values)
        self._rebuild_items()

        if current and current in self._selectable_values():
            self.set_value(current)
        elif self._autofill and self._all_values:
            self.set_value(self._all_values[0])
        else:
            self.setCurrentIndex(-1)
            self.setEditText("")
        self._clear_warning()

    # ------------------------------------------------------------------
    # Hook per le sottoclassi
    # ------------------------------------------------------------------

    def _selectable_values(self) -> list:
        """
        Lista dei valori che il widget considera "validi" come selezione
        finale. Le sottoclassi possono restringere/estendere questa
        lista (es. la catalog combo esclude la sentinella "+ Aggiungi…").
        """
        return list(self._all_values)

    def _rebuild_items(self):
        """
        Ricostruisce le voci nel modello del combo. Le sottoclassi
        possono override per aggiungere voci speciali (es. sentinella).
        """
        self.blockSignals(True)
        self.clear()
        self.addItems(self._all_values)
        self.blockSignals(False)

    # ------------------------------------------------------------------
    # Validazione e warning
    # ------------------------------------------------------------------

    def _on_activated(self, index: int):
        # Selezione esplicita dal popup: per definizione e' valida.
        if index >= 0:
            text = self.itemText(index)
            if text in self._selectable_values():
                self._clear_warning()

    def _validate_or_autofix(self):
        current = self.currentText().strip()
        selectable = self._selectable_values()
        if current in selectable:
            self._clear_warning()
            return

        # Stessa policy del legacy: prima si cerca tra le voci che
        # contengono il testo digitato; se nessuna match, si fallback
        # sulla prima voce della lista.
        if current:
            lower = current.lower()
            matches = [v for v in selectable if lower in v.lower()]
        else:
            matches = []
        fallback = matches[0] if matches else (selectable[0] if selectable else "")
        if not fallback:
            return

        self.blockSignals(True)
        idx = self.findText(fallback)
        if idx >= 0:
            self.setCurrentIndex(idx)
        else:
            self.setEditText(fallback)
        self.blockSignals(False)
        self._show_warning(self.WARNING_MESSAGE)

    def _show_warning(self, message: str):
        self._has_warning = True
        self.lineEdit().setStyleSheet(self.WARNING_BORDER_QSS)
        # Tooltip persistente sul widget (visibile in hover) +
        # tooltip flash subito dopo l'autofix per attirare l'attenzione.
        self.setToolTip(message)
        QToolTip.showText(QCursor.pos(), message, self, self.rect(), self.TOOLTIP_FLASH_DURATION_MS)

    def _clear_warning(self):
        if not self._has_warning:
            return
        self._has_warning = False
        self.lineEdit().setStyleSheet(self.DEFAULT_BORDER_QSS)
        self.setToolTip("")
        QToolTip.hideText()

    @staticmethod
    def _sort_values(values) -> list:
        return sorted([str(v) for v in (values or [])], key=lambda s: s.casefold())

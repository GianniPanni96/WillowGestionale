import os
from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from Backup_manager import (
    INVALID_REASON_INCOMPLETE,
    INVALID_REASON_LEGACY,
    INVALID_REASON_MISSING,
)

if TYPE_CHECKING:
    from App_context import AppContext


_MONTH_NAMES_ITA = {
    1: "Gen", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mag", 6: "Giu",
    7: "Lug", 8: "Ago", 9: "Set", 10: "Ott", 11: "Nov", 12: "Dic",
}


_INVALID_SHORT_LABELS = {
    INVALID_REASON_LEGACY: "versione precedente",
    INVALID_REASON_INCOMPLETE: "file mancanti",
    INVALID_REASON_MISSING: "cartella non trovata",
}


def _invalid_explanation(reason: str, missing: list) -> str:
    """Messaggio esteso, usato per tooltip e per il QMessageBox informativo."""
    if reason == INVALID_REASON_LEGACY:
        return (
            "Questo backup appartiene a una versione precedente dell'applicazione "
            "che utilizzava un unico file di configurazione (app_config_legacy.json).\n\n"
            "La struttura dei file di configurazione e' stata suddivisa in piu' file "
            "(app_settings, catalogs, fiscal_rules, historical_financial_data, "
            "recurring_expenses, gui_preferences) e questo backup non e' piu' "
            "compatibile.\n\n"
            "Per questo motivo non puo' essere importato."
        )
    if reason == INVALID_REASON_INCOMPLETE:
        missing_text = ", ".join(missing) if missing else "alcuni file di configurazione"
        return (
            "Questo backup e' incompleto: mancano uno o piu' file necessari "
            f"({missing_text}).\n\n"
            "Per questo motivo non puo' essere importato."
        )
    return "Backup non importabile (cartella mancante o non valida)."


def _format_interval_name(interval_name: str) -> str:
    """Formatta YYYYMMDD_to_YYYYMMDD nel formato '10-20 Ott' o '20 Ott - 30 Nov'."""
    try:
        parts = interval_name.split("_to_")
        if len(parts) != 2:
            return interval_name
        start = datetime.strptime(parts[0], "%Y%m%d")
        end = datetime.strptime(parts[1], "%Y%m%d")
        if start.month == end.month:
            return f"{start.day}-{end.day} {_MONTH_NAMES_ITA[start.month]}"
        return (
            f"{start.day} {_MONTH_NAMES_ITA[start.month]} - "
            f"{end.day} {_MONTH_NAMES_ITA[end.month]}"
        )
    except Exception:
        return interval_name


class QTLoadBackupDialog(QDialog):
    """
    Finestra "Carica un backup".

    Equivalente di MainWindow.open_load_backup legacy. Mostra in una lista
    raggruppata per intervallo i backup dell'anno corrente e permette di
    importarne uno con conferma esplicita.

    I backup non importabili (struttura legacy o incompleta) restano
    visibili ma sono disabilitati alla selezione e mostrati con uno stile
    differenziato; l'utente puo' cliccarci sopra per leggere il motivo
    della non importabilita'.
    """

    ROLE_BACKUP_PATH = Qt.UserRole + 1
    ROLE_BACKUP_DATETIME = Qt.UserRole + 2
    ROLE_IS_HEADER = Qt.UserRole + 3
    ROLE_IS_VALID = Qt.UserRole + 4
    ROLE_INVALID_REASON = Qt.UserRole + 5
    ROLE_MISSING_FILES = Qt.UserRole + 6

    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.backup_importer = app_context.backup_importer

        self.setWindowTitle("Carica un vecchio database tra i backup")
        self.resize(720, 650)
        self.setModal(True)

        self._build_ui()
        self._populate_list()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        title = QLabel("Seleziona un backup dell'anno corrente da importare")
        font = title.font()
        font.setBold(True)
        font.setPointSize(13)
        title.setFont(font)
        root.addWidget(title)

        legend = QLabel(
            "I backup mostrati in grigio appartengono a una versione precedente "
            "dell'applicazione o sono incompleti, e non possono essere importati. "
            "Cliccaci sopra per leggere il motivo."
        )
        legend.setWordWrap(True)
        legend_font = legend.font()
        legend_font.setItalic(True)
        legend.setFont(legend_font)
        root.addWidget(legend)

        self.list_widget = QListWidget()
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        root.addWidget(self.list_widget, stretch=1)

        selected_row = QHBoxLayout()
        selected_row.addWidget(QLabel("Backup selezionato:"))
        self.selected_label = QLabel("")
        font2 = self.selected_label.font()
        font2.setPointSize(12)
        self.selected_label.setFont(font2)
        selected_row.addWidget(self.selected_label, stretch=1)
        root.addLayout(selected_row)

        buttons = QHBoxLayout()
        self.refresh_btn = QPushButton("Aggiorna lista")
        self.refresh_btn.clicked.connect(self._populate_list)
        buttons.addWidget(self.refresh_btn)

        buttons.addStretch(1)

        self.import_btn = QPushButton("Importa backup selezionato")
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self._do_import)
        buttons.addWidget(self.import_btn)

        root.addLayout(buttons)

    # ------------------------------------------------------------------
    # Popolamento lista
    # ------------------------------------------------------------------

    def _populate_list(self):
        self.list_widget.clear()
        self.selected_label.setText("")
        self.import_btn.setEnabled(False)

        year = datetime.now().year
        backups = self.backup_importer.list_backups_for_year(year)

        if not backups:
            placeholder = QListWidgetItem(f"Nessun backup trovato per l'anno {year}")
            placeholder.setFlags(placeholder.flags() & ~Qt.ItemIsSelectable)
            placeholder.setData(self.ROLE_IS_HEADER, True)
            self.list_widget.addItem(placeholder)
            return

        # Raggruppa per intervallo (cartella padre del backup).
        by_interval: dict = {}
        for entry in backups:
            parts = entry["path"].split(os.sep)
            interval_folder = parts[-2] if len(parts) >= 2 else "Unknown"
            by_interval.setdefault(interval_folder, []).append(entry)

        sorted_intervals = sorted(
            by_interval.keys(),
            key=lambda x: datetime.strptime(x.split("_to_")[0], "%Y%m%d") if "_to_" in x else datetime.min,
            reverse=True,
        )

        for interval in sorted_intervals:
            header_text = f"———  {_format_interval_name(interval)}  ———"
            header_item = QListWidgetItem(header_text)
            header_item.setFlags(header_item.flags() & ~Qt.ItemIsSelectable)
            header_item.setData(self.ROLE_IS_HEADER, True)
            self.list_widget.addItem(header_item)

            interval_backups = sorted(
                by_interval[interval], key=lambda x: x["datetime"], reverse=True
            )
            for entry in interval_backups:
                self.list_widget.addItem(self._build_backup_item(entry))

    def _build_backup_item(self, entry: dict) -> QListWidgetItem:
        dt = entry["datetime"]
        is_valid = entry.get("valid", True)
        reason = entry.get("reason")
        missing = entry.get("missing", []) or []

        base_text = f"    {dt.strftime('%Y-%m-%d %H:%M:%S')}"
        if is_valid:
            text = base_text
        else:
            short = _INVALID_SHORT_LABELS.get(reason, "non importabile")
            text = f"{base_text}    —  non importabile ({short})"

        item = QListWidgetItem(text)
        item.setData(self.ROLE_BACKUP_PATH, entry["path"])
        item.setData(self.ROLE_BACKUP_DATETIME, dt)
        item.setData(self.ROLE_IS_HEADER, False)
        item.setData(self.ROLE_IS_VALID, is_valid)
        item.setData(self.ROLE_INVALID_REASON, reason)
        item.setData(self.ROLE_MISSING_FILES, list(missing))

        if not is_valid:
            # Mantieni l'item abilitato (cliccabile per mostrare il motivo),
            # ma non selezionabile come candidato per l'import. Lo stile
            # grigio + italic lo differenzia dai backup importabili.
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            item.setForeground(QBrush(QColor(140, 140, 140)))
            f = QFont(item.font())
            f.setItalic(True)
            item.setFont(f)
            item.setToolTip(_invalid_explanation(reason, missing))

        return item

    # ------------------------------------------------------------------
    # Selezione e import
    # ------------------------------------------------------------------

    def _on_selection_changed(self):
        item = self.list_widget.currentItem()
        if (
            item is None
            or item.data(self.ROLE_IS_HEADER)
            or not item.data(self.ROLE_IS_VALID)
        ):
            self.import_btn.setEnabled(False)
            self.selected_label.setText("")
            return
        dt = item.data(self.ROLE_BACKUP_DATETIME)
        self.selected_label.setText(str(dt))
        self.import_btn.setEnabled(True)

    def _on_item_clicked(self, item: QListWidgetItem):
        # Click su un backup non importabile: spiega all'utente perche'.
        # I header continuano a essere ignorati.
        if item is None or item.data(self.ROLE_IS_HEADER):
            return
        if item.data(self.ROLE_IS_VALID):
            return
        reason = item.data(self.ROLE_INVALID_REASON)
        missing = item.data(self.ROLE_MISSING_FILES) or []
        QMessageBox.information(
            self,
            "Backup non importabile",
            _invalid_explanation(reason, missing),
        )

    def _on_item_double_clicked(self, item):
        if item is None or item.data(self.ROLE_IS_HEADER):
            return
        if not item.data(self.ROLE_IS_VALID):
            # Il click singolo ha gia' mostrato il motivo: non duplichiamo
            # il popup sul doppio click.
            return
        self._do_import()

    def _do_import(self):
        item = self.list_widget.currentItem()
        if item is None or item.data(self.ROLE_IS_HEADER):
            return
        if not item.data(self.ROLE_IS_VALID):
            return
        path = item.data(self.ROLE_BACKUP_PATH)
        dt = item.data(self.ROLE_BACKUP_DATETIME)
        if not path:
            return

        backup_date = dt.strftime("%d/%m/%Y %H:%M")
        confirm = QMessageBox.question(
            self,
            "CONFERMA IMPORT BACKUP",
            f"Importare questo backup comporta la perdita dei dati inseriti "
            f"da {backup_date} ad oggi.\n\nDesideri continuare?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        success, msg = self.backup_importer.import_backup(path)
        if success:
            QMessageBox.information(self, "Import backup", "Import completato con successo.")
            self.accept()
        else:
            QMessageBox.critical(self, "Errore import backup", f"Si è verificato un errore: {msg}")

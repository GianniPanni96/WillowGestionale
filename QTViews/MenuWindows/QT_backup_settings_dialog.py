from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
)
from PySide6.QtCore import Qt

if TYPE_CHECKING:
    from App_context import AppContext


class QTBackupSettingsDialog(QDialog):
    """
    Finestra "Impostazioni di backup".

    Equivalente di MainWindow.open_backup_settings_window legacy. Permette
    di modificare il percorso di backup del database, l'intervallo di
    schedulazione, il numero massimo di backup per cartella, l'incremento
    in giorni tra cartelle e il percorso dei libri contabili.
    """

    SLIDER_RANGES = {
        "interval_minutes": (1, 120, 15),
        "max_backups": (1, 100, 35),
        "delta_days": (1, 30, 7),
    }

    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.config_manager = app_context.config_manager

        self.setWindowTitle("Impostazioni di backup")
        self.resize(640, 540)
        self.setModal(True)

        self.entries: dict = {}

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(15, 15, 15, 15)
        root.setSpacing(15)

        config = self.config_manager.load_config()
        backup_settings = config.get("backup_settings", {})

        # Sezione Database.
        db_group = QGroupBox("Impostazioni Database")
        db_layout = QFormLayout(db_group)
        db_layout.setSpacing(10)

        self._add_path_field(
            db_layout,
            label="Percorso di backup del database",
            default=backup_settings.get("backup_base_path", {}).get("value", ""),
            key="backup_base_path",
        )
        self._add_slider_field(
            db_layout,
            label="Frequenza esecuzione backup (minuti)",
            default=int(backup_settings.get("interval_minutes", {}).get("value", 15) or 15),
            key="interval_minutes",
        )
        self._add_slider_field(
            db_layout,
            label="Numero massimo di backup per cartella",
            default=int(backup_settings.get("max_backups", {}).get("value", 35) or 35),
            key="max_backups",
        )
        self._add_slider_field(
            db_layout,
            label="Frequenza generazione nuova cartella (giorni)",
            default=int(backup_settings.get("delta_days", {}).get("value", 7) or 7),
            key="delta_days",
        )

        root.addWidget(db_group)

        # Sezione libri contabili.
        books_group = QGroupBox("Impostazioni Libri Contabili")
        books_layout = QFormLayout(books_group)
        books_layout.setSpacing(10)

        self._add_path_field(
            books_layout,
            label="Percorso di backup dei libri contabili",
            default=backup_settings.get("backup_books_path", {}).get("value", ""),
            key="backup_books_path",
        )

        root.addWidget(books_group)

        root.addStretch(1)

        save_btn = QPushButton("Salva Impostazioni")
        save_btn.clicked.connect(self._save_backup_settings)
        root.addWidget(save_btn)

    def _add_path_field(self, layout: QFormLayout, label, default, key):
        edit = QLineEdit(str(default or ""))
        layout.addRow(QLabel(label), edit)
        self.entries[key] = edit

    def _add_slider_field(self, layout: QFormLayout, label, default, key):
        min_val, max_val, _ = self.SLIDER_RANGES[key]
        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(int(default))
        value_label = QLabel(str(int(default)))
        value_label.setMinimumWidth(40)
        slider.valueChanged.connect(lambda v, lbl=value_label: lbl.setText(str(v)))

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(slider, stretch=1)
        row.addWidget(value_label)
        layout.addRow(QLabel(label), row)
        self.entries[key] = slider

    # ------------------------------------------------------------------
    # Salvataggio
    # ------------------------------------------------------------------

    def _save_backup_settings(self):
        new_settings = {}
        for key, widget in self.entries.items():
            if isinstance(widget, QLineEdit):
                new_settings[key] = widget.text()
            elif isinstance(widget, QSlider):
                new_settings[key] = int(widget.value())

        try:
            self.config_manager.update_config_section("backup_settings", new_settings)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Errore salvataggio configurazione",
                f"Impossibile salvare la configurazione: {exc}",
            )
            return

        QMessageBox.information(
            self,
            "Salvataggio configurazione",
            "La configurazione è stata salvata con successo.\n"
            "Le nuove impostazioni saranno ricaricate al prossimo avvio dell'app.",
        )
        self.accept()

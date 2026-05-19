"""
Dialog di modifica del nome del collettivo di partite IVA.

Voce di menu "GUI > Nome del collettivo". Lo stato corrente viene letto
da ``AppSettingsManager.get_collective_name()`` (che fa fallback a
"Willow" se la chiave non esiste nel file di config, caso delle
installazioni in produzione il cui ``app_settings.json`` e' stato creato
prima dell'introduzione del campo).

Il salvataggio passa per ``set_collective_name``, che a sua volta usa
``update_section`` di ``AppSettingsManager`` per persistere il nuovo
valore in ``app_settings.json`` con la struttura
``{"general": {"collective_name": {"value": ..., "description": ...}}}``.
"""

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

if TYPE_CHECKING:
    from App_context import AppContext


class QTCollectiveNameDialog(QDialog):
    """Dialog single-field per il nome del collettivo."""

    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.app_settings_manager = app_context.config_manager.app_settings_manager

        self.setWindowTitle("Nome del collettivo")
        self.resize(480, 200)
        self.setModal(True)

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        title = QLabel("Nome del collettivo di partite IVA")
        f = title.font()
        f.setBold(True)
        f.setPointSize(13)
        title.setFont(f)
        root.addWidget(title)

        hint = QLabel(
            "Questo nome viene usato nell'interfaccia per identificare il "
            "gruppo (es. 'Fatture <nome>', 'Tasse <nome>', tooltip nei "
            "dettagli utente). Non modifica il nome del software, che resta "
            "'Willow Gestionale'."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(mid);")
        root.addWidget(hint)

        current = self.app_settings_manager.get_collective_name()
        self.name_edit = QLineEdit(current)
        self.name_edit.setPlaceholderText("es. Willow")
        root.addWidget(self.name_edit)

        root.addStretch(1)

        buttons_row = QHBoxLayout()
        buttons_row.addStretch(1)
        cancel_btn = QPushButton("Annulla")
        cancel_btn.clicked.connect(self.reject)
        buttons_row.addWidget(cancel_btn)
        save_btn = QPushButton("Salva")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save)
        buttons_row.addWidget(save_btn)
        root.addLayout(buttons_row)

    def _save(self):
        new_name = self.name_edit.text().strip()
        if not new_name:
            QMessageBox.warning(
                self,
                "Validazione",
                "Il nome del collettivo non puo' essere vuoto.",
            )
            return

        try:
            self.app_settings_manager.set_collective_name(new_name)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Errore salvataggio",
                f"Impossibile salvare il nome del collettivo: {exc}",
            )
            return

        QMessageBox.information(
            self,
            "Nome del collettivo aggiornato",
            "Il nuovo nome verra' applicato alle viste al prossimo refresh "
            "(o al riavvio dell'app).",
        )
        self.accept()

"""
Modale "salva il tuo recovery code".

Mostrata una volta sola dopo che un utente imposta o cambia password.
Forza l'utente a confermare di averlo trascritto/salvato (checkbox)
prima di poter chiudere la dialog. Niente bottone X / ESC, niente
modo di lasciare la pagina senza acknowledgement.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class QTRecoveryCodeShowDialog(QDialog):
    """Mostra ``recovery_code`` in chiaro con istruzioni di salvataggio."""

    def __init__(self, recovery_code: str, parent=None):
        super().__init__(parent)
        self.recovery_code = recovery_code

        self.setWindowTitle("Codice di recupero")
        self.setModal(True)
        self.resize(440, 280)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        title = QLabel("Salva questo codice di recupero")
        f = title.font()
        f.setBold(True)
        f.setPointSize(13)
        title.setFont(f)
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        info = QLabel(
            "Se dimentichi la password potrai reimpostarla solo usando questo codice.\n"
            "Stampalo o salvalo in un posto sicuro (offline). Non verra' mostrato di nuovo."
        )
        info.setWordWrap(True)
        info.setAlignment(Qt.AlignCenter)
        root.addWidget(info)

        code_row = QHBoxLayout()
        code_field = QLineEdit(self.recovery_code)
        code_field.setReadOnly(True)
        code_field.setAlignment(Qt.AlignCenter)
        code_font = code_field.font()
        code_font.setPointSize(14)
        code_font.setBold(True)
        code_font.setFamily("Consolas")
        code_field.setFont(code_font)
        code_row.addWidget(code_field, stretch=1)

        copy_btn = QPushButton("Copia")
        copy_btn.clicked.connect(self._copy_to_clipboard)
        code_row.addWidget(copy_btn)
        root.addLayout(code_row)

        self.ack_checkbox = QCheckBox(
            "Ho salvato il codice in un posto sicuro"
        )
        self.ack_checkbox.toggled.connect(self._on_ack_changed)
        root.addWidget(self.ack_checkbox)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.close_btn = QPushButton("Procedi")
        self.close_btn.setEnabled(False)
        self.close_btn.setMinimumSize(120, 32)
        self.close_btn.clicked.connect(self.accept)
        bottom.addWidget(self.close_btn)
        root.addLayout(bottom)

    def _copy_to_clipboard(self):
        QGuiApplication.clipboard().setText(self.recovery_code)

    def _on_ack_changed(self, checked: bool):
        self.close_btn.setEnabled(checked)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    def reject(self):
        return

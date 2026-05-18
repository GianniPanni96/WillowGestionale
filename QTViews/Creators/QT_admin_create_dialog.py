"""Dialog di creazione dell'amministratore di sistema.

Mostrato:
- al primo avvio dopo installazione (DB vuoto, prima dell'onboarding utenti)
- al primo avvio dopo aggiornamento (DB esistente che ha appena ricevuto
  la migrazione della tabella admin) — vedi MainQT.

Mandatory: non puo' essere chiuso con X o ESC. Una volta creato l'admin
viene mostrato il suo recovery code (una volta sola) e si procede.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

if TYPE_CHECKING:
    from App_context import AppContext


class QTAdminCreateDialog(QDialog):
    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.admin_controller = app_context.admin_controller

        self.setWindowTitle("Crea amministratore di sistema")
        self.setModal(True)
        self.resize(480, 380)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        self._created: bool = False
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        title = QLabel("Amministratore di sistema")
        f = title.font()
        f.setBold(True)
        f.setPointSize(14)
        title.setFont(f)
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        info = QLabel(
            "Prima di procedere serve creare l'utente amministratore. "
            "Un solo amministratore esiste nel sistema: potra' impostare "
            "password agli utenti che ne sono sprovvisti, forzare reset "
            "password, cancellare utenti e gestire i conti correnti.\n\n"
            "Scegli una password robusta: e' l'unica via per accedere "
            "alle funzioni amministrative."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("almeno 8 caratteri")
        form.addRow("Password admin:", self.password_edit)

        self.password_confirm_edit = QLineEdit()
        self.password_confirm_edit.setEchoMode(QLineEdit.Password)
        form.addRow("Conferma password:", self.password_confirm_edit)

        root.addLayout(form)

        warning = QLabel(
            "Attenzione: dopo la creazione ti verra' mostrato un recovery "
            "code che dovrai conservare con cura. E' l'unico modo per "
            "recuperare l'accesso admin se dimentichi la password."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #b97a00;")
        root.addWidget(warning)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.create_btn = QPushButton("Crea amministratore")
        self.create_btn.setMinimumSize(180, 38)
        self.create_btn.clicked.connect(self._on_create)
        buttons.addWidget(self.create_btn)
        buttons.addStretch(1)
        root.addLayout(buttons)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    def reject(self):
        return

    def _on_create(self):
        pwd = self.password_edit.text()
        pwd_confirm = self.password_confirm_edit.text()
        if pwd != pwd_confirm:
            QMessageBox.warning(self, "Validazione", "Le due password non coincidono.")
            return

        ok, msg, info = self.admin_controller.save_admin(pwd)
        if not ok:
            QMessageBox.critical(self, "Errore", msg)
            return

        recovery_code = (info or {}).get("recovery_code")
        if recovery_code:
            from QTViews.LoginViews.QT_recovery_code_show_dialog import QTRecoveryCodeShowDialog
            QTRecoveryCodeShowDialog(recovery_code, parent=self).exec()

        self._created = True
        self.accept()

    @property
    def created(self) -> bool:
        return self._created

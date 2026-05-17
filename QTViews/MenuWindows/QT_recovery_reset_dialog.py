"""
Dialog "Password dimenticata?".

Permette di reimpostare la password di un utente fornendo il recovery
code che e' stato consegnato quando la password era stata impostata.
Al successo invoca ``QTRecoveryCodeShowDialog`` per mostrare il nuovo
recovery code (l'operazione di reset ne genera uno nuovo, e il
vecchio viene invalidato).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from Gestionale_Enums import DBUsersColumns
from QTViews.MenuWindows.QT_recovery_code_show_dialog import QTRecoveryCodeShowDialog
from Utils.Validation_utils import ValidationUtils

if TYPE_CHECKING:
    from App_context import AppContext


class QTRecoveryResetDialog(QDialog):
    """Form: utente + recovery code + nuova password."""

    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.user_query_service = app_context.user_query_service
        self.user_controller = app_context.user_controller

        self.success = False
        self.reset_username: str | None = None
        self.reset_password: str | None = None

        self.setWindowTitle("Reimposta password con recovery code")
        self.setModal(True)
        self.resize(420, 320)

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        title = QLabel("Inserisci il recovery code dell'utente")
        title.setWordWrap(True)
        root.addWidget(title)

        form = QFormLayout()
        users = self.user_query_service.retrieve_users_map_list()
        self.username_combo = QComboBox()
        self.username_combo.addItems([
            f"{u[DBUsersColumns.FIRST_NAME.value]} {u[DBUsersColumns.LAST_NAME.value]}"
            for u in users
        ])
        form.addRow("Utente:", self.username_combo)

        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        form.addRow("Recovery code:", self.code_edit)

        self.pwd_edit = QLineEdit()
        self.pwd_edit.setEchoMode(QLineEdit.Password)
        self.pwd_edit.setPlaceholderText("almeno 8 caratteri")
        form.addRow("Nuova password:", self.pwd_edit)

        self.pwd_confirm_edit = QLineEdit()
        self.pwd_confirm_edit.setEchoMode(QLineEdit.Password)
        form.addRow("Conferma password:", self.pwd_confirm_edit)

        root.addLayout(form)

        warning = QLabel(
            "Attenzione: il reset svuota le credenziali del provider "
            "di fatturazione (se valorizzate)."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #b97a00;")
        root.addWidget(warning)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Annulla")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        submit = QPushButton("Reimposta")
        submit.setDefault(True)
        submit.clicked.connect(self._submit)
        buttons.addWidget(submit)
        root.addLayout(buttons)

    def _submit(self):
        username = self.username_combo.currentText()
        code = self.code_edit.text().strip()
        pwd = self.pwd_edit.text()
        pwd_confirm = self.pwd_confirm_edit.text()

        if not code:
            QMessageBox.warning(self, "Validazione", "Recovery code obbligatorio.")
            return
        if pwd != pwd_confirm:
            QMessageBox.warning(self, "Validazione", "Le due password non coincidono.")
            return
        is_valid, _ = ValidationUtils.validate_password_strength(pwd)
        if not is_valid:
            QMessageBox.warning(self, "Validazione", "Password troppo debole (min 8 caratteri).")
            return

        ok, msg, info = self.user_controller.reset_password_via_recovery(username, code, pwd)
        if not ok:
            QMessageBox.critical(self, "Reset fallito", msg)
            return

        new_code = (info or {}).get("recovery_code")
        if new_code:
            QTRecoveryCodeShowDialog(new_code, parent=self).exec()

        self.success = True
        self.reset_username = username
        self.reset_password = pwd
        self.accept()

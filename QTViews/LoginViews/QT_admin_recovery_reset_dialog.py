"""Reset password admin via recovery code."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
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


class QTAdminRecoveryResetDialog(QDialog):
    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.admin_controller = app_context.admin_controller

        self.success: bool = False
        self.new_password: str | None = None

        self.setWindowTitle("Recupero password admin")
        self.setModal(True)
        self.resize(440, 320)

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        title = QLabel("Reset password amministratore")
        f = title.font()
        f.setBold(True)
        f.setPointSize(13)
        title.setFont(f)
        root.addWidget(title)

        info = QLabel(
            "Inserisci il recovery code dell'amministratore e una nuova "
            "password. Al successo verra' generato un nuovo recovery code."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)

        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        form.addRow("Recovery code:", self.code_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("almeno 8 caratteri")
        form.addRow("Nuova password:", self.password_edit)

        self.password_confirm_edit = QLineEdit()
        self.password_confirm_edit.setEchoMode(QLineEdit.Password)
        form.addRow("Conferma password:", self.password_confirm_edit)

        root.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Annulla")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        confirm = QPushButton("Reimposta")
        confirm.setDefault(True)
        confirm.clicked.connect(self._on_confirm)
        buttons.addWidget(confirm)
        root.addLayout(buttons)

    def _on_confirm(self):
        code = self.code_edit.text().strip()
        pwd = self.password_edit.text()
        pwd_confirm = self.password_confirm_edit.text()
        if not code:
            QMessageBox.warning(self, "Validazione", "Recovery code obbligatorio.")
            return
        if pwd != pwd_confirm:
            QMessageBox.warning(self, "Validazione", "Le due password non coincidono.")
            return

        ok, msg, info = self.admin_controller.reset_password_via_recovery(code, pwd)
        if not ok:
            QMessageBox.critical(self, "Errore", msg)
            return

        recovery_code = (info or {}).get("recovery_code")
        if recovery_code:
            from QTViews.LoginViews.QT_recovery_code_show_dialog import QTRecoveryCodeShowDialog
            QTRecoveryCodeShowDialog(recovery_code, parent=self).exec()

        self.success = True
        self.new_password = pwd
        self.accept()

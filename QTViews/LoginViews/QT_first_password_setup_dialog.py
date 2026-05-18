"""Bootstrap dialog: imposta la prima password per un utente esistente.

Si attiva al boot quando ci sono utenti nel DB ma nessuno ha una
``password_login`` impostata (scenario di un'installazione che ha
appena ricevuto la migrazione crypto: nessuno puo' autenticarsi).

Permette di scegliere uno degli utenti senza password e di
impostargliela; ricicla ``UserController.update_user`` per la rotation
crypto e la generazione del recovery code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
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

if TYPE_CHECKING:
    from App_context import AppContext


class QTFirstPasswordSetupDialog(QDialog):
    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.user_query_service = app_context.user_query_service
        self.user_controller = app_context.user_controller

        self.success: bool = False
        self.target_user_id: int | None = None
        self.target_user_name: str | None = None
        self.target_password: str | None = None

        self.setWindowTitle("Imposta password al primo utente")
        self.setModal(True)
        self.resize(480, 360)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        self._users_without_pw = self._load_users_without_password()
        self._build_ui()

    def _load_users_without_password(self) -> list[dict]:
        users = self.user_query_service.retrieve_users_map_list() or []
        return [u for u in users if not u.get(DBUsersColumns.PASSWORD_LOGIN.value)]

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        title = QLabel("Imposta password a un utente")
        f = title.font()
        f.setBold(True)
        f.setPointSize(14)
        title.setFont(f)
        root.addWidget(title)

        info = QLabel(
            "Nessuno degli utenti esistenti ha una password di login. "
            "Per poter usare l'app scegli un utente e imposta una password. "
            "Potrai poi loggarti con quell'utente e impostare le password "
            "agli altri dal dettaglio utente.\n\n"
            "In alternativa, fai logout e accedi come amministratore "
            "per gestire le password di tutti gli utenti."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)

        self.user_combo = QComboBox()
        for u in self._users_without_pw:
            self.user_combo.addItem(
                f"{u[DBUsersColumns.FIRST_NAME.value]} {u[DBUsersColumns.LAST_NAME.value]}",
                userData=u,
            )
        form.addRow("Utente:", self.user_combo)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("almeno 8 caratteri")
        form.addRow("Password:", self.password_edit)

        self.password_confirm_edit = QLineEdit()
        self.password_confirm_edit.setEchoMode(QLineEdit.Password)
        form.addRow("Conferma password:", self.password_confirm_edit)

        root.addLayout(form)

        warning = QLabel(
            "Dopo il salvataggio verra' mostrato un recovery code: "
            "conservalo, e' l'unico modo per recuperare l'accesso "
            "se dimentichi la password."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #b97a00;")
        root.addWidget(warning)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.skip_btn = QPushButton("Salta (login admin)")
        self.skip_btn.clicked.connect(self._on_skip)
        buttons.addWidget(self.skip_btn)
        self.save_btn = QPushButton("Imposta password")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._on_save)
        buttons.addWidget(self.save_btn)
        root.addLayout(buttons)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    def reject(self):
        return

    def _on_skip(self):
        # L'utente preferisce loggarsi come admin: si accetta la dialog
        # senza target. Il chiamante (MainQT) interpretera' success=False
        # come "salta al login normale".
        self.success = False
        self.accept()

    def _on_save(self):
        idx = self.user_combo.currentIndex()
        if idx < 0:
            QMessageBox.warning(self, "Validazione", "Seleziona un utente.")
            return
        user = self.user_combo.itemData(idx)
        if not user:
            QMessageBox.warning(self, "Validazione", "Utente non valido.")
            return

        pwd = self.password_edit.text()
        pwd_confirm = self.password_confirm_edit.text()
        if pwd != pwd_confirm:
            QMessageBox.warning(self, "Validazione", "Le due password non coincidono.")
            return
        if not pwd:
            QMessageBox.warning(self, "Validazione", "La password e' obbligatoria.")
            return

        # update_user con i campi minimi richiesti per non incappare in
        # validation errors (PIVA, regime, anno, provider).
        from Fatturazione_elettronica_API import FatturazioneElettronicaProvider
        user_id = int(user[DBUsersColumns.ID.value])
        ok, msg, info = self.user_controller.update_user(user_id, {
            DBUsersColumns.PASSWORD_LOGIN.value: pwd,
            DBUsersColumns.FIRST_NAME.value: user[DBUsersColumns.FIRST_NAME.value],
            DBUsersColumns.LAST_NAME.value: user[DBUsersColumns.LAST_NAME.value],
            DBUsersColumns.PARTITA_IVA.value: user[DBUsersColumns.PARTITA_IVA.value],
            DBUsersColumns.REGIME_FISCALE.value: user[DBUsersColumns.REGIME_FISCALE.value],
            DBUsersColumns.ANNO_APERTURA_PIVA.value: user[DBUsersColumns.ANNO_APERTURA_PIVA.value],
            DBUsersColumns.PROVIDER_FATTURE.value: user.get(
                DBUsersColumns.PROVIDER_FATTURE.value,
                FatturazioneElettronicaProvider.NESSUNO.value,
            ),
        })
        if not ok:
            QMessageBox.critical(self, "Errore", msg)
            return

        recovery_code = (info or {}).get("recovery_code")
        if recovery_code:
            from QTViews.LoginViews.QT_recovery_code_show_dialog import QTRecoveryCodeShowDialog
            QTRecoveryCodeShowDialog(recovery_code, parent=self).exec()

        self.success = True
        self.target_user_id = user_id
        self.target_user_name = (
            f"{user[DBUsersColumns.FIRST_NAME.value]} {user[DBUsersColumns.LAST_NAME.value]}"
        )
        self.target_password = pwd
        self.accept()

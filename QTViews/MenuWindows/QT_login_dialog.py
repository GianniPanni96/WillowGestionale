from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from Model import DBUsersColumns
from Utils.View_utils import ViewUtils

if TYPE_CHECKING:
    from App_context import AppContext


class QTLoginDialog(QDialog):
    """
    Finestra di login utente.

    Quando ``mandatory=True`` (caso "forced login" all'avvio dell'app)
    la dialog non puo' essere chiusa via X o ESC: l'utente deve
    autenticarsi per proseguire. La chiusura programmatica via accept()
    e' sempre permessa.

    Pubblica su event_bus l'evento LOGIN_STATUS_CHANGED quando il login
    va a buon fine. La crypto session per-utente viene sbloccata da
    ``UserAuthService.check_password_for_login`` come parte della
    verifica password (vedi quel modulo).
    """

    def __init__(self, app_context: "AppContext", parent=None, mandatory: bool = False):
        super().__init__(parent)
        self.app_context = app_context
        self.user_query_service = app_context.user_query_service
        self.user_auth_service = app_context.user_auth_service
        self.event_bus = app_context.event_bus

        self.success = False
        self.user_id = -1
        self._mandatory = mandatory

        self.setWindowTitle("Esegui il login")
        self.resize(380, 320)
        self.setModal(True)

        if mandatory:
            self.setWindowFlag(Qt.WindowCloseButtonHint, False)
            self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("SCEGLI L'UTENTE E INSERISCI LA PASSWORD")
        layout.addWidget(title)

        users = self.user_query_service.retrieve_users_map_list()
        self.username_combo = QComboBox()
        self.username_combo.addItems([
            f"{u[DBUsersColumns.FIRST_NAME.value]} {u[DBUsersColumns.LAST_NAME.value]}"
            for u in users
        ])
        layout.addWidget(self.username_combo)

        layout.addWidget(QLabel("Password:"))
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.returnPressed.connect(self._try_login)
        layout.addWidget(self.password_edit)

        layout.addStretch(1)

        login_btn = QPushButton("Esegui il login")
        login_btn.clicked.connect(self._try_login)
        layout.addWidget(login_btn)

        forgot_btn = QPushButton("Password dimenticata?")
        forgot_btn.setFlat(True)
        forgot_btn.setStyleSheet("text-align: center; color: palette(highlight);")
        forgot_btn.clicked.connect(self._open_recovery_reset)
        layout.addWidget(forgot_btn)

    def keyPressEvent(self, event: QKeyEvent):
        # Blocca ESC quando la dialog e' obbligatoria.
        if self._mandatory and event.key() == Qt.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    def reject(self):
        # Disabilita il reject implicito (X / ESC) in modalita' mandatory.
        if self._mandatory:
            return
        super().reject()

    def _open_recovery_reset(self):
        # Import locale: il modulo importa QTLoginDialog indirettamente
        # via gli show-dialog, niente cicli ma teniamo l'import vicino
        # all'uso per non rallentare la finestra di login.
        from QTViews.MenuWindows.QT_recovery_reset_dialog import QTRecoveryResetDialog

        dialog = QTRecoveryResetDialog(app_context=self.app_context, parent=self)
        if dialog.exec() != QTRecoveryResetDialog.Accepted or not dialog.success:
            return
        # Pre-popola i campi del login con i dati appena reimpostati,
        # cosi' l'utente puo' completare il login con un click.
        if dialog.reset_username:
            idx = self.username_combo.findText(dialog.reset_username)
            if idx >= 0:
                self.username_combo.setCurrentIndex(idx)
        self.password_edit.setText(dialog.reset_password or "")
        self.password_edit.setFocus()

    def _try_login(self):
        username = self.username_combo.currentText()
        password = self.password_edit.text()
        success, message, user_id = self.user_auth_service.check_password_for_login(
            username, password
        )
        if success:
            QMessageBox.information(self, "Login", message)
            self.success = True
            self.user_id = user_id
            self.event_bus.publish(
                ViewUtils.EventBusKeys.LOGIN_STATUS_CHANGED.value,
                {"login_status": True, "logged_user_id": user_id},
            )
            self.accept()
        else:
            QMessageBox.warning(self, "Login", message)

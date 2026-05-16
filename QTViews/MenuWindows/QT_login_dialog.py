from typing import TYPE_CHECKING

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

    Equivalente di MainWindow.open_login_window della view legacy. Pubblica
    su event_bus l'evento LOGIN_STATUS_CHANGED quando il login va a buon
    fine, in modo coerente con il flusso customtkinter.
    """

    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.user_query_service = app_context.user_query_service
        self.user_auth_service = app_context.user_auth_service
        self.event_bus = app_context.event_bus

        self.success = False
        self.user_id = -1

        self.setWindowTitle("Esegui il login")
        self.resize(380, 320)
        self.setModal(True)

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

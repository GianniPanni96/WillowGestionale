from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
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
        self.persist_enabled: bool = False
        self.persist_minutes: int = 30
        self._mandatory = mandatory
        self._persist_supported = app_context.session_persistence_service.is_supported()

        self.setWindowTitle("Esegui il login")
        self.resize(420, 420)
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

        self._build_persist_widgets(layout)

        layout.addStretch(1)

        login_btn = QPushButton("Esegui il login")
        login_btn.clicked.connect(self._try_login)
        layout.addWidget(login_btn)

        forgot_btn = QPushButton("Password dimenticata?")
        forgot_btn.setFlat(True)
        forgot_btn.setStyleSheet("text-align: center; color: palette(highlight);")
        forgot_btn.clicked.connect(self._open_recovery_reset)
        layout.addWidget(forgot_btn)

    def _build_persist_widgets(self, layout: QVBoxLayout) -> None:
        """Toggle + slider per la persistenza della sessione dopo la
        chiusura dell'app. Su piattaforme dove la persistenza non e'
        supportata (no DPAPI) i widget vengono nascosti."""
        if not self._persist_supported:
            return

        self.persist_checkbox = QCheckBox("Mantieni l'accesso dopo la chiusura dell'app")
        layout.addWidget(self.persist_checkbox)

        slider_row = QWidget()
        slider_layout = QHBoxLayout(slider_row)
        slider_layout.setContentsMargins(0, 0, 0, 0)
        slider_layout.setSpacing(8)

        slider_layout.addWidget(QLabel("Durata:"))
        self.persist_slider = QSlider(Qt.Horizontal)
        self.persist_slider.setMinimum(5)
        self.persist_slider.setMaximum(60)
        self.persist_slider.setSingleStep(5)
        self.persist_slider.setPageStep(5)
        self.persist_slider.setTickInterval(5)
        self.persist_slider.setTickPosition(QSlider.TicksBelow)
        self.persist_slider.setValue(self.persist_minutes)
        self.persist_slider.setEnabled(False)

        self.persist_value_label = QLabel(f"{self.persist_minutes} min")
        self.persist_value_label.setFixedWidth(60)

        def _on_slider_changed(value: int) -> None:
            # Snap a multipli di 5.
            snapped = max(5, round(value / 5) * 5)
            if snapped != value:
                self.persist_slider.blockSignals(True)
                self.persist_slider.setValue(snapped)
                self.persist_slider.blockSignals(False)
            self.persist_value_label.setText(f"{snapped} min")

        self.persist_slider.valueChanged.connect(_on_slider_changed)
        self.persist_checkbox.toggled.connect(self.persist_slider.setEnabled)

        slider_layout.addWidget(self.persist_slider, stretch=1)
        slider_layout.addWidget(self.persist_value_label)
        layout.addWidget(slider_row)

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
            if self._persist_supported:
                self.persist_enabled = self.persist_checkbox.isChecked()
                self.persist_minutes = int(self.persist_slider.value())
            self.event_bus.publish(
                ViewUtils.EventBusKeys.LOGIN_STATUS_CHANGED.value,
                {"login_status": True, "logged_user_id": user_id, "is_admin": False},
            )
            self.accept()
        else:
            QMessageBox.warning(self, "Login", message)

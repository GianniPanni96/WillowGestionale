"""Dialog di login per l'amministratore di sistema.

A differenza del login utente, qui c'e' un solo "account" possibile
(l'admin). Mostra solo il campo password e un link "Password admin
dimenticata?" che apre il flusso di reset via recovery code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
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

from Utils.View_utils import ViewUtils

if TYPE_CHECKING:
    from App_context import AppContext


class QTAdminLoginDialog(QDialog):
    def __init__(self, app_context: "AppContext", parent=None, mandatory: bool = False):
        super().__init__(parent)
        self.app_context = app_context
        self.user_auth_service = app_context.user_auth_service
        self.event_bus = app_context.event_bus

        self.success: bool = False
        self.exit_requested: bool = False
        self.persist_enabled: bool = False
        self.persist_minutes: int = 30
        self._mandatory = mandatory
        self._persist_supported = app_context.session_persistence_service.is_supported()

        self.setWindowTitle("Login amministratore")
        self.resize(420, 340)
        self.setModal(True)

        if mandatory:
            self.setWindowFlag(Qt.WindowCloseButtonHint, False)
            self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("ACCESSO AMMINISTRATORE")
        f = title.font()
        f.setBold(True)
        title.setFont(f)
        layout.addWidget(title)

        layout.addWidget(QLabel(
            "Inserisci la password dell'amministratore di sistema."
        ))

        layout.addWidget(QLabel("Password:"))
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.returnPressed.connect(self._try_login)
        layout.addWidget(self.password_edit)

        self._build_persist_widgets(layout)

        layout.addStretch(1)

        login_btn = QPushButton("Entra come amministratore")
        login_btn.clicked.connect(self._try_login)
        layout.addWidget(login_btn)

        forgot_btn = QPushButton("Password admin dimenticata?")
        forgot_btn.setFlat(True)
        forgot_btn.setStyleSheet("text-align: center; color: palette(highlight);")
        forgot_btn.clicked.connect(self._open_recovery_reset)
        layout.addWidget(forgot_btn)

        if self._mandatory:
            exit_btn = QPushButton("Esci dall'app")
            exit_btn.setFlat(True)
            exit_btn.setStyleSheet("text-align: center; color: palette(mid);")
            exit_btn.clicked.connect(self._exit_app)
            layout.addWidget(exit_btn)

    def _build_persist_widgets(self, layout: QVBoxLayout) -> None:
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
        if self._mandatory and event.key() == Qt.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    def reject(self):
        if self._mandatory:
            return
        super().reject()

    def _open_recovery_reset(self):
        from QTViews.LoginViews.QT_admin_recovery_reset_dialog import QTAdminRecoveryResetDialog

        dialog = QTAdminRecoveryResetDialog(app_context=self.app_context, parent=self)
        if dialog.exec() != QDialog.Accepted or not dialog.success:
            return
        # Pre-popola la password reimpostata.
        self.password_edit.setText(dialog.new_password or "")
        self.password_edit.setFocus()

    def _exit_app(self):
        self.exit_requested = True
        self.done(QDialog.Rejected)

    def _try_login(self):
        password = self.password_edit.text()
        ok, message = self.user_auth_service.check_admin_password_for_login(password)
        if ok:
            self.success = True
            if self._persist_supported:
                self.persist_enabled = self.persist_checkbox.isChecked()
                self.persist_minutes = int(self.persist_slider.value())
            self.event_bus.publish(
                ViewUtils.EventBusKeys.LOGIN_STATUS_CHANGED.value,
                {"login_status": True, "logged_user_id": -1, "is_admin": True},
            )
            self.accept()
        else:
            QMessageBox.warning(self, "Login admin", message)

"""
Dialog di onboarding al primo avvio dell'app.

Si attiva quando il DB non contiene alcun utente: guida l'utilizzatore
a creare il primo conto corrente e il primo utente "amministratore"
con password obbligatoria. La password e' indispensabile perche'
diventa il seed della chiave per-utente del nuovo modello crypto.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from Fatturazione_elettronica_API import FatturazioneElettronicaProvider
from Gestionale_Enums import (
    DBAccountsColumns,
    DBUsersColumns,
    RegimeFiscale,
    UserStatus,
)
from Utils.Validation_utils import ValidationUtils

if TYPE_CHECKING:
    from App_context import AppContext


_AMOUNT_RE = re.compile(r"^\d+(\.\d{1,2})?$")


class QTOnboardingDialog(QDialog):
    """Wizard a due passi: account + primo utente con password."""

    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.account_controller = app_context.account_controller
        self.account_query_service = app_context.account_query_service
        self.user_controller = app_context.user_controller
        self.user_query_service = app_context.user_query_service
        self.user_auth_service = app_context.user_auth_service

        self.created_user_id: int | None = None
        self.created_user_name: str | None = None
        self.created_user_password: str | None = None

        self.setWindowTitle("Configurazione iniziale - Willow Gestionale")
        self.setModal(True)
        self.resize(520, 640)
        # L'onboarding non puo' essere chiuso con la X o ESC: senza un
        # utente l'app non puo' funzionare.
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        title = QLabel("Benvenuto in Willow Gestionale")
        f = title.font()
        f.setBold(True)
        f.setPointSize(15)
        title.setFont(f)
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        subtitle = QLabel(
            "Per iniziare ad usare l'app crea il tuo primo conto corrente\n"
            "e il primo utente con password di accesso."
        )
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: palette(mid);")
        root.addWidget(subtitle)

        # --- Sezione Conto Corrente ---
        root.addWidget(self._section_header("1. Conto corrente"))
        account_form = QFormLayout()
        account_form.setLabelAlignment(Qt.AlignLeft)
        self.account_name_edit = QLineEdit()
        self.account_name_edit.setPlaceholderText("es. Conto Principale")
        account_form.addRow("Nome conto:", self.account_name_edit)

        self.account_balance_edit = QLineEdit()
        self.account_balance_edit.setPlaceholderText("0.00")
        account_form.addRow("Saldo iniziale (EUR):", self.account_balance_edit)
        root.addLayout(account_form)

        # --- Sezione Utente ---
        root.addWidget(self._section_header("2. Primo utente"))
        user_form = QFormLayout()
        user_form.setLabelAlignment(Qt.AlignLeft)

        self.first_name_edit = QLineEdit()
        user_form.addRow("Nome:", self.first_name_edit)

        self.last_name_edit = QLineEdit()
        user_form.addRow("Cognome:", self.last_name_edit)

        self.piva_edit = QLineEdit()
        self.piva_edit.setPlaceholderText("11 cifre")
        user_form.addRow("Partita IVA:", self.piva_edit)

        self.email_edit = QLineEdit()
        user_form.addRow("Email (opzionale):", self.email_edit)

        self.regime_combo = QComboBox()
        self.regime_combo.addItems([item.value for item in RegimeFiscale])
        user_form.addRow("Regime fiscale:", self.regime_combo)

        self.anno_combo = QComboBox()
        current_year = datetime.now().year
        self.anno_combo.addItems([str(y) for y in range(2000, current_year + 1)])
        self.anno_combo.setCurrentText(str(current_year))
        user_form.addRow("Anno apertura P. IVA:", self.anno_combo)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("almeno 8 caratteri")
        user_form.addRow("Password di login:", self.password_edit)

        self.password_confirm_edit = QLineEdit()
        self.password_confirm_edit.setEchoMode(QLineEdit.Password)
        user_form.addRow("Conferma password:", self.password_confirm_edit)

        root.addLayout(user_form)

        warning = QLabel(
            "Attenzione: la password protegge i dati sensibili dell'utente. "
            "Se la dimentichi, i dati cifrati con quella password andranno persi."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #b97a00;")
        root.addWidget(warning)

        # --- Bottoni ---
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.create_btn = QPushButton("Crea e accedi")
        self.create_btn.setMinimumSize(160, 38)
        self.create_btn.clicked.connect(self._on_create)
        buttons.addWidget(self.create_btn)
        buttons.addStretch(1)
        root.addLayout(buttons)

    @staticmethod
    def _section_header(text: str) -> QFrame:
        frame = QFrame()
        f_layout = QVBoxLayout(frame)
        f_layout.setContentsMargins(0, 8, 0, 0)
        lbl = QLabel(text)
        f = lbl.font()
        f.setBold(True)
        f.setPointSize(12)
        lbl.setFont(f)
        f_layout.addWidget(lbl)
        return frame

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent):
        # Blocca chiusura via ESC.
        if event.key() == Qt.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    def reject(self):
        # Disattiva la chiusura forzata.
        return

    def _on_create(self):
        if not self._validate():
            return

        account_data = {
            DBAccountsColumns.NAME.value: self.account_name_edit.text().strip(),
            DBAccountsColumns.INIT_BALANCE.value: self.account_balance_edit.text().strip() or "0",
        }
        ok, msg = self.account_controller.save_account(account_data)
        if not ok:
            QMessageBox.critical(self, "Errore creazione conto", msg)
            return

        account = self.account_query_service.retrieve_account_map_by_name(
            account_data[DBAccountsColumns.NAME.value]
        )
        if not account:
            QMessageBox.critical(self, "Errore", "Conto creato ma non recuperabile dal DB.")
            return

        password = self.password_edit.text()
        first = self.first_name_edit.text().strip()
        last = self.last_name_edit.text().strip()

        user_data = {
            DBUsersColumns.FIRST_NAME.value: first,
            DBUsersColumns.LAST_NAME.value: last,
            DBUsersColumns.PARTITA_IVA.value: self.piva_edit.text().strip(),
            DBUsersColumns.EMAIL.value: self.email_edit.text().strip(),
            DBUsersColumns.REGIME_FISCALE.value: self.regime_combo.currentText(),
            DBUsersColumns.ANNO_APERTURA_PIVA.value: self.anno_combo.currentText(),
            DBUsersColumns.CONTO_CORRENTE_ID.value: account[DBAccountsColumns.ID.value],
            DBUsersColumns.STATUS.value: UserStatus.ATTIVO.value,
            DBUsersColumns.PROVIDER_FATTURE.value: FatturazioneElettronicaProvider.NESSUNO.value,
            DBUsersColumns.USERNAME_PROVIDER.value: "",
            DBUsersColumns.PASSWORD_PROVIDER.value: "",
            "_plain_password": password,
        }
        ok, msg, info = self.user_controller.save_user(user_data)
        if not ok:
            QMessageBox.critical(self, "Errore creazione utente", msg)
            return

        row = self.user_query_service.retrieve_user_by_fullname(first, last)
        if not row:
            QMessageBox.critical(self, "Errore", "Utente creato ma non recuperabile dal DB.")
            return

        recovery_code = (info or {}).get("recovery_code")
        if recovery_code:
            from QTViews.MenuWindows.QT_recovery_code_show_dialog import QTRecoveryCodeShowDialog
            QTRecoveryCodeShowDialog(recovery_code, parent=self).exec()

        self.created_user_id = int(row[0])
        self.created_user_name = f"{first} {last}"
        self.created_user_password = password
        self.accept()

    # ------------------------------------------------------------------
    # Validazioni
    # ------------------------------------------------------------------

    def _validate(self) -> bool:
        if not self.account_name_edit.text().strip():
            QMessageBox.warning(self, "Validazione", "Il nome del conto e' obbligatorio.")
            return False
        balance = self.account_balance_edit.text().strip() or "0"
        if not _AMOUNT_RE.fullmatch(balance):
            QMessageBox.warning(self, "Validazione", "Saldo iniziale non valido (es. 1234.56).")
            return False

        if not self.first_name_edit.text().strip():
            QMessageBox.warning(self, "Validazione", "Il nome utente e' obbligatorio.")
            return False
        if not self.last_name_edit.text().strip():
            QMessageBox.warning(self, "Validazione", "Il cognome utente e' obbligatorio.")
            return False
        if not ValidationUtils.validate_partita_iva(self.piva_edit.text().strip()):
            QMessageBox.warning(self, "Validazione", "Partita IVA non valida (11 cifre).")
            return False
        email = self.email_edit.text().strip()
        if email and not ValidationUtils.validate_email(email):
            QMessageBox.warning(self, "Validazione", "Email non valida.")
            return False

        pwd = self.password_edit.text()
        pwd_confirm = self.password_confirm_edit.text()
        if pwd != pwd_confirm:
            QMessageBox.warning(self, "Validazione", "Le due password non coincidono.")
            return False
        is_valid, _ = ValidationUtils.validate_password_strength(pwd)
        if not is_valid:
            QMessageBox.warning(self, "Validazione", "Password troppo debole (minimo 8 caratteri).")
            return False
        return True

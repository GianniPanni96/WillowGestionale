"""
Versione Qt del creator utente.

Differenze dalla legacy:
- la parte di login al provider di fatturazione elettronica e' omessa
  dalla UI (la funzionalita' non e' implementata): il campo
  ``PROVIDER_FATTURE`` viene sempre persistito a
  ``FatturazioneElettronicaProvider.NESSUNO`` e i due campi username
  /password vengono salvati come stringhe vuote. Il combo del provider
  resta nascosto dall'interfaccia.
- struttura QDialog modale, in linea con gli altri creator Qt (form +
  validazioni a perdita di focus, salvataggio via
  ``UserController.save_user``).
"""

import os
from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
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


PHOTO_PREVIEW_SIZE = 140


class QTUserCreateViewH(QDialog):
    """QDialog modale per la creazione di un nuovo utente."""

    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.user_controller = app_context.user_controller
        self.user_query_service = app_context.user_query_service
        self.accounts_query_service = app_context.account_query_service

        # ID dell'utente creato, leggibile dal chiamante dopo accept().
        self.created_user_id: int | None = None

        self.setWindowTitle("Aggiungi Nuovo Utente")
        self.resize(520, 700)
        self.setModal(True)

        # State.
        self._photo_path: str = ""
        self._widgets: dict = {}
        self._errors: dict = {}

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll, stretch=1)

        container = QWidget()
        scroll.setWidget(container)
        form = QFormLayout(container)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self._build_photo_row(form)
        self._build_entry(form, DBUsersColumns.FIRST_NAME.value, "Nome", with_error=True)
        self._build_entry(form, DBUsersColumns.LAST_NAME.value, "Cognome", with_error=True)
        self._build_entry(form, DBUsersColumns.PARTITA_IVA.value, "Partita IVA", with_error=True)
        self._build_entry(form, DBUsersColumns.CODICE_FISCALE.value, "Codice Fiscale")
        self._build_entry(form, DBUsersColumns.TELEFONO.value, "Telefono")
        self._build_entry(form, DBUsersColumns.EMAIL.value, "Email", with_error=True)

        # Password di login (opzionale ma necessaria per poter loggare
        # l'utente; abilita anche la cifratura per-utente dei dati
        # sensibili). Se lasciata vuota l'utente esiste ma non puo'
        # autenticarsi finche' un admin non gliela imposta dal dettaglio.
        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.Password)
        self._password_edit.setPlaceholderText("almeno 8 caratteri (opzionale)")
        form.addRow(QLabel("Password login"), self._password_edit)
        self._password_confirm_edit = QLineEdit()
        self._password_confirm_edit.setEchoMode(QLineEdit.Password)
        form.addRow(QLabel("Conferma password"), self._password_confirm_edit)
        self._password_error = QLabel("")
        self._password_error.setStyleSheet("color: #d62929;")
        form.addRow("", self._password_error)

        # Conto corrente (obbligatorio: c'e' un check di esistenza prima
        # di aprire il dialog, qui mostriamo i conti disponibili).
        accounts = self.accounts_query_service.retrieve_accounts_map_list() or []
        account_combo = QComboBox()
        account_combo.addItems([a[DBAccountsColumns.NAME.value] for a in accounts])
        form.addRow(QLabel("Conto Corrente"), account_combo)
        self._widgets[DBUsersColumns.CONTO_CORRENTE_ID.value] = account_combo

        # Regime fiscale.
        regime_combo = QComboBox()
        regime_combo.addItems([item.value for item in RegimeFiscale])
        form.addRow(QLabel("Regime Fiscale"), regime_combo)
        self._widgets[DBUsersColumns.REGIME_FISCALE.value] = regime_combo

        # Anno apertura partita IVA.
        anno_combo = QComboBox()
        current_year = datetime.now().year
        anno_combo.addItems([str(y) for y in range(2000, current_year + 1)])
        anno_combo.setCurrentText(str(current_year))
        form.addRow(QLabel("Anno di apertura P. IVA"), anno_combo)
        self._widgets[DBUsersColumns.ANNO_APERTURA_PIVA.value] = anno_combo

        # Pulsanti.
        bottom = QHBoxLayout()
        bottom.setContentsMargins(20, 10, 20, 20)
        bottom.addStretch(1)
        save_button = QPushButton("Salva Utente")
        save_button.setMinimumSize(140, 40)
        save_button.clicked.connect(self._save_user_data)
        bottom.addWidget(save_button)
        bottom.addStretch(1)
        outer.addLayout(bottom)

        self._bind_validations()

    def _build_photo_row(self, form: QFormLayout):
        wrapper = QWidget()
        v = QVBoxLayout(wrapper)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)

        self._photo_preview = QLabel("Nessuna immagine")
        self._photo_preview.setAlignment(Qt.AlignCenter)
        self._photo_preview.setFixedSize(PHOTO_PREVIEW_SIZE, PHOTO_PREVIEW_SIZE)
        self._photo_preview.setStyleSheet(
            "QLabel {"
            " background-color: palette(window);"
            " border: 1px dashed palette(mid);"
            " border-radius: 6px;"
            " color: palette(mid);"
            "}"
        )
        v.addWidget(self._photo_preview, alignment=Qt.AlignCenter)

        row = QHBoxLayout()
        choose_btn = QPushButton("Scegli Immagine…")
        choose_btn.clicked.connect(self._on_choose_photo)
        row.addWidget(choose_btn)
        clear_btn = QPushButton("Rimuovi")
        clear_btn.clicked.connect(self._on_clear_photo)
        row.addWidget(clear_btn)
        v.addLayout(row)

        self._photo_name_lbl = QLabel("Nessuna immagine selezionata")
        self._photo_name_lbl.setStyleSheet("color: palette(mid);")
        v.addWidget(self._photo_name_lbl, alignment=Qt.AlignCenter)

        form.addRow(QLabel("Immagine Profilo"), wrapper)

    def _build_entry(self, form: QFormLayout, key: str, label: str, with_error: bool = False):
        edit = QLineEdit()
        form.addRow(QLabel(label), edit)
        self._widgets[key] = edit
        if with_error:
            err = QLabel("")
            err.setStyleSheet("color: #d62929;")
            form.addRow("", err)
            self._errors[key] = err

    # ------------------------------------------------------------------
    # Validazioni
    # ------------------------------------------------------------------

    def _bind_validations(self):
        def _required(key, message):
            edit: QLineEdit = self._widgets[key]
            err: QLabel = self._errors[key]
            edit.editingFinished.connect(
                lambda: err.setText("" if edit.text().strip() else message)
            )

        _required(DBUsersColumns.FIRST_NAME.value, "Il nome non può essere vuoto.")
        _required(DBUsersColumns.LAST_NAME.value, "Il cognome non può essere vuoto.")

        piva = self._widgets[DBUsersColumns.PARTITA_IVA.value]
        piva_err = self._errors[DBUsersColumns.PARTITA_IVA.value]

        def _val_piva():
            v = piva.text().strip()
            if v and v.isdigit() and ValidationUtils.validate_partita_iva(v):
                piva_err.setText("")
            else:
                piva_err.setText("La partita IVA deve essere un numero di 11 cifre.")

        piva.editingFinished.connect(_val_piva)

        email = self._widgets[DBUsersColumns.EMAIL.value]
        email_err = self._errors[DBUsersColumns.EMAIL.value]

        def _val_email():
            v = email.text().strip()
            if not v:
                email_err.setText("")  # email opzionale a livello UI
                return
            if ValidationUtils.validate_email(v):
                email_err.setText("")
            else:
                email_err.setText("Inserisci una e-mail valida.")

        email.editingFinished.connect(_val_email)

    # ------------------------------------------------------------------
    # Foto
    # ------------------------------------------------------------------

    def _on_choose_photo(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleziona un'immagine",
            "",
            "Immagini (*.png *.jpg *.jpeg *.gif *.bmp)",
        )
        if not path:
            return
        self._photo_path = path
        self._photo_name_lbl.setText(os.path.basename(path))
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self._photo_preview.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self._photo_preview.setPixmap(scaled)
            self._photo_preview.setText("")

    def _on_clear_photo(self):
        self._photo_path = ""
        self._photo_preview.clear()
        self._photo_preview.setText("Nessuna immagine")
        self._photo_name_lbl.setText("Nessuna immagine selezionata")

    # ------------------------------------------------------------------
    # Salvataggio
    # ------------------------------------------------------------------

    def _save_user_data(self):
        account_name = self._widgets[DBUsersColumns.CONTO_CORRENTE_ID.value].currentText().strip()
        account = self.accounts_query_service.retrieve_account_map_by_name(account_name)
        if not account:
            QMessageBox.critical(self, "ERRORE", "Conto corrente non valido.")
            return

        pwd = self._password_edit.text()
        pwd_confirm = self._password_confirm_edit.text()
        if pwd or pwd_confirm:
            if pwd != pwd_confirm:
                self._password_error.setText("Le password non coincidono.")
                return
            is_valid, _ = ValidationUtils.validate_password_strength(pwd)
            if not is_valid:
                self._password_error.setText("Password troppo debole (minimo 8 caratteri).")
                return
        self._password_error.setText("")

        user_data = {
            DBUsersColumns.FIRST_NAME.value: self._widgets[DBUsersColumns.FIRST_NAME.value].text().strip(),
            DBUsersColumns.LAST_NAME.value: self._widgets[DBUsersColumns.LAST_NAME.value].text().strip(),
            DBUsersColumns.PARTITA_IVA.value: self._widgets[DBUsersColumns.PARTITA_IVA.value].text().strip(),
            DBUsersColumns.CODICE_FISCALE.value: self._widgets[DBUsersColumns.CODICE_FISCALE.value].text().strip(),
            DBUsersColumns.TELEFONO.value: self._widgets[DBUsersColumns.TELEFONO.value].text().strip(),
            DBUsersColumns.EMAIL.value: self._widgets[DBUsersColumns.EMAIL.value].text().strip(),
            DBUsersColumns.REGIME_FISCALE.value: self._widgets[DBUsersColumns.REGIME_FISCALE.value].currentText(),
            DBUsersColumns.ANNO_APERTURA_PIVA.value: self._widgets[DBUsersColumns.ANNO_APERTURA_PIVA.value].currentText(),
            DBUsersColumns.PHOTO_PATH.value: self._photo_path,
            DBUsersColumns.CONTO_CORRENTE_ID.value: account[DBAccountsColumns.ID.value],
            DBUsersColumns.STATUS.value: UserStatus.ATTIVO.value,
            # Provider FE non implementato a livello UI: default a "nessuno".
            DBUsersColumns.PROVIDER_FATTURE.value: FatturazioneElettronicaProvider.NESSUNO.value,
            DBUsersColumns.USERNAME_PROVIDER.value: "",
            DBUsersColumns.PASSWORD_PROVIDER.value: "",
        }
        if pwd:
            # Chiave fuori-enum letta da UserController.save_user per
            # generare hash + salt + crypto_check del nuovo utente.
            user_data["_plain_password"] = pwd

        success, message, info = self.user_controller.save_user(user_data)
        if not success:
            QMessageBox.critical(self, "ERRORE", message)
            return

        recovery_code = (info or {}).get("recovery_code")
        if recovery_code:
            from QTViews.LoginViews.QT_recovery_code_show_dialog import QTRecoveryCodeShowDialog
            QTRecoveryCodeShowDialog(recovery_code, parent=self).exec()

        # Recuperiamo l'id assegnato dal DB usando fullname (come la legacy).
        try:
            row = self.user_query_service.retrieve_user_by_fullname(
                user_data[DBUsersColumns.FIRST_NAME.value],
                user_data[DBUsersColumns.LAST_NAME.value],
            )
            self.created_user_id = row[0] if row else None
        except Exception:
            self.created_user_id = None

        self.accept()

"""
Versione Qt del creator conto corrente.

La legacy (``Views/Accounts_view.py``) non aveva un file dedicato: la
creazione avveniva inline tramite ``open_add_account_window`` con una
``CTkToplevel`` contenente nome + saldo iniziale e validazione a perdita
di focus. Qui replichiamo quella logica come ``QDialog`` modale, in
linea con gli altri creator Qt: form + validazioni su ``editingFinished``
e salvataggio via ``AccountController.save_account``.
"""

import re
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
    QWidget,
)

from Gestionale_Enums import DBAccountsColumns

if TYPE_CHECKING:
    from App_context import AppContext


# Stessa regex di validazione monetaria usata dalla legacy.
_MONEY_RE = re.compile(r"^\d+(\.\d{2})?$")


class QTAccountCreateViewH(QDialog):
    """QDialog modale per la creazione di un nuovo conto corrente."""

    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.account_controller = app_context.account_controller
        self.accounts_query_service = app_context.account_query_service

        # ID del conto creato, leggibile dal chiamante dopo accept().
        self.created_account_id: int | None = None

        self.setWindowTitle("Aggiungi Nuovo Conto")
        self.resize(380, 260)
        self.setModal(True)

        self._widgets: dict = {}
        self._errors: dict = {}

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        container = QWidget()
        outer.addWidget(container, stretch=1)
        form = QFormLayout(container)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self._build_entry(form, DBAccountsColumns.NAME.value, "Nome Conto")
        self._build_entry(form, DBAccountsColumns.INIT_BALANCE.value, "Saldo Iniziale")

        bottom = QHBoxLayout()
        bottom.setContentsMargins(20, 10, 20, 20)
        bottom.addStretch(1)
        save_button = QPushButton("Salva Conto Corrente")
        save_button.setMinimumSize(160, 40)
        save_button.clicked.connect(self._save_account_data)
        bottom.addWidget(save_button)
        bottom.addStretch(1)
        outer.addLayout(bottom)

        self._bind_validations()

    def _build_entry(self, form: QFormLayout, key: str, label: str):
        edit = QLineEdit()
        form.addRow(QLabel(label), edit)
        self._widgets[key] = edit
        err = QLabel("")
        err.setStyleSheet("color: #d62929;")
        err.setWordWrap(True)
        form.addRow("", err)
        self._errors[key] = err

    # ------------------------------------------------------------------
    # Validazioni (perdita di focus, come la legacy)
    # ------------------------------------------------------------------

    def _bind_validations(self):
        name_edit = self._widgets[DBAccountsColumns.NAME.value]
        name_err = self._errors[DBAccountsColumns.NAME.value]
        name_edit.editingFinished.connect(
            lambda: name_err.setText(
                "" if name_edit.text().strip() else "Il campo non può essere vuoto."
            )
        )

        balance_edit = self._widgets[DBAccountsColumns.INIT_BALANCE.value]
        balance_err = self._errors[DBAccountsColumns.INIT_BALANCE.value]

        def _val_balance():
            v = balance_edit.text().strip()
            if _MONEY_RE.fullmatch(v):
                balance_err.setText("")
            else:
                balance_err.setText(
                    "Inserimento non valido: inserire un numero monetario con "
                    "due cifre decimali (es. 123.45)"
                )

        balance_edit.editingFinished.connect(_val_balance)

    # ------------------------------------------------------------------
    # Salvataggio
    # ------------------------------------------------------------------

    def _save_account_data(self):
        name = self._widgets[DBAccountsColumns.NAME.value].text().strip()
        init_balance = self._widgets[DBAccountsColumns.INIT_BALANCE.value].text().strip()

        if not name:
            QMessageBox.critical(self, "ERRORE", "Il nome del conto non può essere vuoto.")
            return
        if not _MONEY_RE.fullmatch(init_balance):
            QMessageBox.critical(
                self,
                "ERRORE",
                "Saldo iniziale non valido: usa una cifra monetaria con due "
                "decimali (es. 123.45).",
            )
            return

        account_data = {
            DBAccountsColumns.NAME.value: name,
            DBAccountsColumns.INIT_BALANCE.value: init_balance,
        }

        success, message = self.account_controller.save_account(account_data)
        if not success:
            QMessageBox.critical(self, "ERRORE", message)
            return

        # Recuperiamo l'id assegnato dal DB (come la legacy).
        try:
            account_map = self.accounts_query_service.retrieve_last_account_insert_map()
            self.created_account_id = (
                account_map[DBAccountsColumns.ID.value] if account_map else None
            )
        except Exception:
            self.created_account_id = None

        self.accept()

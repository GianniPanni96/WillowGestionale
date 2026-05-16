"""
Versione Qt del creator bonifico.

Replica la logica di ``Views/Creators/Transfer_create_view.py``:
- form con CAUSALE (descrizione), IMPORTO e CONTO RICEVENTE;
- la lista dei conti riceventi esclude quello mittente (non ha senso
  trasferire un saldo a se stessi);
- validazioni su perdita di focus (causale non vuota; importo nel
  formato monetario ``\\d+(\\.\\d{2})?``);
- se non esistono altri conti oltre al mittente, il bottone "Esegui
  Bonifico" e' disabilitato e la combo riceventi mostra un placeholder.

A salvataggio riuscito notifica l'``update_controller`` come faceva la
legacy (``on_adding_transfer``) cosi' che le view legacy ancora attive
ricalcolino i saldi.
"""

import re
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
    QWidget,
)

from Gestionale_Enums import DBAccountsColumns, DBTransfersColumns

if TYPE_CHECKING:
    from App_context import AppContext


# Stessa label "logica" usata dalla legacy: il controller la cerca per
# nome per risolvere il conto ricevente.
RECEIVER_ACCOUNT_LABEL = "CONTO RICEVENTE"

# Regex monetaria coerente con la legacy.
_MONEY_RE = re.compile(r"^\d+(\.\d{2})?$")


class QTTransferCreateViewH(QDialog):
    """QDialog modale per la creazione di un bonifico in uscita."""

    def __init__(
        self,
        app_context: "AppContext",
        sender_account_id: int,
        parent=None,
    ):
        super().__init__(parent)
        self.app_context = app_context
        self.sender_account_id = sender_account_id

        self.account_query_service = app_context.account_query_service
        self.transfer_controller = app_context.transfer_controller
        self.update_controller = getattr(app_context, "update_controller", None)

        # Esposto per il chiamante.
        self.transfer_saved: bool = False

        self.setWindowTitle("Esegui Bonifico")
        self.resize(480, 360)
        self.setModal(True)

        self._widgets: dict = {}
        self._errors: dict = {}
        self._accounts_name_list: list[str] = []

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Header informativo con il conto mittente (utile perche' il
        # dialog si apre da una card e l'utente vede subito "da dove"
        # sta partendo il bonifico).
        sender = self.account_query_service.retrieve_account_map_by_id(
            self.sender_account_id
        )
        sender_name = (
            sender.get(DBAccountsColumns.NAME.value, "") if sender else ""
        ) or "Conto sconosciuto"
        header = QLabel(f"Bonifico in uscita da: <b>{sender_name}</b>")
        header.setContentsMargins(20, 16, 20, 4)
        outer.addWidget(header)

        container = QWidget()
        outer.addWidget(container, stretch=1)
        form = QFormLayout(container)
        form.setContentsMargins(20, 12, 20, 12)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        # Causale.
        desc_edit = QLineEdit()
        form.addRow(QLabel("Causale"), desc_edit)
        self._widgets[DBTransfersColumns.DESCRIPTION.value] = desc_edit
        desc_err = QLabel("")
        desc_err.setStyleSheet("color: #d62929;")
        desc_err.setWordWrap(True)
        form.addRow("", desc_err)
        self._errors[DBTransfersColumns.DESCRIPTION.value] = desc_err

        # Importo.
        amount_edit = QLineEdit()
        form.addRow(QLabel("Importo"), amount_edit)
        self._widgets[DBTransfersColumns.AMOUNT.value] = amount_edit
        amount_err = QLabel("")
        amount_err.setStyleSheet("color: #d62929;")
        amount_err.setWordWrap(True)
        form.addRow("", amount_err)
        self._errors[DBTransfersColumns.AMOUNT.value] = amount_err

        # Combo conto ricevente: esclude il mittente.
        accounts_map_list = self.account_query_service.retrieve_accounts_map_list() or []
        self._accounts_name_list = [
            a[DBAccountsColumns.NAME.value]
            for a in accounts_map_list
            if a[DBAccountsColumns.ID.value] != self.sender_account_id
        ]
        receiver_combo = QComboBox()
        if self._accounts_name_list:
            receiver_combo.addItems(self._accounts_name_list)
        else:
            receiver_combo.addItem("Nessun altro conto esistente nel sistema")
            receiver_combo.setEnabled(False)
        form.addRow(QLabel("Conto Ricevente"), receiver_combo)
        self._widgets[RECEIVER_ACCOUNT_LABEL] = receiver_combo

        # Action bar.
        bottom = QHBoxLayout()
        bottom.setContentsMargins(20, 10, 20, 20)
        bottom.addStretch(1)

        self.save_button = QPushButton("Esegui Bonifico")
        self.save_button.setMinimumSize(160, 40)
        self.save_button.clicked.connect(self._save_transfer_data)
        if not self._accounts_name_list:
            self.save_button.setEnabled(False)
        bottom.addWidget(self.save_button)

        cancel_button = QPushButton("Annulla")
        cancel_button.setMinimumSize(120, 40)
        cancel_button.clicked.connect(self.reject)
        bottom.addWidget(cancel_button)

        bottom.addStretch(1)
        outer.addLayout(bottom)

        self._bind_validations()

    # ------------------------------------------------------------------
    # Validazioni (perdita di focus, come la legacy)
    # ------------------------------------------------------------------

    def _bind_validations(self):
        desc_edit: QLineEdit = self._widgets[DBTransfersColumns.DESCRIPTION.value]
        desc_err: QLabel = self._errors[DBTransfersColumns.DESCRIPTION.value]
        desc_edit.editingFinished.connect(
            lambda: desc_err.setText(
                "" if desc_edit.text().strip() else "Il campo non può essere vuoto."
            )
        )

        amount_edit: QLineEdit = self._widgets[DBTransfersColumns.AMOUNT.value]
        amount_err: QLabel = self._errors[DBTransfersColumns.AMOUNT.value]

        def _val_amount():
            v = amount_edit.text().strip()
            if _MONEY_RE.fullmatch(v):
                amount_err.setText("")
            else:
                amount_err.setText(
                    "Inserimento non valido: inserire un numero monetario con "
                    "due cifre decimali (es. 123.45)"
                )

        amount_edit.editingFinished.connect(_val_amount)

    # ------------------------------------------------------------------
    # Salvataggio
    # ------------------------------------------------------------------

    def _save_transfer_data(self):
        description = self._widgets[DBTransfersColumns.DESCRIPTION.value].text().strip()
        amount = self._widgets[DBTransfersColumns.AMOUNT.value].text().strip()
        receiver_name = self._widgets[RECEIVER_ACCOUNT_LABEL].currentText().strip()

        if not description:
            QMessageBox.critical(self, "ERRORE", "La causale non può essere vuota.")
            return
        if not _MONEY_RE.fullmatch(amount):
            QMessageBox.critical(
                self,
                "ERRORE",
                "Importo non valido: usa una cifra monetaria con due decimali "
                "(es. 123.45).",
            )
            return
        if receiver_name not in self._accounts_name_list:
            QMessageBox.critical(self, "ERRORE", "Conto ricevente non valido.")
            return

        transfer_data = {
            DBTransfersColumns.DESCRIPTION.value: description,
            DBTransfersColumns.AMOUNT.value: amount,
            RECEIVER_ACCOUNT_LABEL: receiver_name,
            DBTransfersColumns.SENDER_ACCOUNT_ID.value: self.sender_account_id,
        }

        success, message = self.transfer_controller.save_transfer(transfer_data)
        if not success:
            QMessageBox.critical(self, "ERRORE", message)
            return

        # Notifica le view legacy ancora attive (la Accounts_view legacy
        # registra ``update_accounts_balances`` su questo evento).
        if self.update_controller is not None:
            try:
                self.update_controller.on_adding_transfer()
            except Exception:
                pass

        self.transfer_saved = True
        QMessageBox.information(self, "BONIFICO ESEGUITO", message)
        self.accept()

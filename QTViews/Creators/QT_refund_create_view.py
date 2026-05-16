"""
Versione QT del creator di un rimborso.

Equivalente di Views/Creators/Refund_create_view.RefundCreateView,
realizzato come QDialog modale sulla scia di QTPaymentCreateViewH:
QScrollArea + QFormLayout, stessa convenzione widget/error_labels e
notifica al chiamante via ``on_refund_created(refund_id)``.

I campi e la logica di dominio sono invariati:
- nome rimborso (validato non vuoto);
- importo monetario (validato come ``\\d+(\\.\\d{2})?``);
- data di emissione tramite QDateEdit;
- cliente come QTFilterableComboBox sull'elenco clienti;
- conto come QComboBox sull'elenco conti.
"""

import re
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
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

from Gestionale_Enums import (
    DBAccountsColumns,
    DBClientsColumns,
    DBRefundsColumns,
)
from QTViews.CustomWidgets.QT_filterable_combo_box import QTFilterableComboBox

if TYPE_CHECKING:
    from App_context import AppContext


class QTRefundCreateViewH(QDialog):
    """
    QDialog modale per la creazione di un nuovo rimborso.
    """

    CLIENT_NAME_FIELD = "NOME CLIENTE"
    ACCOUNT_NAME_FIELD = "NOME CONTO"

    def __init__(self, app_context: "AppContext", parent=None, on_refund_created=None):
        super().__init__(parent)

        self.app_context = app_context
        self.refund_controller = app_context.refund_controller
        self.refunds_query_service = app_context.refunds_query_service
        self.clients_query_service = app_context.clients_query_service
        self.accounts_query_service = app_context.account_query_service
        self.on_refund_created = on_refund_created

        self.setWindowTitle("Aggiungi Nuovo Rimborso")
        self.resize(560, 600)
        self.setModal(True)

        self.refund_widgets: dict = {}
        self.refund_labels: dict = {}
        self.error_labels: dict = {}

        self._build_ui()
        self._initialize_default_values()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        outer.addWidget(self.scroll, stretch=1)

        container = QWidget()
        self.scroll.setWidget(container)

        self.form_layout = QFormLayout(container)
        self.form_layout.setContentsMargins(20, 20, 20, 20)
        self.form_layout.setSpacing(8)
        self.form_layout.setLabelAlignment(Qt.AlignLeft)
        self.form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self._build_simple_entry(DBRefundsColumns.REFUND_NAME.value, "Nome Rimborso", with_error=True)
        self._build_simple_entry(DBRefundsColumns.REFUND_AMOUNT.value, "Importo (€)", with_error=True)
        self._build_refund_date_row()
        self._build_client_row()
        self._build_account_row()

        bottom = QHBoxLayout()
        bottom.setContentsMargins(20, 10, 20, 20)
        bottom.addStretch(1)
        self.save_button = QPushButton("Salva Rimborso")
        self.save_button.setMinimumSize(140, 40)
        self.save_button.clicked.connect(self._save_refund_data)
        bottom.addWidget(self.save_button)
        bottom.addStretch(1)
        outer.addLayout(bottom)

        self._bind_validations()

    def _build_simple_entry(self, key, label_text, with_error=False):
        edit = QLineEdit()
        label = QLabel(label_text)
        self.form_layout.addRow(label, edit)
        self.refund_widgets[key] = edit
        self.refund_labels[key] = label

        if with_error:
            error = QLabel("")
            error.setStyleSheet("color: #d62929;")
            self.form_layout.addRow("", error)
            self.error_labels[key] = error

    def _build_refund_date_row(self):
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("yyyy-MM-dd")
        date_edit.setDate(QDate.currentDate())
        label = QLabel("Data Rimborso")
        self.form_layout.addRow(label, date_edit)
        self.refund_widgets[DBRefundsColumns.REFUND_DATE.value] = date_edit
        self.refund_labels[DBRefundsColumns.REFUND_DATE.value] = label

    def _build_client_row(self):
        clients = self.clients_query_service.retrieve_clients_map_list()
        combo = QTFilterableComboBox(
            values=[c[DBClientsColumns.NAME.value] for c in clients],
            placeholder="Cerca cliente…",
            autofill=True,
        )
        label = QLabel(self.CLIENT_NAME_FIELD)
        self.form_layout.addRow(label, combo)
        self.refund_widgets[self.CLIENT_NAME_FIELD] = combo
        self.refund_labels[self.CLIENT_NAME_FIELD] = label

    def _build_account_row(self):
        accounts = self.accounts_query_service.retrieve_accounts_map_list()
        combo = QComboBox()
        combo.addItems([account[DBAccountsColumns.NAME.value] for account in accounts])
        label = QLabel(self.ACCOUNT_NAME_FIELD)
        self.form_layout.addRow(label, combo)
        self.refund_widgets[self.ACCOUNT_NAME_FIELD] = combo
        self.refund_labels[self.ACCOUNT_NAME_FIELD] = label

    # ------------------------------------------------------------------
    # Validazioni
    # ------------------------------------------------------------------

    def _bind_validations(self):
        name_edit: QLineEdit = self.refund_widgets[DBRefundsColumns.REFUND_NAME.value]
        name_error = self.error_labels[DBRefundsColumns.REFUND_NAME.value]

        def _validate_name():
            if not name_edit.text().strip():
                name_error.setText("Il campo non puo essere vuoto.")
            else:
                name_error.setText("")

        name_edit.editingFinished.connect(_validate_name)

        amount_edit: QLineEdit = self.refund_widgets[DBRefundsColumns.REFUND_AMOUNT.value]
        amount_error = self.error_labels[DBRefundsColumns.REFUND_AMOUNT.value]

        def _validate_amount():
            value = amount_edit.text().strip()
            if re.fullmatch(r"^\d+(\.\d{2})?$", value):
                amount_error.setText("")
            else:
                amount_error.setText(
                    "Inserimento non valido: usare un importo monetario con due decimali (es. 123.45)"
                )

        amount_edit.editingFinished.connect(_validate_amount)

    # ------------------------------------------------------------------
    # Inizializzazione default
    # ------------------------------------------------------------------

    def _initialize_default_values(self):
        clients = self.clients_query_service.retrieve_clients_map_list()
        if clients:
            self.refund_widgets[self.CLIENT_NAME_FIELD].set_value(
                clients[0][DBClientsColumns.NAME.value]
            )
        accounts = self.accounts_query_service.retrieve_accounts_map_list()
        if accounts:
            account_combo: QComboBox = self.refund_widgets[self.ACCOUNT_NAME_FIELD]
            account_combo.setCurrentText(accounts[0][DBAccountsColumns.NAME.value])

    # ------------------------------------------------------------------
    # Salvataggio
    # ------------------------------------------------------------------

    def _collect_refund_data(self):
        refund_data = {}
        for key, widget in self.refund_widgets.items():
            if isinstance(widget, QTFilterableComboBox):
                refund_data[key] = widget.value()
            elif isinstance(widget, QComboBox):
                refund_data[key] = widget.currentText().strip()
            elif isinstance(widget, QLineEdit):
                refund_data[key] = widget.text().strip()
            elif isinstance(widget, QDateEdit):
                refund_data[key] = widget.date().toString("yyyy-MM-dd")
        return refund_data

    def _save_refund_data(self):
        refund_data = self._collect_refund_data()
        success, message = self.refund_controller.save_refund(refund_data)
        if not success:
            QMessageBox.critical(self, "ERRORE", message)
            return

        refund_map = self.refunds_query_service.retrieve_last_refund_insert_map()
        refund_id = refund_map[DBRefundsColumns.ID.value] if refund_map else None

        if self.on_refund_created is not None and refund_id is not None:
            self.on_refund_created(refund_id)

        self.accept()

"""
Versione QT del creator di un salario.

Equivalente di Views/Creators/Salary_create_view.SalaryCreateView,
realizzato come QDialog modale sulla scia di QTRefundCreateViewH /
QTPaymentCreateViewH: QScrollArea + QFormLayout, stessa convenzione
widget/error_labels e notifica al chiamante via
``on_salary_created(salary_id)``.

Logica di dominio invariata:
- selezione UTENTE (QComboBox con "<nome> <cognome>") che, al cambio,
  auto-compila il NOME del salario come "<utente> - <mese>/<anno>" e
  seleziona di default il conto corrente associato all'utente;
- data tramite QDateEdit;
- importo monetario (validato con ``\\d+(\\.\\d{2})?``);
- conto come QComboBox sulla lista conti correnti.
"""

import re
from datetime import datetime
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
    DBSalariesColumns,
    DBUsersColumns,
)

if TYPE_CHECKING:
    from App_context import AppContext


class QTSalaryCreateViewH(QDialog):
    """
    QDialog modale per la creazione di un nuovo salario.
    """

    USER_NAME_FIELD = "NOME UTENTE"
    ACCOUNT_NAME_FIELD = "CONTO"

    def __init__(self, app_context: "AppContext", parent=None, on_salary_created=None):
        super().__init__(parent)

        self.app_context = app_context
        self.salary_controller = app_context.salary_controller
        self.salary_query_service = app_context.salary_query_service
        self.user_query_service = app_context.user_query_service
        self.accounts_query_service = app_context.account_query_service
        self.on_salary_created = on_salary_created
        self.today = datetime.now()

        self.setWindowTitle("Aggiungi Nuovo Salario")
        self.resize(560, 620)
        self.setModal(True)

        self.salary_widgets: dict = {}
        self.salary_labels: dict = {}
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

        self._build_user_row()
        self._build_simple_entry(DBSalariesColumns.NAME.value, "Nome Salario", with_error=True)
        self._build_date_row()
        self._build_simple_entry(DBSalariesColumns.AMOUNT.value, "Importo (€)", with_error=True)
        self._build_account_row()

        bottom = QHBoxLayout()
        bottom.setContentsMargins(20, 10, 20, 20)
        bottom.addStretch(1)
        self.save_button = QPushButton("Salva Salario")
        self.save_button.setMinimumSize(140, 40)
        self.save_button.clicked.connect(self._save_salary_data)
        bottom.addWidget(self.save_button)
        bottom.addStretch(1)
        outer.addLayout(bottom)

        self._bind_validations()

    def _build_user_row(self):
        users = self.user_query_service.retrieve_users_map_list()
        combo = QComboBox()
        combo.addItems([
            f"{u[DBUsersColumns.FIRST_NAME.value]} {u[DBUsersColumns.LAST_NAME.value]}"
            for u in users
        ])
        combo.currentTextChanged.connect(self._on_user_changed)
        label = QLabel(self.USER_NAME_FIELD)
        self.form_layout.addRow(label, combo)
        self.salary_widgets[self.USER_NAME_FIELD] = combo
        self.salary_labels[self.USER_NAME_FIELD] = label

    def _build_simple_entry(self, key, label_text, with_error=False):
        edit = QLineEdit()
        label = QLabel(label_text)
        self.form_layout.addRow(label, edit)
        self.salary_widgets[key] = edit
        self.salary_labels[key] = label
        if with_error:
            error = QLabel("")
            error.setStyleSheet("color: #d62929;")
            self.form_layout.addRow("", error)
            self.error_labels[key] = error

    def _build_date_row(self):
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("yyyy-MM-dd")
        date_edit.setDate(QDate.currentDate())
        label = QLabel("Data Salario")
        self.form_layout.addRow(label, date_edit)
        self.salary_widgets[DBSalariesColumns.DATE.value] = date_edit
        self.salary_labels[DBSalariesColumns.DATE.value] = label

    def _build_account_row(self):
        accounts = self.accounts_query_service.retrieve_accounts_map_list()
        combo = QComboBox()
        combo.addItems([a[DBAccountsColumns.NAME.value] for a in accounts])
        label = QLabel(self.ACCOUNT_NAME_FIELD)
        self.form_layout.addRow(label, combo)
        self.salary_widgets[self.ACCOUNT_NAME_FIELD] = combo
        self.salary_labels[self.ACCOUNT_NAME_FIELD] = label

    # ------------------------------------------------------------------
    # Validazioni
    # ------------------------------------------------------------------

    def _bind_validations(self):
        name_edit: QLineEdit = self.salary_widgets[DBSalariesColumns.NAME.value]
        name_error: QLabel = self.error_labels[DBSalariesColumns.NAME.value]

        def _validate_name():
            if not name_edit.text().strip():
                name_error.setText("Il campo non puo essere vuoto.")
            else:
                name_error.setText("")

        name_edit.editingFinished.connect(_validate_name)

        amount_edit: QLineEdit = self.salary_widgets[DBSalariesColumns.AMOUNT.value]
        amount_error: QLabel = self.error_labels[DBSalariesColumns.AMOUNT.value]

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
    # Default
    # ------------------------------------------------------------------

    def _initialize_default_values(self):
        user_combo: QComboBox = self.salary_widgets[self.USER_NAME_FIELD]
        if user_combo.count() > 0:
            self._on_user_changed(user_combo.currentText())

    # ------------------------------------------------------------------
    # Callback dinamici
    # ------------------------------------------------------------------

    def _on_user_changed(self, selected_value):
        # Stessa logica della legacy: auto-fill del nome e del conto.
        if not selected_value:
            return
        user = self.user_query_service.retrieve_user_map_by_extended_name(selected_value.strip())
        if not user:
            return

        # Nome del salario: "<utente> - <mese>/<anno>".
        name_edit: QLineEdit = self.salary_widgets[DBSalariesColumns.NAME.value]
        name_edit.setText(f"{selected_value.strip()} - {self.today.strftime('%m/%Y')}")

        # Conto: di default quello associato all'utente.
        account = self.accounts_query_service.retrieve_account_map_by_id(
            user.get(DBUsersColumns.CONTO_CORRENTE_ID.value)
        )
        if account:
            account_combo: QComboBox = self.salary_widgets[self.ACCOUNT_NAME_FIELD]
            idx = account_combo.findText(account[DBAccountsColumns.NAME.value])
            if idx >= 0:
                account_combo.setCurrentIndex(idx)

    # ------------------------------------------------------------------
    # Salvataggio
    # ------------------------------------------------------------------

    def _collect_salary_data(self):
        salary_data = {}
        for key, widget in self.salary_widgets.items():
            if isinstance(widget, QComboBox):
                salary_data[key] = widget.currentText().strip()
            elif isinstance(widget, QLineEdit):
                salary_data[key] = widget.text().strip()
            elif isinstance(widget, QDateEdit):
                salary_data[key] = widget.date().toString("yyyy-MM-dd")
        return salary_data

    def _save_salary_data(self):
        salary_data = self._collect_salary_data()
        success, message = self.salary_controller.save_salary(salary_data)
        if not success:
            QMessageBox.critical(self, "ERRORE", message)
            return

        salary_map = self.salary_query_service.retrieve_last_salary_insert_map()
        salary_id = salary_map[DBSalariesColumns.ID.value] if salary_map else None

        if self.on_salary_created is not None and salary_id is not None:
            self.on_salary_created(salary_id)

        self.accept()

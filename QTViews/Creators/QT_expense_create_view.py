"""
Versione QT del creator di una spesa.

Equivalente di Views/Creators/Expense_create_view.ExpenseCreateView,
realizzato come QDialog modale sulla scia di QTPaymentCreateViewH /
QTRefundCreateViewH: QScrollArea + QFormLayout, stessa convenzione
widget/error_labels e notifica al chiamante via
``on_expense_created(expense_id)``.

Logica dinamica riportata fedelmente dalla legacy:
- selezione FORNITORE che auto-compila un prefisso visivo "<fornitore> - "
  davanti al nome della spesa;
- combo CATEGORIA agganciata al catalogo ``expenses_category`` via
  QTCatalogFilterableComboBox.bound_to_section: alla scelta della
  categoria "PRODUCTION_EXPENSE" (Spesa di produzione) mostra il combo
  FATTURA ASSOCIATA + warning, altrimenti li nasconde e forza
  "Fattura non ancora emessa";
- combo DEDUCIBILE Si/No: alla scelta di "Si" mostra il combo
  UTENTE DEDUZIONE (utenti in Regime Ordinario), altrimenti lo
  nasconde e azzera il valore;
- combo ALIQUOTA IVA popolato con le aliquote di fiscal_settings;
- combo CONTO popolato con la lista conti correnti.
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
    DBExpensesColumns,
    DBInvoicesColumns,
    DBSuppliersColumns,
    DBUsersColumns,
    RegimeFiscale,
)
from QTViews.CustomWidgets.QT_catalog_filterable_combo_box import QTCatalogFilterableComboBox
from QTViews.CustomWidgets.QT_filterable_combo_box import QTFilterableComboBox

if TYPE_CHECKING:
    from App_context import AppContext


class QTExpenseCreateViewH(QDialog):
    """
    QDialog modale per la creazione di una nuova spesa.

    Le chiavi dei widget/error_labels riprendono quelle attese dal
    ``ExpenseController.save_expense``: ``SUPPLIER_FIELD``,
    ``CATEGORY``, ``NAME``, ``DATE``, ``DEDUCIBILE``,
    ``USER_DEDUZIONE_FIELD``, ``IVA_FIELD``, ``TOT_AMOUNT``,
    ``USER_ANTICIPO_FIELD``, ``INVOICE_FIELD``, ``ACCOUNT_FIELD``.
    """

    SUPPLIER_FIELD = "NOME FORNITORE"
    ACCOUNT_FIELD = "CONTO"
    USER_ANTICIPO_FIELD = "QUALCUNO HA ANTICIPATO?"
    IVA_FIELD = "ALIQUOTA IVA"
    INVOICE_FIELD = "FATTURA ASSOCIATA"
    USER_DEDUZIONE_FIELD = "DEDUZIONE A CARICO"

    INVOICE_PLACEHOLDER = "Fattura non ancora emessa"
    USER_ANTICIPO_PLACEHOLDER = " ----- "

    def __init__(self, app_context: "AppContext", parent=None, on_expense_created=None):
        super().__init__(parent)

        self.app_context = app_context
        self.expense_controller = app_context.expense_controller
        self.expenses_query_service = app_context.expenses_query_service
        self.suppliers_query_service = app_context.suppliers_query_service
        self.invoices_query_service = app_context.invoices_query_service
        self.user_query_service = app_context.user_query_service
        self.accounts_query_service = app_context.account_query_service
        self.update_controller = app_context.update_controller
        self.fiscal_settings = app_context.fiscal_settings
        self.catalogo_elenchi = app_context.catalogo_elenchi
        self.on_expense_created = on_expense_created

        self.setWindowTitle("Aggiungi Nuova Spesa")
        self.resize(560, 760)
        self.setModal(True)

        self.expense_widgets: dict = {}
        self.expense_labels: dict = {}
        self.error_labels: dict = {}
        self.name_prefix_label: QLabel = None
        self.linked_invoice_warning_label: QLabel = None

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

        self._build_supplier_row()
        self._build_category_row()
        self._build_name_row()
        self._build_date_row()
        self._build_deducibile_row()
        self._build_user_deduzione_row()
        self._build_iva_row()
        self._build_tot_amount_row()
        self._build_user_anticipo_row()
        self._build_invoice_row()
        self._build_account_row()

        bottom = QHBoxLayout()
        bottom.setContentsMargins(20, 10, 20, 20)
        bottom.addStretch(1)
        self.save_button = QPushButton("Salva Spesa")
        self.save_button.setMinimumSize(140, 40)
        self.save_button.clicked.connect(self._save_expense_data)
        bottom.addWidget(self.save_button)
        bottom.addStretch(1)
        outer.addLayout(bottom)

        self._bind_validations()

    def _add_row(self, key, label_text, widget, with_error=False):
        label = QLabel(label_text)
        self.form_layout.addRow(label, widget)
        self.expense_widgets[key] = widget
        self.expense_labels[key] = label
        if with_error:
            error = QLabel("")
            error.setStyleSheet("color: #d62929;")
            self.form_layout.addRow("", error)
            self.error_labels[key] = error

    def _build_supplier_row(self):
        suppliers = self.suppliers_query_service.retrieve_suppliers_map_list(year=-1)
        combo = QTFilterableComboBox(
            values=[s[DBSuppliersColumns.NAME.value] for s in suppliers],
            placeholder="Cerca fornitore…",
            autofill=True,
        )
        combo.currentTextChanged.connect(self._on_supplier_changed)
        self._add_row(self.SUPPLIER_FIELD, self.SUPPLIER_FIELD, combo)

    def _build_category_row(self):
        combo = QTCatalogFilterableComboBox.bound_to_section(
            app_context=self.app_context,
            section_name="expenses_category",
            parent=self,
            autofill=True,
        )
        combo.currentTextChanged.connect(self._on_category_changed)
        self._add_row(DBExpensesColumns.CATEGORY.value, "Categoria", combo)

    def _build_name_row(self):
        # Prefisso "<fornitore> - " non editabile alla sinistra del QLineEdit,
        # esattamente come fa la legacy.
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)

        self.name_prefix_label = QLabel("")
        row_layout.addWidget(self.name_prefix_label)

        edit = QLineEdit()
        row_layout.addWidget(edit, stretch=1)

        label = QLabel("Nome Spesa")
        self.form_layout.addRow(label, row)
        self.expense_widgets[DBExpensesColumns.NAME.value] = edit
        self.expense_labels[DBExpensesColumns.NAME.value] = label

        error = QLabel("")
        error.setStyleSheet("color: #d62929;")
        self.form_layout.addRow("", error)
        self.error_labels[DBExpensesColumns.NAME.value] = error

    def _build_date_row(self):
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("yyyy-MM-dd")
        date_edit.setDate(QDate.currentDate())
        self._add_row(DBExpensesColumns.DATE.value, "Data Spesa", date_edit)

    def _build_deducibile_row(self):
        combo = QComboBox()
        combo.addItems(["Si", "No"])
        combo.setCurrentText("No")
        combo.currentTextChanged.connect(self._on_deducibile_changed)
        self._add_row(DBExpensesColumns.DEDUCIBILE.value, "Deducibile", combo)

    def _build_user_deduzione_row(self):
        users = self.user_query_service.retrieve_users_map_list()
        deductible = [
            f"{u[DBUsersColumns.FIRST_NAME.value]} {u[DBUsersColumns.LAST_NAME.value]}"
            for u in users
            if u.get(DBUsersColumns.REGIME_FISCALE.value) == RegimeFiscale.ORDINARIO.value
        ]
        combo = QComboBox()
        combo.addItems(deductible)
        self._add_row(self.USER_DEDUZIONE_FIELD, self.USER_DEDUZIONE_FIELD, combo)
        # Default: nascosto (deducibile = No).
        self._set_row_visible(self.USER_DEDUZIONE_FIELD, False)

    def _build_iva_row(self):
        aliquote = [
            self.fiscal_settings.aliquota_iva.no_iva,
            self.fiscal_settings.aliquota_iva.aliquota_iva_ordinaria,
            self.fiscal_settings.aliquota_iva.aliquota_iva_ridotta_1,
            self.fiscal_settings.aliquota_iva.aliquota_iva_ridotta_2,
            self.fiscal_settings.aliquota_iva.aliquota_iva_minima,
        ]
        combo = QComboBox()
        combo.addItems([str(a) for a in aliquote])
        combo.setCurrentText(str(self.fiscal_settings.aliquota_iva.aliquota_iva_ordinaria))
        self._add_row(self.IVA_FIELD, self.IVA_FIELD, combo)

    def _build_tot_amount_row(self):
        edit = QLineEdit()
        self._add_row(DBExpensesColumns.TOT_AMOUNT.value, "Importo Totale (€)", edit, with_error=True)

    def _build_user_anticipo_row(self):
        users = self.user_query_service.retrieve_users_map_list()
        all_users = [
            f"{u[DBUsersColumns.FIRST_NAME.value]} {u[DBUsersColumns.LAST_NAME.value]}"
            for u in users
        ]
        combo = QComboBox()
        combo.addItem(self.USER_ANTICIPO_PLACEHOLDER)
        combo.addItems(all_users)
        combo.setCurrentText(self.USER_ANTICIPO_PLACEHOLDER)
        self._add_row(self.USER_ANTICIPO_FIELD, self.USER_ANTICIPO_FIELD, combo)

    def _build_invoice_row(self):
        invoices = self.invoices_query_service.retrieve_invoices_map_list(
            year=-1, include_unpaid_invoices=True
        )
        combo = QComboBox()
        combo.addItem(self.INVOICE_PLACEHOLDER)
        combo.addItems([inv[DBInvoicesColumns.NUMERO_FATTURA.value] for inv in invoices])
        combo.setCurrentText(self.INVOICE_PLACEHOLDER)
        combo.currentTextChanged.connect(self._on_invoice_changed)
        self._add_row(self.INVOICE_FIELD, self.INVOICE_FIELD, combo)

        # Warning label sotto la riga, di default nascosto.
        self.linked_invoice_warning_label = QLabel("")
        self.linked_invoice_warning_label.setStyleSheet("color: #e39e27;")
        self.linked_invoice_warning_label.setWordWrap(True)
        self.form_layout.addRow("", self.linked_invoice_warning_label)
        self.linked_invoice_warning_label.setVisible(False)

        # Default: nascosto (la categoria di default non e' di produzione).
        self._set_row_visible(self.INVOICE_FIELD, False)

    def _build_account_row(self):
        accounts = self.accounts_query_service.retrieve_accounts_map_list()
        combo = QComboBox()
        combo.addItems([a[DBAccountsColumns.NAME.value] for a in accounts])
        self._add_row(self.ACCOUNT_FIELD, self.ACCOUNT_FIELD, combo)

    # ------------------------------------------------------------------
    # Validazioni
    # ------------------------------------------------------------------

    def _bind_validations(self):
        name_edit: QLineEdit = self.expense_widgets[DBExpensesColumns.NAME.value]
        name_error: QLabel = self.error_labels[DBExpensesColumns.NAME.value]

        def _validate_name():
            if not name_edit.text().strip():
                name_error.setText("Il campo non puo essere vuoto.")
            else:
                name_error.setText("")

        name_edit.editingFinished.connect(_validate_name)

        tot_edit: QLineEdit = self.expense_widgets[DBExpensesColumns.TOT_AMOUNT.value]
        tot_error: QLabel = self.error_labels[DBExpensesColumns.TOT_AMOUNT.value]

        def _validate_tot():
            value = tot_edit.text().strip()
            if re.fullmatch(r"^\d+(\.\d{1,2})?$", value):
                tot_error.setText("")
            else:
                tot_error.setText(
                    "Inserimento non valido: usare un importo monetario con max due decimali"
                )

        tot_edit.editingFinished.connect(_validate_tot)

    # ------------------------------------------------------------------
    # Default
    # ------------------------------------------------------------------

    def _initialize_default_values(self):
        supplier_widget: QTFilterableComboBox = self.expense_widgets[self.SUPPLIER_FIELD]
        if supplier_widget.value():
            self._on_supplier_changed(supplier_widget.value())

        # Categoria di default: CONSUMABLE_FOR_STUDIO se presente nel
        # catalogo (esattamente come la legacy).
        category_dict = dict(self.catalogo_elenchi.get("expenses_category", []))
        default_category = category_dict.get("CONSUMABLE_FOR_STUDIO", "")
        if default_category:
            category_widget: QTCatalogFilterableComboBox = self.expense_widgets[
                DBExpensesColumns.CATEGORY.value
            ]
            category_widget.set_value(default_category)
            self._on_category_changed(default_category)

    # ------------------------------------------------------------------
    # Callback dinamici
    # ------------------------------------------------------------------

    def _on_supplier_changed(self, supplier_name):
        if self.name_prefix_label is None:
            return
        prefix = f"{supplier_name} - " if supplier_name else ""
        self.name_prefix_label.setText(prefix)

    def _on_category_changed(self, selected_value):
        # Mostra/nasconde il combo INVOICE in funzione della categoria,
        # esattamente come fa la legacy.
        production_expense = dict(self.catalogo_elenchi.get("expenses_category", [])).get(
            "PRODUCTION_EXPENSE"
        )
        if selected_value == production_expense:
            self._set_row_visible(self.INVOICE_FIELD, True)
        else:
            invoice_combo: QComboBox = self.expense_widgets[self.INVOICE_FIELD]
            invoice_combo.setCurrentText(self.INVOICE_PLACEHOLDER)
            self._set_row_visible(self.INVOICE_FIELD, False)
            self.linked_invoice_warning_label.setVisible(False)

    def _on_invoice_changed(self, selected_value):
        if selected_value == self.INVOICE_PLACEHOLDER or not selected_value:
            self.linked_invoice_warning_label.setText("")
            self.linked_invoice_warning_label.setVisible(False)
            return
        self.linked_invoice_warning_label.setText(
            "Attenzione: la spesa verra collegata alla fattura selezionata.\n"
            "Verifica che la categoria sia davvero una spesa di produzione."
        )
        self.linked_invoice_warning_label.setVisible(True)

    def _on_deducibile_changed(self, selected_value):
        if selected_value == "Si":
            self._set_row_visible(self.USER_DEDUZIONE_FIELD, True)
        else:
            self._set_row_visible(self.USER_DEDUZIONE_FIELD, False)

    def _set_row_visible(self, key, visible):
        widget = self.expense_widgets.get(key)
        label = self.expense_labels.get(key)
        if widget is not None:
            widget.setVisible(visible)
        if label is not None:
            label.setVisible(visible)

    # ------------------------------------------------------------------
    # Salvataggio
    # ------------------------------------------------------------------

    def _collect_expense_data(self):
        expense_data = {}
        for key, widget in self.expense_widgets.items():
            if isinstance(widget, QTFilterableComboBox):
                expense_data[key] = widget.value()
            elif isinstance(widget, QComboBox):
                expense_data[key] = widget.currentText().strip()
            elif isinstance(widget, QLineEdit):
                expense_data[key] = widget.text().strip()
            elif isinstance(widget, QDateEdit):
                expense_data[key] = widget.date().toString("yyyy-MM-dd")
        return expense_data

    def prefill_supplier(self, supplier_name: str) -> None:
        """Pre-seleziona il fornitore nel combo e aggiorna il prefisso nome."""
        if not supplier_name:
            return
        combo = self.expense_widgets.get("NOME FORNITORE")
        if combo is None:
            return
        combo.set_value(supplier_name)
        self._on_supplier_changed(supplier_name)

    def _save_expense_data(self):
        expense_data = self._collect_expense_data()

        if not expense_data.get(DBExpensesColumns.CATEGORY.value):
            QMessageBox.critical(self, "ERRORE", "Categoria non valida.")
            return

        # Coerenza con la legacy: se la categoria non e' "Spesa di
        # produzione" l'eventuale fattura associata va scartata.
        production_expense = dict(self.catalogo_elenchi.get("expenses_category", [])).get(
            "PRODUCTION_EXPENSE"
        )
        if expense_data.get(DBExpensesColumns.CATEGORY.value) != production_expense:
            expense_data.pop(self.INVOICE_FIELD, None)
        elif expense_data.get(self.INVOICE_FIELD) == self.INVOICE_PLACEHOLDER:
            expense_data[self.INVOICE_FIELD] = self.INVOICE_PLACEHOLDER

        # Anticipo: il placeholder " ----- " significa "nessuno".
        if expense_data.get(self.USER_ANTICIPO_FIELD) == self.USER_ANTICIPO_PLACEHOLDER:
            expense_data[self.USER_ANTICIPO_FIELD] = ""

        # Se non e' deducibile, niente utente di deduzione.
        if expense_data.get(DBExpensesColumns.DEDUCIBILE.value) == "No":
            expense_data[self.USER_DEDUZIONE_FIELD] = None

        success, message = self.expense_controller.save_expense(expense_data)
        if not success:
            QMessageBox.critical(self, "ERRORE", message)
            return

        # Aggiornamenti collaterali — coerenza con la legacy.
        try:
            self.update_controller.on_adding_expense()
        except Exception:
            pass

        expense_map = self.expenses_query_service.retrieve_last_expense_insert_map()
        expense_id = expense_map[DBExpensesColumns.ID.value] if expense_map else None

        if self.on_expense_created is not None and expense_id is not None:
            self.on_expense_created(expense_id)

        self.accept()

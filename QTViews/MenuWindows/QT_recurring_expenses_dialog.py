from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from Gestionale_Enums import RecurringExpensesFrequencies, RecurringExpensesStatus
from Model import DBAccountsColumns, DBSuppliersColumns, DBUsersColumns
from QTViews.CustomWidgets.QT_catalog_filterable_combo_box import (
    QTCatalogFilterableComboBox,
)
from QTViews.CustomWidgets.QT_filterable_combo_box import QTFilterableComboBox

if TYPE_CHECKING:
    from App_context import AppContext


class _RecurringExpenseTab(QWidget):
    """
    Pannello dei campi modificabili di una singola spesa ricorrente.

    Tutti i widget vengono raccolti in `self.widgets` con la stessa
    convenzione del legacy così che la fase di salvataggio sia identica
    nei due flussi (esistente / nuova spesa).
    """

    def __init__(self, parent_dialog: "QTRecurringExpensesDialog", expense_key, expense, is_new):
        super().__init__()
        self.parent_dialog = parent_dialog
        self.expense_key = expense_key
        self.expense = expense
        self.is_new = is_new
        self.widgets: dict = {}

        self._build()

    def _build(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        form = QFormLayout(container)
        form.setContentsMargins(15, 15, 15, 15)
        form.setSpacing(12)

        accounts = [a[DBAccountsColumns.NAME.value]
                    for a in self.parent_dialog.account_query_service.retrieve_accounts_map_list()]
        suppliers = self.parent_dialog._get_supplier_values()
        categories = self.parent_dialog._get_category_values()
        ivas = self.parent_dialog._get_iva_values()
        users = self.parent_dialog.user_query_service.retrieve_users_map_list()
        deductors = [f"{u[DBUsersColumns.FIRST_NAME.value]} {u[DBUsersColumns.LAST_NAME.value]}" for u in users]

        if self.is_new:
            name_edit = QLineEdit()
            form.addRow("Nome Spesa:", name_edit)
            self.widgets["name"] = name_edit

        amount_val = getattr(self.expense, "amount", 0)
        amount_str = "" if self.is_new else f"{float(amount_val):.2f}"
        amount_edit = QLineEdit(amount_str)
        form.addRow("Importo:", amount_edit)
        self.widgets["amount"] = amount_edit

        supplier_combo = QTFilterableComboBox(
            values=suppliers, placeholder="Cerca fornitore…", autofill=True,
        )
        if not self.is_new:
            supplier_combo.set_value(getattr(self.expense, "supplier", ""))
        form.addRow("Fornitore:", supplier_combo)
        self.widgets["supplier"] = supplier_combo

        category_combo = QTCatalogFilterableComboBox.bound_to_section(
            app_context=self.parent_dialog.app_context,
            section_name="expenses_category",
            parent=self,
        )
        if not self.is_new:
            current = getattr(self.expense, "category", "")
            category_combo.set_value(
                current if current in categories else (categories[0] if categories else "")
            )
        form.addRow("Categoria:", category_combo)
        self.widgets["category"] = category_combo

        iva_combo = QComboBox()
        iva_combo.addItems(ivas)
        if not self.is_new:
            self._set_combo_text(iva_combo, str(getattr(self.expense, "iva", "")))
        form.addRow("IVA:", iva_combo)
        self.widgets["iva"] = iva_combo

        deductor_combo = QComboBox()
        deductor_combo.addItems(deductors + ["Nessuno"])
        if not self.is_new:
            current_id = getattr(self.expense, "deductor", None)
            current_user = self.parent_dialog.user_query_service.retrieve_user_map_by_id(current_id)
            if getattr(self.expense, "deductible", False) and current_user:
                full = f"{current_user[DBUsersColumns.FIRST_NAME.value]} {current_user[DBUsersColumns.LAST_NAME.value]}"
                self._set_combo_text(deductor_combo, full)
            else:
                self._set_combo_text(deductor_combo, "Nessuno")
        form.addRow("Deduzione a carico di:", deductor_combo)
        self.widgets["deductor"] = deductor_combo

        account_combo = QComboBox()
        account_combo.addItems(accounts)
        if not self.is_new:
            self._set_combo_text(account_combo, getattr(self.expense, "account", ""))
        form.addRow("Conto:", account_combo)
        self.widgets["account"] = account_combo

        freq_combo = QComboBox()
        freq_combo.addItems([f.value for f in RecurringExpensesFrequencies])
        if not self.is_new:
            self._set_combo_text(freq_combo, getattr(self.expense, "frequency", ""))
        form.addRow("Frequenza:", freq_combo)
        self.widgets["frequency"] = freq_combo

        deductible_widget, self.widgets["deductible"] = self._build_radio_row(
            ["Sì", "No"],
            "Sì" if (not self.is_new and getattr(self.expense, "deductible", False)) else "No",
        )
        form.addRow("Deduzione:", deductible_widget)

        status_default = (
            RecurringExpensesStatus.ATTIVA.value
            if (not self.is_new and getattr(self.expense, "status", False))
            else RecurringExpensesStatus.SOSPESA.value
        )
        if self.is_new:
            status_default = RecurringExpensesStatus.ATTIVA.value
        status_widget, self.widgets["status"] = self._build_radio_row(
            [s.value for s in RecurringExpensesStatus],
            status_default,
        )
        form.addRow("Stato:", status_widget)

    @staticmethod
    def _set_combo_text(combo: QComboBox, value):
        if value is None:
            return
        text = str(value)
        idx = combo.findText(text)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        elif combo.isEditable():
            combo.setEditText(text)

    @staticmethod
    def _build_radio_row(values, default):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        group = QButtonGroup(container)
        buttons = []
        for v in values:
            rb = QRadioButton(v)
            if v == default:
                rb.setChecked(True)
            group.addButton(rb)
            layout.addWidget(rb)
            buttons.append(rb)
        layout.addStretch(1)
        return container, buttons

    def get_value(self, field):
        widget = self.widgets.get(field)
        if widget is None:
            return ""
        if isinstance(widget, QLineEdit):
            return widget.text().strip()
        # Le filterable (catalog inclusa) hanno un value() che esclude
        # testo libero / sentinella e va preferito al currentText() raw.
        if isinstance(widget, QTFilterableComboBox):
            return widget.value()
        if isinstance(widget, QComboBox):
            return widget.currentText().strip()
        if isinstance(widget, list):  # gruppi di radio button
            for btn in widget:
                if btn.isChecked():
                    return btn.text()
            return ""
        return ""


class QTRecurringExpensesDialog(QDialog):
    """
    Finestra "Gestione Spese Ricorrenti".

    Equivalente di MainWindow.open_recurring_expenses_window legacy. Usa
    un QTabWidget con una tab per ogni spesa ricorrente esistente; il
    bottone "Aggiungi una spesa ricorrente" crea una nuova tab di tipo
    "Nuova Spesa" con anche il campo nome.
    """

    NEW_TAB_KEY = "Nuova Spesa"

    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.config_manager = app_context.config_manager
        self.account_query_service = app_context.account_query_service
        self.user_query_service = app_context.user_query_service
        self.suppliers_query_service = app_context.suppliers_query_service
        self.fiscal_settings = app_context.fiscal_settings
        self.catalogo_elenchi = app_context.catalogo_elenchi
        self.recurring_expenses_settings = app_context.recurring_expenses_settings

        self.setWindowTitle("Gestione Spese Ricorrenti")
        self.resize(1000, 800)
        self.setModal(True)

        self.tabs_by_key: dict = {}

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(15, 15, 15, 15)
        root.setSpacing(15)

        add_btn = QPushButton("Aggiungi una spesa ricorrente")
        add_btn.clicked.connect(self._add_recurring_expense_tab)
        root.addWidget(add_btn)

        self.tabs = QTabWidget()
        for expense_key, expense in self.recurring_expenses_settings.items():
            tab = _RecurringExpenseTab(self, expense_key, expense, is_new=False)
            self.tabs.addTab(tab, expense.description)
            self.tabs_by_key[expense_key] = tab
        root.addWidget(self.tabs, stretch=1)

        save_btn = QPushButton("Salva Tutte le Modifiche")
        save_btn.clicked.connect(self._save_recurring_expenses)
        root.addWidget(save_btn)

    def _add_recurring_expense_tab(self):
        if self.NEW_TAB_KEY in self.tabs_by_key:
            self.tabs.setCurrentWidget(self.tabs_by_key[self.NEW_TAB_KEY])
            return
        tab = _RecurringExpenseTab(self, self.NEW_TAB_KEY, expense=None, is_new=True)
        self.tabs.addTab(tab, self.NEW_TAB_KEY)
        self.tabs_by_key[self.NEW_TAB_KEY] = tab
        self.tabs.setCurrentWidget(tab)

    # ------------------------------------------------------------------
    # Source data helpers (equivalenti legacy)
    # ------------------------------------------------------------------

    def _get_supplier_values(self):
        suppliers = self.suppliers_query_service.retrieve_suppliers_map_list(year=-1)
        return [s[DBSuppliersColumns.NAME.value] for s in suppliers]

    def _get_category_values(self):
        return [
            value for key, value in self.catalogo_elenchi["expenses_category"]
            if key != "ADD_CATEGORY"
        ]

    def _get_iva_values(self):
        aliquote = [
            self.fiscal_settings.aliquota_iva.no_iva,
            self.fiscal_settings.aliquota_iva.aliquota_iva_ordinaria,
            self.fiscal_settings.aliquota_iva.aliquota_iva_ridotta_1,
            self.fiscal_settings.aliquota_iva.aliquota_iva_ridotta_2,
            self.fiscal_settings.aliquota_iva.aliquota_iva_minima,
        ]
        return [str(a) for a in aliquote]

    # ------------------------------------------------------------------
    # Salvataggio
    # ------------------------------------------------------------------

    def _save_recurring_expenses(self):
        new_data = {}

        for key, tab in self.tabs_by_key.items():
            deductible = tab.get_value("deductible")
            deductor_name = tab.get_value("deductor")

            deductor = (
                self.user_query_service.retrieve_user_map_by_extended_name(deductor_name)
                if deductible == "Sì" else None
            )
            deductor_id = deductor[DBUsersColumns.ID.value] if deductor is not None else None

            if key == self.NEW_TAB_KEY:
                raw_name = tab.get_value("name")
                if not raw_name:
                    continue
                description = raw_name.upper()
                new_key = raw_name.lower().replace(" ", "_")
                fields = {
                    "description": description,
                    "amount": tab.get_value("amount"),
                    "supplier": tab.get_value("supplier"),
                    "deductible": deductible,
                    "category": tab.get_value("category"),
                    "deductor": deductor_id if deductible == "Sì" else None,
                    "iva": tab.get_value("iva"),
                    "account": tab.get_value("account"),
                    "frequency": tab.get_value("frequency"),
                    "status": tab.get_value("status"),
                }
                new_data[new_key] = fields
            else:
                description = self.recurring_expenses_settings[key].description
                fields = {
                    "description": description,
                    "amount": tab.get_value("amount"),
                    "supplier": tab.get_value("supplier"),
                    "deductible": deductible,
                    "category": tab.get_value("category"),
                    "deductor": deductor_id if deductible == "Sì" else None,
                    "iva": tab.get_value("iva"),
                    "account": tab.get_value("account"),
                    "frequency": tab.get_value("frequency"),
                    "status": tab.get_value("status"),
                }
                new_data[key] = fields

        try:
            self.config_manager.update_recurring_expenses(new_data)
        except Exception as exc:
            QMessageBox.critical(self, "Errore", f"Salvataggio fallito: {exc}")
            return

        QMessageBox.information(
            self,
            "Successo",
            "Modifiche salvate correttamente.\n"
            "I dati aggiornati saranno visibili al prossimo avvio dell'applicazione.",
        )
        self.accept()

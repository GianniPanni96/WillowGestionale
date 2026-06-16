"""
Versione QT del dettaglio di una spesa.

Equivalente di Views/Details/Expense_detail_view.ExpenseDetailView,
portato sui widget Qt mantenendo la stessa logica di dominio:
- sezione informazioni in griglia 2x2 (Dati Generali / Dati Fiscali /
  Collegamenti / Note);
- categoria via QTCatalogFilterableComboBox sul catalogo
  ``expenses_category``;
- fornitore via QTFilterableComboBox;
- visibilita' della fattura associata legata alla categoria
  "Spesa di produzione" (PRODUCTION_EXPENSE);
- visibilita' dell'utente di deduzione legata al combo DEDUCIBILE
  (Si/No);
- nome spesa di sola lettura se la spesa e' ricorrente, come fa la
  legacy.

Strutturalmente segue il pattern di QTPaymentDetailViewH /
QTRefundDetailViewH: head bar persistente (back + titolo + switch),
QScrollArea per il corpo, refresh totale via load_expense().
"""

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
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
from QTViews.CustomWidgets.QT_warning_banner import WarningBanner
from WarningServices.Warning_types import WarningInfo, WarningSeverity

if TYPE_CHECKING:
    from App_context import AppContext


class QTExpenseDetailViewH(QWidget):
    """
    QWidget dettaglio spesa.
    """

    ACCOUNT_FIELD = "CONTO"
    USER_DEDUZIONE_FIELD = "UTENTE DEDUZIONE"
    USER_ANTICIPO_FIELD = "UTENTE ANTICIPO"
    INVOICE_FIELD = "FATTURA ASSOCIATA"
    SUPPLIER_FIELD = "FORNITORE"

    INVOICE_PLACEHOLDER = "Fattura non ancora emessa"

    SECTIONS = ["Dati Generali", "Dati Fiscali", "Collegamenti", "Note"]

    def __init__(self, app_context: "AppContext", expense_id, on_back, parent=None):
        super().__init__(parent)

        self.app_context = app_context
        self.expense_controller = app_context.expense_controller
        self.expenses_query_service = app_context.expenses_query_service
        self.invoices_query_service = app_context.invoices_query_service
        self.suppliers_query_service = app_context.suppliers_query_service
        self.user_query_service = app_context.user_query_service
        self.accounts_query_service = app_context.account_query_service
        self.update_controller = app_context.update_controller
        self.catalogo_elenchi = app_context.catalogo_elenchi

        self.current_expense_id = expense_id
        self.expense = None
        self.on_back = on_back

        self.expense_widgets: dict = {}
        self.expense_labels: dict = {}
        self.section_grids: dict = {}
        self.section_rows: dict = {}

        self._build_ui()
        self.load_expense(expense_id)

    # ------------------------------------------------------------------
    # UI base
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        head = QFrame()
        head.setObjectName("ExpenseDetailHead")
        head.setStyleSheet(
            "#ExpenseDetailHead { background-color: palette(window); border-radius: 6px; }"
        )
        head_layout = QHBoxLayout(head)
        head_layout.setContentsMargins(10, 6, 10, 6)

        self.back_button = QPushButton("Elenco Spese")
        self.back_button.clicked.connect(self._cleanup_and_go_back)
        head_layout.addWidget(self.back_button)

        self.title_label = QLabel("")
        title_font = self.title_label.font()
        title_font.setPointSize(16)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignCenter)
        head_layout.addWidget(self.title_label, stretch=1)

        self.modify_switch = QCheckBox("Abilita la modifica")
        self.modify_switch.toggled.connect(self._toggle_edit)
        head_layout.addWidget(self.modify_switch)

        root.addWidget(head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        root.addWidget(self.scroll, stretch=1)

        self.content = QWidget()
        self.scroll.setWidget(self.content)
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        self.content_layout.setSpacing(15)

    def _build_info_section(self, expense_data):
        # Warning banner: visibile solo per i sev 1 (FK rotte).
        self.warning_banner = WarningBanner()
        self.content_layout.addWidget(self.warning_banner)
        self._current_warning_info = self._compute_current_warning(expense_data)
        if self._is_consistency_warning(self._current_warning_info):
            self.warning_banner.set_warning(self._current_warning_info)
        else:
            self.warning_banner.hide_warning()

        self.info_frame = QFrame()
        self.info_frame.setObjectName("ExpenseInfoFrame")
        self.info_frame.setStyleSheet(
            "#ExpenseInfoFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
        )
        info_layout = QGridLayout(self.info_frame)
        info_layout.setContentsMargins(15, 15, 15, 15)
        info_layout.setHorizontalSpacing(20)
        info_layout.setVerticalSpacing(10)

        # Griglia 2x2 come la legacy: Dati Generali / Dati Fiscali (riga 0),
        # Collegamenti / Note (riga 1).
        for i, name in enumerate(self.SECTIONS):
            section_frame = QFrame()
            section_frame.setObjectName("ExpenseInfoSectionFrame")
            section_frame.setStyleSheet(
                "#ExpenseInfoSectionFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
            )
            section_layout = QGridLayout(section_frame)
            section_layout.setContentsMargins(10, 10, 10, 10)
            section_layout.setHorizontalSpacing(8)
            section_layout.setVerticalSpacing(8)
            section_layout.setAlignment(Qt.AlignTop)

            section_title = QLabel(name)
            font = section_title.font()
            font.setBold(True)
            font.setPointSize(12)
            section_title.setFont(font)
            section_title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            section_layout.addWidget(section_title, 0, 0, 1, 2, alignment=Qt.AlignTop)

            row = i // 2
            col = i % 2
            info_layout.addWidget(section_frame, row, col)
            info_layout.setColumnStretch(col, 1)
            self.section_grids[name] = section_layout
            self.section_rows[name] = 1

        # --- Dati Generali ---
        # Nome spesa: editabile solo per spese non ricorrenti (la legacy
        # toglie proprio la riga dalla griglia se ``RICORRENTE`` e' True).
        if not expense_data.get(DBExpensesColumns.RICORRENTE.value):
            self._add_field(
                "Dati Generali",
                DBExpensesColumns.NAME.value,
                "Nome Spesa",
                self._make_line_edit(expense_data.get(DBExpensesColumns.NAME.value, "")),
            )
        self._add_field(
            "Dati Generali",
            DBExpensesColumns.DATE.value,
            "Data Spesa",
            self._make_date_edit(expense_data.get(DBExpensesColumns.DATE.value)),
        )

        # --- Dati Fiscali ---
        category_combo = QTCatalogFilterableComboBox.bound_to_section(
            app_context=self.app_context,
            section_name="expenses_category",
            parent=self,
        )
        category_combo.set_value(expense_data.get(DBExpensesColumns.CATEGORY.value, "") or "")
        category_combo.currentTextChanged.connect(self._on_category_changed)
        self._add_field("Dati Fiscali", DBExpensesColumns.CATEGORY.value, "Categoria", category_combo)

        self._add_field(
            "Dati Fiscali",
            DBExpensesColumns.NET_AMOUNT.value,
            "Importo Netto (€)",
            self._make_line_edit(expense_data.get(DBExpensesColumns.NET_AMOUNT.value, ""), money=True),
        )
        self._add_field(
            "Dati Fiscali",
            DBExpensesColumns.IVA_AMOUNT.value,
            "Importo IVA (€)",
            self._make_line_edit(expense_data.get(DBExpensesColumns.IVA_AMOUNT.value, ""), money=True),
        )
        self._add_field(
            "Dati Fiscali",
            DBExpensesColumns.TOT_AMOUNT.value,
            "Importo Totale (€)",
            self._make_line_edit(expense_data.get(DBExpensesColumns.TOT_AMOUNT.value, ""), money=True),
        )

        deducibile_combo = QComboBox()
        deducibile_combo.addItems(["Si", "No"])
        self._set_combo_text(
            deducibile_combo, expense_data.get(DBExpensesColumns.DEDUCIBILE.value, "No")
        )
        deducibile_combo.currentTextChanged.connect(self._on_deducibile_changed)
        self._add_field(
            "Dati Fiscali",
            DBExpensesColumns.DEDUCIBILE.value,
            "Deducibile",
            deducibile_combo,
        )

        # --- Collegamenti ---
        suppliers = self.suppliers_query_service.retrieve_suppliers_map_list(year=-1)
        supplier_combo = QTFilterableComboBox(
            values=[s[DBSuppliersColumns.NAME.value] for s in suppliers],
            placeholder="Cerca fornitore…",
            autofill=True,
        )
        supplier_combo.set_value(expense_data.get(self.SUPPLIER_FIELD, "") or "")
        self._add_field("Collegamenti", self.SUPPLIER_FIELD, "Fornitore", supplier_combo)

        users = self.user_query_service.retrieve_users_map_list()
        deductible_users = [
            f"{u[DBUsersColumns.FIRST_NAME.value]} {u[DBUsersColumns.LAST_NAME.value]}"
            for u in users
            if u.get(DBUsersColumns.REGIME_FISCALE.value) == RegimeFiscale.ORDINARIO.value
        ]
        all_users = [
            f"{u[DBUsersColumns.FIRST_NAME.value]} {u[DBUsersColumns.LAST_NAME.value]}"
            for u in users
        ]

        user_deduzione_combo = QComboBox()
        user_deduzione_combo.addItem("")
        user_deduzione_combo.addItems(deductible_users)
        self._set_combo_text(user_deduzione_combo, expense_data.get(self.USER_DEDUZIONE_FIELD, ""))
        self._add_field(
            "Collegamenti",
            self.USER_DEDUZIONE_FIELD,
            "Utente Deduzione",
            user_deduzione_combo,
        )

        user_anticipo_combo = QComboBox()
        user_anticipo_combo.addItem("")
        user_anticipo_combo.addItems(all_users)
        self._set_combo_text(user_anticipo_combo, expense_data.get(self.USER_ANTICIPO_FIELD, ""))
        self._add_field(
            "Collegamenti",
            self.USER_ANTICIPO_FIELD,
            "Utente Anticipo",
            user_anticipo_combo,
        )

        invoices = self.invoices_query_service.retrieve_invoices_map_list(
            year=-1, include_unpaid_invoices=True
        )
        invoice_combo = QComboBox()
        invoice_combo.addItem(self.INVOICE_PLACEHOLDER)
        invoice_combo.addItems([inv[DBInvoicesColumns.NUMERO_FATTURA.value] for inv in invoices])
        invoice_value = expense_data.get(self.INVOICE_FIELD) or self.INVOICE_PLACEHOLDER
        self._set_combo_text(invoice_combo, invoice_value)
        self._add_field("Collegamenti", self.INVOICE_FIELD, "Fattura Associata", invoice_combo)

        accounts = self.accounts_query_service.retrieve_accounts_map_list()
        account_combo = QComboBox()
        account_combo.addItems([a[DBAccountsColumns.NAME.value] for a in accounts])
        self._set_combo_text(account_combo, expense_data.get(self.ACCOUNT_FIELD, ""))
        self._add_field("Collegamenti", self.ACCOUNT_FIELD, "Conto", account_combo)

        # --- Note: timestamp read-only ---
        created_lbl = QLabel(str(expense_data.get(DBExpensesColumns.created_at.value, "") or ""))
        self._add_field("Note", DBExpensesColumns.created_at.value, "Data Creazione", created_lbl)

        updated_lbl = QLabel(str(expense_data.get(DBExpensesColumns.updated_at.value, "") or ""))
        self._add_field("Note", DBExpensesColumns.updated_at.value, "Ultimo Aggiornamento", updated_lbl)

        # Riga bottoni Salva / Elimina.
        buttons_frame = QFrame()
        buttons_layout = QHBoxLayout(buttons_frame)
        buttons_layout.setContentsMargins(15, 15, 15, 15)

        self.save_btn = QPushButton("Salva Spesa")
        self.save_btn.clicked.connect(self._save_expense_mod)
        buttons_layout.addWidget(self.save_btn, alignment=Qt.AlignBottom)

        buttons_layout.addStretch(1)

        self.delete_btn = QPushButton("Elimina Spesa")
        self.delete_btn.setStyleSheet(
            "QPushButton { background-color: #8B0000; color: palette(highlighted-text); }"
            "QPushButton:hover { background-color: #A52A2A; }"
            "QPushButton:disabled { background-color: #4a2727; color: palette(mid); }"
        )
        self.delete_btn.clicked.connect(self._delete_expense)
        buttons_layout.addWidget(self.delete_btn, alignment=Qt.AlignBottom)

        info_layout.addWidget(buttons_frame, 2, 0, 1, 2)

        self.content_layout.addWidget(self.info_frame)

        # Allinea visibilita' iniziali al pattern legacy.
        self._apply_dynamic_visibility(initial=True)

    def _add_field(self, section_name, key, label_text, widget):
        grid = self.section_grids[section_name]
        row = self.section_rows[section_name]
        label = QLabel(label_text + ":")
        grid.addWidget(label, row, 0, alignment=Qt.AlignLeft)
        grid.addWidget(widget, row, 1)
        self.expense_widgets[key] = widget
        self.expense_labels[key] = label
        self.section_rows[section_name] = row + 1

    def _make_line_edit(self, value, money=False):
        edit = QLineEdit()
        if money and value not in (None, ""):
            try:
                value = f"{float(value):.2f}"
            except (TypeError, ValueError):
                pass
        edit.setText(str(value) if value is not None else "")
        return edit

    def _make_date_edit(self, value):
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("yyyy-MM-dd")
        if value:
            qd = QDate.fromString(str(value), "yyyy-MM-dd")
            if qd.isValid():
                date_edit.setDate(qd)
            else:
                date_edit.setDate(QDate.currentDate())
        else:
            date_edit.setDate(QDate.currentDate())
        return date_edit

    # ------------------------------------------------------------------
    # Caricamento dati
    # ------------------------------------------------------------------

    def load_expense(self, expense_id):
        self.current_expense_id = expense_id
        self._clear_content()

        expense = self.expenses_query_service.retrieve_expense_map_by_id(expense_id)
        if not expense:
            self.title_label.setText("Spesa non trovata")
            return

        # Arricchiamo il dict con i nomi risolti dai vari id, come fa la
        # legacy: ACCOUNT, SUPPLIER, USER_DEDUZIONE, USER_ANTICIPO,
        # INVOICE.
        account = self.accounts_query_service.retrieve_account_map_by_id(
            expense.get(DBExpensesColumns.ACCOUNT_ID.value)
        )
        supplier = self.suppliers_query_service.retrieve_supplier_map_by_id(
            expense.get(DBExpensesColumns.SUPPLIER_ID.value)
        )
        user_ded = self.user_query_service.retrieve_user_map_by_id(
            expense.get(DBExpensesColumns.USER_ID_DEDUZIONE.value)
        )
        user_ant = self.user_query_service.retrieve_user_map_by_id(
            expense.get(DBExpensesColumns.USER_ID_ANTICIPO.value)
        )
        invoice = self.invoices_query_service.retrieve_invoice_map_by_id(
            expense.get(DBExpensesColumns.LINKED_INVOICE_ID.value)
        )

        expense[self.ACCOUNT_FIELD] = account[DBAccountsColumns.NAME.value] if account else ""
        expense[self.SUPPLIER_FIELD] = supplier[DBSuppliersColumns.NAME.value] if supplier else ""
        expense[self.USER_DEDUZIONE_FIELD] = (
            f"{user_ded[DBUsersColumns.FIRST_NAME.value]} {user_ded[DBUsersColumns.LAST_NAME.value]}"
            if user_ded
            else ""
        )
        expense[self.USER_ANTICIPO_FIELD] = (
            f"{user_ant[DBUsersColumns.FIRST_NAME.value]} {user_ant[DBUsersColumns.LAST_NAME.value]}"
            if user_ant
            else ""
        )
        expense[self.INVOICE_FIELD] = (
            invoice[DBInvoicesColumns.NUMERO_FATTURA.value] if invoice else self.INVOICE_PLACEHOLDER
        )

        self.expense = expense
        self.title_label.setText(str(expense.get(DBExpensesColumns.NAME.value, "")))

        self._build_info_section(expense)
        self._toggle_edit(self.modify_switch.isChecked())
        self._apply_broken_field_highlight()

    # ------------------------------------------------------------------
    # Warning di consistenza (sev 1)
    # ------------------------------------------------------------------

    def _compute_current_warning(self, expense):
        try:
            service = self.app_context.expense_warning_service
            warnings = service.collect_warnings_for_list([expense]) or {}
            return warnings.get(expense.get(DBExpensesColumns.NAME.value))
        except Exception:
            return None

    @staticmethod
    def _is_consistency_warning(info) -> bool:
        return isinstance(info, WarningInfo) and info.severity == WarningSeverity.CONSISTENCY

    _BROKEN_FIELD_WIDGET_MAP_EXPENSE = {
        DBExpensesColumns.SUPPLIER_ID.value: "FORNITORE",
        DBExpensesColumns.ACCOUNT_ID.value: "CONTO",
        DBExpensesColumns.USER_ID_DEDUZIONE.value: "UTENTE DEDUZIONE",
        DBExpensesColumns.USER_ID_ANTICIPO.value: "UTENTE ANTICIPO",
        DBExpensesColumns.LINKED_INVOICE_ID.value: "FATTURA ASSOCIATA",
    }

    def _apply_broken_field_highlight(self):
        info = getattr(self, "_current_warning_info", None)
        if not self._is_consistency_warning(info) or not info.broken_field_key:
            return
        widget_key = self._BROKEN_FIELD_WIDGET_MAP_EXPENSE.get(
            info.broken_field_key, info.broken_field_key
        )
        widget = getattr(self, "expense_widgets", {}).get(widget_key)
        if widget is None:
            return
        widget.setStyleSheet(
            widget.styleSheet() + " border: 2px solid #d62929; border-radius: 4px;"
        )

    def _clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.expense_widgets.clear()
        self.expense_labels.clear()
        self.section_grids.clear()
        self.section_rows.clear()
        self.modify_switch.blockSignals(True)
        self.modify_switch.setChecked(False)
        self.modify_switch.blockSignals(False)

    # ------------------------------------------------------------------
    # Modifica abilitata/disabilitata
    # ------------------------------------------------------------------

    def _toggle_edit(self, enabled):
        if not hasattr(self, "save_btn"):
            return

        self.save_btn.setEnabled(enabled)
        self.delete_btn.setEnabled(enabled)

        readonly_keys = {
            DBExpensesColumns.created_at.value,
            DBExpensesColumns.updated_at.value,
        }
        for key, widget in self.expense_widgets.items():
            if key in readonly_keys:
                continue
            widget.setEnabled(enabled)

        # Riapplica le regole di visibilita' (la fattura associata e
        # l'utente deduzione restano disabilitati anche in modalita'
        # modifica se la categoria / il flag deducibile non lo
        # richiedono).
        self._apply_dynamic_visibility(initial=False)

    # ------------------------------------------------------------------
    # Callback dinamici
    # ------------------------------------------------------------------

    def _on_category_changed(self, _selected_value):
        self._apply_dynamic_visibility(initial=False)

    def _on_deducibile_changed(self, _selected_value):
        self._apply_dynamic_visibility(initial=False)

    def _apply_dynamic_visibility(self, initial: bool):
        """Riallinea lo stato enabled/visible di INVOICE e USER_DEDUZIONE
        in base alla categoria e al flag DEDUCIBILE — replica della
        logica di toggle_linked_invoice_selection / toggle_user_deduzione
        della legacy."""
        category_widget = self.expense_widgets.get(DBExpensesColumns.CATEGORY.value)
        if category_widget is None:
            return
        category = (
            category_widget.value()
            if isinstance(category_widget, QTFilterableComboBox)
            else category_widget.currentText()
        )
        production_expense = dict(self.catalogo_elenchi.get("expenses_category", [])).get(
            "PRODUCTION_EXPENSE"
        )

        invoice_widget = self.expense_widgets.get(self.INVOICE_FIELD)
        if invoice_widget is not None:
            if category == production_expense:
                invoice_widget.setEnabled(self.modify_switch.isChecked())
            else:
                # Coerenza con la legacy: forziamo il placeholder e
                # disabilitiamo la combo.
                if isinstance(invoice_widget, QComboBox):
                    invoice_widget.setCurrentText(self.INVOICE_PLACEHOLDER)
                invoice_widget.setEnabled(False)

        deducibile_widget = self.expense_widgets.get(DBExpensesColumns.DEDUCIBILE.value)
        user_deduzione_widget = self.expense_widgets.get(self.USER_DEDUZIONE_FIELD)
        if deducibile_widget is not None and user_deduzione_widget is not None:
            deducibile_value = (
                deducibile_widget.currentText() if isinstance(deducibile_widget, QComboBox) else ""
            )
            if deducibile_value == "Si":
                user_deduzione_widget.setEnabled(self.modify_switch.isChecked())
            else:
                # Su disabilita: svuotiamo per coerenza con la legacy.
                if isinstance(user_deduzione_widget, QComboBox) and not initial:
                    user_deduzione_widget.setCurrentText("")
                user_deduzione_widget.setEnabled(False)

    # ------------------------------------------------------------------
    # Salvataggio / eliminazione
    # ------------------------------------------------------------------

    def _save_expense_mod(self):
        account = self.accounts_query_service.retrieve_account_map_by_name(
            self._combo_text(self.ACCOUNT_FIELD)
        )
        supplier = self.suppliers_query_service.retrieve_supplier_map_by_name(
            self._combo_text(self.SUPPLIER_FIELD)
        )

        user_deduzione = None
        deduzione_name = self._combo_text(self.USER_DEDUZIONE_FIELD)
        if deduzione_name:
            user_deduzione = self.user_query_service.retrieve_user_map_by_extended_name(deduzione_name)

        user_anticipo = None
        anticipo_name = self._combo_text(self.USER_ANTICIPO_FIELD)
        if anticipo_name:
            user_anticipo = self.user_query_service.retrieve_user_map_by_extended_name(anticipo_name)

        invoice = None
        invoice_name = self._combo_text(self.INVOICE_FIELD)
        if invoice_name and invoice_name != self.INVOICE_PLACEHOLDER:
            invoice = self.invoices_query_service.retrieve_invoice_map_by_name(invoice_name)

        date_widget: QDateEdit = self.expense_widgets[DBExpensesColumns.DATE.value]

        expense_data = {
            DBExpensesColumns.DATE.value: date_widget.date().toString("yyyy-MM-dd"),
            DBExpensesColumns.SUPPLIER_ID.value: supplier[DBSuppliersColumns.ID.value] if supplier else None,
            DBExpensesColumns.USER_ID_DEDUZIONE.value: user_deduzione[DBUsersColumns.ID.value] if user_deduzione else None,
            DBExpensesColumns.USER_ID_ANTICIPO.value: user_anticipo[DBUsersColumns.ID.value] if user_anticipo else None,
            DBExpensesColumns.LINKED_INVOICE_ID.value: invoice[DBInvoicesColumns.ID.value] if invoice else None,
            DBExpensesColumns.ACCOUNT_ID.value: account[DBAccountsColumns.ID.value] if account else None,
            DBExpensesColumns.CATEGORY.value: self._combo_text(DBExpensesColumns.CATEGORY.value),
            DBExpensesColumns.NET_AMOUNT.value: self.expense_widgets[
                DBExpensesColumns.NET_AMOUNT.value
            ].text().strip(),
            DBExpensesColumns.IVA_AMOUNT.value: self.expense_widgets[
                DBExpensesColumns.IVA_AMOUNT.value
            ].text().strip(),
            DBExpensesColumns.TOT_AMOUNT.value: self.expense_widgets[
                DBExpensesColumns.TOT_AMOUNT.value
            ].text().strip(),
            DBExpensesColumns.DEDUCIBILE.value: self._combo_text(DBExpensesColumns.DEDUCIBILE.value),
        }

        # La legacy non aggiorna il nome se la spesa e' ricorrente: il
        # widget e' assente in quel caso, quindi rispettiamo lo stesso
        # comportamento.
        name_widget = self.expense_widgets.get(DBExpensesColumns.NAME.value)
        if name_widget is not None and not self.expense.get(DBExpensesColumns.RICORRENTE.value):
            expense_data[DBExpensesColumns.NAME.value] = name_widget.text().strip()

        success, message = self.expense_controller.update_expense(
            self.current_expense_id, expense_data
        )
        if not success:
            QMessageBox.critical(self, "ERRORE", message)
            return

        try:
            self.update_controller.on_adding_expense()
        except Exception:
            pass

        QMessageBox.information(self, "SALVATAGGIO COMPLETATO", message)
        self.modify_switch.setChecked(False)
        self.load_expense(self.current_expense_id)

    def _delete_expense(self):
        confirm = QMessageBox.question(
            self,
            "ELIMINAZIONE SPESA",
            "Stai per eliminare questa spesa.\nDesideri continuare?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        success, message = self.expense_controller.delete_expense(self.current_expense_id)
        if not success:
            QMessageBox.critical(self, "ERRORE", message)
            return

        try:
            self.update_controller.on_adding_expense()
        except Exception:
            pass

        QMessageBox.information(self, "SPESA ELIMINATA", message)
        self._cleanup_and_go_back()

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _cleanup_and_go_back(self):
        if self.on_back is not None:
            self.on_back()

    def _combo_text(self, key):
        widget = self.expense_widgets.get(key)
        if isinstance(widget, QTFilterableComboBox):
            return widget.value()
        if isinstance(widget, QComboBox):
            return widget.currentText().strip()
        if hasattr(widget, "text"):
            return widget.text().strip()
        return ""

    def _set_combo_text(self, combo, value):
        if value is None:
            return
        if isinstance(combo, QTFilterableComboBox):
            combo.set_value(value)
            return
        text = str(value)
        idx = combo.findText(text)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        elif combo.isEditable():
            combo.setEditText(text)

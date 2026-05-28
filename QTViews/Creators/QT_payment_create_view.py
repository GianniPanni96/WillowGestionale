"""
Versione QT del creator di un pagamento.

Equivalente di Views/Creators/Payment_create_view.PaymentCreateView,
realizzato come QDialog modale sulla scia di QTInvoiceCreateViewH /
QTPaymentDetailViewH: QScrollArea + QFormLayout, stessa convenzione
widget/error_labels e notifica al chiamante via
``on_payment_created(payment_id)``.

La logica di dominio resta invariata:
- selezione fattura tramite QTFilterableComboBox (view-friendly:
  "<numero_fattura> - <cliente>"); la fattura selezionata determina
  rateizzazione e importo precompilato della rata;
- combo rata legata alla rateizzazione (1 sola voce se la fattura ha
  numero_rate = 1, altrimenti 1/2/3);
- compilazione automatica dell'importo in funzione della rata
  selezionata, segnalando se gia' saldata;
- selezione conto dalla lista conti disponibili.
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
    DBClientsColumns,
    DBInvoicesColumns,
    DBPaymentsColumns,
    Rateizzazione,
)
from QTViews.CustomWidgets.QT_filterable_combo_box import QTFilterableComboBox

if TYPE_CHECKING:
    from App_context import AppContext


class QTPaymentCreateViewH(QDialog):
    """
    QDialog modale per la creazione di un nuovo pagamento.

    Le chiavi degli error_labels e dei widget riprendono quelle della
    legacy: PAYMENT_NAME, PAYMENT_AMOUNT, LINKED_RATA. Il save
    inoltra a ``PaymentsController.save_payment`` lo stesso dict.
    """

    INVOICE_FIELD = "NOME FATTURA"
    ACCOUNT_FIELD = "NOME CONTO"

    def __init__(self, app_context: "AppContext", parent=None, on_payment_created=None):
        super().__init__(parent)

        self.app_context = app_context
        self.payment_controller = app_context.payment_controller
        self.payments_query_service = app_context.payments_query_service
        self.invoices_query_service = app_context.invoices_query_service
        self.clients_query_service = app_context.clients_query_service
        self.accounts_query_service = app_context.account_query_service
        self.on_payment_created = on_payment_created

        self.setWindowTitle("Aggiungi Nuovo Pagamento")
        self.resize(560, 700)
        self.setModal(True)

        self.payment_widgets: dict = {}
        self.payment_labels: dict = {}
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

        self._build_invoice_row()
        self._build_linked_rata_row()
        self._build_simple_entry(DBPaymentsColumns.PAYMENT_NAME.value, "Nome Pagamento", with_error=True)
        self._build_simple_entry(DBPaymentsColumns.PAYMENT_AMOUNT.value, "Importo (€)", with_error=True)
        self._build_payment_date_row()
        self._build_account_row()

        bottom = QHBoxLayout()
        bottom.setContentsMargins(20, 10, 20, 20)
        bottom.addStretch(1)
        self.save_button = QPushButton("Salva Pagamento")
        self.save_button.setMinimumSize(140, 40)
        self.save_button.clicked.connect(self._save_payment_data)
        bottom.addWidget(self.save_button)
        bottom.addStretch(1)
        outer.addLayout(bottom)

        self._bind_validations()

    def _build_invoice_row(self):
        invoice_values = list(self._construct_invoices_view_friendly().values())[::-1]
        combo = QTFilterableComboBox(
            values=invoice_values,
            placeholder="Cerca fattura…",
            autofill=True,
        )
        combo.currentTextChanged.connect(self._on_invoice_selected)

        label = QLabel(self.INVOICE_FIELD)
        self.form_layout.addRow(label, combo)
        self.payment_widgets[self.INVOICE_FIELD] = combo
        self.payment_labels[self.INVOICE_FIELD] = label

    def _build_linked_rata_row(self):
        combo = QComboBox()
        combo.addItems(["1", "2", "3"])
        combo.currentTextChanged.connect(self._control_linked_rata)
        label = QLabel("Rata Associata")
        self.form_layout.addRow(label, combo)
        self.payment_widgets[DBPaymentsColumns.LINKED_RATA.value] = combo
        self.payment_labels[DBPaymentsColumns.LINKED_RATA.value] = label

        error = QLabel("")
        error.setStyleSheet("color: #e39e27;")
        self.form_layout.addRow("", error)
        self.error_labels[DBPaymentsColumns.LINKED_RATA.value] = error

    def _build_simple_entry(self, key, label_text, with_error=False):
        edit = QLineEdit()
        label = QLabel(label_text)
        self.form_layout.addRow(label, edit)
        self.payment_widgets[key] = edit
        self.payment_labels[key] = label

        if with_error:
            error = QLabel("")
            error.setStyleSheet("color: #d62929;")
            self.form_layout.addRow("", error)
            self.error_labels[key] = error

    def _build_payment_date_row(self):
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("yyyy-MM-dd")
        date_edit.setDate(QDate.currentDate())
        label = QLabel("Data Contabilizzazione")
        self.form_layout.addRow(label, date_edit)
        self.payment_widgets[DBPaymentsColumns.PAYMENT_DATE.value] = date_edit
        self.payment_labels[DBPaymentsColumns.PAYMENT_DATE.value] = label

    def _build_account_row(self):
        accounts = self.accounts_query_service.retrieve_accounts_map_list()
        combo = QComboBox()
        combo.addItems([account[DBAccountsColumns.NAME.value] for account in accounts])
        label = QLabel(self.ACCOUNT_FIELD)
        self.form_layout.addRow(label, combo)
        self.payment_widgets[self.ACCOUNT_FIELD] = combo
        self.payment_labels[self.ACCOUNT_FIELD] = label

    # ------------------------------------------------------------------
    # Validazioni
    # ------------------------------------------------------------------

    def _bind_validations(self):
        name_edit: QLineEdit = self.payment_widgets[DBPaymentsColumns.PAYMENT_NAME.value]
        name_error = self.error_labels[DBPaymentsColumns.PAYMENT_NAME.value]

        def _validate_name():
            if not name_edit.text().strip():
                name_error.setText("Il campo non puo essere vuoto.")
            else:
                name_error.setText("")

        name_edit.editingFinished.connect(_validate_name)

        amount_edit: QLineEdit = self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value]
        amount_error = self.error_labels[DBPaymentsColumns.PAYMENT_AMOUNT.value]

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
    # Inizializzazione e callback dinamici
    # ------------------------------------------------------------------

    def _initialize_default_values(self):
        invoice_values = list(self._construct_invoices_view_friendly().values())[::-1]
        if invoice_values:
            self.payment_widgets[self.INVOICE_FIELD].set_value(invoice_values[0])
            self._on_invoice_selected(invoice_values[0])

    def prefill_invoice(self, invoice_name: str) -> None:
        """Pre-seleziona la fattura col numero_fattura dato nel combo.

        Cerca il primo valore del combo che inizia con ``invoice_name + ' - '``
        e lo imposta come selezione corrente, aggiornando importo e rata.
        """
        if not invoice_name:
            return
        combo = self.payment_widgets.get(self.INVOICE_FIELD)
        if combo is None:
            return
        prefix = f"{invoice_name} - "
        for item in combo.all_values():
            if item.startswith(prefix) or item == invoice_name:
                combo.set_value(item)
                self._on_invoice_selected(item)
                return

    def _construct_invoices_view_friendly(self, year=None):
        invoices = {}
        for invoice in self.invoices_query_service.retrieve_invoices_map_list(
            year=year, include_unpaid_invoices=True
        ):
            client = self.clients_query_service.retrieve_client_map_by_id(
                invoice[DBInvoicesColumns.ID_CLIENTE.value]
            )
            client_name = client[DBClientsColumns.NAME.value] if client else "Cliente non trovato"
            invoices[invoice[DBInvoicesColumns.ID.value]] = (
                f"{invoice[DBInvoicesColumns.NUMERO_FATTURA.value]} - {client_name}"
            )
        return invoices

    @staticmethod
    def _extract_invoice_name(invoice_value):
        parts = invoice_value.split(" - ")
        if len(parts) >= 3:
            # Numero fattura legacy con trattini interni ("FN-2024-001 - Cliente").
            return " - ".join(parts[:3])
        # Caso standard "<numero> - <cliente>".
        return parts[0].strip() if parts else invoice_value.strip()

    def _get_selected_invoice_map(self):
        selected_value = self.payment_widgets[self.INVOICE_FIELD].value()
        if not selected_value:
            return None
        invoice_name = self._extract_invoice_name(selected_value)
        return self.invoices_query_service.retrieve_invoice_map_by_name(invoice_name)

    def _on_invoice_selected(self, _selected_value):
        invoice = self._get_selected_invoice_map()
        if not invoice:
            return

        rata_combo: QComboBox = self.payment_widgets[DBPaymentsColumns.LINKED_RATA.value]
        rateizzazione = int(invoice[DBInvoicesColumns.NUMERO_RATE.value])

        rata_combo.blockSignals(True)
        rata_combo.clear()
        if rateizzazione == int(Rateizzazione.UNA.value):
            rata_combo.addItems(["1"])
            rata_combo.setEnabled(False)
            rata_combo.setCurrentText("1")
        else:
            rata_combo.addItems(["1", "2", "3"])
            rata_combo.setEnabled(True)
            rata_combo.setCurrentText("1")
        rata_combo.blockSignals(False)

        self._autofill_payment_amount()
        self._control_linked_rata(rata_combo.currentText())

    def _autofill_payment_amount(self):
        invoice = self._get_selected_invoice_map()
        if not invoice:
            return
        amount_widget: QLineEdit = self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value]
        invoice_amount = float(invoice[DBInvoicesColumns.NETTO_A_PAGARE.value])
        invoice_rateiz = int(invoice[DBInvoicesColumns.NUMERO_RATE.value])
        if invoice_rateiz == int(Rateizzazione.UNA.value):
            amount_widget.setText(f"{invoice_amount:.2f}")
        else:
            amount_widget.setText(f"{round(invoice_amount / 3, 2):.2f}")

    def _control_linked_rata(self, selected_value):
        invoice = self._get_selected_invoice_map()
        if not invoice:
            return False

        # Replica fedele della logica della legacy: distribuiamo il netto
        # sulle rate, sommiamo i pagamenti gia' esistenti per rata e
        # decidiamo se quella selezionata e' gia' saldata.
        netto_rate_fattura = {"1": 0.0, "2": 0.0, "3": 0.0}
        netto_rate_pagate = {"1": 0.0, "2": 0.0, "3": 0.0}
        rate_saldate = {"1": False, "2": False, "3": False}

        if int(invoice[DBInvoicesColumns.NUMERO_RATE.value]) == int(Rateizzazione.UNA.value):
            netto_rate_fattura["1"] = float(invoice[DBInvoicesColumns.NETTO_A_PAGARE.value])
        else:
            rata = float(invoice[DBInvoicesColumns.NETTO_A_PAGARE.value]) / 3
            netto_rate_fattura = {"1": rata, "2": rata, "3": rata}

        payments = self.payments_query_service.retrieve_payments_map_list_by_invoice_id(
            invoice[DBInvoicesColumns.ID.value], year=-1
        )
        for payment in payments:
            rata = str(payment[DBPaymentsColumns.LINKED_RATA.value])
            if rata in netto_rate_pagate:
                netto_rate_pagate[rata] += float(payment[DBPaymentsColumns.PAYMENT_AMOUNT.value])

        for rata in ("1", "2", "3"):
            tot_mancante = netto_rate_fattura[rata] - netto_rate_pagate[rata]
            if netto_rate_pagate[rata] >= netto_rate_fattura[rata] or (5 > tot_mancante > 0):
                rate_saldate[rata] = True

        selected_rata = str(selected_value) if selected_value else "1"
        amount_widget: QLineEdit = self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value]
        error_label: QLabel = self.error_labels[DBPaymentsColumns.LINKED_RATA.value]

        if rate_saldate.get(selected_rata):
            error_label.setText(
                f"La rata {selected_rata} e' gia interamente saldata "
                f"({round(netto_rate_pagate[selected_rata], 2)} EUR)"
            )
            amount_widget.setText("0.00")
            return True

        tot_mancante = netto_rate_fattura[selected_rata] - netto_rate_pagate[selected_rata]
        error_label.setText("")
        amount_widget.setText(f"{round(tot_mancante, 2):.2f}")

        if netto_rate_pagate[selected_rata] > 0 and tot_mancante >= 5:
            error_label.setText(
                f"Totale mancante da saldare della rata {selected_rata}: "
                f"{round(tot_mancante, 2)} EUR"
            )
        return False

    # ------------------------------------------------------------------
    # Salvataggio
    # ------------------------------------------------------------------

    def _collect_payment_data(self):
        payment_data = {}
        for key, widget in self.payment_widgets.items():
            if isinstance(widget, QTFilterableComboBox):
                payment_data[key] = widget.value()
            elif isinstance(widget, QComboBox):
                payment_data[key] = widget.currentText().strip()
            elif isinstance(widget, QLineEdit):
                payment_data[key] = widget.text().strip()
            elif isinstance(widget, QDateEdit):
                payment_data[key] = widget.date().toString("yyyy-MM-dd")
        return payment_data

    def _save_payment_data(self):
        payment_data = self._collect_payment_data()
        invoice = self._get_selected_invoice_map()
        if not invoice:
            QMessageBox.critical(self, "ERRORE", "Fattura associata non valida.")
            return

        # Sostituiamo la stringa "<numero> - <cliente>" con il vero
        # invoice_id, come fa la legacy prima di chiamare il controller.
        payment_data[DBPaymentsColumns.INVOICE_ID.value] = invoice[DBInvoicesColumns.ID.value]

        # Risolviamo il nome conto in conto_id se il controller lo
        # richiede via chiave (mantenendo anche ACCOUNT_FIELD per
        # compatibilita').
        account_name = payment_data.get(self.ACCOUNT_FIELD)
        account = self.accounts_query_service.retrieve_account_map_by_name(account_name) if account_name else None
        if account:
            payment_data[DBPaymentsColumns.CONTO_ID.value] = account[DBAccountsColumns.ID.value]

        rata_gia_saldata = self._control_linked_rata(
            payment_data.get(DBPaymentsColumns.LINKED_RATA.value)
        )
        if rata_gia_saldata:
            confirm = QMessageBox.question(
                self,
                "CONFERMA OPERAZIONE",
                "La rata selezionata presenta gia un pagamento associato.\n"
                "Sei sicuro di voler continuare?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if confirm != QMessageBox.Yes:
                return

        success, message = self.payment_controller.save_payment(payment_data)
        if not success:
            QMessageBox.critical(self, "ERRORE", message)
            return

        payment_map = self.payments_query_service.retrieve_last_payment_insert_map()
        payment_id = payment_map[DBPaymentsColumns.ID.value] if payment_map else None

        if self.on_payment_created is not None and payment_id is not None:
            self.on_payment_created(payment_id)

        self.accept()

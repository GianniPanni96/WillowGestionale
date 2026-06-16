"""
Versione QT del dettaglio di un pagamento.

Equivalente di Views/Details/Payment_detail_view.PaymentDetailView,
portato sui widget Qt mantenendo la stessa logica di dominio:
- sezione informazioni in griglia 2x2 (Dati Generali / Dati Fiscali /
  Collegamenti / Note), con la fattura come QTFilterableComboBox, conto
  e rata come QComboBox e produzione come label statica (deriva dalla
  fattura selezionata);
- switch "Abilita la modifica" che sblocca i campi editabili e i
  bottoni Salva / Elimina;
- al cambio fattura si ricalcola rateizzazione (1 o 1/2/3) e si
  aggiorna la produzione mostrata;
- la sezione storica e' minimale per il pagamento (e' associato
  comunque a una sola fattura): mostriamo direttamente il pulsante di
  accesso al dettaglio della fattura collegata, attraverso l'event_bus
  esattamente come fa la production detail.

Strutturalmente segue il pattern di QTProductionDetailViewH /
QTClientDetailViewH: head bar persistente (back + titolo + switch),
QScrollArea per il corpo, refresh totale via load_payment().
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
    QSizePolicy,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from Gestionale_Enums import (
    DBAccountsColumns,
    DBClientsColumns,
    DBInvoicesColumns,
    DBPaymentsColumns,
    DBProductionsColumns,
    Rateizzazione,
)
from QTViews.CustomWidgets.QT_filterable_combo_box import QTFilterableComboBox
from QTViews.CustomWidgets.QT_warning_banner import WarningBanner
from WarningServices.Warning_types import WarningInfo, WarningSeverity
from Utils.View_utils import ViewUtils

if TYPE_CHECKING:
    from App_context import AppContext


class QTPaymentDetailViewH(QWidget):
    """
    QWidget dettaglio pagamento.
    """

    INVOICE_FIELD = "FATTURA ASSOCIATA"
    ACCOUNT_FIELD = "CONTO"
    PRODUCTION_FIELD = "PRODUZIONE ASSOCIATA"

    SECTIONS = ["Dati Generali", "Dati Fiscali", "Collegamenti", "Note"]

    def __init__(self, app_context: "AppContext", payment_id, on_back, parent=None):
        super().__init__(parent)

        self.app_context = app_context
        self.payment_controller = app_context.payment_controller
        self.payments_query_service = app_context.payments_query_service
        self.invoices_query_service = app_context.invoices_query_service
        self.clients_query_service = app_context.clients_query_service
        self.productions_query_service = app_context.productions_query_service
        self.accounts_query_service = app_context.account_query_service
        self.update_controller = app_context.update_controller
        self.event_bus = app_context.event_bus

        self.current_payment_id = payment_id
        self.payment = None
        self.on_back = on_back

        self.payment_widgets: dict = {}
        self.payment_labels: dict = {}
        self.section_grids: dict = {}
        self.section_rows: dict = {}

        self._build_ui()
        self.load_payment(payment_id)

    # ------------------------------------------------------------------
    # UI base
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        head = QFrame()
        head.setObjectName("PaymentDetailHead")
        head.setStyleSheet(
            "#PaymentDetailHead { background-color: palette(window); border-radius: 6px; }"
        )
        head_layout = QHBoxLayout(head)
        head_layout.setContentsMargins(10, 6, 10, 6)

        self.back_button = QPushButton("Elenco Pagamenti")
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
        self.content_layout.setSpacing(45)

    def _build_info_section(self, payment_data):
        # Warning banner: visibile solo per i sev 1 (FK rotte). I sev 2/3
        # restano confinati alla list view.
        self.warning_banner = WarningBanner()
        self.content_layout.addWidget(self.warning_banner)
        self._current_warning_info = self._compute_current_warning(payment_data)
        if self._is_consistency_warning(self._current_warning_info):
            self.warning_banner.set_warning(self._current_warning_info)
        else:
            self.warning_banner.hide_warning()

        self.info_frame = QFrame()
        self.info_frame.setObjectName("PaymentInfoFrame")
        self.info_frame.setStyleSheet(
            "#PaymentInfoFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
        )
        info_layout = QGridLayout(self.info_frame)
        info_layout.setContentsMargins(15, 15, 15, 15)
        info_layout.setHorizontalSpacing(20)
        info_layout.setVerticalSpacing(10)

        # Griglia 2 colonne: Dati Generali / Dati Fiscali (riga 0),
        # Collegamenti / Note (riga 1).
        for i, name in enumerate(self.SECTIONS):
            section_frame = QFrame()
            section_frame.setObjectName("PaymentInfoSectionFrame")
            section_frame.setStyleSheet(
                "#PaymentInfoSectionFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
            )
            section_layout = QGridLayout(section_frame)
            section_layout.setContentsMargins(10, 10, 10, 10)
            section_layout.setHorizontalSpacing(8)
            section_layout.setVerticalSpacing(8)

            section_title = QLabel(name)
            font = section_title.font()
            font.setBold(True)
            font.setPointSize(12)
            section_title.setFont(font)
            section_layout.addWidget(section_title, 0, 0, 1, 2)

            row = i // 2
            col = i % 2
            info_layout.addWidget(section_frame, row, col)
            info_layout.setColumnStretch(col, 1)
            self.section_grids[name] = section_layout
            self.section_rows[name] = 1

        # --- Dati Generali ---
        self._add_field(
            "Dati Generali",
            DBPaymentsColumns.PAYMENT_DATE.value,
            "Data Pagamento",
            self._make_date_edit(payment_data.get(DBPaymentsColumns.PAYMENT_DATE.value)),
        )

        # --- Dati Fiscali ---
        self._add_field(
            "Dati Fiscali",
            DBPaymentsColumns.PAYMENT_AMOUNT.value,
            "Importo Pagato (€)",
            self._make_line_edit(payment_data.get(DBPaymentsColumns.PAYMENT_AMOUNT.value, "")),
        )

        # --- Collegamenti ---
        invoice_combo = QTFilterableComboBox(
            values=[
                invoice[DBInvoicesColumns.NUMERO_FATTURA.value]
                for invoice in self.invoices_query_service.retrieve_invoices_map_list(
                    year=-1, include_unpaid_invoices=True
                )
            ],
            placeholder="Cerca fattura…",
            autofill=True,
        )
        invoice_combo.set_value(payment_data.get(self.INVOICE_FIELD, ""))
        invoice_combo.currentTextChanged.connect(self._on_invoice_changed)
        self._add_field("Collegamenti", self.INVOICE_FIELD, "Fattura Associata", invoice_combo)

        rata_combo = QComboBox()
        rata_combo.addItems(["1", "2", "3"])
        self._set_combo_text(rata_combo, payment_data.get(DBPaymentsColumns.LINKED_RATA.value))
        self._add_field("Collegamenti", DBPaymentsColumns.LINKED_RATA.value, "Rata Associata", rata_combo)

        production_label = QLabel(str(payment_data.get(self.PRODUCTION_FIELD, "")))
        self._add_field("Collegamenti", self.PRODUCTION_FIELD, "Produzione Associata", production_label)

        accounts = self.accounts_query_service.retrieve_accounts_map_list()
        account_combo = QComboBox()
        account_combo.addItems([account[DBAccountsColumns.NAME.value] for account in accounts])
        self._set_combo_text(account_combo, payment_data.get(self.ACCOUNT_FIELD))
        self._add_field("Collegamenti", self.ACCOUNT_FIELD, "Conto", account_combo)

        # --- Note: timestamp read-only ---
        created_lbl = QLabel(str(payment_data.get(DBPaymentsColumns.CREATED_AT.value, "") or ""))
        self._add_field("Note", DBPaymentsColumns.CREATED_AT.value, "Data Creazione", created_lbl)

        updated_lbl = QLabel(str(payment_data.get(DBPaymentsColumns.UPDATED_AT.value, "") or ""))
        self._add_field("Note", DBPaymentsColumns.UPDATED_AT.value, "Ultimo Aggiornamento", updated_lbl)

        # Riga bottoni Salva / Elimina.
        buttons_frame = QFrame()
        buttons_layout = QHBoxLayout(buttons_frame)
        buttons_layout.setContentsMargins(15, 15, 15, 15)

        self.save_btn = QPushButton("Salva Pagamento")
        self.save_btn.clicked.connect(self._save_payment_mod)
        buttons_layout.addWidget(self.save_btn)

        buttons_layout.addStretch(1)

        self.delete_btn = QPushButton("Elimina Pagamento")
        self.delete_btn.setStyleSheet(
            "QPushButton { background-color: #8B0000; color: palette(highlighted-text); }"
            "QPushButton:hover { background-color: #A52A2A; }"
            "QPushButton:disabled { background-color: #4a2727; color: palette(mid); }"
        )
        self.delete_btn.clicked.connect(self._delete_payment)
        buttons_layout.addWidget(self.delete_btn)

        info_layout.addWidget(buttons_frame, 2, 0, 1, 2)

        self.content_layout.addWidget(self.info_frame)

    def _add_field(self, section_name, key, label_text, widget):
        grid = self.section_grids[section_name]
        row = self.section_rows[section_name]
        label = QLabel(label_text + ":")
        grid.addWidget(label, row, 0, alignment=Qt.AlignLeft)
        grid.addWidget(widget, row, 1)
        self.payment_widgets[key] = widget
        self.payment_labels[key] = label
        self.section_rows[section_name] = row + 1

    def _make_line_edit(self, value):
        edit = QLineEdit()
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
    # Caricamento dati di un pagamento specifico
    # ------------------------------------------------------------------

    def load_payment(self, payment_id):
        self.current_payment_id = payment_id
        self._clear_content()

        payment = self.payments_query_service.retrieve_payment_map_by_id(payment_id)
        if not payment:
            self.title_label.setText("Pagamento non trovato")
            return

        # Arricchiamo il dict con i nomi risolti (come nella legacy):
        # FATTURA, CONTO, PRODUZIONE, NOME CLIENTE.
        invoice = self.invoices_query_service.retrieve_invoice_map_by_id(
            payment[DBPaymentsColumns.INVOICE_ID.value]
        )
        if invoice:
            account = self.accounts_query_service.retrieve_account_map_by_id(
                payment[DBPaymentsColumns.CONTO_ID.value]
            )
            client = self.clients_query_service.retrieve_client_map_by_id(
                invoice[DBInvoicesColumns.ID_CLIENTE.value]
            )
            production = self.productions_query_service.retrieve_production_map_by_id(
                invoice[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value]
            )
            payment[self.ACCOUNT_FIELD] = account[DBAccountsColumns.NAME.value] if account else "Conto non trovato"
            payment[self.INVOICE_FIELD] = invoice[DBInvoicesColumns.NUMERO_FATTURA.value]
            payment[self.PRODUCTION_FIELD] = production[DBProductionsColumns.NAME.value] if production else "Produzione non trovata"
            payment[DBClientsColumns.NAME.value] = client[DBClientsColumns.NAME.value] if client else "Cliente non trovato"

        self.payment = payment
        self.title_label.setText(str(payment.get(DBPaymentsColumns.PAYMENT_NAME.value, "")))

        self._build_info_section(payment)
        self._toggle_edit(self.modify_switch.isChecked())

        self._build_history_section()
        self._apply_broken_field_highlight()

    def _clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.payment_widgets.clear()
        self.payment_labels.clear()
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
            DBPaymentsColumns.CREATED_AT.value,
            DBPaymentsColumns.UPDATED_AT.value,
            self.PRODUCTION_FIELD,
        }
        for key, widget in self.payment_widgets.items():
            if key in readonly_keys:
                continue
            widget.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Callback dinamici
    # ------------------------------------------------------------------

    def _on_invoice_changed(self, selected_invoice_name):
        invoice = self.invoices_query_service.retrieve_invoice_map_by_name(selected_invoice_name)
        if not invoice:
            return

        rate_count = int(invoice[DBInvoicesColumns.NUMERO_RATE.value])
        rata_combo: QComboBox = self.payment_widgets[DBPaymentsColumns.LINKED_RATA.value]
        rata_combo.blockSignals(True)
        rata_combo.clear()
        if rate_count == int(Rateizzazione.UNA.value):
            rata_combo.addItems(["1"])
            rata_combo.setCurrentText("1")
        else:
            valid_rate = {str(i) for i in range(1, rate_count + 1)}
            rata_combo.addItems(sorted(valid_rate))
            current_rata = str(self.payment.get(DBPaymentsColumns.LINKED_RATA.value, "1")) if self.payment else "1"
            rata_combo.setCurrentText(current_rata if current_rata in valid_rate else "1")
        rata_combo.blockSignals(False)

        # Aggiorna anche la label statica della produzione associata.
        production = self.productions_query_service.retrieve_production_map_by_id(
            invoice[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value]
        )
        production_label: QLabel = self.payment_widgets[self.PRODUCTION_FIELD]
        production_label.setText(
            production[DBProductionsColumns.NAME.value] if production else "Produzione non trovata"
        )

    # ------------------------------------------------------------------
    # Warning di consistenza (sev 1): banner senza dismiss + highlight FK
    # ------------------------------------------------------------------

    def _compute_current_warning(self, payment_data):
        try:
            service = self.app_context.payment_warning_service
            warnings = service.collect_warnings_for_list([payment_data]) or {}
            return warnings.get(payment_data.get(DBPaymentsColumns.PAYMENT_NAME.value))
        except Exception:
            return None

    @staticmethod
    def _is_consistency_warning(info) -> bool:
        return isinstance(info, WarningInfo) and info.severity == WarningSeverity.CONSISTENCY

    # Mappatura tra ``broken_field_key`` (nome colonna DB della FK)
    # e chiave dei widget nel detail.
    _BROKEN_FIELD_WIDGET_MAP = {
        DBPaymentsColumns.INVOICE_ID.value: "FATTURA ASSOCIATA",
        DBPaymentsColumns.CONTO_ID.value: "CONTO",
    }

    def _apply_broken_field_highlight(self):
        info = getattr(self, "_current_warning_info", None)
        if not self._is_consistency_warning(info) or not info.broken_field_key:
            return
        widget_key = self._BROKEN_FIELD_WIDGET_MAP.get(
            info.broken_field_key, info.broken_field_key
        )
        widget = getattr(self, "payment_widgets", {}).get(widget_key)
        if widget is None:
            return
        widget.setStyleSheet(
            widget.styleSheet() + " border: 2px solid #d62929; border-radius: 4px;"
        )

    # ------------------------------------------------------------------
    # Salvataggio / eliminazione
    # ------------------------------------------------------------------

    def _save_payment_mod(self):
        account_name = self._combo_text(self.ACCOUNT_FIELD)
        account = self.accounts_query_service.retrieve_account_map_by_name(account_name)
        invoice_name = self._combo_text(self.INVOICE_FIELD)
        invoice = self.invoices_query_service.retrieve_invoice_map_by_name(invoice_name)

        if not account or not invoice:
            QMessageBox.critical(self, "ERRORE", "Conto o fattura non validi.")
            return

        date_widget: QDateEdit = self.payment_widgets[DBPaymentsColumns.PAYMENT_DATE.value]

        payment_data = {
            DBPaymentsColumns.PAYMENT_NAME.value: self.payment[DBPaymentsColumns.PAYMENT_NAME.value],
            DBPaymentsColumns.PAYMENT_AMOUNT.value: self.payment_widgets[
                DBPaymentsColumns.PAYMENT_AMOUNT.value
            ].text().strip(),
            DBPaymentsColumns.PAYMENT_DATE.value: date_widget.date().toString("yyyy-MM-dd"),
            DBPaymentsColumns.LINKED_RATA.value: self._combo_text(DBPaymentsColumns.LINKED_RATA.value),
            DBPaymentsColumns.INVOICE_ID.value: invoice[DBInvoicesColumns.ID.value],
            DBPaymentsColumns.CONTO_ID.value: account[DBAccountsColumns.ID.value],
        }

        success, message = self.payment_controller.update_payment(self.current_payment_id, payment_data)
        if not success:
            QMessageBox.critical(self, "ERRORE", message)
            return

        # Allinea l'updates controller, come fa la legacy.
        try:
            self.update_controller.on_adding_payment()
        except Exception:
            pass

        QMessageBox.information(self, "SALVATAGGIO COMPLETATO", message)
        self.modify_switch.setChecked(False)
        self.load_payment(self.current_payment_id)

    def _delete_payment(self):
        confirm = QMessageBox.question(
            self,
            "ELIMINAZIONE PAGAMENTO",
            "Stai per eliminare questo pagamento.\nDesideri continuare?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        invoice_id = self.payment[DBPaymentsColumns.INVOICE_ID.value] if self.payment else None
        success, message = self.payment_controller.delete_payment(self.current_payment_id)
        if not success:
            QMessageBox.critical(self, "ERRORE", message)
            return

        try:
            if invoice_id is not None:
                self.update_controller.update_invoices(invoice_id)
            self.update_controller.on_adding_payment()
        except Exception:
            pass

        QMessageBox.information(self, "PAGAMENTO ELIMINATO", message)
        self._cleanup_and_go_back()

    # ------------------------------------------------------------------
    # Sezione storico (fattura collegata)
    # ------------------------------------------------------------------

    def _build_history_section(self):
        wrapper = QFrame()
        wrapper.setObjectName("PaymentHistoryWrapper")
        wrapper.setStyleSheet(
            "#PaymentHistoryWrapper { border: 2px solid palette(highlight); border-radius: 6px; }"
        )
        wrapper_layout = QHBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(15, 15, 15, 15)
        wrapper_layout.setSpacing(20)
        wrapper_layout.setAlignment(Qt.AlignTop)
        wrapper_layout.addWidget(self._create_invoice_history(), stretch=1, alignment=Qt.AlignTop)

        self.content_layout.addWidget(wrapper)

    def _create_invoice_history(self):
        section = self._make_section_frame("DETTAGLIO FATTURA COLLEGATA")

        invoice_id = self.payment[DBPaymentsColumns.INVOICE_ID.value] if self.payment else None
        invoice = self.invoices_query_service.retrieve_invoice_map_by_id(invoice_id) if invoice_id else None

        cards = QHBoxLayout()
        netto_a_pagare = invoice[DBInvoicesColumns.NETTO_A_PAGARE.value] if invoice else 0
        cards.addWidget(self._make_info_card(
            "NETTO A PAGARE FATTURA",
            f"{self._fmt(netto_a_pagare)} €",
        ))
        cards.addWidget(self._make_info_card(
            "IMPORTO DI QUESTO PAGAMENTO",
            f"{self._fmt(self.payment.get(DBPaymentsColumns.PAYMENT_AMOUNT.value) if self.payment else 0)} €",
        ))
        cards.addStretch(1)
        section.layout().addLayout(cards)

        if invoice is not None:
            invoice_name = invoice[DBInvoicesColumns.NUMERO_FATTURA.value]
            btn = QPushButton(f"Apri dettaglio: {invoice_name}")
            btn.setStyleSheet("text-align: left; padding: 6px;")
            btn.clicked.connect(lambda _=False, iid=invoice[DBInvoicesColumns.ID.value]: self._show_invoice_detail(iid))
            section.layout().addWidget(btn)
        else:
            section.layout().addWidget(self._make_subtitle("Nessuna fattura collegata"))

        return section

    def _show_invoice_detail(self, invoice_id):
        self.event_bus.publish(ViewUtils.EventBusKeys.SHOW_INVOICE_DETAIL.value, invoice_id)

    # ------------------------------------------------------------------
    # Helper grafici condivisi con le altre detail Qt
    # ------------------------------------------------------------------

    def _make_section_frame(self, title):
        frame = QFrame()
        frame.setObjectName("PaymentRelatedSectionFrame")
        frame.setStyleSheet(
            "#PaymentRelatedSectionFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(15, 10, 15, 15)
        title_lbl = QLabel(title)
        font = title_lbl.font()
        font.setBold(True)
        font.setPointSize(12)
        title_lbl.setFont(font)
        layout.addWidget(title_lbl)
        return frame

    def _make_info_card(self, title, value):
        card = QFrame()
        card.setObjectName("PaymentInfoCard")
        card.setStyleSheet(
            "#PaymentInfoCard { background-color: palette(alternate-base); border-radius: 6px; }"
            "#PaymentInfoCard QLabel { color: palette(text); }"
        )
        box = QVBoxLayout(card)
        box.setContentsMargins(10, 6, 10, 6)
        title_lbl = QLabel(title)
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet(
            "background-color: palette(highlight); "
            "color: palette(highlighted-text); "
            "padding: 3px; border-radius: 3px;"
        )
        value_lbl = QLabel(str(value))
        value_lbl.setAlignment(Qt.AlignCenter)
        f = value_lbl.font()
        f.setPointSize(11)
        value_lbl.setFont(f)
        box.addWidget(title_lbl)
        box.addWidget(value_lbl)
        return card

    @staticmethod
    def _make_subtitle(text):
        lbl = QLabel(text)
        lbl.setStyleSheet("color: palette(mid); font-style: italic;")
        return lbl

    def _cleanup_and_go_back(self):
        if self.on_back is not None:
            self.on_back()

    def _combo_text(self, key):
        widget = self.payment_widgets.get(key)
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

    @staticmethod
    def _fmt(value):
        if value is None or value == "":
            return "0.00"
        try:
            return format(float(value), ".2f")
        except (TypeError, ValueError):
            return str(value)

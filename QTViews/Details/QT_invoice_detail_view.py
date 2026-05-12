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
    QVBoxLayout,
    QWidget,
)

from Gestionale_Enums import (
    InvoiceSatus,
    PaymentsMethods,
    Rateizzazione,
    RegimeFiscale,
)
from Model import (
    DBAccountsColumns,
    DBClientsColumns,
    DBExpensesColumns,
    DBInvoicesColumns,
    DBPaymentsColumns,
    DBProductionsColumns,
    DBUsersColumns,
)
from QTViews.CustomWidgets.QT_filterable_combo_box import QTFilterableComboBox
from QTViews.CustomWidgets.QT_warning_banner import WarningBanner
from WarningServices.Warning_types import WarningInfo, WarningSeverity

if TYPE_CHECKING:
    from App_context import AppContext


class QTInvoiceDetailViewH(QWidget):
    """
    Versione QT del dettaglio di una fattura.

    Equivalente di Views/Details/Invoice_detail_view.InvoiceDetailView.
    Mantiene la stessa logica (campi editabili / derivati, abilitazione
    modifica via switch, ricalcolo importi al focus-out, salvataggio e
    storno via InvoiceController, sezioni pagamenti e spese collegate)
    portandola sui widget Qt.
    """

    NOME_CONTO = "CONTO"
    NOME_CLIENTE = "CLIENTE"
    NOME_UTENTE = "UTENTE"
    NOME_PRODUZIONE = "PRODUZIONE ASSOCIATA"
    NOME_FATTURA_ASSOCIATA = "FATTURA ASSOCIATA"

    SECTIONS = [
        "Dati Generali",
        "Dati Fiscali",
        "Dati Pagamento",
        "Collegamenti",
        "Note/Status",
    ]
    TOP_ALIGNED_SECTIONS = {"Dati Generali", "Dati Pagamento"}

    DERIVED_FIELDS = {
        DBInvoicesColumns.CASSA_INPS.value: "Cassa INPS (€)",
        DBInvoicesColumns.IMPONIBILE.value: "Imponibile (€)",
        DBInvoicesColumns.IVA.value: "IVA (€)",
        DBInvoicesColumns.TOT_DOCUMENTO.value: "Totale Documento (€)",
        DBInvoicesColumns.RITENUTA.value: "Ritenuta (€)",
        DBInvoicesColumns.NETTO_A_PAGARE.value: "Netto a Pagare (€)",
    }

    def __init__(self, app_context: "AppContext", invoice_id, on_back, parent=None):
        super().__init__(parent)

        self.app_context = app_context
        self.invoice_controller = app_context.invoice_controller
        self.invoices_query_service = app_context.invoices_query_service
        self.invoices_analyzer_service = app_context.invoices_analyzer_service
        self.user_query_service = app_context.user_query_service
        self.clients_query_service = app_context.clients_query_service
        self.productions_query_service = app_context.productions_query_service
        self.account_query_service = app_context.account_query_service

        self.current_invoice_id = invoice_id
        self.on_back = on_back

        self.invoice_widgets: dict = {}
        self.invoice_labels: dict = {}
        self.section_grids: dict = {}
        self.section_rows: dict = {}

        self._build_ui()
        self.load_invoice(invoice_id)

    # ------------------------------------------------------------------
    # UI base
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        head = QFrame()
        head.setObjectName("InvoiceDetailHead")
        head.setStyleSheet(
            "#InvoiceDetailHead { background-color: palette(window); border-radius: 6px; }"
        )
        head_layout = QHBoxLayout(head)
        head_layout.setContentsMargins(10, 6, 10, 6)

        self.back_button = QPushButton("Elenco Fatture")
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
        self.content_layout.setSpacing(55)

    def _build_info_section(self, invoice):
        # Warning banner: visibile solo per i sev 1 (FK rotte). I sev 2/3
        # restano confinati alla list view (bordo sinistro colorato).
        self.warning_banner = WarningBanner()
        self.content_layout.addWidget(self.warning_banner)
        self._current_warning_info = self._compute_current_warning(invoice)
        if self._is_consistency_warning(self._current_warning_info):
            self.warning_banner.set_warning(self._current_warning_info)
        else:
            self.warning_banner.hide_warning()

        # Container con grid 3 colonne, una sezione per cella.
        self.info_frame = QFrame()
        self.info_frame.setObjectName("InvoiceInfoFrame")
        self.info_frame.setStyleSheet(
            "#InvoiceInfoFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
        )
        info_layout = QGridLayout(self.info_frame)
        info_layout.setContentsMargins(15, 15, 15, 15)
        info_layout.setHorizontalSpacing(20)
        info_layout.setVerticalSpacing(10)

        for i, name in enumerate(self.SECTIONS):
            row = 0 if i <= 2 else 1
            col = i if i <= 2 else i - 3

            section_frame = QFrame()
            section_frame.setObjectName(f"InfoSectionFrame")
            section_frame.setStyleSheet(
                "#InfoSectionFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
            )
            section_layout = QGridLayout(section_frame)
            section_layout.setContentsMargins(10, 10, 10, 10)
            section_layout.setHorizontalSpacing(8)
            section_layout.setVerticalSpacing(8)
            if name in self.TOP_ALIGNED_SECTIONS:
                section_layout.setAlignment(Qt.AlignTop)

            section_title = QLabel(name)
            font = section_title.font()
            font.setBold(True)
            font.setPointSize(12)
            section_title.setFont(font)
            section_layout.addWidget(section_title, 0, 0, 1, 2)

            info_layout.addWidget(section_frame, row, col)
            info_layout.setColumnStretch(col, 1)
            self.section_grids[name] = section_layout
            self.section_rows[name] = 1

        # Popolamento sezioni.
        self._add_field("Dati Generali", DBInvoicesColumns.DATA_CREAZIONE.value, "Data Creazione",
                        self._make_date_edit(invoice.get(DBInvoicesColumns.DATA_CREAZIONE.value)))

        clients_combo = QTFilterableComboBox(
            values=[
                c[DBClientsColumns.NAME.value]
                for c in self.clients_query_service.retrieve_clients_map_list()
            ],
            placeholder="Cerca cliente…",
        )
        self._set_combo_text(clients_combo, invoice.get(self.NOME_CLIENTE))
        clients_combo.currentTextChanged.connect(self._on_client_changed)
        self._add_field("Dati Generali", self.NOME_CLIENTE, "Cliente", clients_combo)

        # Dati Fiscali — campi editabili.
        for key, label in [
            (DBInvoicesColumns.SERVIZI.value, "Importo Servizi (€)"),
            (DBInvoicesColumns.RIMBORSI.value, "Rimborsi (€)"),
            (DBInvoicesColumns.RIVALSA_INPS.value, "Rivalsa INPS (€)"),
        ]:
            edit = QLineEdit(self._fmt(invoice.get(key)))
            self._add_field("Dati Fiscali", key, label, edit)

        # Campi derivati — non editabili.
        for key, label in self.DERIVED_FIELDS.items():
            edit = QLineEdit(self._fmt(invoice.get(key)))
            self._add_field("Dati Fiscali", key, label, edit)

        metodo_combo = QComboBox()
        metodo_combo.addItems([m.value for m in PaymentsMethods])
        self._set_combo_text(metodo_combo, invoice.get(DBInvoicesColumns.METODO_PAGAMENTO.value))
        self._add_field("Dati Fiscali", DBInvoicesColumns.METODO_PAGAMENTO.value, "Metodo Pagamento", metodo_combo)

        conto_combo = QComboBox()
        conto_combo.addItems(
            [a[DBAccountsColumns.NAME.value] for a in self.account_query_service.retrieve_accounts_map_list()]
        )
        self._set_combo_text(conto_combo, invoice.get(self.NOME_CONTO))
        self._add_field("Dati Fiscali", self.NOME_CONTO, "Conto", conto_combo)

        # Dati Pagamento.
        rate_combo = QComboBox()
        rate_combo.addItems([r.value for r in Rateizzazione])
        self._set_combo_text(rate_combo, invoice.get(DBInvoicesColumns.NUMERO_RATE.value))
        rate_combo.currentTextChanged.connect(self._on_numero_rate_changed)
        self._add_field("Dati Pagamento", DBInvoicesColumns.NUMERO_RATE.value, "Numero Rate", rate_combo)

        for key, label in [
            (DBInvoicesColumns.DATA_SCADENZA_1.value, "Scadenza 1"),
            (DBInvoicesColumns.DATA_SCADENZA_2.value, "Scadenza 2"),
            (DBInvoicesColumns.DATA_SCADENZA_3.value, "Scadenza 3"),
        ]:
            self._add_field("Dati Pagamento", key, label,
                            self._make_date_edit(invoice.get(key)))

        # Collegamenti.
        prods = self.productions_query_service.retrieve_productions_map_list_by_client_id(
            invoice[DBInvoicesColumns.ID_CLIENTE.value],
            include_prod_with_unpaid_invoices=True,
        )
        prod_combo = QComboBox()
        prod_combo.addItems([p[DBProductionsColumns.NAME.value] for p in prods])
        self._set_combo_text(prod_combo, invoice.get(self.NOME_PRODUZIONE))
        self._add_field("Collegamenti", self.NOME_PRODUZIONE, "Produzione Associata", prod_combo)

        fatt_label = QLabel(str(invoice.get(self.NOME_FATTURA_ASSOCIATA, "") or ""))
        self._add_field("Collegamenti", self.NOME_FATTURA_ASSOCIATA, "Fattura Associata", fatt_label)

        # Note/Status.
        note_edit = QLineEdit(self._fmt(invoice.get(DBInvoicesColumns.NOTE.value)))
        self._add_field("Note/Status", DBInvoicesColumns.NOTE.value, "Note", note_edit)

        status_label = QLabel(str(invoice.get(DBInvoicesColumns.STATUS.value, "") or ""))
        self._add_field("Note/Status", DBInvoicesColumns.STATUS.value, "Status", status_label)

        tipo_label = QLabel(str(invoice.get(DBInvoicesColumns.TIPO.value, "") or ""))
        self._add_field("Note/Status", DBInvoicesColumns.TIPO.value, "Tipo Documento", tipo_label)

        # Riga bottoni.
        buttons_frame = QFrame()
        buttons_layout = QHBoxLayout(buttons_frame)
        buttons_layout.setContentsMargins(15, 15, 15, 15)

        self.save_invoice_btn = QPushButton("Salva Fattura")
        self.save_invoice_btn.clicked.connect(self._save_invoice_mod)
        buttons_layout.addWidget(self.save_invoice_btn)

        buttons_layout.addStretch(1)

        self.storna_btn = QPushButton("Storna Fattura")
        self.storna_btn.clicked.connect(self._storna_invoice)
        buttons_layout.addWidget(self.storna_btn)

        info_layout.addWidget(buttons_frame, 2, 0, 1, 3)

        self.content_layout.addWidget(self.info_frame)

        # Bind ricalcolo derivati su focus-out dei tre campi base.
        for key, is_rivalsa in [
            (DBInvoicesColumns.SERVIZI.value, False),
            (DBInvoicesColumns.RIMBORSI.value, False),
            (DBInvoicesColumns.RIVALSA_INPS.value, True),
        ]:
            widget: QLineEdit = self.invoice_widgets[key]
            widget.editingFinished.connect(
                lambda checked=is_rivalsa: self._toggle_importi_derivati_fattura(checked)
            )

        # Stato iniziale del numero rate (mostra/nasconde scadenza 2 e 3).
        self._on_numero_rate_changed(rate_combo.currentText())
        self._pin_short_sections_to_top()

    def _pin_short_sections_to_top(self):
        for section_name in self.TOP_ALIGNED_SECTIONS:
            grid = self.section_grids.get(section_name)
            next_row = self.section_rows.get(section_name)
            if grid is not None and next_row is not None:
                grid.setRowStretch(next_row, 1)

    def _add_field(self, section_name, key, label_text, widget):
        grid = self.section_grids[section_name]
        row = self.section_rows[section_name]
        label = QLabel(label_text + ":")
        grid.addWidget(label, row, 0, alignment=Qt.AlignLeft)
        grid.addWidget(widget, row, 1)
        self.invoice_widgets[key] = widget
        self.invoice_labels[key] = label
        self.section_rows[section_name] = row + 1

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
    # Caricamento dati di una fattura specifica
    # ------------------------------------------------------------------

    def load_invoice(self, invoice_id):
        self.current_invoice_id = invoice_id
        self._clear_content()

        invoice = self.invoices_query_service.retrieve_invoice_map_by_id(invoice_id)
        if not invoice:
            self.title_label.setText("Fattura non trovata")
            return

        # Risoluzione nomi correlati.
        conto = self.account_query_service.retrieve_account_map_by_id(invoice[DBInvoicesColumns.ID_CONTO.value])
        invoice[self.NOME_CONTO] = conto[DBAccountsColumns.NAME.value] if conto else "Conto non trovato"

        user = self.user_query_service.retrieve_user_map_by_id(invoice[DBInvoicesColumns.ID_UTENTE.value])
        invoice[self.NOME_UTENTE] = (
            f"{user[DBUsersColumns.FIRST_NAME.value]} {user[DBUsersColumns.LAST_NAME.value]}"
            if user else "Utente non trovato"
        )

        cliente = self.clients_query_service.retrieve_client_map_by_id(invoice[DBInvoicesColumns.ID_CLIENTE.value])
        invoice[self.NOME_CLIENTE] = cliente[DBClientsColumns.NAME.value] if cliente else "Cliente non trovato"

        prod = self.productions_query_service.retrieve_production_map_by_id(
            invoice[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value]
        )
        invoice[self.NOME_PRODUZIONE] = prod[DBProductionsColumns.NAME.value] if prod else "Produzione non trovata"

        fatt_ass = self.invoices_query_service.retrieve_invoice_map_by_id(
            invoice[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value]
        )
        invoice[self.NOME_FATTURA_ASSOCIATA] = (
            fatt_ass[DBInvoicesColumns.NUMERO_FATTURA.value] if fatt_ass else "Nessuna fattura associata"
        )

        self.title_label.setText(str(invoice[DBInvoicesColumns.NUMERO_FATTURA.value]))

        self._build_info_section(invoice)
        self._toggle_edit(self.modify_switch.isChecked())

        self._create_payments_section()
        self._create_expenses_section()

        # Highlight rosso del widget FK rotta (eseguito dopo che
        # invoice_widgets e' popolato).
        self._apply_broken_field_highlight()

    def _clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.invoice_widgets.clear()
        self.invoice_labels.clear()
        self.section_grids.clear()
        self.section_rows.clear()
        self.modify_switch.blockSignals(True)
        self.modify_switch.setChecked(False)
        self.modify_switch.blockSignals(False)

    # ------------------------------------------------------------------
    # Modifica abilitata/disabilitata
    # ------------------------------------------------------------------

    def _toggle_edit(self, enabled):
        if not hasattr(self, "save_invoice_btn"):
            return

        self.save_invoice_btn.setEnabled(enabled)
        self.storna_btn.setEnabled(enabled)

        invoice = self.invoices_query_service.retrieve_invoice_map_by_id(self.current_invoice_id)
        if not invoice:
            return
        user = self.user_query_service.retrieve_user_map_by_id(invoice[DBInvoicesColumns.ID_UTENTE.value])
        is_ordinario = user and user[DBUsersColumns.REGIME_FISCALE.value] == RegimeFiscale.ORDINARIO.value

        for key, widget in self.invoice_widgets.items():
            is_derived = key in self.DERIVED_FIELDS
            is_rivalsa_locked = key == DBInvoicesColumns.RIVALSA_INPS.value and is_ordinario
            is_status_or_type = key in (
                DBInvoicesColumns.STATUS.value,
                DBInvoicesColumns.TIPO.value,
                self.NOME_FATTURA_ASSOCIATA,
            )
            widget_state = enabled and not (is_derived or is_rivalsa_locked or is_status_or_type)
            widget.setEnabled(widget_state)

    # ------------------------------------------------------------------
    # Ricalcolo importi derivati
    # ------------------------------------------------------------------

    def _toggle_importi_derivati_fattura(self, is_rivalsa_inps):
        try:
            servizi = float(self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].text() or 0)
            rimborsi = float(self.invoice_widgets[DBInvoicesColumns.RIMBORSI.value].text() or 0)
            rivalsa_inps = float(self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].text() or 0)
        except ValueError:
            return

        invoice = self.invoices_query_service.retrieve_invoice_map_by_id(self.current_invoice_id)
        if not invoice:
            return
        user = self.user_query_service.retrieve_user_map_by_id(invoice[DBInvoicesColumns.ID_UTENTE.value])
        regime_fiscale = user[DBUsersColumns.REGIME_FISCALE.value] if user else None
        client = self.clients_query_service.retrieve_client_map_by_id(invoice[DBInvoicesColumns.ID_CLIENTE.value])
        tipologia_cliente = client[DBClientsColumns.TIPOLOGIA.value] if client else None

        try:
            importi = self.invoices_analyzer_service.calcola_derivati_fattura(
                regime_fiscale, tipologia_cliente, servizi, rimborsi, rivalsa_inps
            )
        except ValueError:
            return

        if not is_rivalsa_inps:
            self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].setText(
                self._fmt(importi[DBInvoicesColumns.RIVALSA_INPS.value])
            )

        for key in (
            DBInvoicesColumns.CASSA_INPS.value,
            DBInvoicesColumns.IMPONIBILE.value,
            DBInvoicesColumns.IVA.value,
            DBInvoicesColumns.TOT_DOCUMENTO.value,
            DBInvoicesColumns.RITENUTA.value,
            DBInvoicesColumns.NETTO_A_PAGARE.value,
        ):
            self.invoice_widgets[key].setText(self._fmt(importi[key]))

    def _on_client_changed(self, client_name):
        cliente = self.clients_query_service.retrieve_client_map_by_name(client_name)
        if not cliente:
            return
        prods = self.productions_query_service.retrieve_productions_map_list_by_client_id(
            cliente[DBClientsColumns.ID.value], include_prod_with_unpaid_invoices=True
        )
        prod_combo: QComboBox = self.invoice_widgets[self.NOME_PRODUZIONE]
        prod_combo.blockSignals(True)
        prod_combo.clear()
        prod_combo.addItems([p[DBProductionsColumns.NAME.value] for p in prods])
        prod_combo.blockSignals(False)

    def _on_numero_rate_changed(self, value):
        is_rateizzata = str(value) == Rateizzazione.TRE.value
        for key in (
            DBInvoicesColumns.DATA_SCADENZA_2.value,
            DBInvoicesColumns.DATA_SCADENZA_3.value,
        ):
            widget = self.invoice_widgets.get(key)
            label = self.invoice_labels.get(key)
            if widget is not None:
                widget.setVisible(is_rateizzata)
            if label is not None:
                label.setVisible(is_rateizzata)

    # ------------------------------------------------------------------
    # Warning di consistenza (sev 1): banner senza dismiss + highlight FK
    # ------------------------------------------------------------------

    def _compute_current_warning(self, invoice):
        """Restituisce il WarningInfo per la fattura corrente, oppure
        None. La config di visibilita' NON viene applicata: i sev 1
        sono sempre visibili e i sev 2/3 non vanno mostrati nel detail
        (banner riservato ai sev 1)."""
        try:
            service = self.app_context.invoice_warning_service
            warnings = service.collect_warnings_for_list([invoice]) or {}
            return warnings.get(invoice.get(DBInvoicesColumns.NUMERO_FATTURA.value))
        except Exception:
            return None

    @staticmethod
    def _is_consistency_warning(info) -> bool:
        return isinstance(info, WarningInfo) and info.severity == WarningSeverity.CONSISTENCY

    # Mappatura tra ``broken_field_key`` (nome colonna DB della FK
    # restituito dal warning service) e chiave dei widget nel detail.
    @property
    def _broken_field_widget_map(self):
        return {
            DBInvoicesColumns.ID_CLIENTE.value: self.NOME_CLIENTE,
            DBInvoicesColumns.ID_UTENTE.value: self.NOME_UTENTE,
            DBInvoicesColumns.ID_CONTO.value: self.NOME_CONTO,
            DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value: self.NOME_PRODUZIONE,
            DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value: self.NOME_FATTURA_ASSOCIATA,
        }

    def _apply_broken_field_highlight(self):
        """Evidenzia in rosso il widget che corrisponde alla FK rotta.

        Il widget viene cercato in ``self.invoice_widgets`` usando la
        mappatura ``_broken_field_widget_map`` (DB col -> chiave
        widget). Lo stylesheet rosso resta in vigore finche' il widget
        non viene ricreato dal prossimo ``load_invoice``."""
        info = getattr(self, "_current_warning_info", None)
        if not self._is_consistency_warning(info) or not info.broken_field_key:
            return
        widget_key = self._broken_field_widget_map.get(
            info.broken_field_key, info.broken_field_key
        )
        widget = getattr(self, "invoice_widgets", {}).get(widget_key)
        if widget is None:
            return
        widget.setStyleSheet(
            widget.styleSheet() + " border: 2px solid #d62929; border-radius: 4px;"
        )

    # ------------------------------------------------------------------
    # Salvataggio
    # ------------------------------------------------------------------

    def _save_invoice_mod(self):
        # Forza ricalcolo dei derivati prima di salvare.
        self._toggle_importi_derivati_fattura(is_rivalsa_inps=True)

        nome_conto = self._combo_text(self.NOME_CONTO)
        conto = self.account_query_service.retrieve_account_map_by_name(nome_conto)
        id_conto = conto[DBAccountsColumns.ID.value] if conto else None

        nome_cliente = self._combo_text(self.NOME_CLIENTE)
        cliente = self.clients_query_service.retrieve_client_map_by_name(nome_cliente)
        if not cliente:
            QMessageBox.critical(self, "ERRORE", "Cliente non valido")
            return
        id_cliente = cliente[DBClientsColumns.ID.value]

        nome_prod = self._combo_text(self.NOME_PRODUZIONE)
        produzione = self.productions_query_service.retrieve_production_map_by_name(nome_prod)
        if not produzione:
            QMessageBox.critical(self, "ERRORE", "Produzione non valida")
            return
        id_produzione = produzione[DBProductionsColumns.ID.value]

        date_widget: QDateEdit = self.invoice_widgets[DBInvoicesColumns.DATA_CREAZIONE.value]
        rate_value = self._combo_text(DBInvoicesColumns.NUMERO_RATE.value)
        is_rateizzata = str(rate_value) == Rateizzazione.TRE.value

        def _date_or_none(key):
            w: QDateEdit = self.invoice_widgets[key]
            return w.date().toString("yyyy-MM-dd")

        invoice_data = {
            DBInvoicesColumns.DATA_CREAZIONE.value: _date_or_none(DBInvoicesColumns.DATA_CREAZIONE.value),
            DBInvoicesColumns.ID_CLIENTE.value: id_cliente,
            DBInvoicesColumns.SERVIZI.value: self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].text().strip(),
            DBInvoicesColumns.RIMBORSI.value: self.invoice_widgets[DBInvoicesColumns.RIMBORSI.value].text().strip(),
            DBInvoicesColumns.RIVALSA_INPS.value: self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].text().strip(),
            DBInvoicesColumns.CASSA_INPS.value: self.invoice_widgets[DBInvoicesColumns.CASSA_INPS.value].text().strip(),
            DBInvoicesColumns.IMPONIBILE.value: self.invoice_widgets[DBInvoicesColumns.IMPONIBILE.value].text().strip(),
            DBInvoicesColumns.IVA.value: self.invoice_widgets[DBInvoicesColumns.IVA.value].text().strip(),
            DBInvoicesColumns.TOT_DOCUMENTO.value: self.invoice_widgets[DBInvoicesColumns.TOT_DOCUMENTO.value].text().strip(),
            DBInvoicesColumns.RITENUTA.value: self.invoice_widgets[DBInvoicesColumns.RITENUTA.value].text().strip(),
            DBInvoicesColumns.NETTO_A_PAGARE.value: self.invoice_widgets[DBInvoicesColumns.NETTO_A_PAGARE.value].text().strip(),
            DBInvoicesColumns.METODO_PAGAMENTO.value: self._combo_text(DBInvoicesColumns.METODO_PAGAMENTO.value),
            DBInvoicesColumns.ID_CONTO.value: id_conto,
            DBInvoicesColumns.NUMERO_RATE.value: rate_value,
            DBInvoicesColumns.DATA_SCADENZA_1.value: _date_or_none(DBInvoicesColumns.DATA_SCADENZA_1.value),
            DBInvoicesColumns.DATA_SCADENZA_2.value: _date_or_none(DBInvoicesColumns.DATA_SCADENZA_2.value) if is_rateizzata else None,
            DBInvoicesColumns.DATA_SCADENZA_3.value: _date_or_none(DBInvoicesColumns.DATA_SCADENZA_3.value) if is_rateizzata else None,
            DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value: id_produzione,
            DBInvoicesColumns.NOTE.value: self.invoice_widgets[DBInvoicesColumns.NOTE.value].text().strip(),
        }

        success, message = self.invoice_controller.update_invoice(self.current_invoice_id, invoice_data)
        if success:
            QMessageBox.information(self, "SALVATAGGIO COMPLETATO", message)
            self.modify_switch.setChecked(False)
            # Ricarica la fattura per riflettere lo stato persistito.
            self.load_invoice(self.current_invoice_id)
        else:
            QMessageBox.critical(self, "ERRORE", message)

    def _storna_invoice(self):
        confirm = QMessageBox.question(
            self,
            "Conferma storno",
            "Stai per stornare questa fattura.\n"
            "Non verrà più conteggiata nel sistema ma resterà visibile.\n"
            "Vuoi continuare?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        invoice_data = {DBInvoicesColumns.STATUS.value: InvoiceSatus.STORNATA.value}
        success, message = self.invoice_controller.storna_invoice(self.current_invoice_id, invoice_data)
        if success:
            QMessageBox.information(self, "FATTURA STORNATA", message)
            self.modify_switch.setChecked(False)
            self.load_invoice(self.current_invoice_id)
        else:
            QMessageBox.critical(self, "ERRORE", message)

    # ------------------------------------------------------------------
    # Sezioni pagamenti / spese di produzione
    # ------------------------------------------------------------------

    def _create_payments_section(self):
        invoice = self.invoices_query_service.retrieve_invoice_map_by_id(self.current_invoice_id)
        section = self._make_section_frame("PAGAMENTI ASSOCIATI")

        totali = self.invoices_analyzer_service.calcola_totale_pagamenti_fattura(self.current_invoice_id)

        cards = QHBoxLayout()
        cards.setSpacing(15)
        labels = [("TOTALE PAGAMENTI", totali[0])]
        if int(invoice[DBInvoicesColumns.NUMERO_RATE.value]) == int(Rateizzazione.TRE.value):
            labels += [
                ("TOTALE RATA 1", totali[1]),
                ("TOTALE RATA 2", totali[2]),
                ("TOTALE RATA 3", totali[3]),
            ]
        for title, value in labels:
            cards.addWidget(self._make_info_card(title, f"{self._fmt(value)} €"))
        cards.addStretch(1)
        section.layout().addLayout(cards)

        payments = self.invoices_query_service.retrieve_invoice_with_payments_map_list(self.current_invoice_id)
        for payment in payments:
            name = payment.get(DBPaymentsColumns.PAYMENT_NAME.value)
            if not name:
                continue
            btn = QPushButton(name)
            btn.setFlat(True)
            btn.setStyleSheet("text-align: left; padding: 6px;")
            section.layout().addWidget(btn)

        self.content_layout.addWidget(section)

    def _create_expenses_section(self):
        section = self._make_section_frame("SPESE DI PRODUZIONE ASSOCIATE")

        totale = self.invoices_analyzer_service.calcola_totale_spese_produzione_fattura(self.current_invoice_id)
        cards = QHBoxLayout()
        cards.setSpacing(15)
        cards.addWidget(self._make_info_card("TOTALE SPESE", f"{self._fmt(totale)} €"))
        cards.addStretch(1)
        section.layout().addLayout(cards)

        expenses = self.invoices_query_service.retrieve_invoice_with_expenses_map_list(self.current_invoice_id)
        for expense in expenses:
            name = expense.get(DBExpensesColumns.NAME.value)
            if not name:
                continue
            btn = QPushButton(name)
            btn.setFlat(True)
            btn.setStyleSheet("text-align: left; padding: 6px;")
            section.layout().addWidget(btn)

        self.content_layout.addWidget(section)

    def _make_section_frame(self, title):
        frame = QFrame()
        frame.setObjectName("InvoiceRelatedSectionFrame")
        frame.setStyleSheet(
            "#InvoiceRelatedSectionFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
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
        card.setObjectName("InvoiceInfoCard")
        card.setStyleSheet(
            "#InvoiceInfoCard { background-color: palette(alternate-base); border-radius: 6px; }"
            "#InvoiceInfoCard QLabel { color: palette(text); }"
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

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _cleanup_and_go_back(self):
        if self.on_back is not None:
            self.on_back()

    def _combo_text(self, key):
        widget = self.invoice_widgets.get(key)
        if isinstance(widget, QTFilterableComboBox):
            # value() restituisce stringa vuota se la selezione corrente
            # non e' una voce valida — evita di esfiltrare testo libero.
            return widget.value()
        if isinstance(widget, QComboBox):
            return widget.currentText().strip()
        if hasattr(widget, "text"):
            return widget.text().strip()
        return ""

    def _set_combo_text(self, combo: QComboBox, value):
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
            return ""
        try:
            return format(float(value), ".2f")
        except (TypeError, ValueError):
            return str(value)

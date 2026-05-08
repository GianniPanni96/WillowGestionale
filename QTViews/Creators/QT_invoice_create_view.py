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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from Gestionale_Enums import (
    PaymentsMethods,
    Rateizzazione,
    RegimeFiscale,
    TipologiaFattura,
)
from Model import (
    DBAccountsColumns,
    DBClientsColumns,
    DBInvoicesColumns,
    DBProductionsColumns,
    DBUsersColumns,
)
from QTViews.CustomWidgets.QT_filterable_combo_box import QTFilterableComboBox

if TYPE_CHECKING:
    from App_context import AppContext


class QTInvoiceCreateViewH(QDialog):
    """
    Versione QT del creator di una fattura.

    Equivalente di Views/Creators/Invoice_create_view.InvoiceCreateView,
    ma realizzato come QDialog modale. La logica di calcolo, di validazione
    e di interazione con i query/analyzer/controller services rimane invariata:
    si limita a tradurre i widget customtkinter nei loro corrispettivi Qt.
    """

    NOME_UTENTE = "NOME UTENTE"
    NOME_CLIENTE = "NOME CLIENTE"
    NOME_PRODUZIONE = "NOME PRODUZIONE"
    NOME_CONTO = "CONTO"

    def __init__(self, app_context: "AppContext", parent=None, on_invoice_created=None):
        super().__init__(parent)

        self.app_context = app_context
        self.invoice_controller = app_context.invoice_controller
        self.user_query_service = app_context.user_query_service
        self.clients_query_service = app_context.clients_query_service
        self.productions_query_service = app_context.productions_query_service
        self.invoices_query_service = app_context.invoices_query_service
        self.invoices_analyzer_service = app_context.invoices_analyzer_service
        self.account_query_service = app_context.account_query_service
        self.fiscal_settings = app_context.fiscal_settings
        self.on_invoice_created = on_invoice_created

        self.setWindowTitle("Aggiungi Nuova Fattura")
        self.resize(620, 760)
        self.setModal(True)

        self.invoice_widgets: dict = {}
        self.invoice_labels: dict = {}
        self.error_labels: dict = {}

        self.invoices_list_of_user = []
        self.productions_list_of_client = []
        self.selected_user = ""

        self._build_ui()
        self._initial_population()

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
        self._build_client_row()
        self._build_production_row()
        self._build_numero_fattura_row()
        self._build_data_creazione_row()
        self._build_simple_entry(DBInvoicesColumns.SERVIZI.value, "Importo Servizi (€)", with_error=True)
        self._build_simple_entry(DBInvoicesColumns.RIMBORSI.value, "Rimborsi (€)", with_error=True)
        self._build_simple_entry(DBInvoicesColumns.RIVALSA_INPS.value, "Rivalsa INPS (€)", with_error=True)
        self._build_combo_row(
            DBInvoicesColumns.METODO_PAGAMENTO.value,
            "Metodo Pagamento",
            [item.value for item in PaymentsMethods],
        )
        self._build_combo_row(
            DBInvoicesColumns.NUMERO_RATE.value,
            "Numero Rate",
            [item.value for item in Rateizzazione],
        )
        self._build_combo_row(
            DBInvoicesColumns.TIPO.value,
            "Tipo Documento",
            [item.value for item in TipologiaFattura],
            command=self._on_tipo_changed,
        )
        self.invoice_widgets[DBInvoicesColumns.TIPO.value].setCurrentText(TipologiaFattura.FATTURA.value)
        self._build_combo_row(
            DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value,
            "Fattura Associata",
            [],
            command=self._on_fattura_associata_changed,
        )
        self._build_combo_row(
            self.NOME_CONTO,
            "Conto",
            [a[DBAccountsColumns.NAME.value] for a in self.account_query_service.retrieve_accounts_map_list()],
        )
        self._build_note_row()

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.save_button = QPushButton("Salva Fattura")
        self.save_button.clicked.connect(self._save_invoice_data)
        bottom.addWidget(self.save_button)
        bottom.addStretch(1)
        outer.addLayout(bottom)

        # In creazione la fattura associata e' nascosta finche' non viene
        # selezionato il tipo "NOTA DI CREDITO".
        self._set_field_visible(DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value, False)

    def _build_user_row(self):
        users = self.user_query_service.retrieve_users_map_list()
        user_names = [
            f"{u[DBUsersColumns.FIRST_NAME.value]} {u[DBUsersColumns.LAST_NAME.value]}"
            for u in users
        ]
        combo = QComboBox()
        combo.addItems(user_names)
        combo.currentTextChanged.connect(self._update_entries_on_regime_fiscale)

        suggest_button = QPushButton("Suggerisci")
        suggest_button.setToolTip(
            "Suggerisce l'utente più adatto a fatturare un certo importo, "
            "scegliendo tra forfettarie e ordinaria in base alle spese deducibili."
        )
        suggest_button.clicked.connect(self._open_suggest_dialog)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(combo, stretch=1)
        row_layout.addWidget(suggest_button)

        label = QLabel(self.NOME_UTENTE)
        self.form_layout.addRow(label, row)
        self.invoice_widgets[self.NOME_UTENTE] = combo
        self.invoice_labels[self.NOME_UTENTE] = label

    def _build_client_row(self):
        clients = self.clients_query_service.retrieve_clients_map_list()
        combo = QTFilterableComboBox(
            values=[c[DBClientsColumns.NAME.value] for c in clients],
            placeholder="Cerca cliente…",
            autofill=True,
        )
        combo.currentTextChanged.connect(self._update_productions_list)

        label = QLabel(self.NOME_CLIENTE)
        self.form_layout.addRow(label, combo)
        self.invoice_widgets[self.NOME_CLIENTE] = combo
        self.invoice_labels[self.NOME_CLIENTE] = label

    def _build_production_row(self):
        combo = QComboBox()
        prods = self.productions_query_service.retrieve_productions_map_list(
            include_prod_with_unpaid_invoices=True
        )
        combo.addItems([p[DBProductionsColumns.NAME.value] for p in prods])
        combo.currentTextChanged.connect(self._prod_already_invoiced_control)

        label = QLabel(self.NOME_PRODUZIONE)
        self.form_layout.addRow(label, combo)
        self.invoice_widgets[self.NOME_PRODUZIONE] = combo
        self.invoice_labels[self.NOME_PRODUZIONE] = label

        error = QLabel("")
        error.setStyleSheet("color: #d62929;")
        self.form_layout.addRow("", error)
        self.error_labels[self.NOME_PRODUZIONE] = error

    def _build_numero_fattura_row(self):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        edit = QLineEdit()
        self.year_label = QLabel(str(datetime.today().date().year))
        row_layout.addWidget(edit, stretch=1)
        row_layout.addWidget(self.year_label)

        label = QLabel(DBInvoicesColumns.NUMERO_FATTURA.value)
        self.form_layout.addRow(label, row)
        self.invoice_widgets[DBInvoicesColumns.NUMERO_FATTURA.value] = edit
        self.invoice_labels[DBInvoicesColumns.NUMERO_FATTURA.value] = label

        error = QLabel("")
        error.setStyleSheet("color: #d62929;")
        self.form_layout.addRow("", error)
        self.error_labels[DBInvoicesColumns.NUMERO_FATTURA.value] = error

    def _build_data_creazione_row(self):
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("yyyy-MM-dd")
        date_edit.setDate(QDate.currentDate())
        date_edit.dateChanged.connect(self._on_date_changed)

        label = QLabel(DBInvoicesColumns.DATA_CREAZIONE.value)
        self.form_layout.addRow(label, date_edit)
        self.invoice_widgets[DBInvoicesColumns.DATA_CREAZIONE.value] = date_edit
        self.invoice_labels[DBInvoicesColumns.DATA_CREAZIONE.value] = label

    def _build_simple_entry(self, key, label_text, with_error=False):
        edit = QLineEdit()
        label = QLabel(label_text)
        self.form_layout.addRow(label, edit)
        self.invoice_widgets[key] = edit
        self.invoice_labels[key] = label

        if with_error:
            error = QLabel("")
            error.setStyleSheet("color: #d62929;")
            self.form_layout.addRow("", error)
            self.error_labels[key] = error

    def _build_combo_row(self, key, label_text, values, command=None):
        combo = QComboBox()
        combo.addItems(values)
        if command is not None:
            combo.currentTextChanged.connect(command)

        label = QLabel(label_text)
        self.form_layout.addRow(label, combo)
        self.invoice_widgets[key] = combo
        self.invoice_labels[key] = label

    def _build_note_row(self):
        text = QTextEdit()
        text.setFixedHeight(80)
        label = QLabel(DBInvoicesColumns.NOTE.value)
        self.form_layout.addRow(label, text)
        self.invoice_widgets[DBInvoicesColumns.NOTE.value] = text
        self.invoice_labels[DBInvoicesColumns.NOTE.value] = label

    # ------------------------------------------------------------------
    # Inizializzazione e dipendenze tra campi
    # ------------------------------------------------------------------

    def _initial_population(self):
        # Popolamento iniziale lista produzioni in funzione del cliente selezionato.
        client_combo: QComboBox = self.invoice_widgets[self.NOME_CLIENTE]
        if client_combo.count() > 0:
            self._update_productions_list(client_combo.currentText())

        user_combo: QComboBox = self.invoice_widgets[self.NOME_UTENTE]
        self.selected_user = user_combo.currentText()
        if self.selected_user:
            self._populate_invoice_list_by_selected_user(self.selected_user)
            regime = self._get_regime_fiscale_from_view(self.selected_user)
            if regime == RegimeFiscale.ORDINARIO.value:
                rivalsa_widget: QLineEdit = self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value]
                rivalsa_widget.setEnabled(False)
                rivalsa_widget.setText("0")
            self._auto_compile_invoice_name(self.selected_user)

        # Se non ci sono fatture per l'utente, blocca tipo + fattura associata.
        if not self.invoices_list_of_user:
            self.invoice_widgets[DBInvoicesColumns.TIPO.value].setEnabled(False)
            self.invoice_widgets[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].setEnabled(False)

        # Bind validazioni amount-only.
        self._bind_amount_validation(DBInvoicesColumns.SERVIZI.value)
        self._bind_amount_validation(DBInvoicesColumns.RIMBORSI.value)
        self._bind_amount_validation(DBInvoicesColumns.RIVALSA_INPS.value)
        self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].textChanged.connect(self._populate_rivalsa_inps)

    def _bind_amount_validation(self, key):
        widget: QLineEdit = self.invoice_widgets[key]
        error_label = self.error_labels.get(key)

        def _validate():
            value = widget.text().strip()
            if value == "":
                if error_label is not None:
                    error_label.setText("")
                return
            ok = re.fullmatch(r"^\d+(\.\d{1,2})?$", value) is not None
            if ok:
                if error_label is not None:
                    error_label.setText("")
            else:
                if error_label is not None:
                    error_label.setText(
                        "Inserimento non valido: numero monetario con max 2 decimali (es. 123.45)"
                    )

        widget.editingFinished.connect(_validate)

    # ------------------------------------------------------------------
    # Callbacks dinamiche dei campi
    # ------------------------------------------------------------------

    def _update_entries_on_regime_fiscale(self, selected_value):
        if not selected_value or selected_value == self.selected_user:
            return
        self.selected_user = selected_value
        self._populate_invoice_list_by_selected_user(selected_value)

        regime = self._get_regime_fiscale_from_view(selected_value)
        rivalsa_widget: QLineEdit = self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value]
        if regime == RegimeFiscale.ORDINARIO.value:
            rivalsa_widget.setText("0")
            rivalsa_widget.setEnabled(False)
        elif regime == RegimeFiscale.FORFETTARIO.value:
            rivalsa_widget.setEnabled(True)
            rivalsa_widget.clear()
            self._populate_rivalsa_inps()

        tipo_widget: QComboBox = self.invoice_widgets[DBInvoicesColumns.TIPO.value]
        fatt_ass_widget: QComboBox = self.invoice_widgets[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value]
        if not self.invoices_list_of_user:
            tipo_widget.setEnabled(False)
            tipo_widget.setCurrentText(TipologiaFattura.FATTURA.value)
            fatt_ass_widget.setEnabled(False)
            self._set_field_visible(DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value, False)
        else:
            tipo_widget.setEnabled(True)
            fatt_ass_widget.setEnabled(True)

        fatt_ass_widget.blockSignals(True)
        fatt_ass_widget.clear()
        fatt_ass_widget.addItems(
            [item[DBInvoicesColumns.NUMERO_FATTURA.value] for item in self.invoices_list_of_user]
        )
        fatt_ass_widget.blockSignals(False)

        self._auto_compile_invoice_name(selected_value)

    def _update_productions_list(self, selected_client_name):
        self._populate_production_list_by_selected_client(selected_client_name)
        prod_combo: QComboBox = self.invoice_widgets[self.NOME_PRODUZIONE]
        prod_combo.blockSignals(True)
        prod_combo.clear()
        prod_combo.addItems(
            [p[DBProductionsColumns.NAME.value] for p in self.productions_list_of_client]
        )
        prod_combo.blockSignals(False)

        if self.productions_list_of_client:
            prod_combo.setCurrentIndex(0)
            self._prod_already_invoiced_control(prod_combo.currentText())
        else:
            self.error_labels[self.NOME_PRODUZIONE].setText(
                "IL CLIENTE SELEZIONATO NON HA ANCORA NESSUNA PRODUZIONE ASSOCIATA"
            )

    def _populate_invoice_list_by_selected_user(self, user_full_name):
        self.invoices_list_of_user = []
        parts = user_full_name.split(" ")
        if len(parts) < 2:
            return
        user = self.user_query_service.retrieve_user_map_by_fullname(parts[0], parts[1])
        if not user:
            return
        user_id = user[DBUsersColumns.ID.value]
        self.invoices_list_of_user = self.invoices_query_service.retrieve_invoices_map_list_by_user(
            user_id, year=-1
        )

    def _populate_production_list_by_selected_client(self, client_name):
        self.productions_list_of_client = []
        if not client_name:
            return
        client = self.clients_query_service.retrieve_client_map_by_name(client_name)
        if not client:
            return
        client_id = client[DBClientsColumns.ID.value]
        self.productions_list_of_client = self.productions_query_service.retrieve_productions_map_list_by_client_id(
            client_id=client_id, include_prod_with_unpaid_invoices=True
        )

    def _get_regime_fiscale_from_view(self, user_full_name):
        parts = user_full_name.split(" ")
        if len(parts) < 2:
            return None
        return self.user_query_service.get_regime_fiscale_by_full_name(parts[0], parts[1])

    def _populate_rivalsa_inps(self):
        importo = self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].text().strip()
        if not importo:
            return
        try:
            servizi = float(importo)
        except ValueError:
            return
        regime = self._get_regime_fiscale_from_view(self.selected_user)
        if regime != RegimeFiscale.FORFETTARIO.value:
            return
        aliquota = float(self.fiscal_settings.partita_iva_forfettaria.aliquota_rivalsa_inps)
        rivalsa = servizi * aliquota
        self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].setText(format(rivalsa, ".2f"))

    def _on_tipo_changed(self, selected_value):
        is_ndc = selected_value == TipologiaFattura.NOTA_DI_CREDITO.value
        self._set_field_visible(DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value, is_ndc)
        if is_ndc:
            fatt_ass_widget: QComboBox = self.invoice_widgets[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value]
            if fatt_ass_widget.count() > 0:
                self._on_fattura_associata_changed(fatt_ass_widget.currentText())
        else:
            self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].clear()
            self.invoice_widgets[DBInvoicesColumns.RIMBORSI.value].clear()
            self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].clear()
            self._auto_compile_invoice_name(self.selected_user)

    def _on_fattura_associata_changed(self, selected_value):
        if not selected_value:
            return
        if self.invoice_widgets[DBInvoicesColumns.TIPO.value].currentText() != TipologiaFattura.NOTA_DI_CREDITO.value:
            return
        invoice = self.invoices_query_service.retrieve_invoice_map_by_name(selected_value)
        if not invoice:
            return
        nome_array = invoice[DBInvoicesColumns.NUMERO_FATTURA.value].split(" - ")
        if len(nome_array) >= 2:
            self.invoice_widgets[DBInvoicesColumns.NUMERO_FATTURA.value].setText(
                f"{nome_array[0]} - {nome_array[1]} - NDC"
            )
        self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].setText(
            f"{invoice[DBInvoicesColumns.SERVIZI.value]:.2f}"
        )
        self.invoice_widgets[DBInvoicesColumns.RIMBORSI.value].setText(
            f"{invoice[DBInvoicesColumns.RIMBORSI.value]:.2f}"
        )
        rivalsa = invoice.get(DBInvoicesColumns.RIVALSA_INPS.value)
        if rivalsa is not None:
            self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].setText(f"{rivalsa:.2f}")

        client = self.clients_query_service.retrieve_client_map_by_id(
            invoice[DBInvoicesColumns.ID_CLIENTE.value]
        )
        if client:
            self._set_combo_text(self.invoice_widgets[self.NOME_CLIENTE], client[DBClientsColumns.NAME.value])
        production = self.productions_query_service.retrieve_production_map_by_id(
            invoice[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value]
        )
        if production:
            self._set_combo_text(
                self.invoice_widgets[self.NOME_PRODUZIONE],
                production[DBProductionsColumns.NAME.value],
            )
        self._set_combo_text(
            self.invoice_widgets[DBInvoicesColumns.METODO_PAGAMENTO.value],
            invoice[DBInvoicesColumns.METODO_PAGAMENTO.value],
        )
        self._set_combo_text(
            self.invoice_widgets[DBInvoicesColumns.NUMERO_RATE.value],
            invoice[DBInvoicesColumns.NUMERO_RATE.value],
        )

    def _on_date_changed(self, qdate):
        self.year_label.setText(str(qdate.year()))
        self._auto_compile_invoice_name(self.selected_user)

    def _auto_compile_invoice_name(self, user_full_name):
        if not user_full_name:
            return
        parts = user_full_name.split(" ")
        if len(parts) < 2:
            return
        user = self.user_query_service.retrieve_user_map_by_fullname(parts[0], parts[1])
        if not user:
            return
        user_id = user[DBUsersColumns.ID.value]
        user_invoices = self.invoices_query_service.retrieve_invoices_map_list_by_user(user_id, year=-1)
        date_edit: QDateEdit = self.invoice_widgets[DBInvoicesColumns.DATA_CREAZIONE.value]
        selected_year = date_edit.date().year()

        numbers_per_year = {}
        for invoice in user_invoices:
            try:
                bits = invoice[DBInvoicesColumns.NUMERO_FATTURA.value].split(" - ")
                invoice_number = int(bits[1].split("FPR")[1])
                invoice_year = int(bits[2])
            except (KeyError, IndexError, ValueError):
                continue
            numbers_per_year.setdefault(invoice_year, []).append(invoice_number)

        same_year_numbers = numbers_per_year.get(selected_year, [])
        next_number = max(same_year_numbers) + 1 if same_year_numbers else 1
        next_number_str = str(next_number).zfill(2)

        numero_widget: QLineEdit = self.invoice_widgets[DBInvoicesColumns.NUMERO_FATTURA.value]
        if self.invoice_widgets[DBInvoicesColumns.TIPO.value].currentText() == TipologiaFattura.FATTURA.value:
            numero_widget.setText(f"{parts[1]} - FPR{next_number_str}")
        else:
            fatt_ass = self.invoice_widgets[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].currentText()
            bits = fatt_ass.split(" - ")
            if len(bits) >= 2:
                numero_widget.setText(f"{bits[0]} - {bits[1]} - NDC")

    def _prod_already_invoiced_control(self, selected_value):
        if not selected_value:
            self.error_labels[self.NOME_PRODUZIONE].setText("")
            return
        production = self.productions_query_service.retrieve_production_map_by_name(selected_value)
        if not production:
            self.error_labels[self.NOME_PRODUZIONE].setText("")
            return
        fatture = self.invoices_query_service.retrieve_invoice_map_list_by_production(
            production.get(DBProductionsColumns.ID.value)
        )
        if fatture:
            nomi = ", ".join(f[DBInvoicesColumns.NUMERO_FATTURA.value] for f in fatture)
            self.error_labels[self.NOME_PRODUZIONE].setText(
                f"Questa produzione ha gia una o piu fatture associate:\n({nomi})"
            )
            self.error_labels[self.NOME_PRODUZIONE].setStyleSheet("color: #e39e27;")
        else:
            self.error_labels[self.NOME_PRODUZIONE].setText("")

    # ------------------------------------------------------------------
    # Salvataggio
    # ------------------------------------------------------------------

    def _save_invoice_data(self):
        invoice_data = {}
        for key, widget in self.invoice_widgets.items():
            if isinstance(widget, QLineEdit):
                invoice_data[key] = widget.text().strip()
            elif isinstance(widget, QTFilterableComboBox):
                # value() restituisce stringa vuota se la selezione non e'
                # tra le voci valide, evitando di salvare testo libero.
                invoice_data[key] = widget.value()
            elif isinstance(widget, QComboBox):
                invoice_data[key] = widget.currentText().strip()
            elif isinstance(widget, QDateEdit):
                invoice_data[key] = widget.date().toString("yyyy-MM-dd")
            elif isinstance(widget, QTextEdit):
                invoice_data[key] = widget.toPlainText().strip()

        invoice_data[DBInvoicesColumns.NUMERO_FATTURA.value] += " - " + str(datetime.today().date().year)
        if invoice_data.get(DBInvoicesColumns.TIPO.value) == TipologiaFattura.FATTURA.value:
            invoice_data.pop(DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value, None)

        success, message = self.invoice_controller.save_invoice(invoice_data)
        if not success:
            QMessageBox.critical(self, "ERRORE", message)
            return

        invoice_map = self.invoices_query_service.retrieve_last_invoice_insert_map()
        invoice_id = invoice_map[DBInvoicesColumns.ID.value] if invoice_map else None
        if self.on_invoice_created is not None and invoice_id is not None:
            self.on_invoice_created(invoice_id)
        self.accept()

    # ------------------------------------------------------------------
    # Suggeritore di fatturatore
    # ------------------------------------------------------------------

    def _open_suggest_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Suggeritore di fatturatore")
        dialog.resize(560, 400)
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        info = QLabel(
            "Inserisci l'importo da fatturare. Il suggeritore cercherà di privilegiare "
            "l'utente ordinario fino al limite delle spese deducibili, e tra le "
            "forfettarie quella con minor fatturato."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addWidget(QLabel("IMPORTO DA FATTURARE"))
        amount_edit = QLineEdit()
        layout.addWidget(amount_edit)

        suggest_btn = QPushButton("SUGGERISCI")
        layout.addWidget(suggest_btn)

        ranking_label = QLabel("")
        ranking_label.setWordWrap(True)
        layout.addWidget(ranking_label, stretch=1)

        def _do_suggest():
            try:
                new_import = float(amount_edit.text().strip())
            except ValueError:
                QMessageBox.warning(dialog, "Errore", "Inserimento non valido")
                return
            try:
                users_rank = self.invoices_analyzer_service.select_best_invoicer(new_import)
            except ValueError as ve:
                QMessageBox.warning(dialog, "Errore", f"Predizione non possibile: {ve}")
                return
            if not users_rank:
                ranking_label.setText("Nessun suggerimento disponibile.")
                return
            lines = [f"{name} — {score}" for name, score in users_rank.items()]
            ranking_label.setText("\n".join(lines))
            best_user = next(iter(users_rank.keys()), None)
            if best_user is not None:
                self._set_combo_text(self.invoice_widgets[self.NOME_UTENTE], best_user)
                self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].setText(f"{new_import:.2f}")
                self._populate_rivalsa_inps()
                self._update_entries_on_regime_fiscale(best_user)
                dialog.accept()

        suggest_btn.clicked.connect(_do_suggest)
        dialog.exec()

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

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

    def _set_field_visible(self, key, visible):
        widget = self.invoice_widgets.get(key)
        label = self.invoice_labels.get(key)
        if widget is not None:
            widget.setVisible(visible)
        if label is not None:
            label.setVisible(visible)

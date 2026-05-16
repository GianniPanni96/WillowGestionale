from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
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

from Gestionale_Enums import TipologiaCliente
from Model import (
    DBClientsColumns,
    DBInvoicesColumns,
    DBProductionsColumns,
    DBRefundsColumns,
)
from QTViews.CustomWidgets.QT_catalog_filterable_combo_box import QTCatalogFilterableComboBox
from QTViews.CustomWidgets.QT_filterable_combo_box import QTFilterableComboBox
from Utils.View_utils import ViewUtils

if TYPE_CHECKING:
    from App_context import AppContext


class QTClientDetailViewH(QWidget):
    """
    Versione QT del dettaglio di un cliente.

    Equivalente di Views/Details/Client_detail_view.ClientDetailView,
    portato sui widget Qt mantenendo la stessa logica di dominio:
    - sezione informazioni in griglia 2x2 (Dati Anagrafici / Settore &
      Tipologia / Referente / Note);
    - switch "Abilita la modifica" che sblocca i campi editabili oltre
      ai bottoni Salva / Elimina;
    - sezioni storico Fatture / Rimborsi / Produzioni, ognuna con card
      aggregate e lista di pulsanti rapidi (l'apertura del dettaglio
      collegato passa per l'event_bus, come nella versione legacy).

    Strutturalmente segue il pattern di QTInvoiceDetailViewH: head bar
    persistente (back + titolo + switch), QScrollArea per il corpo,
    refresh totale via load_client() che ricicla content_layout.
    """

    SECTIONS = ["Dati Anagrafici", "Settore & Tipologia", "Referente", "Note"]

    FIELDS_BY_SECTION = {
        "Dati Anagrafici": [
            (DBClientsColumns.NAME.value, "Nome Cliente"),
            (DBClientsColumns.PARTITA_IVA.value, "Partita IVA"),
            (DBClientsColumns.EMAIL.value, "Email"),
            (DBClientsColumns.SEDE_LEGALE.value, "Sede Legale"),
        ],
        "Settore & Tipologia": [
            (DBClientsColumns.SETTORE.value, "Settore"),
            (DBClientsColumns.TIPOLOGIA.value, "Tipologia"),
        ],
        "Referente": [
            (DBClientsColumns.REFERENTE.value, "Referente"),
            (DBClientsColumns.CONTATTO_REFERENTE.value, "Contatto Referente"),
        ],
        "Note": [
            (DBClientsColumns.NOTE.value, "Note"),
        ],
    }

    def __init__(self, app_context: "AppContext", client_id, on_back, parent=None):
        super().__init__(parent)

        self.app_context = app_context
        self.client_controller = app_context.client_controller
        self.clients_query_service = app_context.clients_query_service
        self.clients_analyzer_service = app_context.clients_analyzer_service
        self.invoices_query_service = app_context.invoices_query_service
        self.productions_query_service = app_context.productions_query_service
        self.productions_analyzer_service = app_context.productions_analyzer_service
        self.refunds_query_service = app_context.refunds_query_service
        self.refunds_analyzer_service = app_context.refunds_analyzer_service
        self.event_bus = app_context.event_bus

        self.current_client_id = client_id
        self.on_back = on_back

        self.client_widgets: dict = {}
        self.client_labels: dict = {}
        self.section_grids: dict = {}
        self.section_rows: dict = {}

        self._build_ui()
        self.load_client(client_id)

    # ------------------------------------------------------------------
    # UI base
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        head = QFrame()
        head.setObjectName("ClientDetailHead")
        head.setStyleSheet(
            "#ClientDetailHead { background-color: palette(window); border-radius: 6px; }"
        )
        head_layout = QHBoxLayout(head)
        head_layout.setContentsMargins(10, 6, 10, 6)

        self.back_button = QPushButton("Elenco Clienti")
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

    def _build_info_section(self, client):
        self.info_frame = QFrame()
        self.info_frame.setObjectName("ClientInfoFrame")
        self.info_frame.setStyleSheet(
            "#ClientInfoFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
        )
        info_layout = QGridLayout(self.info_frame)
        info_layout.setContentsMargins(15, 15, 15, 15)
        info_layout.setHorizontalSpacing(20)
        info_layout.setVerticalSpacing(10)

        # Griglia 2x2 con una sezione per cella, come nella legacy.
        for i, name in enumerate(self.SECTIONS):
            section_frame = QFrame()
            section_frame.setObjectName("ClientInfoSectionFrame")
            section_frame.setStyleSheet(
                "#ClientInfoSectionFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
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

        for section_name, fields in self.FIELDS_BY_SECTION.items():
            for key, label_text in fields:
                widget = self._build_field_widget(key, client.get(key, ""))
                self._add_field(section_name, key, label_text, widget)

        # Riga bottoni: Salva a sinistra, Elimina a destra (rosso scuro
        # come la versione legacy).
        buttons_frame = QFrame()
        buttons_layout = QHBoxLayout(buttons_frame)
        buttons_layout.setContentsMargins(15, 15, 15, 15)

        self.save_btn = QPushButton("Salva Cliente")
        self.save_btn.clicked.connect(self._save_client_mod)
        buttons_layout.addWidget(self.save_btn)

        buttons_layout.addStretch(1)

        self.delete_btn = QPushButton("Elimina Cliente")
        self.delete_btn.setStyleSheet(
            "QPushButton { background-color: #8B0000; color: palette(highlighted-text); }"
            "QPushButton:hover { background-color: #A52A2A; }"
            "QPushButton:disabled { background-color: #4a2727; color: palette(mid); }"
        )
        self.delete_btn.clicked.connect(self._delete_client)
        buttons_layout.addWidget(self.delete_btn)

        info_layout.addWidget(buttons_frame, 2, 0, 1, 2)

        self.content_layout.addWidget(self.info_frame)

    def _build_field_widget(self, key, value):
        if key == DBClientsColumns.SETTORE.value:
            combo = QTCatalogFilterableComboBox.bound_to_section(
                app_context=self.app_context,
                section_name="clients_business_sectors",
                parent=self,
            )
            # Risolve la descrizione del settore dalla chiave salvata sul
            # cliente, esattamente come fa la legacy.
            descr = next(
                (
                    desc
                    for k, desc in self.app_context.catalogo_elenchi["clients_business_sectors"]
                    if k == str(value)
                ),
                str(value) if value is not None else "",
            )
            combo.set_value(descr)
            return combo

        if key == DBClientsColumns.TIPOLOGIA.value:
            combo = QComboBox()
            combo.addItems([item.value for item in TipologiaCliente])
            text = str(value) if value not in (None, "") else TipologiaCliente.PRIVATO.value
            idx = combo.findText(text)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            return combo

        if key == DBClientsColumns.NOTE.value:
            text = QTextEdit()
            text.setFixedHeight(80)
            text.setPlainText(str(value) if value is not None else "")
            return text

        edit = QLineEdit()
        edit.setText(str(value) if value is not None else "")
        return edit

    def _add_field(self, section_name, key, label_text, widget):
        grid = self.section_grids[section_name]
        row = self.section_rows[section_name]
        label = QLabel(label_text + ":")
        grid.addWidget(label, row, 0, alignment=Qt.AlignLeft)
        grid.addWidget(widget, row, 1)
        self.client_widgets[key] = widget
        self.client_labels[key] = label
        self.section_rows[section_name] = row + 1

    # ------------------------------------------------------------------
    # Caricamento dati di un cliente specifico
    # ------------------------------------------------------------------

    def load_client(self, client_id):
        self.current_client_id = client_id
        self._clear_content()

        client = self.clients_query_service.retrieve_client_map_by_id(client_id)
        if not client:
            self.title_label.setText("Cliente non trovato")
            return

        self.title_label.setText(str(client.get(DBClientsColumns.NAME.value, "")))

        self._build_info_section(client)
        self._toggle_edit(self.modify_switch.isChecked())

        self._build_history_section()

    def _clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.client_widgets.clear()
        self.client_labels.clear()
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

        for widget in self.client_widgets.values():
            widget.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Salvataggio / eliminazione
    # ------------------------------------------------------------------

    def _save_client_mod(self):
        client_data = self._collect_client_data()
        success, message = self.client_controller.update_client(self.current_client_id, client_data)
        if success:
            QMessageBox.information(self, "SALVATAGGIO COMPLETATO", message)
            self.modify_switch.setChecked(False)
            self.load_client(self.current_client_id)
        else:
            QMessageBox.critical(self, "ERRORE", message)

    def _collect_client_data(self):
        client_data = {}
        for key, widget in self.client_widgets.items():
            if isinstance(widget, QTFilterableComboBox):
                client_data[key] = widget.value()
            elif isinstance(widget, QLineEdit):
                client_data[key] = widget.text().strip()
            elif isinstance(widget, QComboBox):
                client_data[key] = widget.currentText().strip()
            elif isinstance(widget, QTextEdit):
                client_data[key] = widget.toPlainText().strip()
        return client_data

    def _delete_client(self):
        confirm = QMessageBox.question(
            self,
            "ELIMINAZIONE CLIENTE",
            "Stai per eliminare questo cliente.\nDesideri continuare?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        invoices = self.invoices_query_service.retrieve_invoice_map_list_by_client(self.current_client_id)
        productions = self.productions_query_service.retrieve_productions_map_list_by_client_id(
            self.current_client_id
        )
        refunds = self.refunds_query_service.retrieve_refunds_map_list_by_client_id(self.current_client_id)

        if invoices or productions or refunds:
            QMessageBox.critical(
                self,
                "ERRORE",
                "Impossibile eliminare il cliente.\n\n"
                "Esiste un item collegato a questo cliente.\n"
                "Eliminare ogni riferimento a questo cliente per poterlo "
                "eliminare dal database.",
            )
            return

        success, message = self.client_controller.delete_client(self.current_client_id)
        if success:
            QMessageBox.information(self, "CONFERMA ELIMINAZIONE", message)
            self._cleanup_and_go_back()
        else:
            QMessageBox.critical(self, "ERRORE", message)

    # ------------------------------------------------------------------
    # Sezioni storico fatture / rimborsi / produzioni
    # ------------------------------------------------------------------

    def _build_history_section(self):
        wrapper = QFrame()
        wrapper.setObjectName("ClientHistoryWrapper")
        wrapper.setStyleSheet(
            "#ClientHistoryWrapper { border: 2px solid palette(highlight); border-radius: 6px; }"
        )
        wrapper_layout = QHBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(15, 15, 15, 15)
        wrapper_layout.setSpacing(20)

        wrapper_layout.addWidget(self._create_invoices_history(), stretch=1)
        wrapper_layout.addWidget(self._create_refunds_history(), stretch=1)
        wrapper_layout.addWidget(self._create_productions_history(), stretch=1)

        self.content_layout.addWidget(wrapper)

    def _create_invoices_history(self):
        section = self._make_section_frame("FATTURE")
        year = datetime.now().year

        cards = QHBoxLayout()
        cards.addWidget(self._make_info_card(
            "TOTALE FATTURATO (All Time)",
            f"{self._fmt(self.clients_analyzer_service.calcola_tot_entrate_cliente(self.current_client_id, include_unpaid_invoices=True, year=-1))} €",
        ))
        cards.addWidget(self._make_info_card(
            f"TOTALE FATTURATO {year}",
            f"{self._fmt(self.clients_analyzer_service.calcola_tot_entrate_cliente(self.current_client_id, include_unpaid_invoices=False))} €",
        ))
        cards.addStretch(1)
        section.layout().addLayout(cards)

        section.layout().addWidget(self._make_subtitle(f"- Elenco Fatture {year} -"))

        invoices_list = QFrame()
        list_layout = QVBoxLayout(invoices_list)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(6)

        invoices = self.clients_query_service.retrieve_client_with_invoices_map_list(
            self.current_client_id, include_unpaid_invoices=False
        )
        for invoice in invoices:
            nome_fattura = invoice.get(DBInvoicesColumns.NUMERO_FATTURA.value)
            if not nome_fattura:
                continue
            invoice_id = invoice[DBInvoicesColumns.ID.value]
            prod = self.productions_query_service.retrieve_production_map_by_id(
                invoice[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value]
            )
            nome_prod = (
                prod[DBProductionsColumns.NAME.value] if prod else "Produzione non trovata"
            )
            btn = QPushButton(f"{nome_fattura} - {nome_prod}")
            btn.setStyleSheet("text-align: left; padding: 6px;")
            btn.clicked.connect(lambda _checked=False, iid=invoice_id: self._show_invoice_detail(iid))
            list_layout.addWidget(btn)

        list_layout.addStretch(1)
        section.layout().addWidget(invoices_list, stretch=1)
        return section

    def _create_refunds_history(self):
        section = self._make_section_frame("RIMBORSI")
        year = datetime.now().year

        cards = QHBoxLayout()
        cards.addWidget(self._make_info_card(
            "TOT RIMBORSI (All Time)",
            f"{self._fmt(self.refunds_analyzer_service.calculate_tot_refunds_of_client(self.current_client_id, year=-1))} €",
        ))
        cards.addWidget(self._make_info_card(
            f"TOT RIMBORSI {year}",
            f"{self._fmt(self.refunds_analyzer_service.calculate_tot_refunds_of_client(self.current_client_id))} €",
        ))
        cards.addStretch(1)
        section.layout().addLayout(cards)

        section.layout().addWidget(self._make_subtitle(f"- Elenco Rimborsi {year} -"))

        refunds_list = QFrame()
        list_layout = QVBoxLayout(refunds_list)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(6)

        refunds = self.refunds_query_service.retrieve_refunds_map_list_by_client_id(self.current_client_id)
        for refund in refunds:
            nome_refund = refund.get(DBRefundsColumns.REFUND_NAME.value)
            if not nome_refund:
                continue
            refund_id = refund[DBRefundsColumns.ID.value]
            btn = QPushButton(str(nome_refund))
            btn.setStyleSheet("text-align: left; padding: 6px;")
            btn.clicked.connect(lambda _checked=False, rid=refund_id: self._show_refund_detail(rid))
            list_layout.addWidget(btn)

        list_layout.addStretch(1)
        section.layout().addWidget(refunds_list, stretch=1)
        return section

    def _create_productions_history(self):
        section = self._make_section_frame("PRODUZIONI")
        year = datetime.now().year

        cards = QHBoxLayout()
        cards.addWidget(self._make_info_card(
            "# PRODUZIONI (All time)",
            str(self.productions_analyzer_service.count_productions_of_client(self.current_client_id, year=-1)),
        ))
        cards.addWidget(self._make_info_card(
            f"# PRODUZIONI {year}",
            str(self.productions_analyzer_service.count_productions_of_client(
                self.current_client_id, include_prod_with_unpaid_invoices=False
            )),
        ))
        cards.addStretch(1)
        section.layout().addLayout(cards)

        section.layout().addWidget(self._make_subtitle(f"- Elenco Produzioni {year} -"))

        prods_list = QFrame()
        list_layout = QVBoxLayout(prods_list)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(6)

        productions = self.productions_query_service.retrieve_productions_map_list_by_client_id(
            self.current_client_id, include_prod_with_unpaid_invoices=False
        )
        for production in productions:
            nome_produzione = production.get(DBProductionsColumns.NAME.value)
            if not nome_produzione:
                continue
            production_id = production[DBProductionsColumns.ID.value]
            btn = QPushButton(str(nome_produzione))
            btn.setStyleSheet("text-align: left; padding: 6px;")
            btn.clicked.connect(lambda _checked=False, pid=production_id: self._show_production_detail(pid))
            list_layout.addWidget(btn)

        list_layout.addStretch(1)
        section.layout().addWidget(prods_list, stretch=1)
        return section

    def _show_invoice_detail(self, invoice_id):
        self.event_bus.publish(ViewUtils.EventBusKeys.SHOW_INVOICE_DETAIL.value, invoice_id)

    def _show_refund_detail(self, refund_id):
        self.event_bus.publish(ViewUtils.EventBusKeys.SHOW_REFUND_DETAIL.value, refund_id)

    def _show_production_detail(self, production_id):
        self.event_bus.publish(ViewUtils.EventBusKeys.SHOW_PRODUCTION_DETAIL.value, production_id)

    # ------------------------------------------------------------------
    # Helper grafici condivisi con la detail fatture
    # ------------------------------------------------------------------

    def _make_section_frame(self, title):
        frame = QFrame()
        frame.setObjectName("ClientRelatedSectionFrame")
        frame.setStyleSheet(
            "#ClientRelatedSectionFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
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
        card.setObjectName("ClientInfoCard")
        card.setStyleSheet(
            "#ClientInfoCard { background-color: palette(alternate-base); border-radius: 6px; }"
            "#ClientInfoCard QLabel { color: palette(text); }"
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

    @staticmethod
    def _fmt(value):
        if value is None or value == "":
            return "0.00"
        try:
            return format(float(value), ".2f")
        except (TypeError, ValueError):
            return str(value)

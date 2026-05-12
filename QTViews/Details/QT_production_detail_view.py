from datetime import datetime
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

from Gestionale_Enums import ProductionStatus
from Model import (
    DBClientsColumns,
    DBInvoicesColumns,
    DBProductionsColumns,
)
from QTViews.CustomWidgets.QT_catalog_filterable_combo_box import QTCatalogFilterableComboBox
from QTViews.CustomWidgets.QT_filterable_combo_box import QTFilterableComboBox
from QTViews.CustomWidgets.QT_warning_banner import WarningBanner
from WarningServices.Warning_types import WarningInfo, WarningSeverity
from Views.View_utils import ViewUtils

if TYPE_CHECKING:
    from App_context import AppContext


class QTProductionDetailViewH(QWidget):
    """
    Versione QT del dettaglio di una produzione.

    Equivalente di Views/Details/Production_detail_view.ProductionDetailView,
    portato sui widget Qt mantenendo la stessa logica di dominio:
    - sezione informazioni in griglia 2x2 (Dati Generali / Dati
      Produzione / Note), con il cliente come QTFilterableComboBox e le
      tipologie come QTCatalogFilterableComboBox sui cataloghi
      production_types / production_output_types;
    - switch "Abilita la modifica" che sblocca i campi editabili oltre
      ai bottoni Salva / Elimina;
    - prima del salvataggio/eliminazione si conferma con l'utente se la
      produzione ha fatture associate (potenziale incongruenza), come
      nella legacy;
    - sezione storico Fatture Associate con card aggregate (totale
      servizi+rimborsi e totale preventivo) e lista di pulsanti rapidi;
      l'apertura del dettaglio fattura passa per l'event_bus.

    Strutturalmente segue il pattern di QTClientDetailViewH /
    QTSupplierDetailViewH: head bar persistente (back + titolo +
    switch), QScrollArea per il corpo, refresh totale via
    load_production().
    """

    CLIENT_FIELD = "CLIENTE"

    SECTIONS = ["Dati Generali", "Dati Produzione", "Note"]

    def __init__(self, app_context: "AppContext", production_id, on_back, parent=None):
        super().__init__(parent)

        self.app_context = app_context
        self.production_controller = app_context.production_controller
        self.productions_query_service = app_context.productions_query_service
        self.productions_analyzer_service = app_context.productions_analyzer_service
        self.clients_query_service = app_context.clients_query_service
        self.invoices_query_service = app_context.invoices_query_service
        self.event_bus = app_context.event_bus

        self.current_production_id = production_id
        self.on_back = on_back

        self.production_widgets: dict = {}
        self.production_labels: dict = {}
        self.section_grids: dict = {}
        self.section_rows: dict = {}

        self._build_ui()
        self.load_production(production_id)

    # ------------------------------------------------------------------
    # UI base
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        head = QFrame()
        head.setObjectName("ProductionDetailHead")
        head.setStyleSheet(
            "#ProductionDetailHead { background-color: palette(window); border-radius: 6px; }"
        )
        head_layout = QHBoxLayout(head)
        head_layout.setContentsMargins(10, 6, 10, 6)

        self.back_button = QPushButton("Elenco Produzioni")
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

    def _build_info_section(self, production):
        # Warning banner: visibile solo per i sev 1 (FK rotte).
        self.warning_banner = WarningBanner()
        self.content_layout.addWidget(self.warning_banner)
        self._current_warning_info = self._compute_current_warning(production)
        if self._is_consistency_warning(self._current_warning_info):
            self.warning_banner.set_warning(self._current_warning_info)
        else:
            self.warning_banner.hide_warning()

        self.info_frame = QFrame()
        self.info_frame.setObjectName("ProductionInfoFrame")
        self.info_frame.setStyleSheet(
            "#ProductionInfoFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
        )
        info_layout = QGridLayout(self.info_frame)
        info_layout.setContentsMargins(15, 15, 15, 15)
        info_layout.setHorizontalSpacing(20)
        info_layout.setVerticalSpacing(10)

        # Griglia 2 colonne: Dati Generali (sx) e Dati Produzione (dx),
        # Note in basso a tutta larghezza — coerente con la legacy.
        for i, name in enumerate(self.SECTIONS):
            section_frame = QFrame()
            section_frame.setObjectName("ProductionInfoSectionFrame")
            section_frame.setStyleSheet(
                "#ProductionInfoSectionFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
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
            if name == "Note":
                # Note occupa entrambe le colonne sulla riga finale.
                info_layout.addWidget(section_frame, row, 0, 1, 2)
            else:
                info_layout.addWidget(section_frame, row, col)
                info_layout.setColumnStretch(col, 1)
            self.section_grids[name] = section_layout
            self.section_rows[name] = 1

        # --- Dati Generali ---
        # Nome produzione (editabile).
        self._add_field("Dati Generali", DBProductionsColumns.NAME.value, "Nome Produzione",
                        self._make_line_edit(production.get(DBProductionsColumns.NAME.value, "")))

        # Cliente: QTFilterableComboBox popolato con tutti i clienti.
        clients = self.clients_query_service.retrieve_clients_map_list()
        client_combo = QTFilterableComboBox(
            values=[c[DBClientsColumns.NAME.value] for c in clients],
            placeholder="Cerca cliente…",
        )
        client_id = production.get(DBProductionsColumns.CLIENT_ID.value)
        client = self.clients_query_service.retrieve_client_map_by_id(client_id) if client_id else None
        client_name = client[DBClientsColumns.NAME.value] if client else ""
        client_combo.set_value(client_name)
        self._add_field("Dati Generali", self.CLIENT_FIELD, "Cliente", client_combo)

        # Stato.
        stato_combo = QComboBox()
        stato_combo.addItems([s.value for s in ProductionStatus])
        self._set_combo_text(stato_combo, production.get(DBProductionsColumns.STATO.value))
        self._add_field("Dati Generali", DBProductionsColumns.STATO.value, "Stato", stato_combo)

        # Data conclusione.
        self._add_field(
            "Dati Generali",
            DBProductionsColumns.END_DATE.value,
            "Data Conclusione",
            self._make_date_edit(production.get(DBProductionsColumns.END_DATE.value)),
        )

        # --- Dati Produzione ---
        # Tipologie via catalog combo bound_to_section.
        tipo_prod_combo = QTCatalogFilterableComboBox.bound_to_section(
            app_context=self.app_context,
            section_name="production_types",
            parent=self,
        )
        tipo_prod_combo.set_value(production.get(DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value, "") or "")
        self._add_field("Dati Produzione", DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value,
                        "Tipologia Produzione", tipo_prod_combo)

        tipo_out_combo = QTCatalogFilterableComboBox.bound_to_section(
            app_context=self.app_context,
            section_name="production_output_types",
            parent=self,
        )
        tipo_out_combo.set_value(production.get(DBProductionsColumns.TIPOLOGIA_OUTPUT.value, "") or "")
        self._add_field("Dati Produzione", DBProductionsColumns.TIPOLOGIA_OUTPUT.value,
                        "Tipologia Output", tipo_out_combo)

        self._add_field("Dati Produzione", DBProductionsColumns.HOURS.value, "Ore di produzione",
                        self._make_line_edit(production.get(DBProductionsColumns.HOURS.value, "")))
        self._add_field("Dati Produzione", DBProductionsColumns.TOTALE_PREVENTIVO.value,
                        "Totale Preventivo (€)",
                        self._make_line_edit(production.get(DBProductionsColumns.TOTALE_PREVENTIVO.value, "")))

        # --- Note: campi statici (timestamps) ---
        created_lbl = QLabel(str(production.get(DBProductionsColumns.CREATED_AT.value, "") or ""))
        self._add_field("Note", DBProductionsColumns.CREATED_AT.value, "Data Creazione", created_lbl)

        updated_lbl = QLabel(str(production.get(DBProductionsColumns.UPDATED_AT.value, "") or ""))
        self._add_field("Note", DBProductionsColumns.UPDATED_AT.value, "Ultimo Aggiornamento", updated_lbl)

        # Riga bottoni Salva / Elimina.
        buttons_frame = QFrame()
        buttons_layout = QHBoxLayout(buttons_frame)
        buttons_layout.setContentsMargins(15, 15, 15, 15)

        self.save_btn = QPushButton("Salva Produzione")
        self.save_btn.clicked.connect(self._save_production_mod)
        buttons_layout.addWidget(self.save_btn)

        buttons_layout.addStretch(1)

        self.delete_btn = QPushButton("Elimina Produzione")
        self.delete_btn.setStyleSheet(
            "QPushButton { background-color: #8B0000; color: palette(highlighted-text); }"
            "QPushButton:hover { background-color: #A52A2A; }"
            "QPushButton:disabled { background-color: #4a2727; color: palette(mid); }"
        )
        self.delete_btn.clicked.connect(self._delete_production)
        buttons_layout.addWidget(self.delete_btn)

        # I bottoni vanno alla terza riga, sotto entrambe le colonne.
        info_layout.addWidget(buttons_frame, 2, 0, 1, 2)

        self.content_layout.addWidget(self.info_frame)

    def _add_field(self, section_name, key, label_text, widget):
        grid = self.section_grids[section_name]
        row = self.section_rows[section_name]
        label = QLabel(label_text + ":")
        grid.addWidget(label, row, 0, alignment=Qt.AlignLeft)
        grid.addWidget(widget, row, 1)
        self.production_widgets[key] = widget
        self.production_labels[key] = label
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
    # Caricamento dati di una produzione specifica
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Warning di consistenza (sev 1)
    # ------------------------------------------------------------------

    def _compute_current_warning(self, production):
        try:
            service = self.app_context.production_warning_service
            warnings = service.collect_warnings_for_list([production]) or {}
            return warnings.get(production.get(DBProductionsColumns.NAME.value))
        except Exception:
            return None

    @staticmethod
    def _is_consistency_warning(info) -> bool:
        return isinstance(info, WarningInfo) and info.severity == WarningSeverity.CONSISTENCY

    _BROKEN_FIELD_WIDGET_MAP_PRODUCTION = {
        DBProductionsColumns.CLIENT_ID.value: "CLIENTE",  # cfr CLIENT_FIELD
    }

    def _apply_broken_field_highlight(self):
        info = getattr(self, "_current_warning_info", None)
        if not self._is_consistency_warning(info) or not info.broken_field_key:
            return
        widget_key = self._BROKEN_FIELD_WIDGET_MAP_PRODUCTION.get(
            info.broken_field_key, info.broken_field_key
        )
        widget = getattr(self, "production_widgets", {}).get(widget_key)
        if widget is None:
            return
        widget.setStyleSheet(
            widget.styleSheet() + " border: 2px solid #d62929; border-radius: 4px;"
        )

    # ------------------------------------------------------------------
    # Caricamento
    # ------------------------------------------------------------------

    def load_production(self, production_id):
        self.current_production_id = production_id
        self._clear_content()

        production = self.productions_query_service.retrieve_production_map_by_id(production_id)
        if not production:
            self.title_label.setText("Produzione non trovata")
            return

        self.title_label.setText(str(production.get(DBProductionsColumns.NAME.value, "")))

        self._build_info_section(production)
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
        self.production_widgets.clear()
        self.production_labels.clear()
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

        # I campi anagrafici timestamp restano sempre read-only: sono
        # rendered come QLabel quindi setEnabled non li tocca, ma li
        # escludiamo esplicitamente per chiarezza.
        readonly_keys = {
            DBProductionsColumns.CREATED_AT.value,
            DBProductionsColumns.UPDATED_AT.value,
        }
        for key, widget in self.production_widgets.items():
            if key in readonly_keys:
                continue
            widget.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Salvataggio / eliminazione
    # ------------------------------------------------------------------

    def _save_production_mod(self):
        # Avvisa l'utente se la produzione ha fatture associate, come
        # fa la legacy: la modifica potrebbe rendere incoerenti le
        # fatture gia' generate.
        invoices = self.invoices_query_service.retrieve_invoice_map_list_by_production(
            self.current_production_id
        )
        if invoices:
            confirm = QMessageBox.question(
                self,
                "MODIFICA PRODUZIONE",
                "Questa produzione presenta una o più fatture associate.\n"
                "La sua modifica può comportare delle incongruenze tra i dati "
                "delle fatture ad essa associate.\nDesideri continuare?\n"
                "In caso affermativo ricordati di controllare i dati delle "
                "fatture associate.",
                QMessageBox.Yes | QMessageBox.No,
            )
            if confirm != QMessageBox.Yes:
                return

        nome_cliente = self._combo_text(self.CLIENT_FIELD)
        cliente = self.clients_query_service.retrieve_client_map_by_name(nome_cliente)
        if not cliente:
            QMessageBox.critical(self, "ERRORE", "Cliente non valido")
            return
        id_cliente = cliente[DBClientsColumns.ID.value]

        date_widget: QDateEdit = self.production_widgets[DBProductionsColumns.END_DATE.value]

        production_data = {
            DBProductionsColumns.NAME.value: self.production_widgets[DBProductionsColumns.NAME.value].text().strip(),
            DBProductionsColumns.CLIENT_ID.value: id_cliente,
            DBProductionsColumns.STATO.value: self._combo_text(DBProductionsColumns.STATO.value),
            DBProductionsColumns.END_DATE.value: date_widget.date().toString("yyyy-MM-dd"),
            DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value: self._combo_text(DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value),
            DBProductionsColumns.TIPOLOGIA_OUTPUT.value: self._combo_text(DBProductionsColumns.TIPOLOGIA_OUTPUT.value),
            DBProductionsColumns.HOURS.value: self.production_widgets[DBProductionsColumns.HOURS.value].text().strip(),
            DBProductionsColumns.TOTALE_PREVENTIVO.value: self.production_widgets[DBProductionsColumns.TOTALE_PREVENTIVO.value].text().strip(),
        }

        success, message = self.production_controller.update_production(
            self.current_production_id, production_data
        )
        if success:
            QMessageBox.information(self, "SALVATAGGIO COMPLETATO", message)
            self.modify_switch.setChecked(False)
            self.load_production(self.current_production_id)
        else:
            QMessageBox.critical(self, "ERRORE", message)

    def _delete_production(self):
        invoices = self.invoices_query_service.retrieve_invoice_map_list_by_production(
            self.current_production_id
        )
        if invoices:
            message = (
                "Sei sicuro di voler eliminare questa produzione?\n"
                "Essa presenta delle fatture associate. Controlla eventualmente "
                "la consistenza dei dati di tali fatture a seguito "
                "dell'eliminazione."
            )
        else:
            message = "Sei sicuro di voler eliminare questa produzione?"

        confirm = QMessageBox.question(
            self,
            "ELIMINAZIONE PRODUZIONE",
            message,
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        success = self.production_controller.delete_production(self.current_production_id)
        if success:
            QMessageBox.information(self, "ELIMINAZIONE COMPLETATA",
                                    "Produzione eliminata con successo.")
            self._cleanup_and_go_back()
        else:
            QMessageBox.critical(self, "ERRORE", "Errore nell'eliminazione della produzione.")

    # ------------------------------------------------------------------
    # Sezione storico fatture associate
    # ------------------------------------------------------------------

    def _build_history_section(self):
        wrapper = QFrame()
        wrapper.setObjectName("ProductionHistoryWrapper")
        wrapper.setStyleSheet(
            "#ProductionHistoryWrapper { border: 2px solid palette(highlight); border-radius: 6px; }"
        )
        wrapper_layout = QHBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(15, 15, 15, 15)
        wrapper_layout.setSpacing(20)

        wrapper_layout.addWidget(self._create_invoices_history(), stretch=1)

        self.content_layout.addWidget(wrapper)

    def _create_invoices_history(self):
        section = self._make_section_frame("FATTURE ASSOCIATE")

        production = self.productions_query_service.retrieve_production_map_by_id(self.current_production_id)
        totale_preventivo = production.get(DBProductionsColumns.TOTALE_PREVENTIVO.value) if production else 0

        cards = QHBoxLayout()
        cards.addWidget(self._make_info_card(
            "TOTALE SERVIZI + RIMBORSI\nFATTURE",
            f"{self._fmt(self.productions_analyzer_service.calcola_totale_servizi_rimborsi_per_produzione(self.current_production_id))} €",
        ))
        cards.addWidget(self._make_info_card(
            "TOTALE PREVENTIVO",
            f"{self._fmt(totale_preventivo)} €",
        ))
        cards.addStretch(1)
        section.layout().addLayout(cards)

        section.layout().addWidget(self._make_subtitle(f"- Elenco Fatture {datetime.now().year} -"))

        invoices_list = QFrame()
        list_layout = QVBoxLayout(invoices_list)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(6)

        invoices = self.productions_query_service.retrieve_production_with_invoices_map_list(
            self.current_production_id
        )
        for invoice in invoices:
            nome_fattura = invoice.get(DBInvoicesColumns.NUMERO_FATTURA.value)
            if not nome_fattura:
                continue
            invoice_id = invoice[DBInvoicesColumns.ID.value]
            btn = QPushButton(str(nome_fattura))
            btn.setStyleSheet("text-align: left; padding: 6px;")
            btn.clicked.connect(lambda _checked=False, iid=invoice_id: self._show_invoice_detail(iid))
            list_layout.addWidget(btn)

        list_layout.addStretch(1)
        section.layout().addWidget(invoices_list, stretch=1)
        return section

    def _show_invoice_detail(self, invoice_id):
        self.event_bus.publish(ViewUtils.EventBusKeys.SHOW_INVOICE_DETAIL.value, invoice_id)

    # ------------------------------------------------------------------
    # Helper grafici condivisi con le altre detail Qt
    # ------------------------------------------------------------------

    def _make_section_frame(self, title):
        frame = QFrame()
        frame.setObjectName("ProductionRelatedSectionFrame")
        frame.setStyleSheet(
            "#ProductionRelatedSectionFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
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
        card.setObjectName("ProductionInfoCard")
        card.setStyleSheet(
            "#ProductionInfoCard { background-color: palette(alternate-base); border-radius: 6px; }"
            "#ProductionInfoCard QLabel { color: palette(text); }"
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
        widget = self.production_widgets.get(key)
        if isinstance(widget, QTFilterableComboBox):
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
            return "0.00"
        try:
            return format(float(value), ".2f")
        except (TypeError, ValueError):
            return str(value)

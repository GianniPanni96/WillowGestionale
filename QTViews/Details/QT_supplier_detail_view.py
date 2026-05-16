from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
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

from Model import (
    DBExpensesColumns,
    DBSuppliersColumns,
)
from QTViews.CustomWidgets.QT_catalog_filterable_combo_box import QTCatalogFilterableComboBox
from QTViews.CustomWidgets.QT_filterable_combo_box import QTFilterableComboBox
from Utils.View_utils import ViewUtils

if TYPE_CHECKING:
    from App_context import AppContext


class QTSupplierDetailViewH(QWidget):
    """
    Versione QT del dettaglio di un fornitore.

    Equivalente di Views/Details/Supplier_detail_view.SupplierDetailView,
    portato sui widget Qt mantenendo la stessa logica di dominio:
    - sezione informazioni in griglia 2x2 (Dati Anagrafici / Contatto /
      Categoria / Note);
    - switch "Abilita la modifica" che sblocca i campi editabili oltre
      ai bottoni Salva / Elimina;
    - sezione storico Spese con card aggregate e lista di pulsanti
      rapidi (l'apertura del dettaglio collegato passa per l'event_bus,
      come nella versione legacy).

    Strutturalmente segue il pattern di QTClientDetailViewH /
    QTInvoiceDetailViewH: head bar persistente (back + titolo + switch),
    QScrollArea per il corpo, refresh totale via load_supplier().
    """

    SECTIONS = ["Dati Anagrafici", "Contatto", "Categoria", "Note"]

    FIELDS_BY_SECTION = {
        "Dati Anagrafici": [
            (DBSuppliersColumns.NAME.value, "Nome Fornitore"),
            (DBSuppliersColumns.PARTITA_IVA.value, "Partita IVA"),
            (DBSuppliersColumns.SEDE.value, "Sede"),
        ],
        "Contatto": [
            (DBSuppliersColumns.CONTATTO.value, "Contatto"),
        ],
        "Categoria": [
            (DBSuppliersColumns.CATEGORIA.value, "Categoria"),
        ],
        "Note": [
            (DBSuppliersColumns.NOTE.value, "Note"),
        ],
    }

    def __init__(self, app_context: "AppContext", supplier_id, on_back, parent=None):
        super().__init__(parent)

        self.app_context = app_context
        self.supplier_controller = app_context.supplier_controller
        self.suppliers_query_service = app_context.suppliers_query_service
        self.suppliers_analyzer_service = app_context.suppliers_analyzer_service
        self.expenses_query_service = app_context.expenses_query_service
        self.event_bus = app_context.event_bus

        self.current_supplier_id = supplier_id
        self.on_back = on_back

        self.supplier_widgets: dict = {}
        self.supplier_labels: dict = {}
        self.section_grids: dict = {}
        self.section_rows: dict = {}

        self._build_ui()
        self.load_supplier(supplier_id)

    # ------------------------------------------------------------------
    # UI base
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        head = QFrame()
        head.setObjectName("SupplierDetailHead")
        head.setStyleSheet(
            "#SupplierDetailHead { background-color: palette(window); border-radius: 6px; }"
        )
        head_layout = QHBoxLayout(head)
        head_layout.setContentsMargins(10, 6, 10, 6)

        self.back_button = QPushButton("Elenco Fornitori")
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

    def _build_info_section(self, supplier):
        self.info_frame = QFrame()
        self.info_frame.setObjectName("SupplierInfoFrame")
        self.info_frame.setStyleSheet(
            "#SupplierInfoFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
        )
        info_layout = QGridLayout(self.info_frame)
        info_layout.setContentsMargins(15, 15, 15, 15)
        info_layout.setHorizontalSpacing(20)
        info_layout.setVerticalSpacing(10)

        # Griglia 2x2 con una sezione per cella, come nella legacy.
        for i, name in enumerate(self.SECTIONS):
            section_frame = QFrame()
            section_frame.setObjectName("SupplierInfoSectionFrame")
            section_frame.setStyleSheet(
                "#SupplierInfoSectionFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
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
                widget = self._build_field_widget(key, supplier.get(key, ""))
                self._add_field(section_name, key, label_text, widget)

        # Riga bottoni: Salva a sinistra, Elimina a destra (rosso scuro
        # come la versione legacy).
        buttons_frame = QFrame()
        buttons_layout = QHBoxLayout(buttons_frame)
        buttons_layout.setContentsMargins(15, 15, 15, 15)

        self.save_btn = QPushButton("Salva Fornitore")
        self.save_btn.clicked.connect(self._save_supplier_mod)
        buttons_layout.addWidget(self.save_btn)

        buttons_layout.addStretch(1)

        self.delete_btn = QPushButton("Elimina Fornitore")
        self.delete_btn.setStyleSheet(
            "QPushButton { background-color: #8B0000; color: palette(highlighted-text); }"
            "QPushButton:hover { background-color: #A52A2A; }"
            "QPushButton:disabled { background-color: #4a2727; color: palette(mid); }"
        )
        self.delete_btn.clicked.connect(self._delete_supplier)
        buttons_layout.addWidget(self.delete_btn)

        info_layout.addWidget(buttons_frame, 2, 0, 1, 2)

        self.content_layout.addWidget(self.info_frame)

    def _build_field_widget(self, key, value):
        if key == DBSuppliersColumns.CATEGORIA.value:
            # Il legacy attinge alla stessa sezione settori dei clienti:
            # manteniamo la scelta cosi' creator e detail condividono il
            # catalogo gia' presentato all'utente nelle altre tab.
            combo = QTCatalogFilterableComboBox.bound_to_section(
                app_context=self.app_context,
                section_name="clients_business_sectors",
                parent=self,
            )
            # Risolve la descrizione della categoria dalla chiave salvata
            # sul fornitore, esattamente come fa la legacy.
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

        if key == DBSuppliersColumns.NOTE.value:
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
        self.supplier_widgets[key] = widget
        self.supplier_labels[key] = label
        self.section_rows[section_name] = row + 1

    # ------------------------------------------------------------------
    # Caricamento dati di un fornitore specifico
    # ------------------------------------------------------------------

    def load_supplier(self, supplier_id):
        self.current_supplier_id = supplier_id
        self._clear_content()

        supplier = self.suppliers_query_service.retrieve_supplier_map_by_id(supplier_id)
        if not supplier:
            self.title_label.setText("Fornitore non trovato")
            return

        self.title_label.setText(str(supplier.get(DBSuppliersColumns.NAME.value, "")))

        self._build_info_section(supplier)
        self._toggle_edit(self.modify_switch.isChecked())

        self._build_history_section()

    def _clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.supplier_widgets.clear()
        self.supplier_labels.clear()
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

        for widget in self.supplier_widgets.values():
            widget.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Salvataggio / eliminazione
    # ------------------------------------------------------------------

    def _save_supplier_mod(self):
        supplier_data = self._collect_supplier_data()
        success, message = self.supplier_controller.update_supplier(
            self.current_supplier_id, supplier_data
        )
        if success:
            QMessageBox.information(self, "SALVATAGGIO COMPLETATO", message)
            self.modify_switch.setChecked(False)
            self.load_supplier(self.current_supplier_id)
        else:
            QMessageBox.critical(self, "ERRORE", message)

    def _collect_supplier_data(self):
        supplier_data = {}
        for key, widget in self.supplier_widgets.items():
            if isinstance(widget, QTFilterableComboBox):
                supplier_data[key] = widget.value()
            elif isinstance(widget, QLineEdit):
                supplier_data[key] = widget.text().strip()
            elif isinstance(widget, QTextEdit):
                supplier_data[key] = widget.toPlainText().strip()
        return supplier_data

    def _delete_supplier(self):
        confirm = QMessageBox.question(
            self,
            "ELIMINAZIONE FORNITORE",
            "Stai per eliminare questo fornitore.\nDesideri continuare?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        expenses = self.expenses_query_service.retrieve_expense_map_list_by_supplier(
            self.current_supplier_id
        )

        if expenses:
            QMessageBox.critical(
                self,
                "ERRORE",
                "Impossibile eliminare il fornitore.\n\n"
                "Esiste un item collegato a questo fornitore.\n"
                "Eliminare ogni riferimento a questo fornitore per poterlo "
                "eliminare dal database.",
            )
            return

        success, message = self.supplier_controller.delete_supplier(self.current_supplier_id)
        if success:
            QMessageBox.information(self, "CONFERMA ELIMINAZIONE", message)
            self._cleanup_and_go_back()
        else:
            QMessageBox.critical(self, "ERRORE", message)

    # ------------------------------------------------------------------
    # Sezione storico spese
    # ------------------------------------------------------------------

    def _build_history_section(self):
        # Wrapper con lo stesso stile a bordo blu della info_frame, in
        # linea con quello che abbiamo gia' nel detail clienti.
        wrapper = QFrame()
        wrapper.setObjectName("SupplierHistoryWrapper")
        wrapper.setStyleSheet(
            "#SupplierHistoryWrapper { border: 2px solid palette(highlight); border-radius: 6px; }"
        )
        wrapper_layout = QHBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(15, 15, 15, 15)
        wrapper_layout.setSpacing(20)

        wrapper_layout.addWidget(self._create_expenses_history(), stretch=1)

        self.content_layout.addWidget(wrapper)

    def _create_expenses_history(self):
        section = self._make_section_frame("SPESE")
        year = datetime.now().year

        cards = QHBoxLayout()
        cards.addWidget(self._make_info_card(
            "TOTALE SPESE (All Time)",
            f"{self._fmt(self.suppliers_analyzer_service.calcola_tot_spese_supplier(self.current_supplier_id, year=-1))} €",
        ))
        cards.addWidget(self._make_info_card(
            f"TOTALE SPESE {year}",
            f"{self._fmt(self.suppliers_analyzer_service.calcola_tot_spese_supplier(self.current_supplier_id))} €",
        ))
        cards.addStretch(1)
        section.layout().addLayout(cards)

        section.layout().addWidget(self._make_subtitle(f"- Elenco Spese {year} -"))

        expenses_list = QFrame()
        list_layout = QVBoxLayout(expenses_list)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(6)

        expenses = self.suppliers_query_service.retrieve_supplier_with_expenses_map_list(
            self.current_supplier_id
        )
        for expense in expenses:
            nome_spesa = expense.get(DBExpensesColumns.NAME.value)
            if not nome_spesa:
                continue
            expense_id = expense[DBExpensesColumns.ID.value]
            btn = QPushButton(str(nome_spesa))
            btn.setStyleSheet("text-align: left; padding: 6px;")
            btn.clicked.connect(lambda _checked=False, eid=expense_id: self._show_expense_detail(eid))
            list_layout.addWidget(btn)

        list_layout.addStretch(1)
        section.layout().addWidget(expenses_list, stretch=1)
        return section

    def _show_expense_detail(self, expense_id):
        self.event_bus.publish(ViewUtils.EventBusKeys.SHOW_EXPENSE_DETAIL.value, expense_id)

    # ------------------------------------------------------------------
    # Helper grafici condivisi con la detail clienti/fatture
    # ------------------------------------------------------------------

    def _make_section_frame(self, title):
        frame = QFrame()
        frame.setObjectName("SupplierRelatedSectionFrame")
        frame.setStyleSheet(
            "#SupplierRelatedSectionFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
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
        card.setObjectName("SupplierInfoCard")
        card.setStyleSheet(
            "#SupplierInfoCard { background-color: palette(alternate-base); border-radius: 6px; }"
            "#SupplierInfoCard QLabel { color: palette(text); }"
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

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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

from Model import DBSuppliersColumns
from QTViews.CustomWidgets.QT_catalog_filterable_combo_box import QTCatalogFilterableComboBox
from QTViews.CustomWidgets.QT_filterable_combo_box import QTFilterableComboBox

if TYPE_CHECKING:
    from App_context import AppContext


class QTSupplierCreateViewH(QDialog):
    """
    Versione QT del creator di un fornitore.

    Equivalente di Views/Creators/Supplier_create_view.SupplierCreateView,
    realizzato come QDialog modale sulla scia di QTClientCreateViewH e
    QTInvoiceCreateViewH: QScrollArea + QFormLayout, stessa convenzione
    widget/error_labels e notifica al chiamante via
    ``on_supplier_created(supplier_id)``.

    Il flusso resta identico al legacy:
        raccolta dati → SupplierController.save_supplier → recupero id
        dell'ultimo insert → callback al chiamante → close().
    La validazione lato view e' minima (campo NOME non vuoto): la regola
    sulla partita IVA resta nel controller, come nella versione customtkinter.
    """

    def __init__(self, app_context: "AppContext", parent=None, on_supplier_created=None):
        super().__init__(parent)

        self.app_context = app_context
        self.supplier_controller = app_context.supplier_controller
        self.suppliers_query_service = app_context.suppliers_query_service
        self.on_supplier_created = on_supplier_created

        self.setWindowTitle("Aggiungi Nuovo Fornitore")
        self.resize(460, 500)
        self.setModal(True)

        self.supplier_widgets: dict = {}
        self.supplier_labels: dict = {}
        self.error_labels: dict = {}

        self._build_ui()

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

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(20, 20, 20, 20)
        container_layout.setSpacing(0)

        self.form_layout = QFormLayout()
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setSpacing(12)
        self.form_layout.setLabelAlignment(Qt.AlignLeft)
        self.form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        container_layout.addLayout(self.form_layout)
        container_layout.addStretch(1)

        self._build_simple_entry(DBSuppliersColumns.NAME.value, "Nome", with_error=True)
        self._build_simple_entry(DBSuppliersColumns.PARTITA_IVA.value, "Partita IVA")
        self._build_simple_entry(DBSuppliersColumns.SEDE.value, "Sede")
        self._build_simple_entry(DBSuppliersColumns.CONTATTO.value, "Contatto Referente")
        self._build_categoria_row()
        self._build_note_row()

        bottom = QHBoxLayout()
        bottom.setContentsMargins(20, 10, 20, 20)
        bottom.addStretch(1)
        self.save_button = QPushButton("Salva Fornitore")
        self.save_button.setMinimumSize(120, 40)
        self.save_button.clicked.connect(self._save_supplier_data)
        bottom.addWidget(self.save_button)
        bottom.addStretch(1)
        outer.addLayout(bottom)

        self._bind_validations()

    def _build_simple_entry(self, key, label_text, with_error=False):
        edit = QLineEdit()
        label = QLabel(label_text)
        self.form_layout.addRow(label, edit)
        self.supplier_widgets[key] = edit
        self.supplier_labels[key] = label

        if with_error:
            error = QLabel("")
            error.setStyleSheet("color: #d62929; font-size: 11px;")
            error.setVisible(False)
            self.form_layout.addRow("", error)
            self.error_labels[key] = error

    def _build_categoria_row(self):
        # Il legacy pesca i valori dalla stessa sezione settori dei clienti
        # ("clients_business_sectors"): manteniamo la stessa scelta cosi'
        # creator e detail fornitore condividono il catalogo con i clienti.
        combo = QTCatalogFilterableComboBox.bound_to_section(
            app_context=self.app_context,
            section_name="clients_business_sectors",
            parent=self,
            autofill=True,
        )
        # Default su "Energia e Risorse Naturali" come nella versione
        # customtkinter (chiave ENERGY del catalogo).
        default = next(
            (
                desc
                for k, desc in self.app_context.catalogo_elenchi["clients_business_sectors"]
                if k == "ENERGY"
            ),
            None,
        )
        if default is not None:
            combo.set_value(default)

        label = QLabel("Categoria")
        self.form_layout.addRow(label, combo)
        self.supplier_widgets[DBSuppliersColumns.CATEGORIA.value] = combo
        self.supplier_labels[DBSuppliersColumns.CATEGORIA.value] = label

    def _build_note_row(self):
        text = QTextEdit()
        text.setFixedHeight(80)
        label = QLabel("Note")
        self.form_layout.addRow(label, text)
        self.supplier_widgets[DBSuppliersColumns.NOTE.value] = text
        self.supplier_labels[DBSuppliersColumns.NOTE.value] = label

    # ------------------------------------------------------------------
    # Validazioni lato view
    # ------------------------------------------------------------------

    def _bind_validations(self):
        name_edit: QLineEdit = self.supplier_widgets[DBSuppliersColumns.NAME.value]
        name_error = self.error_labels[DBSuppliersColumns.NAME.value]

        def _validate_name():
            if not name_edit.text().strip():
                name_error.setText("Il nome non puo essere vuoto.")
            else:
                name_error.setText("")

        name_edit.editingFinished.connect(_validate_name)

    # ------------------------------------------------------------------
    # Salvataggio
    # ------------------------------------------------------------------

    def _collect_supplier_data(self):
        supplier_data = {}
        for key, widget in self.supplier_widgets.items():
            if isinstance(widget, QTFilterableComboBox):
                # value() restituisce "" se la selezione non e' fra le voci
                # valide, evitando di passare al controller testo libero.
                supplier_data[key] = widget.value()
            elif isinstance(widget, QLineEdit):
                supplier_data[key] = widget.text().strip()
            elif isinstance(widget, QTextEdit):
                supplier_data[key] = widget.toPlainText().strip()
        return supplier_data

    def _save_supplier_data(self):
        supplier_data = self._collect_supplier_data()
        success, message = self.supplier_controller.save_supplier(supplier_data)
        if not success:
            QMessageBox.critical(self, "ERRORE", message)
            return

        supplier_map = self.suppliers_query_service.retrieve_last_supplier_insert_map()
        supplier_id = supplier_map[DBSuppliersColumns.ID.value] if supplier_map else None

        if self.on_supplier_created is not None and supplier_id is not None:
            self.on_supplier_created(supplier_id)

        self.accept()

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
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

from Gestionale_Enums import TipologiaCliente
from Model import DBClientsColumns
from QTViews.CustomWidgets.QT_catalog_filterable_combo_box import QTCatalogFilterableComboBox
from QTViews.CustomWidgets.QT_filterable_combo_box import QTFilterableComboBox

if TYPE_CHECKING:
    from App_context import AppContext


class QTClientCreateViewH(QDialog):
    """
    Versione QT del creator di un cliente.

    Equivalente di Views/Creators/Client_create_view.ClientCreateView, ma
    realizzato come QDialog modale sulla scia di QTInvoiceCreateViewH:
    QScrollArea + QFormLayout, stessa convenzione widget/error_labels e
    stessa notifica al chiamante via ``on_client_created(client_id)``.

    Il flusso resta identico al legacy:
        raccolta dati → ClientController.save_client → recupero id appena
        inserito → callback al chiamante → close().
    La validazione lato view e' minima (campo NOME non vuoto): le altre
    regole — partita IVA / email / contatto referente — restano in carico
    al controller, come nella versione customtkinter.
    """

    def __init__(self, app_context: "AppContext", parent=None, on_client_created=None):
        super().__init__(parent)

        self.app_context = app_context
        self.client_controller = app_context.client_controller
        self.clients_query_service = app_context.clients_query_service
        self.on_client_created = on_client_created

        self.setWindowTitle("Aggiungi Nuovo Cliente")
        self.resize(460, 720)
        self.setModal(True)

        self.client_widgets: dict = {}
        self.client_labels: dict = {}
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

        self.form_layout = QFormLayout(container)
        self.form_layout.setContentsMargins(20, 20, 20, 20)
        self.form_layout.setSpacing(8)
        self.form_layout.setLabelAlignment(Qt.AlignLeft)
        self.form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self._build_simple_entry(DBClientsColumns.NAME.value, "Nome", with_error=True)
        self._build_tipologia_row()
        self._build_simple_entry(DBClientsColumns.PARTITA_IVA.value, "Partita IVA", with_error=True)
        self._build_simple_entry(DBClientsColumns.EMAIL.value, "Email", with_error=True)
        self._build_simple_entry(DBClientsColumns.SEDE_LEGALE.value, "Sede Legale", with_error=True)
        self._build_settore_row()
        self._build_simple_entry(DBClientsColumns.REFERENTE.value, "Referente")
        self._build_simple_entry(DBClientsColumns.CONTATTO_REFERENTE.value, "Contatto Referente")
        self._build_note_row()

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.save_button = QPushButton("Salva Cliente")
        self.save_button.clicked.connect(self._save_client_data)
        bottom.addWidget(self.save_button)
        bottom.addStretch(1)
        outer.addLayout(bottom)

        self._bind_validations()

    def _build_simple_entry(self, key, label_text, with_error=False):
        edit = QLineEdit()
        label = QLabel(label_text)
        self.form_layout.addRow(label, edit)
        self.client_widgets[key] = edit
        self.client_labels[key] = label

        if with_error:
            error = QLabel("")
            error.setStyleSheet("color: #d62929;")
            self.form_layout.addRow("", error)
            self.error_labels[key] = error

    def _build_tipologia_row(self):
        combo = QComboBox()
        combo.addItems([item.value for item in TipologiaCliente])
        combo.setCurrentText(TipologiaCliente.PRIVATO.value)
        label = QLabel("Tipologia")
        self.form_layout.addRow(label, combo)
        self.client_widgets[DBClientsColumns.TIPOLOGIA.value] = combo
        self.client_labels[DBClientsColumns.TIPOLOGIA.value] = label

    def _build_settore_row(self):
        combo = QTCatalogFilterableComboBox.bound_to_section(
            app_context=self.app_context,
            section_name="clients_business_sectors",
            parent=self,
            autofill=True,
        )
        label = QLabel("Settore")
        self.form_layout.addRow(label, combo)
        self.client_widgets[DBClientsColumns.SETTORE.value] = combo
        self.client_labels[DBClientsColumns.SETTORE.value] = label

        error = QLabel("")
        error.setStyleSheet("color: #d62929;")
        self.form_layout.addRow("", error)
        self.error_labels[DBClientsColumns.SETTORE.value] = error

    def _build_note_row(self):
        text = QTextEdit()
        text.setFixedHeight(80)
        label = QLabel("Note")
        self.form_layout.addRow(label, text)
        self.client_widgets[DBClientsColumns.NOTE.value] = text
        self.client_labels[DBClientsColumns.NOTE.value] = label

    # ------------------------------------------------------------------
    # Validazioni lato view
    # ------------------------------------------------------------------

    def _bind_validations(self):
        name_edit: QLineEdit = self.client_widgets[DBClientsColumns.NAME.value]
        name_error = self.error_labels[DBClientsColumns.NAME.value]

        def _validate_name():
            if not name_edit.text().strip():
                name_error.setText("Il nome non puo essere vuoto.")
            else:
                name_error.setText("")

        name_edit.editingFinished.connect(_validate_name)

    # ------------------------------------------------------------------
    # Salvataggio
    # ------------------------------------------------------------------

    def _collect_client_data(self):
        client_data = {}
        for key, widget in self.client_widgets.items():
            if isinstance(widget, QTFilterableComboBox):
                # value() restituisce "" se la selezione non e' fra le voci
                # valide, evitando di passare al controller testo libero.
                client_data[key] = widget.value()
            elif isinstance(widget, QLineEdit):
                client_data[key] = widget.text().strip()
            elif isinstance(widget, QComboBox):
                client_data[key] = widget.currentText().strip()
            elif isinstance(widget, QTextEdit):
                client_data[key] = widget.toPlainText().strip()
        return client_data

    def _save_client_data(self):
        client_data = self._collect_client_data()
        success, message = self.client_controller.save_client(client_data)
        if not success:
            QMessageBox.critical(self, "ERRORE", message)
            return

        client_map = self.clients_query_service.retrieve_client_map_by_name(
            client_data[DBClientsColumns.NAME.value]
        )
        client_id = client_map[DBClientsColumns.ID.value] if client_map else None

        if self.on_client_created is not None and client_id is not None:
            self.on_client_created(client_id)

        self.accept()

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

from Gestionale_Enums import ProductionStatus
from Model import DBClientsColumns, DBProductionsColumns
from QTViews.CustomWidgets.QT_catalog_filterable_combo_box import QTCatalogFilterableComboBox
from QTViews.CustomWidgets.QT_filterable_combo_box import QTFilterableComboBox

if TYPE_CHECKING:
    from App_context import AppContext


class QTProductionCreateViewH(QDialog):
    """
    Versione QT del creator di una produzione.

    Equivalente di Views/Creators/Production_create_view.ProductionCreateView,
    realizzato come QDialog modale sulla scia di QTInvoiceCreateViewH /
    QTClientCreateViewH: QScrollArea + QFormLayout, stessa convenzione
    widget/error_labels e notifica al chiamante via
    ``on_production_created(production_id)``.

    La logica di dominio resta invariata:
    - il campo NOME PRODUZIONE viene mostrato preceduto da un prefisso
      visivo "<cliente> - " che cambia al variare del cliente
      selezionato (auto-compile come nella legacy); il prefisso e' solo
      decorativo, sara' il ``ProductionController.save_production`` ad
      anteporre il nome cliente al testo digitato dall'utente;
    - le tipologie produzione/output usano la QTCatalogFilterableComboBox
      bound_to_section, cosi' resta disponibile la voce "Aggiungi …" che
      apre la modale di add gia' usata negli altri creator.
    """

    CLIENT_NAME_FIELD = "NOME CLIENTE"

    def __init__(self, app_context: "AppContext", parent=None, on_production_created=None):
        super().__init__(parent)

        self.app_context = app_context
        self.production_controller = app_context.production_controller
        self.clients_query_service = app_context.clients_query_service
        self.productions_query_service = app_context.productions_query_service
        self.on_production_created = on_production_created

        self.setWindowTitle("Aggiungi Nuova Produzione")
        self.resize(560, 700)
        self.setModal(True)

        self.production_widgets: dict = {}
        self.production_labels: dict = {}
        self.error_labels: dict = {}
        self.name_prefix_label: QLabel = None

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

        self._build_client_row()
        self._build_name_row()
        self._build_simple_entry(DBProductionsColumns.HOURS.value, "Ore di produzione", with_error=True)
        self._build_tipologia_produzione_row()
        self._build_tipologia_output_row()
        self._build_stato_row()
        self._build_end_date_row()
        self._build_simple_entry(DBProductionsColumns.TOTALE_PREVENTIVO.value, "Totale Preventivo (€)", with_error=True)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(20, 10, 20, 20)
        bottom.addStretch(1)
        self.save_button = QPushButton("Salva Produzione")
        self.save_button.setMinimumSize(140, 40)
        self.save_button.clicked.connect(self._save_production_data)
        bottom.addWidget(self.save_button)
        bottom.addStretch(1)
        outer.addLayout(bottom)

        self._bind_validations()

    def _build_client_row(self):
        clients = self.clients_query_service.retrieve_clients_map_list()
        combo = QTFilterableComboBox(
            values=[c[DBClientsColumns.NAME.value] for c in clients],
            placeholder="Cerca cliente…",
            autofill=True,
        )
        combo.currentTextChanged.connect(self._on_client_changed)

        label = QLabel(self.CLIENT_NAME_FIELD)
        self.form_layout.addRow(label, combo)
        self.production_widgets[self.CLIENT_NAME_FIELD] = combo
        self.production_labels[self.CLIENT_NAME_FIELD] = label

    def _build_name_row(self):
        # Mostriamo "<cliente> - " come prefisso non editabile alla
        # sinistra del QLineEdit, esattamente come fa la legacy.
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)

        self.name_prefix_label = QLabel("")
        row_layout.addWidget(self.name_prefix_label)

        edit = QLineEdit()
        row_layout.addWidget(edit, stretch=1)

        label = QLabel(DBProductionsColumns.NAME.value)
        self.form_layout.addRow(label, row)
        self.production_widgets[DBProductionsColumns.NAME.value] = edit
        self.production_labels[DBProductionsColumns.NAME.value] = label

        error = QLabel("")
        error.setStyleSheet("color: #d62929;")
        self.form_layout.addRow("", error)
        self.error_labels[DBProductionsColumns.NAME.value] = error

    def _build_simple_entry(self, key, label_text, with_error=False):
        edit = QLineEdit()
        label = QLabel(label_text)
        self.form_layout.addRow(label, edit)
        self.production_widgets[key] = edit
        self.production_labels[key] = label

        if with_error:
            error = QLabel("")
            error.setStyleSheet("color: #d62929;")
            self.form_layout.addRow("", error)
            self.error_labels[key] = error

    def _build_tipologia_produzione_row(self):
        combo = QTCatalogFilterableComboBox.bound_to_section(
            app_context=self.app_context,
            section_name="production_types",
            parent=self,
            autofill=True,
        )
        label = QLabel("Tipologia Produzione")
        self.form_layout.addRow(label, combo)
        self.production_widgets[DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value] = combo
        self.production_labels[DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value] = label

    def _build_tipologia_output_row(self):
        combo = QTCatalogFilterableComboBox.bound_to_section(
            app_context=self.app_context,
            section_name="production_output_types",
            parent=self,
            autofill=True,
        )
        label = QLabel("Tipologia Output")
        self.form_layout.addRow(label, combo)
        self.production_widgets[DBProductionsColumns.TIPOLOGIA_OUTPUT.value] = combo
        self.production_labels[DBProductionsColumns.TIPOLOGIA_OUTPUT.value] = label

    def _build_stato_row(self):
        combo = QComboBox()
        combo.addItems([s.value for s in ProductionStatus])
        combo.setCurrentText(ProductionStatus.START_WAITING.value)
        label = QLabel("Stato")
        self.form_layout.addRow(label, combo)
        self.production_widgets[DBProductionsColumns.STATO.value] = combo
        self.production_labels[DBProductionsColumns.STATO.value] = label

    def _build_end_date_row(self):
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("yyyy-MM-dd")
        date_edit.setDate(QDate.currentDate())
        label = QLabel("Data Consegna")
        self.form_layout.addRow(label, date_edit)
        self.production_widgets[DBProductionsColumns.END_DATE.value] = date_edit
        self.production_labels[DBProductionsColumns.END_DATE.value] = label

    # ------------------------------------------------------------------
    # Inizializzazione e callback dinamici
    # ------------------------------------------------------------------

    def _initialize_default_values(self):
        clients = self.clients_query_service.retrieve_clients_map_list()
        if clients:
            first_client = clients[0][DBClientsColumns.NAME.value]
            self.production_widgets[self.CLIENT_NAME_FIELD].set_value(first_client)
            self._on_client_changed(first_client)

    def _on_client_changed(self, client_name):
        if self.name_prefix_label is None:
            return
        prefix = f"{client_name} - " if client_name else ""
        self.name_prefix_label.setText(prefix)

    # ------------------------------------------------------------------
    # Validazioni lato view
    # ------------------------------------------------------------------

    def _bind_validations(self):
        # Nome non vuoto.
        name_edit: QLineEdit = self.production_widgets[DBProductionsColumns.NAME.value]
        name_error = self.error_labels[DBProductionsColumns.NAME.value]

        def _validate_name():
            if not name_edit.text().strip():
                name_error.setText("Il campo non puo essere vuoto.")
            else:
                name_error.setText("")

        name_edit.editingFinished.connect(_validate_name)

        # Ore intere positive.
        hours_edit: QLineEdit = self.production_widgets[DBProductionsColumns.HOURS.value]
        hours_error = self.error_labels[DBProductionsColumns.HOURS.value]

        def _validate_hours():
            value = hours_edit.text().strip()
            if not value or not value.isdigit():
                hours_error.setText("Il campo deve contenere un numero intero.")
            else:
                hours_error.setText("")

        hours_edit.editingFinished.connect(_validate_hours)

        # Totale preventivo: importo monetario max 2 decimali.
        import re

        tot_edit: QLineEdit = self.production_widgets[DBProductionsColumns.TOTALE_PREVENTIVO.value]
        tot_error = self.error_labels[DBProductionsColumns.TOTALE_PREVENTIVO.value]

        def _validate_amount():
            value = tot_edit.text().strip()
            if re.fullmatch(r"^\d+(\.\d{1,2})?$", value):
                tot_error.setText("")
            else:
                tot_error.setText("Inserimento non valido: usare un importo come 123.45")

        tot_edit.editingFinished.connect(_validate_amount)

    # ------------------------------------------------------------------
    # Salvataggio
    # ------------------------------------------------------------------

    def _collect_production_data(self):
        production_data = {}
        for key, widget in self.production_widgets.items():
            if isinstance(widget, QTFilterableComboBox):
                production_data[key] = widget.value()
            elif isinstance(widget, QLineEdit):
                production_data[key] = widget.text().strip()
            elif isinstance(widget, QComboBox):
                production_data[key] = widget.currentText().strip()
            elif isinstance(widget, QDateEdit):
                production_data[key] = widget.date().toString("yyyy-MM-dd")
        return production_data

    def prefill_client(self, client_name: str) -> None:
        """Pre-seleziona il cliente nel combo e aggiorna il prefisso nome."""
        if not client_name:
            return
        combo = self.production_widgets.get("NOME CLIENTE")
        if combo is None:
            return
        combo.set_value(client_name)
        self._on_client_changed(client_name)

    def _save_production_data(self):
        production_data = self._collect_production_data()
        success, message = self.production_controller.save_production(production_data)
        if not success:
            QMessageBox.critical(self, "ERRORE", message)
            return

        production_map = self.productions_query_service.retrieve_last_production_insert_map()
        production_id = production_map[DBProductionsColumns.ID.value] if production_map else None

        if self.on_production_created is not None and production_id is not None:
            self.on_production_created(production_id)

        self.accept()

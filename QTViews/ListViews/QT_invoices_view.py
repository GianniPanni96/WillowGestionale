import time
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from QTViews.Creators.QT_invoice_create_view import QTInvoiceCreateViewH
from QTViews.ListViews.QT_invoices_table_model import InvoicesTableModel, RateDelegate

if TYPE_CHECKING:
    from App_context import AppContext


class QTInvoicesViewH(QWidget):
    """
    Versione QT della list view delle fatture.

    Differenza architetturale chiave rispetto alla versione customtkinter:
    qui non si crea un widget per ogni fattura. Si crea un solo modello in
    memoria con i dati pronti, e una QTableView che renderizza solo le
    celle effettivamente visibili. Il filtro e l'ordinamento avvengono sul
    modello (operazioni su dati), non sui widget.
    """

    TIME_WINDOWS = [
        ("60 GG", 60),
        ("90 GG", 90),
        ("365 GG", 365),
        ("TUTTE", None),
    ]

    def __init__(self, app_context: "AppContext", initial_invoice_id=None,
                 on_open_detail=None, parent=None):
        super().__init__(parent)

        self.app_context = app_context
        self.invoices_query_service = app_context.invoices_query_service
        self.invoices_analyzer_service = app_context.invoices_analyzer_service
        self.clients_query_service = app_context.clients_query_service
        self.user_query_service = app_context.user_query_service
        self.productions_query_service = app_context.productions_query_service

        self._initial_invoice_id = initial_invoice_id
        self._on_open_detail = on_open_detail

        self._build_ui()
        self._reload_data(window_days=60)

        if initial_invoice_id is not None:
            self._select_invoice(initial_invoice_id)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        self.aggregates_bar = QHBoxLayout()
        self.aggregates_bar.setSpacing(10)
        root.addLayout(self.aggregates_bar)

        self._aggregate_labels = {}
        for key in ("# FATTURE", "FATTURATO", "CREDITI", "MEDIA FATTURE"):
            card = QFrame()
            card.setFrameShape(QFrame.StyledPanel)
            card.setStyleSheet(
                "QFrame { background-color: #333333; border-radius: 6px; }"
                "QLabel { color: #f0f0f0; }"
            )
            box = QVBoxLayout(card)
            box.setContentsMargins(12, 8, 12, 8)
            title = QLabel(key)
            title.setAlignment(Qt.AlignCenter)
            title.setStyleSheet("background-color: #1F6AA5; padding: 4px; border-radius: 4px;")
            value = QLabel("0")
            value.setAlignment(Qt.AlignCenter)
            f = value.font()
            f.setPointSize(12)
            value.setFont(f)
            box.addWidget(title)
            box.addWidget(value)
            self.aggregates_bar.addWidget(card)
            self._aggregate_labels[key] = value
        self.aggregates_bar.addStretch(1)

        self.lordo_netto_combo = QComboBox()
        self.lordo_netto_combo.addItems(["LORDI", "NETTI"])
        self.lordo_netto_combo.currentIndexChanged.connect(self._refresh_aggregates)
        self.aggregates_bar.addWidget(self.lordo_netto_combo)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        root.addLayout(controls)

        controls.addWidget(QLabel("Mostra ultimi"))
        self.window_combo = QComboBox()
        for label, _ in self.TIME_WINDOWS:
            self.window_combo.addItem(label)
        self.window_combo.setCurrentIndex(0)
        self.window_combo.currentIndexChanged.connect(self._on_window_changed)
        controls.addWidget(self.window_combo)

        controls.addSpacing(20)

        controls.addStretch(1)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Cerca in tutte le colonne…")
        self.search_edit.textChanged.connect(self._apply_filter)
        controls.addWidget(self.search_edit, stretch=1)

        self.table = QTableView()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setItemDelegateForColumn(InvoicesTableModel.COL_RATE, RateDelegate(self))
        self.table.doubleClicked.connect(self._on_row_double_clicked)
        root.addWidget(self.table, stretch=1)

        bottom = QHBoxLayout()
        self.add_button = QPushButton("Aggiungi una fattura")
        self.add_button.clicked.connect(self._on_add_invoice)
        bottom.addStretch(1)
        bottom.addWidget(self.add_button)
        bottom.addStretch(1)
        root.addLayout(bottom)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888888;")
        root.addWidget(self.status_label)

    def _reload_data(self, window_days=None):
        t0 = time.perf_counter()

        if window_days is None:
            invoices = self.invoices_query_service.retrieve_invoices_map_list(year=-1)
        else:
            invoices = self.invoices_query_service.get_invoices_for_days_window(window_days)

        t_query = time.perf_counter()

        rows = InvoicesTableModel.build_rows(
            invoices,
            self.clients_query_service,
            self.user_query_service,
            self.productions_query_service,
            self.invoices_query_service,
        )

        t_build = time.perf_counter()

        self._source_model = InvoicesTableModel(rows, self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._source_model)
        self._proxy.setSortRole(Qt.UserRole)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        # -1 = filtra su tutte le colonne testuali della tabella.
        self._proxy.setFilterKeyColumn(-1)
        self.table.setModel(self._proxy)

        t_view = time.perf_counter()

        self._refresh_aggregates()
        self._apply_filter()

        self.status_label.setText(
            f"Caricate {len(rows)} fatture — "
            f"query: {(t_query - t0) * 1000:.0f} ms, "
            f"build righe: {(t_build - t_query) * 1000:.0f} ms, "
            f"setup view: {(t_view - t_build) * 1000:.0f} ms"
        )

    def _on_window_changed(self):
        idx = self.window_combo.currentIndex()
        _, days = self.TIME_WINDOWS[idx]
        self._reload_data(window_days=days)
        if self._initial_invoice_id is not None:
            self._select_invoice(self._initial_invoice_id)

    def _apply_filter(self):
        self._proxy.setFilterFixedString(self.search_edit.text())

    def _refresh_aggregates(self):
        netti = self.lordo_netto_combo.currentText() == "NETTI"

        count = self.invoices_analyzer_service.count_invoices(include_unpaid_invoices=False)

        if netti:
            fatturato = self.invoices_analyzer_service.calculate_FATT_NETTO_invoiced(
                include_unpaid_invoices=False
            )
            crediti = self.invoices_analyzer_service.calculate_CRED_NETTO_invoiced(
                include_unpaid_invoices=False
            )
            media = self.invoices_analyzer_service.calculate_MEDIA_FATTURA_NETTO_invoiced(
                include_unpaid_invoices=False
            )
        else:
            fatturato = self.invoices_analyzer_service.calculate_FATT_LORDO_invoiced(
                include_unpaid_invoices=False
            )
            crediti = self.invoices_analyzer_service.calculate_CRED_LORDO_invoiced(
                include_unpaid_invoices=False
            )
            media = self.invoices_analyzer_service.calculate_MEDIA_FATTURA_LORDO_invoiced(
                include_unpaid_invoices=False
            )

        if media is None or media < 0:
            media = 0

        self._aggregate_labels["# FATTURE"].setText(str(count))
        self._aggregate_labels["FATTURATO"].setText(f"{fatturato} €")
        self._aggregate_labels["CREDITI"].setText(f"{crediti} €")
        self._aggregate_labels["MEDIA FATTURE"].setText(f"{media} €")

    def _select_invoice(self, invoice_id):
        source_row = self._source_model.find_row_by_invoice_id(invoice_id)
        if source_row < 0:
            return
        proxy_index = self._proxy.mapFromSource(self._source_model.index(source_row, 0))
        if not proxy_index.isValid():
            return
        self.table.selectRow(proxy_index.row())
        self.table.scrollTo(proxy_index, QAbstractItemView.PositionAtCenter)

    def _on_row_double_clicked(self, proxy_index):
        if not proxy_index.isValid() or self._on_open_detail is None:
            return
        source_index = self._proxy.mapToSource(proxy_index)
        invoice_id = self._source_model.data(source_index, InvoicesTableModel.ROLE_INVOICE_ID)
        if invoice_id is not None:
            self._on_open_detail(invoice_id)

    def _on_add_invoice(self):
        dialog = QTInvoiceCreateViewH(
            app_context=self.app_context,
            parent=self,
            on_invoice_created=self._on_invoice_created,
        )
        dialog.exec()

    def _on_invoice_created(self, invoice_id):
        idx = self.window_combo.currentIndex()
        _, days = self.TIME_WINDOWS[idx]
        self._reload_data(window_days=days)
        if invoice_id is not None:
            self._select_invoice(invoice_id)
            if self._on_open_detail is not None:
                self._on_open_detail(invoice_id)

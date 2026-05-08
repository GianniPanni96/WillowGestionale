"""
Base condivisa per le list view in versione Qt.

Replica in chiave Qt il pattern di Views/ListViews/BaseList_view.py: la
classe base mette a disposizione l'ossatura comune di una list view —
barra aggregati, controllo time window, search box, tabella, bottone di
aggiunta, status label — e delega alle sottoclassi tutto cio' che dipende
dal dominio (modello dati, calcolo aggregati, dialog di creazione,
identificazione delle righe).

Differenza chiave rispetto al BaseListView legacy: qui non si crea un
widget per ogni item della lista. La rappresentazione tabellare e la
logica di sort/filter restano interamente delegate al meccanismo
QAbstractTableModel + QSortFilterProxyModel di Qt — efficiente perche'
la QTableView renderizza solo le celle visibili. La base si limita ad
orchestrare il ciclo "fetch → build_rows → swap del source model" e a
collegare i controlli UI al proxy.
"""

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

if TYPE_CHECKING:
    from App_context import AppContext


class QTBaseListView(QWidget):
    """
    Sottoclasse questa view per ogni dominio (Fatture, Clienti, …) e
    implementa gli hook indicati. Il flusso di costruzione e' fisso:

        __init__ → _setup_services(ctx) → _build_ui() → _reload_data()

    e ogni cambio di time window / inserimento / refresh riusa la stessa
    pipeline.
    """

    # ------------------------------------------------------------------
    # Configurazione statica — override nelle sottoclassi
    # ------------------------------------------------------------------

    AGGREGATE_KEYS = ()
    """Etichette delle card aggregate da mostrare in alto (in ordine)."""

    AGGREGATE_TOGGLE_OPTIONS = None
    """Se valorizzato (es. ('LORDI', 'NETTI')), mostra un combo a destra
    delle card aggregate; il valore corrente viene passato a
    compute_aggregates()."""

    TIME_WINDOWS = (
        ("60 GG", 60),
        ("90 GG", 90),
        ("365 GG", 365),
        ("TUTTE", None),
    )
    """Tuple (label, giorni). None = nessun limite temporale."""

    DEFAULT_WINDOW_INDEX = 0

    SEARCH_PLACEHOLDER = "Cerca in tutte le colonne…"
    ADD_BUTTON_TEXT = "Aggiungi un elemento"
    ITEM_LABEL_PLURAL = "elementi"

    # ------------------------------------------------------------------
    # Costruzione
    # ------------------------------------------------------------------

    def __init__(
        self,
        app_context: "AppContext",
        initial_item_id=None,
        on_open_detail=None,
        parent=None,
    ):
        super().__init__(parent)

        self.app_context = app_context
        self._initial_item_id = initial_item_id
        self._on_open_detail = on_open_detail

        self._source_model = None
        self._proxy = None
        self._aggregate_labels: dict = {}
        self.aggregate_toggle = None

        # I servizi di dominio devono essere disponibili prima di _build_ui
        # e _reload_data (entrambi possono interrogare le sottoclassi).
        self._setup_services(app_context)

        self._build_ui()

        _, days = self.TIME_WINDOWS[self.DEFAULT_WINDOW_INDEX]
        self._reload_data(window_days=days)

        if initial_item_id is not None:
            self._select_item(initial_item_id)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        self._build_aggregates_bar(root)
        self._build_controls_bar(root)
        self._build_table(root)
        self._build_bottom_bar(root)

    def _build_aggregates_bar(self, root: QVBoxLayout):
        if not self.AGGREGATE_KEYS:
            return

        self.aggregates_bar = QHBoxLayout()
        self.aggregates_bar.setSpacing(10)
        root.addLayout(self.aggregates_bar)

        for key in self.AGGREGATE_KEYS:
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
            title.setStyleSheet(
                "background-color: #1F6AA5; padding: 4px; border-radius: 4px;"
            )
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

        if self.AGGREGATE_TOGGLE_OPTIONS:
            self.aggregate_toggle = QComboBox()
            self.aggregate_toggle.addItems(list(self.AGGREGATE_TOGGLE_OPTIONS))
            self.aggregate_toggle.currentIndexChanged.connect(self._refresh_aggregates)
            self.aggregates_bar.addWidget(self.aggregate_toggle)

    def _build_controls_bar(self, root: QVBoxLayout):
        controls = QHBoxLayout()
        controls.setSpacing(8)
        root.addLayout(controls)

        controls.addWidget(QLabel("Mostra ultimi"))
        self.window_combo = QComboBox()
        for label, _ in self.TIME_WINDOWS:
            self.window_combo.addItem(label)
        self.window_combo.setCurrentIndex(self.DEFAULT_WINDOW_INDEX)
        self.window_combo.currentIndexChanged.connect(self._on_window_changed)
        controls.addWidget(self.window_combo)

        controls.addSpacing(20)
        controls.addStretch(1)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(self.SEARCH_PLACEHOLDER)
        self.search_edit.textChanged.connect(self._apply_filter)
        controls.addWidget(self.search_edit, stretch=1)

    def _build_table(self, root: QVBoxLayout):
        self.table = QTableView()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.doubleClicked.connect(self._on_row_double_clicked)
        self.configure_table(self.table)
        root.addWidget(self.table, stretch=1)

    def _build_bottom_bar(self, root: QVBoxLayout):
        bottom = QHBoxLayout()
        self.add_button = QPushButton(self.ADD_BUTTON_TEXT)
        self.add_button.clicked.connect(self._on_add_item)
        bottom.addStretch(1)
        bottom.addWidget(self.add_button)
        bottom.addStretch(1)
        root.addLayout(bottom)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888888;")
        root.addWidget(self.status_label)

    # ------------------------------------------------------------------
    # Pipeline reload
    # ------------------------------------------------------------------

    def _reload_data(self, window_days=None):
        t0 = time.perf_counter()
        items = self.fetch_items(window_days=window_days)
        t_query = time.perf_counter()
        rows = self.build_rows(items)
        t_build = time.perf_counter()

        self._source_model = self.create_table_model(rows)
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
            f"Caricati {len(rows)} {self.ITEM_LABEL_PLURAL} — "
            f"query: {(t_query - t0) * 1000:.0f} ms, "
            f"build righe: {(t_build - t_query) * 1000:.0f} ms, "
            f"setup view: {(t_view - t_build) * 1000:.0f} ms"
        )

    # ------------------------------------------------------------------
    # Eventi UI
    # ------------------------------------------------------------------

    def _on_window_changed(self):
        idx = self.window_combo.currentIndex()
        _, days = self.TIME_WINDOWS[idx]
        self._reload_data(window_days=days)
        if self._initial_item_id is not None:
            self._select_item(self._initial_item_id)

    def _apply_filter(self):
        if self._proxy is not None:
            self._proxy.setFilterFixedString(self.search_edit.text())

    def _refresh_aggregates(self):
        if not self._aggregate_labels:
            return
        toggle_value = (
            self.aggregate_toggle.currentText() if self.aggregate_toggle is not None else None
        )
        values = self.compute_aggregates(toggle_value) or {}
        for key, lbl in self._aggregate_labels.items():
            if key in values:
                lbl.setText(str(values[key]))

    def _on_row_double_clicked(self, proxy_index):
        if not proxy_index.isValid() or self._on_open_detail is None:
            return
        if self._proxy is None:
            return
        source_index = self._proxy.mapToSource(proxy_index)
        item_id = self.id_for_index(source_index)
        if item_id is not None:
            self._on_open_detail(item_id)

    def _on_add_item(self):
        new_item_id = self.open_creator_dialog()
        if new_item_id is None:
            return
        # Ricarica con la time-window correntemente selezionata e seleziona
        # il nuovo item, replicando la UX della legacy.
        idx = self.window_combo.currentIndex()
        _, days = self.TIME_WINDOWS[idx]
        self._reload_data(window_days=days)
        self._select_item(new_item_id)
        if self._on_open_detail is not None:
            self._on_open_detail(new_item_id)

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _select_item(self, item_id):
        if self._source_model is None or self._proxy is None:
            return
        source_row = self.row_for_id(item_id)
        if source_row < 0:
            return
        proxy_index = self._proxy.mapFromSource(self._source_model.index(source_row, 0))
        if not proxy_index.isValid():
            return
        self.table.selectRow(proxy_index.row())
        self.table.scrollTo(proxy_index, QAbstractItemView.PositionAtCenter)

    # ------------------------------------------------------------------
    # Hook da implementare nelle sottoclassi
    # ------------------------------------------------------------------

    def _setup_services(self, app_context: "AppContext"):
        """
        Lega qui i query/analyzer service del dominio. Eseguito prima di
        _build_ui e _reload_data, quindi gli attributi sono disponibili
        anche nei vari hook (fetch_items, compute_aggregates, ecc.).
        """
        return

    def fetch_items(self, window_days):
        """Carica la lista di item dal query service per la time-window."""
        raise NotImplementedError

    def build_rows(self, items):
        """Trasforma items in righe pronte per il source model."""
        raise NotImplementedError

    def create_table_model(self, rows):
        """Crea l'istanza del QAbstractTableModel concreto."""
        raise NotImplementedError

    def configure_table(self, table: QTableView):
        """Hook per applicare delegate, dimensioni custom, stylesheet, ecc."""
        return

    def compute_aggregates(self, toggle_value):
        """
        Restituisce dict[chiave_aggregato] -> stringa formattata.
        ``toggle_value`` e' il valore corrente di AGGREGATE_TOGGLE_OPTIONS,
        oppure None se la list view non ha un toggle.
        """
        return {}

    def open_creator_dialog(self):
        """
        Apre il dialog di creazione del dominio. Restituisce l'id del nuovo
        item (per attivarne il dettaglio) oppure None se annullato.
        """
        return None

    def id_for_index(self, source_index):
        """Estrae l'id dell'item dato un indice del source model."""
        raise NotImplementedError

    def row_for_id(self, item_id):
        """Trova la riga del source model corrispondente all'id (-1 se assente)."""
        raise NotImplementedError

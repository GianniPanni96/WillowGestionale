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

from PySide6.QtCore import QEvent, QObject, Qt, QSortFilterProxyModel
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from App_context import AppContext


# ----------------------------------------------------------------------
# Interaction helpers condivisi da tutte le QTListView
# ----------------------------------------------------------------------


from WarningServices.Warning_types import (
    SEVERITY_COLORS,
    WarningInfo,
    WarningSeverity,
    color_for_severity,
)


# Mantenuto come fallback (giallo INFO) per chi importa la costante
# dall'esterno; il delegate usa il colore per-riga letto dal modello.
WARNING_COLOR_HEX = SEVERITY_COLORS[WarningSeverity.INFO]


# Ruoli custom letti dal delegate per riconoscere le righe in warning e
# dipingerle col colore della severity.
ROLE_WARNING_TEXT = Qt.UserRole + 50
ROLE_WARNING_COLOR = Qt.UserRole + 51
ROLE_WARNING_INFO = Qt.UserRole + 52


class FirstColumnHoverDelegate(QStyledItemDelegate):
    """
    Delegate per la colonna "nome" (di default la 0) delle list view.

    Tre responsabilita' visive:
    - tinge il background al passaggio del mouse (hover);
    - dipinge un bordo sinistro colorato in base alla severity del
      warning (letto via ``ROLE_WARNING_TEXT`` + ``ROLE_WARNING_COLOR``);
    - lascia che il rendering standard del testo + decoration
      (icona warning) avvenga via ``super().paint()``.

    La logica di tracking della riga hoverata vive in
    ``_ListViewInteractionHandler``: qui ci si limita a leggerla.
    """

    WARNING_BORDER_PX = 4

    def __init__(self, table: "QTableView", parent=None):
        super().__init__(parent)
        self._table = table
        self._hovered_row = -1

    def set_hovered_row(self, row: int) -> None:
        if row != self._hovered_row:
            self._hovered_row = row
            self._table.viewport().update()

    def paint(self, painter, option, index):
        # Hover background.
        if index.isValid() and index.row() == self._hovered_row:
            color = QColor(option.palette.color(QPalette.Highlight))
            color.setAlpha(70)  # tinta leggera, non invadente
            painter.save()
            painter.fillRect(option.rect, color)
            painter.restore()

        # Rendering standard (testo + icona warning via Qt.DecorationRole).
        super().paint(painter, option, index)

        # Bordo sinistro colorato sulle righe con warning. Il colore
        # viene letto dal modello (ROLE_WARNING_COLOR) per riflettere la
        # severity; il giallo fallback resta sul WARNING_COLOR_HEX.
        if index.isValid() and index.data(ROLE_WARNING_TEXT):
            border_color_hex = index.data(ROLE_WARNING_COLOR) or WARNING_COLOR_HEX
            painter.save()
            rect = option.rect
            painter.fillRect(
                rect.left(),
                rect.top(),
                self.WARNING_BORDER_PX,
                rect.height(),
                QColor(border_color_hex),
            )
            painter.restore()


class _ListViewInteractionHandler(QObject):
    """
    Centralizza i comportamenti comuni di hover/tooltip delle QTListView.

    Responsabilità:
    - feedback visivo del cursore (pointer) e del background solo sulla
      colonna nome, attraverso ``FirstColumnHoverDelegate``;
    - reset dello stato al ``Leave`` del viewport;
    - tooltip "intelligente" su ``QEvent.ToolTip``: se il modello fornisce
      esplicitamente ``Qt.ToolTipRole`` lo si rispetta, altrimenti si
      mostra il valore ``Qt.DisplayRole`` per intero solo se la cella
      lo sta troncando (font metrics vs larghezza visiva).

    L'installazione passa per ``QTBaseListView._install_interaction_handler``,
    che può essere disabilitata o sovrascritta nelle sottoclassi.
    """

    def __init__(self, table: "QTableView", hover_column: int = 0, parent=None):
        super().__init__(parent)
        self._table = table
        self._hover_column = hover_column
        self._delegate = FirstColumnHoverDelegate(table, parent=table)

        table.setItemDelegateForColumn(hover_column, self._delegate)
        table.setMouseTracking(True)
        # entered() viene emesso quando il cursore entra in una cella
        # (richiede mouseTracking=True): è il punto giusto per aggiornare
        # riga hoverata e cursor shape.
        table.entered.connect(self._on_entered)
        table.viewport().installEventFilter(self)

    # Property utili a chi vuole estendere il comportamento.
    @property
    def delegate(self) -> FirstColumnHoverDelegate:
        return self._delegate

    @property
    def hover_column(self) -> int:
        return self._hover_column

    def _on_entered(self, index):
        if index.isValid() and index.column() == self._hover_column:
            self._delegate.set_hovered_row(index.row())
            self._table.viewport().setCursor(Qt.PointingHandCursor)
        else:
            self._delegate.set_hovered_row(-1)
            self._table.viewport().setCursor(Qt.ArrowCursor)

    def eventFilter(self, obj, event):
        if obj is self._table.viewport():
            etype = event.type()
            if etype == QEvent.Leave:
                self._delegate.set_hovered_row(-1)
                self._table.viewport().setCursor(Qt.ArrowCursor)
            elif etype == QEvent.ToolTip:
                if self._show_tooltip_for_event(event):
                    return True
        return super().eventFilter(obj, event)

    def _show_tooltip_for_event(self, event) -> bool:
        index = self._table.indexAt(event.pos())
        if not index.isValid():
            QToolTip.hideText()
            return True

        # Se il modello ha un suo tooltip esplicito, vince sempre.
        explicit = index.data(Qt.ToolTipRole)
        if explicit:
            QToolTip.showText(
                event.globalPos(), str(explicit), self._table.viewport(), self._table.visualRect(index)
            )
            return True

        text = index.data(Qt.DisplayRole)
        if text is None or text == "":
            QToolTip.hideText()
            return True
        text = str(text)

        rect = self._table.visualRect(index)
        fm = self._table.fontMetrics()
        # Margine empirico (padding cella ~6/8px per lato): se il testo
        # non ci sta, lo mostriamo per intero nel tooltip.
        available = rect.width() - 12
        if fm.horizontalAdvance(text) > available:
            QToolTip.showText(event.globalPos(), text, self._table.viewport(), rect)
        else:
            QToolTip.hideText()
        return True


class WarningSupportMixin:
    """
    Mixin riutilizzabile per i ``QAbstractTableModel`` delle list view.

    La mappa warnings ora trasporta oggetti ``WarningInfo`` (non piu'
    stringhe), che includono ``severity``, ``text``, ``type_key``,
    ``broken_field_key``. Il mixin espone:
    - ``Qt.ToolTipRole`` sulla colonna nome con il testo del warning;
    - ``Qt.DecorationRole`` sulla colonna nome con un'icona warning;
    - ``ROLE_WARNING_TEXT`` (testo);
    - ``ROLE_WARNING_COLOR`` (hex color associato alla severity);
    - ``ROLE_WARNING_INFO`` (l'intero ``WarningInfo``).

    Le sottoclassi devono:
    - definire ``WARNING_KEY_FIELD`` con il nome del campo del row dict
      usato come chiave dal warning service;
    - definire ``COL_NOME``;
    - chiamare ``self._init_warning_state()`` da ``__init__``;
    - includere ``self._warning_data_for_role(...)`` dentro ``data()``.

    La pipeline di ``QTBaseListView._reload_data`` chiama
    ``apply_warnings`` automaticamente dopo il fetch.
    """

    WARNING_KEY_FIELD: str = "name"

    def _init_warning_state(self):
        self._warnings_by_row_index: dict = {}
        self._warning_icon = None

    def _ensure_warning_icon(self):
        if self._warning_icon is None:
            try:
                from PySide6.QtWidgets import QApplication, QStyle
                style = QApplication.style()
                self._warning_icon = style.standardIcon(QStyle.SP_MessageBoxWarning)
            except Exception:
                self._warning_icon = None
        return self._warning_icon

    def apply_warnings(self, warnings: dict) -> None:
        """Aggancia la mappa ``warning_key -> WarningInfo`` alle righe
        del modello. Accetta anche stringhe (back-compat morbida): in
        tal caso le wrappa in ``WarningInfo`` con severity INFO."""
        self._warnings_by_row_index = {}
        if not warnings:
            self.layoutChanged.emit()
            return
        for i, row in enumerate(self._rows):
            key = row.get(self.WARNING_KEY_FIELD)
            if key not in warnings:
                continue
            value = warnings[key]
            if isinstance(value, WarningInfo):
                info = value
            else:
                info = WarningInfo(
                    type_key="_legacy",
                    severity=WarningSeverity.INFO,
                    text=str(value),
                )
            self._warnings_by_row_index[i] = info
        self.layoutChanged.emit()

    def warning_for_row(self, row_index: int):
        return self._warnings_by_row_index.get(row_index)

    def has_warning(self, row_index: int) -> bool:
        return row_index in self._warnings_by_row_index

    def _warning_data_for_role(self, index, role):
        """Restituisce il dato warning per il ruolo richiesto, o
        ``None`` se non pertinente. Da invocare dentro ``data()`` PRIMA
        del fallback ``return None``.

        Convenzione: warning visibile solo sulla colonna ``COL_NOME``
        (icona + bordo + tooltip)."""
        if not index.isValid():
            return None

        info = self.warning_for_row(index.row())
        if info is None:
            return None

        # ROLE_WARNING_TEXT/COLOR esposti su tutte le colonne (delegate
        # legge il colore della severity per ridipingere il bordo).
        if role == ROLE_WARNING_TEXT:
            return info.text
        if role == ROLE_WARNING_COLOR:
            return info.color
        if role == ROLE_WARNING_INFO:
            return info

        # Tooltip e icona solo sulla colonna nome.
        if index.column() != getattr(self, "COL_NOME", 0):
            return None
        if role == Qt.ToolTipRole:
            return info.text
        if role == Qt.DecorationRole:
            return self._ensure_warning_icon()
        return None


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
    """Se valorizzato (es. ('LORDI', 'NETTI')), mostra un combo sopra
    le card aggregate; il valore corrente viene passato a
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
    # Comportamento interattivo comune a tutte le list view.
    # Override-friendly: ogni sottoclasse può spegnere o cambiare un
    # singolo aspetto senza riscrivere l'intera pipeline.
    # ------------------------------------------------------------------

    HOVER_COLUMN = 0
    """Colonna su cui si concentra l'affordance di apertura del dettaglio
    (hover background + cursor pointer + double-click attivo).
    Imposta a un intero negativo per disabilitare completamente il
    meccanismo (in quel caso il double-click torna a essere globale)."""

    RESTRICT_DOUBLE_CLICK_TO_HOVER_COLUMN = True
    """Se True, il double-click sulle colonne diverse da ``HOVER_COLUMN``
    non apre il dettaglio (le altre celle diventano "non cliccabili")."""

    DISABLE_DEFAULT_ITEM_HOVER = True
    """Se True, sopprime via stylesheet il background di hover di default
    su tutte le celle, lasciando l'evidenza solo sulla colonna nome."""

    ELIDED_TOOLTIPS_ENABLED = True
    """Se True, l'event filter mostra un tooltip con il testo completo
    della cella quando il rendering lo sta troncando."""

    WARNING_SERVICE_ATTR: str = None
    """Nome dell'attributo (su ``self``) del warning service di dominio.
    Se valorizzato, ``collect_warnings`` chiama
    ``getattr(self, attr).collect_warnings_for_list(items)`` per produrre
    la mappa ``warning_key -> WarningInfo``. Lasciato a None se la list
    view non ha un dominio con warning."""

    WARNING_DOMAIN_KEY: str = None
    """Chiave del dominio nel file ``warnings_visibility.json`` (es.
    ``"fatture"``, ``"pagamenti"``). Se valorizzata, i warning di
    severity 2/3 disabilitati nella config vengono filtrati prima di
    essere applicati al modello. I sev 1 NON sono filtrabili."""

    AGGREGATE_TOOLTIP_BUILDER_ATTR: str = None
    """Nome dell'attributo (su ``app_context``) del tooltip builder
    degli aggregati. Se valorizzato, la pipeline di refresh aggregati
    invoca ``build_tooltips(toggle_value=…)`` (o lo passa con ``rows=``
    per i domini che lavorano sui rows) e applica il testo come tooltip
    alle card aggregate."""

    ROW_SELECTION_ENABLED = False
    """Se False, il click singolo non seleziona la riga (la tabella usa
    ``QAbstractItemView.NoSelection``). Tieni presente che senza
    selezione l'unico feedback "questa è la riga" è quello dell'hover
    sulla colonna nome.

    Lo si imposta a True nelle sottoclassi che hanno bisogno del concetto
    di "riga corrente" — ad esempio quelle che reagiscono alla
    selezione con un'azione contestuale."""

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
        self._aggregate_cards: dict = {}  # key -> QFrame (per setToolTip)
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
        root.setContentsMargins(10, 30, 10, 10)
        root.setSpacing(30)

        self._build_aggregates_bar(root)
        self._build_controls_bar(root)
        self._build_table(root)
        self._build_bottom_bar(root)

    def _build_aggregates_bar(self, root: QVBoxLayout):
        if not self.AGGREGATE_KEYS:
            return

        aggregate_section = QVBoxLayout()
        aggregate_section.setSpacing(8)
        root.addLayout(aggregate_section)

        if self.AGGREGATE_TOGGLE_OPTIONS:
            toggle_row = QHBoxLayout()
            toggle_row.setSpacing(8)
            self.aggregate_toggle = QComboBox()
            self.aggregate_toggle.addItems(list(self.AGGREGATE_TOGGLE_OPTIONS))
            self.aggregate_toggle.currentIndexChanged.connect(self._refresh_aggregates)
            toggle_row.addWidget(self.aggregate_toggle)
            toggle_row.addStretch(1)
            aggregate_section.addLayout(toggle_row)

        self.aggregates_bar = QHBoxLayout()
        self.aggregates_bar.setSpacing(10)
        aggregate_section.addLayout(self.aggregates_bar)

        for key in self.AGGREGATE_KEYS:
            card = QFrame()
            card.setFrameShape(QFrame.StyledPanel)
            card.setStyleSheet(
                "QFrame { background-color: palette(alternate-base); border-radius: 6px; }"
                "QLabel { color: palette(text); }"
            )
            box = QVBoxLayout(card)
            box.setContentsMargins(12, 8, 12, 8)
            title = QLabel(key)
            title.setAlignment(Qt.AlignCenter)
            title.setStyleSheet(
                "background-color: palette(highlight); "
                "color: palette(highlighted-text); "
                "padding: 4px; border-radius: 4px;"
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
            # Memorizziamo anche la card per poter applicare il tooltip
            # esplicativo (vedi ``_refresh_aggregate_tooltips``).
            self._aggregate_cards[key] = card
        self.aggregates_bar.addStretch(1)

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
        # Selezione disabilitabile a livello di sottoclasse: senza di
        # essa il click singolo non colora più la riga, mentre l'hover
        # sulla colonna nome continua a dare il feedback visivo.
        self.table.setSelectionMode(
            QAbstractItemView.SingleSelection
            if self.ROW_SELECTION_ENABLED
            else QAbstractItemView.NoSelection
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.doubleClicked.connect(self._on_row_double_clicked)

        # Lascio prima alle sottoclassi la libertà di applicare stylesheet,
        # delegate custom, dimensioni cell... Poi sovrappongo i wiring
        # comuni (hover/tooltip/disable hover default). In questo modo,
        # se una sottoclasse vuole tenersi un proprio delegate sulla
        # colonna nome, basta che imposti ``HOVER_COLUMN = -1`` o che
        # faccia override di ``_install_interaction_handler``.
        self.configure_table(self.table)
        self._install_interaction_handler()
        self._apply_common_table_stylesheet()

        root.addWidget(self.table, stretch=1)

    def _install_interaction_handler(self):
        """
        Installa l'handler comune di hover/tooltip/cursor sulla tabella.

        Override-point: se una sottoclasse vuole personalizzare la logica
        può restituire un'istanza alternativa (ad es. una sottoclasse di
        ``_ListViewInteractionHandler``) oppure non chiamare il super
        per disattivarlo del tutto.
        """
        self._interaction_handler = None
        if self.HOVER_COLUMN is None or self.HOVER_COLUMN < 0:
            return
        self._interaction_handler = _ListViewInteractionHandler(
            self.table, hover_column=self.HOVER_COLUMN, parent=self
        )

    def _apply_common_table_stylesheet(self):
        """
        Appende allo stylesheet della tabella le regole comuni (hover
        spento) senza calpestare quello impostato dalla sottoclasse in
        ``configure_table``. Override-friendly.
        """
        if not self.DISABLE_DEFAULT_ITEM_HOVER:
            return
        existing = self.table.styleSheet()
        # Tutte le celle non hoverable; la cella della HOVER_COLUMN viene
        # comunque ridipinta dal FirstColumnHoverDelegate, quindi resta
        # l'unica con feedback visivo.
        suppression = "\nQTableView::item:hover { background-color: transparent; }"
        self.table.setStyleSheet(existing + suppression)

    def _build_bottom_bar(self, root: QVBoxLayout):
        bottom = QHBoxLayout()
        self.add_button = QPushButton(self.ADD_BUTTON_TEXT)
        self.add_button.clicked.connect(self._on_add_item)
        bottom.addStretch(1)
        bottom.addWidget(self.add_button)
        bottom.addStretch(1)
        root.addLayout(bottom)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: palette(mid);")
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

        # Warnings: dict ``warning_key -> warning_text`` calcolato da un
        # warning service di dominio (override in collect_warnings). Il
        # dict viene applicato alle righe via apply_warnings sul model
        # cosi' la sottoclasse non deve duplicare la logica.
        self._warnings = self.collect_warnings(items) or {}

        self._source_model = self.create_table_model(rows)
        if hasattr(self._source_model, "apply_warnings"):
            self._source_model.apply_warnings(self._warnings)
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
        # Aggiorniamo anche i tooltip esplicativi (testo descrittivo del
        # calcolo) sulla stessa pipeline di refresh: cosi' quando i
        # valori cambiano, anche il dettaglio nel tooltip resta coerente.
        self._refresh_aggregate_tooltips(toggle_value)

    def _refresh_aggregate_tooltips(self, toggle_value):
        """Applica i tooltip descrittivi alle card aggregate, leggendo
        i testi dal builder di dominio indicato in
        ``AGGREGATE_TOOLTIP_BUILDER_ATTR``. Override-friendly: una
        sottoclasse puo' sovrascrivere questo metodo per logiche custom
        (es. domini che vogliono passare ``rows=`` al builder).
        """
        if not self._aggregate_cards or not self.AGGREGATE_TOOLTIP_BUILDER_ATTR:
            return
        builder = getattr(self.app_context, self.AGGREGATE_TOOLTIP_BUILDER_ATTR, None)
        if builder is None:
            return
        try:
            tooltips = builder.build_tooltips(toggle_value=toggle_value) or {}
        except Exception:
            tooltips = {}
        self._apply_aggregate_tooltips(tooltips)

    def _apply_aggregate_tooltips(self, tooltips: dict):
        for key, card in self._aggregate_cards.items():
            tip = tooltips.get(key)
            if tip:
                card.setToolTip(str(tip))

    def _on_row_double_clicked(self, proxy_index):
        if not proxy_index.isValid() or self._on_open_detail is None:
            return
        if self._proxy is None:
            return
        # Le celle fuori dalla colonna "nome" non sono cliccabili: solo
        # la colonna con l'affordance visiva apre il dettaglio. Le
        # sottoclassi possono spegnere questa restrizione impostando
        # RESTRICT_DOUBLE_CLICK_TO_HOVER_COLUMN = False.
        if (
            self.RESTRICT_DOUBLE_CLICK_TO_HOVER_COLUMN
            and self.HOVER_COLUMN is not None
            and self.HOVER_COLUMN >= 0
            and proxy_index.column() != self.HOVER_COLUMN
        ):
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
        # selectRow è no-op con NoSelection, ma lo evitiamo esplicitamente
        # per chiarezza — scrollTo resta utile in entrambe le modalità.
        if self.ROW_SELECTION_ENABLED:
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

    def collect_warnings(self, items) -> dict:
        """
        Restituisce ``dict[warning_key] -> WarningInfo`` per gli item
        correnti, applicando il filtro di visibilita' configurato in
        ``warnings_visibility.json`` (i sev 1 non sono filtrabili).

        Default: delega al warning service indicato in
        ``WARNING_SERVICE_ATTR``. Le sottoclassi possono fare override
        per logiche custom o per aggregare piu' service.
        """
        if not self.WARNING_SERVICE_ATTR:
            return {}
        service = getattr(self, self.WARNING_SERVICE_ATTR, None)
        if service is None or not hasattr(service, "collect_warnings_for_list"):
            return {}
        try:
            raw = service.collect_warnings_for_list(items) or {}
        except Exception:
            return {}
        return self._filter_warnings_by_visibility(raw)

    def _filter_warnings_by_visibility(self, warnings: dict) -> dict:
        """Rimuove i warning di severity 2/3 disabilitati dall'utente
        nella config. I sev 1 restano sempre."""
        if not warnings or not self.WARNING_DOMAIN_KEY:
            return warnings
        manager = getattr(self.app_context, "warnings_visibility_manager", None)
        if manager is None:
            return warnings

        filtered = {}
        for key, info in warnings.items():
            if not isinstance(info, WarningInfo):
                # Sicurezza: warning legacy come stringa -> tienilo.
                filtered[key] = info
                continue
            if info.severity == WarningSeverity.CONSISTENCY:
                filtered[key] = info
                continue
            if manager.is_warning_enabled(self.WARNING_DOMAIN_KEY, info.type_key):
                filtered[key] = info
        return filtered

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

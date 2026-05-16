"""
QAbstractTableModel del dominio Produzioni per QTProductionsViewH.

Stessa filosofia di QT_clients_table_model / QT_suppliers_table_model:
- ogni riga della lista produzioni viene pre-calcolata una sola volta
  (dati anagrafici + nome cliente + prezzo orario derivato);
- la QTableView interroga il modello solo per le celle visibili,
  riciclando le strutture di rendering;
- il QSortFilterProxyModel applica filtro testo e ordinamento sui
  dati esposti, senza ricalcolare nulla.
"""

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal
from PySide6.QtWidgets import QApplication, QComboBox, QStyle, QStyleOptionViewItem, QStyledItemDelegate


class _NoScrollComboBox(QComboBox):
    """QComboBox che ignora la rotellina del mouse a meno che non abbia il focus."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # StrongFocus: il widget acquisisce focus solo via click/Tab,
        # non per semplice hover — così hasFocus() riflette l'intenzione
        # reale dell'utente e non il semplice passaggio del cursore.
        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()

from Gestionale_Enums import ProductionStatus
from Model import DBClientsColumns, DBProductionsColumns
from QTViews.ListViews.QT_base_list_view import WarningSupportMixin


class ProductionsTableModel(WarningSupportMixin, QAbstractTableModel):
    """
    Modello dati produzioni per QTableView.

    Le colonne ricalcano quelle della Views/ListViews/Productions_view_H.py
    legacy. Il prezzo orario e' derivato al momento della build_rows
    tramite ProductionAnalyzerService.calculate_production_cost_per_hour.
    """

    HEADERS = [
        "NOME",
        "CLIENTE",
        "TIPOLOGIA\nPRODUZIONE",
        "TIPOLOGIA\nOUTPUT",
        "STATO",
        "DATA\nCONSEGNA",
        "TOTALE\nPREVENTIVO",
        "DURATA\nPRODUZIONE",
        "PREZZO\nORARIO",
    ]

    COL_NOME = 0
    COL_CLIENTE = 1
    COL_TIPO_PROD = 2
    COL_TIPO_OUT = 3
    COL_STATO = 4
    COL_DATA_CONSEGNA = 5
    COL_TOTALE = 6
    COL_DURATA = 7
    COL_PREZZO_ORARIO = 8

    ROLE_PRODUCTION_ID = Qt.UserRole + 2

    # Emesso dopo che lo stato di una produzione e' stato modificato
    # dalla cella combobox e persistito su DB. Lo intercetta la list
    # view per aggiornare aggregati e ridipingere la riga.
    status_committed = Signal(int, str)

    # Chiave usata dal ProductionWarningService (mappa NAME -> testo).
    WARNING_KEY_FIELD = "name"

    def __init__(self, rows, production_controller=None, parent=None):
        super().__init__(parent)
        self._rows = rows
        self._production_controller = production_controller
        self._init_warning_state()

    @classmethod
    def build_rows(cls, productions, clients_query_service, productions_analyzer_service):
        # Risoluzione nome cliente fatta in un solo passaggio caching gli
        # id gia' visti — evita di ripetere fetch_client_by_id ogni volta
        # che lo stesso cliente compare nella lista.
        client_name_cache: dict = {}

        def _resolve_client_name(client_id):
            if client_id in client_name_cache:
                return client_name_cache[client_id]
            client = clients_query_service.retrieve_client_map_by_id(client_id)
            name = client[DBClientsColumns.NAME.value] if client else "Cliente non trovato"
            client_name_cache[client_id] = name
            return name

        rows = []
        for production in productions:
            production_id = production[DBProductionsColumns.ID.value]
            client_id = production.get(DBProductionsColumns.CLIENT_ID.value)
            client_name = _resolve_client_name(client_id) if client_id is not None else ""

            try:
                prezzo_orario = productions_analyzer_service.calculate_production_cost_per_hour(production_id)
            except Exception:
                prezzo_orario = -1

            if prezzo_orario == -1:
                prezzo_orario = 0.0

            rows.append(
                {
                    "id": production_id,
                    "name": production.get(DBProductionsColumns.NAME.value, "") or "",
                    "client_name": client_name,
                    "tipologia_produzione": production.get(DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value, "") or "",
                    "tipologia_output": production.get(DBProductionsColumns.TIPOLOGIA_OUTPUT.value, "") or "",
                    "stato": production.get(DBProductionsColumns.STATO.value, "") or "",
                    "data_consegna": production.get(DBProductionsColumns.END_DATE.value, "") or "",
                    "totale_preventivo": cls._safe_float(production.get(DBProductionsColumns.TOTALE_PREVENTIVO.value)),
                    "durata": cls._safe_float(production.get(DBProductionsColumns.HOURS.value)),
                    "prezzo_orario": cls._safe_float(prezzo_orario),
                    "created_at": production.get(DBProductionsColumns.CREATED_AT.value, "") or "",
                    "updated_at": production.get(DBProductionsColumns.UPDATED_AT.value, "") or "",
                }
            )
        return rows

    # ------------------------------------------------------------------
    # API QAbstractTableModel
    # ------------------------------------------------------------------

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == self.COL_NOME:
                return row["name"]
            if col == self.COL_CLIENTE:
                return row["client_name"]
            if col == self.COL_TIPO_PROD:
                return row["tipologia_produzione"]
            if col == self.COL_TIPO_OUT:
                return row["tipologia_output"]
            if col == self.COL_STATO:
                return row["stato"]
            if col == self.COL_DATA_CONSEGNA:
                return row["data_consegna"]
            if col == self.COL_TOTALE:
                return f"{round(row['totale_preventivo'], 2)} €"
            if col == self.COL_DURATA:
                return f"{round(row['durata'], 2)} h"
            if col == self.COL_PREZZO_ORARIO:
                return f"{round(row['prezzo_orario'], 2)} €/h"

        if role == Qt.UserRole:
            if col == self.COL_NOME:
                return row["name"].lower() if row["name"] else ""
            if col == self.COL_CLIENTE:
                return row["client_name"].lower() if row["client_name"] else ""
            if col == self.COL_TIPO_PROD:
                return row["tipologia_produzione"].lower() if row["tipologia_produzione"] else ""
            if col == self.COL_TIPO_OUT:
                return row["tipologia_output"].lower() if row["tipologia_output"] else ""
            if col == self.COL_STATO:
                return row["stato"]
            if col == self.COL_DATA_CONSEGNA:
                return row["data_consegna"]
            if col == self.COL_TOTALE:
                return row["totale_preventivo"]
            if col == self.COL_DURATA:
                return row["durata"]
            if col == self.COL_PREZZO_ORARIO:
                return row["prezzo_orario"]
            return self.data(index, Qt.DisplayRole)

        if role == self.ROLE_PRODUCTION_ID:
            return row["id"]

        if role == Qt.TextAlignmentRole:
            if col == self.COL_NOME:
                return int(Qt.AlignVCenter | Qt.AlignLeft)
            return int(Qt.AlignCenter)

        warning_data = self._warning_data_for_role(index, role)
        if warning_data is not None:
            return warning_data

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.HEADERS[section]
        return None

    def flags(self, index):
        base = super().flags(index)
        if index.isValid() and index.column() == self.COL_STATO:
            return base | Qt.ItemIsEditable
        return base

    def setData(self, index, value, role=Qt.EditRole):
        # Persistenza inline dello stato. Chiamato dal delegate dopo che
        # l'utente ha scelto una voce dal combobox della cella STATO.
        if not index.isValid() or role != Qt.EditRole:
            return False
        if index.column() != self.COL_STATO:
            return False

        row = self._rows[index.row()]
        new_status = "" if value is None else str(value).strip()
        if not new_status or new_status == row["stato"]:
            return False

        # Senza controller il modello e' read-only: la persistenza non
        # viene tentata (utile in test o se la view non passa il
        # controller).
        if self._production_controller is not None:
            success, _ = self._production_controller.update_specific_production_data(
                row["id"], {DBProductionsColumns.STATO.value: new_status}
            )
            if not success:
                return False

        row["stato"] = new_status
        self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
        self.status_committed.emit(row["id"], new_status)
        return True

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def find_row_by_production_id(self, production_id) -> int:
        for i, row in enumerate(self._rows):
            if row["id"] == production_id:
                return i
        return -1

    def rows(self) -> list:
        return self._rows

    @staticmethod
    def _safe_float(value, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default


class ProductionStatusDelegate(QStyledItemDelegate):
    """
    Delegate per la colonna STATO della list view produzioni.

    Mostra un QComboBox sempre visibile (la view chiama
    openPersistentEditor sulle celle della colonna), popolato con i
    valori di ProductionStatus. Alla selezione di una nuova voce
    l'editor emette ``commitData``, che a sua volta invoca
    ``setData`` sul ProductionsTableModel: e' li' che avviene la
    persistenza tramite ProductionController.update_specific_production_data
    e l'emissione di ``status_committed``, il segnale che la list view
    aggancia per aggiornare gli aggregati.

    Usiamo ``activated`` invece di ``currentIndexChanged`` per evitare
    il commit spurioso che si avrebbe quando il delegate inizializza
    l'editor con setEditorData (``activated`` scatta solo su scelta
    esplicita dell'utente).
    """

    def createEditor(self, parent, option, index):
        editor = _NoScrollComboBox(parent)
        editor.addItems([s.value for s in ProductionStatus])
        editor.activated.connect(lambda _i, e=editor: self.commitData.emit(e))
        editor.setStyleSheet("_NoScrollComboBox {border: 2px solid palette(highlight); border-radius: 6px; }")
        return editor

    def paint(self, painter, option, index):
        # super().paint() chiama internamente initStyleOption(opt, index)
        # che rilegge Qt.DisplayRole e sovrascrive opt.text, vanificando
        # qualsiasi azzeramento fatto prima.  Replica del comportamento di
        # QStyledItemDelegate.paint() senza quel secondo sovrascrittura:
        # 1) initStyleOption popola opt (background, stato selezione, ecc.)
        # 2) azzeriamo opt.text per non disegnare il testo della cella
        # 3) passiamo opt direttamente allo stile — bypassa il secondo
        #    initStyleOption che avrebbe riscritto il testo.
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        widget = option.widget
        style = widget.style() if widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, widget)

    def setEditorData(self, editor: QComboBox, index):
        value = index.data(Qt.DisplayRole)
        if value is None:
            return
        i = editor.findText(str(value))
        if i >= 0:
            editor.setCurrentIndex(i)

    def setModelData(self, editor: QComboBox, model, index):
        model.setData(index, editor.currentText(), Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

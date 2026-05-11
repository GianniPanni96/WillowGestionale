"""
QAbstractTableModel del dominio Fornitori per QTSuppliersViewH.

Stessa filosofia di QT_clients_table_model:
- ogni riga della lista fornitori viene pre-calcolata una sola volta
  (nome + dati aggregati restituiti da SupplierAnalyzerService);
- la QTableView interroga il modello solo per le celle visibili,
  riciclando le strutture di rendering;
- il QSortFilterProxyModel applica filtro testo e ordinamento sui
  dati esposti, senza ricalcolare nulla.
"""

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex

from Gestionale_Enums import SupplierAggregateData
from Model import DBSuppliersColumns


class SuppliersTableModel(QAbstractTableModel):
    """
    Modello dati fornitori per QTableView.

    Le colonne ricalcano quelle della Views/ListViews/Suppliers_view_H.py
    legacy. I dati aggregati sono calcolati al momento della build_rows
    tramite SupplierAnalyzerService.construct_supplier_map_aggregate_data,
    in linea con ``ViewUtils.create_extractor_for_suppliers``.
    """

    HEADERS = [
        "NOME",
        "PARTITA IVA",
        "TOT. SPESE",
        "# SPESE",
        "SPESA MEDIA",
        "NOTE",
        "CONTATTO",
    ]

    COL_NOME = 0
    COL_PARTITA_IVA = 1
    COL_TOT_SPESE = 2
    COL_NUM_SPESE = 3
    COL_SPESA_MEDIA = 4
    COL_NOTE = 5
    COL_CONTATTO = 6

    ROLE_SUPPLIER_ID = Qt.UserRole + 2

    def __init__(self, rows, parent=None):
        super().__init__(parent)
        self._rows = rows

    @classmethod
    def build_rows(cls, suppliers, suppliers_analyzer_service):
        rows = []
        for supplier in suppliers:
            supplier_id = supplier[DBSuppliersColumns.ID.value]
            name = supplier.get(DBSuppliersColumns.NAME.value, "") or ""
            partita_iva = supplier.get(DBSuppliersColumns.PARTITA_IVA.value, "") or ""
            note = supplier.get(DBSuppliersColumns.NOTE.value, "") or ""
            contatto = supplier.get(DBSuppliersColumns.CONTATTO.value, "") or ""

            try:
                aggregate = suppliers_analyzer_service.construct_supplier_map_aggregate_data(supplier_id)
            except Exception:
                aggregate = {}

            rows.append(
                {
                    "id": supplier_id,
                    "name": name,
                    "partita_iva": partita_iva,
                    "tot_spese": cls._safe_float(aggregate.get(SupplierAggregateData.TOT_SPESE.value)),
                    "num_spese": cls._safe_int(aggregate.get(SupplierAggregateData.NUM_SPESE.value)),
                    "media_spese": cls._safe_float(aggregate.get(SupplierAggregateData.MEDIA_SPESE.value)),
                    "note": note,
                    "contatto": contatto,
                    "created_at": supplier.get(DBSuppliersColumns.CREATED_AT.value, "") or "",
                    "updated_at": supplier.get(DBSuppliersColumns.UPDATED_AT.value, "") or "",
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
            if col == self.COL_PARTITA_IVA:
                return row["partita_iva"]
            if col == self.COL_TOT_SPESE:
                return f"{round(row['tot_spese'], 2)} €"
            if col == self.COL_NUM_SPESE:
                return str(row["num_spese"])
            if col == self.COL_SPESA_MEDIA:
                return f"{round(row['media_spese'], 2)} €"
            if col == self.COL_NOTE:
                return row["note"]
            if col == self.COL_CONTATTO:
                return row["contatto"]

        if role == Qt.UserRole:
            if col == self.COL_NOME:
                return row["name"].lower() if row["name"] else ""
            if col == self.COL_PARTITA_IVA:
                return row["partita_iva"]
            if col == self.COL_TOT_SPESE:
                return row["tot_spese"]
            if col == self.COL_NUM_SPESE:
                return row["num_spese"]
            if col == self.COL_SPESA_MEDIA:
                return row["media_spese"]
            if col == self.COL_NOTE:
                return row["note"].lower() if row["note"] else ""
            if col == self.COL_CONTATTO:
                return row["contatto"]
            return self.data(index, Qt.DisplayRole)

        if role == self.ROLE_SUPPLIER_ID:
            return row["id"]

        if role == Qt.TextAlignmentRole:
            if col == self.COL_NOME:
                return int(Qt.AlignVCenter | Qt.AlignLeft)
            return int(Qt.AlignCenter)

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.HEADERS[section]
        return None

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def find_row_by_supplier_id(self, supplier_id) -> int:
        for i, row in enumerate(self._rows):
            if row["id"] == supplier_id:
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

    @staticmethod
    def _safe_int(value, default: int = 0) -> int:
        try:
            if value is None:
                return default
            return int(value)
        except (TypeError, ValueError):
            return default

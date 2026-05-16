"""
QAbstractTableModel del dominio Clienti per QTClientsViewH.

Stessa filosofia di QT_invoices_table_model:
- ogni riga della lista clienti viene pre-calcolata una sola volta
  (nome + dati aggregati restituiti da ClientAnalyzerService);
- la QTableView interroga il modello solo per le celle visibili,
  riciclando le strutture di rendering;
- il QSortFilterProxyModel applica filtro testo e ordinamento sui
  dati esposti, senza ricalcolare nulla.
"""

from typing import Optional

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex

from Gestionale_Enums import ClientsAggregateData
from Model import DBClientsColumns


class ClientsTableModel(QAbstractTableModel):
    """
    Modello dati clienti per QTableView.

    I dati aggregati sono calcolati al momento della build_rows tramite
    ClientAnalyzerService.construct_client_map_aggregate_data, in modo
    coerente con `ViewUtils.create_extractor_for_clients` legacy.
    """

    HEADERS = [
        "NOME",
        "TOT. ENTRATE",
        "# FATTURE",
        "FATTURA MEDIA",
        "TOT. CREDITI",
        "TOT. RIMBORSI",
        "PAGAM. ORARIO\nMEDIO",
        "TOT. GIORNI\nRITARDO",
        "MEDIA RITARDO",
    ]

    COL_NOME = 0
    COL_TOT_ENTRATE = 1
    COL_NUM_FATTURE = 2
    COL_FATTURA_MEDIA = 3
    COL_TOT_CREDITI = 4
    COL_TOT_RIMBORSI = 5
    COL_PAGAM_ORARIO = 6
    COL_GIORNI_RIT = 7
    COL_MEDIA_RIT = 8

    ROLE_CLIENT_ID = Qt.UserRole + 2

    def __init__(self, rows, parent=None):
        super().__init__(parent)
        self._rows = rows
        # Tooltip degli header di tabella, popolati dalla view via
        # ``set_header_tooltips`` con i testi del tooltip builder. Vive
        # qui (nel model) perche' Qt richiede che ``headerData`` ritorni
        # il valore per Qt.ToolTipRole.
        self._header_tooltips: dict = {}

    def set_header_tooltips(self, tooltips: dict) -> None:
        """Accetta sia ``dict[header_label, testo]`` sia
        ``dict[col_index, testo]``. La normalizzazione interna mappa
        tutto a ``col_index`` per il lookup in ``headerData``."""
        normalized = {}
        for k, v in (tooltips or {}).items():
            if isinstance(k, int):
                normalized[k] = v
            else:
                # key e' l'header label: lo cerchiamo in HEADERS.
                try:
                    idx = self.HEADERS.index(k)
                    normalized[idx] = v
                except ValueError:
                    continue
        self._header_tooltips = normalized
        # Notifica la view che gli header sono cambiati, cosi' che il
        # rendering aggiorni i tooltip.
        self.headerDataChanged.emit(Qt.Horizontal, 0, max(0, len(self.HEADERS) - 1))

    @classmethod
    def build_rows(cls, clients, clients_analyzer_service):
        rows = []
        for client in clients:
            client_id = client[DBClientsColumns.ID.value]
            name = client.get(DBClientsColumns.NAME.value, "") or ""

            try:
                aggregate = clients_analyzer_service.construct_client_map_aggregate_data(
                    client_id, year=-1
                )
            except Exception:
                aggregate = {}

            rows.append(
                {
                    "id": client_id,
                    "name": name,
                    "tot_entrate": cls._safe_float(aggregate.get(ClientsAggregateData.TOT_ENTRATE.value)),
                    "num_fatture": cls._safe_int(aggregate.get(ClientsAggregateData.NUM_FATTURE.value)),
                    "media_fatture": cls._safe_float(aggregate.get(ClientsAggregateData.MEDIA_FATTURE.value)),
                    "tot_crediti": cls._safe_float(aggregate.get(ClientsAggregateData.TOT_CREDITI.value)),
                    "tot_rimborsi": cls._safe_float(aggregate.get(ClientsAggregateData.TOT_RIMBORSI.value)),
                    "pagam_orario": cls._safe_float(aggregate.get(ClientsAggregateData.PAGAM_ORARIO_MEDIO.value)),
                    "giorni_rit": cls._safe_int(aggregate.get(ClientsAggregateData.TOT_GIORNI_RIT.value)),
                    "media_rit": cls._safe_float(aggregate.get(ClientsAggregateData.MEDIA_RITARDO.value)),
                    "created_at": client.get(DBClientsColumns.CREATED_AT.value, "") or "",
                    "updated_at": client.get(DBClientsColumns.UPDATED_AT.value, "") or "",
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
            if col == self.COL_TOT_ENTRATE:
                return f"{round(row['tot_entrate'], 2)} €"
            if col == self.COL_NUM_FATTURE:
                return str(row["num_fatture"])
            if col == self.COL_FATTURA_MEDIA:
                return f"{round(row['media_fatture'], 2)} €"
            if col == self.COL_TOT_CREDITI:
                return f"{round(row['tot_crediti'], 2)} €"
            if col == self.COL_TOT_RIMBORSI:
                return f"{round(row['tot_rimborsi'], 2)} €"
            if col == self.COL_PAGAM_ORARIO:
                return f"{round(row['pagam_orario'], 2)} €/h"
            if col == self.COL_GIORNI_RIT:
                return str(row["giorni_rit"])
            if col == self.COL_MEDIA_RIT:
                return f"{round(row['media_rit'], 2)} GG"

        if role == Qt.UserRole:
            if col == self.COL_NOME:
                return row["name"].lower() if row["name"] else ""
            if col == self.COL_TOT_ENTRATE:
                return row["tot_entrate"]
            if col == self.COL_NUM_FATTURE:
                return row["num_fatture"]
            if col == self.COL_FATTURA_MEDIA:
                return row["media_fatture"]
            if col == self.COL_TOT_CREDITI:
                return row["tot_crediti"]
            if col == self.COL_TOT_RIMBORSI:
                return row["tot_rimborsi"]
            if col == self.COL_PAGAM_ORARIO:
                return row["pagam_orario"]
            if col == self.COL_GIORNI_RIT:
                return row["giorni_rit"]
            if col == self.COL_MEDIA_RIT:
                return row["media_rit"]
            return self.data(index, Qt.DisplayRole)

        if role == self.ROLE_CLIENT_ID:
            return row["id"]

        if role == Qt.TextAlignmentRole:
            if col == self.COL_NOME:
                return int(Qt.AlignVCenter | Qt.AlignLeft)
            return int(Qt.AlignCenter)

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return self.HEADERS[section]
            if role == Qt.ToolTipRole:
                return self._header_tooltips.get(section)
        return None

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def find_row_by_client_id(self, client_id) -> int:
        for i, row in enumerate(self._rows):
            if row["id"] == client_id:
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

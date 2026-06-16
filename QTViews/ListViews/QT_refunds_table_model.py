"""
QAbstractTableModel del dominio Rimborsi per QTRefundsViewH.

Stessa filosofia di QT_payments_table_model: ogni riga della lista
rimborsi viene pre-calcolata una sola volta (nome cliente / conto
risolti dai loro id) e la QTableView interroga il modello solo per le
celle visibili. Il QSortFilterProxyModel applica filtro testo e
ordinamento sui dati esposti, senza ricalcolare nulla.
"""

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex

from Gestionale_Enums import (
    DBAccountsColumns,
    DBClientsColumns,
    DBRefundsColumns,
)
from QTViews.ListViews.QT_base_list_view import WarningSupportMixin


class RefundsTableModel(WarningSupportMixin, QAbstractTableModel):
    """
    Modello dati rimborsi per QTableView.

    Le colonne ricalcano quelle di Views/ListViews/Refunds_view_H.py
    legacy: NOME, CLIENTE, TOTALE, DATA EMISSIONE, CONTO CORRENTE.
    """

    HEADERS = [
        "NOME",
        "CLIENTE",
        "TOTALE",
        "DATA\nEMISSIONE",
        "CONTO\nCORRENTE",
    ]

    COL_NOME = 0
    COL_CLIENTE = 1
    COL_TOTALE = 2
    COL_DATA = 3
    COL_CONTO = 4

    ROLE_REFUND_ID = Qt.UserRole + 2

    # Chiave usata dal RefundWarningService (mappa REFUND_NAME -> testo).
    WARNING_KEY_FIELD = "name"

    def __init__(self, rows, parent=None):
        super().__init__(parent)
        self._rows = rows
        self._init_warning_state()

    # ------------------------------------------------------------------
    # Build rows
    # ------------------------------------------------------------------

    @classmethod
    def build_rows(cls, refunds, clients_query_service, accounts_query_service):
        # Cache su client_id / account_id: evita di richiamare lo stesso
        # retrieve per ogni rimborso quando cliente/conto sono condivisi.
        client_cache: dict = {}
        account_cache: dict = {}

        def _client(client_id):
            if client_id in client_cache:
                return client_cache[client_id]
            client = clients_query_service.retrieve_client_map_by_id(client_id) if client_id is not None else None
            client_cache[client_id] = client
            return client

        def _account(account_id):
            if account_id in account_cache:
                return account_cache[account_id]
            account = accounts_query_service.retrieve_account_map_by_id(account_id) if account_id is not None else None
            account_cache[account_id] = account
            return account

        rows = []
        for refund in refunds:
            refund_id = refund[DBRefundsColumns.ID.value]
            client = _client(refund.get(DBRefundsColumns.CLIENT_ID.value))
            account = _account(refund.get(DBRefundsColumns.CONTO_ID.value))

            rows.append(
                {
                    "id": refund_id,
                    "name": refund.get(DBRefundsColumns.REFUND_NAME.value, "") or "",
                    "client_name": client[DBClientsColumns.NAME.value] if client else "Cliente non trovato",
                    "amount": cls._safe_float(refund.get(DBRefundsColumns.REFUND_AMOUNT.value)),
                    "refund_date": refund.get(DBRefundsColumns.REFUND_DATE.value, "") or "",
                    "account_name": account[DBAccountsColumns.NAME.value] if account else "Conto non trovato",
                    "created_at": refund.get(DBRefundsColumns.CREATED_AT.value, "") or "",
                    "updated_at": refund.get(DBRefundsColumns.UPDATED_AT.value, "") or "",
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
            if col == self.COL_TOTALE:
                return f"{row['amount']:.2f} €"
            if col == self.COL_DATA:
                return row["refund_date"]
            if col == self.COL_CONTO:
                return row["account_name"]

        if role == Qt.UserRole:
            if col == self.COL_NOME:
                return row["name"].lower() if row["name"] else ""
            if col == self.COL_CLIENTE:
                return row["client_name"].lower() if row["client_name"] else ""
            if col == self.COL_TOTALE:
                return row["amount"]
            if col == self.COL_DATA:
                return row["refund_date"]
            if col == self.COL_CONTO:
                return row["account_name"].lower() if row["account_name"] else ""
            return self.data(index, Qt.DisplayRole)

        if role == self.ROLE_REFUND_ID:
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

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def find_row_by_refund_id(self, refund_id) -> int:
        for i, row in enumerate(self._rows):
            if row["id"] == refund_id:
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

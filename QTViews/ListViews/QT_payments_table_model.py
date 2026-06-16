"""
QAbstractTableModel del dominio Pagamenti per QTPaymentsViewH.

Stessa filosofia di QT_productions_table_model / QT_suppliers_table_model:
- ogni riga della lista pagamenti viene pre-calcolata una sola volta
  (nome pagamento + cliente / produzione / fattura / conto risolti dai
  loro id);
- la QTableView interroga il modello solo per le celle visibili,
  riciclando le strutture di rendering;
- il QSortFilterProxyModel applica filtro testo e ordinamento sui
  dati esposti, senza ricalcolare nulla.
"""

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex

from Gestionale_Enums import (
    DBAccountsColumns,
    DBClientsColumns,
    DBInvoicesColumns,
    DBPaymentsColumns,
    DBProductionsColumns,
)
from QTViews.ListViews.QT_base_list_view import WarningSupportMixin


class PaymentsTableModel(WarningSupportMixin, QAbstractTableModel):
    """
    Modello dati pagamenti per QTableView.

    Le colonne ricalcano quelle della Views/ListViews/Payments_view_H.py
    legacy: NOME, CLIENTE, PRODUZIONE, FATTURA, TOTALE, DATA
    CONTABILIZZAZIONE, RATA FATTURA, CONTO CORRENTE.
    """

    HEADERS = [
        "NOME",
        "CLIENTE",
        "PRODUZIONE",
        "FATTURA",
        "TOTALE",
        "DATA\nCONTABILIZZAZIONE",
        "RATA\nFATTURA",
        "CONTO\nCORRENTE",
    ]

    COL_NOME = 0
    COL_CLIENTE = 1
    COL_PRODUZIONE = 2
    COL_FATTURA = 3
    COL_TOTALE = 4
    COL_DATA = 5
    COL_RATA = 6
    COL_CONTO = 7

    ROLE_PAYMENT_ID = Qt.UserRole + 2

    # Chiave usata dal PaymentWarningService (mappa PAYMENT_NAME -> testo).
    WARNING_KEY_FIELD = "name"

    def __init__(self, rows, parent=None):
        super().__init__(parent)
        self._rows = rows
        self._init_warning_state()

    # ------------------------------------------------------------------
    # Build rows
    # ------------------------------------------------------------------

    @classmethod
    def build_rows(
        cls,
        payments,
        invoices_query_service,
        clients_query_service,
        productions_query_service,
        accounts_query_service,
    ):
        # Cache per evitare di richiamare lo stesso retrieve per ogni
        # pagamento — fattura, cliente, produzione e conto vengono
        # condivisi tra pagamenti diversi.
        invoice_cache: dict = {}
        client_cache: dict = {}
        production_cache: dict = {}
        account_cache: dict = {}

        def _invoice(invoice_id):
            if invoice_id in invoice_cache:
                return invoice_cache[invoice_id]
            invoice = invoices_query_service.retrieve_invoice_map_by_id(invoice_id) if invoice_id is not None else None
            invoice_cache[invoice_id] = invoice
            return invoice

        def _client(client_id):
            if client_id in client_cache:
                return client_cache[client_id]
            client = clients_query_service.retrieve_client_map_by_id(client_id) if client_id is not None else None
            client_cache[client_id] = client
            return client

        def _production(production_id):
            if production_id in production_cache:
                return production_cache[production_id]
            production = productions_query_service.retrieve_production_map_by_id(production_id) if production_id is not None else None
            production_cache[production_id] = production
            return production

        def _account(account_id):
            if account_id in account_cache:
                return account_cache[account_id]
            account = accounts_query_service.retrieve_account_map_by_id(account_id) if account_id is not None else None
            account_cache[account_id] = account
            return account

        rows = []
        for payment in payments:
            payment_id = payment[DBPaymentsColumns.ID.value]
            invoice = _invoice(payment.get(DBPaymentsColumns.INVOICE_ID.value))
            client = _client(invoice[DBInvoicesColumns.ID_CLIENTE.value]) if invoice else None
            production = _production(invoice[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value]) if invoice else None
            account = _account(payment.get(DBPaymentsColumns.CONTO_ID.value))

            rows.append(
                {
                    "id": payment_id,
                    "name": payment.get(DBPaymentsColumns.PAYMENT_NAME.value, "") or "",
                    "client_name": client[DBClientsColumns.NAME.value] if client else "Cliente non trovato",
                    "production_name": production[DBProductionsColumns.NAME.value] if production else "Produzione non trovata",
                    "invoice_name": invoice[DBInvoicesColumns.NUMERO_FATTURA.value] if invoice else "Fattura non trovata",
                    "amount": cls._safe_float(payment.get(DBPaymentsColumns.PAYMENT_AMOUNT.value)),
                    "payment_date": payment.get(DBPaymentsColumns.PAYMENT_DATE.value, "") or "",
                    "linked_rata": str(payment.get(DBPaymentsColumns.LINKED_RATA.value, "") or ""),
                    "account_name": account[DBAccountsColumns.NAME.value] if account else "Conto non trovato",
                    "created_at": payment.get(DBPaymentsColumns.CREATED_AT.value, "") or "",
                    "updated_at": payment.get(DBPaymentsColumns.UPDATED_AT.value, "") or "",
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
            if col == self.COL_PRODUZIONE:
                return row["production_name"]
            if col == self.COL_FATTURA:
                return row["invoice_name"]
            if col == self.COL_TOTALE:
                return f"{row['amount']:.2f} €"
            if col == self.COL_DATA:
                return row["payment_date"]
            if col == self.COL_RATA:
                return row["linked_rata"]
            if col == self.COL_CONTO:
                return row["account_name"]

        if role == Qt.UserRole:
            if col == self.COL_NOME:
                return row["name"].lower() if row["name"] else ""
            if col == self.COL_CLIENTE:
                return row["client_name"].lower() if row["client_name"] else ""
            if col == self.COL_PRODUZIONE:
                return row["production_name"].lower() if row["production_name"] else ""
            if col == self.COL_FATTURA:
                return row["invoice_name"].lower() if row["invoice_name"] else ""
            if col == self.COL_TOTALE:
                return row["amount"]
            if col == self.COL_DATA:
                return row["payment_date"]
            if col == self.COL_RATA:
                return row["linked_rata"]
            if col == self.COL_CONTO:
                return row["account_name"].lower() if row["account_name"] else ""
            return self.data(index, Qt.DisplayRole)

        if role == self.ROLE_PAYMENT_ID:
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

    def find_row_by_payment_id(self, payment_id) -> int:
        for i, row in enumerate(self._rows):
            if row["id"] == payment_id:
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

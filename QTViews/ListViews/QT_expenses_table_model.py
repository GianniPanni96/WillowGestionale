"""
QAbstractTableModel del dominio Spese per QTExpensesViewH.

Stessa filosofia di QT_payments_table_model / QT_refunds_table_model:
ogni riga della lista spese viene pre-calcolata una sola volta (nome
fornitore / utente di deduzione / conto risolti dai loro id) e la
QTableView interroga il modello solo per le celle visibili. Il
QSortFilterProxyModel applica filtro testo e ordinamento sui dati
esposti.
"""

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex

from Gestionale_Enums import (
    DBAccountsColumns,
    DBExpensesColumns,
    DBSuppliersColumns,
    DBUsersColumns,
)
from QTViews.ListViews.QT_base_list_view import WarningSupportMixin


class ExpensesTableModel(WarningSupportMixin, QAbstractTableModel):
    """
    Modello dati spese per QTableView.

    Le colonne ricalcano quelle di Views/ListViews/Expenses_view_H.py
    legacy: NOME, FORNITORE, NETTO, LORDO, CATEGORIA, DATA EMISSIONE,
    DEDUCIBILE, DEDUZIONE A CARICO DI, CONTO CORRENTE.
    """

    HEADERS = [
        "NOME",
        "FORNITORE",
        "NETTO",
        "LORDO",
        "CATEGORIA",
        "DATA\nEMISSIONE",
        "DEDUCIBILE",
        "DEDUZIONE A\nCARICO DI",
        "CONTO\nCORRENTE",
    ]

    COL_NOME = 0
    COL_FORNITORE = 1
    COL_NETTO = 2
    COL_LORDO = 3
    COL_CATEGORIA = 4
    COL_DATA = 5
    COL_DEDUCIBILE = 6
    COL_UTENTE = 7
    COL_CONTO = 8

    ROLE_EXPENSE_ID = Qt.UserRole + 2

    # Chiave usata dall'ExpenseWarningService (mappa NOME -> testo).
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
        expenses,
        suppliers_query_service,
        user_query_service,
        accounts_query_service,
    ):
        # Cache su supplier_id / user_id / account_id: evita di richiamare
        # lo stesso retrieve per ogni spesa quando l'entita' e' condivisa.
        supplier_cache: dict = {}
        user_cache: dict = {}
        account_cache: dict = {}

        def _supplier(supplier_id):
            if supplier_id in supplier_cache:
                return supplier_cache[supplier_id]
            supplier = (
                suppliers_query_service.retrieve_supplier_map_by_id(supplier_id)
                if supplier_id is not None
                else None
            )
            supplier_cache[supplier_id] = supplier
            return supplier

        def _user(user_id):
            if user_id in user_cache:
                return user_cache[user_id]
            user = user_query_service.retrieve_user_map_by_id(user_id) if user_id is not None else None
            user_cache[user_id] = user
            return user

        def _account(account_id):
            if account_id in account_cache:
                return account_cache[account_id]
            account = (
                accounts_query_service.retrieve_account_map_by_id(account_id)
                if account_id is not None
                else None
            )
            account_cache[account_id] = account
            return account

        rows = []
        for expense in expenses:
            expense_id = expense[DBExpensesColumns.ID.value]
            supplier = _supplier(expense.get(DBExpensesColumns.SUPPLIER_ID.value))
            user_ded = _user(expense.get(DBExpensesColumns.USER_ID_DEDUZIONE.value))
            account = _account(expense.get(DBExpensesColumns.ACCOUNT_ID.value))

            user_name = ""
            if user_ded:
                user_name = (
                    f"{user_ded.get(DBUsersColumns.FIRST_NAME.value, '') or ''} "
                    f"{user_ded.get(DBUsersColumns.LAST_NAME.value, '') or ''}"
                ).strip()

            rows.append(
                {
                    "id": expense_id,
                    "name": expense.get(DBExpensesColumns.NAME.value, "") or "",
                    "supplier_name": supplier[DBSuppliersColumns.NAME.value] if supplier else "Fornitore non trovato",
                    "net_amount": cls._safe_float(expense.get(DBExpensesColumns.NET_AMOUNT.value)),
                    "tot_amount": cls._safe_float(expense.get(DBExpensesColumns.TOT_AMOUNT.value)),
                    "category": expense.get(DBExpensesColumns.CATEGORY.value, "") or "",
                    "date": expense.get(DBExpensesColumns.DATE.value, "") or "",
                    "deducibile": expense.get(DBExpensesColumns.DEDUCIBILE.value, "") or "",
                    "user_name": user_name,
                    "account_name": account[DBAccountsColumns.NAME.value] if account else "",
                    "created_at": expense.get(DBExpensesColumns.created_at.value, "") or "",
                    "updated_at": expense.get(DBExpensesColumns.updated_at.value, "") or "",
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
            if col == self.COL_FORNITORE:
                return row["supplier_name"]
            if col == self.COL_NETTO:
                return f"{round(row['net_amount'], 2)} €"
            if col == self.COL_LORDO:
                return f"{round(row['tot_amount'], 2)} €"
            if col == self.COL_CATEGORIA:
                return row["category"]
            if col == self.COL_DATA:
                return row["date"]
            if col == self.COL_DEDUCIBILE:
                return row["deducibile"]
            if col == self.COL_UTENTE:
                return row["user_name"]
            if col == self.COL_CONTO:
                return row["account_name"]

        if role == Qt.UserRole:
            if col == self.COL_NOME:
                return row["name"].lower() if row["name"] else ""
            if col == self.COL_FORNITORE:
                return row["supplier_name"].lower() if row["supplier_name"] else ""
            if col == self.COL_NETTO:
                return row["net_amount"]
            if col == self.COL_LORDO:
                return row["tot_amount"]
            if col == self.COL_CATEGORIA:
                return row["category"].lower() if row["category"] else ""
            if col == self.COL_DATA:
                return row["date"]
            if col == self.COL_DEDUCIBILE:
                return row["deducibile"]
            if col == self.COL_UTENTE:
                return row["user_name"].lower() if row["user_name"] else ""
            if col == self.COL_CONTO:
                return row["account_name"].lower() if row["account_name"] else ""
            return self.data(index, Qt.DisplayRole)

        if role == self.ROLE_EXPENSE_ID:
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

    def find_row_by_expense_id(self, expense_id) -> int:
        for i, row in enumerate(self._rows):
            if row["id"] == expense_id:
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

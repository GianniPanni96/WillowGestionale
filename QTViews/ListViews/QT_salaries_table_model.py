"""
QAbstractTableModel del dominio Salari per QTSalariesViewH.

Stessa filosofia di QT_payments_table_model / QT_refunds_table_model /
QT_expenses_table_model: ogni riga viene pre-calcolata una sola volta
(nome utente / conto risolti dai loro id) e la QTableView interroga il
modello solo per le celle visibili. Il QSortFilterProxyModel applica
filtro testo e ordinamento sui dati esposti.
"""

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex

from Gestionale_Enums import (
    DBAccountsColumns,
    DBSalariesColumns,
    DBUsersColumns,
)
from QTViews.ListViews.QT_base_list_view import WarningSupportMixin


class SalariesTableModel(WarningSupportMixin, QAbstractTableModel):
    """
    Modello dati salari per QTableView.

    Le colonne ricalcano quelle di Views/ListViews/Salaries_view_H.py
    legacy: NOME, UTENTE, IMPORTO, DATA EMISSIONE, CONTO CORRENTE.
    """

    HEADERS = [
        "NOME",
        "UTENTE",
        "IMPORTO",
        "DATA\nEMISSIONE",
        "CONTO\nCORRENTE",
    ]

    COL_NOME = 0
    COL_UTENTE = 1
    COL_IMPORTO = 2
    COL_DATA = 3
    COL_CONTO = 4

    ROLE_SALARY_ID = Qt.UserRole + 2

    # Chiave usata dal SalaryWarningService (mappa NAME -> testo).
    WARNING_KEY_FIELD = "name"

    def __init__(self, rows, parent=None):
        super().__init__(parent)
        self._rows = rows
        self._init_warning_state()

    # ------------------------------------------------------------------
    # Build rows
    # ------------------------------------------------------------------

    @classmethod
    def build_rows(cls, salaries, user_query_service, accounts_query_service):
        # Cache su user_id / account_id: condividere il retrieve tra
        # salari di uno stesso utente/conto.
        user_cache: dict = {}
        account_cache: dict = {}

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
        for salary in salaries:
            salary_id = salary[DBSalariesColumns.ID.value]
            user = _user(salary.get(DBSalariesColumns.USER_ID.value))
            account = _account(salary.get(DBSalariesColumns.ACCOUNT_ID.value))

            user_name = ""
            if user:
                user_name = (
                    f"{user.get(DBUsersColumns.FIRST_NAME.value, '') or ''} "
                    f"{user.get(DBUsersColumns.LAST_NAME.value, '') or ''}"
                ).strip()

            rows.append(
                {
                    "id": salary_id,
                    "name": salary.get(DBSalariesColumns.NAME.value, "") or "",
                    "user_name": user_name if user_name else "Utente non trovato",
                    "amount": cls._safe_float(salary.get(DBSalariesColumns.AMOUNT.value)),
                    "date": salary.get(DBSalariesColumns.DATE.value, "") or "",
                    "account_name": account[DBAccountsColumns.NAME.value] if account else "Conto non trovato",
                    "created_at": salary.get(DBSalariesColumns.CREATED_AT.value, "") or "",
                    "updated_at": salary.get(DBSalariesColumns.UPDATED_AT.value, "") or "",
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
            if col == self.COL_UTENTE:
                return row["user_name"]
            if col == self.COL_IMPORTO:
                return f"{round(row['amount'], 2)} €"
            if col == self.COL_DATA:
                return row["date"]
            if col == self.COL_CONTO:
                return row["account_name"]

        if role == Qt.UserRole:
            if col == self.COL_NOME:
                return row["name"].lower() if row["name"] else ""
            if col == self.COL_UTENTE:
                return row["user_name"].lower() if row["user_name"] else ""
            if col == self.COL_IMPORTO:
                return row["amount"]
            if col == self.COL_DATA:
                return row["date"]
            if col == self.COL_CONTO:
                return row["account_name"].lower() if row["account_name"] else ""
            return self.data(index, Qt.DisplayRole)

        if role == self.ROLE_SALARY_ID:
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

    def find_row_by_salary_id(self, salary_id) -> int:
        for i, row in enumerate(self._rows):
            if row["id"] == salary_id:
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

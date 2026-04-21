from ConfigManagers import FiscalSettings
from Gestionale_Enums import DBExpensesColumns, DBInvoicesColumns, DBSalariesColumns, DBUsersColumns, RegimeFiscale
from Model import DatabaseModel
from Utils.Controller_utils import ControllerUtils


class UserQueryService:
    def __init__(self, db_model: DatabaseModel, fiscal_settings: FiscalSettings):
        self.db_model = db_model
        self.fiscal_settings:FiscalSettings = fiscal_settings

    def retrieve_user_by_id(self, user_id):
        return self.db_model.fetch_user_by_id(user_id)

    def retrieve_user_by_fullname(self, user_first_name, user_last_name):
        return self.db_model.fetch_user_by_fullname(user_first_name, user_last_name)

    def retrieve_user_map_by_fullname(self, user_first_name, user_last_name):
        row = self.retrieve_user_by_fullname(user_first_name, user_last_name)
        return ControllerUtils.row_to_map(row, DBUsersColumns)

    def retrieve_user_map_by_extended_name(self, user_extended_name):
        parts = user_extended_name.split(' ')
        if len(parts) < 2:
            return None
        return self.retrieve_user_map_by_fullname(parts[0], parts[1])

    def id_to_full_name_tuple(self, user_id: int) -> list[str]:
        user = self.retrieve_user_map_by_id(user_id)
        if not user:
            return ['', '']
        return [user[DBUsersColumns.FIRST_NAME.value], user[DBUsersColumns.LAST_NAME.value]]

    def id_to_full_name_str(self, user_id: int) -> str:
        user = self.retrieve_user_map_by_id(user_id)
        if not user:
            return ''
        return f"{user[DBUsersColumns.FIRST_NAME.value]} {user[DBUsersColumns.LAST_NAME.value]}"

    def retrieve_user_map_by_id(self, user_id):
        row = self.db_model.fetch_user_by_id(user_id)
        return ControllerUtils.row_to_map(row, DBUsersColumns)

    def retrieve_users_map_list(self):
        rows = self.db_model.fetch_users()
        return [ControllerUtils.row_to_map(row, DBUsersColumns) for row in rows]

    def retrieve_user_with_invoices_map_list(self, user_id, include_unpaid_invoices: bool = True, year: int = None):
        rows = self.db_model.fetch_user_with_invoices(user_id)
        if not rows:
            return []

        all_columns = list(DBUsersColumns) + list(DBInvoicesColumns)
        mapped_rows = [ControllerUtils.row_to_map(row, all_columns) for row in rows]
        return ControllerUtils.filter_invoices(
            mapped_rows,
            self.db_model,
            year,
            include_unpaid_invoices=include_unpaid_invoices,
        )

    def retrieve_user_with_anticipated_expenses_map_list(self, user_id, year: int = None):
        rows = self.db_model.fetch_user_with_anticipated_expenses(user_id)
        all_columns = list(DBUsersColumns) + list(DBExpensesColumns)
        mapped_rows = [ControllerUtils.row_to_map(row, all_columns) for row in rows]
        return ControllerUtils.filter_expenses(mapped_rows, year=year)

    def retrieve_user_with_deducted_expenses_map_list(self, user_id, year: int = None):
        rows = self.db_model.fetch_user_with_deducted_expenses(user_id)
        if not rows:
            return []

        all_columns = list(DBUsersColumns) + list(DBExpensesColumns)
        mapped_rows = [ControllerUtils.row_to_map(row, all_columns) for row in rows]
        return ControllerUtils.filter_expenses(mapped_rows, year=year)

    def retrieve_user_with_salaries_map_list(self, user_id, year: int = None):
        rows = self.db_model.fetch_user_with_salaries(user_id)
        all_columns = list(DBUsersColumns) + list(DBSalariesColumns)
        mapped_rows = [ControllerUtils.row_to_map(row, all_columns) for row in rows]
        return ControllerUtils.filter_salaries(mapped_rows, year=year)

    def get_regime_fiscale_by_id(self, user_id):
        user_map = self.retrieve_user_map_by_id(user_id)
        if not user_map:
            return None
        return user_map[DBUsersColumns.REGIME_FISCALE.value]

    def get_regime_fiscale_by_full_name(self, user_first_name, user_last_name):
        user = self.retrieve_user_by_fullname(user_first_name, user_last_name)
        if not user:
            return None
        return self.get_regime_fiscale_by_id(user[0])

    def print_utente(self, user):
        if not user:
            return 'Utente non trovato.'

        printed_string = '\n'.join(
            f"{column.value}: {user.get(column.value, 'N/A')}"
            for column in DBUsersColumns
        )
        print(printed_string)
        return printed_string

    def print_utenti(self):
        for user in self.retrieve_users_map_list():
            self.print_utente(user)

from Gestionale_Enums import DBAccountsColumns
from Model import DatabaseModel
from Utils.Controller_utils import ControllerUtils


class AccountQueryService:
    def __init__(self, db_model: DatabaseModel):
        self.db_model = db_model

    def retrieve_account_map_by_id(self, account_id):
        row = self.db_model.fetch_account_by_id(account_id)
        return ControllerUtils.row_to_map(row, DBAccountsColumns)

    def retrieve_account_map_by_name(self, account_name):
        row = self.db_model.fetch_account_by_name(account_name)
        return ControllerUtils.row_to_map(row, DBAccountsColumns)

    def retrieve_accounts_map_list(self):
        rows = self.db_model.fetch_accounts()
        return [ControllerUtils.row_to_map(row, DBAccountsColumns) for row in rows]

    def retrieve_last_account_insert_map(self):
        row = self.db_model.fetch_last_account_insert()
        return ControllerUtils.row_to_map(row, DBAccountsColumns)

    def get_accounts_names(self):
        return [account[1] for account in self.db_model.fetch_accounts()]

    @staticmethod
    def get_accounts_mapping(db_model):
        accounts = db_model.fetch_accounts()
        if not accounts:
            return {}
        return {account[1]: account[0] for account in accounts}

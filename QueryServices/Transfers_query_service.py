from Gestionale_Enums import DBTransfersColumns
from Model import DatabaseModel
from Utils.Controller_utils import ControllerUtils


class TransferQueryService:
    def __init__(self, db_model: DatabaseModel):
        self.db_model = db_model

    def retrieve_transfer_map_by_id(self, transfer_id):
        row = self.db_model.fetch_transfer_by_id(transfer_id)
        return ControllerUtils.row_to_map(row, DBTransfersColumns)

    def retrieve_transfers_map_list(self, year: int = None):
        rows = self.db_model.fetch_all_transfers()
        transfers = [ControllerUtils.row_to_map(row, DBTransfersColumns) for row in rows]
        return ControllerUtils.filter_transfers(transfers, year)

    def retrieve_last_transfer_insert_map(self):
        row = self.db_model.fetch_last_transfer_insert()
        return ControllerUtils.row_to_map(row, DBTransfersColumns)

    def retrieve_sent_transfers_map_by_account(self, account_id, year: int = None):
        rows = self.db_model.fetch_sent_transfers_by_account(account_id)
        if not rows:
            return []
        transfers = [ControllerUtils.row_to_map(row, DBTransfersColumns) for row in rows]
        return ControllerUtils.filter_transfers(transfers, year)

    def retrieve_received_transfers_map_by_account(self, account_id, year: int = None):
        rows = self.db_model.fetch_received_transfers_by_account(account_id)
        if not rows:
            return []
        transfers = [ControllerUtils.row_to_map(row, DBTransfersColumns) for row in rows]
        return ControllerUtils.filter_transfers(transfers, year)

    def retrieve_received_transfers_map(self, account_id, year: int = None):
        rows = self.db_model.fetch_received_transfers_by_account(account_id)
        transfers = [ControllerUtils.row_to_map(row, DBTransfersColumns) for row in rows]
        return ControllerUtils.filter_transfers(transfers, year)

    def retrieve_sent_transfers_map(self, account_id, year: int = None):
        rows = self.db_model.fetch_sended_transfers_by_account(account_id)
        transfers = [ControllerUtils.row_to_map(row, DBTransfersColumns) for row in rows]
        return ControllerUtils.filter_transfers(transfers, year)

from Gestionale_Enums import DBTransfersColumns
from QueryServices.Transfers_query_service import TransferQueryService


class TransferAnalyzerService:
    def __init__(self, transfer_query_service: TransferQueryService):
        self.transfer_query_service = transfer_query_service

    def calculate_tot_amount_sent_transfers_by_account(self, account_id, year: int = None):
        sent_transfers = self.transfer_query_service.retrieve_sent_transfers_map_by_account(account_id, year)
        return sum(float(tr[DBTransfersColumns.AMOUNT.value]) for tr in sent_transfers)

    def calculate_tot_amount_received_transfers_by_account(self, account_id, year: int = None):
        received_transfers = self.transfer_query_service.retrieve_received_transfers_map_by_account(account_id, year)
        return sum(float(tr[DBTransfersColumns.AMOUNT.value]) for tr in received_transfers)

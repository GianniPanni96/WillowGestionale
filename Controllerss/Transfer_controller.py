from Gestionale_Enums import DBAccountsColumns, DBTransfersColumns
from Model import DatabaseModel
from QueryServices.Account_query_service import AccountQueryService
from QueryServices.Transfers_query_service import TransferQueryService
from AnalyzerServices.Transfer_analyzer_service import TransferAnalyzerService
from Utils.Validation_utils import ValidationUtils


class TransferController:
    def __init__(
        self,
        db_model: DatabaseModel,
        account_query_service: AccountQueryService,
        transfer_query_service: TransferQueryService,
        transfer_analyzer_service: TransferAnalyzerService,
    ):
        self.db_model = db_model
        self.account_query_service = account_query_service
        self.transfer_query_service = transfer_query_service
        self.transfer_analyzer_service = transfer_analyzer_service

    def save_transfer(self, transfer_data):
        required_fields = {
            DBTransfersColumns.DESCRIPTION.value,
            DBTransfersColumns.AMOUNT.value,
        }
        missing_fields = [field for field in required_fields if not transfer_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        amount = transfer_data.get(DBTransfersColumns.AMOUNT.value)
        if not ValidationUtils.validate_amount(amount):
            return False, "L'importo inserito non è valido"

        receiver_account_name = transfer_data.get("CONTO RICEVENTE")
        receiver_account = self.account_query_service.retrieve_account_map_by_name(receiver_account_name)
        receiver_account_id = receiver_account[DBAccountsColumns.ID.value] if receiver_account else None

        prepared = {
            DBTransfersColumns.DESCRIPTION.value: transfer_data.get(DBTransfersColumns.DESCRIPTION.value),
            DBTransfersColumns.AMOUNT.value: amount,
            DBTransfersColumns.SENDER_ACCOUNT_ID.value: transfer_data.get(DBTransfersColumns.SENDER_ACCOUNT_ID.value),
            DBTransfersColumns.RECEIVER_ACCOUNT_ID.value: receiver_account_id,
        }

        try:
            self.db_model.add_transfer(**prepared)
            return True, "Bonifico salvato con successo!"
        except Exception as e:
            return False, f"Errore durante il salvataggio: {str(e)}"

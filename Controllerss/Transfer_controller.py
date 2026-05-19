from datetime import datetime

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

    def update_transfer(self, transfer_id, transfer_data):
        """Aggiorna i dati di un bonifico esistente."""
        try:
            if not transfer_id or not isinstance(transfer_id, int):
                return False, "ID bonifico non valido."

            description = transfer_data.get(DBTransfersColumns.DESCRIPTION.value)
            amount = transfer_data.get(DBTransfersColumns.AMOUNT.value)
            sender_id = transfer_data.get(DBTransfersColumns.SENDER_ACCOUNT_ID.value)
            receiver_id = transfer_data.get(DBTransfersColumns.RECEIVER_ACCOUNT_ID.value)

            if not description:
                return False, "La causale non puo' essere vuota."
            if amount is None or not ValidationUtils.validate_amount(amount):
                return False, "L'importo inserito non e' valido."
            if sender_id is None or receiver_id is None:
                return False, "Conto mittente e ricevente sono obbligatori."
            if sender_id == receiver_id:
                return False, "Il conto mittente e quello ricevente devono essere diversi."

            prepared = {
                DBTransfersColumns.DESCRIPTION.value: description,
                DBTransfersColumns.AMOUNT.value: amount,
                DBTransfersColumns.SENDER_ACCOUNT_ID.value: sender_id,
                DBTransfersColumns.RECEIVER_ACCOUNT_ID.value: receiver_id,
                DBTransfersColumns.UPDATED_AT.value: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            self.db_model.update_transfer(transfer_id, **prepared)
            return True, "Bonifico aggiornato con successo!"
        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento del bonifico: {str(e)}"

    def delete_transfer(self, transfer_id):
        try:
            result = self.db_model.delete_transfer(transfer_id)
            if result:
                return True, "Bonifico eliminato con successo."
            return False, "Bonifico non trovato o errore durante l'eliminazione."
        except Exception as e:
            return False, f"Errore durante l'eliminazione del bonifico: {str(e)}"

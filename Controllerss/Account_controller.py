from datetime import datetime

from Gestionale_Enums import DBAccountsColumns
from Model import DatabaseModel
from QueryServices.Account_query_service import AccountQueryService
from AnalyzerServices.Account_analyzer_service import AccountAnalyzerService
from Utils.Validation_utils import ValidationUtils


class AccountController:
    def __init__(
        self,
        db_model: DatabaseModel,
        account_query_service: AccountQueryService,
        account_analyzer_service: AccountAnalyzerService,
    ):
        self.db_model = db_model
        self.account_query_service = account_query_service
        self.account_analyzer_service = account_analyzer_service


    def save_account(self, account_data):
        required_fields = {DBAccountsColumns.NAME.value, DBAccountsColumns.INIT_BALANCE.value}
        missing_fields = [field for field in required_fields if not account_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        init_balance = account_data.get(DBAccountsColumns.INIT_BALANCE.value)
        if not ValidationUtils.validate_amount(init_balance):
            return False, "L'importo INIT_BALANCE non è valido"

        prepared = {
            DBAccountsColumns.NAME.value: account_data.get(DBAccountsColumns.NAME.value),
            DBAccountsColumns.INIT_BALANCE.value: float(init_balance),
        }

        try:
            self.db_model.add_account(**prepared)
            return True, "Produzione salvata con successo!"
        except Exception as e:
            return False, f"Errore durante il salvataggio: {str(e)}"

    def update_account(self, account_id, account_data):
        try:
            if not account_id or not isinstance(account_id, int):
                return False, "ID account non valido. Deve essere un intero positivo."

            required_fields = {DBAccountsColumns.NAME.value, DBAccountsColumns.INIT_BALANCE.value}
            missing_fields = [field for field in required_fields if not account_data.get(field)]
            if missing_fields:
                return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

            amount = account_data.get(DBAccountsColumns.INIT_BALANCE.value)
            if amount and not ValidationUtils.validate_amount(amount):
                return False, "L'importo inserito non è valido."

            account_data[DBAccountsColumns.UPDATED_AT.value] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.db_model.update_account(account_id, **account_data)
            return True, "Account aggiornato con successo!"
        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento del conto: {str(e)}"

    def delete_account_by_ID(self, account_id):
        try:
            self.db_model.delete_row("accounts", DBAccountsColumns.ID.value, account_id)
            return True, f"Account {account_id} rimosso con successo"
        except Exception as e:
            return False, f"Errore durante l'eliminazione del conto: {str(e)}"


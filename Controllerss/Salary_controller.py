from datetime import datetime

from Gestionale_Enums import DBAccountsColumns, DBSalariesColumns, DBUsersColumns
from Model import DatabaseModel
from QueryServices.Account_query_service import AccountQueryService
from QueryServices.Salaries_query_service import SalaryQueryService
from AnalyzerServices.Salary_analyzer_service import SalaryAnalyzerService
from Utils.Validation_utils import ValidationUtils


class SalaryController:
    def __init__(
        self,
        db_model: DatabaseModel,
        user_controller,
        account_query_service: AccountQueryService,
        salary_query_service: SalaryQueryService,
        salary_analyzer_service: SalaryAnalyzerService,
    ):
        self.db_model = db_model
        self.user_controller = user_controller
        self.account_query_service = account_query_service
        self.salary_query_service = salary_query_service
        self.salary_analyzer_service = salary_analyzer_service

    def save_salary(self, salary_data):
        required_fields = {DBSalariesColumns.NAME.value, DBSalariesColumns.AMOUNT.value}
        missing_fields = [field for field in required_fields if not salary_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        amount = salary_data.get(DBSalariesColumns.AMOUNT.value)
        if not ValidationUtils.validate_amount(amount):
            return False, "L'importo non è valido"

        user_id = None
        user_name = salary_data.get("NOME UTENTE")
        if user_name and len(user_name.split(" ")) >= 2:
            user_first = user_name.split(" ")[0]
            user_last = user_name.split(" ")[1]
            user = self.user_controller.retrieve_user_map_by_fullname(user_first, user_last)
            user_id = user[DBUsersColumns.ID.value] if user else None

        account_id = None
        account_name = salary_data.get("CONTO")
        if account_name:
            account = self.account_query_service.retrieve_account_map_by_name(account_name)
            account_id = account[DBAccountsColumns.ID.value] if account else None

        prepared = {
            DBSalariesColumns.NAME.value: salary_data.get(DBSalariesColumns.NAME.value),
            DBSalariesColumns.USER_ID.value: user_id,
            DBSalariesColumns.DATE.value: salary_data.get(DBSalariesColumns.DATE.value),
            DBSalariesColumns.AMOUNT.value: amount,
            DBSalariesColumns.ACCOUNT_ID.value: account_id,
        }

        try:
            self.db_model.add_salary(**prepared)
            return True, "Salario salvato con successo!"
        except Exception as e:
            return False, f"Errore durante il salvataggio: {str(e)}"

    def update_salary(self, salary_id, salary_data):
        try:
            if not salary_id or not isinstance(salary_id, int):
                return False, "ID salario non valido. Deve essere un intero positivo."

            required_fields = {DBSalariesColumns.NAME.value, DBSalariesColumns.AMOUNT.value}
            missing_fields = [field for field in required_fields if not salary_data.get(field)]
            if missing_fields:
                return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

            if DBSalariesColumns.AMOUNT.value in salary_data:
                amount = salary_data[DBSalariesColumns.AMOUNT.value]
                if amount and not ValidationUtils.validate_amount(amount):
                    return False, "L'importo inserito non è valido."

            salary_data[DBSalariesColumns.UPDATED_AT.value] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.db_model.update_salary(salary_id, **salary_data)
            return True, "Salario aggiornato con successo!"
        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento del salario: {str(e)}"

    def delete_salary(self, salary_id):
        return self.db_model.remove_salary(salary_id)

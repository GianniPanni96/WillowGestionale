from Gestionale_Enums import DBSalariesColumns
from Model import DatabaseModel
from Utils.Controller_utils import ControllerUtils


class SalaryQueryService:
    def __init__(self, db_model: DatabaseModel):
        self.db_model = db_model

    def retrieve_salary_map_by_name(self, salary_name: str) -> dict | None:
        row = self.db_model.fetch_salary_by_name(salary_name)
        if not row:
            return None
        return ControllerUtils.row_to_map(row, DBSalariesColumns)

    def retrieve_salary_map_by_id(self, salary_id: int) -> dict | None:
        row = self.db_model.fetch_salary_by_id(salary_id)
        return ControllerUtils.row_to_map(row, DBSalariesColumns)

    def retrieve_salaries_map_list(self, year: int = None) -> list[dict]:
        rows = self.db_model.fetch_all_salaries()
        salaries = [ControllerUtils.row_to_map(row, DBSalariesColumns) for row in rows]
        return ControllerUtils.filter_salaries(salaries, year)

    def retrieve_last_salary_insert_map(self) -> dict | None:
        row = self.db_model.fetch_last_salary_insert()
        return ControllerUtils.row_to_map(row, DBSalariesColumns)

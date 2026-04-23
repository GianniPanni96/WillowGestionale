from datetime import datetime
from enum import Enum

from Gestionale_Enums import DBSalariesColumns
from Model import DatabaseModel
from QueryServices.Salaries_query_service import SalaryQueryService
from Utils.Controller_utils import ControllerUtils


class SalaryAnalyzerService:
    class SalariesAggregateData(Enum):
        NUMERO_SALARI = "#SALARI"
        TOT_SALARI = "TOT. SALARI"

    def __init__(self, salary_query_service: SalaryQueryService, db_model: DatabaseModel):
        self.salary_query_service = salary_query_service
        self.db_model = db_model

    def count_salaries(self, year: int = None) -> int:
        salaries = self.salary_query_service.retrieve_salaries_map_list(year=year)
        return len(salaries)

    def calculate_tot_salaries(self, year: int = None) -> float:
        salary_list = self.salary_query_service.retrieve_salaries_map_list(year=year)
        return sum(float(sal[DBSalariesColumns.AMOUNT.value]) for sal in salary_list)

    def sum_salaries_for_account(self, account_id, year: int = None):
        target_year = year if year is not None else datetime.now().year
        return self.db_model.sum_salaries_by_account(account_id, year=target_year)

    def calculate_mean_salary_by_month(self, month: int, year: int = None) -> float | None:
        if month < 1 or month > 12:
            print(f"SalaryAnalyzerService.calculate_mean_salary_by_month(): Invalid month {month}. Must be between 1-12.")
            return None

        try:
            salaries = self.salary_query_service.retrieve_salaries_map_list(year=year)
            if not salaries:
                print("SalaryAnalyzerService.calculate_mean_salary_by_month(): No salary data found.")
                return None

            filtered_salaries = ControllerUtils.filter_salaries(salaries=salaries, year=year)

            monthly_tot = 0.0
            count = 0

            for salary in filtered_salaries:
                date_str = salary.get(DBSalariesColumns.DATE.value)
                if not date_str:
                    continue

                try:
                    date = datetime.strptime(date_str, "%Y-%m-%d")
                    if date.month == month:
                        amount = salary.get(DBSalariesColumns.AMOUNT.value)
                        if amount is not None:
                            monthly_tot += float(amount)
                            count += 1
                except (ValueError, TypeError) as e:
                    print(f"Warning: Invalid date format for salary: {date_str} - {e}")
                    continue

            if count == 0:
                print(f"No salary data found for month {month}")
                return None

            return monthly_tot / count

        except Exception as e:
            print(f"Error in calculate_mean_salary_by_month: {e}")
            return None

from Gestionale_Enums import DBExpensesColumns
from Model import DatabaseModel
from Utils.Controller_utils import ControllerUtils
from Utils.Validation_utils import ValidationUtils


class ExpenseQueryService:
    """
    Query service dedicato alle letture del dominio spese.
    """

    def __init__(self, db_model: DatabaseModel):
        self.db_model = db_model

    def retrieve_expense_by_id(self, expense_id):
        return self.db_model.fetch_expense_by_id(expense_id)

    def retrieve_expense_map_by_id(self, expense_id):
        row = self.db_model.fetch_expense_by_id(expense_id)
        return ControllerUtils.row_to_map(row, DBExpensesColumns)

    def retrieve_expense_map_by_name(self, expense_name):
        row = self.db_model.fetch_expense_by_name(expense_name)
        return ControllerUtils.row_to_map(row, DBExpensesColumns)

    # TODO: i costumers stanno ricevendo anche le spese relative a iva e tasse, controllare che sia corretto
    # TODO: aggiungere argomenti per filtrare iva e tasse dal retrieving oppure definire nuove funzioni
    def retrieve_expenses_map_list(self, year: int = None):
        rows = self.db_model.fetch_expenses()
        expenses = [ControllerUtils.row_to_map(row, DBExpensesColumns) for row in rows]
        return ControllerUtils.filter_expenses(expenses, year)


    def retrieve_expense_map_list_by_supplier(self, supplier_id, year: int = None):
        rows = self.db_model.fetch_expenses_by_supplier_id(supplier_id)
        expenses = [ControllerUtils.row_to_map(row, DBExpensesColumns) for row in rows]
        return ControllerUtils.filter_expenses(expenses, year)

    def retrieve_last_expense_insert_map(self):
        row = self.db_model.fetch_last_expense_insert()
        return ControllerUtils.row_to_map(row, DBExpensesColumns)

    def retrieve_expenses_map_dictionary(self, keyIsName: bool = False, year: int = -1):
        expenses = self.retrieve_expenses_map_list(year=year)
        if keyIsName:
            return {
                expense[DBExpensesColumns.NAME.value]: expense
                for expense in expenses
            }

        return {
            expense[DBExpensesColumns.ID.value]: expense
            for expense in expenses
        }

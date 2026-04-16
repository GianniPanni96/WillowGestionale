from Utils.Controller_utils import ControllerUtils
from datetime import datetime, timedelta
from Model import DatabaseModel
from Gestionale_Enums import *
from Utils.Date_utils import parse_db_datetime

class SupplierQueryService:
    """
    Query service dedicato alle letture sul dominio Fornitori.

    La classe concentra query, trasformazioni dei record e filtri temporali,
    cosi' view e analyzer possono lavorare con strutture gia' pronte senza
    incorporare logica di accesso al database.
    """

    def __init__(self, database_model:DatabaseModel):
        self.db_model:DatabaseModel = database_model

    def get_suppliers_for_days_window(self, days):
        """
        Restituisce i fornitori visibili nella finestra temporale selezionata.

        Un fornitore viene incluso se possiede almeno una spesa associata recente
        oppure se è stato creato di recente, cosi' resta visibile anche prima
        di avere produzioni collegate.
        """
        limit_date = datetime.now() - timedelta(days=days)

        all_suppliers = self.retrieve_suppliers_map_list(year=-1)
        filtered_suppliers = []

        for supplier in all_suppliers:
            supplier_id = supplier[DBSuppliersColumns.ID.value]
            supplier_expenses = self.retrieve_supplier_with_expenses_map_list(supplier_id, year=-1)

            has_recent_expense = False
            for expense in supplier_expenses:
                date_str = expense.get(DBExpensesColumns.DATE.value)

                expense_date = parse_db_datetime(date_str)
                if expense_date and expense_date >= limit_date:
                    has_recent_expense = True
                    break

            supplier_creation_date =parse_db_datetime(
                supplier.get(DBSuppliersColumns.CREATED_AT.value))

            is_just_created = False
            if datetime.now() - supplier_creation_date <= timedelta(days=30):
                is_just_created = True

            if has_recent_expense or is_just_created:
                filtered_suppliers.append(supplier)

        return filtered_suppliers

    def retrieve_supplier_by_id(self, supplier_id):
        """Recupera un supplier specifico per ID."""
        return self.db_model.fetch_supplier_by_id(supplier_id)

    def retrieve_supplier_by_name(self, supplier_name):
        """Recupera un supplier specifico per nome."""
        return self.db_model.fetch_supplier_by_name(supplier_name)

    def retrieve_supplier_map_by_name(self, supplier_name):
        """Recupera un supplier specifico e lo restituisce come dizionario."""
        row = self.retrieve_supplier_by_name(supplier_name)
        return ControllerUtils.row_to_map(row, DBSuppliersColumns)

    def retrieve_supplier_map_by_id(self, supplier_id):
        """Recupera un supplier specifico e lo restituisce come dizionario."""
        row = self.db_model.fetch_supplier_by_id(supplier_id)
        return ControllerUtils.row_to_map(row, DBSuppliersColumns)

    def retrieve_suppliers_map_list(self, year: int = None):
        """Recupera tutti i suppliers e li restituisce come lista di dizionari."""
        rows = self.db_model.fetch_suppliers()

        # mapping tuple → dict
        suppliers = [
            ControllerUtils.row_to_map(row, DBSuppliersColumns)
            for row in rows
        ] if rows else []

        # filtro corretto sul dominio productions
        if suppliers:
            suppliers = ControllerUtils.filter_suppliers(
                suppliers=suppliers,
                year=year
            )

        return suppliers

    def retrieve_suppliers_map_dictionary(self, keyIsName: bool = False):
        """
        Restituisce tutti i fornitori in un dizionario indicizzato.

        Args:
            keyIsName: se ``True`` usa il nome fornitore come chiave, altrimenti l'id.
        """
        supplier_list = self.retrieve_suppliers_map_list(year=-1)
        dictionary = {}

        for row in supplier_list:
            dictionary[
                f"{row[DBSuppliersColumns.NAME.value]}" if keyIsName else f"{row[DBSuppliersColumns.ID.value]}"
            ] = row

        return dictionary

    def retrieve_last_supplier_insert_map(self):
        """
        Recupera l'ultimo supplier inserito e lo restituisce come dizionario.
        """
        row = self.db_model.fetch_last_supplier_insert()
        return ControllerUtils.row_to_map(row, DBSuppliersColumns)

    def retrieve_supplier_with_expenses_map_list(self, supplier_id, year:int = None):
        """ Recupera lo specifico supplier unito alle rispettive spese e
           li restituisce come lista di dizionari.

           Utilizza la funzione fetch_supplier_with_expenses per ottenere le righe,
           quindi combina le colonne dei supplier e delle spese per convertire
           ogni riga in un dizionario tramite _row_to_map.
           """
        # Recupera le righe dal database per lo specifico client
        rows = self.db_model.fetch_supplier_with_expenses(supplier_id)

        all_columns = list(DBSuppliersColumns) + list(DBExpensesColumns)

        expenses_map = [ControllerUtils.row_to_map(row, all_columns) for row in rows]

        if expenses_map:
            expenses_map = ControllerUtils.filter_expenses(
                expenses=expenses_map,
                year=year
            )

        # Converte ogni riga in un dizionario
        return expenses_map


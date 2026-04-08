from QueryServices.Suppliers_query_service import SupplierQueryService
from Gestionale_Enums import *

from Model import DatabaseModel

class SupplierAnalyzerService:
    """
    Servizio applicativo che calcola gli aggregati economici dei fornitori.

    Questa classe lavora sopra ``SupplierQueryService`` e ``DatabaseModel``:
    non costruisce interfacce, ma espone metriche pronte per view e report,
    mantenendo fuori dalla UI la logica di analisi.
    """

    def __init__(self, supplier_query_service:SupplierQueryService, database_model:DatabaseModel):
        self.supplier_query_service:SupplierQueryService = supplier_query_service
        self.db_model:DatabaseModel = database_model

    def calcola_tot_spese_supplier(self, supplier_id, year:int = None):
        supplier_with_expenses = self.supplier_query_service.retrieve_supplier_with_expenses_map_list(supplier_id, year=year)
        tot = 0.0
        for row in supplier_with_expenses: #in questo modo sto in realtà scorrendo le fatture
            tot = tot + float(row[DBExpensesColumns.TOT_AMOUNT.value]) if row[DBExpensesColumns.TOT_AMOUNT.value] is not None else tot

        return tot

    def calcola_numero_spese_supplier(self, supplier_id, year:int = None):
        supplier_with_expenses = self.supplier_query_service.retrieve_supplier_with_expenses_map_list(supplier_id, year=year)
        tot = 0
        for row in supplier_with_expenses:
            tot = tot + 1

        return tot

    def calcola_media_spese_supplier(self, supplier_id, year:int = None):
        numero = self.calcola_numero_spese_supplier(supplier_id, year=year)
        tot = self.calcola_tot_spese_supplier(supplier_id, year=year)

        return tot/numero if numero > 0 else 0

    def construct_supplier_map_aggregate_data(self, supplier_id):
        supplier_aggregate_data = {
            SupplierAggregateData.TOT_SPESE.value: self.calcola_tot_spese_supplier(supplier_id, year=-1),
            SupplierAggregateData.NUM_SPESE.value: self.calcola_numero_spese_supplier(supplier_id, year=-1),
            SupplierAggregateData.MEDIA_SPESE.value: self.calcola_media_spese_supplier(supplier_id, year=-1)
        }

        return supplier_aggregate_data
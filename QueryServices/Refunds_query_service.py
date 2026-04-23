from Model import DatabaseModel
from Gestionale_Enums import DBRefundsColumns
from Utils.Controller_utils import ControllerUtils


class RefundQueryService:
    """
    Query service dedicato alle letture sul dominio Rimborsi.

    Centralizza il retrieving dal model e il filtraggio temporale, cosi' view e
    analyzer non dipendono dal controller per le operazioni di sola lettura.
    """

    def __init__(self, database_model: DatabaseModel):
        self.db_model: DatabaseModel = database_model

    def retrieve_refund_by_id(self, refund_id):
        row = self.db_model.fetch_refund_by_id(refund_id)
        if not row:
            return row

        columns = [col.value for col in DBRefundsColumns]
        return dict(zip(columns, row))

    def retrieve_refund_map_by_id(self, refund_id):
        row = self.db_model.fetch_refund_by_id(refund_id)
        if not row:
            return None

        columns = [col.value for col in DBRefundsColumns]
        return dict(zip(columns, row))

    def retrieve_refund_map_by_name(self, refund_name):
        row = self.db_model.fetch_refund_by_name(refund_name)
        if not row:
            return None

        columns = [col.value for col in DBRefundsColumns]
        return dict(zip(columns, row))

    def retrieve_refunds_map_list(self, year: int = None):
        rows = self.db_model.fetch_refunds()
        refunds = [ControllerUtils.row_to_map(row, DBRefundsColumns) for row in rows]
        return ControllerUtils.filter_refunds(refunds, year)

    def retrieve_refunds_map_list_by_client_id(self, client_id, year: int = None):
        rows = self.db_model.fetch_refunds_by_client_id(client_id)
        refunds = [ControllerUtils.row_to_map(row, DBRefundsColumns) for row in rows]
        return ControllerUtils.filter_refunds(refunds, year)

    def retrieve_refunds_map_dictionary(self, keyIsName: bool = False):
        refunds = self.retrieve_refunds_map_list(year=-1)
        if keyIsName:
            return {
                refund[DBRefundsColumns.REFUND_NAME.value]: refund
                for refund in refunds
            }

        return {
            refund[DBRefundsColumns.ID.value]: refund
            for refund in refunds
        }

    def retrieve_last_refund_insert_map(self):
        row = self.db_model.fetch_last_refund_insert()
        return ControllerUtils.row_to_map(row, DBRefundsColumns)

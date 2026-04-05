from Utils.Controller_utils import ControllerUtils
from Model import DatabaseModel
from Gestionale_Enums import *

class PaymentQueryService:
    """
    Query service dedicato alle letture sul dominio Pagamenti.

    La classe concentra query, trasformazioni dei record e filtri temporali,
    cosi' view e analyzer possono lavorare con strutture gia' pronte senza
    incorporare logica di accesso al database.
    """
    def __init__(self, database_model:DatabaseModel):
        self.db_model:DatabaseModel = database_model

    def retrieve_payment_map_by_id(self, payment_id):
        """
        Recupera un pagamento specifico e lo restituisce come dizionario,
        filtrando per l'anno corrente se specificato.
        :param payment_id: ID del pagamento.
        :return: Dizionario con i dati del pagamento oppure None.
        """
        row = self.db_model.fetch_payment_by_id(payment_id)
        if not row:
            return None

        columns = [col.value for col in DBPaymentsColumns]
        payment_dict = dict(zip(columns, row))

        return payment_dict

    def retrieve_payment_map_by_name(self, payment_name):
        """
        Recupera un pagamento specifico e lo restituisce come dizionario,
        filtrando per l'anno corrente se specificato.
        :param payment_name: nome del pagamento.
        :return: Dizionario con i dati del pagamento oppure None.
        """
        row = self.db_model.fetch_payment_by_name(payment_name)
        if not row:
            return None

        columns = [col.value for col in DBPaymentsColumns]
        payment_dict = dict(zip(columns, row))

        return payment_dict

    def retrieve_payments_map_list(self, year: int = None, include_unpaid_invoice_payments: bool = True):
        """
        Recupera tutti i pagamenti come lista di dizionari,
        filtrandoli per l'anno specificato.

        :param include_unpaid_invoice_payments:
        :param year:
            - None → anno corrente
            - -1   → nessun filtro
            - altro int → anno specifico
        :return: Lista di pagamenti (dizionari)
        """
        rows = self.db_model.fetch_payments()
        payments = [ControllerUtils.row_to_map(row, DBPaymentsColumns) for row in rows]

        return ControllerUtils.filter_payments(
            payments = payments,
            db_model = self.db_model,
            year = year,
            include_unpaid_invoice_payments = include_unpaid_invoice_payments)

    def retrieve_payments_map_list_by_invoice_id(self, invoice_id, year: int = None):
        """
        Recupera tutti i pagamenti collegati a una fattura come lista di dizionari,
        filtrandoli per l'anno specificato.

        :param invoice_id: ID della fattura
        :param year:
            - None → anno corrente
            - -1   → nessun filtro
            - altro int → anno specifico
        :return: Lista di pagamenti (dizionari)
        """
        rows = self.db_model.fetch_payments_by_invoice_id(invoice_id)
        payments = [ControllerUtils.row_to_map(row, DBPaymentsColumns) for row in rows]

        return ControllerUtils.filter_payments(payments=payments, year=year, db_model=self.db_model)

    def retrieve_payments_map_dictionary(self, keyIsName: bool = False):
        """
        Restituisce tutti i pagamenti in un dizionario indicizzato.

        Args:
            keyIsName: se ``True`` usa il nome pagamento come chiave, altrimenti l'id.
        """
        payments = self.retrieve_payments_map_list(year=-1, include_unpaid_invoice_payments=True)

        if keyIsName:
            return {
                payment[DBPaymentsColumns.PAYMENT_NAME.value]: payment
                for payment in payments
            }

        return {
            payment[DBPaymentsColumns.ID.value]: payment
            for payment in payments
        }

    def retrieve_last_payment_insert_map(self):
        """
        Recupera l'ultimo pagamento inserito e lo restituisce come dizionario.
        """
        row = self.db_model.fetch_last_payment_insert()
        return ControllerUtils.row_to_map(row, DBPaymentsColumns)

from datetime import datetime

from Gestionale_Enums import DBAccountsColumns, DBClientsColumns, DBRefundsColumns
from Model import DatabaseModel
from Utils.Validation_utils import ValidationUtils


class RefundController:
    """
    Controller dedicato alle operazioni di scrittura sul dominio rimborsi.

    Mantiene solo salvataggio, aggiornamento ed eliminazione, lasciando retrieve
    e aggregazioni a query service e analyzer service.
    """

    def __init__(self, db_model: DatabaseModel, client_controller, account_controller):
        self.db_model = db_model
        self.client_controller = client_controller
        self.account_controller = account_controller

    def save_refund(self, refund_data):
        required_fields = {
            DBRefundsColumns.REFUND_NAME.value,
            DBRefundsColumns.REFUND_AMOUNT.value
        }

        missing_fields = [field for field in required_fields if not refund_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        tot_refund = refund_data.get(DBRefundsColumns.REFUND_AMOUNT.value)
        if not ValidationUtils.validate_amount(tot_refund):
            return False, "L'importo del rimborso non e valido"

        nome_conto = refund_data.get("NOME CONTO")
        conto = self.account_controller.retrieve_account_map_by_name(nome_conto)
        id_conto = conto[DBAccountsColumns.ID.value] if conto else None

        nome_cliente = refund_data.get("NOME CLIENTE")
        cliente = self.client_controller.retrieve_client_map_by_name(nome_cliente)
        id_cliente = cliente[DBClientsColumns.ID.value] if cliente else None

        if id_conto is None or id_cliente is None:
            return False, "Conto o cliente non validi."

        refund_data_prepared = {
            DBRefundsColumns.REFUND_NAME.value: refund_data.get(DBRefundsColumns.REFUND_NAME.value),
            DBRefundsColumns.REFUND_AMOUNT.value: refund_data.get(DBRefundsColumns.REFUND_AMOUNT.value),
            DBRefundsColumns.REFUND_DATE.value: refund_data.get(DBRefundsColumns.REFUND_DATE.value),
            DBRefundsColumns.CLIENT_ID.value: id_cliente,
            DBRefundsColumns.CONTO_ID.value: id_conto,
        }

        try:
            self.db_model.add_refund(**refund_data_prepared)
            return True, "Rimborso salvato con successo!"
        except Exception as e:
            return False, f"Errore durante il salvataggio: {str(e)}"

    def update_refund(self, refund_id, refund_data):
        try:
            if not refund_id or not isinstance(refund_id, int):
                return False, "ID rimborso non valido. Deve essere un intero positivo."

            required_fields = [
                DBRefundsColumns.REFUND_NAME.value,
                DBRefundsColumns.REFUND_AMOUNT.value,
                DBRefundsColumns.REFUND_DATE.value,
                DBRefundsColumns.CLIENT_ID.value,
                DBRefundsColumns.CONTO_ID.value,
            ]

            missing_fields = [field for field in required_fields if not refund_data.get(field)]
            if missing_fields:
                return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

            amount = refund_data.get(DBRefundsColumns.REFUND_AMOUNT.value)
            if amount and not ValidationUtils.validate_amount(amount):
                return False, "L'importo inserito non e valido."

            refund_data[DBRefundsColumns.UPDATED_AT.value] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.db_model.update_refund(refund_id, **refund_data)
            return True, "Rimborso aggiornato con successo!"

        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento del rimborso: {str(e)}"

    def delete_refund(self, refund_id):
        return self.db_model.remove_refund(refund_id)

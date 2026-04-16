from datetime import datetime

from Model import DatabaseModel
from Gestionale_Enums import *
from QueryServices.Account_query_service import AccountQueryService
from Utils.Validation_utils import ValidationUtils


class PaymentsController:

    def __init__(self, db_model: DatabaseModel, account_query_service:AccountQueryService):
        self.db_model:DatabaseModel = db_model
        self.account_query_service:AccountQueryService = account_query_service

        self.on_adding_payment_callbacks = []

    def save_payment(self, payment_data):
        """
        Gestisce il salvataggio di un pagamento, con validazioni di primo livello.
        :param payment_data: Dizionario contenente i dati del pagamento
        :return: Tuple (success, message), dove success è True/False
        """

        # Campi obbligatori (solo quelli modellati tramite entry)
        self.required_fields = {"NOME FATTURA", DBPaymentsColumns.PAYMENT_NAME.value, DBPaymentsColumns.PAYMENT_AMOUNT.value}

        # Validazione dei campi obbligatori
        missing_fields = [field for field in self.required_fields if not payment_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        # Validazione importi
        tot_pagamento = payment_data.get(DBPaymentsColumns.PAYMENT_AMOUNT.value)
        if not ValidationUtils.validate_amount(tot_pagamento):
            return False, "L'importo del preventivo non è valido"

        # prendo i dati necessari del conto
        nome_conto = payment_data.get("NOME CONTO")
        conto = self.account_query_service.retrieve_account_map_by_name(nome_conto)
        id_conto = conto[DBAccountsColumns.ID.value]


        payment_data_prepared = {
            DBPaymentsColumns.PAYMENT_NAME.value : payment_data.get(DBPaymentsColumns.PAYMENT_NAME.value),
            DBPaymentsColumns.PAYMENT_AMOUNT.value: payment_data.get(DBPaymentsColumns.PAYMENT_AMOUNT.value),
            DBPaymentsColumns.INVOICE_ID.value : payment_data.get(DBPaymentsColumns.INVOICE_ID.value),
            DBPaymentsColumns.PAYMENT_DATE.value: payment_data.get(DBPaymentsColumns.PAYMENT_DATE.value),
            DBPaymentsColumns.LINKED_RATA.value: payment_data.get(DBPaymentsColumns.LINKED_RATA.value),
            DBPaymentsColumns.CONTO_ID.value: id_conto,
        }

        try:
            self.db_model.add_payment(**payment_data_prepared)
            return True, "Produzione salvata con successo!"
        except Exception as e:
            return False, f"Errore durante il salvataggio: {str(e)}"

    def update_payment(self, payment_id, payment_data):
        """
        Aggiorna i dati di un pagamento esistente.
        :param payment_id: ID del pagamento da aggiornare
        :param payment_data: Dizionario contenente i dati da aggiornare
        :return: Tuple (success, message), dove success è True/False
        """
        try:
            # Controllo validità payment_id
            if not payment_id or not isinstance(payment_id, int):
                return False, "ID pagamento non valido. Deve essere un intero positivo."

            required_fields = {DBPaymentsColumns.PAYMENT_AMOUNT.value}

            # Validazione campi obbligatori
            missing_fields = [field for field in required_fields if not payment_data.get(field)]
            if missing_fields:
                return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."


            # Validazione Importo
            if DBPaymentsColumns.PAYMENT_AMOUNT.value in payment_data:
                amount = payment_data[DBPaymentsColumns.PAYMENT_AMOUNT.value]
                if amount and not ValidationUtils.validate_amount(amount):
                    return False, "L'importo inserito non è valido."

            payment_data[DBPaymentsColumns.UPDATED_AT.value] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Invoca il metodo del model per aggiornare l'utente
            self.db_model.update_payment(payment_id, **payment_data)
            return True, "Pagamento aggiornato con successo!"

        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento del pagamento: {str(e)}"

    def delete_payment(self, payment_id):
        try:
            # Ottieni il risultato dal model
            result = self.db_model.delete_payment(payment_id)
            if result:
                return True, "Pagamento eliminato con successo."  # Successo
            else:
                return False, "Pagamento non trovato o errore durante l'eliminazione."  # Fallimento
        except Exception as e:
            return False, f"Errore durante l'eliminazione del pagamento: {str(e)}"  # Eccezione
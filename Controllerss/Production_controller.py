from Gestionale_Enums import*
from QueryServices.Clients_query_service import ClientQueryService
from Utils.Validation_utils import ValidationUtils
from Model import DatabaseModel
from datetime import datetime

class ProductionController:

    def __init__(self,  db_model: DatabaseModel, client_query_service:ClientQueryService):
        self.db_model:DatabaseModel = db_model
        self.client_query_service:ClientQueryService = client_query_service

        # i dati aggregati sono variabili di classe, aggiornati ogni volta che viene fatto un save di una nuova fattura
        self.productions_aggregated_data = {}
        self.CY_productions_aggregated_data = {}

    def save_production(self, production_data):
        """
        Gestisce il salvataggio di una produzione, con validazioni di primo livello.
        :param production_data: Dizionario contenente i dati della produzione
        :return: Tuple (success, message), dove success è True/False
        """

        # Campi obbligatori (solo quelli modellati tramite entry)
        self.required_fields = {"NOME CLIENTE", DBProductionsColumns.NAME.value, DBProductionsColumns.HOURS.value, DBProductionsColumns.TOTALE_PREVENTIVO.value}

        # Validazione dei campi obbligatori
        missing_fields = [field for field in self.required_fields if not production_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        # Validazione importi
        tot_preventivo = production_data.get(DBProductionsColumns.TOTALE_PREVENTIVO.value)
        if not ValidationUtils.validate_amount(tot_preventivo):
            return False, "L'importo del preventivo non è valido"

        #validazione hours
        hours = production_data.get(DBProductionsColumns.HOURS.value)
        if not ValidationUtils.validate_integers(tot_preventivo):
            return False, "Il monte ore non è valido"

        # prendo i dati necessari del cliente
        nome_cliente = production_data.get("NOME CLIENTE")
        cliente_list = self.client_query_service.retrieve_client_by_name(nome_cliente)
        cliente_map = self.client_query_service.retrieve_client_map_by_id(cliente_list[0])
        id_cliente = cliente_map[DBClientsColumns.ID.value]
        tipologia_cliente = cliente_map[DBClientsColumns.TIPOLOGIA.value]

        #aggiungo al nome della produzione il nome del cliente
        prod_name = production_data.get(DBProductionsColumns.NAME.value)
        prod_name = nome_cliente + " - " + prod_name

        production_data_prepared = {
            DBProductionsColumns.NAME.value : prod_name,
            DBProductionsColumns.CLIENT_ID.value: id_cliente,
            DBProductionsColumns.HOURS.value: production_data.get(DBProductionsColumns.HOURS.value),
            DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value: production_data.get(DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value),
            DBProductionsColumns.TIPOLOGIA_OUTPUT.value: production_data.get(DBProductionsColumns.TIPOLOGIA_OUTPUT.value),
            DBProductionsColumns.STATO.value: production_data.get(DBProductionsColumns.STATO.value),
            DBProductionsColumns.END_DATE.value: production_data.get(DBProductionsColumns.END_DATE.value),
            DBProductionsColumns.TOTALE_PREVENTIVO.value: production_data.get(DBProductionsColumns.TOTALE_PREVENTIVO.value),
        }

        try:
            self.db_model.add_production(**production_data_prepared)
            return True, "Produzione salvata con successo!"
        except Exception as e:
            return False, f"Errore durante il salvataggio: {str(e)}"

    def update_production(self, production_id, production_data):
        """
        Aggiorna i dati di una produzione esistente.
        :param production_id: ID della produzione da aggiornare
        :param production_data: Dizionario contenente i dati da aggiornare
        :return: Tuple (success, message), dove success è True/False
        """
        try:
            # Controllo validità payment_id
            if not production_id or not isinstance(production_id, int):
                return False, "ID pagamento non valido. Deve essere un intero positivo."

            required_fields = {DBProductionsColumns.NAME.value, DBProductionsColumns.HOURS.value, DBProductionsColumns.TOTALE_PREVENTIVO.value}

            # Validazione campi obbligatori
            missing_fields = [field for field in required_fields if not production_data.get(field)]
            if missing_fields:
                return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."


            # Validazione ore di lavoro
            if DBProductionsColumns.HOURS.value in production_data:
                hours = production_data[DBProductionsColumns.HOURS.value]
                if hours and not ValidationUtils.validate_amount(hours):
                    return False, "L'importo orario inserito non è valido, inserire un valore numerico"

            # Validazione Importo
            if DBProductionsColumns.TOTALE_PREVENTIVO.value in production_data:
                amount = production_data[DBProductionsColumns.TOTALE_PREVENTIVO.value]
                if amount and not ValidationUtils.validate_amount(amount):
                    return False, "L'importo del preventivo inserito non è valido."

            production_data[DBProductionsColumns.UPDATED_AT.value] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Invoca il metodo del model per aggiornare l'utente
            self.db_model.update_production(production_id, **production_data)
            return True, "Produzione aggiornata con successo!"

        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento della produzione: {str(e)}"

    def delete_production(self, production_id):
        return self.db_model.remove_production(production_id)

    def update_specific_production_data(self, production_id, production_data):
        try:
            self.db_model.update_production(production_id, **production_data)
            return True, "Produzione aggiornata con successo!"
        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento della produzione: {str(e)}"


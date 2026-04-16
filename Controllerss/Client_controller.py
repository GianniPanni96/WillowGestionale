from Model import DatabaseModel
from Gestionale_Enums import*
from Utils.Validation_utils import ValidationUtils

class ClientController:

    def __init__(self, db_model: DatabaseModel):
        """Inizializza il controller con il modello del database"""
        self.db_model = db_model

    def save_client(self, client_data):
        """
        Gestisce il salvataggio di un cliente, con validazioni di primo livello.
        :param client_data: Dizionario contenente i dati del cliente
        :return: Tuple (success, message), dove success è True/False
        """
        # Campi obbligatori
        required_fields = {DBClientsColumns.SETTORE.value, DBClientsColumns.NAME.value, DBClientsColumns.TIPOLOGIA.value}

        # Validazione dei campi obbligatori
        missing_fields = [field for field in required_fields if not client_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        # Validazione Partita IVA
        partita_iva = client_data.get(DBClientsColumns.PARTITA_IVA.value)
        if partita_iva and not ValidationUtils.validate_partita_iva(partita_iva):
            return False, "La partita IVA non è valida. Deve contenere esattamente 11 cifre."

        # Validazione Email
        email = client_data.get(DBClientsColumns.EMAIL.value)
        if email and not ValidationUtils.validate_email(email):
            return False, "L'indirizzo email non è valido."

        # Validazione contatto referente (se presente)
        contatto_referente = client_data.get(DBClientsColumns.CONTATTO_REFERENTE.value)
        if contatto_referente and not ValidationUtils.validate_phone_number(contatto_referente):
            return False, "Il contatto del referente non è valido. Deve essere un numero di telefono valido."

        # Preparazione dei dati per il salvataggio
        client_data_filtered = {
            column.value: client_data.get(column.value)
            for column in DBClientsColumns
            if column.value in client_data
        }

        # Rimuove i campi None
        client_data_filtered = {key: value for key, value in client_data_filtered.items() if value is not None}

        # Salvataggio nel DB
        try:
            self.db_model.add_client(**client_data_filtered)
            #self.update_clients_list()
            return True, "Cliente salvato con successo!"
        except Exception as e:
            return False, f"Errore durante il salvataggio del cliente: {str(e)}"

    def delete_client(self, client_id):
        return self.db_model.remove_client(client_id)

    def update_client(self, client_id, client_data):
        """
        Aggiorna i dati di un cliente esistente.
        :param client_id: ID del cliente da aggiornare
        :param client_data: Dizionario contenente i dati da aggiornare
        :return: Tuple (success, message), dove success è True/False
        """
        try:
            # Controllo validità
            if not client_id or not isinstance(client_id, int):
                return False, "ID cliente non valido. Deve essere un intero positivo."

            required_fields = {DBClientsColumns.NAME.value}

            # Validazione campi obbligatori
            missing_fields = [field for field in required_fields if not client_data.get(field)]
            if missing_fields:
                return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

            # Invoca il metodo del model per aggiornare l'utente
            self.db_model.update_client(client_id, **client_data)
            return True, "Cliente aggiornato con successo!"

        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento del cliente: {str(e)}"

    def print_cliente(self, client):
        """
        Stampa a scopo di debug il cliente passato come argomento.
        :param client: Dizionario contenente i dati del cliente.
        """
        if not client:
            return "Cliente non trovato."

        # Genera la stringa formattata usando l'enum DBClientsColumns
        printed_string = "\n".join(
            f"{column.value}: {client.get(column.value, 'N/A')}"
            for column in DBClientsColumns
        )

        print(printed_string)
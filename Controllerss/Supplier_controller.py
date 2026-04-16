from Gestionale_Enums import*
from Utils.Validation_utils import ValidationUtils
from Model import DatabaseModel

class SupplierController:

    def __init__(self, db_model:DatabaseModel):
        self.db_model = db_model

    def save_supplier(self, supplier_data):
        """
        Gestisce il salvataggio di un fornitore, con validazioni di primo livello.
        :param supplier_data: Dizionario contenente i dati del supplier
        :return: Tuple (success, message), dove success è True/False
        """
        # Campi obbligatori
        required_fields = {DBSuppliersColumns.NAME.value}

        # Validazione dei campi obbligatori
        missing_fields = [field for field in required_fields if not supplier_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        # Validazione Partita IVA
        partita_iva = supplier_data.get(DBSuppliersColumns.PARTITA_IVA.value)
        if partita_iva and not ValidationUtils.validate_partita_iva(partita_iva):
            return False, "La partita IVA non è valida. Deve contenere esattamente 11 cifre."


        # Preparazione dei dati per il salvataggio
        supplier_data_filtered = {
            column.value: supplier_data.get(column.value)
            for column in DBSuppliersColumns
            if column.value in supplier_data
        }

        # Rimuove i campi None
        supplier_data_filtered = {key: value for key, value in supplier_data_filtered.items() if value is not None}

        # Salvataggio nel DB
        try:
            self.db_model.add_supplier(**supplier_data_filtered)
            return True, "Fornitore salvato con successo!"
        except Exception as e:
            return False, f"Errore durante il salvataggio del fornitore: {str(e)}"

    def update_supplier(self, supplier_id, supplier_data):
        """
        Aggiorna i dati di un fornitore esistente.
        :param supplier_id: ID del fornitore da aggiornare
        :param supplier_data: Dizionario contenente i dati da aggiornare
        :return: Tuple (success, message), dove success è True/False
        """
        try:
            # Controllo validità
            if not supplier_id or not isinstance(supplier_id, int):
                return False, "ID fornitore non valido. Deve essere un intero positivo."

            required_fields = {DBSuppliersColumns.NAME.value}

            # Validazione campi obbligatori
            missing_fields = [field for field in required_fields if not supplier_data.get(field)]
            if missing_fields:
                return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

            # Invoca il metodo del model per aggiornare l'utente
            self.db_model.update_supplier(supplier_id, **supplier_data)
            return True, "Fornitore aggiornato con successo!"

        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento del fornitore: {str(e)}"

    def delete_supplier(self, supplier_id):
        return self.db_model.remove_supplier(supplier_id)

    def delete_supplier_by_id(self, supplier_id):
        """Elimina un supplier dato il suo ID."""
        table = "suppliers"
        try:
            self.db_model.delete_row(table, DBSuppliersColumns.ID.value, supplier_id)
            print(f"Supplier {supplier_id} rimosso con successo")
            return True, f"Supplier {supplier_id} rimosso con successo"
        except Exception as e:
            return False, f"Errore durante l'eliminazione del supplier: {str(e)}"
import requests
import json
from enum import Enum


class FatturazioneElettronicaProvider(Enum):
    NESSUNO = "nessuno"
    ARUBA = "aruba"


class ArubaFatturazioneAPI:
    """
    Gestisce l'interazione con l'API REST di Aruba Fatturazione Elettronica.
    """

    def __init__(self, base_url, api_key):
        """
        Inizializza la classe con i dettagli dell'API.

        :param base_url: URL di base per l'API di Aruba.
        :param api_key: Token di autenticazione API.
        """
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def fetch_fatture(self, utente_id):
        """
        Recupera tutte le fatture associate a un utente specifico.

        :param utente_id: ID dell'utente di cui recuperare le fatture.
        :return: Lista delle fatture o errore.
        """
        endpoint = f"{self.base_url}/fatture/{utente_id}"
        try:
            response = requests.get(endpoint, headers=self.headers)
            response.raise_for_status()
            return response.json()  # Restituisce i dati in formato JSON
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error: {http_err}")
        except Exception as err:
            print(f"Errore generico: {err}")
        return None

    def create_fattura(self, fattura_data):
        """
        Crea una nuova fattura per un utente.

        :param fattura_data: Dizionario contenente i dettagli della fattura.
        :return: Risultato della creazione.
        """
        endpoint = f"{self.base_url}/fatture"
        try:
            response = requests.post(endpoint, headers=self.headers, data=json.dumps(fattura_data))
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error: {http_err}")
        except Exception as err:
            print(f"Errore generico: {err}")
        return None

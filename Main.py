import threading
from Model import DatabaseModel
from Views.View import MainWindow
import os, re, json
from typing import List
from dataclasses import dataclass, field



class BackupScheduler:
    def __init__(self, interval_minutes, max_backups, backup_base_path, delta_days):
        """
        Classe che gestisce l'intervallo di tempo con cui i backups vengono creati su un thread separato dal main.
        :param interval_minutes: Intervallo di tempo tra i backup, in minuti.
        :param max_backups: Numero massimo di backup da conservare.
        """
        self.interval_seconds = interval_minutes * 60  # Converti minuti in secondi
        self.max_backups = max_backups
        self.backup_base_path = backup_base_path
        self.delta_days = delta_days
        self.stop_event = threading.Event()
        self.backup_thread = None

    def start(self):
        """Avvia la programmazione dei backup."""
        self.stop_event.clear()
        self._schedule_backup()

    def stop(self):
        """Ferma la programmazione dei backup."""
        self.stop_event.set()
        if self.backup_thread:
            self.backup_thread.join()

    def _schedule_backup(self):
        """Pianifica il prossimo backup."""
        if not self.stop_event.is_set():
            self.backup_thread = threading.Timer(self.interval_seconds, self._execute_backup)
            self.backup_thread.start()

    def _execute_backup(self):
        """Esegue il backup e pianifica il successivo."""
        try:
            print("Esecuzione del backup...")
            DatabaseModel.backup_gestionale_db(self.max_backups, self.backup_base_path, self.delta_days)
            print("Backup completato.")
        except Exception as e:
            print(f"Errore durante il backup: {e}")
        finally:
            self._schedule_backup()  # Pianifica il prossimo backup


class ConfigManager:
    """
    Gestisce il caricamento e il salvataggio delle impostazioni dell'applicazione tramite un file JSON.
    Attributi:
        CONFIG_FILE (str): Percorso del file di configurazione.
    """

    def __init__(self):
        """
        Inizializza la classe ConfigManager e imposta il percorso del file di configurazione.
        """
        # Nome della variabile d'ambiente
        self.DB_PATH_ENV_VAR = "GESTIONALE_DB_PATH"

        # Ottieni il percorso del database dalla variabile d'ambiente
        self.db_path = os.environ.get(self.DB_PATH_ENV_VAR)
        if not self.db_path:
            raise EnvironmentError(f"La variabile d'ambiente {self.DB_PATH_ENV_VAR} non è impostata.")

        self.CONFIG_FILE = os.path.join(self.db_path, "app_config.json")

    def load_config(self):
        """Carica le impostazioni dal file di configurazione."""
        if not os.path.exists(self.CONFIG_FILE):
            print("File di configurazione non trovato. Creazione di un file predefinito...")
            default_config = {
                "backup_settings": {
                    "backup_base_path": {
                        "value": os.path.join(self.db_path, "backups"),
                        "description": "Percorso dove verranno salvati i backup del database gestionale."
                    },
                    "interval_minutes": {
                        "value": 6,
                        "description": "Intervallo in minuti tra l'esecuzione dei backup."
                    },
                    "max_backups": {
                        "value": 35,
                        "description": "Numero massimo di backup da conservare per ogni intervallo."
                    },
                    "delta_days": {
                        "value": 7,
                        "description": "Intervallo di tempo in giorni per organizzare i backup in cartelle separate."
                    }
                },
                "fiscal_settings": {
                    "aliquota_iva": {
                        "value": 0.22,
                        "description": "Aliquota IVA standard applicata alle fatture (22%)."
                    },
                    "partita_iva_forfettaria": {
                        "aliquota_irpef_min": {
                            "value": 0.05,
                            "description": "Aliquota IRPEF minima per partite IVA forfettarie, applicata nei primi anni (5%)."
                        },
                        "aliquota_irpef_max": {
                            "value": 0.15,
                            "description": "Aliquota IRPEF massima per partite IVA forfettarie, applicata dopo il periodo agevolato (15%)."
                        },
                        "anni_agevolazione": {
                            "value": 5,
                            "description": "Numero di anni durante i quali si applica la tariffa agevolata per il regime forfettario."
                        },
                        "aliquota_inps": {
                            "value": 0.2607,
                            "description": "Contributo INPS per partite IVA forfettarie (26.07%)."
                        },
                        "aliquota_rivalsa_inps": {
                            "value": 0.04,
                            "description": "Aliquota per rivalsa INPS per p. iva forfettarie."
                        },
                        "imponibile": {
                            "value": 0.78,
                            "description": "Percentuale dell'imponibile considerata per il calcolo fiscale nel regime forfettario (78%)."
                        }
                    },
                    "partita_iva_ordinaria": {
                        "aliquota_irpef_1": {
                            "value": 0.23,
                            "description": "Aliquota IRPEF per il primo scaglione di reddito (ipotesi per il 2025, 23%)."
                        },
                        "aliquota_irpef_2": {
                            "value": 0.27,
                            "description": "Aliquota IRPEF per il secondo scaglione di reddito (ipotesi per il 2025, 27%)."
                        },
                        "aliquota_irpef_3": {
                            "value": 0.38,
                            "description": "Aliquota IRPEF per il terzo scaglione di reddito (ipotesi per il 2025, 38%)."
                        },
                        "aliquota_inps": {
                            "value": 0.2607,
                            "description": "Contributo INPS per partite IVA ordinarie (26.07%)."
                        },
                        "aliquota_cassa_inps": {
                            "value": 0.04,
                            "description": "Aliquota per la cassa INPS (4%)."
                        },
                        "aliquota_ritenuta": {
                            "value": 0.2,
                            "description": "Aliquota per la ritenuta d'acconto (20%)."
                        },
                        "imponibile_iva": {
                            "value": 1,
                            "description": "Coefficiente per il calcolo dell'imponibile IVA (100%)."
                        },
                        "imponibile_ritenuta_acconto": {
                            "value": 1,
                            "description": "Coefficiente per il calcolo dell'imponibile per la ritenuta d'acconto (100%)."
                        },
                        "imponibile_cassa_inps": {
                            "value": 1,
                            "description": "Coefficiente per il calcolo dell'imponibile per la cassa INPS (100%)."
                        }
                    }
                },
                "clients_business_sectors": {
                    "AEROSPACE": "Aerospaziale e Difesa",
                    "AGRICULTURE": "Agricoltura e Allevamento",
                    "CREATIVE_AGENCY": "Agenzia Creativa",
                    "FOOD_AND_BEVERAGE": "Alimentare e Bevande",
                    "AUTOMOTIVE": "Automobilistico",
                    "CHEMICAL": "Chimico",
                    "RETAIL": "Commercio al Dettaglio",
                    "WHOLESALE": "Commercio all'Ingrosso",
                    "CONSULTING": "Consulenza e Servizi Professionali",
                    "CONSTRUCTION": "Costruzioni e Edilizia",
                    "ENERGY": "Energia e Risorse Naturali",
                    "PHARMACEUTICAL": "Farmaceutico",
                    "FINANCE": "Finanza e Assicurazioni",
                    "GOVERNMENT": "Governo e Settore Pubblico",
                    "REAL_ESTATE": "Immobiliare",
                    "EDUCATION": "Istruzione e Formazione",
                    "ENTERTAINMENT": "Intrattenimento e Media",
                    "MANUFACTURING": "Manifatturiero e Produzione",
                    "NON_PROFIT": "Organizzazioni Non Profit",
                    "RESEARCH_AND_DEVELOPMENT": "Ricerca e Sviluppo",
                    "HEALTHCARE": "Sanità e Servizi Medici",
                    "ENVIRONMENTAL_SERVICES": "Servizi Ambientali",
                    "SECURITY": "Sicurezza e Vigilanza",
                    "SPORTS": "Sport e Benessere",
                    "INFORMATION_TECHNOLOGY": "Tecnologia dell'Informazione (IT)",
                    "TELECOMMUNICATIONS": "Telecomunicazioni",
                    "TEXTILE": "Tessile e Abbigliamento",
                    "TOURISM": "Turismo e Ospitalità",
                    "TRANSPORTATION": "Trasporti e Logistica"
                },
                "production_types": {
                    "PRODUZIONE": "PRODUZIONE",
                    "POST_PRODUZIONE": "POST_PRODUZIONE",
                    "MISTA": "MISTA",
                    "CONSULENZA": "CONSULENZA"
                },
                "output_types": {
                    "VIDEO_MUSICALE": "VIDEO_MUSICALE",
                    "ADV_SOCIAL": "ADV_SOCIAL",
                    "COMMERCIAL": "COMMERCIAL",
                    "INTEGRAZIONE_VFX": "INTEGRAZIONE_VFX"
                }
            }
            self.save_config(default_config)
            return default_config

        with open(self.CONFIG_FILE, "r", encoding="utf-8") as file:
            return json.load(file)

    def save_config(self, config):
        """Salva le impostazioni nel file di configurazione."""
        with open(self.CONFIG_FILE, "w", encoding="utf-8") as file:
            json.dump(config, file, indent=4)

    def update_config_section(self, section_key: str, new_section_data: dict):
        """
        Aggiorna una specifica sezione della configurazione modificando solamente il campo "value"
        di ciascuna impostazione.

        :param section_key: Nome della sezione da aggiornare (es. "backup_settings").
        :param new_section_data: Dizionario contenente i nuovi valori, ad es.
                                 {"backup_base_path": "nuovo/percorso", "interval_minutes": 10, ...}
        :raises Exception: Se si verifica un errore durante il salvataggio (ad es. file bloccato).
        """
        try:
            # Carica la configurazione corrente
            current_config = self.load_config()

            # Se la sezione non esiste, la inizializza
            if section_key not in current_config:
                current_config[section_key] = {}

            # Aggiorna ciascun campo nella sezione: modifica soltanto il campo "value"
            for key, new_val in new_section_data.items():
                if key in current_config[section_key] and isinstance(current_config[section_key][key], dict):
                    current_config[section_key][key]["value"] = new_val
                else:
                    # Se la chiave non esiste, la crea con una description vuota (o un valore di default)
                    current_config[section_key][key] = {"value": new_val, "description": ""}

            # Prova a salvare l'intera configurazione
            self.save_config(current_config)

        except Exception as e:
            # Solleva un'eccezione con un messaggio esplicativo in caso di errore (es. file lock)
            raise Exception(f"Errore durante il salvataggio della sezione '{section_key}': {str(e)}")

    def update_fiscal_settings(self, new_fiscal_data: dict):
        """
        Aggiorna la sezione "fiscal_settings" della configurazione, sostituendo
        il valore ("value") di ciascun campo con quello fornito nel dizionario in ingresso.

        Per i campi della sotto-sezione "partita_iva_ordinaria" che corrispondono al pattern
        "aliquota_irpef_<numero>", vengono aggiornati anche "reddito_min", "reddito_max" e "description".
        Inoltre, se nella configurazione corrente esiste uno scaglione IRPEF che non è presente nel dizionario
        passato (cioè è stato eliminato dall'interfaccia), esso viene rimosso.

        Il dizionario in ingresso deve avere una struttura simile a:

        {
          "aliquota_iva": {"value": ...},
          "partita_iva_forfettaria": {
                "aliquota_irpef_min": {"value": ...},
                "aliquota_irpef_max": {"value": ...},
                "anni_agevolazione": {"value": ...},
                "aliquota_inps": {"value": ...},
                "imponibile": {"value": ...}
          },
          "partita_iva_ordinaria": {
                "aliquota_irpef_1": {"value": ..., "reddito_min": ..., "reddito_max": ..., "description": ...},
                "aliquota_irpef_2": {"value": ..., "reddito_min": ..., "reddito_max": ..., "description": ...},
                // Altri parametri fissi:
                "aliquota_inps": {"value": ...},
                "aliquota_cassa_inps": {"value": ...},
                "aliquota_ritenuta": {"value": ...},
                // Imponibili:
                "imponibile_iva": {"value": ...},
                "imponibile_ritenuta_acconto": {"value": ...},
                "imponibile_cassa_inps": {"value": ...},
                "imponibile_inps": {"value": ...},
                "imponibile_irpef": {"value": ...}
          }
        }

        In particolare, per la sezione non ordinaria (ad es. "aliquota_iva") se la chiave è "value"
        allora si aggiorna direttamente (senza incapsularlo in un ulteriore dizionario), così da mantenere la struttura originale:

        "aliquota_iva": {
             "value": <nuovo_valore>,
             "description": <descrizione_esistente>
        }

        Solleva un'eccezione in caso di errore.
        """
        try:
            # Carica la configurazione attuale
            current_config = self.load_config()

            # Assicura che la sezione "fiscal_settings" esista
            if "fiscal_settings" not in current_config:
                current_config["fiscal_settings"] = {}

            # Per ogni sotto-sezione (es. "aliquota_iva", "partita_iva_forfettaria", "partita_iva_ordinaria")
            for section_key, new_section in new_fiscal_data.items():
                if section_key not in current_config["fiscal_settings"]:
                    current_config["fiscal_settings"][section_key] = {}
                for key, new_val in new_section.items():
                    # Se il valore passato non è un dizionario, lo incapsuliamo
                    if not isinstance(new_val, dict):
                        new_val = {"value": new_val}

                    # Special handling per gli scaglioni IRPEF nella sezione "partita_iva_ordinaria"
                    if section_key == "partita_iva_ordinaria" and re.match(r'^aliquota_irpef_\d+$', key):
                        if key in current_config["fiscal_settings"][section_key] and isinstance(
                                current_config["fiscal_settings"][section_key][key], dict):
                            current_config["fiscal_settings"][section_key][key]["value"] = new_val.get("value",
                                                                                                       current_config[
                                                                                                           "fiscal_settings"][
                                                                                                           section_key][
                                                                                                           key].get(
                                                                                                           "value", ""))
                            current_config["fiscal_settings"][section_key][key]["reddito_min"] = new_val.get(
                                "reddito_min",
                                current_config["fiscal_settings"][section_key][key].get("reddito_min", ""))
                            current_config["fiscal_settings"][section_key][key]["reddito_max"] = new_val.get(
                                "reddito_max",
                                current_config["fiscal_settings"][section_key][key].get("reddito_max", ""))
                            current_config["fiscal_settings"][section_key][key]["description"] = new_val.get(
                                "description",
                                current_config["fiscal_settings"][section_key][key].get("description", ""))
                        else:
                            current_config["fiscal_settings"][section_key][key] = {
                                "value": new_val.get("value", ""),
                                "reddito_min": new_val.get("reddito_min", ""),
                                "reddito_max": new_val.get("reddito_max", ""),
                                "description": new_val.get("description", "")
                            }
                    else:
                        # Per le altre sotto-sezioni: se la chiave è "value" e la sezione non è "partita_iva_ordinaria",
                        # aggiorniamo direttamente, in modo da non incapsulare il nuovo valore in un dizionario.
                        if key == "value" and section_key != "partita_iva_ordinaria":
                            # Se esiste già, aggiorniamo il valore mantenendo la descrizione esistente, se presente.
                            if key in current_config["fiscal_settings"][section_key]:
                                # Se il valore esistente è un dizionario, aggiorniamo il campo "value"
                                if isinstance(current_config["fiscal_settings"][section_key][key], dict):
                                    current_config["fiscal_settings"][section_key][key]["value"] = new_val.get("value",
                                                                                                               new_val)
                                else:
                                    current_config["fiscal_settings"][section_key][key] = new_val.get("value", new_val)
                            else:
                                current_config["fiscal_settings"][section_key][key] = new_val.get("value", new_val)
                        else:
                            # Per gli altri campi: aggiorna soltanto "value" all'interno del dizionario
                            if key in current_config["fiscal_settings"][section_key]:
                                if isinstance(current_config["fiscal_settings"][section_key][key], dict):
                                    current_config["fiscal_settings"][section_key][key]["value"] = new_val.get("value",
                                                                                                               current_config[
                                                                                                                   "fiscal_settings"][
                                                                                                                   section_key][
                                                                                                                   key].get(
                                                                                                                   "value",
                                                                                                                   ""))
                                else:
                                    current_config["fiscal_settings"][section_key][key] = {
                                        "value": new_val.get("value", new_val), "description": ""}
                            else:
                                current_config["fiscal_settings"][section_key][key] = {
                                    "value": new_val.get("value", new_val), "description": ""}

                # Se la sezione è "partita_iva_ordinaria", rimuoviamo eventuali scaglioni IRPEF
                # presenti nel file corrente ma non nel dizionario new_section (cioè cancellati dall'interfaccia)
                if section_key == "partita_iva_ordinaria":
                    current_irpef_keys = [k for k in current_config["fiscal_settings"][section_key].keys() if
                                          re.match(r'^aliquota_irpef_\d+$', k)]
                    new_irpef_keys = set([k for k in new_section.keys() if re.match(r'^aliquota_irpef_\d+$', k)])
                    for k in current_irpef_keys:
                        if k not in new_irpef_keys:
                            del current_config["fiscal_settings"][section_key][k]

            self.save_config(current_config)

        except Exception as e:
            raise Exception(f"Errore durante l'aggiornamento dei dati fiscali: {str(e)}")

    def update_list_field(self, section_name: str, key: str, value: str = None, operation: str = "update"):
        """
        Aggiorna, aggiunge o elimina un elemento all'interno di una sezione della configurazione che rappresenta un elenco.

        :param section_name: Nome della sezione (es. "clients_business_sectors", "production_types", "output_types").
        :param key: Chiave dell'elemento da aggiornare/agginungere/eliminare.
        :param value: Nuovo valore associato alla chiave. Non è necessario se operation è "delete".
        :param operation: Operazione da eseguire: "update" (aggiunge o modifica) oppure "delete" (elimina).
        :raises Exception: Se l'operazione non è riconosciuta.
        """
        # Carica la configurazione corrente
        config = self.load_config()

        # Se la sezione non esiste, la crea (solo per operazioni di update)
        if section_name not in config:
            if operation == "update":
                config[section_name] = {}
            else:
                raise Exception(f"La sezione '{section_name}' non esiste.")

        # Operazioni di update/aggiunta
        if operation == "update":
            config[section_name][key] = value
        # Operazione di eliminazione
        elif operation == "delete":
            if key in config[section_name]:
                del config[section_name][key]
            else:
                print(f"Chiave '{key}' non trovata in '{section_name}'. Nessuna operazione eseguita.")
        else:
            raise Exception("Operazione non riconosciuta. Utilizzare 'update' o 'delete'.")

        # Salva la configurazione aggiornata
        self.save_config(config)


@dataclass
class PartitaIVAForfettaria:
    aliquota_irpef_min: float
    aliquota_irpef_max: float
    anni_agevolazione: int
    aliquota_inps: float
    imponibile: float
    aliquota_rivalsa_inps : float

    @staticmethod
    def from_dict(data: dict):
        return PartitaIVAForfettaria(
            aliquota_irpef_min=data.get("aliquota_irpef_min", {}).get("value", 0.0),
            aliquota_irpef_max=data.get("aliquota_irpef_max", {}).get("value", 0.0),
            anni_agevolazione=data.get("anni_agevolazione", {}).get("value", 0),
            aliquota_inps=data.get("aliquota_inps", {}).get("value", 0.0),
            imponibile=data.get("imponibile", {}).get("value", 0.0),
            aliquota_rivalsa_inps = data.get("aliquota_rivalsa_inps", {}).get("value", 0.0)
        )

@dataclass
class ScaglioneIrpef:
    value: float
    reddito_min: float
    reddito_max: float
    description: str

    @staticmethod
    def from_dict(data: dict) -> 'ScaglioneIrpef':
        # Gestione del valore "infinito" per reddito_max:
        reddito_max_raw = data.get("reddito_max")
        if isinstance(reddito_max_raw, str):
            # Rimuove eventuali spazi e il segno '+' e controlla se si tratta di "infinity"
            if reddito_max_raw.strip().lower().replace("+", "") == "infinity":
                reddito_max_val = float("inf")
            else:
                try:
                    reddito_max_val = float(reddito_max_raw)
                except ValueError:
                    reddito_max_val = float("inf")
        elif reddito_max_raw is None:
            # Se non viene specificato il limite superiore, lo interpretiamo come infinito
            reddito_max_val = float("inf")
        else:
            reddito_max_val = reddito_max_raw

        return ScaglioneIrpef(
            value=data.get("value", 0.0),
            reddito_min=data.get("reddito_min", 0.0),
            reddito_max=reddito_max_val,
            description=data.get("description", "")
        )

@dataclass
class PartitaIVAOrdinaria:
    # Lista degli scaglioni IRPEF (procedurale: da 1 a n)
    scaglioni_irpef: List[ScaglioneIrpef] = field(default_factory=list)
    aliquota_inps: float = 0.0
    aliquota_cassa_inps: float = 0.0
    aliquota_ritenuta: float = 0.0
    imponibile_iva: float = 0.0
    imponibile_ritenuta_acconto: float = 0.0
    imponibile_cassa_inps: float = 0.0
    imponibile_inps: float = 0.0
    imponibile_irpef: float = 0.0

    @staticmethod
    def from_dict(data: dict) -> 'PartitaIVAOrdinaria':
        scaglioni = []
        # Cerchiamo tutte le chiavi che corrispondono al pattern "aliquota_irpef_<numero>"
        pattern = re.compile(r"aliquota_irpef_(\d+)$")
        for key, value in data.items():
            match = pattern.match(key)
            if match and isinstance(value, dict):
                index = int(match.group(1))
                scaglione = ScaglioneIrpef.from_dict(value)
                scaglioni.append((index, scaglione))
        # Ordina gli scaglioni per indice
        scaglioni.sort(key=lambda x: x[0])
        scaglioni_list = [s for idx, s in scaglioni]

        return PartitaIVAOrdinaria(
            scaglioni_irpef=scaglioni_list,
            aliquota_inps=data.get("aliquota_inps", {}).get("value", 0.0),
            aliquota_cassa_inps=data.get("aliquota_cassa_inps", {}).get("value", 0.0),
            aliquota_ritenuta=data.get("aliquota_ritenuta", {}).get("value", 0.0),
            imponibile_iva=data.get("imponibile_iva", {}).get("value", 0.0),
            imponibile_ritenuta_acconto=data.get("imponibile_ritenuta_acconto", {}).get("value", 0.0),
            imponibile_cassa_inps=data.get("imponibile_cassa_inps", {}).get("value", 0.0),
            imponibile_inps=data.get("imponibile_inps", {}).get("value", 0.0),
            imponibile_irpef = data.get("imponibile_irpef", {}).get("value", 0.0)
        )

@dataclass
class FiscalSettings:
    aliquota_iva: float
    partita_iva_forfettaria: PartitaIVAForfettaria
    partita_iva_ordinaria: PartitaIVAOrdinaria

    @staticmethod
    def from_dict(data: dict):
        fiscal_data = data or {}
        return FiscalSettings(
            aliquota_iva=fiscal_data.get("aliquota_iva", {}).get("value", 0.0),
            partita_iva_forfettaria=PartitaIVAForfettaria.from_dict(
                fiscal_data.get("partita_iva_forfettaria", {})
            ),
            partita_iva_ordinaria=PartitaIVAOrdinaria.from_dict(
                fiscal_data.get("partita_iva_ordinaria", {})
            )
        )


# Avvia l'applicazione
if __name__ == "__main__":
    # Inizializza il gestore delle configurazioni
    config_manager = ConfigManager()
    config = config_manager.load_config()  # Carica la configurazione

    # Estrai le impostazioni di backup dalla configurazione,
    # recuperando solo il campo "value" di ciascuna impostazione
    backup_settings = config.get("backup_settings", {})
    interval_minutes = backup_settings.get("interval_minutes", {}).get("value", 15)
    max_backups = backup_settings.get("max_backups", {}).get("value", 35)
    backup_base_path = backup_settings.get("backup_base_path", {}).get("value")
    delta_days = backup_settings.get("delta_days", {}).get("value", 7)

    # Estrai le impostazioni fiscali dalla configurazione
    fiscal_config = config.get("fiscal_settings", {})
    # Crea un'istanza di FiscalSettings
    fiscal_settings = FiscalSettings.from_dict(fiscal_config)

    #creo il dizionario degli elenchi
    # Trasforma le sezioni in liste di tuple (chiave, valore)
    clients_business_sectors = [
        (key, value)
        for key, value in config.get("clients_business_sectors", {}).items()
    ]
    productions_types = [
        (key, value)
        for key, value in config.get("production_types", {}).items()
    ]
    productions_outputs_types = [
        (key, value)
        for key, value in config.get("production_output_types", {}).items()
    ]

    catalogo_elenchi = {
        "clients_business_sectors": clients_business_sectors,
        "production_types": productions_types,
        "production_output_types": productions_outputs_types,
    }

    # Inizializza il gestore del backup con i parametri dalla configurazione
    scheduler = BackupScheduler(
        interval_minutes=interval_minutes,
        max_backups=max_backups,
        backup_base_path=backup_base_path,
        delta_days=delta_days
    )

    try:
        print("Avvio dell'applicazione e scheduler dei backup...")

        # Avvia il backup in un thread separato
        backup_thread = threading.Thread(target=scheduler.start, daemon=True)
        backup_thread.start()

        # Avvia il frontend
        app = MainWindow(config_manager, fiscal_settings, catalogo_elenchi)
        app.mainloop()

    except KeyboardInterrupt:
        print("Interruzione manuale. Fermando il backup...")
        scheduler.stop()

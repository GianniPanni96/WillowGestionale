import threading
from Model import DatabaseModel
import os, re, json
from typing import List
from dataclasses import dataclass, field
from Controllers import ExpenseController

from typing import Dict
from dataclasses import dataclass


class BackupScheduler:
    def __init__(self, interval_minutes, max_backups, backup_base_path, delta_days):
        """
        Gestisce il scheduling di backup in un thread separato.
        :param interval_minutes: Intervallo tra backup, in minuti.
        :param max_backups: Numero massimo di backup da mantenere.
        :param backup_base_path: Cartella base dove salvare i backup.
        :param delta_days: Intervallo di giorni per suddividere i backup in sub‐cartelle.
        """
        self.interval_seconds = interval_minutes * 60
        self.max_backups = max_backups
        self.backup_base_path = backup_base_path
        self.delta_days = delta_days

        self.stop_event = threading.Event()
        self.backup_timer = None

    def start(self):
        """Avvia il ciclo di backup pianificato."""
        self.stop_event.clear()
        self._schedule_backup()

    def stop(self):
        """
        Ferma la pianificazione e esegue un ultimo backup sincrono.
        Chiamala prima di distruggere la GUI.
        """
        # 1) Evita ulteriori pianificazioni
        self.stop_event.set()

        # 2) Annulla il timer pendente
        if self.backup_timer:
            self.backup_timer.cancel()
            self.backup_timer = None

        # 3) Esegui un ultimo backup subito
        try:
            print("Esecuzione backup finale prima della chiusura…")
            os.makedirs(self.backup_base_path, exist_ok=True)
            DatabaseModel.backup_gestionale_db(
                self.max_backups,
                self.backup_base_path,
                self.delta_days
            )
            print("Backup finale completato.")
        except Exception as e:
            print(f"Errore durante il backup finale: {e}")

    def _schedule_backup(self):
        """Pianifica il prossimo timer di backup se non fermato."""
        if not self.stop_event.is_set():
            t = threading.Timer(self.interval_seconds, self._execute_backup)
            t.daemon = True             # <— rendilo daemon
            self.backup_timer = t
            t.start()

    def _execute_backup(self):
        """
        Esegue il backup programmato e, se non fermato, ripianifica il successivo.
        """
        try:
            print("Esecuzione del backup programmato…")
            os.makedirs(self.backup_base_path, exist_ok=True)
            DatabaseModel.backup_gestionale_db(
                self.max_backups,
                self.backup_base_path,
                self.delta_days
            )
            print("Backup completato.")
        except Exception as e:
            print(f"Errore durante il backup programmato: {e}")
        finally:
            # Ripianifica solo se non abbiamo chiamato stop()
            if not self.stop_event.is_set():
                self._schedule_backup()


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
                    "iva": {
                        "aliquota_iva_ordinaria": {
                            "value": 0.22,
                            "description": "Aliquota IVA standard"
                        },
                        "aliquota_iva_ridotta_1": {
                            "value": 0.1,
                            "description": "Aliquota IVA ridotta per turismo, costruzioni edilizie e servizi alimentari"
                        },
                        "aliquota_iva_ridotta_2": {
                            "value": 0.5,
                            "description": "Aliquota IVA ridotta per servizi sociali, sanitari, ed educativi delle cooperative"
                        },
                        "aliquota_iva_minima": {
                            "value": 0.4,
                            "description": "Aliquota IVA ridotta per beni di prima necessità"
                        },
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

        Per la sezione "iva", se viene passato un nuovo valore per ciascuna chiave
        (ad esempio "aliquota_iva_ordinaria", "aliquota_iva_ridotta_1", ecc.),
        il valore viene aggiornato mantenendo la struttura (value, description).

        In particolare, per la sezione non ordinaria se la chiave è "value"
        allora si aggiorna direttamente (senza incapsularlo in un ulteriore dizionario),
        così da mantenere la struttura originale.

        Solleva un'eccezione in caso di errore.
        """
        try:
            # Carica la configurazione attuale
            current_config = self.load_config()

            # Assicura che la sezione "fiscal_settings" esista
            if "fiscal_settings" not in current_config:
                current_config["fiscal_settings"] = {}

            # Aggiorna ogni sotto-sezione
            for section_key, new_section in new_fiscal_data.items():
                if section_key not in current_config["fiscal_settings"]:
                    current_config["fiscal_settings"][section_key] = {}

                # Sezione "partita_iva_ordinaria" (gestione speciale per gli scaglioni IRPEF)
                if section_key == "partita_iva_ordinaria":
                    for key, new_val in new_section.items():
                        if not isinstance(new_val, dict):
                            new_val = {"value": new_val}
                        if re.match(r'^aliquota_irpef_\d+$', key):
                            if key in current_config["fiscal_settings"][section_key] and isinstance(
                                    current_config["fiscal_settings"][section_key][key], dict):
                                current_config["fiscal_settings"][section_key][key]["value"] = new_val.get("value",
                                                                                                           current_config[
                                                                                                               "fiscal_settings"][
                                                                                                               section_key][
                                                                                                               key].get(
                                                                                                               "value",
                                                                                                               ""))
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
                                    current_config["fiscal_settings"][section_key][key] = new_val.get("value", new_val)
                            else:
                                current_config["fiscal_settings"][section_key][key] = {
                                    "value": new_val.get("value", new_val),
                                    "description": ""
                                }
                    # Rimuove eventuali scaglioni IRPEF non presenti nella nuova sezione
                    current_irpef_keys = [k for k in current_config["fiscal_settings"][section_key].keys() if
                                          re.match(r'^aliquota_irpef_\d+$', k)]
                    new_irpef_keys = set([k for k in new_section.keys() if re.match(r'^aliquota_irpef_\d+$', k)])
                    for k in current_irpef_keys:
                        if k not in new_irpef_keys:
                            del current_config["fiscal_settings"][section_key][k]

                # Sezione "iva"
                elif section_key == "iva":
                    for key, new_val in new_section.items():
                        if not isinstance(new_val, dict):
                            new_val = {"value": new_val}
                        if key in current_config["fiscal_settings"][section_key]:
                            if isinstance(current_config["fiscal_settings"][section_key][key], dict):
                                current_config["fiscal_settings"][section_key][key]["value"] = new_val.get("value",
                                                                                                           current_config[
                                                                                                               "fiscal_settings"][
                                                                                                               section_key][
                                                                                                               key].get(
                                                                                                               "value",
                                                                                                               ""))
                                current_config["fiscal_settings"][section_key][key]["description"] = new_val.get(
                                    "description",
                                    current_config["fiscal_settings"][section_key][key].get("description", ""))
                            else:
                                current_config["fiscal_settings"][section_key][key] = {
                                    "value": new_val.get("value", new_val),
                                    "description": new_val.get("description", "")
                                }
                        else:
                            current_config["fiscal_settings"][section_key][key] = {
                                "value": new_val.get("value", new_val),
                                "description": new_val.get("description", "")
                            }

                # Per le altre sotto-sezioni (es. "partita_iva_forfettaria", ecc.)
                else:
                    for key, new_val in new_section.items():
                        if not isinstance(new_val, dict):
                            new_val = {"value": new_val}
                        if key == "value":
                            if key in current_config["fiscal_settings"][section_key]:
                                if isinstance(current_config["fiscal_settings"][section_key][key], dict):
                                    current_config["fiscal_settings"][section_key][key]["value"] = new_val.get("value",
                                                                                                               new_val)
                                else:
                                    current_config["fiscal_settings"][section_key][key] = new_val.get("value", new_val)
                            else:
                                current_config["fiscal_settings"][section_key][key] = new_val.get("value", new_val)
                        else:
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
                                        "value": new_val.get("value", new_val),
                                        "description": ""
                                    }
                            else:
                                current_config["fiscal_settings"][section_key][key] = {
                                    "value": new_val.get("value", new_val),
                                    "description": ""
                                }

            self.save_config(current_config)

        except Exception as e:
            raise Exception(f"Errore durante l'aggiornamento dei dati fiscali: {str(e)}")

    def update_list_field(self, section_name: str, key: str, value: str = None, operation: str = "update"):
        """
        Aggiorna, aggiunge o elimina un elemento all'interno di una sezione della configurazione che rappresenta un elenco.

        :param section_name: Nome della sezione (es. "clients_business_sectors", "production_types", "output_types").
        :param key: Chiave dell'elemento da aggiornare/aggiungere/eliminare.
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

        section_dict = config[section_name]

        # Operazione di aggiornamento o aggiunta
        if operation == "update":
            # Se la chiave esiste già, aggiorna il valore
            if key in section_dict:
                section_dict[key] = value
            else:
                # Nuovo elemento: dobbiamo inserirlo all'inizio, mantenendo l'ultimo elemento trigger immutato
                trigger_key = "ADD_SECTOR"
                # Convertiamo il dizionario in una lista di tuple per preservare l'ordine
                items = list(section_dict.items())
                trigger_item = None

                # Se l'ultimo elemento esiste ed è il trigger, lo rimuoviamo temporaneamente
                if items and items[-1][0] == trigger_key:
                    trigger_item = items.pop(-1)

                # Crea un nuovo dizionario inserendo il nuovo elemento come primo
                new_section = {key: value}
                # Reinserisce i restanti elementi
                for k, v in items:
                    new_section[k] = v
                # Reinserisce il trigger, se presente, in fondo
                if trigger_item:
                    new_section[trigger_item[0]] = trigger_item[1]

                # Aggiorna la sezione nella configurazione
                config[section_name] = new_section

        # Operazione di eliminazione
        elif operation == "delete":
            if key in section_dict:
                del section_dict[key]
            else:
                print(f"Chiave '{key}' non trovata in '{section_name}'. Nessuna operazione eseguita.")
        else:
            raise Exception("Operazione non riconosciuta. Utilizzare 'update' o 'delete'.")

        # Salva la configurazione aggiornata
        self.save_config(config)

        # Salva la configurazione aggiornata
        self.save_config(config)

    def update_recurring_expenses(self, new_recurring_data: dict):
        """
        Aggiorna la sezione "recurring_expenses":
          - se 'description' è in fields, lo salva come scalar
          - per gli altri campi, aggiorna/crea dict {"value":…, "description": ""}
        new_recurring_data deve essere:
        {
          "office_rental": {
             "description": "Affitto mensile",
             "amount": "1700",
             "supplier": "XYZ SRL",
             …
          },
          …
        }
        """
        cfg = self.load_config()
        rec = cfg.setdefault("recurring_expenses", {})

        for expense_key, fields in new_recurring_data.items():
            node = rec.setdefault(expense_key, {})

            # Se c'è una descrizione scalar, la salvo prima
            if "description" in fields:
                node["description"] = fields.pop("description")

            # Ora gestisco tutti gli altri campi come prima
            for field_name, new_val in fields.items():
                existing = node.get(field_name)
                if isinstance(existing, dict):
                    existing["value"] = new_val
                else:
                    node[field_name] = {"value": new_val, "description": ""}

        self.save_config(cfg)


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
class AliquotaIva:
    no_iva: float = 0.0
    desc_no_iva: str = ""
    aliquota_iva_ordinaria: float = 0.0
    desc_iva_ordinaria: str = ""
    aliquota_iva_ridotta_1: float = 0.0
    desc_iva_ridotta_1: str = ""
    aliquota_iva_ridotta_2: float = 0.0
    desc_iva_ridotta_2: str = ""
    aliquota_iva_minima: float = 0.0
    desc_iva_minima: str = ""

    @staticmethod
    def from_dict(data: dict) -> 'AliquotaIva':
        return AliquotaIva(
            no_iva                  = float(data.get("no_iva", {}).get("value", 0.0)),
            aliquota_iva_ordinaria  = float(data.get("aliquota_iva_ordinaria", {}).get("value", 0.0)),
            desc_iva_ordinaria      = data.get("aliquota_iva_ordinaria", {}).get("description", ""),
            aliquota_iva_ridotta_1  = float(data.get("aliquota_iva_ridotta_1", {}).get("value", 0.0)),
            desc_iva_ridotta_1      = data.get("aliquota_iva_ridotta_1", {}).get("description", ""),
            aliquota_iva_ridotta_2  = float(data.get("aliquota_iva_ridotta_2", {}).get("value", 0.0)),
            desc_iva_ridotta_2      = data.get("aliquota_iva_ridotta_2", {}).get("description", ""),
            aliquota_iva_minima     = float(data.get("aliquota_iva_minima", {}).get("value", 0.0)),
            desc_iva_minima         = data.get("aliquota_iva_minima", {}).get("description", "")
        )

@dataclass
class FiscalSettings:
    aliquota_iva: AliquotaIva
    partita_iva_forfettaria: PartitaIVAForfettaria
    partita_iva_ordinaria: PartitaIVAOrdinaria

    @staticmethod
    def from_dict(data: dict):
        fiscal_data = data or {}
        return FiscalSettings(
            aliquota_iva=AliquotaIva.from_dict(
                fiscal_data.get("iva", {})
            ),
            partita_iva_forfettaria=PartitaIVAForfettaria.from_dict(
                fiscal_data.get("partita_iva_forfettaria", {})
            ),
            partita_iva_ordinaria=PartitaIVAOrdinaria.from_dict(
                fiscal_data.get("partita_iva_ordinaria", {})
            )
        )

@dataclass
class RecurringExpense:
    description: str
    amount: float
    descr_amount : ""
    supplier: str
    descr_supplier : ""
    deductible: bool
    descr_deductible : ""
    category: str
    descr_category : ""
    iva: float
    descr_iva : ""
    account: str
    descr_account : ""
    frequency: str
    descr_frequency : ""
    status: bool
    descr_status : ""

    @staticmethod
    def from_dict(data: dict):
        return RecurringExpense(
            description=data.get("description", ""),
            amount=float(data.get("amount", {}).get("value", 0)),
            descr_amount=data.get("amount", {}).get("description", ""),
            supplier=data.get("supplier", {}).get("value", ""),
            descr_supplier=data.get("supplier", {}).get("description", ""),
            deductible=data.get("deductible", {}).get("value", "No") == "Sì",
            descr_deductible=data.get("deductible", {}).get("description", ""),
            category=data.get("category", {}).get("value", ""),
            descr_category=data.get("category", {}).get("description", ""),
            iva=float(data.get("iva", {}).get("value", 0)),
            descr_iva=data.get("iva", {}).get("description", ""),
            account=data.get("account", {}).get("value", ""),
            descr_account=data.get("account", {}).get("description", ""),
            frequency=data.get("frequency", {}).get("value", ""),
            descr_frequency=data.get("frequency", {}).get("description", ""),
            status=data.get("status", {}).get("value", ExpenseController.RecurringExpensesStatus.SOSPESA.value) == ExpenseController.RecurringExpensesStatus.ATTIVA.value,
            descr_status=data.get("status", {}).get("description", ""),
        )

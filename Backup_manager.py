import shutil
from datetime import datetime, timedelta
import threading
import os, re, json
from typing import List, Dict, Tuple, Optional
from ConfigManagers.type_utils import coerce_to_int
from Utils.App_paths import get_runtime_paths


DB_FILENAME = "gestionale.db"
LEGACY_CONFIG_FILENAME = "app_config.json"

# JSON di configurazione da includere in ogni backup. Mirror della suddivisione
# applicata da fix_db/migrate_legacy_app_config_to_split_jsons.py, piu'
# gui_preferences.json (gestito separatamente da GuiPreferencesManager).
CONFIG_BACKUP_FILES: Tuple[str, ...] = (
    "app_settings.json",
    "catalogs.json",
    "fiscal_rules.json",
    "historical_financial_data.json",
    "recurring_expenses.json",
    "gui_preferences.json",
)


# Motivi di non-importabilita' per un backup. Vengono mappati a un messaggio
# user-facing dalla dialog di import.
INVALID_REASON_LEGACY = "legacy"
INVALID_REASON_INCOMPLETE = "incomplete"
INVALID_REASON_MISSING = "missing"


class BackupScheduler:
    def __init__(self, interval_minutes, max_backups, db_backup_base_path, delta_days, books_backup_path, books_default_path):
        """
        Gestisce il scheduling di backup in un thread separato.
        :param interval_minutes: Intervallo tra backup, in minuti.
        :param max_backups: Numero massimo di backup da mantenere.
        :param db_backup_base_path: Cartella base dove salvare i backup.
        :param delta_days: Intervallo di giorni per suddividere i backup in sub‐cartelle.
        """
        self.interval_minutes = max(1, coerce_to_int(interval_minutes, 15))
        self.interval_seconds = self.interval_minutes * 60
        self.max_backups = max(1, coerce_to_int(max_backups, 35))
        self.db_backup_base_path = db_backup_base_path
        self.books_backup_path = books_backup_path
        self.books_default_path=books_default_path
        self.delta_days = max(1, coerce_to_int(delta_days, 7))

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
            os.makedirs(self.db_backup_base_path, exist_ok=True)
            self.backup_gestionale_db(
                self.max_backups,
                self.db_backup_base_path,
                self.delta_days
            )
            print("Backup finale completato.")
        except Exception as e:
            print(f"Errore durante il backup finale: {e}")

    def _schedule_backup(self):
        """Pianifica il prossimo timer di backup se non fermato."""
        if not self.stop_event.is_set():
            t = threading.Timer(self.interval_seconds, self._execute_scheduled_backup)
            t.daemon = True             # <— rendilo daemon
            self.backup_timer = t
            t.start()

    def _execute_scheduled_backup(self):
        """
        Esegue il backup programmato e, se non fermato, ripianifica il successivo.
        """
        try:
            print("Esecuzione del backup programmato…")
            os.makedirs(self.db_backup_base_path, exist_ok=True)
            self.backup_gestionale_db(
                self.max_backups,
                self.db_backup_base_path,
                self.delta_days
            )
            print("Backup completato.")
        except Exception as e:
            print(f"Errore durante il backup programmato: {e}")
        finally:
            # Ripianifica solo se non abbiamo chiamato stop()
            if not self.stop_event.is_set():
                self._schedule_backup()

    def backup_gestionale_db(self, max_backups=None, db_backup_base_path=None, delta_days=None):
        """
        Esegue il backup del database gestionale con una logica FIFO per mantenere un numero massimo di n backup
        in cartelle organizzate per intervallo di tempo.

        :param max_backups: Numero massimo di backup da conservare per intervallo.
        :param db_backup_base_path: Path base dove salvare i backup.
        :param delta_days: Intervallo di tempo in giorni per organizzare le cartelle dei backup.
        """

        max_backups = max_backups if max_backups is not None else self.max_backups
        db_backup_base_path = db_backup_base_path if db_backup_base_path is not None else self.db_backup_base_path
        delta_days = delta_days if delta_days is not None else self.delta_days
        max_backups = max(1, coerce_to_int(max_backups, self.max_backups))
        delta_days = max(1, coerce_to_int(delta_days, self.delta_days))


        runtime_paths = get_runtime_paths()

        # Verifica che il file gestionale.db esista
        db_file = str(runtime_paths.db_file)
        if not os.path.exists(db_file):
            print(f"Errore: Il file {db_file} non esiste.")
            return

        # Raccoglie tutti i file di configurazione split. Il backup deve essere
        # completo: se uno manca, abortiamo per evitare di scrivere backup
        # parziali che poi non risulterebbero importabili.
        storage_root = runtime_paths.storage_root
        config_sources: Dict[str, str] = {}
        for name in CONFIG_BACKUP_FILES:
            src = str(storage_root / name)
            if not os.path.exists(src):
                print(f"Errore: il file di configurazione {src} non esiste. Backup annullato.")
                return
            config_sources[name] = src

        # Determina l'intervallo di tempo corrente e il nome della sottocartella
        now = datetime.now()
        start_interval = now - timedelta(days=now.day % delta_days)
        folder_name = f"{start_interval.strftime('%Y%m%d')}_to_{(start_interval + timedelta(days=delta_days)).strftime('%Y%m%d')}"
        interval_folder = os.path.join(db_backup_base_path, folder_name)

        # Verifica o crea la cartella per l'intervallo corrente
        os.makedirs(interval_folder, exist_ok=True)

        # Crea la sottocartella contenente bk del db e dei file di config
        sub_folder = os.path.join(interval_folder, f"gestionale_data_{now.strftime('%Y%m%d_%H%M%S')}")
        os.makedirs(sub_folder, exist_ok=True)

        # Copia il database e tutti i file di configurazione split
        db_backup_filepath = os.path.join(sub_folder, DB_FILENAME)
        shutil.copy2(db_file, db_backup_filepath)
        copied_files: List[str] = [db_backup_filepath]
        for name, src in config_sources.items():
            dst = os.path.join(sub_folder, name)
            shutil.copy2(src, dst)
            copied_files.append(dst)

        # Gestione della rotazione dei backup
        if os.path.exists(interval_folder):
            # Ottieni solo le directory
            subfolders = [f for f in os.listdir(interval_folder)
                          if os.path.isdir(os.path.join(interval_folder, f))]

            # Ordina per data di creazione
            subfolders.sort(key=lambda x: os.path.getctime(os.path.join(interval_folder, x)))

            # Se il numero di backup è maggiore di max_backups, elimina i più vecchi
            while len(subfolders) > max_backups:
                oldest_subfolder = subfolders.pop(0)
                oldest_subfolder_path = os.path.join(interval_folder, oldest_subfolder)
                try:
                    shutil.rmtree(oldest_subfolder_path)
                    print(f"Rimosso backup vecchio: {oldest_subfolder_path}")
                except Exception as e:
                    print(f"Errore nella rimozione di {oldest_subfolder_path}: {e}")

        print(f"Backup creato in {sub_folder}: {', '.join(os.path.basename(f) for f in copied_files)}")

    def backup_gestionale_books(self, books_backup_path=None):
        """
        Esegue il backup completo dei books copiando tutti i file e le sottocartelle
        dal percorso di default verso il percorso di backup, sovrascrivendo
        interamente il contenuto precedente.

        :param books_backup_path: Path di destinazione per il backup.
        :return: (success: bool, message: str)
        """

        books_backup_path = (
            books_backup_path
            if books_backup_path is not None
            else self.books_backup_path
        )

        source_path = self.books_default_path

        # Validazione path sorgente
        if not source_path or not os.path.isdir(source_path):
            return False, f"Percorso sorgente non valido o inesistente: {source_path}"

        # Validazione path destinazione
        if not books_backup_path or not os.path.isdir(books_backup_path):
            return False, f"Percorso di backup non valido o inesistente: {books_backup_path}"

        try:
            # Pulizia completa della cartella di backup
            for item in os.listdir(books_backup_path):
                item_path = os.path.join(books_backup_path, item)

                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)

            # Copia ricorsiva di file e sottocartelle
            for item in os.listdir(source_path):
                src_item = os.path.join(source_path, item)
                dst_item = os.path.join(books_backup_path, item)

                if os.path.isdir(src_item):
                    shutil.copytree(src_item, dst_item)
                else:
                    shutil.copy2(src_item, dst_item)

            return True, "Backup books completato con successo (contenuto sovrascritto)."

        except Exception as e:
            return False, f"Errore durante il backup dei books: {e}"


class BackupImporter:
    """
    Manages listing and importing backups stored under:
      db_backup_base_path/<interval_folder>/<subfolder_with_timestamp>/

    Ogni subfolder importabile deve contenere:
      - gestionale.db
      - tutti i file in CONFIG_BACKUP_FILES (app_settings.json, catalogs.json,
        fiscal_rules.json, historical_financial_data.json,
        recurring_expenses.json, gui_preferences.json).

    I backup creati da versioni precedenti dell'app (con un unico
    ``app_config.json`` o senza i file split) sono identificabili tramite
    ``validate_backup`` e vengono mostrati in UI ma non sono importabili,
    perche' la struttura dei config files non e' piu' compatibile.

    API principali:
      - list_backups_for_year(year) -> List[dict] (each dict contiene
        'path', 'datetime', 'display', 'valid', 'reason', 'missing')
      - validate_backup(subfolder) -> dict {valid, reason, missing}
      - import_backup(subfolder_path) -> (success: bool, message: str)
    """

    TIMESTAMP_PATTERN = re.compile(r"gestionale_data_(\d{8})_(\d{6})")

    def __init__(self, db_backup_base_path: str, db_path: str):
        self.db_backup_base_path = os.path.abspath(db_backup_base_path) if db_backup_base_path else None
        self.db_path_input = db_path

    # --- Listing helpers -------------------------------------------------
    def _parse_datetime_from_subfolder(self, subfolder_name: str) -> Optional[datetime]:
        """
        Cerca di estrarre la datetime dal nome della sottocartella con pattern:
            gestionale_data_YYYYMMDD_HHMMSS
        Ritorna None se non matcha.
        """
        m = self.TIMESTAMP_PATTERN.search(subfolder_name)
        if not m:
            return None
        datepart = m.group(1)  # YYYYMMDD
        timepart = m.group(2)  # HHMMSS
        try:
            return datetime.strptime(datepart + timepart, "%Y%m%d%H%M%S")
        except Exception:
            return None

    def _collect_all_subfolders(self) -> List[str]:
        """
        Ritorna una lista di percorsi assoluti per ogni subfolder trovato in db_backup_base_path/*/*
        (cioè scende di due livelli: interval_folder -> subfolders).
        """
        results = []
        if not self.db_backup_base_path or not os.path.isdir(self.db_backup_base_path):
            return results

        try:
            for interval in os.listdir(self.db_backup_base_path):
                interval_path = os.path.join(self.db_backup_base_path, interval)
                if not os.path.isdir(interval_path):
                    continue
                for sub in os.listdir(interval_path):
                    sub_path = os.path.join(interval_path, sub)
                    if os.path.isdir(sub_path):
                        results.append(sub_path)
        except Exception:
            # Non solleviamo qui: il chiamante può decidere come loggare/mostrare errori
            return results

        return results

    def list_backups_for_year(self, year: int) -> List[Dict]:
        """
        Restituisce una lista di dict che rappresentano i backup appartenenti all'anno 'year'.
        Ogni dict contiene:
            - 'path': percorso assoluto della sottocartella del backup
            - 'datetime': datetime oggetto (se ricavato), altrimenti la ctime come fallback
            - 'display': stringa leggibile per mostrare in UI
            - 'valid': True se il backup contiene tutti i file richiesti
            - 'reason': None se valid, altrimenti uno tra
              INVALID_REASON_LEGACY / INVALID_REASON_INCOMPLETE / INVALID_REASON_MISSING
            - 'missing': lista dei file mancanti (vuota se valid)
        Ordinati dal più recente al più vecchio.
        """
        candidates = self._collect_all_subfolders()
        found = []

        for p in candidates:
            subfolder_name = os.path.basename(p)
            dt = self._parse_datetime_from_subfolder(subfolder_name)
            if dt is None:
                # fallback: usa la ctime del filesystem
                try:
                    ctime = os.path.getctime(p)
                    dt = datetime.fromtimestamp(ctime)
                except Exception:
                    continue

            if dt.year == year:
                display = dt.strftime("%Y-%m-%d %H:%M:%S") + " — " + os.path.relpath(p, self.db_backup_base_path)
                validation = self.validate_backup(p)
                found.append({
                    "path": p,
                    "datetime": dt,
                    "display": display,
                    "valid": validation["valid"],
                    "reason": validation["reason"],
                    "missing": validation["missing"],
                })

        # Ordina dal più recente al più vecchio
        found.sort(key=lambda x: x["datetime"], reverse=True)
        return found

    # --- Validation ------------------------------------------------------
    def validate_backup(self, subfolder_path: str) -> Dict:
        """
        Verifica se ``subfolder_path`` contiene tutti i file richiesti dal
        nuovo schema (db + split config JSON).

        Restituisce ``{"valid": bool, "reason": str|None, "missing": list}``.

        Reason values quando ``valid`` e' False:
          - INVALID_REASON_LEGACY: backup creato dalla vecchia versione con
            ``app_config.json`` monolitico (i config sono stati smembrati in
            file separati e la struttura non e' piu' compatibile).
          - INVALID_REASON_INCOMPLETE: alcuni file split sono presenti ma
            non tutti (backup parziale o corrotto).
          - INVALID_REASON_MISSING: percorso non esiste o non e' una cartella.
        """
        if not subfolder_path or not os.path.isdir(subfolder_path):
            return {"valid": False, "reason": INVALID_REASON_MISSING, "missing": []}

        required = (DB_FILENAME,) + CONFIG_BACKUP_FILES
        missing = [f for f in required if not os.path.exists(os.path.join(subfolder_path, f))]
        if not missing:
            return {"valid": True, "reason": None, "missing": []}

        has_legacy_config = os.path.exists(os.path.join(subfolder_path, LEGACY_CONFIG_FILENAME))
        reason = INVALID_REASON_LEGACY if has_legacy_config else INVALID_REASON_INCOMPLETE
        return {"valid": False, "reason": reason, "missing": missing}

    # --- Import helper ---------------------------------------------------
    def _destination_folder(self) -> Optional[str]:
        """
        Ricava la cartella di destinazione da self.db_path_input.
        Se db_path_input è una cartella -> la usa. Altrimenti estrae dirname.
        """
        if not self.db_path_input:
            return None
        if os.path.isdir(self.db_path_input):
            return os.path.abspath(self.db_path_input)
        # Se è un file path (es. /path/to/gestionale.db) -> return dirname
        return os.path.abspath(os.path.dirname(self.db_path_input))

    def import_backup(self, subfolder_path: str) -> Tuple[bool, str]:
        """
        Copia il database e tutti i file di configurazione split da
        ``subfolder_path`` verso la destinazione (cartella del gestionale).

        L'operazione e' atomica best-effort: tutti i file vengono copiati su
        file temporanei nella stessa cartella di destinazione, e solo se TUTTE
        le copie hanno successo viene eseguita la sequenza di
        ``os.replace`` finale. In caso di errore i ``.tmp`` vengono ripuliti
        e i file gia' presenti restano intatti.

        Ritorna (True, "messaggio") oppure (False, "messaggio di errore").
        """
        tmp_paths: List[Tuple[str, str]] = []
        try:
            validation = self.validate_backup(subfolder_path)
            if not validation["valid"]:
                reason = validation["reason"]
                if reason == INVALID_REASON_LEGACY:
                    return False, (
                        "Backup non importabile: appartiene a una versione precedente "
                        "dell'applicazione che utilizzava un singolo file di configurazione "
                        "(app_config.json). La struttura dei file di configurazione e' "
                        "cambiata e questo backup non e' piu' compatibile."
                    )
                if reason == INVALID_REASON_INCOMPLETE:
                    missing = ", ".join(validation["missing"])
                    return False, f"Backup incompleto: mancano i file: {missing}"
                return False, "Backup selezionato non trovato o non e' una cartella valida."

            dest_folder = self._destination_folder()
            if not dest_folder:
                return False, "Percorso di destinazione per il gestionale non definito."

            os.makedirs(dest_folder, exist_ok=True)

            items_to_copy: Tuple[str, ...] = (DB_FILENAME,) + CONFIG_BACKUP_FILES

            # 1) Copia su file temporanei
            for name in items_to_copy:
                src = os.path.join(subfolder_path, name)
                dst = os.path.join(dest_folder, name)
                tmp = dst + ".tmp"
                shutil.copy2(src, tmp)
                tmp_paths.append((tmp, dst))

            # 2) Sostituzioni atomiche (su Windows os.replace sovrascrive)
            for tmp, dst in tmp_paths:
                os.replace(tmp, dst)

            return True, (
                f"Import completato: {len(items_to_copy)} file aggiornati in {dest_folder}"
            )
        except Exception as e:
            # Cleanup dei file temporanei in caso di errore
            for tmp, _ in tmp_paths:
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except Exception:
                    pass
            return False, f"Errore durante l'import: {e}"


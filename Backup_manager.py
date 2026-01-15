import shutil
from datetime import datetime, timedelta
import threading
import os, re, json
from typing import List, Dict, Tuple, Optional



class BackupScheduler:
    def __init__(self, interval_minutes, max_backups, db_backup_base_path, delta_days, books_backup_path, books_default_path):
        """
        Gestisce il scheduling di backup in un thread separato.
        :param interval_minutes: Intervallo tra backup, in minuti.
        :param max_backups: Numero massimo di backup da mantenere.
        :param db_backup_base_path: Cartella base dove salvare i backup.
        :param delta_days: Intervallo di giorni per suddividere i backup in sub‐cartelle.
        """
        self.interval_seconds = interval_minutes * 60
        self.max_backups = max_backups
        self.db_backup_base_path = db_backup_base_path
        self.books_backup_path = books_backup_path
        self.books_default_path=books_default_path
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


        # Recupera il percorso del DB tramite la variabile di ambiente
        db_path = os.getenv("GESTIONALE_DB_PATH")
        if not db_path:
            print("Errore: variabile di ambiente GESTIONALE_DB_PATH non definita.")
            return

        # Verifica che il file gestionale.db esista
        db_file = os.path.join(db_path, "gestionale.db")
        if not os.path.exists(db_file):
            print(f"Errore: Il file {db_file} non esiste.")
            return

        # Verifica che il file app_config esista
        config_file = os.path.join(db_path, "app_config.json")
        if not os.path.exists(config_file):
            print(f"Errore: Il file {config_file} non esiste.")
            return

        # Determina l'intervallo di tempo corrente e il nome della sottocartella
        now = datetime.now()
        start_interval = now - timedelta(days=now.day % delta_days)
        folder_name = f"{start_interval.strftime('%Y%m%d')}_to_{(start_interval + timedelta(days=delta_days)).strftime('%Y%m%d')}"
        interval_folder = os.path.join(db_backup_base_path, folder_name)

        # Verifica o crea la cartella per l'intervallo corrente
        os.makedirs(interval_folder, exist_ok=True)

        # Crea la sottocartella contenente bk del db e del file di config
        sub_folder = os.path.join(interval_folder, f"gestionale_data_{now.strftime('%Y%m%d_%H%M%S')}")
        os.makedirs(sub_folder, exist_ok=True)

        # Crea il nome del file di backup basato sulla data e ora correnti
        db_backup_filename = "gestionale.db"
        config_backup_filename = "app_config.json"
        db_backup_filepath = os.path.join(sub_folder, db_backup_filename)
        config_backup_filepath = os.path.join(sub_folder, config_backup_filename)

        # Copia il database nella cartella dell'intervallo corrente
        shutil.copy2(db_file, db_backup_filepath)
        shutil.copy2(config_file, config_backup_filepath)

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

        print(f"Backup creato: {db_backup_filepath}, {config_backup_filepath}")

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

    Each subfolder is expected to contain:
      - gestionale.db
      - app_config.json

    API principali:
      - list_backups_for_year(year) -> List[dict] (each dict contiene 'path', 'datetime', 'display')
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
                found.append({"path": p, "datetime": dt, "display": display})

        # Ordina dal più recente al più vecchio
        found.sort(key=lambda x: x["datetime"], reverse=True)
        return found

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
        Copia i file gestionale.db e app_config.json da subfolder_path -> destinazione.
        L'operazione va a buon fine SOLO SE entrambi i file esistono nel subfolder.
        Ritorna (True, "messaggio") oppure (False, "messaggio di errore").
        """
        try:
            if not subfolder_path or not os.path.isdir(subfolder_path):
                return False, "Backup selezionato non trovato o non è una cartella."

            db_file = os.path.join(subfolder_path, "gestionale.db")
            config_file = os.path.join(subfolder_path, "app_config.json")

            if not os.path.exists(db_file) or not os.path.exists(config_file):
                missing = []
                if not os.path.exists(db_file):
                    missing.append("gestionale.db")
                if not os.path.exists(config_file):
                    missing.append("app_config.json")
                return False, f"Backup incompleto: mancano i file: {', '.join(missing)}"

            dest_folder = self._destination_folder()
            if not dest_folder:
                return False, "Percorso di destinazione per il gestionale non definito."

            os.makedirs(dest_folder, exist_ok=True)

            dest_db = os.path.join(dest_folder, "gestionale.db")
            dest_config = os.path.join(dest_folder, "app_config.json")

            # Copia atomica best-effort:
            # 1) copia su file temporanei nella stessa cartella di destinazione
            # 2) rinomina/replaces per minimizzare rischi di file parziali
            tmp_db = dest_db + ".tmp"
            tmp_cfg = dest_config + ".tmp"

            shutil.copy2(db_file, tmp_db)
            shutil.copy2(config_file, tmp_cfg)

            # poi replace finali (su Windows os.replace sovrascrive)
            os.replace(tmp_db, dest_db)
            os.replace(tmp_cfg, dest_config)

            return True, f"Import completato: {os.path.basename(dest_db)} e {os.path.basename(dest_config)} aggiornati in {dest_folder}"
        except Exception as e:
            return False, f"Errore durante l'import: {e}"


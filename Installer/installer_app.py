import os
import re
import sys
import shutil
import threading
import winreg
import ctypes
import logging
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk


_DEFAULT_INSTALL_PATH = r"C:\Program Files\WillowGestionale"
_DEFAULT_DATA_PATH = str(
    Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    / "WillowGestionale"
)
_BASE_STEPS = 16  # 1 cartelle + 12 tabelle + 1 Data + 1 copia exe + 1 env var
_PROTECTED_ROOTS = (
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
    Path(os.environ.get("SystemRoot", r"C:\Windows")),
)


def _bootstrap_import_paths() -> None:
    candidates = []

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend([exe_dir, exe_dir / "Installer"])
    else:
        project_root = Path(__file__).resolve().parent.parent
        candidates.extend([project_root, project_root / "Installer"])

    for candidate in candidates:
        candidate_str = str(candidate)
        if candidate.exists() and candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)


_bootstrap_import_paths()

from PatchLauncher import patchLauncher

# ---------------------------------------------------------------------------
# Logging setup – scrive su file E su stdout
# Il file di log è in %TEMP%\willow_installer_debug.log
# ---------------------------------------------------------------------------

_LOG_PATH = Path(os.environ.get("TEMP", ".")) / "willow_installer_debug.log"


class _FlushingFileHandler(logging.FileHandler):
    """FileHandler che fa flush() dopo ogni emit.

    Necessario perche' Utils.App_paths chiama os._exit(1) in caso fatale e
    senza flush gli ultimi log non finirebbero su disco -- impossibile poi
    capire quale step abbia provocato il problema.
    """

    def emit(self, record):
        super().emit(record)
        try:
            self.flush()
        except Exception:
            pass


logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(funcName)s: %(message)s",
    handlers=[
        _FlushingFileHandler(str(_LOG_PATH), mode="w", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("WillowInstaller")
log.info("=== Willow Installer avviato ===")
log.info(f"Log file: {_LOG_PATH}")
log.info(f"Python: {sys.version}")
log.info(f"Frozen: {getattr(sys, 'frozen', False)}")
log.info(f"Executable: {sys.executable}")
log.debug(f"sys.path[0:5]: {sys.path[:5]}")


# ---------------------------------------------------------------------------
# Package layout: l'installer si aspetta di trovare accanto a se' una
# cartella Data/, una cartella Patches/ e un file <gestionale>.exe da
# copiare nella install folder. Non scarica nulla da rete.
# ---------------------------------------------------------------------------

def _get_package_root() -> Path:
    """Cartella che contiene installer.exe, Data/, Patches/, <gestionale>.exe."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _get_source_data_dir() -> Path:
    p = _get_package_root() / "Data"
    log.debug(f"source_data_dir => {p}  (exists={p.exists()})")
    return p


def _find_packaged_gestionale_exe() -> Path | None:
    """Trova l'exe del gestionale nel package, escludendo l'installer stesso.

    Preferisce gli exe il cui nome contiene 'willow' o 'gestionale'.
    """
    package_root = _get_package_root()
    installer_name = Path(sys.executable).name.lower() if getattr(sys, "frozen", False) else ""
    candidates: list[Path] = []
    for path in package_root.glob("*.exe"):
        if not path.is_file():
            continue
        if installer_name and path.name.lower() == installer_name:
            continue
        if "installer" in path.name.lower():
            continue
        candidates.append(path)

    if not candidates:
        log.warning(f"Nessun exe del gestionale trovato nel package: {package_root}")
        return None

    preferred = [p for p in candidates if "willow" in p.name.lower() or "gestionale" in p.name.lower()]
    pool = preferred or candidates
    chosen = max(pool, key=lambda p: (patchLauncher.normalize_version(p.name) or (-1, -1, -1), p.stat().st_mtime))
    log.info(f"Exe gestionale rilevato nel package: {chosen}")
    return chosen


def _set_persistent_env_var(name: str, value: str) -> None:
    log.debug(f"Scrittura registro: {name} = {value}")
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE
    )
    winreg.SetValueEx(key, name, 0, winreg.REG_EXPAND_SZ, value)
    winreg.CloseKey(key)
    log.debug("Chiave registro scritta. Invio WM_SETTINGCHANGE...")
    ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x1A, 0, "Environment", 0, 5000, None)
    log.debug("WM_SETTINGCHANGE inviato.")


def _is_running_as_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _requires_elevation(path: str) -> bool:
    resolved = Path(path).expanduser().resolve(strict=False)
    for protected_root in _PROTECTED_ROOTS:
        try:
            resolved.relative_to(protected_root.resolve(strict=False))
            return True
        except ValueError:
            continue
    return False


def _relaunch_as_admin(target: str, data_target: str, create_shortcut: bool) -> bool:
    shortcut_flag = "1" if create_shortcut else "0"
    if getattr(sys, "frozen", False):
        executable = str(Path(sys.executable).resolve())
        params = (
            f'--install-path "{target}" --data-path "{data_target}" '
            f"--create-shortcut {shortcut_flag} --auto-install"
        )
    else:
        executable = sys.executable
        script_path = str(Path(__file__).resolve())
        params = (
            f'"{script_path}" --install-path "{target}" --data-path "{data_target}" '
            f"--create-shortcut {shortcut_flag} --auto-install"
        )

    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        executable,
        params,
        None,
        1,
    )
    return result > 32


def _consume_startup_options() -> dict:
    options = {
        "install_path": None,
        "data_path": None,
        "create_shortcut": True,
        "auto_install": False,
    }
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--install-path" and i + 1 < len(args):
            options["install_path"] = args[i + 1]
            i += 2
            continue
        if arg == "--create-shortcut" and i + 1 < len(args):
            options["create_shortcut"] = args[i + 1] == "1"
            i += 2
            continue
        if arg == "--data-path" and i + 1 < len(args):
            options["data_path"] = args[i + 1]
            i += 2
            continue
        if arg == "--auto-install":
            options["auto_install"] = True
        i += 1
    return options


def _extract_version_from_filename(filename: str) -> str:
    """Estrae un token di versione dal nome del file .exe."""
    stem = Path(filename).stem
    match = re.search(r"v?\d+(?:[._]\d+)+", stem)
    if match:
        return match.group(0).replace("_", ".")
    log.debug(f"Nessuna versione riconosciuta nel nome file: {filename!r}")
    return ""


def _create_desktop_shortcut(exe_path: str) -> None:
    log.debug(f"Creazione shortcut per: {exe_path}")
    version = _extract_version_from_filename(Path(exe_path).name)
    invalid_chars = set('\\/:*?"<>|')
    safe_version = "".join(ch for ch in version if ch not in invalid_chars).strip()
    shortcut_name = (
        f"Willow Gestionale {safe_version}".strip() if safe_version else "Willow Gestionale"
    )
    log.info(f"Nome shortcut: {shortcut_name!r} (versione rilevata: {version!r})")
    ps = (
        '$desktop = [Environment]::GetFolderPath("Desktop"); '
        f'$s = (New-Object -ComObject WScript.Shell).CreateShortcut($desktop + "\\{shortcut_name}.lnk"); '
        f'$s.TargetPath = "{exe_path}"; '
        '$s.IconLocation = $s.TargetPath; '
        '$s.Save()'
    )
    import subprocess
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        check=True,
        capture_output=True,
        text=True,
    )
    log.debug(f"PowerShell stdout: {result.stdout!r}")
    log.debug(f"PowerShell stderr: {result.stderr!r}")
    log.info("Shortcut desktop creata con successo.")


# ---------------------------------------------------------------------------
# Copia exe del gestionale (sostituisce il download da GitHub)
# ---------------------------------------------------------------------------

def _copy_local_gestionale_exe(target_folder: str, label_cb) -> tuple:
    """Copia l'exe del gestionale dal package alla cartella di installazione.

    Ritorna (ok, percorso_destinazione, errore, versione).
    """
    log.info("=== Inizio copia exe gestionale (sorgente locale) ===")

    source_exe = _find_packaged_gestionale_exe()
    if source_exe is None:
        msg = (
            "Nessun exe del gestionale trovato nel pacchetto di installazione. "
            "Verifica che WillowGestionale_X_Y.exe sia presente accanto a installer.exe."
        )
        log.error(msg)
        return False, "", msg, ""

    dest_path = Path(target_folder) / source_exe.name
    total_size = source_exe.stat().st_size
    version = _extract_version_from_filename(source_exe.name)

    log.info(f"Sorgente: {source_exe} ({total_size} bytes)")
    log.info(f"Destinazione: {dest_path}")
    log.info(f"Versione rilevata: {version!r}")

    try:
        label_cb(f"Copia {source_exe.name}: 0%")
        shutil.copy2(str(source_exe), str(dest_path))
        actual_size = dest_path.stat().st_size
        log.info(f"Copia completata. Dimensione file: {actual_size} bytes")
        label_cb(f"Copia {source_exe.name}: 100%")
        return True, str(dest_path), "", version
    except Exception as exc:
        log.error(f"Eccezione in _copy_local_gestionale_exe: {type(exc).__name__}: {exc}")
        log.error(traceback.format_exc())
        return False, "", f"{type(exc).__name__}: {exc}", ""


# ---------------------------------------------------------------------------
# Funzione principale di installazione (thread secondario)
# ---------------------------------------------------------------------------

def _run_installation(
    target_folder: str,
    data_folder: str,
    create_shortcut: bool,
    step_cb,
    download_label_cb,
    done_cb,
    skip_db: bool = False,
    overwrite_db: bool = False,
    run_patches: bool = False,
    installed_exe_version: str = "",
    installed_exe_path: str = "",
) -> None:
    log.info(
        f"=== _run_installation START | target={target_folder} | data={data_folder} | "
        f"shortcut={create_shortcut} | skip_db={skip_db} | overwrite_db={overwrite_db} | "
        f"run_patches={run_patches} | installed_exe={installed_exe_path!r} | "
        f"installed_version={installed_exe_version!r} ==="
    )
    errors = []

    # Step 0 – setta SUBITO le env var IN-PROCESS sui percorsi scelti dall'UI.
    # Cosi' qualunque modulo del gestionale (Utils.App_paths in primis) che
    # venga importato durante i prossimi step (Db_initializer -> Model ->
    # get_runtime_paths) trova i path coerenti con quanto deciso dall'utente,
    # anche prima che Step 15 li scriva nel registro di sistema.
    os.environ["GESTIONALE_DB_PATH"] = str(data_folder)
    os.environ["GESTIONALE_INSTALLATION_PATH"] = str(target_folder)
    log.info(
        f"Step 0: env in-process settate "
        f"(GESTIONALE_DB_PATH={data_folder!r}, GESTIONALE_INSTALLATION_PATH={target_folder!r})"
    )

    # Step 1 – struttura cartelle
    log.info("Step 1: creazione struttura cartelle")
    try:
        Path(target_folder).mkdir(parents=True, exist_ok=True)
        data_root = Path(data_folder)
        data_root.mkdir(parents=True, exist_ok=True)
        (data_root / "Books").mkdir(exist_ok=True)
        (data_root / "Backups").mkdir(exist_ok=True)
        log.info("Cartelle applicazione e dati create con successo.")
        step_cb("Cartelle applicazione e dati create", True)
    except Exception as exc:
        log.error(f"Errore creazione cartelle: {exc}\n{traceback.format_exc()}")
        step_cb(f"Errore creazione cartelle: {exc}", False)
        done_cb(False, str(exc))
        return

    # Steps 2–12 – tabelle DB
    db_file = Path(data_folder) / "gestionale.db"
    if skip_db:
        log.info("Creazione database saltata su richiesta utente (database esistente mantenuto).")
        step_cb("Creazione database saltata (database esistente mantenuto)", True)
    else:
        if overwrite_db and db_file.exists():
            log.info(f"Overwrite richiesto: rimozione database esistente {db_file}")
            try:
                db_file.unlink()
                log.info("Database esistente rimosso con successo.")
            except Exception as exc:
                log.error(f"Errore rimozione database esistente: {exc}\n{traceback.format_exc()}")
                step_cb(f"Errore rimozione database esistente: {exc}", False)
                errors.append(f"Rimozione database esistente: {exc}")
                done_cb(False, str(exc))
                return

        log.info("Steps 2-12: creazione tabelle database")
        try:
            from DatabaseCreation.Db_initializer import create_all_tables
            for name, ok, err in create_all_tables(data_folder):
                log.log(logging.INFO if ok else logging.ERROR, f"  {name}: {'OK' if ok else 'ERRORE: ' + err}")
                step_cb(name, ok)
                if not ok:
                    errors.append(f"{name}: {err}")
        except Exception as exc:
            log.error(f"Eccezione in create_all_tables: {exc}\n{traceback.format_exc()}")
            step_cb(f"Errore creazione tabelle: {exc}", False)
            errors.append(str(exc))

    # Step 13 – copia Data/
    log.info("Step 13: copia cartella Data/")
    source_data = _get_source_data_dir()
    dest_data = Path(target_folder) / "Data"
    try:
        if source_data.exists():
            if dest_data.exists():
                log.debug(f"Rimozione dest_data esistente: {dest_data}")
                shutil.rmtree(dest_data)
            shutil.copytree(str(source_data), str(dest_data))
            log.info(f"Data/ copiata: {source_data} -> {dest_data}")
            step_cb("Cartella Data copiata", True)
        else:
            log.warning(f"Cartella Data sorgente non trovata: {source_data}")
            step_cb("Cartella Data non trovata (ignorata)", False)
            errors.append("Cartella Data sorgente non trovata")
    except Exception as exc:
        log.error(f"Errore copia Data: {exc}\n{traceback.format_exc()}")
        step_cb(f"Errore copia Data: {exc}", False)
        errors.append(str(exc))

    # Step 14 – copia gestionale.exe dal package locale
    log.info("Step 14 START: copia gestionale.exe dal package locale")
    exe_path = ""
    packaged_version = ""
    ok_copy, exe_path, err_copy, packaged_version = _copy_local_gestionale_exe(
        target_folder, download_label_cb
    )
    if ok_copy:
        log.info(f"Step 14 OK: {exe_path} | versione={packaged_version!r}")
        step_cb(f"Exe gestionale copiato: {Path(exe_path).name}", True)
    else:
        log.error(f"Step 14 FALLITO: {err_copy}")
        step_cb(f"Errore copia exe: {err_copy}", False)
        errors.append(err_copy)
    log.info("Step 14 END")

    # Step 15 – variabile d'ambiente
    log.info(f"Step 15 START: scrittura env vars in registro HKCU. data={data_folder!r} install={target_folder!r}")
    try:
        _set_persistent_env_var("GESTIONALE_DB_PATH", data_folder)
        log.info("Step 15: GESTIONALE_DB_PATH scritta")
        _set_persistent_env_var("GESTIONALE_INSTALLATION_PATH", target_folder)
        log.info("Step 15: GESTIONALE_INSTALLATION_PATH scritta")
        step_cb(
            "Variabili d'ambiente GESTIONALE_DB_PATH e GESTIONALE_INSTALLATION_PATH impostate",
            True,
        )
    except Exception as exc:
        log.error(f"Step 15 ERRORE env var: {exc}\n{traceback.format_exc()}")
        step_cb(f"Errore variabile d'ambiente: {exc}", False)
        errors.append(str(exc))
    log.info("Step 15 END")

    if run_patches and ok_copy:
        log.info(
            f"Step patch: installed_version={installed_exe_version!r}, "
            f"target_version={packaged_version!r}, db={data_folder!r}"
        )
        try:
            launcher = patchLauncher(logger=log)
            results = launcher.launch_required_patches(
                installed_exe_version,
                packaged_version,
                target_folder,
                data_folder,
                step_cb=step_cb,
            )
            failed = [result for result in results if not result.success]
            if failed:
                for result in failed:
                    errors.append(
                        f"Patch {result.patch_folder.name}/{result.script_path.name}: "
                        f"{result.error or 'errore sconosciuto'}"
                    )
            elif results:
                log.info(f"Patch completate: {len(results)} script eseguiti.")
            else:
                log.info("Nessuna patch richiesta per questo upgrade.")
        except Exception as exc:
            log.error(f"Errore lancio patch: {exc}\n{traceback.format_exc()}")
            step_cb(f"Errore lancio patch: {exc}", False)
            errors.append(str(exc))

    # Step 16 (opzionale) – shortcut desktop
    if create_shortcut:
        log.info("Step 16 START: creazione shortcut desktop")
        if exe_path and Path(exe_path).exists():
            try:
                _create_desktop_shortcut(exe_path)
                step_cb("Shortcut desktop creata", True)
                log.info("Step 16 OK")
            except Exception as exc:
                log.error(f"Step 16 ERRORE shortcut: {exc}\n{traceback.format_exc()}")
                step_cb(f"Errore shortcut: {exc}", False)
                errors.append(str(exc))
        else:
            log.warning(f"Step 16 saltato: exe non disponibile (exe_path={exe_path!r})")
            step_cb("Shortcut saltata (exe non disponibile)", False)
        log.info("Step 16 END")

    log.info(f"=== _run_installation END | errori={len(errors)} ===")
    if errors:
        for e in errors:
            log.error(f"  Errore accumulato: {e}")
        done_cb(False, "\n".join(errors))
    else:
        done_cb(True, "Installazione completata con successo!")


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

class _DatabaseExistsDialog(ctk.CTkToplevel):
    """Dialog modale mostrato quando esiste già un database nel percorso scelto.

    Imposta self.result a uno tra: "overwrite", "skip", "cancel".
    """

    def __init__(self, parent, db_path: str):
        super().__init__(parent)
        self.result = "cancel"
        self.title("Database già esistente")
        self.geometry("540x470")
        self.resizable(False, False)
        self.transient(parent)

        ctk.CTkLabel(
            self,
            text="⚠️  Database già presente",
            font=("Arial", 18, "bold"),
        ).pack(pady=(22, 6))
        ctk.CTkLabel(
            self,
            text=(
                "È stato rilevato un database esistente nel percorso selezionato:\n"
                f"{db_path}\n\nScegli come procedere:"
            ),
            font=("Arial", 12),
            wraplength=490,
            justify="left",
        ).pack(padx=25, pady=(0, 16))

        ctk.CTkButton(
            self,
            text="Sovrascrivi i dati",
            fg_color="#a83232",
            hover_color="#8a2828",
            command=lambda: self._choose("overwrite"),
        ).pack(fill="x", padx=25, pady=(0, 4))
        ctk.CTkLabel(
            self,
            text=(
                "Il database esistente verrà cancellato DEFINITIVAMENTE e ne verrà "
                "creato uno nuovo e vuoto. Tutti i dati attuali andranno persi: "
                "esegui un backup prima di procedere."
            ),
            font=("Arial", 10),
            text_color="#e09a9a",
            wraplength=490,
            justify="left",
        ).pack(padx=25, pady=(0, 14), anchor="w")

        ctk.CTkButton(
            self,
            text="Salta la creazione del database",
            command=lambda: self._choose("skip"),
        ).pack(fill="x", padx=25, pady=(0, 4))
        ctk.CTkLabel(
            self,
            text=(
                "Il database esistente viene mantenuto intatto e le tabelle non "
                "vengono ricreate. Nessun errore verrà mostrato."
            ),
            font=("Arial", 10),
            text_color="#8a8a8a",
            wraplength=490,
            justify="left",
        ).pack(padx=25, pady=(0, 14), anchor="w")

        ctk.CTkButton(
            self,
            text="Annulla",
            fg_color="gray",
            hover_color="#5a5a5a",
            command=lambda: self._choose("cancel"),
        ).pack(fill="x", padx=25, pady=(0, 4))
        ctk.CTkLabel(
            self,
            text=(
                "Annulla l'operazione per cambiare il percorso di creazione del "
                "database nella finestra precedente."
            ),
            font=("Arial", 10),
            text_color="#8a8a8a",
            wraplength=490,
            justify="left",
        ).pack(padx=25, pady=(0, 10), anchor="w")

        self.protocol("WM_DELETE_WINDOW", lambda: self._choose("cancel"))
        self.after(50, self._grab)

    def _grab(self):
        try:
            self.grab_set()
        except Exception:
            pass

    def _choose(self, value: str):
        self.result = value
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


class InstallerApp(ctk.CTk):
    def __init__(self, startup_options: dict | None = None):
        super().__init__()
        self._startup_options = startup_options or {}
        self.title("Willow Gestionale — Installer")
        self.geometry("600x680")
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")

        self._step_count = 0
        self._total_steps = _BASE_STEPS
        self._build_ui()
        self._apply_startup_options()
        log.info("InstallerApp UI costruita.")

    def _build_ui(self):
        ctk.CTkLabel(
            self,
            text="Willow Gestionale — Installer",
            font=("Arial", 20, "bold"),
        ).pack(pady=(28, 4))
        ctk.CTkLabel(
            self,
            text="Seleziona la cartella dove installare il gestionale.",
            font=("Arial", 13),
            text_color="gray",
        ).pack(pady=(0, 18))

        # Selezione percorso installazione
        ctk.CTkLabel(
            self,
            text="Percorso applicazione",
            font=("Arial", 13, "bold"),
            anchor="w",
        ).pack(fill="x", padx=40, pady=(0, 6))

        path_frame = ctk.CTkFrame(self, fg_color="transparent")
        path_frame.pack(fill="x", padx=40)

        self._install_path_entry = ctk.CTkEntry(
            path_frame,
            placeholder_text=_DEFAULT_INSTALL_PATH,
            width=400,
            font=("Arial", 13),
        )
        self._install_path_entry.insert(0, _DEFAULT_INSTALL_PATH)
        self._install_path_entry.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            path_frame,
            text="Sfoglia",
            width=90,
            command=self._browse_install_path,
        ).pack(side="left")

        ctk.CTkLabel(
            self,
            text=(
                "Se scegli un percorso diverso da quello predefinito, al termine "
                "dell'installazione dovrai riavviare il PC per usare correttamente l'app."
            ),
            font=("Arial", 11),
            text_color="#8a8a8a",
            wraplength=500,
            justify="left",
        ).pack(padx=40, pady=(8, 0), anchor="w")

        ctk.CTkLabel(
            self,
            text="Percorso dati scrivibili",
            font=("Arial", 13, "bold"),
            anchor="w",
        ).pack(fill="x", padx=40, pady=(18, 6))

        data_path_frame = ctk.CTkFrame(self, fg_color="transparent")
        data_path_frame.pack(fill="x", padx=40)

        self._data_path_entry = ctk.CTkEntry(
            data_path_frame,
            placeholder_text=_DEFAULT_DATA_PATH,
            width=400,
            font=("Arial", 13),
        )
        self._data_path_entry.insert(0, _DEFAULT_DATA_PATH)
        self._data_path_entry.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            data_path_frame,
            text="Sfoglia",
            width=90,
            command=self._browse_data_path,
        ).pack(side="left")

        ctk.CTkLabel(
            self,
            text=(
                "In questo percorso verranno creati database, Books, Backups e i "
                "file di configurazione. Il predefinito usa AppData locale e non "
                "richiede privilegi di amministratore."
            ),
            font=("Arial", 11),
            text_color="#8a8a8a",
            wraplength=500,
            justify="left",
        ).pack(padx=40, pady=(8, 0), anchor="w")

        # Checkbox shortcut
        self._shortcut_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            self,
            text="Crea shortcut sul Desktop",
            variable=self._shortcut_var,
            font=("Arial", 13),
        ).pack(pady=(14, 0))

        # Label percorso log
        ctk.CTkLabel(
            self,
            text=f"Log di debug: {_LOG_PATH}",
            font=("Arial", 10),
            text_color="#888888",
        ).pack(pady=(6, 0))

        # Bottone installa
        self._install_btn = ctk.CTkButton(
            self,
            text="Installa",
            width=180,
            height=42,
            font=("Arial", 15, "bold"),
            command=self._start_installation,
        )
        self._install_btn.pack(pady=(14, 8))

        # Progress bar
        self._progress_bar = ctk.CTkProgressBar(self, width=520, mode="determinate")
        self._progress_bar.set(0)
        self._progress_bar.pack(pady=(4, 2))

        self._progress_label = ctk.CTkLabel(
            self, text="In attesa...", font=("Arial", 12), text_color="gray"
        )
        self._progress_label.pack(pady=(0, 8))

        # Log scrollabile
        self._log_frame = ctk.CTkScrollableFrame(self, width=520, height=200)
        self._log_frame.pack(padx=40, pady=(0, 18))

    def _browse_install_path(self):
        folder = filedialog.askdirectory(title="Seleziona cartella di installazione")
        if folder:
            self._install_path_entry.delete(0, "end")
            self._install_path_entry.insert(0, folder)
            log.info(f"Percorso installazione selezionato: {folder}")

    def _browse_data_path(self):
        folder = filedialog.askdirectory(title="Seleziona cartella dati")
        if folder:
            self._data_path_entry.delete(0, "end")
            self._data_path_entry.insert(0, folder)
            log.info(f"Percorso dati selezionato: {folder}")

    def _apply_startup_options(self):
        install_path = self._startup_options.get("install_path")
        if install_path:
            self._install_path_entry.delete(0, "end")
            self._install_path_entry.insert(0, install_path)

        data_path = self._startup_options.get("data_path")
        if data_path:
            self._data_path_entry.delete(0, "end")
            self._data_path_entry.insert(0, data_path)

        self._shortcut_var.set(self._startup_options.get("create_shortcut", True))

        if self._startup_options.get("auto_install"):
            self.after(200, self._start_installation)

    def _add_log_row(self, text: str, ok: bool):
        icon = "✅" if ok else "❌"
        color = "#c8ffc8" if ok else "#ffc8c8"
        ctk.CTkLabel(
            self._log_frame,
            text=f"{icon}  {text}",
            font=("Arial", 12),
            text_color=color,
            anchor="w",
        ).pack(fill="x", padx=5, pady=1)

    def _on_step(self, msg: str, ok: bool):
        self._step_count += 1
        progress = min(self._step_count / self._total_steps, 1.0)

        def _update():
            self._progress_bar.set(progress)
            pct = int(progress * 100)
            self._progress_label.configure(text=f"{msg} ({pct}%)")
            self._add_log_row(msg, ok)
            self._log_frame._parent_canvas.yview_moveto(1.0)

        self.after(0, _update)

    def _on_download_progress(self, msg: str):
        self.after(0, lambda: self._progress_label.configure(text=msg))

    def _on_done(self, success: bool, _msg: str):
        def _update():
            if success:
                self._progress_bar.set(1.0)
                self._progress_label.configure(
                    text="✅ Installazione completata!", text_color="#6fcf6f"
                )
            else:
                self._progress_label.configure(
                    text="❌ Installazione terminata con errori.", text_color="#cf6f6f"
                )
            self._install_btn.configure(
                text="Chiudi", state="normal", command=self.destroy
            )

        self.after(0, _update)

    @staticmethod
    def _is_default_install_path(path: str) -> bool:
        normalized_path = os.path.normcase(os.path.normpath(path))
        normalized_default = os.path.normcase(os.path.normpath(_DEFAULT_INSTALL_PATH))
        return normalized_path == normalized_default

    def _start_installation(self):
        target = self._install_path_entry.get().strip() or _DEFAULT_INSTALL_PATH
        data_target = self._data_path_entry.get().strip() or _DEFAULT_DATA_PATH
        create_shortcut = self._shortcut_var.get()
        log.info(
            f"Avvio installazione: target={target!r}, data_target={data_target!r}, shortcut={create_shortcut}"
        )
        if _requires_elevation(target) and not _is_running_as_admin():
            log.info("Percorso protetto rilevato: richiesta elevazione UAC.")
            relaunched = _relaunch_as_admin(target, data_target, create_shortcut)
            if relaunched:
                self.destroy()
                return
            messagebox.showwarning(
                "Permessi richiesti",
                "Per installare in questa cartella devi confermare il prompt di "
                "amministratore di Windows.",
            )
            return
        if not self._is_default_install_path(target):
            messagebox.showinfo(
                "Riavvio richiesto",
                "Hai scelto un percorso di installazione diverso da quello "
                "predefinito.\n\nPer usare correttamente Willow Gestionale "
                "dovrai riavviare il PC al termine dell'installazione.",
            )

        # Controllo installazione pregressa: DB + exe applicativo.
        skip_db = False
        overwrite_db = False
        run_patches = False
        installed_exe_path = ""
        installed_exe_version = ""
        db_file = Path(data_target) / "gestionale.db"
        existing_exe = patchLauncher.find_existing_executable(target)
        has_existing_db = db_file.exists()
        has_existing_exe = existing_exe is not None

        log.info(
            f"Controllo pregresso: db_exists={has_existing_db} ({db_file}), "
            f"exe_exists={has_existing_exe} ({existing_exe})"
        )

        if has_existing_db and has_existing_exe:
            installed_exe_path = str(existing_exe)
            installed_exe_version = patchLauncher.extract_version_token(existing_exe.name)
            skip_db = True
            run_patches = True
            log.info(
                f"Installazione pregressa rilevata: exe={installed_exe_path}, "
                f"version={installed_exe_version!r}. DB mantenuto e patch abilitate."
            )
        elif has_existing_db:
            log.info(f"Database esistente rilevato: {db_file}")
            dialog = _DatabaseExistsDialog(self, str(db_file))
            self.wait_window(dialog)
            choice = dialog.result
            log.info(f"Scelta utente su database esistente: {choice}")
            if choice == "cancel":
                log.info("Installazione annullata dall'utente per cambiare percorso.")
                return
            skip_db = choice == "skip"
            overwrite_db = choice == "overwrite"
        elif has_existing_exe:
            log.info(
                f"Exe esistente senza database rilevato: {existing_exe}. "
                "Installazione trattata come nuova per il database; patch non abilitate."
            )

        if skip_db:
            patch_steps = max(1, patchLauncher(logger=log).count_required_patches(installed_exe_version)) if run_patches else 0
            self._total_steps = 5 + patch_steps + (1 if create_shortcut else 0)
        else:
            self._total_steps = _BASE_STEPS + (1 if create_shortcut else 0)
        self._install_btn.configure(state="disabled")
        self._step_count = 0
        self._progress_bar.set(0)
        for w in self._log_frame.winfo_children():
            w.destroy()

        threading.Thread(
            target=_run_installation,
            args=(
                target,
                data_target,
                create_shortcut,
                self._on_step,
                self._on_download_progress,
                self._on_done,
                skip_db,
                overwrite_db,
                run_patches,
                installed_exe_version,
                installed_exe_path,
            ),
            daemon=True,
        ).start()


if __name__ == "__main__":
    startup_options = _consume_startup_options()
    app = InstallerApp(startup_options=startup_options)
    app.mainloop()

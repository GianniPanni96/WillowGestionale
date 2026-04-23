import os
import sys
import json
import shutil
import threading
import winreg
import ctypes
import urllib.request
import urllib.error
import logging
import traceback
from pathlib import Path
from tkinter import filedialog
import customtkinter as ctk


_GITHUB_API_LATEST = "https://api.github.com/repos/GianniPanni96/WillowGestionale/releases?per_page=1"
_DEFAULT_INSTALL_PATH = r"C:\Program Files\WillowGestionale"
_BASE_STEPS = 15  # 1 cartelle + 11 tabelle + 1 Data + 1 download + 1 env var

# ---------------------------------------------------------------------------
# Logging setup – scrive su file E su stdout
# Il file di log è in %TEMP%\willow_installer_debug.log
# ---------------------------------------------------------------------------

_LOG_PATH = Path(os.environ.get("TEMP", ".")) / "willow_installer_debug.log"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(funcName)s: %(message)s",
    handlers=[
        logging.FileHandler(str(_LOG_PATH), mode="w", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("WillowInstaller")
log.info("=== Willow Installer avviato ===")
log.info(f"Log file: {_LOG_PATH}")
log.info(f"Python: {sys.version}")
log.info(f"Frozen: {getattr(sys, 'frozen', False)}")
log.info(f"Executable: {sys.executable}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_source_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        p = Path(sys.executable).parent / "Data"
    else:
        p = Path(__file__).parent.parent / "Data"
    log.debug(f"source_data_dir => {p}  (exists={p.exists()})")
    return p


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


def _create_desktop_shortcut(exe_path: str) -> None:
    log.debug(f"Creazione shortcut per: {exe_path}")
    ps = (
        '$desktop = [Environment]::GetFolderPath("Desktop"); '
        '$s = (New-Object -ComObject WScript.Shell).CreateShortcut($desktop + "\\Willow Gestionale.lnk"); '
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
# Download
# ---------------------------------------------------------------------------

def _download_latest_exe(target_folder: str, download_label_cb) -> tuple:
    """Scarica l'exe dell'ultima release. Ritorna (ok, percorso_file, errore)."""
    log.info(f"=== Inizio download da GitHub ===")
    log.info(f"API URL: {_GITHUB_API_LATEST}")
    log.info(f"Cartella destinazione: {target_folder}")

    try:
        # 1. Chiamata API GitHub
        log.debug("Apertura connessione all'API GitHub...")
        req = urllib.request.Request(
            _GITHUB_API_LATEST,
            headers={
                "User-Agent": "WillowInstaller/1.0",
                "Accept": "application/vnd.github+json",
            },
        )
        log.debug(f"Headers richiesta: {req.headers}")

        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                status = resp.status
                headers = dict(resp.headers)
                raw_body = resp.read()
        except urllib.error.HTTPError as http_err:
            raw_body = http_err.read()
            log.error(f"HTTPError {http_err.code}: {http_err.reason}")
            log.error(f"Response headers: {dict(http_err.headers)}")
            log.error(f"Response body: {raw_body.decode('utf-8', errors='replace')}")
            return False, "", f"HTTP {http_err.code}: {http_err.reason}"
        except urllib.error.URLError as url_err:
            log.error(f"URLError: {url_err.reason}")
            return False, "", f"Errore di rete: {url_err.reason}"

        log.info(f"Risposta API: status={status}")
        log.debug(f"Response headers: {headers}")

        body_str = raw_body.decode("utf-8", errors="replace")
        log.debug(f"Response body (primi 2000 char): {body_str[:2000]}")

        # 2. Parse JSON
        try:
            parsed = json.loads(body_str)
        except json.JSONDecodeError as json_err:
            log.error(f"Errore parsing JSON: {json_err}")
            log.error(f"Body grezzo: {body_str}")
            return False, "", f"Risposta JSON non valida: {json_err}"

        # L'endpoint ?per_page=1 ritorna una lista
        release = parsed[0] if isinstance(parsed, list) else parsed

        log.info(f"Release tag: {release.get('tag_name', 'N/A')}")
        log.info(f"Release name: {release.get('name', 'N/A')}")
        log.info(f"Pre-release: {release.get('prerelease', False)}")
        log.info(f"Numero asset: {len(release.get('assets', []))}")

        assets = release.get("assets", [])
        for i, a in enumerate(assets):
            log.debug(f"  Asset[{i}]: name={a.get('name')} size={a.get('size')} url={a.get('browser_download_url')}")

        # 3. Trova il primo .exe
        exe_assets = [a for a in assets if a.get("name", "").lower().endswith(".exe")]
        log.info(f"Asset .exe trovati: {[a['name'] for a in exe_assets]}")

        if not exe_assets:
            msg = "Nessun file .exe trovato negli asset della release"
            log.error(msg)
            return False, "", msg

        asset = exe_assets[0]
        download_url = asset["browser_download_url"]
        dest_path = Path(target_folder) / asset["name"]
        total_size = asset.get("size", 0)

        log.info(f"Scelto asset: {asset['name']} ({total_size} bytes)")
        log.info(f"URL download: {download_url}")
        log.info(f"Destinazione: {dest_path}")

        # 4. Download con progress
        _last_pct = [-1]

        def _reporthook(block_num, block_size, _total):
            if total_size > 0:
                pct = min(int(block_num * block_size / total_size * 100), 100)
                if pct != _last_pct[0] and pct % 5 == 0:
                    _last_pct[0] = pct
                    log.debug(f"Download progress: {pct}%")
                    download_label_cb(f"Download {asset['name']}: {pct}%")

        download_label_cb(f"Download {asset['name']}: 0%")
        log.debug("Avvio urlretrieve...")
        urllib.request.urlretrieve(download_url, str(dest_path), reporthook=_reporthook)

        actual_size = dest_path.stat().st_size
        log.info(f"Download completato. Dimensione file scaricato: {actual_size} bytes")
        return True, str(dest_path), ""

    except Exception as exc:
        log.error(f"Eccezione inattesa in _download_latest_exe: {type(exc).__name__}: {exc}")
        log.error(traceback.format_exc())
        return False, "", f"{type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------
# Funzione principale di installazione (thread secondario)
# ---------------------------------------------------------------------------

def _run_installation(
    target_folder: str,
    create_shortcut: bool,
    step_cb,
    download_label_cb,
    done_cb,
) -> None:
    log.info(f"=== _run_installation START | target={target_folder} | shortcut={create_shortcut} ===")
    errors = []

    # Step 1 – struttura cartelle
    log.info("Step 1: creazione struttura cartelle")
    try:
        Path(target_folder).mkdir(parents=True, exist_ok=True)
        (Path(target_folder) / "Books").mkdir(exist_ok=True)
        (Path(target_folder) / "Backups").mkdir(exist_ok=True)
        log.info("Cartelle create con successo.")
        step_cb("Struttura cartelle creata", True)
    except Exception as exc:
        log.error(f"Errore creazione cartelle: {exc}\n{traceback.format_exc()}")
        step_cb(f"Errore creazione cartelle: {exc}", False)
        done_cb(False, str(exc))
        return

    # Steps 2–12 – tabelle DB
    log.info("Steps 2-12: creazione tabelle database")
    try:
        from DatabaseCreation.Db_initializer import create_all_tables
        for name, ok, err in create_all_tables(target_folder):
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

    # Step 14 – download gestionale.exe
    log.info("Step 14: download gestionale.exe")
    exe_path = ""
    ok_dl, exe_path, err_dl = _download_latest_exe(target_folder, download_label_cb)
    if ok_dl:
        log.info(f"Download OK: {exe_path}")
        step_cb(f"Download completato: {Path(exe_path).name}", True)
    else:
        log.error(f"Download FALLITO: {err_dl}")
        step_cb(f"Errore download: {err_dl}", False)
        errors.append(err_dl)

    # Step 15 – variabile d'ambiente
    log.info("Step 15: impostazione variabile d'ambiente")
    try:
        _set_persistent_env_var("GESTIONALE_DB_PATH", target_folder)
        step_cb("Variabile d'ambiente GESTIONALE_DB_PATH impostata", True)
    except Exception as exc:
        log.error(f"Errore env var: {exc}\n{traceback.format_exc()}")
        step_cb(f"Errore variabile d'ambiente: {exc}", False)
        errors.append(str(exc))

    # Step 16 (opzionale) – shortcut desktop
    if create_shortcut:
        log.info("Step 16: creazione shortcut desktop")
        if exe_path and Path(exe_path).exists():
            try:
                _create_desktop_shortcut(exe_path)
                step_cb("Shortcut desktop creata", True)
            except Exception as exc:
                log.error(f"Errore shortcut: {exc}\n{traceback.format_exc()}")
                step_cb(f"Errore shortcut: {exc}", False)
                errors.append(str(exc))
        else:
            log.warning(f"Shortcut saltata: exe non disponibile (exe_path={exe_path!r})")
            step_cb("Shortcut saltata (exe non disponibile)", False)

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

class InstallerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Willow Gestionale — Installer")
        self.geometry("600x600")
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")

        self._step_count = 0
        self._total_steps = _BASE_STEPS
        self._build_ui()
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

        # Selezione percorso
        path_frame = ctk.CTkFrame(self, fg_color="transparent")
        path_frame.pack(fill="x", padx=40)

        self._path_entry = ctk.CTkEntry(
            path_frame,
            placeholder_text=_DEFAULT_INSTALL_PATH,
            width=400,
            font=("Arial", 13),
        )
        self._path_entry.insert(0, _DEFAULT_INSTALL_PATH)
        self._path_entry.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            path_frame,
            text="Sfoglia",
            width=90,
            command=self._browse,
        ).pack(side="left")

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

    def _browse(self):
        folder = filedialog.askdirectory(title="Seleziona cartella di installazione")
        if folder:
            self._path_entry.delete(0, "end")
            self._path_entry.insert(0, folder)
            log.info(f"Percorso selezionato: {folder}")

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

    def _start_installation(self):
        target = self._path_entry.get().strip() or _DEFAULT_INSTALL_PATH
        create_shortcut = self._shortcut_var.get()
        log.info(f"Avvio installazione: target={target!r}, shortcut={create_shortcut}")

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
                create_shortcut,
                self._on_step,
                self._on_download_progress,
                self._on_done,
            ),
            daemon=True,
        ).start()


if __name__ == "__main__":
    app = InstallerApp()
    app.mainloop()

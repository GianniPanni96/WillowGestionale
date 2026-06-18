"""
Verifica all'avvio che il database del gestionale sia presente e popolato di
tutte le tabelle attese. In caso contrario mostra un messaggio nativo
all'utente con istruzioni e termina il processo, evitando crash silenziosi
piu' avanti nella catena di import (Model.py, AppContext, ecc.).
"""

from __future__ import annotations

import ctypes
import os
import sqlite3
import sys
from pathlib import Path
from typing import NoReturn


# Tabelle che il gestionale si aspetta di trovare nel database. Ricavate dai
# moduli DatabaseCreation/Create_table_* lanciati dall'installer al primo avvio.
EXPECTED_TABLES = (
    "accounts",
    "users",
    "clients",
    "invoices",
    "expenses",
    "payments",
    "productions",
    "transfers",
    "suppliers",
    "salaries",
    "refunds",
    "admin",
)

DB_PATH_ENV_VAR = "GESTIONALE_DB_PATH"

_APP_TITLE = "Willow Gestionale"


def _is_windows() -> bool:
    return os.name == "nt"


def _show_error_and_exit(message: str) -> NoReturn:
    """Popup nativo (Windows) + termina l'intero processo, incluso il thread scheduler."""
    if _is_windows():
        try:
            ctypes.windll.user32.MessageBoxW(None, message, _APP_TITLE, 0x10)
        except Exception:
            pass
    print(message, file=sys.stderr)
    os._exit(1)


def _list_existing_tables(db_path: Path) -> set[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        return {row[0] for row in cursor.fetchall()}
    finally:
        conn.close()


def verify_database_health(db_path: Path) -> None:
    """Controlla che il DB esista e contenga tutte le tabelle attese.

    Mostra un popup e termina il processo se uno dei due controlli fallisce.
    Niente eccezioni che possano essere ingoiate altrove.
    """
    db_path = Path(db_path)

    if not db_path.exists():
        _show_error_and_exit(
            "Database non trovato.\n\n"
            f"Percorso atteso:\n{db_path}\n\n"
            "Cosa fare:\n"
            "1. Se e' la prima volta che usi l'app, lancia l'installer\n"
            "   (installer.exe) dal pacchetto di installazione.\n"
            "2. Se hai gia' installato il gestionale ma hai spostato la\n"
            f"   cartella dati, imposta la variabile d'ambiente\n"
            f"   {DB_PATH_ENV_VAR} e riavvia Windows.\n"
            "3. Se il database e' stato cancellato, rilancia l'installer."
        )
        return  # unreachable, ma documenta l'invariante

    try:
        existing = _list_existing_tables(db_path)
    except sqlite3.DatabaseError as exc:
        _show_error_and_exit(
            "Il file database esiste ma non e' un database SQLite valido.\n\n"
            f"Percorso:\n{db_path}\n\n"
            f"Dettaglio errore:\n{exc}\n\n"
            "Cosa fare:\n"
            "1. Ripristina un backup dalla cartella 'Backups' accanto al DB.\n"
            "2. In alternativa rilancia l'installer scegliendo\n"
            "   'Sovrascrivi i dati' per ricreare un database vuoto."
        )
        return

    missing = [table for table in EXPECTED_TABLES if table not in existing]
    if missing:
        _show_error_and_exit(
            "Il database esiste ma mancano alcune tabelle richieste.\n\n"
            f"Percorso:\n{db_path}\n\n"
            f"Tabelle mancanti ({len(missing)}):\n  - " + "\n  - ".join(missing) + "\n\n"
            "Cosa fare:\n"
            "Probabilmente gli script di creazione tabelle non sono stati\n"
            "eseguiti. Rilancia l'installer (installer.exe) sul percorso\n"
            "applicazione attuale: l'installer riconoscera' l'installazione\n"
            "esistente e potrai scegliere 'Sovrascrivi i dati' per ricreare\n"
            "il database completo, oppure puoi eseguire manualmente gli\n"
            "script in DatabaseCreation/ del pacchetto di installazione."
        )
        return

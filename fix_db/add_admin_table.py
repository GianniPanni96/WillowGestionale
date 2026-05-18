"""
Migration script standalone: crea la tabella ``admin`` per supportare il
ruolo di amministratore del sistema (singolo admin, separato dagli
utenti normali).

Pensato per essere eseguito sui PC dove l'app e' gia' in produzione:
- nessuna dipendenza dal resto del codice del progetto;
- crea un backup .pre_admin_<timestamp>.bak prima di modificare il DB;
- idempotente: se la tabella esiste gia' non fa nulla.

USO
---
    set GESTIONALE_DB_PATH=C:\\percorso\\al\\db\\folder
    python add_admin_table.py

oppure passando il path completo come primo argomento:
    python add_admin_table.py "C:\\percorso\\al\\db\\folder\\gestionale.db"

L'admin va poi creato dall'interfaccia al primo avvio post-update
(dialog dedicato che si attiva automaticamente se nessun admin esiste).

EXIT CODES
----------
0  ok                 1  argomento/percorso non valido
2  errore SQL         3  permessi/IO
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import sys
from datetime import datetime


PATH_ENV_VAR = "GESTIONALE_DB_PATH"
DB_FILENAME = "gestionale.db"
TABLE_NAME = "admin"

CREATE_TABLE_SQL = """
CREATE TABLE admin (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL DEFAULT 'ADMIN',
    password_login TEXT NOT NULL,
    recovery_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


def _resolve_db_path() -> str:
    if len(sys.argv) >= 2:
        candidate = sys.argv[1]
    else:
        base = os.environ.get(PATH_ENV_VAR)
        if not base:
            print(
                f"ERRORE: variabile d'ambiente {PATH_ENV_VAR} non impostata e "
                f"nessun percorso passato come primo argomento.",
                file=sys.stderr,
            )
            sys.exit(1)
        candidate = os.path.join(base, DB_FILENAME)

    if not os.path.isfile(candidate):
        print(f"ERRORE: database non trovato in '{candidate}'.", file=sys.stderr)
        sys.exit(1)
    return candidate


def _backup_db(db_path: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.pre_admin_{ts}.bak"
    shutil.copy2(db_path, backup_path)
    print(f"Backup creato: {backup_path}")
    return backup_path


def _table_exists(cursor: sqlite3.Cursor, table: str) -> bool:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return cursor.fetchone() is not None


def main():
    print("=" * 60)
    print(" Willow Gestionale - creazione tabella admin")
    print("=" * 60)

    db_path = _resolve_db_path()
    print(f"DB target: {db_path}")

    try:
        _backup_db(db_path)
    except OSError as exc:
        print(f"ERRORE creando il backup: {exc}", file=sys.stderr)
        sys.exit(3)

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        if _table_exists(cursor, TABLE_NAME):
            print(f"La tabella '{TABLE_NAME}' esiste gia': nessuna modifica necessaria.")
            return
        print(f"Creo la tabella '{TABLE_NAME}'...")
        cursor.execute(CREATE_TABLE_SQL)
        conn.commit()
        if not _table_exists(cursor, TABLE_NAME):
            print(f"ERRORE di verifica: la tabella '{TABLE_NAME}' non risulta creata.", file=sys.stderr)
            sys.exit(2)
        print(f"Tabella '{TABLE_NAME}' creata con successo.")
    except sqlite3.Error as exc:
        conn.rollback()
        print(f"ERRORE SQL: {exc}", file=sys.stderr)
        sys.exit(2)
    finally:
        conn.close()

    print(
        "\nProssimi passi:\n"
        "  - Avviare l'app: al primo avvio verra' chiesto di creare\n"
        "    l'amministratore con una password (e un recovery code)."
    )


if __name__ == "__main__":
    main()

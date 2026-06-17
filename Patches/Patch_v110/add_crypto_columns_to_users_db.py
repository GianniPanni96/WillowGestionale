"""
Migration script standalone: aggiunge le colonne ``crypto_salt`` e
``crypto_check`` alla tabella ``users`` per supportare il nuovo modello
di crittografia per-utente (chiave derivata dalla password).

Pensato per essere eseguito sui PC dove l'app e' gia' in produzione:
- nessuna dipendenza dal resto del codice del progetto;
- crea un backup .db_backup_<timestamp> prima di modificare il DB;
- idempotente: se le colonne esistono gia' non fa nulla.

USO
---
Comando consigliato dal PC dove e' installato il gestionale:

    set GESTIONALE_DB_PATH=C:\\percorso\\al\\db\\folder
    python add_crypto_columns_to_users_db.py

Il file sqlite atteso e' ``<GESTIONALE_DB_PATH>\\gestionale.db``.

I dati gia' cifrati con la vecchia master key (campi
``username_provider`` / ``password_provider``) NON vengono toccati da
questo script: la migrazione avviene in modo trasparente al primo
login post-update, dove la nuova chiave per-utente viene derivata
dalla password digitata.

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
NEW_COLUMNS = (
    ("crypto_salt", "TEXT"),
    ("crypto_check", "TEXT"),
    ("recovery_hash", "TEXT"),
)


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
    backup_path = f"{db_path}.pre_crypto_{ts}.bak"
    shutil.copy2(db_path, backup_path)
    print(f"Backup creato: {backup_path}")
    return backup_path


def _existing_columns(cursor: sqlite3.Cursor, table: str) -> set[str]:
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def _add_missing_columns(cursor: sqlite3.Cursor):
    if "users" not in _all_tables(cursor):
        print("ERRORE: la tabella 'users' non esiste in questo DB.", file=sys.stderr)
        sys.exit(2)

    existing = _existing_columns(cursor, "users")
    added = []
    for col_name, col_type in NEW_COLUMNS:
        if col_name in existing:
            print(f"  - {col_name}: gia' presente, salto.")
            continue
        cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
        added.append(col_name)
        print(f"  + {col_name} {col_type}: aggiunto.")
    return added


def _all_tables(cursor: sqlite3.Cursor) -> set[str]:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {row[0] for row in cursor.fetchall()}


def _verify(cursor: sqlite3.Cursor):
    cols = _existing_columns(cursor, "users")
    missing = [c for c, _ in NEW_COLUMNS if c not in cols]
    if missing:
        print(f"ERRORE di verifica: colonne ancora mancanti: {missing}", file=sys.stderr)
        sys.exit(2)
    print("Verifica OK: tutte le nuove colonne sono presenti.")


def main():
    print("=" * 60)
    print(" Willow Gestionale - migrazione schema crypto utenti")
    print("=" * 60)

    db_path = _resolve_db_path()
    print(f"DB target: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        if "users" not in _all_tables(cursor):
            print("ERRORE: la tabella 'users' non esiste in questo DB.", file=sys.stderr)
            sys.exit(2)
        missing = [col_name for col_name, _ in NEW_COLUMNS if col_name not in _existing_columns(cursor, "users")]
        if not missing:
            print("Nessuna modifica necessaria: schema gia' allineato.")
            _verify(cursor)
            return
        try:
            _backup_db(db_path)
        except OSError as exc:
            print(f"ERRORE creando il backup: {exc}", file=sys.stderr)
            sys.exit(3)
        print("Aggiungo le colonne mancanti...")
        added = _add_missing_columns(cursor)
        conn.commit()
        _verify(cursor)
    except sqlite3.Error as exc:
        conn.rollback()
        print(f"ERRORE SQL: {exc}", file=sys.stderr)
        sys.exit(2)
    finally:
        conn.close()

    if added:
        print(f"\nMigrazione completata. Aggiunte: {', '.join(added)}.")
    else:
        print("\nNessuna modifica necessaria: schema gia' allineato.")
    print(
        "I dati legacy (username_provider/password_provider) verranno migrati\n"
        "automaticamente al prossimo login di ciascun utente."
    )


if __name__ == "__main__":
    main()

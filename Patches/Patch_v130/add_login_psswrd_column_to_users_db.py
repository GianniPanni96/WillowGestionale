import os
import shutil
import sqlite3
from datetime import datetime


PATH_ENV_VAR = "GESTIONALE_DB_PATH"
DB_FILENAME = "gestionale.db"
TABLE_NAME = "users"
TEMP_TABLE_NAME = "users_temp_patch_v130"

DESIRED_ORDER = [
    "id",
    "first_name",
    "last_name",
    "partita_iva",
    "codice_fiscale",
    "telefono",
    "email",
    "regime_fiscale",
    "anno_apertura_piva",
    "reddito_esterno",
    "spese_dedotte_esterne",
    "conto_corrente_id",
    "provider_fatture",
    "username_provider",
    "password_provider",
    "password_login",
    "status",
    "acconto_irpef",
    "acconto_inps",
    "photo_path",
    "created_at",
    "updated_at",
    "crypto_salt",
    "crypto_check",
    "recovery_hash",
]

KNOWN_COLUMN_DEFINITIONS = {
    "id": "id INTEGER PRIMARY KEY AUTOINCREMENT",
    "first_name": "first_name TEXT NOT NULL",
    "last_name": "last_name TEXT NOT NULL",
    "partita_iva": "partita_iva TEXT NOT NULL UNIQUE",
    "codice_fiscale": "codice_fiscale TEXT UNIQUE",
    "telefono": "telefono TEXT",
    "email": "email TEXT",
    "regime_fiscale": "regime_fiscale TEXT NOT NULL",
    "anno_apertura_piva": "anno_apertura_piva INTEGER NOT NULL",
    "reddito_esterno": "reddito_esterno REAL NOT NULL DEFAULT 0",
    "spese_dedotte_esterne": "spese_dedotte_esterne REAL NOT NULL DEFAULT 0",
    "conto_corrente_id": "conto_corrente_id INTEGER",
    "provider_fatture": "provider_fatture TEXT NOT NULL",
    "username_provider": "username_provider TEXT",
    "password_provider": "password_provider TEXT",
    "password_login": "password_login TEXT",
    "status": "status INTEGER NOT NULL DEFAULT 1",
    "acconto_irpef": "acconto_irpef REAL NOT NULL DEFAULT 0",
    "acconto_inps": "acconto_inps REAL NOT NULL DEFAULT 0",
    "photo_path": "photo_path TEXT",
    "created_at": "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "crypto_salt": "crypto_salt TEXT",
    "crypto_check": "crypto_check TEXT",
    "recovery_hash": "recovery_hash TEXT",
}


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def resolve_db_path() -> str:
    path = os.environ.get(PATH_ENV_VAR)
    if not path:
        raise EnvironmentError(f"La variabile d'ambiente {PATH_ENV_VAR} non e' stata configurata.")

    candidate = path if path.lower().endswith(".db") else os.path.join(path, DB_FILENAME)
    if not os.path.exists(candidate):
        raise FileNotFoundError(f"Database non trovato in: {candidate}")
    return candidate


def create_backup(db_path: str) -> str:
    directory = os.path.dirname(db_path)
    filename = os.path.basename(db_path)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(directory, f"{filename}.pre_password_login_{stamp}.bak")
    shutil.copy2(db_path, backup_path)
    print(f"Backup creato: {backup_path}")
    return backup_path


def table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def get_columns_info(cursor: sqlite3.Cursor):
    cursor.execute(f"PRAGMA table_info({quote_identifier(TABLE_NAME)})")
    return cursor.fetchall()


def get_column_names(cursor: sqlite3.Cursor) -> list[str]:
    return [column[1] for column in get_columns_info(cursor)]


def build_final_order(existing_columns: list[str]) -> list[str]:
    ordered = [
        column
        for column in DESIRED_ORDER
        if column in existing_columns or column == "password_login"
    ]
    ordered.extend(column for column in existing_columns if column not in ordered)
    return ordered


def column_definition(column_name: str, columns_info_by_name: dict[str, tuple]) -> str:
    if column_name in KNOWN_COLUMN_DEFINITIONS:
        return KNOWN_COLUMN_DEFINITIONS[column_name]

    info = columns_info_by_name[column_name]
    name = quote_identifier(column_name)
    column_type = info[2] or "TEXT"
    definition = f"{name} {column_type}"
    if info[3]:
        definition += " NOT NULL"
    if info[4] is not None:
        definition += f" DEFAULT {info[4]}"
    return definition


def rebuild_users_table(cursor: sqlite3.Cursor, final_order: list[str]):
    columns_info = get_columns_info(cursor)
    existing_columns = [column[1] for column in columns_info]
    info_by_name = {column[1]: column for column in columns_info}

    definitions = [column_definition(column, info_by_name) for column in final_order]
    definitions.append("FOREIGN KEY (conto_corrente_id) REFERENCES accounts (id)")

    cursor.execute(f"DROP TABLE IF EXISTS {quote_identifier(TEMP_TABLE_NAME)}")
    cursor.execute(
        f"CREATE TABLE {quote_identifier(TEMP_TABLE_NAME)} ({', '.join(definitions)})"
    )

    select_columns = [
        quote_identifier(column) if column in existing_columns else "NULL"
        for column in final_order
    ]
    quoted_final_columns = ", ".join(quote_identifier(column) for column in final_order)
    cursor.execute(
        f"""
        INSERT INTO {quote_identifier(TEMP_TABLE_NAME)} ({quoted_final_columns})
        SELECT {', '.join(select_columns)}
        FROM {quote_identifier(TABLE_NAME)}
        """
    )
    cursor.execute(f"DROP TABLE {quote_identifier(TABLE_NAME)}")
    cursor.execute(
        f"ALTER TABLE {quote_identifier(TEMP_TABLE_NAME)} RENAME TO {quote_identifier(TABLE_NAME)}"
    )


def safe_add_password_login_column(db_path: str) -> bool:
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, TABLE_NAME):
            raise RuntimeError(f"La tabella '{TABLE_NAME}' non esiste in questo DB.")

        current_order = get_column_names(cursor)
        final_order = build_final_order(current_order)

        if "password_login" in current_order and current_order == final_order:
            print("La colonna password_login e' gia' presente nell'ordine corretto.")
            return False

        create_backup(db_path)
        rebuild_users_table(cursor, final_order)

        verified_order = get_column_names(cursor)
        if "password_login" not in verified_order:
            raise RuntimeError("Verifica fallita: password_login non risulta presente.")
        if verified_order != final_order:
            raise RuntimeError("Verifica fallita: ordine finale della tabella users non coerente.")

        conn.commit()
        print("Tabella users aggiornata in modo idempotente.")
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def verify_table_structure(db_path: str):
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({quote_identifier(TABLE_NAME)})")
        columns = cursor.fetchall()

        print("\nStruttura finale della tabella users:")
        for col in columns:
            print(f"  {col[0]}: {col[1]} ({col[2]})")
    finally:
        conn.close()


if __name__ == "__main__":
    db_path = resolve_db_path()
    print(f"Connessione al database: {db_path}")
    changed = safe_add_password_login_column(db_path)
    if changed:
        verify_table_structure(db_path)
    print("\nOperazione completata con successo!")

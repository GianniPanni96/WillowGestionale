import os
import sqlite3


def safe_add_password_login_column(db_path: str):
    """
    Aggiunge in modo sicuro la colonna PASSWORD_LOGIN alla tabella 'users'
    nella posizione corretta secondo l'enum, mantenendo tutti i dati.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. Verifica se la colonna esiste già
        cursor.execute("PRAGMA table_info(users)")
        columns_info = cursor.fetchall()
        column_names = [col[1] for col in columns_info]

        # 2. Definisci l'ordine corretto delle colonne basato sull'enum
        correct_column_order = [
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
            "password_login",  # Questa è la nuova colonna
            "status",
            "acconto_irpef",
            "acconto_inps",
            "photo_path",
            "created_at",
            "updated_at"
        ]

        # 3. Se la colonna non esiste, la aggiungiamo
        if 'password_login' not in column_names:
            print("Aggiungo la colonna PASSWORD_LOGIN...")
            cursor.execute("ALTER TABLE users ADD COLUMN password_login TEXT")
            # Dopo l'aggiunta, ricostruiamo la tabella per avere l'ordine corretto
            _rebuild_table_with_correct_order(cursor, correct_column_order)
        else:
            # Se esiste già, verifichiamo se l'ordine è corretto
            current_order = [col[1] for col in columns_info]
            if current_order != correct_column_order:
                print("L'ordine delle colonne non è corretto. Ricostruisco la tabella...")
                _rebuild_table_with_correct_order(cursor, correct_column_order)
            else:
                print("La colonna PASSWORD_LOGIN è già presente nella posizione corretta.")
                return

        print("Operazione completata con successo.")

    except Exception as e:
        print(f"Errore durante l'operazione: {e}")
        conn.rollback()
        raise
    finally:
        conn.commit()
        conn.close()


def _rebuild_table_with_correct_order(cursor, correct_column_order):
    """
    Ricostruisce la tabella users con l'ordine delle colonne corretto.
    """
    # 1. Crea una tabella temporanea con l'ordine corretto
    create_columns = [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "first_name TEXT NOT NULL",
        "last_name TEXT NOT NULL",
        "partita_iva TEXT NOT NULL UNIQUE",
        "codice_fiscale TEXT UNIQUE",
        "telefono TEXT",
        "email TEXT",
        "regime_fiscale TEXT NOT NULL",
        "anno_apertura_piva INTEGER NOT NULL",
        "reddito_esterno REAL NOT NULL DEFAULT 0",
        "spese_dedotte_esterne REAL NOT NULL DEFAULT 0",
        "conto_corrente_id INTEGER",
        "provider_fatture TEXT NOT NULL",
        "username_provider TEXT",
        "password_provider TEXT",
        "password_login TEXT",  # Nuova colonna
        "status INTEGER NOT NULL DEFAULT 1",
        "acconto_irpef REAL NOT NULL DEFAULT 0",
        "acconto_inps REAL NOT NULL DEFAULT 0",
        "photo_path TEXT",
        "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "FOREIGN KEY (conto_corrente_id) REFERENCES accounts (id)"
    ]

    cursor.execute(f"CREATE TABLE users_temp ({', '.join(create_columns)})")

    # 2. Ottieni i nomi delle colonne dalla tabella originale
    cursor.execute("PRAGMA table_info(users)")
    original_columns = [col[1] for col in cursor.fetchall()]

    # 3. Costruisci la query di inserimento mappando per nome
    # Per ogni colonna nella tabella di destinazione, usa il valore dalla colonna con lo stesso nome nella tabella sorgente
    select_columns = []
    for col_name in correct_column_order:
        if col_name in original_columns:
            select_columns.append(col_name)
        else:
            # Per colonne nuove (come password_login) usa NULL
            select_columns.append("NULL")

    # 4. Copia i dati mappando per nome di colonna
    insert_query = f"""
        INSERT INTO users_temp ({', '.join(correct_column_order)})
        SELECT {', '.join(select_columns)}
        FROM users
    """

    cursor.execute(insert_query)

    # 5. Sostituisci la tabella originale
    cursor.execute("DROP TABLE users")
    cursor.execute("ALTER TABLE users_temp RENAME TO users")

    print("Tabella users ricostruita con l'ordine delle colonne corretto.")


def verify_table_structure(db_path: str):
    """
    Verifica la struttura della tabella users dopo l'operazione.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()

    print("\nStruttura finale della tabella users:")
    for col in columns:
        print(f"  {col[0]}: {col[1]} ({col[2]})")

    # Verifica che i dati siano corretti
    cursor.execute("""
        SELECT id, first_name, password_provider, password_login, 
               acconto_irpef, acconto_inps, photo_path 
        FROM users LIMIT 3
    """)
    sample_data = cursor.fetchall()

    print(f"\nDati di esempio (prime 3 righe):")
    for row in sample_data:
        print(f"  ID: {row[0]}, Nome: {row[1]}")
        print(f"    Password Provider: {row[2]}")
        print(f"    Password Login: {row[3]}")
        print(f"    Acconto IRPEF: {row[4]} (tipo: {type(row[4])})")
        print(f"    Acconto INPS: {row[5]} (tipo: {type(row[5])})")
        print(f"    Photo Path: {row[6]}")
        print()

    conn.close()


def create_backup(db_path: str):
    """
    Crea un backup del database prima di modificarlo.
    """
    backup_path = db_path + ".backup"
    import shutil
    shutil.copy2(db_path, backup_path)
    print(f"Backup creato: {backup_path}")


if __name__ == "__main__":
    # Nome della variabile d'ambiente
    PATH_ENV_VAR = "GESTIONALE_DB_PATH"

    # Ottieni il percorso base del database dalla variabile d'ambiente
    path = os.environ.get(PATH_ENV_VAR)
    if not path:
        raise EnvironmentError(f"La variabile d'ambiente {PATH_ENV_VAR} non è stata configurata.")

    # Percorso completo del file SQLite
    db_path = os.path.join(path, "gestionale.db")

    # Controllo di esistenza
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database non trovato in: {db_path}")

    print(f"Connessione al database: {db_path}")

    # Crea un backup prima di procedere
    create_backup(db_path)

    # Esegui l'aggiunta sicura della colonna
    safe_add_password_login_column(db_path)

    # Verifica la struttura finale
    verify_table_structure(db_path)

    print("\nOperazione completata con successo!")
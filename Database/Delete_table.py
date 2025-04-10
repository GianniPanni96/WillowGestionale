import sqlite3
from Model import db_path  # Assicurati che db_path sia definito in Model.py


def delete_all_rows(table_name):
    """
    Elimina tutte le righe dalla tabella specificata e azzera il contatore degli ID.

    :param table_name: Nome della tabella da svuotare.
    """
    try:
        # Connessione al database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Esecuzione del comando DELETE per eliminare tutte le righe
        cursor.execute(f"DELETE FROM {table_name}")

        # Resetta il contatore degli ID per la tabella (funziona se la tabella usa AUTOINCREMENT)
        cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table_name}'")

        # 4. Elimina la vecchia tabella
        cursor.execute(f"DROP TABLE {table_name};")

        conn.commit()
        print(
            f"Tutte le righe della tabella '{table_name}' sono state eliminate e il contatore degli ID è stato resettato.")
    except Exception as e:
        print(f"Errore durante l'eliminazione delle righe: {e}")
    finally:
        conn.close()

table_name = "expenses"
delete_all_rows(table_name)
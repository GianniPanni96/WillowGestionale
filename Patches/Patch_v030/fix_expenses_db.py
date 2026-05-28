import os
import sqlite3

def fix_expenses_table(db_path: str):
    """
    Ricalcola NET_AMOUNT e IVA_AMOUNT nella tabella 'expenses'
    a partire dai valori di TOT_AMOUNT e dall'aliquota IVA dedotta.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT ID, IMPORTO_NETTO, IMPORTO_LORDO, IMPORTO_IVA FROM expenses")
    rows = cursor.fetchall()

    updated_count = 0

    for row in rows:
        expense_id, old_net, tot, old_iva = row

        # Evita divisioni per zero o valori mancanti
        if old_net is None or old_net == 0 or tot is None:
            continue

        # Deduci aliquota IVA approssimativa
        a = old_iva / tot

        # Salta righe con aliquote non sensate
        if a < 0 or a > 1:
            continue

        # Ricalcola netto e IVA corretti
        new_net = tot / (a + 1)
        new_iva = tot - new_net

        # Aggiorna la riga
        cursor.execute("""
            UPDATE expenses
            SET IMPORTO_NETTO = ?, IMPORTO_IVA = ?
            WHERE ID = ?
        """, (new_net, new_iva, expense_id))

        updated_count += 1

    conn.commit()
    conn.close()

    print(f"Aggiornamento completato. Righe aggiornate: {updated_count}")


if __name__ == "__main__":
    import sys

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
    fix_expenses_table(db_path)

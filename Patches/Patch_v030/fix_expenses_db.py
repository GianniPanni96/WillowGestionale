import os
import sqlite3


VAT_RATES = (0.0, 0.04, 0.10, 0.22)
TOLERANCE = 0.01


def _is_close(left, right, tolerance=TOLERANCE):
    return abs(float(left or 0) - float(right or 0)) <= tolerance


def _nearest_known_vat_rate(rate):
    if rate is None or rate < 0 or rate > 1:
        return None
    nearest = min(VAT_RATES, key=lambda candidate: abs(candidate - rate))
    return nearest if abs(nearest - rate) <= 0.015 else None


def _recalculate_amounts(old_net, gross, old_iva):
    if gross is None or gross < 0:
        return None

    if _is_close((old_net or 0) + (old_iva or 0), gross):
        return None

    if old_iva is not None and gross > old_iva >= 0:
        rate = _nearest_known_vat_rate(old_iva / (gross - old_iva))
        if rate is not None:
            net = round(gross / (1 + rate), 2)
            iva = round(gross - net, 2)
            return net, iva

    if old_net is not None and old_net > 0:
        rate = _nearest_known_vat_rate((gross / old_net) - 1)
        if rate is not None:
            net = round(gross / (1 + rate), 2)
            iva = round(gross - net, 2)
            return net, iva

    return None


def fix_expenses_table(db_path: str):
    """
    Ricalcola NET_AMOUNT e IVA_AMOUNT nella tabella 'expenses'
    solo per le righe incoerenti dove netto + IVA non torna al lordo.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT ID, IMPORTO_NETTO, IMPORTO_LORDO, IMPORTO_IVA FROM expenses")
    rows = cursor.fetchall()

    updated_count = 0

    for row in rows:
        expense_id, old_net, tot, old_iva = row
        recalculated = _recalculate_amounts(old_net, tot, old_iva)
        if recalculated is None:
            continue

        new_net, new_iva = recalculated
        if _is_close(old_net, new_net) and _is_close(old_iva, new_iva):
            continue

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
        raise EnvironmentError(f"La variabile d'ambiente {PATH_ENV_VAR} non e' stata configurata.")

    # Percorso completo del file SQLite
    db_path = os.path.join(path, "gestionale.db")

    # Controllo di esistenza
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database non trovato in: {db_path}")

    print(f"Connessione al database: {db_path}")
    fix_expenses_table(db_path)

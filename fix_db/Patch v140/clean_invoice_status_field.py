"""Patch v1.4.0 - pulizia del campo ``invoices.status``.

CONTESTO
--------
A partire da v1.4.0 il campo ``status`` della tabella ``invoices`` non viene
piu' usato per persistere stati derivabili (EMESSA / SALDATA / SCADUTA /
PAGATA / PARZIALMENTE_SALDATA / CRITICA). Lo stato di una fattura e' calcolato
on-the-fly da pagamenti+scadenze tramite ``Utils.Invoice_status_utils.
compute_invoice_status``.

Il campo ``status`` resta nel DB per persistere SOLO l'eccezione manuale
``STORNATA`` (decisione utente, non derivabile dai dati). Questo script
azzera (stringa vuota) il valore di ``status`` per tutte le fatture il cui
valore non e' ``STORNATA``, in modo da evitare letture spurie da codice
legacy o eventuali strumenti esterni che dovessero ispezionare il campo.

COSA FA LO SCRIPT
-----------------
1. Backup di sicurezza del file DB (copia con timestamp).
2. ``UPDATE invoices SET status = '' WHERE status <> 'STORNATA'``.
3. Stampa un riepilogo: numero di righe toccate e numero di STORNATA preservate.

L'operazione e' idempotente: rilanciare lo script non causa danni.

ESECUZIONE (dalla macchina del cliente)
---------------------------------------
    python "fix_db/Patch v140/clean_invoice_status_field.py"

Usa gli stessi percorsi runtime dell'applicazione (``get_runtime_paths``):
non serve configurare nulla se il gestionale gira gia' su quella macchina.
"""

import os
import shutil
import sqlite3
import sys
from datetime import datetime

# --- Rende importabili i moduli dell'app anche da fix_db/Patch v140/ ---
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from Gestionale_Enums import DBInvoicesColumns, InvoiceSatus
from Utils.App_paths import get_runtime_paths


STORNATA_VALUE = InvoiceSatus.STORNATA.value


def backup_db(db_path: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.bak_{stamp}"
    shutil.copy2(db_path, backup_path)
    return backup_path


def clean_status_field(db_path: str) -> tuple[int, int]:
    """Esegue l'UPDATE. Ritorna (righe_aggiornate, stornate_preservate)."""
    status_col = DBInvoicesColumns.STATUS.value
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()

        # Conteggio diagnostico.
        cur.execute(
            f"SELECT COUNT(*) FROM invoices WHERE {status_col} = ?",
            (STORNATA_VALUE,),
        )
        stornate_count = cur.fetchone()[0]

        cur.execute(
            f"SELECT COUNT(*) FROM invoices "
            f"WHERE {status_col} IS NOT NULL AND {status_col} <> '' AND {status_col} <> ?",
            (STORNATA_VALUE,),
        )
        to_clean = cur.fetchone()[0]

        # UPDATE: azzera tutto cio' che non e' STORNATA (e non e' gia' vuoto).
        cur.execute(
            f"UPDATE invoices SET {status_col} = '' "
            f"WHERE {status_col} IS NOT NULL AND {status_col} <> '' AND {status_col} <> ?",
            (STORNATA_VALUE,),
        )
        conn.commit()
        return to_clean, stornate_count
    finally:
        conn.close()


def main() -> int:
    print("== Patch v1.4.0 - pulizia campo invoices.status ==\n")

    runtime_paths = get_runtime_paths()
    db_path = str(runtime_paths.db_file)
    if not os.path.exists(db_path):
        print(f"[!] Database non trovato: {db_path}")
        return 1

    print(f"Database: {db_path}")
    backup_path = backup_db(db_path)
    print(f"Backup creato: {backup_path}")

    try:
        cleaned, preserved = clean_status_field(db_path)
    except Exception as exc:
        print(f"[!] Errore durante l'UPDATE: {exc}")
        print(f"    Il DB e' invariato. Il backup resta disponibile in: {backup_path}")
        return 1

    print()
    print(f"Righe aggiornate (status azzerato):  {cleaned}")
    print(f"Fatture STORNATE preservate:         {preserved}")
    print()
    print("Operazione completata. Lo stato delle fatture viene ora calcolato")
    print("on-the-fly da pagamenti+scadenze; il campo invoices.status resta")
    print("popolato solo per le fatture STORNATE (eccezione manuale).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

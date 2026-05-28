"""
Fix dei libri contabili 2025 - tabella ``taxes_aggregated_data.csv``.

CONTESTO
--------
L'anno contabile 2025 e' gia' stato chiuso (books emessi) usando la vecchia
logica di calcolo tasse. Dopo le correzioni fiscali (base imponibile al netto
IVA, aliquota forfettaria agevolata, deduzione INPS, massimale, ripartizione
collettivo proporzionale, ecc.) i valori vanno rigenerati.

In piu', per i libri 2025 si adotta il principio di CASSA PURO basato sulla data
di incasso (``PAYMENT_DATE``, NON ``created_at``):
- fatture emesse nel 2025 e saldate entro il 31/12/2025 → incluse;
- fatture emesse nel 2025 ma non saldate entro fine anno → escluse;
- fatture emesse in anni precedenti, saldate entro il 31/12/2025 e con almeno
  un pagamento incassato nel 2025 → incluse (il flusso di cassa cade nel 2025).

COSA FA LO SCRIPT
-----------------
1. Istanzia i servizi minimi (DB + settings) senza avviare la GUI/scheduler.
2. Ricalcola la previsione tasse 2025 riusando ESATTAMENTE la matematica
   corretta dell'app (``UserAnalyzerService``), ma con una sottoclasse che
   seleziona le fatture in base alla data di saldo <= 31/12/2025.
3. Fa un backup del CSV esistente.
4. Riscrive le sole righe dell'anno 2025 in ``taxes_aggregated_data.csv``
   (le altre annualita' restano intatte).
5. Genera un report di testo con il confronto PRIMA/DOPO di tutti i valori,
   utile se sono gia' stati calcolati/emessi rimborsi sui vecchi dati.

ESECUZIONE (dalla macchina del cliente)
---------------------------------------
    python fix_db/fix_taxes_books_2025.py

Usa gli stessi percorsi runtime dell'applicazione (get_runtime_paths): non
serve configurare nulla se il gestionale gira gia' su quella macchina.
"""

import csv
import os
import shutil
import sys
from datetime import datetime

# --- Rende importabili i moduli dell'app anche lanciando lo script da fix_db/ ---
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from AnalyzerServices.User_analyzer_service import UserAnalyzerService
from ConfigManagers import ConfigManager, FiscalSettings
from Gestionale_Enums import (
    DBInvoicesColumns,
    DBPaymentsColumns,
    DBUsersColumns,
    RegimeFiscale,
)
from Model import DatabaseModel
from QueryServices.Users_query_service import UserQueryService
from Utils.App_paths import get_runtime_paths
from Utils.Controller_utils import ControllerUtils
from Utils.Validation_utils import ValidationUtils

# ---------------------------------------------------------------------------
# Parametri della fix
# ---------------------------------------------------------------------------
ANNO_FIX = 2025
DATA_CUTOFF = datetime(2025, 12, 31, 23, 59, 59)  # saldo entro fine anno contabile

# Colonne del CSV taxes_aggregated_data.csv (come scritte da BookCloser.export_tax_data)
CSV_FIELDNAMES = [
    "anno",
    "user_id",
    "nome_utente",
    "tipo_riga",
    "saldo_willow",
    "acconto_willow",
    "irpef_willow",
    "inps_willow",
    "inps_totale",
    "irpef_totale",
    "data_esportazione",
]

# Campi numerici di cui mostrare la variazione nel report
DIFF_FIELDS = [
    ("saldo_willow", "Saldo collettivo"),
    ("acconto_willow", "Acconto collettivo"),
    ("irpef_willow", "IRPEF collettivo"),
    ("inps_willow", "INPS collettivo"),
    ("irpef_totale", "IRPEF totale (propria)"),
    ("inps_totale", "INPS totale (propria)"),
]


class CassaCutoffUserAnalyzer(UserAnalyzerService):
    """``UserAnalyzerService`` con selezione delle fatture per data di saldo (cassa pura).

    Sovrascrive solo le funzioni che leggono la base imponibile/ritenuta dalle
    fatture. Applica il principio di cassa puro:
    - fatture emesse nell'anno e saldate entro cutoff;
    - fatture emesse in anni precedenti, saldate entro cutoff, con almeno un
      pagamento (PAYMENT_DATE) caduto nell'anno target.
    Tutta la matematica fiscale a valle resta quella (corretta) della classe base.
    """

    def __init__(self, user_query_service, db_model, fiscal_settings, cutoff: datetime):
        super().__init__(user_query_service, db_model, fiscal_settings)
        self.cutoff = cutoff
        self._payments_by_invoice_cache = None

    def _payments_by_invoice(self):
        if self._payments_by_invoice_cache is None:
            mapping: dict = {}
            for row in self.db_model.fetch_payments():
                p = ValidationUtils._row_to_map(row, DBPaymentsColumns)
                if not p:
                    continue
                inv_id = p.get(DBPaymentsColumns.INVOICE_ID.value)
                mapping.setdefault(inv_id, []).append(p)
            self._payments_by_invoice_cache = mapping
        return self._payments_by_invoice_cache

    @staticmethod
    def _issued_year(invoice):
        date_str = invoice.get(DBInvoicesColumns.DATA_CREAZIONE.value)
        dt = ControllerUtils._parse_date(date_str) if date_str else None
        return dt.year if dt else None

    def _is_settled_by_cutoff(self, invoice) -> bool:
        """Vero se tutte le rate risultano pagate entro il cutoff."""
        try:
            num_rate = int(invoice.get(DBInvoicesColumns.NUMERO_RATE.value) or 1)
        except (TypeError, ValueError):
            num_rate = 1

        payments = self._payments_by_invoice().get(invoice.get(DBInvoicesColumns.ID.value), [])
        paid_rate = set()
        for p in payments:
            d = ControllerUtils._parse_date(p.get(DBPaymentsColumns.PAYMENT_DATE.value) or "")
            if d is not None and d <= self.cutoff:
                # LINKED_RATA puo' essere None: in tal caso conta come rata singola.
                paid_rate.add(p.get(DBPaymentsColumns.LINKED_RATA.value) or 1)
        return len(paid_rate) >= num_rate

    def _had_payment_in_year(self, invoice, year: int) -> bool:
        """Vero se almeno un pagamento della fattura ha PAYMENT_DATE nell'anno ``year``."""
        payments = self._payments_by_invoice().get(invoice.get(DBInvoicesColumns.ID.value), [])
        for p in payments:
            d = ControllerUtils._parse_date(p.get(DBPaymentsColumns.PAYMENT_DATE.value) or "")
            if d is not None and d.year == year:
                return True
        return False

    def _settled_invoices(self, user_id, year):
        """Fatture conteggiate per cassa nell'anno ``year``.

        Include:
        - fatture EMESSE in ``year`` e saldate entro il cutoff;
        - fatture emesse in anni PRECEDENTI, saldate entro il cutoff,
          con almeno un pagamento incassato nell'anno ``year``
          (principio di cassa puro: il flusso di cassa cade nell'anno).
        """
        target_year = year if (year not in (None, -1)) else datetime.now().year
        all_invoices = self.user_query_service.retrieve_user_with_invoices_map_list(
            user_id, include_unpaid_invoices=True, year=-1,
        ) or []
        result = []
        for inv in all_invoices:
            issued = self._issued_year(inv)
            if issued == target_year:
                # Emessa nell'anno: includi solo se saldata entro cutoff.
                if self._is_settled_by_cutoff(inv):
                    result.append(inv)
            elif issued is not None and issued < target_year:
                # Emessa in anni precedenti: includi se saldata entro cutoff
                # E con almeno un incasso nell'anno target.
                if self._is_settled_by_cutoff(inv) and self._had_payment_in_year(inv, target_year):
                    result.append(inv)
        return result

    # --- override delle basi imponibili (per cassa al cutoff) ---------------

    def calcola_tot_imponibile_utente(self, user_id, include_unpaid_invoices: bool = False, year: int = None):
        return sum(
            float(inv.get(DBInvoicesColumns.IMPONIBILE.value) or 0.0)
            for inv in self._settled_invoices(user_id, year)
        )

    def calcola_tot_fatturato_utente(self, user_id, include_unpaid_invoices: bool = True, year: int = None):
        return sum(
            float(inv.get(DBInvoicesColumns.TOT_DOCUMENTO.value) or 0.0)
            for inv in self._settled_invoices(user_id, year)
        )

    def calcola_tot_ritenuta_acconto_ordinaria(self, user_id, year: int = None):
        settled = ControllerUtils.clear_invoices_list_from_NDC_and_stornate(
            self._settled_invoices(user_id, year)
        )
        tot = 0.0
        for inv in settled:
            if inv.get(DBInvoicesColumns.ID_CLIENTE.value):
                tot += float(inv.get(DBInvoicesColumns.RITENUTA.value) or 0.0)
        return tot


# ---------------------------------------------------------------------------
# Costruzione servizi minimi
# ---------------------------------------------------------------------------

def build_analyzer():
    runtime_paths = get_runtime_paths()
    db_path = str(runtime_paths.db_file)
    books_dir = str(runtime_paths.books_dir)

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database non trovato in: {db_path}")

    config = ConfigManager().load_config()
    fiscal_settings = FiscalSettings.from_dict(config.get("fiscal_settings", {}))

    db_model = DatabaseModel(db_path)
    user_query_service = UserQueryService(db_model, fiscal_settings)
    analyzer = CassaCutoffUserAnalyzer(user_query_service, db_model, fiscal_settings, DATA_CUTOFF)
    return analyzer, user_query_service, books_dir


# ---------------------------------------------------------------------------
# Calcolo nuove righe (stessa struttura di BookCloser.export_tax_data)
# ---------------------------------------------------------------------------

_DEBUG_ORDINARIO_KEYS = [
    ("FATTURATO_WILLOW",      "  Fatturato willow (imponibile)"),
    ("REDDITO_ESTERNO",       "  Reddito esterno"),
    ("RICAVI_TOTALI",         "  Ricavi totali"),
    ("SPESE_WILLOW",          "  Spese willow dedotte"),
    ("SPESE_ESTERNE",         "  Spese esterne dedotte"),
    ("SPESE_TOTALI",          "  Spese totali"),
    ("REDDITO_NETTO",         "  Reddito netto completo"),
    ("MASSIMALE_INPS",        "  Massimale INPS"),
    ("INPS",                  "  INPS dovuta"),
    ("BASE_IRPEF",            "  Base IRPEF"),
    ("IRPEF_LORDA",           "  IRPEF lorda"),
    ("RITENUTA",              "  Ritenuta d'acconto"),
    ("IRPEF_NETTA",           "  IRPEF netta (neg.=credito)"),
    ("QUOTA_WILLOW_BASE",     "  Quota reddito willow"),
    ("WILLOW_INPS",           "  INPS willow (proporzionale)"),
    ("WILLOW_IRPEF_TOT",      "  IRPEF willow (lorda, proporzionale)"),
    ("SALDO_WILLOW",          "  Saldo willow"),
    ("ACCONTO_WILLOW",        "  Acconto willow"),
]

_DEBUG_FORFETTARIO_KEYS = [
    ("FATTURATO_WILLOW",        "  Fatturato willow (imponibile)"),
    ("REDDITO_ESTERNO",         "  Reddito esterno lordo"),
    ("COEFFICIENTE_IMPONIBILE", "  Coefficiente imponibile"),
    ("REDDITO_TOT",             "  Reddito totale (dopo coefficiente)"),
    ("MASSIMALE_INPS",          "  Massimale INPS"),
    ("INPS",                    "  INPS dovuta"),
    ("BASE_IMPONIBILE_IRPEF",   "  Base imponibile IRPEF (dopo INPS)"),
    ("ALIQUOTA_IRPEF",          "  Aliquota IRPEF"),
    ("IRPEF",                   "  Imposta sostitutiva"),
    ("INPS WILLOW",             "  INPS willow"),
    ("IRPEF WILLOW",            "  IRPEF willow"),
    ("SALDO_WILLOW",            "  Saldo willow"),
    ("ACCONTO_WILLOW",          "  Acconto willow"),
]


def _print_debug_user(user_name, regime, output_map, n_invoices):
    print(f"\n  --- DEBUG: {user_name} ({regime}) ---")
    print(f"  Fatture conteggiate (per cassa cutoff): {n_invoices}")
    keys = _DEBUG_ORDINARIO_KEYS if regime == RegimeFiscale.ORDINARIO.value else _DEBUG_FORFETTARIO_KEYS
    for key, label in keys:
        val = output_map.get(key, "n/d")
        if isinstance(val, float):
            print(f"  {label:<40} {val:>12,.2f}")
        else:
            print(f"  {label:<40} {val!r:>12}")


def compute_new_rows(analyzer: CassaCutoffUserAnalyzer, user_query_service: UserQueryService,
                     debug: bool = False):
    tax_data = analyzer.calculate_previsione_tasse_willow(year=ANNO_FIX)
    export_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows = []
    total_inps = 0.0
    total_irpef = 0.0

    for user_name, values in tax_data.items():
        if user_name == "TOTALE":
            continue

        try:
            user_map = user_query_service.retrieve_user_map_by_extended_name(user_name)
            user_id = user_map.get(DBUsersColumns.ID.value) if user_map else None
        except Exception:
            user_id = None

        inps_totale = 0.0
        irpef_totale = 0.0
        output_map_debug = {}
        try:
            regime = user_map.get(DBUsersColumns.REGIME_FISCALE.value) if user_map else None
            if regime == RegimeFiscale.FORFETTARIO.value:
                tasse_map, _, output_map_debug = analyzer.calculate_previsione_tasse_forfettaria(user_id, year=ANNO_FIX)
                inps_totale = tasse_map.get("INPS", 0.0)
                irpef_totale = tasse_map.get("IRPEF", 0.0)
            elif regime == RegimeFiscale.ORDINARIO.value:
                tasse_map, _, output_map_debug = analyzer.calculate_previsione_tasse_ordinaria(user_id, year=ANNO_FIX)
                inps_totale = tasse_map.get("INPS", 0.0)
                irpef_totale = tasse_map.get("IRPEF NETTA", 0.0)
        except Exception as exc:
            print(f"  [!] Errore calcolo tasse base per '{user_name}': {exc}")
            import traceback; traceback.print_exc()

        if debug:
            regime_str = (user_map.get(DBUsersColumns.REGIME_FISCALE.value) or "?") if user_map else "?"
            n_inv = len(analyzer._settled_invoices(user_id, ANNO_FIX)) if user_id else 0
            _print_debug_user(user_name, regime_str, output_map_debug, n_inv)

        rows.append({
            "anno": ANNO_FIX,
            "user_id": user_id,
            "nome_utente": user_name,
            "tipo_riga": "UTENTE",
            "saldo_willow": round(values.get("SALDO WILLOW", 0.0), 2),
            "acconto_willow": round(values.get("ACCONTO WILLOW", 0.0), 2),
            "irpef_willow": round(values.get("IRPEF WILLOW", 0.0), 2),
            "inps_willow": round(values.get("INPS WILLOW", 0.0), 2),
            "inps_totale": round(inps_totale, 2),
            "irpef_totale": round(irpef_totale, 2),
            "data_esportazione": export_timestamp,
        })
        total_inps += inps_totale
        total_irpef += irpef_totale

    totale_vals = tax_data.get("TOTALE", {})
    rows.append({
        "anno": ANNO_FIX,
        "user_id": None,
        "nome_utente": "TOTALE",
        "tipo_riga": "TOTALE",
        "saldo_willow": round(totale_vals.get("SALDO WILLOW", 0.0), 2),
        "acconto_willow": round(totale_vals.get("ACCONTO WILLOW", 0.0), 2),
        "irpef_willow": round(totale_vals.get("IRPEF WILLOW", 0.0), 2),
        "inps_willow": round(totale_vals.get("INPS WILLOW", 0.0), 2),
        "inps_totale": round(total_inps, 2),
        "irpef_totale": round(total_irpef, 2),
        "data_esportazione": export_timestamp,
    })
    return rows


# ---------------------------------------------------------------------------
# Lettura righe esistenti (PRIMA)
# ---------------------------------------------------------------------------

def read_existing_rows(csv_path):
    if not os.path.isfile(csv_path):
        return [], []
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        all_rows = list(reader)
        fieldnames = reader.fieldnames or []
    return all_rows, fieldnames


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# Scrittura CSV (replace-by-year) con backup
# ---------------------------------------------------------------------------

def write_updated_csv(csv_path, existing_rows, existing_fieldnames, new_rows):
    # Backup di sicurezza.
    if os.path.isfile(csv_path):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{csv_path}.bak_{stamp}"
        shutil.copy2(csv_path, backup_path)
        print(f"Backup del CSV creato: {backup_path}")
    else:
        backup_path = None

    # Rimuove le righe dell'anno target e accoda quelle nuove.
    kept = [r for r in existing_rows if str(r.get("anno")) != str(ANNO_FIX)]
    kept.extend(new_rows)

    # Ordina per anno, UTENTE prima del TOTALE, poi per nome.
    kept.sort(key=lambda r: (
        int(r.get("anno", 0) or 0),
        1 if r.get("tipo_riga") == "TOTALE" else 0,
        str(r.get("nome_utente", "")),
    ))

    fieldnames = existing_fieldnames if existing_fieldnames else CSV_FIELDNAMES
    # Aggiunge eventuali colonne nuove non presenti nell'header originale.
    for r in kept:
        for k in r.keys():
            if k not in fieldnames:
                fieldnames.append(k)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(kept)

    print(f"CSV aggiornato: {csv_path}")
    return backup_path


# ---------------------------------------------------------------------------
# Report variazioni PRIMA/DOPO
# ---------------------------------------------------------------------------

def build_report(old_rows, new_rows, books_dir, backup_path):
    old_by_name = {
        r.get("nome_utente"): r
        for r in old_rows
        if str(r.get("anno")) == str(ANNO_FIX)
    }
    new_by_name = {r.get("nome_utente"): r for r in new_rows}

    lines = []
    lines.append("=" * 78)
    lines.append(f" REPORT FIX TASSE - ANNO CONTABILE {ANNO_FIX}")
    lines.append(f" Generato il: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 78)
    lines.append("")
    lines.append("Criterio applicato (cassa pura):")
    lines.append(f"  - fatture emesse nel {ANNO_FIX} e saldate entro 31/12/{ANNO_FIX};")
    lines.append(f"  - fatture emesse prima del {ANNO_FIX}, saldate entro 31/12/{ANNO_FIX}")
    lines.append(f"    con almeno un pagamento incassato nel {ANNO_FIX}.")
    lines.append("I valori riflettono le correzioni di calcolo fiscale (base imponibile")
    lines.append("al netto IVA/rivalsa/rimborsi, aliquota forfettaria corretta, ecc.).")
    lines.append("")
    lines.append("NOTA: un valore negativo in 'IRPEF totale' indica un CREDITO di")
    lines.append("ritenuta d'acconto (ritenuta subita > IRPEF dovuta). Non e' un debito.")
    lines.append("Un INPS/IRPEF willow a zero puo' indicare reddito netto negativo o")
    lines.append("nullo dopo la correzione della base imponibile (IVA esclusa).")
    if backup_path:
        lines.append(f"Backup del CSV precedente: {os.path.basename(backup_path)}")
    lines.append("")
    lines.append("ATTENZIONE: se sono gia' stati calcolati o erogati rimborsi dai")
    lines.append("conti del collettivo sulla base dei valori PRECEDENTI, confrontare")
    lines.append("le differenze qui sotto per gli eventuali conguagli.")
    lines.append("")

    all_names = list(new_by_name.keys())
    # Mette TOTALE in fondo.
    all_names.sort(key=lambda n: (1 if n == "TOTALE" else 0, n))

    for name in all_names:
        new_r = new_by_name.get(name, {})
        old_r = old_by_name.get(name)
        lines.append("-" * 78)
        lines.append(f"UTENTE: {name}" + ("   [NUOVO - assente nei dati precedenti]" if old_r is None else ""))
        lines.append("-" * 78)
        header = f"  {'Voce':<28}{'PRIMA':>14}{'DOPO':>14}{'VARIAZIONE':>16}"
        lines.append(header)
        for key, label in DIFF_FIELDS:
            new_v = _to_float(new_r.get(key))
            old_v = _to_float(old_r.get(key)) if old_r else 0.0
            delta = new_v - old_v
            if old_r is None:
                prima_str = "n/d"
            else:
                prima_str = f"{old_v:,.2f}"
            lines.append(
                f"  {label:<28}{prima_str:>14}{new_v:>14,.2f}{delta:>+16,.2f}"
            )
        lines.append("")

    # Utenti presenti prima ma non piu' nel nuovo calcolo (es. azzerati).
    removed = [n for n in old_by_name.keys() if n not in new_by_name]
    if removed:
        lines.append("-" * 78)
        lines.append("UTENTI presenti nei dati precedenti ma non nel nuovo calcolo:")
        for n in removed:
            lines.append(f"  - {n}")
        lines.append("")

    lines.append("=" * 78)
    lines.append("Fine report.")

    report_text = "\n".join(lines)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(books_dir, f"fix_taxes_{ANNO_FIX}_report_{stamp}.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    return report_path, report_text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    debug = "--debug" in sys.argv
    print(f"== Fix libri tasse anno {ANNO_FIX} (cutoff saldo {DATA_CUTOFF.date()}) ==")
    if debug:
        print("   [modalita' DEBUG attiva: verranno stampati i valori intermedi per ogni utente]")
    print()

    analyzer, user_query_service, books_dir = build_analyzer()
    csv_path = os.path.join(books_dir, "taxes_aggregated_data.csv")

    if not os.path.isfile(csv_path):
        print(f"[!] File non trovato: {csv_path}")
        print("    Nessun libro tasse da correggere. Interrotto.")
        return 1

    print("Lettura dati esistenti...")
    existing_rows, existing_fieldnames = read_existing_rows(csv_path)

    print("Ricalcolo previsione tasse 2025 (per cassa al 31/12/2025 + logica corretta)...")
    new_rows = compute_new_rows(analyzer, user_query_service, debug=debug)

    print("Generazione report variazioni...")
    report_path, report_text = build_report(existing_rows, new_rows, books_dir, backup_path=None)

    print("Scrittura CSV aggiornato (con backup)...")
    backup_path = write_updated_csv(csv_path, existing_rows, existing_fieldnames, new_rows)

    # Rigenera il report includendo il riferimento al backup appena creato.
    report_path, report_text = build_report(existing_rows, new_rows, books_dir, backup_path)

    print("\n" + report_text)
    print(f"\nReport salvato in: {report_path}")
    print("\nOperazione completata.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

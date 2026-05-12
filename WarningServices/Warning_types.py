"""
Tipi condivisi del sistema warnings.

Tre livelli di severity (in ordine decrescente di gravita'):
- ``CONSISTENCY`` (1, rosso): rottura di chiave esterna — l'item referenziato
  non esiste piu' nel database. Non disabilitabile dall'utente: rimane visibile
  finche' non viene risolto agendo sul dettaglio.
- ``INCONSISTENCY`` (2, arancione): dato incoerente — es. somma pagamenti !=
  netto a pagare, sforamento preventivo, importo netto+iva != lordo.
- ``INFO`` (3, giallo): warning di retrieving, informativo. Spiega perche'
  un item di un anno contabile passato e' ancora visualizzato.

Ogni ``WarningInfo`` espone:
- ``type_key``: chiave breve usata sia dalla GUI di configurazione (per
  abilitare/disabilitare il warning) sia per identificarne il "tipo" in
  modo stabile in eventuali log.
- ``severity``: il livello sopra descritto.
- ``text``: testo presentato all'utente.
- ``broken_field_key``: opzionale, valorizzato per i sev 1, e' la chiave
  del widget nel detail view che corrisponde alla FK rotta — usata per
  evidenziare in rosso quel widget.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class WarningSeverity(IntEnum):
    CONSISTENCY = 1
    INCONSISTENCY = 2
    INFO = 3


# Colore associato a ogni severity. Coerente con la scala
# "rosso / arancione / giallo" richiesta.
SEVERITY_COLORS = {
    WarningSeverity.CONSISTENCY: "#d62929",   # rosso
    WarningSeverity.INCONSISTENCY: "#e07b00", # arancione
    WarningSeverity.INFO: "#e6c719",          # giallo
}


def color_for_severity(severity: "WarningSeverity | int | None") -> str:
    """Restituisce il colore esadecimale per la severity passata. Per
    severity sconosciute / None usa il giallo della INFO come fallback
    morbido."""
    try:
        sev = WarningSeverity(int(severity))
    except (TypeError, ValueError):
        sev = WarningSeverity.INFO
    return SEVERITY_COLORS.get(sev, SEVERITY_COLORS[WarningSeverity.INFO])


@dataclass(frozen=True)
class WarningInfo:
    """Descrittore di un singolo warning prodotto da un warning service.

    I service restituiscono ``dict[item_key, WarningInfo]``.
    """

    type_key: str
    severity: WarningSeverity
    text: str
    broken_field_key: str | None = None

    @property
    def color(self) -> str:
        return color_for_severity(self.severity)


# Domini esposti nella config + GUI. Usati come chiavi top-level del file
# JSON e come etichette nella dialog di settings. Il primo elemento e' la
# chiave interna; il secondo l'etichetta utente.
WARNING_DOMAINS = (
    ("fatture", "FATTURE"),
    ("pagamenti", "PAGAMENTI"),
    ("produzioni", "PRODUZIONI"),
    ("spese", "SPESE"),
    ("rimborsi", "RIMBORSI"),
    ("salari", "SALARI"),
)


# Catalogo dei type_key per dominio: severity + etichetta utente +
# descrizione breve. Usato dalla GUI di configurazione per costruire la
# vista gerarchica. ``locked = True`` significa "non disabilitabile"
# (regola: tutti i sev 1 sono locked).
WARNING_CATALOG = {
    "fatture": [
        ("client_missing",        WarningSeverity.CONSISTENCY,   "Cliente mancante",
         "Il cliente associato alla fattura non esiste più nel database."),
        ("invoicer_missing",      WarningSeverity.CONSISTENCY,   "Utente emittente mancante",
         "L'utente emittente della fattura non esiste più nel database."),
        ("account_missing",       WarningSeverity.CONSISTENCY,   "Conto mancante",
         "Il conto associato alla fattura non esiste più nel database."),
        ("production_missing",    WarningSeverity.CONSISTENCY,   "Produzione mancante",
         "La produzione associata alla fattura non esiste più nel database."),
        ("linked_invoice_missing", WarningSeverity.CONSISTENCY,  "Fattura associata mancante",
         "La fattura collegata (per nota di credito o simili) non esiste più."),
        ("payment_total_mismatch", WarningSeverity.INCONSISTENCY, "Somma pagamenti != netto",
         "La somma dei pagamenti collegati differisce dal netto a pagare."),
        ("previous_year",         WarningSeverity.INFO,          "Anno contabile precedente",
         "Fattura di un anno contabile passato, ancora visibile perché non saldata."),
    ],
    "pagamenti": [
        ("linked_invoice_missing", WarningSeverity.CONSISTENCY,  "Fattura collegata mancante",
         "La fattura collegata al pagamento non esiste più nel database."),
        ("account_missing",        WarningSeverity.CONSISTENCY,  "Conto mancante",
         "Il conto associato al pagamento non esiste più nel database."),
        ("linked_invoice_stornata", WarningSeverity.INCONSISTENCY, "Fattura stornata",
         "La fattura collegata è stata stornata: dato incoerente."),
        ("linked_invoice_modified_after", WarningSeverity.INCONSISTENCY, "Fattura modificata dopo il pagamento",
         "La fattura collegata è stata modificata dopo il pagamento: verifica consistenza."),
        ("rata_overpayment",      WarningSeverity.INCONSISTENCY, "Overpayment rata",
         "La somma dei pagamenti sulla rata supera la quota teorica."),
        ("previous_year",         WarningSeverity.INFO,          "Anno contabile precedente",
         "Pagamento collegato a una fattura di un anno contabile passato."),
    ],
    "produzioni": [
        ("client_missing",        WarningSeverity.CONSISTENCY,   "Cliente mancante",
         "Il cliente associato alla produzione non esiste più nel database."),
        ("preventivo_overrun",    WarningSeverity.INCONSISTENCY, "Sforamento preventivo",
         "La somma servizi+rimborsi delle fatture supera il totale preventivo."),
        ("closed_without_invoices", WarningSeverity.INCONSISTENCY, "CLOSED senza fatture",
         "La produzione è in stato CLOSED ma non ha alcuna fattura collegata."),
        ("previous_year",         WarningSeverity.INFO,          "Anno contabile precedente",
         "Produzione di un anno contabile passato, visibile perché collegata a fatture non saldate."),
    ],
    "spese": [
        ("supplier_missing",      WarningSeverity.CONSISTENCY,   "Fornitore mancante",
         "Il fornitore associato alla spesa non esiste più nel database."),
        ("account_missing",       WarningSeverity.CONSISTENCY,   "Conto mancante",
         "Il conto associato alla spesa non esiste più nel database."),
        ("user_deduzione_missing", WarningSeverity.CONSISTENCY,  "Utente deduzione mancante",
         "L'utente di deduzione indicato non esiste più nel database."),
        ("user_anticipo_missing", WarningSeverity.CONSISTENCY,   "Utente anticipo mancante",
         "L'utente che ha anticipato la spesa non esiste più nel database."),
        ("linked_invoice_missing", WarningSeverity.CONSISTENCY,  "Fattura collegata mancante",
         "La fattura collegata alla spesa di produzione non esiste più."),
        ("production_without_invoice", WarningSeverity.INCONSISTENCY, "Spesa di produzione senza fattura",
         "Categoria 'Spesa di produzione' ma nessuna fattura collegata."),
        ("amount_mismatch",       WarningSeverity.INCONSISTENCY, "Netto + IVA != Lordo",
         "Importo netto + IVA non corrisponde all'importo lordo."),
        ("deducibile_without_user", WarningSeverity.INCONSISTENCY, "Deducibile senza utente",
         "Spesa deducibile senza utente di deduzione indicato."),
    ],
    "rimborsi": [
        ("client_missing",        WarningSeverity.CONSISTENCY,   "Cliente mancante",
         "Il cliente associato al rimborso non esiste più nel database."),
        ("account_missing",       WarningSeverity.CONSISTENCY,   "Conto mancante",
         "Il conto associato al rimborso non esiste più nel database."),
    ],
    "salari": [
        ("user_missing",          WarningSeverity.CONSISTENCY,   "Utente mancante",
         "L'utente associato allo stipendio non esiste più nel database."),
        ("account_missing",       WarningSeverity.CONSISTENCY,   "Conto mancante",
         "Il conto associato allo stipendio non esiste più nel database."),
        ("monthly_duplicate",     WarningSeverity.INCONSISTENCY, "Doppione mensile",
         "Due o più stipendi per lo stesso utente nello stesso mese."),
    ],
}

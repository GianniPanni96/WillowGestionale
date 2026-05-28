"""Calcolo on-the-fly dello stato di una fattura.

A partire da v1.4.0 il campo ``DBInvoicesColumns.STATUS`` nel DB e' usato
ESCLUSIVAMENTE per persistere l'eccezione manuale ``STORNATA`` (decisione
dell'utente, non derivabile dai dati). Tutti gli altri stati
(EMESSA / SALDATA / SCADUTA / PAGATA / PARZIALMENTE_SALDATA / CRITICA)
sono ora derivati on-the-fly da pagamenti + scadenze tramite
``compute_invoice_status``, eliminando il rischio di desincronia fra
campo persistito e dati reali (cancellazioni di pagamenti, scadenze che
maturano col tempo, import/fix da script).

L'unico writer rimasto sul campo STATUS e' la funzione di storno
(``InvoiceController.storna_invoice`` / ``modify_invoice_datum`` sulla
linked invoice). Per leggere lo stato, usare ``compute_invoice_status``
o gli helper di questo modulo.
"""

from datetime import date

from Gestionale_Enums import (
    DBInvoicesColumns,
    DBPaymentsColumns,
    InvoiceRateizzSatus,
    InvoiceSatus,
    Rateizzazione,
)
from Utils.Controller_utils import ControllerUtils


def is_invoice_stornata(invoice) -> bool:
    """STORNATA e' l'unica eccezione manuale persistita nel campo STATUS."""
    if not invoice:
        return False
    return (invoice.get(DBInvoicesColumns.STATUS.value) or "") == InvoiceSatus.STORNATA.value


def compute_invoice_status(invoice, payments, today: date = None) -> str:
    """Calcola lo stato corrente della fattura a partire da pagamenti+scadenze.

    Args:
        invoice: dict con i campi di ``DBInvoicesColumns``.
        payments: lista di dict con i campi di ``DBPaymentsColumns`` (puo'
            essere vuota o None). Ogni pagamento deve avere ``LINKED_RATA``.
        today: data di riferimento per il confronto con le scadenze.
            Default: ``date.today()``. Parametro presente per testabilita'.

    Returns:
        Uno dei valori in ``InvoiceSatus`` / ``InvoiceRateizzSatus`` come
        stringa. Stringa vuota se ``invoice`` e' None o se ``NUMERO_RATE``
        non e' tra i valori validi (1 o 3).
    """
    if not invoice:
        return ""

    # Eccezione manuale: STORNATA vince su qualsiasi calcolo.
    if is_invoice_stornata(invoice):
        return InvoiceSatus.STORNATA.value

    today = today or date.today()

    try:
        num_rate = int(invoice.get(DBInvoicesColumns.NUMERO_RATE.value) or 1)
    except (TypeError, ValueError):
        num_rate = 1

    paid_rates = _extract_paid_rates(payments)

    if num_rate == int(Rateizzazione.UNA.value):
        return _compute_status_1_rata(invoice, paid_rates, today)

    if num_rate == int(Rateizzazione.TRE.value):
        return _compute_status_3_rate(invoice, paid_rates, today)

    return ""


def is_invoice_fully_paid(invoice, payments, today: date = None) -> bool:
    """True se la fattura risulta interamente saldata (1 rata SALDATA o 3 rate PAGATA)."""
    status = compute_invoice_status(invoice, payments, today)
    return status in (InvoiceSatus.SALDATA.value, InvoiceRateizzSatus.PAGATA.value)


# ---------------------------------------------------------------------------
# Helper interni
# ---------------------------------------------------------------------------

def _extract_paid_rates(payments) -> set:
    """Set degli indici di rata risultati pagati (LINKED_RATA, default 1 se mancante)."""
    paid = set()
    for p in payments or []:
        if not p:
            continue
        linked = p.get(DBPaymentsColumns.LINKED_RATA.value)
        if linked is None:
            paid.add(1)
            continue
        try:
            paid.add(int(linked))
        except (TypeError, ValueError):
            continue
    return paid


def _compute_status_1_rata(invoice, paid_rates, today) -> str:
    if 1 in paid_rates:
        return InvoiceSatus.SALDATA.value
    scadenza = ControllerUtils.parse_date(
        invoice.get(DBInvoicesColumns.DATA_SCADENZA_1.value) or ""
    )
    if scadenza is not None and today > scadenza:
        return InvoiceSatus.SCADUTA.value
    return InvoiceSatus.EMESSA.value


def _compute_status_3_rate(invoice, paid_rates, today) -> str:
    paid_count = len(paid_rates & {1, 2, 3})
    if paid_count == 3:
        return InvoiceRateizzSatus.PAGATA.value

    scadenze = [
        ControllerUtils.parse_date(invoice.get(DBInvoicesColumns.DATA_SCADENZA_1.value) or ""),
        ControllerUtils.parse_date(invoice.get(DBInvoicesColumns.DATA_SCADENZA_2.value) or ""),
        ControllerUtils.parse_date(invoice.get(DBInvoicesColumns.DATA_SCADENZA_3.value) or ""),
    ]

    # Rate non pagate ma con scadenza gia' passata.
    overdue_unpaid = sum(
        1
        for i, s in enumerate(scadenze, start=1)
        if i not in paid_rates and s is not None and today > s
    )

    if paid_count == 0:
        if overdue_unpaid == 3:
            return InvoiceRateizzSatus.SCADUTA.value
        if overdue_unpaid > 0:
            return InvoiceRateizzSatus.CRITICA.value
        return InvoiceRateizzSatus.EMESSA.value

    # 1 o 2 rate pagate.
    if overdue_unpaid > 0:
        return InvoiceRateizzSatus.CRITICA.value
    return InvoiceRateizzSatus.PARZIALMENTE_SALDATA.value

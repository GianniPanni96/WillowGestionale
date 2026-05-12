from datetime import datetime

from Gestionale_Enums import DBInvoicesColumns, DBPaymentsColumns, InvoiceSatus
from Utils.Controller_utils import ControllerUtils

from WarningServices.Warning_types import WarningInfo, WarningSeverity


class InvoiceWarningService:
    """
    Costruttore di warning per le liste fatture.

    Trigger:
    - SEV 1 (FK rotte): client_missing, invoicer_missing, account_missing,
      production_missing, linked_invoice_missing;
    - SEV 2 (incoerenza dato): payment_total_mismatch;
    - SEV 3 (info retrieval): previous_year.

    I sev 1 hanno priorita' (vengono restituiti se rilevati prima di
    valutare gli altri). Sui detail view, il warning sev 1 indica anche
    quale widget evidenziare in rosso (``broken_field_key``).
    """

    PAYMENT_TOTAL_TOLERANCE = 0.01

    # Mappatura type_key -> chiave widget nel detail view. Il detail
    # usa questa stringa per matchare ``self.invoice_widgets[key]`` ed
    # evidenziarlo in rosso.
    FK_FIELD_BY_TYPE = {
        "client_missing": DBInvoicesColumns.ID_CLIENTE.value,
        "invoicer_missing": DBInvoicesColumns.ID_UTENTE.value,
        "account_missing": DBInvoicesColumns.ID_CONTO.value,
        "production_missing": DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value,
        "linked_invoice_missing": DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value,
    }

    def __init__(
        self,
        productions_query_service,
        payments_query_service=None,
        clients_query_service=None,
        user_query_service=None,
        accounts_query_service=None,
        invoices_query_service=None,
    ):
        self.productions_query_service = productions_query_service
        self.payments_query_service = payments_query_service
        self.clients_query_service = clients_query_service
        self.user_query_service = user_query_service
        self.accounts_query_service = accounts_query_service
        self.invoices_query_service = invoices_query_service

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def collect_warnings_for_list(self, items_list) -> dict[str, WarningInfo]:
        warnings: dict[str, WarningInfo] = {}

        for invoice in items_list:
            if not invoice:
                continue
            name = invoice[DBInvoicesColumns.NUMERO_FATTURA.value]

            # SEV 1: FK rotte (priorita' assoluta).
            sev1 = self._check_fk_consistency(invoice)
            if sev1 is not None:
                warnings[name] = sev1
                continue

            # SEV 3: previous year.
            previous = self._check_previous_year(invoice)
            if previous is not None:
                warnings[name] = previous
                continue

            # SEV 2: incoerenze.
            mismatch = self._check_payments_total_mismatch(invoice)
            if mismatch is not None:
                warnings[name] = mismatch

        return warnings

    # ------------------------------------------------------------------
    # SEV 1 - FK consistency
    # ------------------------------------------------------------------

    def _check_fk_consistency(self, invoice) -> WarningInfo | None:
        # produzione_missing
        prod_id = invoice.get(DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value)
        if prod_id and self.productions_query_service is not None:
            if self.productions_query_service.retrieve_production_map_by_id(prod_id) is None:
                return self._fk_info(
                    "production_missing",
                    "La produzione associata a questa fattura non esiste piu' nel database.\n"
                    "Provvedere alla modifica o allo storno di questa fattura.",
                )
        # client_missing
        cli_id = invoice.get(DBInvoicesColumns.ID_CLIENTE.value)
        if cli_id and self.clients_query_service is not None:
            if self.clients_query_service.retrieve_client_map_by_id(cli_id) is None:
                return self._fk_info(
                    "client_missing",
                    "Il cliente associato a questa fattura non esiste piu' nel database.",
                )
        # invoicer_missing
        inv_id = invoice.get(DBInvoicesColumns.ID_UTENTE.value)
        if inv_id and self.user_query_service is not None:
            if self.user_query_service.retrieve_user_map_by_id(inv_id) is None:
                return self._fk_info(
                    "invoicer_missing",
                    "L'utente emittente di questa fattura non esiste piu' nel database.",
                )
        # account_missing
        acc_id = invoice.get(DBInvoicesColumns.ID_CONTO.value)
        if acc_id and self.accounts_query_service is not None:
            if self.accounts_query_service.retrieve_account_map_by_id(acc_id) is None:
                return self._fk_info(
                    "account_missing",
                    "Il conto associato a questa fattura non esiste piu' nel database.",
                )
        # linked_invoice_missing (opzionale: e' una FK self)
        linked = invoice.get(DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value)
        if linked and self.invoices_query_service is not None:
            if self.invoices_query_service.retrieve_invoice_map_by_id(linked) is None:
                return self._fk_info(
                    "linked_invoice_missing",
                    "La fattura collegata a questa non esiste piu' nel database.",
                )
        return None

    def _fk_info(self, type_key: str, text: str) -> WarningInfo:
        return WarningInfo(
            type_key=type_key,
            severity=WarningSeverity.CONSISTENCY,
            text=text,
            broken_field_key=self.FK_FIELD_BY_TYPE.get(type_key),
        )

    # ------------------------------------------------------------------
    # SEV 2 - data inconsistency
    # ------------------------------------------------------------------

    def _check_payments_total_mismatch(self, invoice) -> WarningInfo | None:
        if self.payments_query_service is None:
            return None

        # Trigger valido solo per fatture interamente saldate: per le
        # fatture EMESSE / SCADUTE e' normale che la somma pagamenti
        # sia inferiore al netto (rate ancora in corso). Il warning
        # diventerebbe ridondante con il label di stato della fattura
        # e farebbe rumore inutile sulle rateizzate non saldate.
        if str(invoice.get(DBInvoicesColumns.STATUS.value) or "") != InvoiceSatus.SALDATA.value:
            return None

        try:
            netto = float(invoice.get(DBInvoicesColumns.NETTO_A_PAGARE.value) or 0)
        except (TypeError, ValueError):
            return None

        invoice_id = invoice.get(DBInvoicesColumns.ID.value)
        try:
            payments = self.payments_query_service.retrieve_payments_map_list_by_invoice_id(
                invoice_id, year=-1
            ) or []
        except Exception:
            return None
        if not payments:
            return None

        total_paid = 0.0
        for payment in payments:
            try:
                total_paid += float(payment.get(DBPaymentsColumns.PAYMENT_AMOUNT.value) or 0)
            except (TypeError, ValueError):
                continue

        diff = round(total_paid - netto, 2)
        if abs(diff) <= self.PAYMENT_TOTAL_TOLERANCE:
            return None

        if diff > 0:
            text = (
                "Incoerenza dato: la somma dei pagamenti collegati a questa fattura\n"
                f"({round(total_paid, 2)} €) supera il netto a pagare ({round(netto, 2)} €).\n"
                "Verifica gli importi dei pagamenti."
            )
        else:
            text = (
                "La somma dei pagamenti collegati a questa fattura\n"
                f"({round(total_paid, 2)} €) e' inferiore al netto a pagare ({round(netto, 2)} €).\n"
                f"Residuo da saldare: {round(-diff, 2)} €."
            )
        return WarningInfo(
            type_key="payment_total_mismatch",
            severity=WarningSeverity.INCONSISTENCY,
            text=text,
        )

    # ------------------------------------------------------------------
    # SEV 3 - retrieval info
    # ------------------------------------------------------------------

    def _check_previous_year(self, invoice) -> WarningInfo | None:
        creation = ControllerUtils.parse_date(invoice.get(DBInvoicesColumns.DATA_CREAZIONE.value))
        if not creation or creation.year == datetime.now().year:
            return None
        return WarningInfo(
            type_key="previous_year",
            severity=WarningSeverity.INFO,
            text=(
                f"Questa fattura riguarda l'anno contabile {creation.year}.\n"
                "Stai visualizzando questa fattura perche' risulta non interamente saldata "
                "durante il suo anno contabile di riferimento.\n"
                f"Questa fattura non viene conteggiata per i dati aggregati del {datetime.now().year},"
                "ma presa in considerazione per il calcolo della previsione tasse."
            ),
        )

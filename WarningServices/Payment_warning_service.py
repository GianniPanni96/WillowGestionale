from datetime import datetime

from Gestionale_Enums import (
    DBInvoicesColumns,
    DBPaymentsColumns,
    InvoiceSatus,
    Rateizzazione,
)
from WarningServices.Warning_types import WarningInfo, WarningSeverity


class PaymentWarningService:
    """
    Costruttore warning per le liste pagamenti.

    Trigger:
    - SEV 1: linked_invoice_missing, account_missing.
    - SEV 2: linked_invoice_stornata, linked_invoice_modified_after,
      rata_overpayment.
    - SEV 3: previous_year.
    """

    RATA_TOLERANCE = 0.01

    FK_FIELD_BY_TYPE = {
        "linked_invoice_missing": DBPaymentsColumns.INVOICE_ID.value,
        "account_missing": DBPaymentsColumns.CONTO_ID.value,
    }

    def __init__(self, invoices_query_service, payments_query_service=None, accounts_query_service=None,
                 fiscal_settings=None):
        self.invoices_query_service = invoices_query_service
        self.payments_query_service = payments_query_service
        self.accounts_query_service = accounts_query_service
        self.fiscal_settings = fiscal_settings

    def collect_warnings_for_list(self, items_list) -> dict[str, WarningInfo]:
        warnings: dict[str, WarningInfo] = {}

        for payment in items_list:
            if not payment:
                continue
            name = payment[DBPaymentsColumns.PAYMENT_NAME.value]

            # SEV 1: FK rotte.
            sev1 = self._check_fk_consistency(payment)
            if sev1 is not None:
                warnings[name] = sev1
                continue

            # Per i restanti check serve la fattura collegata.
            invoice = self.invoices_query_service.retrieve_invoice_map_by_id(
                payment[DBPaymentsColumns.INVOICE_ID.value]
            )
            if not invoice:
                continue

            # SEV 2: stornata.
            if invoice[DBInvoicesColumns.STATUS.value] == InvoiceSatus.STORNATA.value:
                warnings[name] = WarningInfo(
                    type_key="linked_invoice_stornata",
                    severity=WarningSeverity.INCONSISTENCY,
                    text=(
                        "Questo pagamento fa riferimento ad una fattura stornata.\n"
                        "Modificare i dati del pagamento per mantenere la consistenza dei dati.\n"
                        "Si consiglia di eliminare questo pagamento o collegarlo alla fattura corretta."
                    ),
                )
                continue

            # SEV 2: invoice modified after payment.
            inv_updated = self._parse_datetime(invoice.get(DBInvoicesColumns.UPDATED_AT.value))
            pay_updated = self._parse_datetime(payment.get(DBPaymentsColumns.UPDATED_AT.value))
            if inv_updated and pay_updated and inv_updated > pay_updated:
                warnings[name] = WarningInfo(
                    type_key="linked_invoice_modified_after",
                    severity=WarningSeverity.INCONSISTENCY,
                    text=(
                        "Questo pagamento fa riferimento ad una fattura i cui dati sono stati modificati.\n"
                        "Controllare la consistenza dei dati di questo pagamento.\n"
                        "Salva nuovamente i dati di questo pagamento per non visualizzare più questo warning"
                    ),
                )
                continue

            # SEV 3: previous year.
            inv_creation = self._parse_datetime(invoice.get(DBInvoicesColumns.DATA_CREAZIONE.value))
            if inv_creation and inv_creation.year != datetime.now().year:
                warnings[name] = WarningInfo(
                    type_key="previous_year",
                    severity=WarningSeverity.INFO,
                    text=(
                        f"Questo pagamento riguarda l'anno contabile {inv_creation.year}.\n"
                        "Stai visualizzando questo pagamento perche' e collegato ad una fattura non "
                        "interamente saldata durante il suo anno contabile di riferimento.\n"
                        "Questo pagamento non viene conteggiato all'interno di questo anno contabile."
                    ),
                )
                continue

            # SEV 2: rata overpayment.
            overpayment_info = self._check_rata_overpayment(payment, invoice)
            if overpayment_info is not None:
                warnings[name] = overpayment_info

        return warnings

    # ------------------------------------------------------------------
    # SEV 1 - FK consistency
    # ------------------------------------------------------------------

    def _check_fk_consistency(self, payment) -> WarningInfo | None:
        inv_id = payment.get(DBPaymentsColumns.INVOICE_ID.value)
        if inv_id is None or (
            self.invoices_query_service is not None
            and self.invoices_query_service.retrieve_invoice_map_by_id(inv_id) is None
        ):
            return self._fk_info(
                "linked_invoice_missing",
                "La fattura collegata a questo pagamento non esiste piu' nel database.",
            )
        acc_id = payment.get(DBPaymentsColumns.CONTO_ID.value)
        if self.accounts_query_service is not None and acc_id and (
            self.accounts_query_service.retrieve_account_map_by_id(acc_id) is None
        ):
            return self._fk_info(
                "account_missing",
                "Il conto associato a questo pagamento non esiste piu' nel database.",
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
    # SEV 2 - rata overpayment
    # ------------------------------------------------------------------

    def _check_rata_overpayment(self, payment, invoice) -> WarningInfo | None:
        if self.payments_query_service is None:
            return None
        try:
            netto = float(invoice.get(DBInvoicesColumns.NETTO_A_PAGARE.value) or 0)
            num_rate = int(invoice.get(DBInvoicesColumns.NUMERO_RATE.value) or 1)
        except (TypeError, ValueError):
            return None

        rata = str(payment.get(DBPaymentsColumns.LINKED_RATA.value) or "")
        if rata not in {str(i) for i in range(1, num_rate + 1)}:
            return None

        if num_rate == int(Rateizzazione.UNA.value):
            quota_rata = netto if rata == "1" else 0.0
        elif self.fiscal_settings is not None:
            quota_rata = self.fiscal_settings.quota_for_rata(netto, num_rate, int(rata))
        else:
            quota_rata = netto / num_rate

        try:
            all_payments = self.payments_query_service.retrieve_payments_map_list_by_invoice_id(
                invoice.get(DBInvoicesColumns.ID.value), year=-1
            ) or []
        except Exception:
            return None

        total_for_rata = 0.0
        for p in all_payments:
            if str(p.get(DBPaymentsColumns.LINKED_RATA.value) or "") != rata:
                continue
            try:
                total_for_rata += float(p.get(DBPaymentsColumns.PAYMENT_AMOUNT.value) or 0)
            except (TypeError, ValueError):
                continue

        diff = round(total_for_rata - quota_rata, 2)
        if diff <= self.RATA_TOLERANCE:
            return None
        return WarningInfo(
            type_key="rata_overpayment",
            severity=WarningSeverity.INCONSISTENCY,
            text=(
                "Incoerenza dato: la somma dei pagamenti registrati sulla rata "
                f"{rata} ({round(total_for_rata, 2)} €) supera la quota teorica della "
                f"rata ({round(quota_rata, 2)} €).\n"
                "Verifica gli importi dei pagamenti su questa rata."
            ),
        )

    @staticmethod
    def _parse_datetime(value):
        if not value:
            return None
        for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, pattern)
            except ValueError:
                continue
        return None

from datetime import datetime

from Gestionale_Enums import DBInvoicesColumns, DBPaymentsColumns, InvoiceSatus


class PaymentWarningService:
    """
    Servizio dedicato alla costruzione dei warning per le liste pagamenti.

    Replica le regole della legacy view spostandole fuori dalla UI.
    """

    def __init__(self, invoices_query_service):
        self.invoices_query_service = invoices_query_service

    def collect_warnings_for_list(self, items_list):
        warnings = {}

        for payment in items_list:
            if not payment:
                continue

            payment_name = payment[DBPaymentsColumns.PAYMENT_NAME.value]
            invoice = self.invoices_query_service.retrieve_invoice_map_by_id(payment[DBPaymentsColumns.INVOICE_ID.value])
            if not invoice:
                continue

            invoice_creation_date = self._parse_datetime(invoice.get(DBInvoicesColumns.DATA_CREAZIONE.value))

            if invoice[DBInvoicesColumns.STATUS.value] == InvoiceSatus.STORNATA.value:
                warnings[payment_name] = (
                    "Questo pagamento fa riferimento ad una fattura stornata,\n"
                    "modificare i dati del pagamento per mantenere la consistenza dei dati.\n"
                    "Si consiglia di eliminare questo pagamento o collegarlo alla fattura corretta."
                )
                continue

            invoice_update_date = self._parse_datetime(invoice.get(DBInvoicesColumns.UPDATED_AT.value))
            payment_update_date = self._parse_datetime(payment.get(DBPaymentsColumns.UPDATED_AT.value))
            if invoice_update_date and payment_update_date and invoice_update_date > payment_update_date:
                warnings[payment_name] = (
                    "Questo pagamento fa riferimento ad una fattura i cui dati sono stati modificati.\n"
                    "Controllare la consistenza dei dati di questo pagamento.\n"
                )

            if invoice_creation_date and invoice_creation_date.year != datetime.now().year:
                warnings[payment_name] = (
                    f"Questo pagamento riguarda l'anno contabile {invoice_creation_date.year}.\n"
                    "Stai visualizzando questo pagamento perche' e collegato ad una fattura non interamente "
                    "saldata durante il suo anno contabile di riferimento.\n"
                    "Questo pagamento non viene conteggiato all'interno di questo anno contabile."
                )

        return warnings

    def _parse_datetime(self, value):
        if not value:
            return None

        for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, pattern)
            except ValueError:
                continue

        return None

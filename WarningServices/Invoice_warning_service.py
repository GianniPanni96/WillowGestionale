from datetime import datetime

from Gestionale_Enums import DBInvoicesColumns
from Utils.Controller_utils import ControllerUtils


class InvoiceWarningService:
    """
    Servizio dedicato alla costruzione dei warning per le liste fatture.

    Incapsula le regole di warning della legacy view, cosi' la list view resta
    concentrata sulla sola presentazione.
    """

    def __init__(self, productions_query_service):
        self.productions_query_service = productions_query_service

    def collect_warnings_for_list(self, items_list):
        warnings = {}

        for invoice in items_list:
            if not invoice:
                continue

            invoice_name = invoice[DBInvoicesColumns.NUMERO_FATTURA.value]
            production_id = invoice[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value]
            production = self.productions_query_service.retrieve_production_map_by_id(production_id)
            invoice_creation_date = ControllerUtils.parse_date(invoice.get(DBInvoicesColumns.DATA_CREAZIONE.value))

            if not production:
                warnings[invoice_name] = (
                    "La produzione associata a questa fattura non esiste nel database.\n"
                    "Provvedere alla modifica o allo storno di questa fattura."
                )
                continue

            if invoice_creation_date and invoice_creation_date.year != datetime.now().year:
                warnings[invoice_name] = (
                    f"Questa fattura riguarda l'anno contabile {invoice_creation_date.year}.\n"
                    "Stai visualizzando questa fattura perche' risulta non interamente saldata "
                    "durante il suo anno contabile di riferimento.\n"
                    "Questa fattura non viene conteggiata all'interno di questo anno contabile."
                )

        return warnings

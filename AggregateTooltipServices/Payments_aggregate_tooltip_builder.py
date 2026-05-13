"""Tooltip builder degli aggregati Pagamenti."""

from AggregateTooltipServices.Aggregate_tooltip_builder_base import (
    AggregateTooltipBuilderBase,
)


class PaymentsAggregateTooltipBuilder(AggregateTooltipBuilderBase):
    """Tooltip per: # PAGAMENTI, TOT. PAGAMENTI."""

    def __init__(self, payment_analyzer_service):
        self.analyzer = payment_analyzer_service

    def build_tooltips(self, toggle_value=None) -> dict:
        a = self.analyzer
        count = a.count_payments(include_unpaid_invoice_payments=False)
        tot = a.calculate_tot_payments(include_unpaid_invoice_payments=False)

        return {
            "# PAGAMENTI": (
                "Numero pagamenti\n\n"
                "• Vengono retrievati i pagamenti dell'anno contabile corrente.\n"
                "• Vengono esclusi i pagamenti collegati a fatture non saldate:\n"
                "  contano solo quelli legati a fatture interamente incassate.\n\n"
                f"Risultato: {self.fmt_int(count)} pagamenti."
            ),
            "TOT. PAGAMENTI": (
                "Totale pagamenti incassati\n\n"
                "• Stesso insieme della voce '# PAGAMENTI' (anno corrente, fatture\n"
                "  interamente saldate).\n"
                "• Somma del campo 'Importo Pagato' di ciascun pagamento; gli importi\n"
                "  sono al lordo dell'IVA, perché la fattura collegata viene saldata\n"
                "  per intero al netto delle ritenute.\n\n"
                f"Risultato: {self.fmt_money(tot)}."
            ),
        }

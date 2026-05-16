"""Tooltip builder degli aggregati Rimborsi."""

from Gestionale_Enums import RefundsAggregateData
from AggregateTooltipServices.Aggregate_tooltip_builder_base import (
    AggregateTooltipBuilderBase,
)


class RefundsAggregateTooltipBuilder(AggregateTooltipBuilderBase):
    """Tooltip per: #RIMBORSI, TOT. RIMBORSI."""

    def __init__(self, refund_analyzer_service):
        self.analyzer = refund_analyzer_service

    def build_tooltips(self, toggle_value=None) -> dict:
        a = self.analyzer
        count = a.count_refunds()
        tot = a.calculate_tot_refunds()

        return {
            RefundsAggregateData.NUMERO_RIMBORSI.value: (
                "Numero rimborsi\n\n"
                "• Vengono retrievati tutti i rimborsi dell'anno contabile corrente.\n"
                "• Nessun ulteriore filtro: il rimborso e' un movimento di denaro\n"
                "  in uscita verso il cliente, indipendente dallo stato di fatture\n"
                "  o pagamenti.\n\n"
                f"Risultato: {self.fmt_int(count)} rimborsi."
            ),
            RefundsAggregateData.TOT_RIMBORSI.value: (
                "Totale rimborsi erogati\n\n"
                "• Stesso insieme della voce '#RIMBORSI' (anno contabile corrente).\n"
                "• Somma del campo 'Importo Rimborsato' di ciascun rimborso.\n"
                "• Gli importi sono al lordo: il rimborso non genera IVA né ritenuta,\n"
                "  quindi non c'è una versione netta separata.\n\n"
                f"Risultato: {self.fmt_money(tot)}."
            ),
        }

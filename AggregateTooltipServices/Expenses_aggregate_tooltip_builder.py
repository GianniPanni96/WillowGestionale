"""Tooltip builder degli aggregati Spese."""

from Gestionale_Enums import ExpensesAggregateData
from AggregateTooltipServices.Aggregate_tooltip_builder_base import (
    AggregateTooltipBuilderBase,
)


class ExpensesAggregateTooltipBuilder(AggregateTooltipBuilderBase):
    """Tooltip per: #SPESE, TOT. SPESE."""

    def __init__(self, expenses_analyzer_service):
        self.analyzer = expenses_analyzer_service

    def build_tooltips(self, toggle_value=None) -> dict:
        a = self.analyzer
        count = a.count_expenses()
        tot = a.calculate_tot_expenses()

        return {
            ExpensesAggregateData.NUMERO_SPESE.value: (
                "Numero spese\n\n"
                "• Vengono retrievate tutte le spese dell'anno contabile corrente.\n"
                "• Vengono inclusi sia gli importi una tantum sia quelli generati\n"
                "  da spese ricorrenti.\n"
                "• Nessun filtro su categoria, deducibilità o presenza fattura.\n\n"
                f"Risultato: {self.fmt_int(count)} spese."
            ),
            ExpensesAggregateData.TOT_SPESE.value: (
                "Totale spese sostenute\n\n"
                "• Stesso insieme della voce '#SPESE' (anno contabile corrente).\n"
                "• Somma del campo 'Importo Lordo' di ciascuna spesa: è il valore\n"
                "  IVA inclusa, ossia l'esborso effettivo.\n"
                "• Per ottenere imponibile (netto) e IVA separati si guarda al\n"
                "  dettaglio della singola spesa o ai report fiscali.\n\n"
                f"Risultato: {self.fmt_money(tot)}."
            ),
        }

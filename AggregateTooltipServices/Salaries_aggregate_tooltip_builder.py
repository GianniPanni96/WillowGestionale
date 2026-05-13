"""Tooltip builder degli aggregati Salari."""

from Gestionale_Enums import SalariesAggregateData
from AggregateTooltipServices.Aggregate_tooltip_builder_base import (
    AggregateTooltipBuilderBase,
)


class SalariesAggregateTooltipBuilder(AggregateTooltipBuilderBase):
    """Tooltip per: #SALARI, TOT. SALARI."""

    def __init__(self, salary_analyzer_service):
        self.analyzer = salary_analyzer_service

    def build_tooltips(self, toggle_value=None) -> dict:
        a = self.analyzer
        count = a.count_salaries()
        tot = a.calculate_tot_salaries()

        return {
            SalariesAggregateData.NUMERO_SALARI.value: (
                "Numero stipendi\n\n"
                "• Vengono retrievati tutti gli stipendi dell'anno contabile corrente.\n"
                "• Nessun ulteriore filtro: lo stipendio e' un movimento in uscita\n"
                "  verso un utente del sistema, indipendente da fatture o pagamenti.\n\n"
                f"Risultato: {self.fmt_int(count)} stipendi."
            ),
            SalariesAggregateData.TOT_SALARI.value: (
                "Totale stipendi erogati\n\n"
                "• Stesso insieme della voce '#SALARI' (anno contabile corrente).\n"
                "• Somma del campo 'Importo' di ciascuno stipendio.\n"
                "• Gli importi sono al lordo per l'azienda (esborso effettivo); le\n"
                "  trattenute fiscali sono gestite separatamente nella sezione TASSE\n"
                "  del dettaglio utente.\n\n"
                f"Risultato: {self.fmt_money(tot)}."
            ),
        }

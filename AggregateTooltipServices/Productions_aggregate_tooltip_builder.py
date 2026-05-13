"""Tooltip builder degli aggregati Produzioni."""

from AggregateTooltipServices.Aggregate_tooltip_builder_base import (
    AggregateTooltipBuilderBase,
)


class ProductionsAggregateTooltipBuilder(AggregateTooltipBuilderBase):
    """Tooltip per: # PRODUZIONI ATTIVE, # PRODUZIONI CHIUSE, MEDIA ORE, MEDIA €/h."""

    def __init__(self, productions_analyzer_service):
        self.analyzer = productions_analyzer_service

    def build_tooltips(self, toggle_value=None) -> dict:
        a = self.analyzer
        n_attive = a.count_active_productions(include_prod_with_unpaid_invoices=True, year=-1)
        n_chiuse = a.count_closed_productions(include_prod_with_unpaid_invoices=True, year=-1)
        media_ore = a.mean_hours_for_production(include_prod_with_unpaid_invoices=True, year=-1)
        media_eur = a.mean_prezzo_orario(include_prod_with_unpaid_invoices=True, year=-1)

        common_intro = (
            "• Vengono retrievate tutte le produzioni (nessun filtro anno),\n"
            "  comprese quelle collegate a fatture non interamente saldate.\n"
        )

        return {
            "# PRODUZIONI ATTIVE": (
                "Numero produzioni attive\n\n"
                + common_intro
                + "• Si conteggiano solo le produzioni con stato diverso da CLOSED\n"
                  "  (es. START_WAITING, WORKING, DOC_WAITING, REVISION).\n\n"
                  f"Risultato: {self.fmt_int(n_attive)} produzioni attive."
            ),
            "# PRODUZIONI CHIUSE": (
                "Numero produzioni chiuse\n\n"
                + common_intro
                + "• Si conteggiano solo le produzioni con stato CLOSED.\n\n"
                  f"Risultato: {self.fmt_int(n_chiuse)} produzioni chiuse."
            ),
            "MEDIA ORE": (
                "Media ore di produzione\n\n"
                + common_intro
                + "• Media del campo 'Ore di produzione' su tutte le produzioni\n"
                  "  retrievate (attive + chiuse, senza distinzione di stato).\n\n"
                  f"Risultato: {self.fmt_hours(media_ore)} per produzione."
            ),
            "MEDIA €/h": (
                "Prezzo orario medio\n\n"
                + common_intro
                + "• Per ogni produzione il prezzo orario e' derivato dalle fatture\n"
                  "  collegate: somma servizi + rimborsi delle fatture ÷ ore della\n"
                  "  produzione.\n"
                  "• Le produzioni senza fatture o con prezzo orario non calcolabile\n"
                  "  vengono escluse dalla media; le altre concorrono come valore\n"
                  "  unitario.\n"
                  "• Gli importi delle fatture sono usati al lordo dell'IVA (campo\n"
                  "  Servizi e Rimborsi).\n\n"
                  f"Risultato: {self.fmt_rate(media_eur)} di prezzo orario medio."
            ),
        }

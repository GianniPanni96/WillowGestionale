"""
Tooltip builder degli aggregati della list view Fatture.

Si appoggia all'``InvoiceAnalyzerService`` per recuperare i valori
numerici e ricostruisce la formula in chiave business.
"""

from AggregateTooltipServices.Aggregate_tooltip_builder_base import (
    AggregateTooltipBuilderBase,
)


class InvoicesAggregateTooltipBuilder(AggregateTooltipBuilderBase):
    """
    Tooltip per: # FATTURE, FATTURATO, CREDITI, MEDIA FATTURE.

    Le quattro voci dipendono dal toggle LORDI/NETTI esposto in alto
    nella aggregate bar; il builder produce due varianti di testo a
    seconda del ``toggle_value``.
    """

    def __init__(self, invoices_analyzer_service):
        self.analyzer = invoices_analyzer_service

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def build_tooltips(self, toggle_value: "str | None" = None) -> dict:
        netti = (toggle_value or "").upper() == "NETTI"
        a = self.analyzer

        # Snapshot dei valori sottostanti, per esporli nelle formule.
        tot_doc = a.calculate_TOT_DOCUMENTO_invoiced(include_unpaid_invoices=False)
        iva = a.calculate_IVA_invoiced(include_unpaid_invoices=False)
        ritenuta = a.calculate_RITENUTA_ACCONTO_invoiced(include_unpaid_invoices=False)
        count = a.count_invoices(include_unpaid_invoices=False)

        fatt_lordo = tot_doc - iva
        fatt_netto = tot_doc - iva - ritenuta
        fatturato_value = fatt_netto if netti else fatt_lordo
        media_value = (fatturato_value / count) if count > 0 else 0
        crediti_lordo = a.calculate_CRED_LORDO_invoiced(include_unpaid_invoices=False)
        crediti_netto = a.calculate_CRED_NETTO_invoiced(include_unpaid_invoices=False)
        crediti_value = crediti_netto if netti else crediti_lordo

        modalita = "NETTI" if netti else "LORDI"

        return {
            "# FATTURE": self._tooltip_count(count),
            "FATTURATO": self._tooltip_fatturato(
                modalita, tot_doc, iva, ritenuta, fatt_lordo, fatt_netto, fatturato_value, netti
            ),
            "CREDITI": self._tooltip_crediti(modalita, crediti_value, netti),
            "MEDIA FATTURE": self._tooltip_media(modalita, fatturato_value, count, media_value),
        }

    # ------------------------------------------------------------------
    # Singoli tooltip
    # ------------------------------------------------------------------

    def _tooltip_count(self, count: int) -> str:
        return (
            "Numero fatture\n\n"
            "• Vengono retrievate tutte le fatture dell'anno contabile corrente,\n"
            "  comprese quelle non interamente saldate.\n"
            "• Vengono escluse le note di credito (NDC) e le fatture stornate:\n"
            "  non concorrono al conteggio.\n\n"
            f"Risultato: {self.fmt_int(count)} fatture."
        )

    def _tooltip_fatturato(
        self, modalita, tot_doc, iva, ritenuta, fatt_lordo, fatt_netto, fatturato_value, netti
    ) -> str:
        intro = (
            f"Fatturato {modalita}\n\n"
            "• Vengono retrievate le fatture dell'anno contabile corrente,\n"
            "  comprese quelle non interamente saldate.\n"
            "• Vengono escluse note di credito (NDC) e fatture stornate.\n"
        )
        if netti:
            return (
                intro
                + "\nFormula (NETTI):\n"
                  "  1. Totale documento delle fatture incluse\n"
                  f"     = {self.fmt_money(tot_doc)}\n"
                  "  2. IVA fatturata\n"
                  f"     = {self.fmt_money(iva)}\n"
                  "  3. Ritenuta d'acconto fatturata\n"
                  f"     = {self.fmt_money(ritenuta)}\n"
                  "  4. Fatturato netto = Totale documento − IVA − Ritenuta\n"
                  f"     = {self.fmt_money(tot_doc)} − {self.fmt_money(iva)} − "
                  f"{self.fmt_money(ritenuta)}\n"
                  f"     = {self.fmt_money(fatt_netto)}"
            )
        return (
            intro
            + "\nFormula (LORDI):\n"
              "  1. Totale documento delle fatture incluse\n"
              f"     = {self.fmt_money(tot_doc)}\n"
              "  2. IVA fatturata\n"
              f"     = {self.fmt_money(iva)}\n"
              "  3. Fatturato lordo = Totale documento − IVA\n"
              f"     = {self.fmt_money(tot_doc)} − {self.fmt_money(iva)}\n"
              f"     = {self.fmt_money(fatt_lordo)}"
        )

    def _tooltip_crediti(self, modalita, crediti_value, netti) -> str:
        intro = (
            f"Crediti {modalita}\n\n"
            "• Vengono retrievate le fatture dell'anno contabile corrente,\n"
            "  comprese quelle non interamente saldate.\n"
            "• Per ogni fattura si confronta la somma dei pagamenti collegati\n"
            "  con l'importo dovuto della rata; la parte mancante diventa credito.\n"
            "• Note di credito e fatture stornate vengono escluse.\n"
        )
        if netti:
            modalita_text = (
                "\nL'importo dovuto per rata e' calcolato sul netto "
                "(Totale documento − IVA − Ritenuta), suddiviso secondo "
                "il numero di rate della fattura.\n"
            )
        else:
            modalita_text = (
                "\nL'importo dovuto per rata e' calcolato sul lordo "
                "(Totale documento − IVA), suddiviso secondo il numero "
                "di rate della fattura.\n"
            )
        return (
            intro
            + modalita_text
            + f"\nRisultato: {self.fmt_money(crediti_value)} di crediti residui."
        )

    def _tooltip_media(self, modalita, fatturato_value, count, media_value) -> str:
        return (
            f"Media fatture {modalita}\n\n"
            "• Media calcolata sullo stesso insieme di fatture usato per il fatturato\n"
            "  (anno corrente, no NDC, no stornate).\n\n"
            f"Formula: Fatturato {modalita} ÷ Numero fatture\n"
            f"  = {self.fmt_money(fatturato_value)} ÷ {self.fmt_int(count)}\n"
            f"  = {self.fmt_money(media_value)}"
        )

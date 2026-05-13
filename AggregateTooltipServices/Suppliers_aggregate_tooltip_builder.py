"""Tooltip builder degli aggregati Fornitori."""

from AggregateTooltipServices.Aggregate_tooltip_builder_base import (
    AggregateTooltipBuilderBase,
)


class SuppliersAggregateTooltipBuilder(AggregateTooltipBuilderBase):
    """
    Tooltip per: # FORNITORI, TOT. SPESE, SPESA MEDIA.

    Stessa filosofia del builder Clienti: gli aggregati sono calcolati
    sulle righe del modello (gia' arricchite di TOT_SPESE / NUM_SPESE
    per supplier dal Supplier analyzer).
    """

    def __init__(self, suppliers_analyzer_service=None):
        self.analyzer = suppliers_analyzer_service

    def build_tooltips(self, toggle_value=None, rows=None) -> dict:
        rows = rows or []
        n_fornitori = len(rows)
        tot_spese = sum(r.get("tot_spese", 0) for r in rows)
        tot_num_spese = sum(r.get("num_spese", 0) for r in rows)
        spesa_media = (tot_spese / tot_num_spese) if tot_num_spese else 0

        time_window_note = (
            "• Insieme di riferimento: i fornitori correntemente esposti nella tabella,\n"
            "  in funzione della time window selezionata in alto.\n"
        )

        return {
            "# FORNITORI": (
                "Numero fornitori\n\n"
                + time_window_note
                + "• Si conteggiano i fornitori con almeno una spesa nel periodo\n"
                  "  considerato.\n\n"
                  f"Risultato: {self.fmt_int(n_fornitori)} fornitori."
            ),
            "TOT. SPESE": (
                "Totale spese verso fornitori\n\n"
                + time_window_note
                + "• Per ogni fornitore: somma del campo 'Importo Lordo' delle spese\n"
                  "  registrate (IVA inclusa, e' l'esborso effettivo).\n"
                  "• Il totale qui mostrato e' la somma su tutti i fornitori in lista.\n\n"
                  f"Risultato: {self.fmt_money(tot_spese)}."
            ),
            "SPESA MEDIA": (
                "Spesa media per fornitore\n\n"
                + time_window_note
                + "• Indica il valore medio di una singola spesa, considerando tutte le\n"
                  "  spese registrate verso i fornitori in lista.\n\n"
                  "Formula:\n"
                  "  Spesa media = Somma TOT. SPESE ÷ Somma del numero di spese\n"
                  f"  = {self.fmt_money(tot_spese)} ÷ {self.fmt_int(tot_num_spese)}\n"
                  f"  = {self.fmt_money(spesa_media)}"
            ),
        }

    # ------------------------------------------------------------------
    # Tooltip degli header di tabella (per-fornitore)
    # ------------------------------------------------------------------

    def build_header_tooltips(self) -> dict:
        """
        Restituisce ``dict[header_label, testo]`` con la spiegazione di
        come viene calcolata ciascuna colonna **per il singolo
        fornitore**.

        Le colonne dei dati anagrafici (NOME, PARTITA IVA, NOTE,
        CONTATTO) ricevono un tooltip descrittivo breve; le tre colonne
        aggregate (TOT. SPESE / # SPESE / SPESA MEDIA) ricevono la
        spiegazione del calcolo.
        """
        return {
            "NOME": (
                "Ragione sociale del fornitore, come salvata nel database."
            ),
            "PARTITA IVA": (
                "Partita IVA del fornitore, come salvata nel database."
            ),
            "TOT. SPESE": (
                "Totale spese verso il fornitore\n\n"
                "• Vengono retrievate tutte le spese registrate verso il fornitore\n"
                "  (senza filtro temporale: storico completo).\n"
                "• Somma del campo 'Importo Lordo' di ciascuna spesa: IVA inclusa,\n"
                "  ossia l'esborso effettivo dell'azienda."
            ),
            "# SPESE": (
                "Numero di spese registrate verso il fornitore.\n"
                "Stesso insieme della colonna TOT. SPESE (storico completo)."
            ),
            "SPESA MEDIA": (
                "Spesa media verso il fornitore\n\n"
                "Formula: TOT. SPESE ÷ # SPESE\n"
                "(stessa base di calcolo lorda della colonna TOT. SPESE)."
            ),
            "NOTE": (
                "Annotazioni libere registrate sul fornitore."
            ),
            "CONTATTO": (
                "Riferimento di contatto del fornitore (email o telefono),\n"
                "come salvato nei dati anagrafici."
            ),
        }

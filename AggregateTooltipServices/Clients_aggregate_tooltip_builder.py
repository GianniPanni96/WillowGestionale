"""Tooltip builder degli aggregati Clienti."""

from AggregateTooltipServices.Aggregate_tooltip_builder_base import (
    AggregateTooltipBuilderBase,
)


class ClientsAggregateTooltipBuilder(AggregateTooltipBuilderBase):
    """
    Tooltip per: # CLIENTI, TOT. ENTRATE, TOT. CREDITI, FATTURA MEDIA.

    A differenza degli altri dominî, qui gli aggregati sono calcolati
    direttamente sulle righe del modello (l'analyzer ha gia' aggregato
    per cliente le metriche TOT_ENTRATE / TOT_CREDITI / NUM_FATTURE).
    Per questo motivo ``build_tooltips`` accetta i ``rows`` correnti.
    """

    def __init__(self, clients_analyzer_service=None):
        # Manteniamo il parametro per simmetria con gli altri builder;
        # nello specifico la documentazione di calcolo lavora sui rows.
        self.analyzer = clients_analyzer_service

    def build_tooltips(self, toggle_value=None, rows=None) -> dict:
        rows = rows or []
        n_clienti = len(rows)
        tot_entrate = sum(r.get("tot_entrate", 0) for r in rows)
        tot_crediti = sum(r.get("tot_crediti", 0) for r in rows)
        tot_fatture = sum(r.get("num_fatture", 0) for r in rows)
        media_fattura = (tot_entrate / tot_fatture) if tot_fatture else 0

        time_window_note = (
            "• Insieme di riferimento: i clienti correntemente esposti nella tabella,\n"
            "  in funzione della time window selezionata in alto.\n"
        )

        return {
            "# CLIENTI": (
                "Numero clienti\n\n"
                + time_window_note
                + "• Si conteggiano tutti i clienti con almeno una fattura nel\n"
                  "  periodo corrente (così come restituiti dal query service).\n\n"
                  f"Risultato: {self.fmt_int(n_clienti)} clienti."
            ),
            "TOT. ENTRATE": (
                "Totale entrate dai clienti\n\n"
                + time_window_note
                + "• Per ogni cliente: somma del fatturato (lordo, IVA inclusa) delle\n"
                  "  fatture associate, incluse quelle non interamente saldate.\n"
                  "• Note di credito e fatture stornate sono escluse.\n"
                  "• Il totale qui mostrato e' la somma di queste entrate su tutti\n"
                  "  i clienti correntemente in lista.\n\n"
                  f"Risultato: {self.fmt_money(tot_entrate)}."
            ),
            "TOT. CREDITI": (
                "Totale crediti aperti\n\n"
                + time_window_note
                + "• Per ogni cliente: somma dei crediti aperti = importo dovuto per\n"
                  "  ciascuna rata di fattura meno la somma dei pagamenti incassati su\n"
                  "  quella rata.\n"
                  "• Modalita' lorda (IVA inclusa), in linea con il valore mostrato\n"
                  "  nella colonna TOT. CREDITI di ciascuna riga.\n\n"
                  f"Risultato: {self.fmt_money(tot_crediti)}."
            ),
            "FATTURA MEDIA": (
                "Fattura media\n\n"
                + time_window_note
                + "• Indica il valore medio di una fattura emessa ai clienti correntemente\n"
                  "  in lista.\n\n"
                  "Formula:\n"
                  "  Fattura media = Somma TOT. ENTRATE ÷ Somma del numero di fatture\n"
                  f"  = {self.fmt_money(tot_entrate)} ÷ {self.fmt_int(tot_fatture)}\n"
                  f"  = {self.fmt_money(media_fattura)}"
            ),
        }

    # ------------------------------------------------------------------
    # Tooltip degli header di tabella (per-cliente)
    # ------------------------------------------------------------------

    def build_header_tooltips(self) -> dict:
        """
        Restituisce ``dict[header_label, testo]`` con la spiegazione di
        come viene calcolata ciascuna colonna **per il singolo cliente**.

        Diversamente dai tooltip delle card aggregate, qui non
        sostituiamo valori: la spiegazione e' statica (logica di calcolo
        invariante rispetto allo stato del DB).
        """
        return {
            "NOME": (
                "Ragione sociale del cliente, come salvata nel database."
            ),
            "TOT. ENTRATE": (
                "Totale entrate dal cliente\n\n"
                "• Vengono retrievate le fatture associate al cliente nel periodo\n"
                "  corrente (anno contabile in corso), incluse quelle non interamente\n"
                "  saldate.\n"
                "• Vengono escluse note di credito e fatture stornate.\n"
                "• Somma del campo 'Totale Documento' (importi lordi, IVA inclusa)."
            ),
            "# FATTURE": (
                "Numero di fatture associate al cliente nello stesso insieme\n"
                "usato per TOT. ENTRATE (anno corrente, no NDC, no stornate)."
            ),
            "FATTURA MEDIA": (
                "Valore medio di una fattura del cliente.\n\n"
                "Formula: TOT. ENTRATE ÷ # FATTURE\n"
                "(stessa base di calcolo lorda delle altre due colonne)."
            ),
            "TOT. CREDITI": (
                "Crediti residui aperti verso il cliente\n\n"
                "• Per ogni fattura del cliente si confronta, rata per rata,\n"
                "  l'importo dovuto con la somma dei pagamenti incassati su quella\n"
                "  rata; la parte mancante diventa credito.\n"
                "• Modalita' lorda (IVA inclusa).\n"
                "• Note di credito e fatture stornate sono escluse."
            ),
            "TOT. RIMBORSI": (
                "Totale rimborsi erogati al cliente\n\n"
                "• Somma del campo 'Importo Rimborsato' dei rimborsi associati\n"
                "  al cliente nel periodo corrente.\n"
                "• Il rimborso non genera IVA né ritenuta: importo lordo = netto."
            ),
            "PAGAM. ORARIO\nMEDIO": (
                "Pagamento orario medio del cliente\n\n"
                "• Si considerano solo le fatture del cliente collegate a una\n"
                "  produzione (no NDC, no stornate).\n"
                "• Formula: Totale fatturato (lordo) ÷ Totale ore delle produzioni\n"
                "  collegate.\n"
                "• Esprime quanto, in media, il cliente paga per un'ora di lavoro\n"
                "  effettivamente svolta su sue produzioni."
            ),
            "TOT. GIORNI\nRITARDO": (
                "Giorni di ritardo cumulati\n\n"
                "• Si analizzano rata per rata le fatture del cliente nel periodo\n"
                "  corrente (no NDC, no stornate).\n"
                "• Per ciascuna rata in ritardo si conta il numero di giorni di\n"
                "  ritardo: se la rata e' stata pagata in ritardo, dalla scadenza\n"
                "  alla data del pagamento; se non e' ancora pagata e la scadenza\n"
                "  e' già passata, dalla scadenza ad oggi.\n"
                "• Le rate pagate puntualmente non contribuiscono.\n"
                "• Risultato: somma di tutti questi giorni su tutte le rate."
            ),
            "MEDIA RITARDO": (
                "Ritardo medio per rata\n\n"
                "• Stessa base di calcolo di TOT. GIORNI RITARDO: si analizzano le\n"
                "  rate del cliente nel periodo corrente.\n"
                "• Formula: TOT. GIORNI RITARDO ÷ numero di rate considerate,\n"
                "  per dare una misura 'per-rata' del comportamento di pagamento."
            ),
        }

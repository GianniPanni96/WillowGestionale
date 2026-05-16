"""
Base condivisa per i tooltip builder degli aggregati di lista.

Ogni builder e' un service "view-friendly" che produce
``dict[aggregate_key, tooltip_text]`` per il proprio dominio. Vive
fuori dalle classi view (MVC separation): la list view legge il dict
e applica i tooltip alle card aggregate, senza conoscere la logica di
calcolo.

I tooltip descrivono in linguaggio business *come* viene calcolato
ogni aggregato: quali item vengono retrieved, quali filtri vengono
applicati, eventuale distinzione lordo/netto/IVA. Lo stile e'
schematico ma non asciutto, ispirato ai tooltip della sezione TASSE
del dettaglio utente legacy.
"""

from __future__ import annotations


class AggregateTooltipBuilderBase:
    """
    Classe base. Le sottoclassi implementano ``build_tooltips`` (opzionalmente
    parametrico in base al ``toggle_value`` esposto dalla list view) e
    restituiscono un dict ``aggregate_key -> testo del tooltip``.
    """

    def build_tooltips(self, toggle_value: "str | None" = None) -> dict:
        """Override nelle sottoclassi."""
        return {}

    # ------------------------------------------------------------------
    # Helper di formattazione condivisi
    # ------------------------------------------------------------------

    @staticmethod
    def fmt_money(value) -> str:
        """Formattazione monetaria: 1.234,56 €."""
        try:
            n = float(value)
        except (TypeError, ValueError):
            return "0,00 €"
        s = f"{n:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")
        return f"{s} €"

    @staticmethod
    def fmt_int(value) -> str:
        try:
            return str(int(value))
        except (TypeError, ValueError):
            return "0"

    @staticmethod
    def fmt_hours(value) -> str:
        try:
            return f"{round(float(value), 2)} h"
        except (TypeError, ValueError):
            return "0 h"

    @staticmethod
    def fmt_rate(value) -> str:
        """Formattazione €/h."""
        try:
            return f"{round(float(value), 2)} €/h"
        except (TypeError, ValueError):
            return "0 €/h"

from datetime import datetime

from Gestionale_Enums import DBProductionsColumns


class ProductionWarningService:
    """
    Servizio dedicato alla costruzione dei warning per le liste produzione.

    Il servizio riceve item gia' recuperati dal query service e restituisce una
    mappa ``warning_key -> warning_text`` pronta per la view.
    """

    def collect_warnings_for_list(self, items_list):
        """
        Raccoglie i warning da mostrare sulle card produzione.

        Una produzione fuori dall'anno contabile corrente viene evidenziata
        quando resta visibile perche' collegata a fatture non interamente saldate.
        """
        warnings = {}

        for production in items_list:
            if not production:
                continue

            production_name = production[DBProductionsColumns.NAME.value]
            created_at = production.get(DBProductionsColumns.CREATED_AT.value)
            if not created_at:
                continue

            production_creation_date = None
            for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    production_creation_date = datetime.strptime(created_at, pattern)
                    break
                except ValueError:
                    continue

            if production_creation_date is None:
                continue

            if production_creation_date.year != datetime.now().year:
                warnings[production_name] = (
                    f"{production_name}\n\n"
                    f"Questa produzione riguarda l'anno contabile {production_creation_date.year}.\n"
                    "Stai visualizzando questa produzione perche' e' collegata ad una fattura non interamente "
                    "saldata durante il suo anno contabile di riferimento.\n"
                    "Questa produzione non viene conteggiata all'interno di questo anno contabile."
                )

        return warnings

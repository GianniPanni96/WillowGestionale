from datetime import datetime

from Gestionale_Enums import DBProductionsColumns, ProductionStatus
from WarningServices.Warning_types import WarningInfo, WarningSeverity


class ProductionWarningService:
    """
    Costruttore warning per le liste produzione.

    Trigger:
    - SEV 1: client_missing.
    - SEV 2: preventivo_overrun, closed_without_invoices.
    - SEV 3: previous_year.
    """

    PREVENTIVO_TOLERANCE = 0.01

    FK_FIELD_BY_TYPE = {
        "client_missing": DBProductionsColumns.CLIENT_ID.value,
    }

    def __init__(
        self,
        productions_query_service=None,
        productions_analyzer_service=None,
        clients_query_service=None,
    ):
        self.productions_query_service = productions_query_service
        self.productions_analyzer_service = productions_analyzer_service
        self.clients_query_service = clients_query_service

    def collect_warnings_for_list(self, items_list) -> dict[str, WarningInfo]:
        warnings: dict[str, WarningInfo] = {}

        for production in items_list:
            if not production:
                continue
            name = production[DBProductionsColumns.NAME.value]

            # SEV 1.
            sev1 = self._check_fk_consistency(production)
            if sev1 is not None:
                warnings[name] = sev1
                continue

            # SEV 3.
            previous = self._check_previous_year(production)
            if previous is not None:
                warnings[name] = previous
                continue

            # SEV 2.
            overrun = self._check_preventivo_overrun(production)
            if overrun is not None:
                warnings[name] = overrun
                continue
            closed = self._check_closed_without_invoices(production)
            if closed is not None:
                warnings[name] = closed

        return warnings

    # ------------------------------------------------------------------
    # SEV 1
    # ------------------------------------------------------------------

    def _check_fk_consistency(self, production) -> WarningInfo | None:
        cli_id = production.get(DBProductionsColumns.CLIENT_ID.value)
        if cli_id is None:
            return None
        if self.clients_query_service is None:
            return None
        if self.clients_query_service.retrieve_client_map_by_id(cli_id) is not None:
            return None
        return WarningInfo(
            type_key="client_missing",
            severity=WarningSeverity.CONSISTENCY,
            text=(
                f"{production.get(DBProductionsColumns.NAME.value, '')}\n\n"
                "Il cliente associato a questa produzione non esiste piu' nel database."
            ),
            broken_field_key=self.FK_FIELD_BY_TYPE["client_missing"],
        )

    # ------------------------------------------------------------------
    # SEV 2
    # ------------------------------------------------------------------

    def _check_preventivo_overrun(self, production) -> WarningInfo | None:
        if self.productions_analyzer_service is None:
            return None
        try:
            totale_preventivo = float(
                production.get(DBProductionsColumns.TOTALE_PREVENTIVO.value) or 0
            )
        except (TypeError, ValueError):
            return None
        if totale_preventivo <= 0:
            return None
        try:
            totale_fatturato = float(
                self.productions_analyzer_service
                    .calcola_totale_servizi_rimborsi_per_produzione(
                        production.get(DBProductionsColumns.ID.value)
                    ) or 0
            )
        except Exception:
            return None
        diff = round(totale_fatturato - totale_preventivo, 2)
        if diff <= self.PREVENTIVO_TOLERANCE:
            return None
        return WarningInfo(
            type_key="preventivo_overrun",
            severity=WarningSeverity.INCONSISTENCY,
            text=(
                "Incoerenza dato: la somma servizi+rimborsi delle fatture collegate\n"
                f"({round(totale_fatturato, 2)} €) supera il totale preventivo "
                f"({round(totale_preventivo, 2)} €).\n"
                f"Sforamento: {round(diff, 2)} €."
            ),
        )

    def _check_closed_without_invoices(self, production) -> WarningInfo | None:
        if self.productions_query_service is None:
            return None
        if production.get(DBProductionsColumns.STATO.value) != ProductionStatus.CLOSED.value:
            return None
        try:
            invoices = self.productions_query_service.retrieve_production_with_invoices_map_list(
                production.get(DBProductionsColumns.ID.value)
            ) or []
        except Exception:
            return None
        if invoices:
            return None
        return WarningInfo(
            type_key="closed_without_invoices",
            severity=WarningSeverity.INCONSISTENCY,
            text=(
                "Incoerenza dato: questa produzione e' in stato CLOSED ma\n"
                "non ha alcuna fattura collegata."
            ),
        )

    # ------------------------------------------------------------------
    # SEV 3
    # ------------------------------------------------------------------

    def _check_previous_year(self, production) -> WarningInfo | None:
        created_at = production.get(DBProductionsColumns.CREATED_AT.value)
        creation = self._parse_date(created_at)
        if creation is None or creation.year == datetime.now().year:
            return None
        return WarningInfo(
            type_key="previous_year",
            severity=WarningSeverity.INFO,
            text=(
                f"{production.get(DBProductionsColumns.NAME.value, '')}\n\n"
                f"Questa produzione riguarda l'anno contabile {creation.year}.\n"
                "Stai visualizzando questa produzione perche' e' collegata ad una fattura non "
                "interamente saldata durante il suo anno contabile di riferimento.\n"
                "Questa produzione non viene conteggiata all'interno di questo anno contabile."
            ),
        )

    @staticmethod
    def _parse_date(value):
        if not value:
            return None
        for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, pattern)
            except ValueError:
                continue
        return None

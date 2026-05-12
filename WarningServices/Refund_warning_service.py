from Gestionale_Enums import DBRefundsColumns
from WarningServices.Warning_types import WarningInfo, WarningSeverity


class RefundWarningService:
    """
    Costruttore warning per le liste rimborsi.

    Trigger:
    - SEV 1: client_missing, account_missing.
    """

    FK_FIELD_BY_TYPE = {
        "client_missing": DBRefundsColumns.CLIENT_ID.value,
        "account_missing": DBRefundsColumns.CONTO_ID.value,
    }

    def __init__(self, clients_query_service=None, accounts_query_service=None):
        self.clients_query_service = clients_query_service
        self.accounts_query_service = accounts_query_service

    def collect_warnings_for_list(self, items_list) -> dict[str, WarningInfo]:
        warnings: dict[str, WarningInfo] = {}

        for refund in items_list:
            if not refund:
                continue
            name = refund.get(DBRefundsColumns.REFUND_NAME.value)
            if not name:
                continue
            info = self._check_fk_consistency(refund)
            if info is not None:
                warnings[name] = info

        return warnings

    def _check_fk_consistency(self, refund) -> WarningInfo | None:
        client_id = refund.get(DBRefundsColumns.CLIENT_ID.value)
        if not client_id:
            return self._fk(
                "client_missing",
                "Il rimborso non ha un cliente associato.\n"
                "Collegare il rimborso a un cliente valido.",
            )
        if self.clients_query_service is not None and (
            self.clients_query_service.retrieve_client_map_by_id(client_id) is None
        ):
            return self._fk(
                "client_missing",
                "Il cliente associato a questo rimborso non esiste piu' nel database.",
            )

        acc_id = refund.get(DBRefundsColumns.CONTO_ID.value)
        if acc_id and self.accounts_query_service is not None and (
            self.accounts_query_service.retrieve_account_map_by_id(acc_id) is None
        ):
            return self._fk(
                "account_missing",
                "Il conto associato a questo rimborso non esiste piu' nel database.",
            )
        return None

    def _fk(self, type_key: str, text: str) -> WarningInfo:
        return WarningInfo(
            type_key=type_key,
            severity=WarningSeverity.CONSISTENCY,
            text=text,
            broken_field_key=self.FK_FIELD_BY_TYPE.get(type_key),
        )

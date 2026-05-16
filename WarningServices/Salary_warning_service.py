from datetime import datetime

from Gestionale_Enums import DBSalariesColumns
from WarningServices.Warning_types import WarningInfo, WarningSeverity


class SalaryWarningService:
    """
    Costruttore warning per le liste salari.

    Trigger:
    - SEV 1: user_missing, account_missing.
    - SEV 2: monthly_duplicate.
    """

    FK_FIELD_BY_TYPE = {
        "user_missing": DBSalariesColumns.USER_ID.value,
        "account_missing": DBSalariesColumns.ACCOUNT_ID.value,
    }

    def __init__(self, salary_query_service=None, user_query_service=None, accounts_query_service=None):
        self.salary_query_service = salary_query_service
        self.user_query_service = user_query_service
        self.accounts_query_service = accounts_query_service

    def collect_warnings_for_list(self, items_list) -> dict[str, WarningInfo]:
        warnings: dict[str, WarningInfo] = {}
        if not items_list:
            return warnings

        # Pre-calcolo bucket per il doppione mensile (vedi dettagli sotto).
        all_salaries = self._fetch_all_salaries()
        bucket_count = self._build_bucket_count(all_salaries)

        for salary in items_list:
            if not salary:
                continue
            name = salary.get(DBSalariesColumns.NAME.value)
            if not name:
                continue

            # SEV 1.
            sev1 = self._check_fk_consistency(salary)
            if sev1 is not None:
                warnings[name] = sev1
                continue

            # SEV 2.
            bucket = self._bucket_for(salary)
            if bucket is not None and bucket_count.get(bucket, 0) >= 2:
                warnings[name] = WarningInfo(
                    type_key="monthly_duplicate",
                    severity=WarningSeverity.INCONSISTENCY,
                    text=(
                        "Incoerenza dato: per questo utente risultano registrati\n"
                        "due o piu' salari nello stesso mese.\n"
                        "Verifica che non si tratti di un inserimento duplicato."
                    ),
                )

        return warnings

    # ------------------------------------------------------------------
    # SEV 1
    # ------------------------------------------------------------------

    def _check_fk_consistency(self, salary) -> WarningInfo | None:
        user_id = salary.get(DBSalariesColumns.USER_ID.value)
        if user_id and self.user_query_service is not None and (
            self.user_query_service.retrieve_user_map_by_id(user_id) is None
        ):
            return self._fk(
                "user_missing",
                "L'utente associato a questo stipendio non esiste piu' nel database.",
            )
        acc_id = salary.get(DBSalariesColumns.ACCOUNT_ID.value)
        if acc_id and self.accounts_query_service is not None and (
            self.accounts_query_service.retrieve_account_map_by_id(acc_id) is None
        ):
            return self._fk(
                "account_missing",
                "Il conto associato a questo stipendio non esiste piu' nel database.",
            )
        return None

    def _fk(self, type_key: str, text: str) -> WarningInfo:
        return WarningInfo(
            type_key=type_key,
            severity=WarningSeverity.CONSISTENCY,
            text=text,
            broken_field_key=self.FK_FIELD_BY_TYPE.get(type_key),
        )

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _fetch_all_salaries(self):
        if self.salary_query_service is None:
            return []
        try:
            return self.salary_query_service.retrieve_salaries_map_list(year=-1) or []
        except Exception:
            return []

    def _build_bucket_count(self, salaries):
        counts: dict = {}
        for salary in salaries:
            bucket = self._bucket_for(salary)
            if bucket is None:
                continue
            counts[bucket] = counts.get(bucket, 0) + 1
        return counts

    @staticmethod
    def _bucket_for(salary):
        user_id = salary.get(DBSalariesColumns.USER_ID.value)
        date_str = salary.get(DBSalariesColumns.DATE.value)
        if not user_id or not date_str:
            return None
        for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                d = datetime.strptime(date_str, pattern)
                return (user_id, d.year, d.month)
            except ValueError:
                continue
        return None

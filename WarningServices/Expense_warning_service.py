from Gestionale_Enums import DBExpensesColumns
from WarningServices.Warning_types import WarningInfo, WarningSeverity


class ExpenseWarningService:
    """
    Costruttore warning per le liste spese.

    Trigger:
    - SEV 1: supplier_missing, account_missing, user_deduzione_missing,
      user_anticipo_missing, linked_invoice_missing.
    - SEV 2: production_without_invoice, amount_mismatch,
      deducibile_without_user.
    """

    AMOUNT_TOLERANCE = 0.01

    FK_FIELD_BY_TYPE = {
        "supplier_missing": DBExpensesColumns.SUPPLIER_ID.value,
        "account_missing": DBExpensesColumns.ACCOUNT_ID.value,
        "user_deduzione_missing": DBExpensesColumns.USER_ID_DEDUZIONE.value,
        "user_anticipo_missing": DBExpensesColumns.USER_ID_ANTICIPO.value,
        "linked_invoice_missing": DBExpensesColumns.LINKED_INVOICE_ID.value,
    }

    def __init__(
        self,
        catalogo_elenchi=None,
        suppliers_query_service=None,
        accounts_query_service=None,
        user_query_service=None,
        invoices_query_service=None,
    ):
        self._production_expense_value = None
        if catalogo_elenchi is not None:
            try:
                self._production_expense_value = dict(
                    catalogo_elenchi.get("expenses_category", [])
                ).get("PRODUCTION_EXPENSE")
            except Exception:
                self._production_expense_value = None
        self.suppliers_query_service = suppliers_query_service
        self.accounts_query_service = accounts_query_service
        self.user_query_service = user_query_service
        self.invoices_query_service = invoices_query_service

    def collect_warnings_for_list(self, items_list) -> dict[str, WarningInfo]:
        warnings: dict[str, WarningInfo] = {}

        for expense in items_list:
            if not expense:
                continue
            name = expense.get(DBExpensesColumns.NAME.value)
            if not name:
                continue

            sev1 = self._check_fk_consistency(expense)
            if sev1 is not None:
                warnings[name] = sev1
                continue

            info = (
                self._check_production_without_invoice(expense)
                or self._check_amount_mismatch(expense)
                or self._check_deducibile_without_user(expense)
            )
            if info is not None:
                warnings[name] = info

        return warnings

    # ------------------------------------------------------------------
    # SEV 1
    # ------------------------------------------------------------------

    def _check_fk_consistency(self, expense) -> WarningInfo | None:
        sup_id = expense.get(DBExpensesColumns.SUPPLIER_ID.value)
        if sup_id and self.suppliers_query_service is not None and (
            self.suppliers_query_service.retrieve_supplier_map_by_id(sup_id) is None
        ):
            return self._fk("supplier_missing", "Il fornitore associato a questa spesa non esiste piu' nel database.")
        acc_id = expense.get(DBExpensesColumns.ACCOUNT_ID.value)
        if acc_id and self.accounts_query_service is not None and (
            self.accounts_query_service.retrieve_account_map_by_id(acc_id) is None
        ):
            return self._fk("account_missing", "Il conto associato a questa spesa non esiste piu' nel database.")
        ded_id = expense.get(DBExpensesColumns.USER_ID_DEDUZIONE.value)
        if ded_id and self.user_query_service is not None and (
            self.user_query_service.retrieve_user_map_by_id(ded_id) is None
        ):
            return self._fk("user_deduzione_missing", "L'utente di deduzione indicato non esiste piu' nel database.")
        ant_id = expense.get(DBExpensesColumns.USER_ID_ANTICIPO.value)
        if ant_id and self.user_query_service is not None and (
            self.user_query_service.retrieve_user_map_by_id(ant_id) is None
        ):
            return self._fk("user_anticipo_missing", "L'utente che ha anticipato la spesa non esiste piu' nel database.")
        inv_id = expense.get(DBExpensesColumns.LINKED_INVOICE_ID.value)
        if inv_id and self.invoices_query_service is not None and (
            self.invoices_query_service.retrieve_invoice_map_by_id(inv_id) is None
        ):
            return self._fk("linked_invoice_missing", "La fattura collegata a questa spesa non esiste piu' nel database.")
        return None

    def _fk(self, type_key: str, text: str) -> WarningInfo:
        return WarningInfo(
            type_key=type_key,
            severity=WarningSeverity.CONSISTENCY,
            text=text,
            broken_field_key=self.FK_FIELD_BY_TYPE.get(type_key),
        )

    # ------------------------------------------------------------------
    # SEV 2
    # ------------------------------------------------------------------

    def _check_production_without_invoice(self, expense) -> WarningInfo | None:
        if not self._production_expense_value:
            return None
        if expense.get(DBExpensesColumns.CATEGORY.value) != self._production_expense_value:
            return None
        if expense.get(DBExpensesColumns.LINKED_INVOICE_ID.value):
            return None
        return WarningInfo(
            type_key="production_without_invoice",
            severity=WarningSeverity.INCONSISTENCY,
            text=(
                "Incoerenza dato: la spesa e' categorizzata come\n"
                "\"Spesa di produzione\" ma non e' collegata ad alcuna fattura."
            ),
        )

    def _check_amount_mismatch(self, expense) -> WarningInfo | None:
        try:
            netto = float(expense.get(DBExpensesColumns.NET_AMOUNT.value) or 0)
            iva = float(expense.get(DBExpensesColumns.IVA_AMOUNT.value) or 0)
            lordo = float(expense.get(DBExpensesColumns.TOT_AMOUNT.value) or 0)
        except (TypeError, ValueError):
            return None
        if lordo == 0 and netto == 0 and iva == 0:
            return None
        if abs(round(netto + iva - lordo, 2)) <= self.AMOUNT_TOLERANCE:
            return None
        return WarningInfo(
            type_key="amount_mismatch",
            severity=WarningSeverity.INCONSISTENCY,
            text=(
                "Incoerenza dato: la somma di importo netto + IVA "
                f"({round(netto + iva, 2)} €) non corrisponde all'importo lordo "
                f"({round(lordo, 2)} €)."
            ),
        )

    def _check_deducibile_without_user(self, expense) -> WarningInfo | None:
        if str(expense.get(DBExpensesColumns.DEDUCIBILE.value) or "").strip().lower() != "si":
            return None
        if expense.get(DBExpensesColumns.USER_ID_DEDUZIONE.value):
            return None
        return WarningInfo(
            type_key="deducibile_without_user",
            severity=WarningSeverity.INCONSISTENCY,
            text=(
                "Incoerenza dato: la spesa e' marcata come deducibile ma\n"
                "non e' indicato l'utente a cui imputare la deduzione."
            ),
        )

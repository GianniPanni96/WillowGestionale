from collections import defaultdict
from datetime import datetime

from Gestionale_Enums import (
    DBClientsColumns,
    DBExpensesColumns,
    DBInvoicesColumns,
    DBProductionsColumns,
    DBSuppliersColumns,
)
from QueryServices.Clients_query_service import ClientQueryService
from QueryServices.Expenses_query_service import ExpenseQueryService
from QueryServices.Invoices_query_service import InvoiceQueryService
from QueryServices.Productions_query_service import ProductionQueryService
from QueryServices.Suppliers_query_service import SupplierQueryService
from Utils.Controller_utils import ControllerUtils


class ReportBreakdownAnalyzerService:
    """
    Aggrega i dati annuali necessari alla reportistica grafica.

    La view riceve dati gia' pronti per i grafici, senza doversi occupare di
    collegare manualmente fatture, produzioni, clienti e spese.
    """

    def __init__(
        self,
        invoices_query_service: InvoiceQueryService,
        productions_query_service: ProductionQueryService,
        clients_query_service: ClientQueryService,
        expenses_query_service: ExpenseQueryService,
        suppliers_query_service: SupplierQueryService,
    ):
        self.invoices_query_service = invoices_query_service
        self.productions_query_service = productions_query_service
        self.clients_query_service = clients_query_service
        self.expenses_query_service = expenses_query_service
        self.suppliers_query_service = suppliers_query_service

    def retrieve_annual_breakdown_data(self, year: int = None) -> dict:
        target_year = year if year is not None else datetime.now().year

        productions_by_id = {
            production[DBProductionsColumns.ID.value]: production
            for production in self.productions_query_service.retrieve_productions_map_list(year=-1)
        }
        clients_by_id = {
            client[DBClientsColumns.ID.value]: client
            for client in self.clients_query_service.retrieve_clients_map_list()
        }
        suppliers_by_id = {
            supplier[DBSuppliersColumns.ID.value]: supplier
            for supplier in self.suppliers_query_service.retrieve_suppliers_map_list(year=-1)
        }

        return {
            "year": target_year,
            "revenue": self._aggregate_revenue_breakdowns(
                year=target_year,
                productions_by_id=productions_by_id,
                clients_by_id=clients_by_id,
            ),
            "expenses": self._aggregate_expense_breakdowns(
                year=target_year,
                suppliers_by_id=suppliers_by_id,
            ),
        }

    def _aggregate_revenue_breakdowns(
        self,
        year: int,
        productions_by_id: dict,
        clients_by_id: dict,
    ) -> dict:
        revenue_by_production_type = defaultdict(float)
        revenue_by_output_type = defaultdict(float)
        revenue_by_client_sector = defaultdict(float)

        invoices = self.invoices_query_service.retrieve_invoices_map_list(
            year=year,
            include_unpaid_invoices=False,
        )
        invoices = ControllerUtils.clear_invoices_list_from_NDC_and_stornate(invoices)

        for invoice in invoices:
            invoice_amount = self._calculate_invoice_revenue(invoice)
            if invoice_amount <= 0:
                continue

            production = productions_by_id.get(invoice.get(DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value))

            production_type = self._safe_label(
                production.get(DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value) if production else None,
                "Produzione non associata",
            )
            output_type = self._safe_label(
                production.get(DBProductionsColumns.TIPOLOGIA_OUTPUT.value) if production else None,
                "Output non associato",
            )

            client = None
            if production:
                client = clients_by_id.get(production.get(DBProductionsColumns.CLIENT_ID.value))

            client_sector = self._safe_label(
                client.get(DBClientsColumns.SETTORE.value) if client else None,
                "Settore non associato",
            )

            revenue_by_production_type[production_type] += invoice_amount
            revenue_by_output_type[output_type] += invoice_amount
            revenue_by_client_sector[client_sector] += invoice_amount

        return {
            "by_production_type": self._sorted_items(revenue_by_production_type),
            "by_output_type": self._sorted_items(revenue_by_output_type),
            "by_client_sector": self._sorted_items(revenue_by_client_sector),
        }

    def _aggregate_expense_breakdowns(self, year: int, suppliers_by_id: dict) -> dict:
        expense_by_category = defaultdict(float)
        expense_by_supplier = defaultdict(float)
        expense_by_deductibility = defaultdict(float)

        expenses = self.expenses_query_service.retrieve_expenses_map_list(year=year)

        for expense in expenses:
            total_amount = self._to_float(expense.get(DBExpensesColumns.TOT_AMOUNT.value))
            if total_amount <= 0:
                continue

            category = self._safe_label(
                expense.get(DBExpensesColumns.CATEGORY.value),
                "Categoria non indicata",
            )

            supplier = suppliers_by_id.get(expense.get(DBExpensesColumns.SUPPLIER_ID.value))
            supplier_name = self._safe_label(
                supplier.get(DBSuppliersColumns.NAME.value) if supplier else None,
                "Fornitore non associato",
            )

            deductible_label = (
                "Deducibile"
                if self._is_deductible(expense.get(DBExpensesColumns.DEDUCIBILE.value))
                else "Non deducibile"
            )

            expense_by_category[category] += total_amount
            expense_by_supplier[supplier_name] += total_amount
            expense_by_deductibility[deductible_label] += total_amount

        return {
            "by_category": self._sorted_items(expense_by_category),
            "by_supplier": self._sorted_items(expense_by_supplier),
            "by_deductibility": self._sorted_items(expense_by_deductibility),
        }

    @staticmethod
    def _calculate_invoice_revenue(invoice: dict) -> float:
        total_document = ReportBreakdownAnalyzerService._to_float(
            invoice.get(DBInvoicesColumns.TOT_DOCUMENTO.value)
        )
        iva_amount = ReportBreakdownAnalyzerService._to_float(invoice.get(DBInvoicesColumns.IVA.value))
        return max(0.0, total_document - iva_amount)

    @staticmethod
    def _is_deductible(value) -> bool:
        if isinstance(value, bool):
            return value

        normalized = str(value or "").strip().lower()
        normalized = normalized.replace("ì", "i").replace("í", "i")
        return normalized in {"si", "true", "1", "yes"}

    @staticmethod
    def _safe_label(value, fallback: str) -> str:
        normalized = str(value).strip() if value is not None else ""
        return normalized or fallback

    @staticmethod
    def _sorted_items(values_map: dict) -> list[dict]:
        return [
            {"label": label, "value": round(value, 2)}
            for label, value in sorted(values_map.items(), key=lambda item: item[1], reverse=True)
            if value > 0
        ]

    @staticmethod
    def _to_float(value) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

from collections import defaultdict
from datetime import datetime

from Gestionale_Enums import (
    DBClientsColumns,
    DBExpensesColumns,
    DBInvoicesColumns,
    DBProductionsColumns,
    DBSuppliersColumns,
    DBSalariesColumns,
    DBRefundsColumns,
    DBPaymentsColumns,
)
from AnalyzerServices.Account_analyzer_service import AccountAnalyzerService
from QueryServices.Account_query_service import AccountQueryService
from QueryServices.Clients_query_service import ClientQueryService
from QueryServices.Expenses_query_service import ExpenseQueryService
from QueryServices.Invoices_query_service import InvoiceQueryService
from QueryServices.Productions_query_service import ProductionQueryService
from QueryServices.Suppliers_query_service import SupplierQueryService
from QueryServices.Salaries_query_service import SalaryQueryService
from QueryServices.Refunds_query_service import RefundQueryService
from Utils.Controller_utils import ControllerUtils


class ReportBreakdownAnalyzerService:
    """
    Aggrega i dati annuali necessari alla reportistica grafica.
    """

    def __init__(
        self,
        invoices_query_service: InvoiceQueryService,
        productions_query_service: ProductionQueryService,
        clients_query_service: ClientQueryService,
        expenses_query_service: ExpenseQueryService,
        suppliers_query_service: SupplierQueryService,
        salaries_query_service: SalaryQueryService,
        refunds_query_service: RefundQueryService,
        account_query_service: AccountQueryService,
        account_analyzer_service: AccountAnalyzerService,
    ):
        self.invoices_query_service = invoices_query_service
        self.productions_query_service = productions_query_service
        self.clients_query_service = clients_query_service
        self.expenses_query_service = expenses_query_service
        self.suppliers_query_service = suppliers_query_service
        self.salaries_query_service = salaries_query_service
        self.refunds_query_service = refunds_query_service
        self.account_query_service = account_query_service
        self.account_analyzer_service = account_analyzer_service

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

        revenue_data = self._aggregate_revenue_breakdowns(
            year=target_year,
            productions_by_id=productions_by_id,
            clients_by_id=clients_by_id,
        )
        expense_data = self._aggregate_expense_breakdowns(
            year=target_year,
            suppliers_by_id=suppliers_by_id,
        )

        # Calcolo Rapporto Spese/Fatturato per il nuovo chart
        total_revenue = sum(item["value"] for item in revenue_data["by_production_type"])
        # Nota: _aggregate_expense_breakdowns usa TOT_AMOUNT, ma per il confronto IVA esclusa 
        # dovremmo usare NET_AMOUNT o scorporare. Uso il NET_AMOUNT per coerenza con la richiesta.
        expenses_raw = self.expenses_query_service.retrieve_expenses_map_list(year=target_year)
        total_net_expenses = sum(self._to_float(exp.get(DBExpensesColumns.NET_AMOUNT.value)) for exp in expenses_raw)
        #TODO: togliere le spese legate a iva e tasse dal calcolo delle spese

        expense_vs_revenue = []
        if total_revenue > 0:
            remaining = max(0, total_revenue - total_net_expenses)
            expense_vs_revenue = [
                {"label": "Spese Totali (Netto IVA)", "value": round(total_net_expenses, 2)},
                {"label": "Utile Netto", "value": round(remaining, 2)},
            ]

        return {
            "year": target_year,
            "revenue": revenue_data,
            "expenses": expense_data,
            "expense_vs_revenue": expense_vs_revenue,
            "financial": self.retrieve_financial_breakdown(year=target_year),
        }

    def retrieve_financial_breakdown(self, year: int = None) -> dict:
        """
        Prepara i dati per i 3 grafici a torta finanziari:
        - Patrimonio: Distribuzione tra conti (Saldi calcolati runtime)
        - Entrate: Fatturato vs Rimborsi
        - Uscite: IVA vs Salari vs Spese Operative
        """
        target_year = year if year is not None else datetime.now().year

        # 1. Patrimonio (Suddivisione tra conti correnti calcolata tramite Analyzer)
        accounts = self.account_query_service.retrieve_accounts_map_list()
        patrimonio_data = []
        
        for acc in accounts:
            account_id = acc.get("ID")
            # Calcoliamo il saldo reale usando l'analyzer
            balance_value = self.account_analyzer_service.calculate_account_balance_by_account_id(account_id, year=target_year)
            
            if balance_value > 0:
                patrimonio_data.append({
                    "label": acc.get("NAME", f"Conto {account_id}"),
                    "value": round(balance_value, 2)
                })

        # 2. Entrate (Fatturato vs Rimborsi)
        invoices = self.invoices_query_service.retrieve_invoices_map_list(year=target_year, include_unpaid_invoices=False)
        invoices = ControllerUtils.clear_invoices_list_from_NDC_and_stornate(invoices)
        total_revenue = sum(self._calculate_invoice_revenue(inv) for inv in invoices)
        
        refunds = self.refunds_query_service.retrieve_refunds_map_list(year=target_year)
        total_refunds = sum(self._to_float(ref.get(DBRefundsColumns.REFUND_AMOUNT.value)) for ref in refunds)

        entrate_data = [
            {"label": "Fatturato (Netto IVA)", "value": round(total_revenue, 2)},
            {"label": "Rimborsi", "value": round(total_refunds, 2)},
        ]

        # 3. Uscite (IVA vs Salari vs Spese Operative)
        total_iva = sum(self._to_float(inv.get(DBInvoicesColumns.IVA.value)) for inv in invoices)
        
        salaries = self.salaries_query_service.retrieve_salaries_map_list(year=target_year)
        total_salaries = sum(self._to_float(sal.get(DBSalariesColumns.AMOUNT.value)) for sal in salaries)
        
        expenses = self.expenses_query_service.retrieve_expenses_map_list(year=target_year)
        total_expenses = sum(self._to_float(exp.get(DBExpensesColumns.TOT_AMOUNT.value)) for exp in expenses)

        uscite_data = [
            {"label": "IVA versata", "value": round(total_iva, 2)},
            {"label": "Costi Personale", "value": round(total_salaries, 2)},
            {"label": "Spese Operative", "value": round(total_expenses, 2)},
        ]

        return {
            "patrimonio": patrimonio_data,
            "entrate": entrate_data,
            "uscite": uscite_data
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

        # 1. Recupero pagamenti per calcolo Crediti VS Incassato
        all_payments = self.invoices_query_service.db_model.fetch_payments()
        payments_by_invoice = {}
        for p in all_payments:
            p_map = ControllerUtils.row_to_map(p, DBPaymentsColumns)
            inv_id = p_map[DBPaymentsColumns.INVOICE_ID.value]
            payments_by_invoice.setdefault(inv_id, []).append(p_map)

        total_collected = 0.0
        total_credits = 0.0

        for invoice in invoices:
            invoice_amount = self._calculate_invoice_revenue(invoice)
            if invoice_amount <= 0:
                continue

            # Calcolo Crediti VS Incassato per la singola fattura
            invoice_id = invoice.get(DBInvoicesColumns.ID.value)
            num_rate = int(invoice.get(DBInvoicesColumns.NUMERO_RATE.value) or 1)
            payments = payments_by_invoice.get(invoice_id, [])
            paid_rates = {p.get(DBPaymentsColumns.LINKED_RATA.value) for p in payments}

            if num_rate == 1:
                if 1 in paid_rates:
                    total_collected += invoice_amount
                else:
                    total_credits += invoice_amount
            else:
                # Distribuzione proporzionale dell'imponibile sulle rate
                amount_per_rata = invoice_amount / num_rate
                for r in range(1, num_rate + 1):
                    if r in paid_rates:
                        total_collected += amount_per_rata
                    else:
                        total_credits += amount_per_rata

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
            "credits_vs_cached": [
                {"label": "Incassato", "value": round(total_collected, 2)},
                {"label": "Crediti", "value": round(total_credits, 2)},
            ]
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

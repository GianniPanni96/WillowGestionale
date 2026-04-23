from datetime import datetime

from Gestionale_Enums import*
from QueryServices.Expenses_query_service import ExpenseQueryService
from QueryServices.Invoices_query_service import InvoiceQueryService
from QueryServices.Payments_query_service import PaymentQueryService
from QueryServices.Refunds_query_service import RefundQueryService
from QueryServices.Salaries_query_service import SalaryQueryService

class MonthlyReportAnalyzerService:
    def __init__(self,
                 invoices_query_service:InvoiceQueryService,
                 payments_query_service:PaymentQueryService,
                 expenses_query_service:ExpenseQueryService,
                 salary_query_service:SalaryQueryService,
                 refunds_query_service:RefundQueryService):

        self.invoices_query_service:InvoiceQueryService = invoices_query_service
        self.payments_query_service:PaymentQueryService = payments_query_service
        self.expenses_query_service: ExpenseQueryService = expenses_query_service
        self.salary_query_service: SalaryQueryService = salary_query_service
        self.refunds_query_service: RefundQueryService = refunds_query_service

    def retrieve_monthly_data(self, year: int = None):
        # Recupera i dati per l'anno corrente
        invoices = self.invoices_query_service.retrieve_invoices_map_list(year = year, include_unpaid_invoices = False)
        payments = self.payments_query_service.retrieve_payments_map_list(year = year, include_unpaid_invoice_payments= False)
        expenses = self.expenses_query_service.retrieve_expenses_map_list(year=year)
        salaries = self.salary_query_service.retrieve_salaries_map_list(year = year)
        refunds = self.refunds_query_service.retrieve_refunds_map_list(year = year)

        # Inizializza la struttura per i dati mensili
        monthly_data = {month: {
            'fatturato': 0.0,
            'spese': 0.0,
            'incomes': 0.0,
            'outcomes': 0.0
        } for month in range(1, 13)}

        # Funzione di supporto per estrarre il mese dalle date
        def extract_month(date_str):
            if isinstance(date_str, datetime):
                return date_str.month
            try:
                return datetime.strptime(date_str, "%Y-%m-%d").month
            except:
                return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").month

        # 1. Calcola il fatturato (TOT_DOCUMENTO - IVA)
        for inv in invoices:
            month = extract_month(inv[DBInvoicesColumns.DATA_CREAZIONE.value])
            tot_doc = float(inv[DBInvoicesColumns.TOT_DOCUMENTO.value])
            iva = float(inv[DBInvoicesColumns.IVA.value])
            monthly_data[month]['fatturato'] += (tot_doc - iva)

        # 2. Calcola le spese (NET_AMOUNT)
        for exp in expenses:
            month = extract_month(exp[DBExpensesColumns.DATE.value])
            monthly_data[month]['spese'] += float(exp[DBExpensesColumns.NET_AMOUNT.value])

        # 3. Calcola gli incomes (NETTO_A_PAGARE + REFUND_AMOUNT)
        for pay in payments:
            month = extract_month(pay[DBPaymentsColumns.PAYMENT_DATE.value])
            monthly_data[month]['incomes'] += float(pay[DBPaymentsColumns.PAYMENT_AMOUNT.value])

        for ref in refunds:
            month = extract_month(ref[DBRefundsColumns.REFUND_DATE.value])
            monthly_data[month]['incomes'] += float(ref[DBRefundsColumns.REFUND_AMOUNT.value])

        # 4. Calcola gli outcomes (NET_AMOUNT + AMOUNT)
        for exp in expenses:
            month = extract_month(exp[DBExpensesColumns.DATE.value])
            monthly_data[month]['outcomes'] += float(exp[DBExpensesColumns.NET_AMOUNT.value])

        for sal in salaries:
            month = extract_month(sal[DBSalariesColumns.DATE.value])
            monthly_data[month]['outcomes'] += float(sal[DBSalariesColumns.AMOUNT.value])

        # Calcola le medie mensili (solo per i mesi passati se la funzione è chiamata per retrievare i dati dell'esercizio corrente, altrimenti di tutti i mesi)
        if year == datetime.now().year or year is None:
            current_month = datetime.now().month
        else:
            current_month = 12

        passed_months = [m for m in range(1, current_month + 1)]

        # Calcola i totali per i mesi passati
        totals = {k: 0.0 for k in ['fatturato', 'spese', 'incomes', 'outcomes']}
        for month in passed_months:
            for key in totals:
                totals[key] += monthly_data[month][key]

        # Calcola le medie
        averages = {
            key: (totals[key] / len(passed_months)) if passed_months else 0.0
            for key in totals
        }

        # Costruisci il risultato finale con deviazioni
        result = {}
        for month in range(1, 13):
            month_data = monthly_data[month]
            deviations = {}

            if month in passed_months:
                for key, value in month_data.items():
                    avg = averages[key]
                    if avg != 0:
                        deviations[key] = round(((value - avg) / avg) * 100, 2)
                    else:
                        deviations[key] = 0.0
            else:
                deviations = {k: None for k in month_data}

            result[month] = {
                'values': {k: round(v, 2) for k, v in month_data.items()},
                'averages': {k: round(v, 2) for k, v in averages.items()},
                'deviations': deviations
            }

        return result



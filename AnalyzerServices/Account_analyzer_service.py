from datetime import datetime

from AnalyzerServices.Expense_analyzer_service import ExpenseAnalyzerService
from AnalyzerServices.Payment_analyzer_service import PaymentAnalyzerService
from AnalyzerServices.Refund_analyzer_service import RefundAnalyzerService
from AnalyzerServices.Salary_analyzer_service import SalaryAnalyzerService
from AnalyzerServices.Transfer_analyzer_service import TransferAnalyzerService
from Gestionale_Enums import*
from QueryServices.Account_query_service import AccountQueryService
from QueryServices.Expenses_query_service import ExpenseQueryService
from QueryServices.Payments_query_service import PaymentQueryService
from QueryServices.Refunds_query_service import RefundQueryService
from QueryServices.Salaries_query_service import SalaryQueryService
from QueryServices.Transfers_query_service import TransferQueryService
from QueryServices.Users_query_service import UserQueryService
from Utils.Controller_utils import ControllerUtils


class AccountAnalyzerService:
    def __init__(self, account_query_service: AccountQueryService,
                 user_query_service: UserQueryService,
                 payment_analyzer_service: PaymentAnalyzerService,
                 payment_query_service: PaymentQueryService,
                 expenses_analyzer_service: ExpenseAnalyzerService,
                 expenses_query_service:ExpenseQueryService,
                 transfer_analyzer_service: TransferAnalyzerService,
                 transfer_query_service: TransferQueryService,
                 salary_analyzer_service: SalaryAnalyzerService,
                 salary_query_service:SalaryQueryService,
                 refund_analyzer_service: RefundAnalyzerService,
                 refunds_query_service:RefundQueryService):
        self.account_query_service:AccountQueryService = account_query_service
        self.user_query_service:UserQueryService = user_query_service
        self.payments_analyzer_service:PaymentAnalyzerService = payment_analyzer_service
        self.payments_query_service:PaymentQueryService = payment_query_service
        self.expenses_analyzer_service:ExpenseAnalyzerService = expenses_analyzer_service
        self.expenses_query_service:ExpenseQueryService = expenses_query_service
        self.transfer_analyzer_service:TransferAnalyzerService = transfer_analyzer_service
        self.transfer_query_service:TransferQueryService = transfer_query_service
        self.salary_analyzer_service:SalaryAnalyzerService = salary_analyzer_service
        self.salary_query_service:SalaryQueryService = salary_query_service
        self.refunds_analyzer_service:RefundAnalyzerService = refund_analyzer_service
        self.refunds_query_service:RefundQueryService = refunds_query_service

    def count_accounts(self):
        return len(self.account_query_service.retrieve_accounts_map_list())

    def calculate_account_balance_by_account_id(self, account_id, year:int = None, init_balance_arg:str = ""):
        account = self.account_query_service.retrieve_account_map_by_id(account_id)
        balance = 0.0
        if account:
            init_balance = float(account[DBAccountsColumns.INIT_BALANCE.value]) if init_balance_arg == "" else float(init_balance_arg)

            tot_payments = self.payments_analyzer_service.sum_payments_for_account(account_id, year = year)
            tot_expenses = self.expenses_analyzer_service.sum_expenses_for_account(account_id, year=year)
            tot_rec_transf = self.transfer_analyzer_service.calculate_tot_amount_received_transfers_by_account(account_id, year = year)
            tot_sent_transf = self.transfer_analyzer_service.calculate_tot_amount_sent_transfers_by_account(account_id, year = year)
            tot_salaries = self.salary_analyzer_service.sum_salaries_for_account(account_id, year = year)
            tot_refunds = self.refunds_analyzer_service.sum_refunds_for_account(account_id, year = year)

            tot_entrate = tot_payments + tot_rec_transf + tot_refunds
            tot_uscite = tot_expenses + tot_sent_transf + tot_salaries

            balance = init_balance + float(tot_entrate) - float(tot_uscite)

        return balance

    def retrieve_account_movements_by_account_id(self, account_id, year:int = None):
        movements = []

        # Payments (+) - Entrate
        payments = self.payments_query_service.retrieve_payments_map_list(year = year, include_unpaid_invoice_payments = False)
        filtered_payments = [p for p in payments if p[DBPaymentsColumns.CONTO_ID.value] == account_id]
        for payment in filtered_payments:
            movements.append({
                "id": payment[DBPaymentsColumns.ID.value],
                "kind": "payment",
                "name": payment[DBPaymentsColumns.PAYMENT_NAME.value],
                "date": payment[DBPaymentsColumns.PAYMENT_DATE.value],
                "amount": float(payment[DBPaymentsColumns.PAYMENT_AMOUNT.value]),
                "type": "Pagamento",
                "sign": "+"
            })

        # Refunds (+) - Entrate
        refunds = self.refunds_query_service.retrieve_refunds_map_list(year = year)
        filtered_refunds = [r for r in refunds if r[DBRefundsColumns.CONTO_ID.value] == account_id]
        for refund in filtered_refunds:
            movements.append({
                "id": refund[DBRefundsColumns.ID.value],
                "kind": "refund",
                "name": refund[DBRefundsColumns.REFUND_NAME.value],
                "date": refund[DBRefundsColumns.REFUND_DATE.value],
                "amount": float(refund[DBRefundsColumns.REFUND_AMOUNT.value]),
                "type": "Rimborso",
                "sign": "+"
            })

        # Expenses (-) - Uscite
        expenses = self.expenses_query_service.retrieve_expenses_map_list(year=year)
        filtered_expenses = [e for e in expenses if e[DBExpensesColumns.ACCOUNT_ID.value] == account_id]
        for expense in filtered_expenses:
            movements.append({
                "id": expense[DBExpensesColumns.ID.value],
                "kind": "expense",
                "name": expense[DBExpensesColumns.NAME.value],
                "date": expense[DBExpensesColumns.DATE.value],
                "amount": float(expense[DBExpensesColumns.TOT_AMOUNT.value]),
                "type": "Spesa",
                "sign": "-"
            })

        # Salaries (-) - Uscite
        salaries = self.salary_query_service.retrieve_salaries_map_list(year = year)
        filtered_salaries = [s for s in salaries if s[DBSalariesColumns.ACCOUNT_ID.value] == account_id]
        for salary in filtered_salaries:
            movements.append({
                "id": salary[DBSalariesColumns.ID.value],
                "kind": "salary",
                "name": salary[DBSalariesColumns.NAME.value],
                "date": salary[DBSalariesColumns.DATE.value],
                "amount": float(salary[DBSalariesColumns.AMOUNT.value]),
                "type": "Stipendio",
                "sign": "-"
            })

        # Transfers (bonifici) - Possono essere entrate o uscite
        transfers = self.transfer_query_service.retrieve_transfers_map_list(year = year)

        # Bonifici in entrata (ricevuti)
        incoming_transfers = [t for t in transfers if t[DBTransfersColumns.RECEIVER_ACCOUNT_ID.value] == account_id]
        for transfer in incoming_transfers:
            movements.append({
                "id": transfer[DBTransfersColumns.ID.value],
                "kind": "transfer",
                "name": f"{transfer[DBTransfersColumns.DESCRIPTION.value]}",
                "date": transfer[DBTransfersColumns.CREATED_AT.value].split(" ")[0],
                "amount": float(transfer[DBTransfersColumns.AMOUNT.value]),
                "type": "Bonifico",
                "sign": "+"
            })

        # Bonifici in uscita (inviati)
        outgoing_transfers = [t for t in transfers if t[DBTransfersColumns.SENDER_ACCOUNT_ID.value] == account_id]
        for transfer in outgoing_transfers:
            movements.append({
                "id": transfer[DBTransfersColumns.ID.value],
                "kind": "transfer",
                "name": f"{transfer[DBTransfersColumns.DESCRIPTION.value]}",
                "date": transfer[DBTransfersColumns.CREATED_AT.value].split(" ")[0],
                "amount": float(transfer[DBTransfersColumns.AMOUNT.value]),
                "type": "Bonifico",
                "sign": "-"
            })

        # Ordina per data (dalla più recente alla più vecchia)
        movements.sort(key=lambda x: x["date"], reverse=True)

        return movements

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

    def calculate_trimestral_iva_by_account_id(self, account_id, year:int = None):
        # Dizionario di output con i trimestri
        output_dict = {
            "Gen-Marz": {"debito": 0.0, "credito": 0.0, "da_pagare": 0.0},
            "Apr-Giu": {"debito": 0.0, "credito": 0.0, "da_pagare": 0.0},
            "Lug-Sett": {"debito": 0.0, "credito": 0.0, "da_pagare": 0.0},
            "Ott-Dic": {"debito": 0.0, "credito": 0.0, "da_pagare": 0.0}
        }

        # Funzione per determinare il trimestre da un mese
        def get_trimestre(month):
            if 1 <= month <= 3:
                return "Gen-Marz"
            elif 4 <= month <= 6:
                return "Apr-Giu"
            elif 7 <= month <= 9:
                return "Lug-Sett"
            else:
                return "Ott-Dic"

        # Recupera le spese deducibili e le fatture
        deducted_expenses = self.user_query_service.retrieve_user_with_deducted_expenses_map_list(account_id, year=year)
        invoices = self.user_query_service.retrieve_user_with_invoices_map_list(account_id, include_unpaid_invoices=False, year=year)
        invoices = ControllerUtils.clear_invoices_list_from_NDC_and_stornate(invoices)

        # Elabora le spese (IVA a credito)
        for e in deducted_expenses:
            date_str = e.get(DBExpensesColumns.DATE.value)
            if date_str:
                try:
                    # Converti la stringa in data ed estrai il mese
                    expense_date = datetime.strptime(date_str, "%Y-%m-%d")
                    trimestre = get_trimestre(expense_date.month)

                    # Somma l'IVA a credito
                    iva_amount = float(e.get(DBExpensesColumns.IVA_AMOUNT.value, 0))
                    output_dict[trimestre]["credito"] += iva_amount
                except (ValueError, TypeError):
                    # Gestisci errori di conversione
                    continue

        # Elabora le fatture (IVA a debito)
        for i in invoices:
            date_str = i.get(DBInvoicesColumns.DATA_CREAZIONE.value)
            if date_str:
                try:
                    # Converti la stringa in data e estrai il mese
                    invoice_date = datetime.strptime(date_str, "%Y-%m-%d")
                    trimestre = get_trimestre(invoice_date.month)

                    # Somma l'IVA a debito
                    iva_amount = float(i.get(DBInvoicesColumns.IVA.value, 0))
                    output_dict[trimestre]["debito"] += iva_amount
                except (ValueError, TypeError):
                    # Gestisci errori di conversione
                    continue

        # Calcola l'IVA da pagare per ogni trimestre
        for trimestre, valori in output_dict.items():
            valori["da_pagare"] = valori["debito"] - valori["credito"]

        return output_dict

    def calculate_tot_trimestral_iva(self, year:int = None):
        output_map = {}

        for user in self.user_query_service.retrieve_users_map_list():
            if user[DBUsersColumns.REGIME_FISCALE.value] == RegimeFiscale.ORDINARIO.value:
                user_name = user[DBUsersColumns.FIRST_NAME.value] + " " + user[DBUsersColumns.LAST_NAME.value]
                user_id = user[DBUsersColumns.ID.value]
                output_map[user_name] = self.calculate_trimestral_iva_by_account_id(user_id, year=year)

        return output_map

    def retrieve_account_movements_by_account_id(self, account_id, year:int = None):
        movements = []

        # Payments (+) - Entrate
        payments = self.payments_query_service.retrieve_payments_map_list(year = year, include_unpaid_invoice_payments = False)
        filtered_payments = [p for p in payments if p[DBPaymentsColumns.CONTO_ID.value] == account_id]
        for payment in filtered_payments:
            movements.append({
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
                "name": f"{transfer[DBTransfersColumns.DESCRIPTION.value]}",
                "date": transfer[DBTransfersColumns.CREATED_AT.value].split(" ")[0],
                "amount": float(transfer[DBTransfersColumns.AMOUNT.value]),
                "type": "Bonifico",
                "sign": "-"
            })

        # Ordina per data (dalla più recente alla più vecchia)
        movements.sort(key=lambda x: x["date"], reverse=True)

        return movements

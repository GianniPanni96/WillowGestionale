from QueryServices.Account_query_service import AccountQueryService


class AccountAnalyzerService:
    def __init__(self, account_query_service: AccountQueryService):
        self.account_query_service = account_query_service

    def count_accounts(self):
        return len(self.account_query_service.retrieve_accounts_map_list())

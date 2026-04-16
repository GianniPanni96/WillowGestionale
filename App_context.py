from AnalyzerServices.Client_analyzer_service import ClientAnalyzerService
from AnalyzerServices.Iva_analyzer_service import IvaAnalyzerService
from AnalyzerServices.Production_analyzer_service import ProductionAnalyzerService
from AnalyzerServices.Supplier_analyzer_service import SupplierAnalyzerService
from AnalyzerServices.Invoice_analyzer_service import InvoiceAnalyzerService
from AnalyzerServices.Payment_analyzer_service import PaymentAnalyzerService
from AnalyzerServices.Refund_analyzer_service import RefundAnalyzerService
from AnalyzerServices.Expense_analyzer_service import ExpenseAnalyzerService
from AnalyzerServices.Account_analyzer_service import AccountAnalyzerService
from AnalyzerServices.Transfer_analyzer_service import TransferAnalyzerService
from AnalyzerServices.Salary_analyzer_service import SalaryAnalyzerService
from AnalyzerServices.User_analyzer_service import UserAnalyzerService

from AnalyzerServices.Monthly_report_analyzer_service import MonthlyReportAnalyzerService
from Updates_controller import UpdatesController

from Model import DatabaseModel
from Event_bus import EventBus
from Books_retriever import BooksRetriever
from Book_closer import BookCloser
from Config import FiscalSettings

from Controllerss.Client_controller import ClientController
from Controllerss.Supplier_controller import SupplierController
from Controllerss.Production_controller import ProductionController
from Controllerss.Invoice_controller import InvoiceController
from Controllerss.Payment_controller import PaymentsController
from Controllerss.Refund_controller import RefundController
from Controllerss.Expense_controller import ExpenseController
from Controllerss.Account_controller import AccountController
from Controllerss.Transfer_controller import TransferController
from Controllerss.Salary_controller import SalaryController
from Controllerss.User_controller import UserController

from QueryServices.Account_query_service import AccountQueryService
from QueryServices.Clients_query_service import ClientQueryService
from QueryServices.Suppliers_query_service import SupplierQueryService
from QueryServices.Productions_query_service import ProductionQueryService
from QueryServices.Invoices_query_service import InvoiceQueryService
from QueryServices.Payments_query_service import PaymentQueryService
from QueryServices.Refunds_query_service import RefundQueryService
from QueryServices.Expenses_query_service import ExpenseQueryService
from QueryServices.Transfers_query_service import TransferQueryService
from QueryServices.Salaries_query_service import SalaryQueryService
from QueryServices.Users_query_service import UserQueryService
from OtherServices.User_auth_service import UserAuthService
from OtherServices.User_crypto_service import UserCryptoService
from WarningServices.Production_warning_service import ProductionWarningService
from WarningServices.Invoice_warning_service import InvoiceWarningService
from WarningServices.Payment_warning_service import PaymentWarningService




from Config import ConfigManager
from Backup_manager import BackupImporter, BackupScheduler
from Tab_ui_state_store import TabUIStateStore


class AppContext:
    def __init__(self, fiscal_settings,
                 historical_financial_data_settings,
                 recurring_expenses_settings,
                 catalogo_elenchi,
                 config_manager:"ConfigManager",
                 backup_importer:"BackupImporter",
                 backup_scheduler:"BackupScheduler",
                 environment_db_variable,
                 db_path,
                 data_path,
                 images_path,
                 db_backup_path,
                 books_path):
        # inizializzatori oggetti controllers e model
        self.environment_db_variable = environment_db_variable
        self.db_path = db_path
        self.data_path = data_path
        self.images_path = images_path
        self.db_backup_path = db_backup_path
        self.books_path = books_path
        self.db_model:DatabaseModel = DatabaseModel(db_path)  # Istanzia il modello
        self.fiscal_settings: FiscalSettings = fiscal_settings

        self.suppliers_query_service: SupplierQueryService = SupplierQueryService(self.db_model)
        self.productions_query_service:ProductionQueryService = ProductionQueryService(self.db_model)
        self.invoices_query_service:InvoiceQueryService = InvoiceQueryService(self.db_model)
        self.account_query_service:AccountQueryService = AccountQueryService(self.db_model)
        self.payments_query_service:PaymentQueryService = PaymentQueryService(self.db_model)
        self.refunds_query_service:RefundQueryService = RefundQueryService(self.db_model)
        self.expenses_query_service:ExpenseQueryService = ExpenseQueryService(self.db_model)
        self.transfer_query_service:TransferQueryService = TransferQueryService(self.db_model)
        self.salary_query_service:SalaryQueryService = SalaryQueryService(self.db_model)
        self.user_query_service:UserQueryService = UserQueryService(self.db_model, fiscal_settings)
        self.clients_query_service:ClientQueryService = ClientQueryService(self.productions_query_service, self.db_model)

        self.clients_analyzer_service:ClientAnalyzerService = ClientAnalyzerService(self.clients_query_service, self.db_model)
        self.suppliers_analyzer_service:SupplierAnalyzerService = SupplierAnalyzerService(self.suppliers_query_service, self.db_model)
        self.productions_analyzer_service:ProductionAnalyzerService = ProductionAnalyzerService(self.productions_query_service, self.db_model)
        self.payments_analyzer_service:PaymentAnalyzerService = PaymentAnalyzerService(self.payments_query_service, self.db_model)
        self.refunds_analyzer_service:RefundAnalyzerService = RefundAnalyzerService(self.refunds_query_service, self.db_model)
        self.expenses_analyzer_service:ExpenseAnalyzerService = ExpenseAnalyzerService(self.expenses_query_service, self.db_model)
        self.transfer_analyzer_service:TransferAnalyzerService = TransferAnalyzerService(self.transfer_query_service)
        self.salary_analyzer_service:SalaryAnalyzerService = SalaryAnalyzerService(self.salary_query_service, self.db_model)
        self.user_analyzer_service:UserAnalyzerService = UserAnalyzerService(
            self.user_query_service,
            self.db_model,
            self.fiscal_settings
        )
        self.iva_analyzer_service:IvaAnalyzerService = IvaAnalyzerService(self.user_query_service)
        self.account_analyzer_service:AccountAnalyzerService = AccountAnalyzerService(self.account_query_service,
                                                                                      self.user_query_service,
                                                                                      self.payments_analyzer_service,
                                                                                      self.payments_query_service,
                                                                                      self.expenses_analyzer_service,
                                                                                      self.expenses_query_service,
                                                                                      self.transfer_analyzer_service,
                                                                                      self.transfer_query_service,
                                                                                      self.salary_analyzer_service,
                                                                                      self.salary_query_service,
                                                                                      self.refunds_analyzer_service,
                                                                                      self.refunds_query_service,
                                                                                      )
        self.user_crypto_service:UserCryptoService = UserCryptoService()
        self.user_auth_service:UserAuthService = UserAuthService(self.user_query_service)
        self.production_warning_service:ProductionWarningService = ProductionWarningService()
        self.invoice_warning_service:InvoiceWarningService = InvoiceWarningService(self.productions_query_service)
        self.payment_warning_service:PaymentWarningService = PaymentWarningService(self.invoices_query_service)

        self.user_controller:UserController = UserController(
            self.db_model,
            self.fiscal_settings,
            self.user_query_service,
            self.user_analyzer_service,
            self.user_crypto_service,
            self.user_auth_service,
        )
        self.invoices_analyzer_service:InvoiceAnalyzerService = InvoiceAnalyzerService(self.user_controller, self.user_query_service, self.user_analyzer_service,
                                                                                       self.invoices_query_service,
                                                                                       self.db_model, self.fiscal_settings,
                                                                                       historical_financial_data_settings)
        self.account_controller:AccountController = AccountController(
            self.db_model,
            self.account_query_service,
            self.account_analyzer_service
        )
        self.salary_controller:SalaryController = SalaryController(
            self.db_model,
            self.user_query_service,
            self.account_query_service,
            self.salary_query_service,
            self.salary_analyzer_service
        )
        self.transfer_controller:TransferController = TransferController(
            self.db_model,
            self.account_query_service,
            self.transfer_query_service,
            self.transfer_analyzer_service
        )
        self.client_controller:ClientController = ClientController(self.db_model)
        self.supplier_controller:SupplierController = SupplierController(self.db_model)
        self.payment_controller:PaymentsController = PaymentsController(self.db_model, self.account_query_service)
        self.production_controller:ProductionController = ProductionController(self.db_model, self.clients_query_service)
        self.invoice_controller:InvoiceController = InvoiceController(self.db_model, self.invoices_analyzer_service, self.clients_query_service,
                                                    self.invoices_query_service, self.productions_query_service,
                                                    self.user_query_service, fiscal_settings, self.account_query_service)
        self.expense_controller:ExpenseController = ExpenseController(
            self.db_model,
            self.user_query_service,
            self.account_controller,
            self.account_query_service,
            self.supplier_controller,
            self.suppliers_query_service,
            self.invoices_query_service,
            self.expenses_query_service,
            recurring_expenses_settings,
            catalogo_elenchi
        )
        self.refund_controller:RefundController = RefundController(self.db_model, self.clients_query_service, self.account_query_service)
        self.update_controller:UpdatesController = UpdatesController(self.user_controller, self.client_controller,
                                                   self.invoice_controller, self.payment_controller,
                                                   self.account_controller, self.production_controller)
        self.monthly_report_analyzer_service:MonthlyReportAnalyzerService = MonthlyReportAnalyzerService(
                                 self.invoices_query_service,
                                 self.payments_query_service,
                                 self.expenses_query_service,
                                 self.salary_query_service,
                                 self.refunds_query_service)
        self.catalogo_elenchi = catalogo_elenchi
        self.config_manager:ConfigManager = config_manager
        self.event_bus:EventBus = EventBus()
        self.tab_ui_state_store:TabUIStateStore = TabUIStateStore()
        self.backup_importer:BackupImporter = backup_importer
        self.backup_scheduler:BackupScheduler = backup_scheduler
        self.historical_financial_data_settings = historical_financial_data_settings
        self.recurring_expenses_settings = recurring_expenses_settings
        self.books_retriever:BooksRetriever = BooksRetriever(books_path=self.books_path)
        self.book_closer:BookCloser = BookCloser(environment_db_variable=self.environment_db_variable,
                                                 books_path=self.books_path,
                                                 account_controller=self.account_controller,
                                                 accounts_query_service=self.account_query_service,
                                                 account_analyzer_service=self.account_analyzer_service,
                                                 monthly_report_analyzer_service=self.monthly_report_analyzer_service,
                                                 user_controller=self.user_controller,
                                                 user_analyzer_service=self.user_analyzer_service,
                                                 user_query_service=self.user_query_service,
                                                 config_manager=self.config_manager,
                                                 invoices_analyzer_service=self.invoices_analyzer_service,
                                                 expense_analyzer_service=self.expenses_analyzer_service,
                                                 productions_analyzer_service=self.productions_analyzer_service,
                                                 salary_analyzer_service=self.salary_analyzer_service,
                                                 iva_analyzer_service=self.iva_analyzer_service)


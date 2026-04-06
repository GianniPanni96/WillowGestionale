from Analyzers.Client_analyzer_service import ClientAnalyzerService
from Analyzers.Production_analyzer_service import ProductionAnalyzerService
from Analyzers.Supplier_analyzer_service import SupplierAnalyzerService
from Analyzers.Invoice_analyzer_service import InvoiceAnalyzerService
from Analyzers.Payment_analyzer_service import PaymentAnalyzerService
from Analyzers.Refund_analyzer_service import RefundAnalyzerService
from Analyzers.Expense_analyzer_service import ExpenseAnalyzerService


from Controllers import UserController, AccountController, \
     UpdatesController, \
    Analyzer, TransfersController, SalaryController


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

from QueryServices.Clients_query_service import ClientQueryService
from QueryServices.Suppliers_query_service import SupplierQueryService
from QueryServices.Productions_query_service import ProductionQueryService
from QueryServices.Invoices_query_service import InvoiceQueryService
from QueryServices.Payments_query_service import PaymentQueryService
from QueryServices.Refunds_query_service import RefundQueryService
from QueryServices.Expenses_query_service import ExpenseQueryService
from WarningServices.Production_warning_service import ProductionWarningService
from WarningServices.Invoice_warning_service import InvoiceWarningService
from WarningServices.Payment_warning_service import PaymentWarningService



from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from Config import ConfigManager
    from Backup_manager import BackupImporter, BackupScheduler


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
        self.payments_query_service:PaymentQueryService = PaymentQueryService(self.db_model)
        self.refunds_query_service:RefundQueryService = RefundQueryService(self.db_model)
        self.expenses_query_service:ExpenseQueryService = ExpenseQueryService(self.db_model)
        self.clients_query_service:ClientQueryService = ClientQueryService(self.productions_query_service, self.db_model)

        self.clients_analyzer_service:ClientAnalyzerService = ClientAnalyzerService(self.clients_query_service, self.db_model)
        self.suppliers_analyzer_service:SupplierAnalyzerService = SupplierAnalyzerService(self.suppliers_query_service, self.db_model)
        self.productions_analyzer_service:ProductionAnalyzerService = ProductionAnalyzerService(self.productions_query_service, self.db_model)
        self.payments_analyzer_service:PaymentAnalyzerService = PaymentAnalyzerService(self.payments_query_service, self.db_model)
        self.refunds_analyzer_service:RefundAnalyzerService = RefundAnalyzerService(self.refunds_query_service, self.db_model)
        self.expenses_analyzer_service:ExpenseAnalyzerService = ExpenseAnalyzerService(self.expenses_query_service, self.db_model)
        self.production_warning_service:ProductionWarningService = ProductionWarningService()
        self.invoice_warning_service:InvoiceWarningService = InvoiceWarningService(self.productions_query_service)
        self.payment_warning_service:PaymentWarningService = PaymentWarningService(self.invoices_query_service)

        self.user_controller:UserController = UserController(self.db_model, self.fiscal_settings)  # Crea il controller per gli utenti
        self.invoices_analyzer_service:InvoiceAnalyzerService = InvoiceAnalyzerService(self.user_controller, self.invoices_query_service,
                                                                                       self.db_model, self.fiscal_settings,
                                                                                       historical_financial_data_settings)
        self.account_controller:AccountController = AccountController(self.db_model, self.user_controller)
        self.salary_controller:SalaryController = SalaryController(self.db_model, self.user_controller, self.account_controller)
        self.transfer_controller:TransfersController = TransfersController(self.db_model, self.account_controller)
        self.client_controller:ClientController = ClientController(self.db_model)
        self.supplier_controller:SupplierController = SupplierController(self.db_model)
        self.payment_controller:PaymentsController = PaymentsController(self.db_model, self.account_controller)
        self.production_controller:ProductionController = ProductionController(self.db_model, self.clients_query_service)
        self.invoice_controller:InvoiceController = InvoiceController(self.db_model, self.invoices_analyzer_service, self.clients_query_service,
                                                    self.invoices_query_service, self.productions_query_service,
                                                    self.user_controller, fiscal_settings, self.account_controller)
        self.expense_controller:ExpenseController = ExpenseController(
            self.db_model,
            self.user_controller,
            self.account_controller,
            self.supplier_controller,
            self.suppliers_query_service,
            self.invoices_query_service,
            self.expenses_query_service,
            recurring_expenses_settings,
            catalogo_elenchi
        )
        self.refund_controller:RefundController = RefundController(self.db_model, self.clients_query_service, self.account_controller)
        self.update_controller:UpdatesController = UpdatesController(self.user_controller, self.client_controller,
                                                   self.invoice_controller, self.payment_controller,
                                                   self.account_controller, self.production_controller)
        self.analyzer:Analyzer = Analyzer(self.user_controller,
                                 self.client_controller,
                                 self.account_controller,
                                 self.invoice_controller,
                                 self.transfer_controller,
                                 self.supplier_controller,
                                 self.production_controller,
                                 self.payment_controller,
                                 self.payments_analyzer_service,
                                 self.payments_query_service,
                                 self.refunds_query_service,
                                 self.expenses_query_service,
                                 self.expenses_analyzer_service,
                                 self.salary_controller,
                                 self.refunds_analyzer_service,
                                 self.fiscal_settings,
                                 recurring_expenses_settings)
        self.catalogo_elenchi = catalogo_elenchi
        self.config_manager:ConfigManager = config_manager
        self.event_bus:EventBus = EventBus()
        self.backup_importer:BackupImporter = backup_importer
        self.backup_scheduler:BackupScheduler = backup_scheduler
        self.historical_financial_data_settings = historical_financial_data_settings
        self.recurring_expenses_settings = recurring_expenses_settings
        self.books_retriever:BooksRetriever = BooksRetriever(books_path=self.books_path)
        self.book_closer:BookCloser = BookCloser(environment_db_variable=self.environment_db_variable,
                                                 books_path=self.books_path,
                                                 account_controller=self.account_controller,
                                                 analyzer=self.analyzer,
                                                 user_controller=self.user_controller,
                                                 config_manager=self.config_manager,
                                                 invoices_analyzer_service=self.invoices_analyzer_service,
                                                 expense_analyzer_service=self.expenses_analyzer_service,
                                                 productions_analyzer_service=self.productions_analyzer_service,
                                                 salary_controller=self.salary_controller)


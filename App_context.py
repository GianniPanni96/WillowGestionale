from Controllers import UserController, AccountController, ClientController, InvoiceController, \
    PaymentsController, ProductionController, ExpenseController, SupplierController, UpdatesController, ControllerUtils, \
    Analyzer, TransfersController, SalaryController, RefundController
from Model import DatabaseModel
from Event_bus import EventBus
from Books_retriever import BooksRetriever


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from Config import ConfigManager
    from Backup_manager import BackupImporter


class AppContext:
    def __init__(self, fiscal_settings,
                 historical_financial_data_settings,
                 recurring_expenses_settings,
                 catalogo_elenchi,
                 config_manager:"ConfigManager",
                 backup_importer:"BackupImporter",
                 environment_db_variable,
                 db_path,
                 data_path,
                 images_path,
                 backup_path):
        # inizializzatori oggetti controllers e model
        self.environment_db_variable = environment_db_variable
        self.db_path = db_path
        self.data_path = data_path
        self.images_path = images_path
        self.backup_path = backup_path
        self.db_model:DatabaseModel = DatabaseModel(db_path)  # Istanzia il modello
        self.fiscal_settings = fiscal_settings
        self.user_controller:UserController = UserController(self.db_model, self.fiscal_settings)  # Crea il controller per gli utenti
        self.account_controller:AccountController = AccountController(self.db_model, self.user_controller)
        self.salary_controller:SalaryController = SalaryController(self.db_model, self.user_controller, self.account_controller)
        self.transfer_controller:TransfersController = TransfersController(self.db_model, self.account_controller)
        self.client_controller:ClientController = ClientController(self.db_model)
        self.supplier_controller:SupplierController = SupplierController(self.db_model)
        self.payment_controller:PaymentsController = PaymentsController(self.db_model, self.account_controller)
        self.production_controller:ProductionController = ProductionController(self.db_model, self.client_controller)
        self.invoice_controller:InvoiceController = InvoiceController(self.db_model, self.user_controller, self.client_controller,
                                                    self.production_controller, self.payment_controller,
                                                    self.account_controller, fiscal_settings,
                                                    historical_financial_data_settings)
        self.expense_controller:ExpenseController = ExpenseController(self.db_model, self.user_controller, self.account_controller,
                                                    self.invoice_controller, self.supplier_controller,
                                                    recurring_expenses_settings, catalogo_elenchi)
        self.refund_controller:RefundController = RefundController(self.db_model, self.client_controller, self.account_controller)
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
                                 self.expense_controller,
                                 self.salary_controller,
                                 self.refund_controller,
                                 self.fiscal_settings,
                                 recurring_expenses_settings)
        self.catalogo_elenchi = catalogo_elenchi
        self.config_manager:ConfigManager = config_manager
        self.event_bus:EventBus = EventBus()
        self.backup_importer:BackupImporter = backup_importer
        self.historical_financial_data_settings = historical_financial_data_settings
        self.recurring_expenses_settings = recurring_expenses_settings
        self.books_retriever:BooksRetriever = BooksRetriever(self.environment_db_variable)
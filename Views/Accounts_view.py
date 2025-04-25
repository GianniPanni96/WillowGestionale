import customtkinter as ctk
import tkinter as tk
from tkcalendar import Calendar
from Views.View_utils import ViewUtils
from Controllers import PaymentsController, InvoiceController, UserController, ControllerUtils, SupplierController
from Model import DBInvoicesColumns, DBUsersColumns, DBClientsColumns, DBPaymentsColumns, DBProductionsColumns, DBAccountsColumns, DBSuppliersColumns
from datetime import datetime
import re
from enum import Enum

class AccountsView(ctk.CTk):

    def __init__(self, db_model, update_controller,  config_manager, catalogo_elenchi, tab):
        super().__init__()

        self.db_model = db_model
        self.update_controller = update_controller
        self.config_manager = config_manager
        self.catalogo_elenchi = catalogo_elenchi
        self.tab = tab

        self.global_infos = {}
        self.amount_aggregate_labels = {}

        self.suppliers_card_list = {}
        self.supplier_card_labels_status = {}

    def create_accounts_tab(self):
        return
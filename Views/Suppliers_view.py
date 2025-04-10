import customtkinter as ctk
import tkinter as tk
from tkcalendar import Calendar
from Views.View_utils import ViewUtils
from Controllers import PaymentsController, InvoiceController, UserController, ControllerUtils
from Model import DBInvoicesColumns, DBUsersColumns, DBClientsColumns, DBPaymentsColumns, DBProductionsColumns, DBAccountsColumns
from datetime import datetime
import re
from enum import Enum

class SuppliersView(ctk.CTk):

    def __init__(self, db_model, update_controller, tab):
        super().__init__()

        self.db_model = db_model
        self.update_controller = update_controller
        self.tab = tab

        self.global_infos = {}
        self.amount_aggregate_labels = {}

        self.suppliers_card_list = {}
        self.supplier_card_labels_status = {}
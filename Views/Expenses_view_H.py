from datetime import datetime, timedelta

import customtkinter as ctk

from App_context import AppContext
from Controllerss.Expense_controller import ExpenseController
from Gestionale_Enums import*
from QueryServices.Account_query_service import AccountQueryService
from QueryServices.Users_query_service import UserQueryService
from Views.BaseList_view import BaseListView
from Views.Creators.Expense_create_view import ExpenseCreateView
from Views.Details.Expense_detail_view import ExpenseDetailView
from Views.View_utils import ViewUtils


class ExpensesViewH(BaseListView):
    TAB_NAME = "Spese"
    CARDS_FRAME_NAME = "expenses_cards_frame"
    ADD_BUTTON_TEXT = "Aggiungi una spesa"

    aggregate_UOM = {
        ExpensesAggregateData.NUMERO_SPESE.value: "",
        ExpensesAggregateData.TOT_SPESE.value: "EUR",
    }

    HEADERS = [
        "NOME", "FORNITORE", "NETTO", "LORDO", "CATEGORIA",
        "DATA\nEMISSIONE", "DEDUCIBILE", "DEDUZIONE A\nCARICO DI", "CONTO\nCORRENTE"
    ]

    SEARCH_BAR_OPTIONS = {
        "NOME SPESA": "NOME SPESA",
        "NOME FORNITORE": "NOME FORNITORE",
        "CATEGORIA": "CATEGORIA",
        "NOME UTENTE": "NOME UTENTE",
        "CONTO": "CONTO",
    }

    FILTER_MAPPING = {
        "NOME SPESA": (0, ctk.CTkButton),
        "NOME FORNITORE": (1, ctk.CTkLabel),
        "CATEGORIA": (4, ctk.CTkLabel),
        "NOME UTENTE": (7, ctk.CTkLabel),
        "CONTO": (8, ctk.CTkLabel),
    }

    SORT_CONFIG = {
        "TOTALE LORDO": {
            "label": "TOTALE LORDO",
            "access": "direct",
            "index": 3,
            "converter": "currency",
        },
        "DATA EMISSIONE": {
            "label": "DATA EMISSIONE",
            "access": "direct",
            "index": 5,
            "converter": "date",
        },
        "DATA CREAZIONE": {
            "label": "DATA CREAZIONE",
            "access": "database",
            "db_column": "created_at",
            "converter": "datetime",
        },
        "ULTIMA MODIFICA": {
            "label": "ULTIMA MODIFICA",
            "access": "database",
            "db_column": "updated_at",
            "converter": "datetime",
        },
    }

    SHOW_LAST_CARDS_OPTIONS = {
        "30 GG": "30 GG",
        "60 GG": "60 GG",
        "90 GG": "90 GG",
        "365 GG": "365 GG",
    }

    def __init__(self, app_context: AppContext, tab, initial_expense_id=None):
        super().__init__(tab, db_retrieving_function=app_context.expenses_query_service.retrieve_expenses_map_dictionary)

        self.app_context = app_context
        self.expense_controller = app_context.expense_controller
        self.expenses_query_service = app_context.expenses_query_service
        self.expenses_analyzer_service = app_context.expenses_analyzer_service
        self.suppliers_query_service = app_context.suppliers_query_service
        self.user_query_service:UserQueryService = app_context.user_query_service
        self.accounts_query_service:AccountQueryService = app_context.account_query_service

        self.expenses_card_list = self.cards_list
        self.expense_create_view = None

        self.initialize_view()
        self.show_last_cards_optionMenu.set("60 GG")
        self.show_last_cards()

        self.expense_detail_view = ExpenseDetailView(
            parent=self,
            app_context=self.app_context,
            back_callback=self.show_main_view,
            on_expense_changed=self._on_expense_changed,
        )

        if initial_expense_id is not None:
            self.after(100, lambda: self.open_expense_detail_tab(initial_expense_id))
        else:
            self.show_main_view()

    def populate_global_infos(self):
        self.global_infos[ExpensesAggregateData.NUMERO_SPESE.value] = self.expenses_analyzer_service.count_expenses()
        self.global_infos[ExpensesAggregateData.TOT_SPESE.value] = f"{self.expenses_analyzer_service.calculate_tot_expenses():.2f}"

    def open_add_window(self):
        if self.expense_create_view is not None and self.expense_create_view.winfo_exists():
            self.expense_create_view.focus()
            self.expense_create_view.lift()
            return

        self.expense_create_view = ExpenseCreateView(
            parent=self,
            app_context=self.app_context,
            on_expense_created=self._on_expense_created,
            on_close=self._clear_expense_create_view,
        )

    def _clear_expense_create_view(self):
        self.expense_create_view = None

    def _on_expense_created(self, expense_id, expense_data):
        self._refresh_global_infos()
        self.show_last_cards()
        self.filter_cards(None)

    def _on_expense_changed(self):
        self._refresh_global_infos()
        self.show_last_cards()
        self.filter_cards(None)

    def _refresh_global_infos(self):
        self.global_infos.clear()
        self.populate_global_infos()
        for key, amount_label in self.amount_aggregate_labels.items():
            amount_label.configure(text=f"{self.global_infos.get(key, 0)} {self.aggregate_UOM.get(key, '')}".strip())

    def load_items_chunked(self, items_list):
        items_list.sort(key=self._parse_expense_updated_at, reverse=True)

        extractor = ViewUtils.create_extractor_for_expenses(
            self.suppliers_query_service,
            self.user_query_service,
            self.accounts_query_service
        )

        ViewUtils.process_items_in_chunks(
            widget=self,
            items_list=items_list,
            add_card_callback=self.add_item_card,
            extract_args_callback=extractor,
            cards_frame=self.expenses_cards_frame,
        )

    def add_item_card(self, expense_id, name, supplier_name, net_amount, amount, category, date, deducibile, user_name, account_name):
        card = ctk.CTkFrame(self.expenses_cards_frame, fg_color="dimgray")
        card.pack(pady=10, padx=8, fill="x", expand=True)

        data = [
            supplier_name,
            round(float(net_amount), 2),
            round(float(amount), 2),
            ViewUtils.split_string_by_length(category, 15),
            ViewUtils.invert_data_string(date),
            deducibile,
            user_name,
            account_name,
        ]
        units = ["", "EUR", "EUR", "", "", "", "", ""]

        for col in range(1 + len(data)):
            card.grid_columnconfigure(col, weight=1, uniform="expensecol")
        card.grid_rowconfigure(0, weight=1)

        btn = ctk.CTkButton(
            card,
            text=name,
            command=lambda eid=expense_id: self.open_expense_detail_tab(eid)
        )
        btn.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        for idx, value in enumerate(data, start=1):
            text = f"{value} {units[idx - 1]}".strip()
            label = ctk.CTkLabel(card, text=text, font=("Arial", 14))
            label.grid(row=0, column=idx, sticky="nsew", padx=5, pady=10)

        self.finalize_item_card(card, name, btn)

    def open_expense_detail_tab(self, expense_id):
        self.main_container.pack_forget()
        self.expense_detail_view.pack(fill="both", expand=True)
        self.expense_detail_view.create_detail_tab(expense_id)

    def show_last_cards(self):
        selected = self.show_last_cards_optionMenu.get()
        days_map = {"30 GG": 30, "60 GG": 60, "90 GG": 90, "365 GG": 365}
        limit_date = datetime.now() - timedelta(days=days_map.get(selected, 30))

        all_expenses = self.expenses_query_service.retrieve_expenses_map_list()
        filtered_expenses = []

        for expense in all_expenses:
            expense_date = self._parse_datetime_value(expense.get(DBExpensesColumns.DATE.value))
            if expense_date is not None and expense_date >= limit_date:
                filtered_expenses.append(expense)

        self.reload_cards(filtered_expenses)

    def _parse_expense_updated_at(self, expense):
        return self._parse_datetime_value(expense.get(DBExpensesColumns.updated_at.value)) or datetime.min

    def _parse_datetime_value(self, value):
        if not value:
            return None

        for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, pattern)
            except ValueError:
                continue
        return None

from datetime import datetime, timedelta

import customtkinter as ctk

from App_context import AppContext
from Analyzers.Salary_analyzer_service import SalaryAnalyzerService
from Controllerss.Salary_controller import SalaryController
from Gestionale_Enums import DBSalariesColumns
from QueryServices.Account_query_service import AccountQueryService
from QueryServices.Salaries_query_service import SalaryQueryService
from Views.BaseList_view import BaseListView
from Views.Creators.Salary_create_view import SalaryCreateView
from Views.Details.Salary_detail_view import SalaryDetailView
from Views.View_utils import ViewUtils


class SalariesViewH(BaseListView):
    TAB_NAME = "Salario"
    CARDS_FRAME_NAME = "salaries_cards_frame"
    ADD_BUTTON_TEXT = "Aggiungi un salario"

    aggregate_UOM = {
        SalaryAnalyzerService.SalariesAggregateData.NUMERO_SALARI.value: "",
        SalaryAnalyzerService.SalariesAggregateData.TOT_SALARI.value: "EUR",
    }

    HEADERS = ["NOME", "UTENTE", "IMPORTO", "DATA\nEMISSIONE", "CONTO\nCORRENTE"]

    SEARCH_BAR_OPTIONS = {
        "NOME SALARIO": "NOME SALARIO",
        "NOME UTENTE": "NOME UTENTE",
        "CONTO": "CONTO",
    }

    FILTER_MAPPING = {
        "NOME SALARIO": (0, ctk.CTkButton),
        "NOME UTENTE": (1, ctk.CTkLabel),
        "CONTO": (4, ctk.CTkLabel),
    }

    SORT_CONFIG = {
        "IMPORTO": {
            "label": "IMPORTO",
            "access": "direct",
            "index": 2,
            "converter": "currency",
        },
        "DATA EMISSIONE": {
            "label": "DATA EMISSIONE",
            "access": "direct",
            "index": 3,
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
        }
    }

    SHOW_LAST_CARDS_OPTIONS = {
        "30 GG": "30 GG",
        "60 GG": "60 GG",
        "90 GG": "90 GG",
        "365 GG": "365 GG"
    }

    def __init__(self, app_context: AppContext, tab, initial_salary_id=None):
        super().__init__(
            tab,
            db_retrieving_function=app_context.salary_query_service.retrieve_salaries_map_dictionary
        )

        self.app_context = app_context
        self.salary_controller: SalaryController = app_context.salary_controller
        self.salary_query_service: SalaryQueryService = app_context.salary_query_service
        self.salary_analyzer_service: SalaryAnalyzerService = app_context.salary_analyzer_service
        self.account_query_service: AccountQueryService = app_context.account_query_service
        self.user_controller = app_context.user_controller

        self.salaries_card_list = self.cards_list
        self.salary_create_view = None

        self.initialize_view()
        self.show_last_cards_optionMenu.set("60 GG")
        self.show_last_cards()

        self.salary_detail_view = SalaryDetailView(
            parent=self,
            app_context=self.app_context,
            back_callback=self.show_main_view,
            on_salary_changed=self._on_salary_changed
        )

        if initial_salary_id is not None:
            self.after(100, lambda: self.open_salary_detail_tab(initial_salary_id))
        else:
            self.show_main_view()

    def populate_global_infos(self):
        self.global_infos[SalaryAnalyzerService.SalariesAggregateData.NUMERO_SALARI.value] = (
            self.salary_analyzer_service.count_salaries()
        )
        self.global_infos[SalaryAnalyzerService.SalariesAggregateData.TOT_SALARI.value] = round(
            self.salary_analyzer_service.calculate_tot_salaries(), 2
        )

    def open_add_window(self):
        if self.salary_create_view is not None and self.salary_create_view.winfo_exists():
            self.salary_create_view.focus()
            self.salary_create_view.lift()
            return

        self.salary_create_view = SalaryCreateView(
            parent=self,
            app_context=self.app_context,
            on_salary_created=self._on_salary_created,
            on_close=self._clear_salary_create_view
        )

    def _clear_salary_create_view(self):
        self.salary_create_view = None

    def _on_salary_created(self, salary_id, salary_map):
        self._refresh_global_infos()
        self.show_last_cards()
        self.filter_cards(None)

    def _on_salary_changed(self):
        self._refresh_global_infos()
        self.show_last_cards()
        self.filter_cards(None)

    def _refresh_global_infos(self):
        self.global_infos.clear()
        self.populate_global_infos()
        for key, amount_label in self.amount_aggregate_labels.items():
            amount_label.configure(
                text=f"{self.global_infos.get(key, 0)} {self.aggregate_UOM.get(key, '')}".strip()
            )

    def load_items_chunked(self, items_list):
        items_list.sort(key=self._parse_salary_updated_at, reverse=True)

        extractor = ViewUtils.create_extractor_for_salaries(
            self.user_controller,
            self.account_query_service
        )
        ViewUtils.process_items_in_chunks(
            widget=self,
            items_list=items_list,
            add_card_callback=self.add_item_card,
            extract_args_callback=extractor,
            cards_frame=self.salaries_cards_frame
        )

    def add_item_card(self, salary_id, salary_name, user_name, amount, date, account_name):
        card = ctk.CTkFrame(self.salaries_cards_frame, fg_color="dimgray")
        card.pack(pady=10, padx=8, fill="x", expand=True)

        data = [user_name, round(float(amount), 2), ViewUtils.invert_data_string(date), account_name]
        units = ["", "EUR", "", ""]

        for col in range(len(self.HEADERS)):
            card.grid_columnconfigure(col, weight=1, uniform="salarycol")
        card.grid_rowconfigure(0, weight=1)

        btn = ctk.CTkButton(
            card,
            text=salary_name,
            command=lambda sid=salary_id: self.open_salary_detail_tab(sid)
        )
        btn.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        for idx, value in enumerate(data, start=1):
            label = ctk.CTkLabel(card, text=f"{value} {units[idx - 1]}".strip(), font=("Arial", 14))
            label.grid(row=0, column=idx, sticky="nsew", padx=5, pady=10)

        self.finalize_item_card(card, salary_name, btn)

    def open_salary_detail_tab(self, salary_id):
        self.main_container.pack_forget()
        self.salary_detail_view.pack(fill="both", expand=True)
        self.salary_detail_view.create_detail_tab(salary_id)

    def show_last_cards(self):
        selected = self.show_last_cards_optionMenu.get()
        days_map = {
            "30 GG": 30,
            "60 GG": 60,
            "90 GG": 90,
            "365 GG": 365
        }
        limit_date = datetime.now() - timedelta(days=days_map.get(selected, 30))

        all_salaries = self.salary_query_service.retrieve_salaries_map_list()
        filtered_salaries = []
        for salary in all_salaries:
            salary_date = self._parse_datetime_value(salary.get(DBSalariesColumns.DATE.value))
            if salary_date is not None and salary_date >= limit_date:
                filtered_salaries.append(salary)

        self.reload_cards(filtered_salaries)

    def _parse_salary_updated_at(self, salary):
        return self._parse_datetime_value(salary.get(DBSalariesColumns.UPDATED_AT.value)) or datetime.min

    def _parse_datetime_value(self, value):
        if not value:
            return None

        for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, pattern)
            except ValueError:
                continue
        return None

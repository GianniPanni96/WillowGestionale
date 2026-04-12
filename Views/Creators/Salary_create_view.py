import re
import tkinter as tk
from datetime import datetime

import customtkinter as ctk
from tkcalendar import Calendar

from App_context import AppContext
from Controllerss.Salary_controller import SalaryController
from Gestionale_Enums import DBAccountsColumns, DBSalariesColumns, DBUsersColumns
from QueryServices.Account_query_service import AccountQueryService
from QueryServices.Salaries_query_service import SalaryQueryService
from QueryServices.Users_query_service import UserQueryService
from Views.View_utils import ViewUtils


class SalaryCreateView(ctk.CTkToplevel):
    USER_NAME_FIELD = "NOME UTENTE"
    ACCOUNT_NAME_FIELD = "CONTO"

    def __init__(self, parent, app_context: AppContext, on_salary_created=None, on_close=None):
        super().__init__(parent)

        self.app_context = app_context
        self.salary_controller:SalaryController = app_context.salary_controller
        self.salary_query_service: SalaryQueryService = app_context.salary_query_service
        self.account_query_service: AccountQueryService = app_context.account_query_service
        self.user_query_service:UserQueryService = app_context.user_query_service

        self.on_salary_created = on_salary_created
        self.on_close = on_close
        self.today = datetime.now()

        self.entry_fields = {
            self.USER_NAME_FIELD: ctk.CTkOptionMenu,
            DBSalariesColumns.NAME.value: ctk.CTkEntry,
            DBSalariesColumns.DATE.value: Calendar,
            DBSalariesColumns.AMOUNT.value: ctk.CTkEntry,
            self.ACCOUNT_NAME_FIELD: ctk.CTkOptionMenu,
        }
        self.error_fields = {
            DBSalariesColumns.NAME.value: ctk.CTkLabel,
            DBSalariesColumns.AMOUNT.value: ctk.CTkLabel,
        }

        self.salaries_widgets = {}
        self.error_labels = {}
        self.salaries_labels = {}

        self.title("Aggiungi Nuovo Salario")
        self.geometry("550x700")
        self.lift()
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.scrollable_frame = ctk.CTkScrollableFrame(self)
        self.scrollable_frame.pack(fill="both", expand=True)

        self._build_form()
        self._bind_validations()
        self._initialize_default_values()

    def _build_form(self):
        for i, (label_text, widget_class) in enumerate(self.entry_fields.items()):
            label = ctk.CTkLabel(self.scrollable_frame, text=label_text)
            label.pack(pady=5 if i == 0 else (35, 0))
            self.salaries_labels[label_text] = label

            widget = self._create_field_widget(label_text, widget_class)
            widget.pack(pady=5, padx=10, fill="x", expand=True)
            self.salaries_widgets[label_text] = widget

            if self.error_fields.get(label_text) is not None:
                error_label = ctk.CTkLabel(self.scrollable_frame, text="")
                error_label.pack(pady=(0, 15))
                self.error_labels[label_text] = error_label

        self.save_button = ctk.CTkButton(
            self.scrollable_frame,
            text="Salva Salario",
            command=self.save_salary_data
        )
        self.save_button.pack(pady=(50, 15))

    def _create_field_widget(self, label_text, widget_class):
        if label_text == self.USER_NAME_FIELD:
            users = self.user_query_service.retrieve_users_map_list()
            return widget_class(
                self.scrollable_frame,
                values=[
                    f"{user[DBUsersColumns.FIRST_NAME.value]} {user[DBUsersColumns.LAST_NAME.value]}"
                    for user in users
                ],
                command=self.toggle_widgets_on_user_selection
            )

        if label_text == DBSalariesColumns.DATE.value:
            return widget_class(self.scrollable_frame, date_pattern=ViewUtils.date_pattern)

        if label_text == self.ACCOUNT_NAME_FIELD:
            accounts = self.account_query_service.retrieve_accounts_map_list()
            return widget_class(
                self.scrollable_frame,
                values=[account[DBAccountsColumns.NAME.value] for account in accounts]
            )

        return widget_class(self.scrollable_frame)

    def _bind_validations(self):
        self.salaries_widgets[DBSalariesColumns.NAME.value].bind(
            "<FocusOut>",
            lambda event: ViewUtils.validate_entry(
                self.salaries_widgets[DBSalariesColumns.NAME.value],
                lambda val: val.strip() != "",
                self.error_labels[DBSalariesColumns.NAME.value],
                "Il campo non può essere vuoto."
            )
        )

        self.salaries_widgets[DBSalariesColumns.AMOUNT.value].bind(
            "<FocusOut>",
            lambda event: ViewUtils.validate_entry(
                self.salaries_widgets[DBSalariesColumns.AMOUNT.value],
                lambda val: re.fullmatch(r"^\d+(\.\d{2})?$", val.strip()) is not None,
                self.error_labels[DBSalariesColumns.AMOUNT.value],
                "Inserimento non valido: inserire un numero monetario con due cifre decimali (es. 123.45)"
            )
        )

    def _initialize_default_values(self):
        selected_user = self.salaries_widgets[self.USER_NAME_FIELD].get().strip()
        if selected_user:
            self.toggle_widgets_on_user_selection(selected_user)

    def toggle_widgets_on_user_selection(self, selected_value):
        user = self.user_query_service.retrieve_user_map_by_extended_name(selected_value.strip())
        if not user:
            return

        account = self.account_query_service.retrieve_account_map_by_id(
            user[DBUsersColumns.CONTO_CORRENTE_ID.value]
        )

        self.salaries_widgets[DBSalariesColumns.NAME.value].delete(0, tk.END)
        self.salaries_widgets[DBSalariesColumns.NAME.value].insert(
            0,
            f"{selected_value.strip()} - {self.today.strftime('%m/%Y')}"
        )

        if account:
            self.salaries_widgets[self.ACCOUNT_NAME_FIELD].set(account[DBAccountsColumns.NAME.value])

    def _collect_salary_data(self):
        salary_data = {}
        for label_text, widget in self.salaries_widgets.items():
            if isinstance(widget, (ctk.CTkEntry, ctk.CTkOptionMenu)):
                salary_data[label_text] = widget.get().strip()
            elif isinstance(widget, Calendar):
                salary_data[label_text] = widget.get_date()
        return salary_data

    def save_salary_data(self):
        salary_data = self._collect_salary_data()
        success, message = self.salary_controller.save_salary(salary_data)

        if not success:
            ViewUtils.show_error_popup(self, "ERRORE", message)
            return

        salary_map = self.salary_query_service.retrieve_last_salary_insert_map()
        salary_id = salary_map[DBSalariesColumns.ID.value] if salary_map else None

        if self.on_salary_created:
            self.on_salary_created(salary_id, salary_map)

        self._on_close()

    def _on_close(self):
        try:
            self.grab_release()
        except Exception:
            pass

        if self.on_close:
            self.on_close()

        self.destroy()

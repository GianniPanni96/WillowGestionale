import re
from datetime import datetime

import customtkinter as ctk
from tkcalendar import Calendar

from App_context import AppContext
from Gestionale_Enums import DBAccountsColumns, DBSalariesColumns, DBUsersColumns
from QueryServices.Account_query_service import AccountQueryService
from QueryServices.Salaries_query_service import SalaryQueryService
from Views.View_utils import ViewUtils


class SalaryDetailView(ctk.CTkFrame):
    ACCOUNT_LABEL = "CONTO"
    USER_LABEL = "UTENTE"

    def __init__(self, parent, app_context: AppContext, back_callback, on_salary_changed=None):
        super().__init__(parent)
        self.parent = parent
        self.app_context = app_context
        self.back_callback = back_callback
        self.on_salary_changed = on_salary_changed

        self.salary_controller = app_context.salary_controller
        self.salary_query_service: SalaryQueryService = app_context.salary_query_service
        self.account_query_service: AccountQueryService = app_context.account_query_service
        self.user_controller = app_context.user_controller
        self.update_controller = app_context.update_controller
        self.current_salary_id = None

        self.configure(fg_color="transparent")

        self.head_frame = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.back_button = ctk.CTkButton(
            self.head_frame,
            text="Elenco Stipendi",
            command=self._cleanup_and_go_back
        )
        self.title_label = ctk.CTkLabel(self.head_frame, font=("Arial", 22, "bold"))
        self.switch_modify = ctk.CTkSwitch(
            self.head_frame,
            text="Abilita la modifica",
            command=lambda: self.toggle_edit(self.content_frame)
        )
        self.content_frame = ctk.CTkFrame(self)

        self.salary_info_widgets = {}
        self.salary_info_labels = {}
        self.error_labels_salaries = {}

        self._setup_base_layout()

    def _setup_base_layout(self):
        self.head_frame.pack(fill="x", pady=5, padx=5)
        self.back_button.pack(anchor="w", side="left", pady=10, padx=10)
        self.title_label.pack(anchor="c", side="left", fill="x", expand=True, pady=10)
        self.switch_modify.pack(anchor="e", side="left", pady=10, padx=10)
        self.content_frame.pack(fill="both", expand=True, pady=20, padx=20)

    def create_detail_tab(self, salary_id):
        self.current_salary_id = salary_id
        self._clear_content()

        self.salary = self.salary_query_service.retrieve_salary_map_by_id(salary_id)
        if not self.salary:
            return

        account_id = self.salary[DBSalariesColumns.ACCOUNT_ID.value]
        account = self.account_query_service.retrieve_account_map_by_id(account_id)
        if account is not None:
            self.salary[self.ACCOUNT_LABEL] = account[DBAccountsColumns.NAME.value]

        user_id = self.salary[DBSalariesColumns.USER_ID.value]
        user = self.user_controller.retrieve_user_map_by_id(user_id)
        if user is not None:
            self.salary[self.USER_LABEL] = f"{user[DBUsersColumns.FIRST_NAME.value]} {user[DBUsersColumns.LAST_NAME.value]}"

        self.title_label.configure(text=self.salary[DBSalariesColumns.NAME.value])
        self._create_salary_info_section(self.salary)
        self.toggle_edit(self.content_frame)

    def _create_salary_info_section(self, salary_data):
        entry_fields = {
            DBSalariesColumns.NAME.value: {
                "type": ctk.CTkEntry,
                "label": "Nome Stipendio",
                "section": "Dati Generali"
            },
            DBSalariesColumns.DATE.value: {
                "type": Calendar,
                "label": "Data Stipendio",
                "section": "Dati Generali"
            },
            DBSalariesColumns.AMOUNT.value: {
                "type": ctk.CTkEntry,
                "label": "Importo (EUR)",
                "section": "Dati Generali"
            },
            self.ACCOUNT_LABEL: {
                "type": ctk.CTkOptionMenu,
                "label": "Conto",
                "section": "Collegamenti",
                "values": [c[DBAccountsColumns.NAME.value] for c in self.account_query_service.retrieve_accounts_map_list()]
            },
            self.USER_LABEL: {
                "type": ctk.CTkOptionMenu,
                "label": "Utente",
                "section": "Collegamenti",
                "values": [
                    f"{u[DBUsersColumns.FIRST_NAME.value]} {u[DBUsersColumns.LAST_NAME.value]}"
                    for u in self.user_controller.retrieve_users_map_list()
                ]
            },
            DBSalariesColumns.CREATED_AT.value: {
                "type": ctk.CTkLabel,
                "label": "Data Creazione",
                "section": "Note"
            },
            DBSalariesColumns.UPDATED_AT.value: {
                "type": ctk.CTkLabel,
                "label": "Ultimo Aggiornamento",
                "section": "Note"
            }
        }

        validation_rules = {
            DBSalariesColumns.NAME.value: (
                lambda val: val.strip() != "",
                "Nome obbligatorio"
            ),
            DBSalariesColumns.DATE.value: (
                lambda val: val.strip() != "",
                "Data obbligatoria"
            ),
            DBSalariesColumns.AMOUNT.value: (
                lambda val: re.fullmatch(r"^\d+(\.\d{1,2})?$", val),
                "Formato valido: 1234.56"
            )
        }

        self.salary_info_widgets = {}
        self.salary_info_labels = {}
        self.error_labels_salaries = {}
        sections = {}

        info_frame = ctk.CTkFrame(self.content_frame, border_width=2, border_color="#2659ab")
        info_frame.pack(fill="both", expand=True, pady=(5, 10), padx=(5, 25))
        info_frame.grid_columnconfigure(0, weight=1, uniform="col")
        info_frame.grid_columnconfigure(1, weight=1, uniform="col")

        for i, section_name in enumerate(["Dati Generali", "Collegamenti", "Note"]):
            frame = ctk.CTkFrame(info_frame)
            frame.grid(row=i // 2, column=i % 2, sticky="nsew", padx=15, pady=15)
            frame.grid_columnconfigure(1, weight=1)
            sections[section_name] = {"frame": frame, "row": 1}
            ctk.CTkLabel(frame, text=section_name, font=("Arial", 14, "bold")).grid(
                row=0, column=0, columnspan=2, sticky="w", padx=15, pady=5
            )

        for field, config in entry_fields.items():
            section = sections[config["section"]]
            frame = section["frame"]
            row = section["row"]

            lbl = ctk.CTkLabel(frame, text=config["label"] + ":")
            lbl.grid(row=row, column=0, sticky="w", padx=(15, 5), pady=(5, 5))
            self.salary_info_labels[field] = lbl

            widget = self._build_widget(frame, field, config, salary_data)
            widget.grid(
                row=row,
                column=1,
                sticky="ew" if config["type"] != ctk.CTkLabel else "w",
                padx=(5, 15),
                pady=(5, 5)
            )
            self.salary_info_widgets[field] = widget

            if field in validation_rules:
                validation_func, error_message = validation_rules[field]
                error_lbl = ctk.CTkLabel(frame, text="", text_color="#e8e5dc")
                error_lbl.grid(row=row + 1, column=1, sticky="w", padx=5, pady=(0, 10))
                self.error_labels_salaries[field] = error_lbl
                widget.bind(
                    "<FocusOut>",
                    lambda e, w=widget, vl=validation_func, el=error_lbl, em=error_message: ViewUtils.validate_entry(w, vl, el, em)
                )
                section["row"] += 2
            else:
                section["row"] += 1

        buttons_frame = ctk.CTkFrame(info_frame, fg_color="#2b2b2b")
        buttons_frame.grid(row=2, column=0, columnspan=2, pady=(5, 15), padx=20, sticky="we")

        self.save_info_btn = ctk.CTkButton(buttons_frame, text="Salva Stipendio", command=self.save_salary_mod)
        self.save_info_btn.pack(padx=(400, 10), pady=(20, 20), side="left")

        self.delete_btn = ctk.CTkButton(
            buttons_frame,
            text="Elimina Stipendio",
            fg_color="#8B0000",
            hover_color="#A52A2A",
            command=self.delete_salary
        )
        self.delete_btn.pack(padx=10, pady=(20, 20), side="right", anchor="e")

    def _build_widget(self, frame, field, config, salary_data):
        if config["type"] == ctk.CTkLabel:
            return config["type"](frame, text=str(salary_data.get(field, "")))

        if config["type"] == ctk.CTkOptionMenu:
            widget = config["type"](frame, values=config.get("values", []))
            if field == self.ACCOUNT_LABEL:
                widget.set(salary_data.get(self.ACCOUNT_LABEL, ""))
            elif field == self.USER_LABEL:
                widget.set(salary_data.get(self.USER_LABEL, ""))
            else:
                values = config.get("values", [""])
                widget.set(salary_data.get(field, values[0] if values else ""))
            return widget

        if config["type"] == Calendar:
            widget = config["type"](frame, date_pattern=ViewUtils.date_pattern)
            value = salary_data.get(field, "")
            widget.selection_set(str(value) if value else datetime.today())
            return widget

        widget = config["type"](frame)
        widget.insert(0, str(salary_data.get(field, "")))
        return widget

    def toggle_edit(self, parent):
        state = ctk.NORMAL if self.switch_modify.get() else ctk.DISABLED
        self.save_info_btn.configure(state=state)
        self.delete_btn.configure(state=state)

        for widget in parent.winfo_children():
            if isinstance(widget, (ctk.CTkEntry, ctk.CTkTextbox)):
                widget.configure(state=state, text_color="#636363" if state == ctk.DISABLED else "#c2c2c2")
            elif isinstance(widget, ctk.CTkOptionMenu):
                widget.configure(state=state)
            elif isinstance(widget, Calendar):
                widget.configure(state=state)
            elif isinstance(widget, (ctk.CTkFrame, ctk.CTkScrollableFrame, ctk.CTkToplevel)):
                self.toggle_edit(widget)

    def save_salary_mod(self):
        account_name = self.salary_info_widgets[self.ACCOUNT_LABEL].get()
        account = self.account_query_service.retrieve_account_map_by_name(account_name)

        user_name = self.salary_info_widgets[self.USER_LABEL].get()
        user_id = None
        if user_name:
            parts = user_name.split(" ", 1)
            first_name = parts[0] if len(parts) > 0 else ""
            last_name = parts[1] if len(parts) > 1 else ""
            user = self.user_controller.retrieve_user_map_by_fullname(first_name, last_name)
            user_id = user[DBUsersColumns.ID.value] if user else None

        salary_data = {
            DBSalariesColumns.NAME.value: self.salary_info_widgets[DBSalariesColumns.NAME.value].get().strip(),
            DBSalariesColumns.DATE.value: self.salary_info_widgets[DBSalariesColumns.DATE.value].get_date(),
            DBSalariesColumns.AMOUNT.value: self.salary_info_widgets[DBSalariesColumns.AMOUNT.value].get().strip(),
            DBSalariesColumns.ACCOUNT_ID.value: account[DBAccountsColumns.ID.value] if account else None,
            DBSalariesColumns.USER_ID.value: user_id
        }

        success, message = self.salary_controller.update_salary(self.current_salary_id, salary_data)
        if success:
            self.salary = self.salary_query_service.retrieve_salary_map_by_id(self.current_salary_id)
            if self.salary:
                self.title_label.configure(text=self.salary[DBSalariesColumns.NAME.value])
            ViewUtils.show_confirm_popup_2(self.content_frame, "SALVATAGGIO COMPLETATO", message)
            self.switch_modify.deselect()
            self.toggle_edit(self.content_frame)
            if self.on_salary_changed:
                self.on_salary_changed()
        else:
            ViewUtils.show_error_popup(self.content_frame, "ERRORE", message)

    def delete_salary(self):
        confirmation = ViewUtils.ask_confirmation_popup(
            self.content_frame,
            "Stai per eliminare questo stipendio.\nDesideri continuare?",
            "ELIMINAZIONE STIPENDIO"
        )
        if not confirmation:
            return

        success, message = self.salary_controller.delete_salary(self.current_salary_id)
        if success:
            ViewUtils.show_confirm_popup_2(self.content_frame, "STIPENDIO ELIMINATO CON SUCCESSO", message)
            if self.on_salary_changed:
                self.on_salary_changed()
            self._cleanup_and_go_back()
        else:
            ViewUtils.show_error_popup(self.content_frame, "ERRORE", message)

    def _clear_content(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        self.switch_modify.deselect()

    def _cleanup_and_go_back(self):
        self._clear_content()
        self.pack_forget()
        self.back_callback()

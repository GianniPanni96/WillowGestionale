import re
import tkinter as tk
from datetime import datetime

import customtkinter as ctk
from tkcalendar import Calendar

from App_context import AppContext
from Gestionale_Enums import*
from QueryServices.Account_query_service import AccountQueryService
from QueryServices.Users_query_service import UserQueryService
from Utils.Controller_utils import ControllerUtils
from Views.View_utils import ViewUtils
from Views.CustomWidgets.Catalog_filterable_combo_box import CatalogFilterableComboBox
from Views.CustomWidgets.Filterable_combo_box import FilterableComboBox


class ExpenseDetailView(ctk.CTkFrame):
    ACCOUNT_FIELD = "CONTO"
    USER_DEDUZIONE_FIELD = "UTENTE DEDUZIONE"
    USER_ANTICIPO_FIELD = "UTENTE ANTICIPO"
    INVOICE_FIELD = "FATTURA ASSOCIATA"
    SUPPLIER_FIELD = "FORNITORE"

    def __init__(self, parent, app_context: AppContext, back_callback, on_expense_changed=None):
        super().__init__(parent)
        self.parent = parent
        self.app_context = app_context
        self.back_callback = back_callback
        self.on_expense_changed = on_expense_changed

        self.expense_controller = app_context.expense_controller
        self.expenses_query_service = app_context.expenses_query_service
        self.invoices_query_service = app_context.invoices_query_service
        self.suppliers_query_service = app_context.suppliers_query_service
        self.user_query_service: UserQueryService = app_context.user_query_service
        self.accounts_query_service: AccountQueryService = app_context.account_query_service
        self.update_controller = app_context.update_controller
        self.config_manager = app_context.config_manager
        self.catalogo_elenchi = app_context.catalogo_elenchi

        self.current_expense_id = None
        self.expense = None
        self.expense_info_widgets = {}
        self.expense_info_labels = {}
        self.error_labels_expenses = {}
        self.add_category_window = None

        self.configure(fg_color="transparent")

        self.head_frame = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.back_button = ctk.CTkButton(self.head_frame, text="Elenco Spese", command=self._cleanup_and_go_back)
        self.title_label = ctk.CTkLabel(self.head_frame, font=("Arial", 22, "bold"))
        self.switch_modify = ctk.CTkSwitch(
            self.head_frame,
            text="Abilita la modifica",
            command=lambda: self.toggle_edit(self.content_frame)
        )
        self.content_frame = ctk.CTkScrollableFrame(self)

        self._setup_base_layout()

    def _setup_base_layout(self):
        self.head_frame.pack(fill="x", pady=5, padx=5)
        self.back_button.pack(anchor="w", side="left", pady=10, padx=10)
        self.title_label.pack(anchor="c", side="left", fill="x", expand=True, pady=10)
        self.switch_modify.pack(anchor="e", side="left", pady=10, padx=10)
        self.content_frame.pack(fill="both", expand=True, pady=20, padx=20)

    def create_detail_tab(self, expense_id):
        self.current_expense_id = expense_id
        self._clear_content()

        expense = self.expenses_query_service.retrieve_expense_map_by_id(expense_id)
        if not expense:
            return

        account = self.accounts_query_service.retrieve_account_map_by_id(expense.get(DBExpensesColumns.ACCOUNT_ID.value))
        supplier = self.suppliers_query_service.retrieve_supplier_map_by_id(expense.get(DBExpensesColumns.SUPPLIER_ID.value))
        user_deduzione = self.user_query_service.retrieve_user_map_by_id(expense.get(DBExpensesColumns.USER_ID_DEDUZIONE.value))
        user_anticipo = self.user_query_service.retrieve_user_map_by_id(expense.get(DBExpensesColumns.USER_ID_ANTICIPO.value))
        fattura = self.invoices_query_service.retrieve_invoice_map_by_id(expense.get(DBExpensesColumns.LINKED_INVOICE_ID.value))

        expense[self.ACCOUNT_FIELD] = account[DBAccountsColumns.NAME.value] if account else ""
        expense[self.SUPPLIER_FIELD] = supplier[DBSuppliersColumns.NAME.value] if supplier else ""
        expense[self.USER_DEDUZIONE_FIELD] = (
            f"{user_deduzione[DBUsersColumns.FIRST_NAME.value]} {user_deduzione[DBUsersColumns.LAST_NAME.value]}"
            if user_deduzione else ""
        )
        expense[self.USER_ANTICIPO_FIELD] = (
            f"{user_anticipo[DBUsersColumns.FIRST_NAME.value]} {user_anticipo[DBUsersColumns.LAST_NAME.value]}"
            if user_anticipo else ""
        )
        expense[self.INVOICE_FIELD] = fattura[DBInvoicesColumns.NUMERO_FATTURA.value] if fattura else "Fattura non ancora emessa"

        self.expense = expense
        self.title_label.configure(text=expense[DBExpensesColumns.NAME.value])
        self._create_expense_info_section(expense)
        self.toggle_edit(self.content_frame)

    def _create_expense_info_section(self, expense_data):
        users = self.user_query_service.retrieve_users_map_list()
        deductible_users = [
            f"{u[DBUsersColumns.FIRST_NAME.value]} {u[DBUsersColumns.LAST_NAME.value]}"
            for u in users
            if u[DBUsersColumns.REGIME_FISCALE.value] == RegimeFiscale.ORDINARIO.value
        ]
        all_users = [f"{u[DBUsersColumns.FIRST_NAME.value]} {u[DBUsersColumns.LAST_NAME.value]}" for u in users]

        self.entry_fields_expenses = {
            DBExpensesColumns.NAME.value: {
                "type": ctk.CTkEntry,
                "label": "Nome Spesa",
                "section": "Dati Generali"
            },
            DBExpensesColumns.DATE.value: {
                "type": Calendar,
                "label": "Data Spesa",
                "section": "Dati Generali"
            },
            DBExpensesColumns.CATEGORY.value: {
                "type": CatalogFilterableComboBox,
                "label": "Categoria",
                "section": "Dati Fiscali",
                "values": self._get_expense_category_values(),
                "add_button_text": "Aggiungi categoria",
                "add_button_command": self.open_add_expenses_category,
                "command": self.expense_category_option_menu_behaviour
            },
            DBExpensesColumns.NET_AMOUNT.value: {
                "type": ctk.CTkEntry,
                "label": "Importo Netto (EUR)",
                "section": "Dati Fiscali"
            },
            DBExpensesColumns.IVA_AMOUNT.value: {
                "type": ctk.CTkEntry,
                "label": "Importo IVA (EUR)",
                "section": "Dati Fiscali"
            },
            DBExpensesColumns.TOT_AMOUNT.value: {
                "type": ctk.CTkEntry,
                "label": "Importo Totale (EUR)",
                "section": "Dati Fiscali"
            },
            DBExpensesColumns.DEDUCIBILE.value: {
                "type": ctk.CTkOptionMenu,
                "label": "Deducibile",
                "section": "Dati Fiscali",
                "values": ["Si", "No"],
                "command": self.toggle_user_deduzione
            },
            self.SUPPLIER_FIELD: {
                "type": FilterableComboBox,
                "label": "Fornitore",
                "section": "Collegamenti",
                "values": [s[DBSuppliersColumns.NAME.value] for s in self.suppliers_query_service.retrieve_suppliers_map_list(year=-1)]
            },
            self.USER_DEDUZIONE_FIELD: {
                "type": ctk.CTkOptionMenu,
                "label": "Utente Deduzione",
                "section": "Collegamenti",
                "values": deductible_users
            },
            self.USER_ANTICIPO_FIELD: {
                "type": ctk.CTkOptionMenu,
                "label": "Utente Anticipo",
                "section": "Collegamenti",
                "values": [""] + all_users
            },
            self.INVOICE_FIELD: {
                "type": ctk.CTkOptionMenu,
                "label": "Fattura Associata",
                "section": "Collegamenti",
                "values": ["Fattura non ancora emessa"] + [
                    invoice[DBInvoicesColumns.NUMERO_FATTURA.value]
                    for invoice in self.invoices_query_service.retrieve_invoices_map_list(year=-1, include_unpaid_invoices=True)
                ]
            },
            self.ACCOUNT_FIELD: {
                "type": ctk.CTkOptionMenu,
                "label": "Conto",
                "section": "Collegamenti",
                "values": [a[DBAccountsColumns.NAME.value] for a in self.accounts_query_service.retrieve_accounts_map_list()]
            },
            DBExpensesColumns.created_at.value: {
                "type": ctk.CTkLabel,
                "label": "Data Creazione",
                "section": "Note"
            },
            DBExpensesColumns.updated_at.value: {
                "type": ctk.CTkLabel,
                "label": "Ultimo Aggiornamento",
                "section": "Note"
            },
        }

        validation_rules = {
            DBExpensesColumns.NET_AMOUNT.value: (
                lambda val: re.fullmatch(r"^\d+(\.\d{1,2})?$", val),
                "Formato valido: 1234.56"
            ),
            DBExpensesColumns.IVA_AMOUNT.value: (
                lambda val: re.fullmatch(r"^\d+(\.\d{1,2})?$", val),
                "Formato valido: 1234.56"
            ),
            DBExpensesColumns.TOT_AMOUNT.value: (
                lambda val: re.fullmatch(r"^\d+(\.\d{1,2})?$", val),
                "Formato valido: 1234.56"
            ),
            DBExpensesColumns.NAME.value: (
                lambda val: val.strip() != "",
                "Campo obbligatorio"
            ),
            DBExpensesColumns.DATE.value: (
                lambda val: val.strip() != "",
                "Campo obbligatorio"
            ),
        }

        self.expense_info_widgets = {}
        self.expense_info_labels = {}
        self.error_labels_expenses = {}
        sections = {}

        if expense_data.get(DBExpensesColumns.RICORRENTE.value):
            self.entry_fields_expenses.pop(DBExpensesColumns.NAME.value, None)

        self.info_frame = ctk.CTkFrame(self.content_frame, border_width=2, border_color="#2659ab")
        self.info_frame.pack(fill="both", expand=True, pady=(5, 10), padx=(5, 25))
        self.info_frame.grid_columnconfigure(0, weight=1, uniform="col")
        self.info_frame.grid_columnconfigure(1, weight=1, uniform="col")

        for i, section_name in enumerate(["Dati Generali", "Dati Fiscali", "Collegamenti", "Note"]):
            frame = ctk.CTkFrame(self.info_frame)
            frame.grid(row=i // 2, column=i % 2, sticky="nsew", padx=15, pady=15)
            frame.grid_columnconfigure(1, weight=1)
            sections[section_name] = {"frame": frame, "row": 1}
            ctk.CTkLabel(frame, text=section_name, font=("Arial", 14, "bold")).grid(
                row=0, column=0, columnspan=2, sticky="w", padx=15, pady=5
            )

        for field, config in self.entry_fields_expenses.items():
            section = sections[config["section"]]
            frame = section["frame"]
            row = section["row"]

            lbl = ctk.CTkLabel(frame, text=config["label"] + ":")
            lbl.grid(row=row, column=0, sticky="w", padx=(15, 5), pady=(5, 5))
            self.expense_info_labels[field] = lbl

            widget = self._build_widget(frame, field, config, expense_data)
            widget.grid(row=row, column=1, sticky="ew" if config["type"] != ctk.CTkLabel else "w", padx=(5, 15), pady=(5, 5))
            self.expense_info_widgets[field] = widget

            if field in validation_rules:
                validation_func, error_message = validation_rules[field]
                error_lbl = ctk.CTkLabel(frame, text="", text_color="#e8e5dc")
                error_lbl.grid(row=row + 1, column=1, sticky="w", padx=5, pady=(0, 10))
                self.error_labels_expenses[field] = error_lbl
                widget.bind(
                    "<FocusOut>",
                    lambda e, w=widget, vl=validation_func, el=error_lbl, em=error_message: ViewUtils.validate_entry(w, vl, el, em)
                )
                section["row"] += 2
            else:
                section["row"] += 1

        if self.expense_info_widgets[DBExpensesColumns.DEDUCIBILE.value].get() == "No":
            self.expense_info_widgets[self.USER_DEDUZIONE_FIELD].set("")

        self.toggle_linked_invoice_selection(self.expense_info_widgets[DBExpensesColumns.CATEGORY.value].get_value())

        buttons_frame = ctk.CTkFrame(self.info_frame, fg_color="#2b2b2b")
        buttons_frame.grid(row=2, column=0, columnspan=2, pady=(5, 15), padx=20, sticky="we")

        self.save_info_btn = ctk.CTkButton(buttons_frame, text="Salva Spesa", command=self.save_expense_mod)
        self.save_info_btn.pack(padx=(400, 10), pady=(20, 20), side="left")

        self.delete_btn = ctk.CTkButton(
            buttons_frame,
            text="Elimina Spesa",
            fg_color="#8B0000",
            hover_color="#A52A2A",
            command=self.delete_expense
        )
        self.delete_btn.pack(padx=10, pady=(20, 20), side="right", anchor="e")

    def _build_widget(self, frame, field, config, expense_data):
        widget_type = config["type"]

        if widget_type == ctk.CTkLabel:
            return widget_type(frame, text=str(expense_data.get(field, "")))

        if issubclass(widget_type, FilterableComboBox):
            combo_kwargs = {
                "values": config.get("values", []),
                "placeholder": "Cerca",
                "autofill": True,
                "command": config.get("command"),
            }
            if issubclass(widget_type, CatalogFilterableComboBox):
                combo_kwargs["add_button_text"] = config.get("add_button_text", "")
                combo_kwargs["add_button_command"] = config.get("add_button_command")

            widget = widget_type(frame, **combo_kwargs)
            widget.set_value(str(expense_data.get(field, "")), safe_mode=False)
            return widget

        if widget_type == ctk.CTkOptionMenu:
            widget = widget_type(frame, values=config.get("values", []))
            if "command" in config:
                widget.configure(command=config["command"])
            values = config.get("values", [""])
            widget.set(str(expense_data.get(field, values[0] if values else "")))
            return widget

        if widget_type == Calendar:
            widget = widget_type(frame, date_pattern=ViewUtils.date_pattern)
            value = expense_data.get(field, "")
            widget.selection_set(str(value) if value else datetime.today())
            return widget

        widget = widget_type(frame)
        widget.insert(0, str(expense_data.get(field, "")))
        return widget

    def toggle_edit(self, parent):
        state = ctk.NORMAL if self.switch_modify.get() else ctk.DISABLED
        self.save_info_btn.configure(state=state)
        self.delete_btn.configure(state=state)

        category = self.expense_info_widgets[DBExpensesColumns.CATEGORY.value].get_value()
        production_expense = dict(self.catalogo_elenchi["expenses_category"]).get("PRODUCTION_EXPENSE")

        for widget in parent.winfo_children():
            if isinstance(widget, ctk.CTkEntry):
                widget.configure(state=state, text_color="#636363" if state == ctk.DISABLED else "#c2c2c2")
            elif isinstance(widget, FilterableComboBox):
                widget.state = state
                widget._apply_state()
            elif isinstance(widget, ctk.CTkOptionMenu):
                widget.configure(state=state)
                if widget == self.expense_info_widgets[self.INVOICE_FIELD] and category != production_expense:
                    widget.configure(state=tk.DISABLED)
                if widget == self.expense_info_widgets[self.USER_DEDUZIONE_FIELD] and self.expense_info_widgets[DBExpensesColumns.DEDUCIBILE.value].get() == "No":
                    widget.configure(state=tk.DISABLED)
            elif isinstance(widget, Calendar):
                widget.configure(state=state)
            elif isinstance(widget, (ctk.CTkFrame, ctk.CTkScrollableFrame, ctk.CTkToplevel)):
                self.toggle_edit(widget)

    def _get_expense_category_values(self):
        return [value for key, value in self.catalogo_elenchi["expenses_category"] if key != "ADD_CATEGORY"]

    def expense_category_option_menu_behaviour(self, selected_value):
        self.toggle_linked_invoice_selection(selected_value)

    def toggle_linked_invoice_selection(self, selected_value):
        production_expense = dict(self.catalogo_elenchi["expenses_category"]).get("PRODUCTION_EXPENSE")
        widget = self.expense_info_widgets.get(self.INVOICE_FIELD)
        if widget is None:
            return

        if selected_value == production_expense:
            if self.switch_modify.get():
                widget.configure(state=tk.NORMAL)
        else:
            widget.set("Fattura non ancora emessa")
            widget.configure(state=tk.DISABLED)

    def toggle_user_deduzione(self, selected_value):
        widget = self.expense_info_widgets[self.USER_DEDUZIONE_FIELD]
        if selected_value == "Si":
            widget.configure(state=tk.NORMAL if self.switch_modify.get() else ctk.DISABLED)
            if not widget.get():
                values = widget.cget("values")
                if values:
                    widget.set(values[0])
        else:
            widget.set("")
            widget.configure(state=tk.DISABLED)

    def open_add_expenses_category(self):
        if self.add_category_window is not None and self.add_category_window.winfo_exists():
            self.add_category_window.focus()
            self.add_category_window.lift()
            return

        self.add_category_window = ctk.CTkToplevel(self)
        self.add_category_window.title("Aggiungi una nuova categoria di spesa")
        self.add_category_window.geometry("400x220")
        self.add_category_window.lift()
        self.add_category_window.grab_set()
        self.add_category_window.protocol("WM_DELETE_WINDOW", self._close_add_category_window)

        frame = ctk.CTkFrame(self.add_category_window)
        frame.pack(fill="both", expand=True)

        ctk.CTkLabel(
            frame,
            text="Aggiungi una categoria di spesa alla lista\nsepara parole diverse solo tramite spazio"
        ).pack(padx=10, pady=(25, 0))

        self.add_category_entry = ctk.CTkEntry(frame)
        self.add_category_entry.pack(padx=10, pady=5, fill="x", expand=True)

        ctk.CTkButton(frame, text="Aggiungi categoria", command=self.save_expenses_category).pack(
            padx=10, pady=(15, 10)
        )

    def save_expenses_category(self):
        new_category = self.add_category_entry.get().strip()
        if not new_category:
            ViewUtils.show_error_popup(self.add_category_window, "ERRORE", "Inserire una categoria valida.")
            return

        new_category_key = ControllerUtils.normalize_string_for_key(new_category)
        try:
            self.config_manager.update_list_field("expenses_category", new_category_key, new_category, "update")
        except Exception as e:
            ViewUtils.show_error_popup(self.add_category_window, "ERRORE", f"Impossibile aggiungere la nuova categoria: {str(e)}")
            return

        category_widget = self.expense_info_widgets[DBExpensesColumns.CATEGORY.value]
        updated_values = list(category_widget.all_values)
        if new_category not in updated_values:
            updated_values.append(new_category)
        category_widget.set_values(updated_values, preserve_current=False)
        category_widget.set_value(new_category, safe_mode=False)
        self._close_add_category_window()

    def _close_add_category_window(self):
        if self.add_category_window is not None and self.add_category_window.winfo_exists():
            self.add_category_window.destroy()
        self.add_category_window = None
        self.grab_set()

    def save_expense_mod(self):
        account = self.accounts_query_service.retrieve_account_map_by_name(self.expense_info_widgets[self.ACCOUNT_FIELD].get())
        supplier = self.suppliers_query_service.retrieve_supplier_map_by_name(self.expense_info_widgets[self.SUPPLIER_FIELD].get_value())

        user_deduzione = None
        if self.expense_info_widgets[self.USER_DEDUZIONE_FIELD].get():
            user_deduzione = self.user_query_service.retrieve_user_map_by_extended_name(
                self.expense_info_widgets[self.USER_DEDUZIONE_FIELD].get()
            )

        user_anticipo = None
        if self.expense_info_widgets[self.USER_ANTICIPO_FIELD].get():
            user_anticipo = self.user_query_service.retrieve_user_map_by_extended_name(
                self.expense_info_widgets[self.USER_ANTICIPO_FIELD].get()
            )

        invoice = None
        if self.expense_info_widgets[self.INVOICE_FIELD].get() != "Fattura non ancora emessa":
            invoice = self.invoices_query_service.retrieve_invoice_map_by_name(
                self.expense_info_widgets[self.INVOICE_FIELD].get()
            )

        expense_data = {
            DBExpensesColumns.DATE.value: self.expense_info_widgets[DBExpensesColumns.DATE.value].get_date(),
            DBExpensesColumns.SUPPLIER_ID.value: supplier[DBSuppliersColumns.ID.value] if supplier else None,
            DBExpensesColumns.USER_ID_DEDUZIONE.value: user_deduzione[DBUsersColumns.ID.value] if user_deduzione else None,
            DBExpensesColumns.USER_ID_ANTICIPO.value: user_anticipo[DBUsersColumns.ID.value] if user_anticipo else None,
            DBExpensesColumns.LINKED_INVOICE_ID.value: invoice[DBInvoicesColumns.ID.value] if invoice else None,
            DBExpensesColumns.ACCOUNT_ID.value: account[DBAccountsColumns.ID.value] if account else None,
            DBExpensesColumns.CATEGORY.value: self.expense_info_widgets[DBExpensesColumns.CATEGORY.value].get_value(),
            DBExpensesColumns.NET_AMOUNT.value: self.expense_info_widgets[DBExpensesColumns.NET_AMOUNT.value].get().strip(),
            DBExpensesColumns.IVA_AMOUNT.value: self.expense_info_widgets[DBExpensesColumns.IVA_AMOUNT.value].get().strip(),
            DBExpensesColumns.TOT_AMOUNT.value: self.expense_info_widgets[DBExpensesColumns.TOT_AMOUNT.value].get().strip(),
            DBExpensesColumns.DEDUCIBILE.value: self.expense_info_widgets[DBExpensesColumns.DEDUCIBILE.value].get(),
        }

        if not self.expense.get(DBExpensesColumns.RICORRENTE.value):
            expense_data[DBExpensesColumns.NAME.value] = self.expense_info_widgets[DBExpensesColumns.NAME.value].get().strip()

        success, message = self.expense_controller.update_expense(self.current_expense_id, expense_data)
        if not success:
            ViewUtils.show_error_popup(self.content_frame, "ERRORE", message)
            return

        self.update_controller.on_adding_expense()
        self.expense = self.expenses_query_service.retrieve_expense_map_by_id(self.current_expense_id)
        if self.expense:
            self.title_label.configure(text=self.expense[DBExpensesColumns.NAME.value])

        ViewUtils.show_confirm_popup_2(self.content_frame, "SALVATAGGIO COMPLETATO", message)
        self.switch_modify.deselect()
        self.toggle_edit(self.content_frame)

        if self.on_expense_changed:
            self.on_expense_changed()

        self.create_detail_tab(self.current_expense_id)

    def delete_expense(self):
        confirmation = ViewUtils.ask_confirmation_popup(
            self.content_frame,
            "Stai per eliminare questa spesa.\nDesideri continuare ?",
            "ELIMINAZIONE SPESA"
        )
        if not confirmation:
            return

        success, message = self.expense_controller.delete_expense(self.current_expense_id)
        if not success:
            ViewUtils.show_error_popup(self.content_frame, "ERRORE", message)
            return

        self.update_controller.on_adding_expense()
        ViewUtils.show_confirm_popup_2(self.content_frame, "SPESA ELIMINATA CON SUCCESSO", message)
        if self.on_expense_changed:
            self.on_expense_changed()
        self._cleanup_and_go_back()

    def _clear_content(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        self.switch_modify.deselect()

    def _cleanup_and_go_back(self):
        self._clear_content()
        self.pack_forget()
        self.back_callback()

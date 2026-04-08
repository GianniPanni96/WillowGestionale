import re
import tkinter as tk

import customtkinter as ctk
from tkcalendar import Calendar

from App_context import AppContext
from Controllerss.User_controller import UserController
from Utils.Controller_utils import ControllerUtils
from Gestionale_Enums import DBAccountsColumns, DBExpensesColumns, DBInvoicesColumns, DBSuppliersColumns, DBUsersColumns
from Views.View_utils import CatalogFilterableComboBox, FilterableComboBox, ViewUtils


class ExpenseCreateView(ctk.CTkToplevel):
    SUPPLIER_FIELD = "NOME FORNITORE"
    ACCOUNT_FIELD = "CONTO"
    USER_ANTICIPO_FIELD = "QUALCUNO HA ANTICIPATO?"
    IVA_FIELD = "ALIQUOTA IVA"
    INVOICE_FIELD = "FATTURA ASSOCIATA"
    USER_DEDUZIONE_FIELD = "DEDUZIONE A CARICO"

    def __init__(self, parent, app_context: AppContext, on_expense_created=None, on_close=None):
        super().__init__(parent)

        self.parent = parent
        self.app_context = app_context
        self.expense_controller = app_context.expense_controller
        self.expenses_query_service = app_context.expenses_query_service
        self.suppliers_query_service = app_context.suppliers_query_service
        self.invoices_query_service = app_context.invoices_query_service
        self.user_controller = app_context.user_controller
        self.account_controller = app_context.account_controller
        self.update_controller = app_context.update_controller
        self.config_manager = app_context.config_manager
        self.catalogo_elenchi = app_context.catalogo_elenchi
        self.fiscal_settings = app_context.fiscal_settings

        self.on_expense_created = on_expense_created
        self.on_close = on_close
        self.expense_widgets = {}
        self.error_labels = {}
        self.expense_labels = {}
        self.add_category_window = None
        self.name_prefix_label = None

        self.title("Aggiungi Nuova Spesa")
        self.geometry("550x700")
        self.lift()
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.scrollable_frame = ctk.CTkScrollableFrame(self)
        self.scrollable_frame.pack(fill="both", expand=True)

        self.entry_fields = {
            self.SUPPLIER_FIELD: FilterableComboBox,
            DBExpensesColumns.CATEGORY.value: CatalogFilterableComboBox,
            DBExpensesColumns.NAME.value: ctk.CTkEntry,
            DBExpensesColumns.DATE.value: Calendar,
            DBExpensesColumns.DEDUCIBILE.value: ctk.CTkOptionMenu,
            self.USER_DEDUZIONE_FIELD: ctk.CTkOptionMenu,
            self.IVA_FIELD: ctk.CTkOptionMenu,
            DBExpensesColumns.TOT_AMOUNT.value: ctk.CTkEntry,
            self.USER_ANTICIPO_FIELD: ctk.CTkOptionMenu,
            self.INVOICE_FIELD: ctk.CTkOptionMenu,
            self.ACCOUNT_FIELD: ctk.CTkOptionMenu,
        }

        self._build_form()
        self._bind_validations()
        self._initialize_default_values()

    def _build_form(self):
        for i, (label_text, widget_class) in enumerate(self.entry_fields.items()):
            label = ctk.CTkLabel(self.scrollable_frame, text=label_text)
            if label_text not in {self.INVOICE_FIELD, self.USER_DEDUZIONE_FIELD}:
                label.pack(pady=5 if i == 0 else (35, 0))
            self.expense_labels[label_text] = label

            widget = self._create_field_widget(label_text, widget_class)
            if label_text not in {self.INVOICE_FIELD, self.USER_DEDUZIONE_FIELD}:
                widget.pack(pady=5, padx=10, fill="x", expand=True)
            self.expense_widgets[label_text] = widget

            if label_text in {DBExpensesColumns.NAME.value, DBExpensesColumns.TOT_AMOUNT.value}:
                error_label = ctk.CTkLabel(self.scrollable_frame, text="")
                error_label.pack(pady=(0, 15))
                self.error_labels[label_text] = error_label

        self.linked_invoice_warning_label = ctk.CTkLabel(self.scrollable_frame, text="")
        self.linked_invoice_warning_label.pack_forget()

        self.save_button = ctk.CTkButton(
            self.scrollable_frame,
            text="Salva Spesa",
            command=self.save_expense_data
        )
        self.save_button.pack(pady=(50, 15))

    def _create_field_widget(self, label_text, widget_class):
        if label_text == self.SUPPLIER_FIELD:
            supplier_names = [
                supplier[DBSuppliersColumns.NAME.value]
                for supplier in self.suppliers_query_service.retrieve_suppliers_map_list(year=-1)
            ][::-1]
            return widget_class(
                parent=self.scrollable_frame,
                placeholder="Cerca",
                autofill=True,
                values=supplier_names,
                command=self.autofill_expense_name
            )

        if label_text == DBExpensesColumns.CATEGORY.value:
            return widget_class(
                parent=self.scrollable_frame,
                placeholder="Cerca",
                autofill=True,
                values=self._get_expense_category_values(),
                command=self.expense_category_option_menu_behaviour,
                add_button_text="Aggiungi categoria",
                add_button_command=self.open_add_expenses_category
            )

        if label_text == DBExpensesColumns.NAME.value:
            name_frame = ctk.CTkFrame(self.scrollable_frame)
            name_frame.pack(pady=0, padx=0, fill="x", expand=True)
            self.name_prefix_label = ctk.CTkLabel(name_frame, text="")
            self.name_prefix_label.pack(side=tk.LEFT, pady=5, padx=(10, 0))
            return widget_class(name_frame)

        if label_text == DBExpensesColumns.DATE.value:
            return widget_class(self.scrollable_frame, date_pattern=ViewUtils.date_pattern)

        if label_text == DBExpensesColumns.DEDUCIBILE.value:
            return widget_class(
                self.scrollable_frame,
                values=["Si", "No"],
                command=self.toggle_user_deduzione
            )

        if label_text == self.USER_DEDUZIONE_FIELD:
            users = [
                f"{user[DBUsersColumns.FIRST_NAME.value]} {user[DBUsersColumns.LAST_NAME.value]}"
                for user in self.user_controller.retrieve_users_map_list()
                if user[DBUsersColumns.REGIME_FISCALE.value] == UserController.RegimeFiscale.ORDINARIO.value
            ]
            return widget_class(self.scrollable_frame, values=users)

        if label_text == self.USER_ANTICIPO_FIELD:
            users = [
                f"{user[DBUsersColumns.FIRST_NAME.value]} {user[DBUsersColumns.LAST_NAME.value]}"
                for user in self.user_controller.retrieve_users_map_list()
            ]
            return widget_class(self.scrollable_frame, values=[" ----- "] + users)

        if label_text == self.IVA_FIELD:
            aliquote_list = [
                self.fiscal_settings.aliquota_iva.no_iva,
                self.fiscal_settings.aliquota_iva.aliquota_iva_ordinaria,
                self.fiscal_settings.aliquota_iva.aliquota_iva_ridotta_1,
                self.fiscal_settings.aliquota_iva.aliquota_iva_ridotta_2,
                self.fiscal_settings.aliquota_iva.aliquota_iva_minima,
            ]
            return widget_class(self.scrollable_frame, values=[str(aliquota) for aliquota in aliquote_list])

        if label_text == self.INVOICE_FIELD:
            invoices = self.invoices_query_service.retrieve_invoices_map_list(year=-1, include_unpaid_invoices=True)
            values = ["Fattura non ancora emessa"] + [
                invoice[DBInvoicesColumns.NUMERO_FATTURA.value]
                for invoice in invoices
            ]
            return widget_class(
                self.scrollable_frame,
                values=values,
                command=self.linked_invoice_option_menu_behaviour
            )

        if label_text == self.ACCOUNT_FIELD:
            accounts = self.account_controller.retrieve_accounts_map_list()
            return widget_class(
                self.scrollable_frame,
                values=[account[DBAccountsColumns.NAME.value] for account in accounts]
            )

        return widget_class(self.scrollable_frame)

    def _bind_validations(self):
        self.expense_widgets[DBExpensesColumns.NAME.value].bind(
            "<FocusOut>",
            lambda event: ViewUtils.validate_entry(
                self.expense_widgets[DBExpensesColumns.NAME.value],
                lambda val: val.strip() != "",
                self.error_labels[DBExpensesColumns.NAME.value],
                "Il campo non puo essere vuoto."
            )
        )

        self.expense_widgets[DBExpensesColumns.TOT_AMOUNT.value].bind(
            "<FocusOut>",
            lambda event: ViewUtils.validate_entry(
                self.expense_widgets[DBExpensesColumns.TOT_AMOUNT.value],
                lambda val: re.fullmatch(r"^\d+(\.\d{1,2})?$", val.strip()) is not None,
                self.error_labels[DBExpensesColumns.TOT_AMOUNT.value],
                "Inserimento non valido: inserire un numero monetario con massimo due cifre decimali"
            )
        )

    def _initialize_default_values(self):
        supplier_value = self.expense_widgets[self.SUPPLIER_FIELD].get_value()
        if supplier_value:
            self.autofill_expense_name(supplier_value)

        self.expense_widgets[DBExpensesColumns.DEDUCIBILE.value].set("No")

        deduzione_values = self.expense_widgets[self.USER_DEDUZIONE_FIELD].cget("values")
        if deduzione_values:
            self.expense_widgets[self.USER_DEDUZIONE_FIELD].set(deduzione_values[0])

        self.expense_widgets[DBExpensesColumns.CATEGORY.value].set_value(
            dict(self.catalogo_elenchi["expenses_category"]).get("CONSUMABLE_FOR_STUDIO", ""),
            safe_mode=False
        )
        self.expense_category_option_menu_behaviour(self.expense_widgets[DBExpensesColumns.CATEGORY.value].get_value())

        self.expense_widgets[self.USER_ANTICIPO_FIELD].set(" ----- ")
        self.expense_widgets[self.INVOICE_FIELD].set("Fattura non ancora emessa")
        self.expense_widgets[self.IVA_FIELD].set(str(self.fiscal_settings.aliquota_iva.aliquota_iva_ordinaria))

        account_values = self.expense_widgets[self.ACCOUNT_FIELD].cget("values")
        if account_values:
            self.expense_widgets[self.ACCOUNT_FIELD].set(account_values[0])

    def _get_expense_category_values(self):
        return [
            value for key, value in self.catalogo_elenchi["expenses_category"]
            if key != "ADD_CATEGORY"
        ]

    def autofill_expense_name(self, selected_value):
        if self.name_prefix_label is not None:
            self.name_prefix_label.configure(text=f"{selected_value} - ")

    def expense_category_option_menu_behaviour(self, selected_value):
        self.toggle_linked_invoice_selection(selected_value)

    def linked_invoice_option_menu_behaviour(self, selected_value):
        if selected_value == "Fattura non ancora emessa":
            self.linked_invoice_warning_label.configure(text="")
            self.linked_invoice_warning_label.pack_forget()
            return

        warning = (
            "Attenzione: la spesa verra collegata alla fattura selezionata.\n"
            "Verifica che la categoria sia davvero una spesa di produzione."
        )
        self.linked_invoice_warning_label.configure(text=warning, text_color="#e39e27")
        self.linked_invoice_warning_label.pack(pady=(5, 0))

    def toggle_linked_invoice_selection(self, selected_value):
        production_expense = dict(self.catalogo_elenchi["expenses_category"]).get("PRODUCTION_EXPENSE")
        widget = self.expense_widgets[self.INVOICE_FIELD]
        label = self.expense_labels[self.INVOICE_FIELD]

        if selected_value == production_expense:
            if not label.winfo_manager():
                label.pack(pady=(35, 0))
            if not widget.winfo_manager():
                widget.pack(pady=5, padx=10, fill="x", expand=True)
            widget.configure(state=tk.NORMAL)
        else:
            if self.linked_invoice_warning_label.winfo_manager():
                self.linked_invoice_warning_label.pack_forget()
            widget.set("Fattura non ancora emessa")
            widget.pack_forget()
            label.pack_forget()

    def toggle_user_deduzione(self, selected_value):
        widget = self.expense_widgets[self.USER_DEDUZIONE_FIELD]
        label = self.expense_labels[self.USER_DEDUZIONE_FIELD]

        if selected_value == "Si":
            if not label.winfo_manager():
                label.pack(pady=(35, 0))
            if not widget.winfo_manager():
                widget.pack(pady=5, padx=10, fill="x", expand=True)
            widget.configure(state=tk.NORMAL)
        else:
            widget.set("")
            widget.pack_forget()
            label.pack_forget()

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

        category_widget = self.expense_widgets[DBExpensesColumns.CATEGORY.value]
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

    def _collect_expense_data(self):
        expense_data = {}
        for label_text, widget in self.expense_widgets.items():
            if isinstance(widget, (ctk.CTkEntry, ctk.CTkOptionMenu)):
                expense_data[label_text] = str(widget.get()).strip()
            elif isinstance(widget, Calendar):
                expense_data[label_text] = widget.get_date()
            elif isinstance(widget, FilterableComboBox):
                expense_data[label_text] = widget.get_value()
        return expense_data

    def save_expense_data(self):
        expense_data = self._collect_expense_data()

        if not expense_data.get(DBExpensesColumns.CATEGORY.value):
            ViewUtils.show_error_popup(self, "ERRORE", "Categoria non valida.")
            return

        category_dict = dict(self.catalogo_elenchi["expenses_category"])
        if expense_data.get(DBExpensesColumns.CATEGORY.value) != category_dict.get("PRODUCTION_EXPENSE"):
            expense_data.pop(self.INVOICE_FIELD, None)

        if expense_data.get(DBExpensesColumns.DEDUCIBILE.value) == "No":
            expense_data[self.USER_DEDUZIONE_FIELD] = None

        success, message = self.expense_controller.save_expense(expense_data)
        if not success:
            ViewUtils.show_error_popup(self, "ERRORE", message)
            return

        self.update_controller.on_adding_expense()

        expense_map = self.expenses_query_service.retrieve_last_expense_insert_map()
        expense_id = expense_map[DBExpensesColumns.ID.value] if expense_map else None

        if self.on_expense_created:
            self.on_expense_created(expense_id, expense_map)

        self._on_close()

    def _on_close(self):
        try:
            self.grab_release()
        except Exception:
            pass

        if self.on_close:
            self.on_close()

        self.destroy()

import re

import customtkinter as ctk
from tkcalendar import Calendar

from App_context import AppContext
from Gestionale_Enums import*
from QueryServices.Account_query_service import AccountQueryService
from Views.View_utils import ViewUtils
from Views.CustomWidgets.Filterable_combo_box import FilterableComboBox

from Controllerss.Refund_controller import RefundController

from QueryServices.Refunds_query_service import RefundQueryService
from QueryServices.Clients_query_service import ClientQueryService


class RefundCreateView(ctk.CTkToplevel):
    """
    Finestra modale per la creazione di un nuovo rimborso.
    """

    CLIENT_NAME_FIELD = "NOME CLIENTE"
    ACCOUNT_NAME_FIELD = "NOME CONTO"

    def __init__(self, parent, app_context: AppContext, on_refund_created=None, on_close=None):
        super().__init__(parent)

        self.app_context = app_context
        self.refund_controller:RefundController = app_context.refund_controller
        self.refunds_query_service:RefundQueryService = app_context.refunds_query_service
        self.clients_query_service:ClientQueryService = app_context.clients_query_service
        self.accounts_query_service:AccountQueryService = app_context.account_query_service


        self.on_refund_created = on_refund_created
        self.on_close = on_close

        self.entry_fields = {
            DBRefundsColumns.REFUND_NAME.value: ctk.CTkEntry,
            DBRefundsColumns.REFUND_AMOUNT.value: ctk.CTkEntry,
            DBRefundsColumns.REFUND_DATE.value: Calendar,
            self.CLIENT_NAME_FIELD: FilterableComboBox,
            self.ACCOUNT_NAME_FIELD: ctk.CTkOptionMenu,
        }
        self.error_fields = {
            DBRefundsColumns.REFUND_NAME.value: ctk.CTkLabel,
            DBRefundsColumns.REFUND_AMOUNT.value: ctk.CTkLabel,
        }

        self.refund_widgets = {}
        self.error_labels = {}
        self.refund_labels = {}

        self.title("Aggiungi Nuovo Rimborso")
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
            self.refund_labels[label_text] = label

            widget = self._create_field_widget(label_text, widget_class)
            widget.pack(pady=5, padx=10, fill="x", expand=True)
            self.refund_widgets[label_text] = widget

            if self.error_fields.get(label_text) is not None:
                error_label = ctk.CTkLabel(self.scrollable_frame, text="")
                error_label.pack(pady=(0, 15))
                self.error_labels[label_text] = error_label

        self.save_button = ctk.CTkButton(
            self.scrollable_frame,
            text="Salva Rimborso",
            command=self.save_refund_data
        )
        self.save_button.pack(pady=(35, 15))

    def _create_field_widget(self, label_text, widget_class):
        if label_text == self.ACCOUNT_NAME_FIELD:
            return widget_class(
                self.scrollable_frame,
                values=[item[DBAccountsColumns.NAME.value] for item in self.accounts_query_service.retrieve_accounts_map_list()]
            )

        if label_text == self.CLIENT_NAME_FIELD:
            return widget_class(
                parent=self.scrollable_frame,
                placeholder="Cerca",
                autofill=True,
                values=[item[DBClientsColumns.NAME.value] for item in self.clients_query_service.retrieve_clients_map_list()]
            )

        if label_text == DBRefundsColumns.REFUND_DATE.value:
            return widget_class(self.scrollable_frame, date_pattern=ViewUtils.date_pattern)

        return widget_class(self.scrollable_frame)

    def _bind_validations(self):
        self.refund_widgets[DBRefundsColumns.REFUND_NAME.value].bind(
            "<FocusOut>",
            lambda event: ViewUtils.validate_entry(
                self.refund_widgets[DBRefundsColumns.REFUND_NAME.value],
                lambda val: val.strip() != "",
                self.error_labels[DBRefundsColumns.REFUND_NAME.value],
                "Il campo non puo essere vuoto."
            )
        )

        self.refund_widgets[DBRefundsColumns.REFUND_AMOUNT.value].bind(
            "<FocusOut>",
            lambda event: ViewUtils.validate_entry(
                self.refund_widgets[DBRefundsColumns.REFUND_AMOUNT.value],
                lambda val: re.fullmatch(r"^\d+(\.\d{2})?$", val.strip()) is not None,
                self.error_labels[DBRefundsColumns.REFUND_AMOUNT.value],
                "Inserimento non valido: inserire un numero monetario con due cifre decimali (es. 123.45)"
            )
        )

    def _initialize_default_values(self):
        clients = self.clients_query_service.retrieve_clients_map_list()
        if clients:
            self.refund_widgets[self.CLIENT_NAME_FIELD].set_value(clients[0][DBClientsColumns.NAME.value], safe_mode=False)

        accounts = self.accounts_query_service.retrieve_accounts_map_list()
        if accounts:
            self.refund_widgets[self.ACCOUNT_NAME_FIELD].set(accounts[0][DBAccountsColumns.NAME.value])

    def _collect_refund_data(self):
        refund_data = {}
        for label_text, widget in self.refund_widgets.items():
            if isinstance(widget, (ctk.CTkEntry, ctk.CTkOptionMenu)):
                refund_data[label_text] = str(widget.get()).strip()
            elif isinstance(widget, Calendar):
                refund_data[label_text] = widget.get_date()
            elif isinstance(widget, FilterableComboBox):
                refund_data[label_text] = widget.get_value()
        return refund_data

    def save_refund_data(self):
        refund_data = self._collect_refund_data()
        success, message = self.refund_controller.save_refund(refund_data)

        if not success:
            ViewUtils.show_error_popup(self, "ERRORE", message)
            return

        refund_map = self.refunds_query_service.retrieve_last_refund_insert_map()
        refund_id = refund_map[DBRefundsColumns.ID.value] if refund_map else None

        if self.on_refund_created:
            self.on_refund_created(refund_id, refund_map)

        self._on_close()

    def _on_close(self):
        try:
            self.grab_release()
        except Exception:
            pass

        if self.on_close:
            self.on_close()

        self.destroy()

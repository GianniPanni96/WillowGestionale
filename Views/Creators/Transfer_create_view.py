import re

import customtkinter as ctk

from App_context import AppContext
from Gestionale_Enums import DBAccountsColumns, DBTransfersColumns
from Views.View_utils import ViewUtils


class TransferCreateView(ctk.CTkToplevel):
    """
    Toplevel modale per l'inserimento di un trasferimento bancario.
    """

    RECEIVER_ACCOUNT_LABEL = "CONTO RICEVENTE"

    def __init__(
        self,
        parent,
        app_context: AppContext,
        sender_account_id: int,
        on_transfer_created=None,
        on_close=None,
    ):
        super().__init__(parent)

        self.app_context = app_context
        self.sender_account_id = sender_account_id
        self.account_query_service = app_context.account_query_service
        self.transfer_controller = app_context.transfer_controller
        self.update_controller = app_context.update_controller
        self.on_transfer_created = on_transfer_created
        self.on_close = on_close

        self.transfer_widgets = {}
        self.transfer_labels = {}
        self.error_labels = {}

        self.entry_fields = {
            DBTransfersColumns.DESCRIPTION.value: ctk.CTkEntry,
            DBTransfersColumns.AMOUNT.value: ctk.CTkEntry,
            self.RECEIVER_ACCOUNT_LABEL: ctk.CTkOptionMenu,
        }
        self.error_fields = {
            DBTransfersColumns.DESCRIPTION.value: ctk.CTkLabel,
            DBTransfersColumns.AMOUNT.value: ctk.CTkLabel,
        }

        self.title("Esegui Bonifico")
        self.geometry("550x500")
        self.lift()
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.scrollable_frame = ctk.CTkScrollableFrame(self)
        self.scrollable_frame.pack(fill="both", expand=True)

        self._build_form()
        self._bind_validations()

    def _build_form(self):
        accounts_map_list = self.account_query_service.retrieve_accounts_map_list()
        self.accounts_name_list = [
            account[DBAccountsColumns.NAME.value]
            for account in accounts_map_list
            if account[DBAccountsColumns.ID.value] != self.sender_account_id
        ]

        for i, (label_text, widget_class) in enumerate(self.entry_fields.items()):
            label = ctk.CTkLabel(self.scrollable_frame, text=label_text)
            label.pack(pady=5 if i == 0 else (35, 0))
            self.transfer_labels[label_text] = label

            widget = self._create_widget(label_text, widget_class)
            widget.pack(pady=5, padx=(0, 10), fill="x", expand=True)
            self.transfer_widgets[label_text] = widget

            if self.error_fields.get(label_text) is not None:
                error_label = ctk.CTkLabel(self.scrollable_frame, text="")
                error_label.pack(pady=(0, 15))
                self.error_labels[label_text] = error_label

        self.save_button = ctk.CTkButton(
            self.scrollable_frame,
            text="Esegui Bonifico",
            command=self.save_transfer_data,
        )
        self.save_button.pack(pady=(85, 15))

        if len(self.accounts_name_list) == 0:
            self.transfer_widgets[self.RECEIVER_ACCOUNT_LABEL].set("Nessun altro conto esistente nel sistema")
            self.save_button.configure(state=ctk.DISABLED)

    def _create_widget(self, label_text, widget_class):
        if label_text == self.RECEIVER_ACCOUNT_LABEL:
            return widget_class(
                self.scrollable_frame,
                values=self.accounts_name_list,
            )
        return widget_class(self.scrollable_frame)

    def _bind_validations(self):
        self.transfer_widgets[DBTransfersColumns.DESCRIPTION.value].bind(
            "<FocusOut>",
            lambda event: ViewUtils.validate_entry(
                self.transfer_widgets[DBTransfersColumns.DESCRIPTION.value],
                lambda val: val.strip() != "",
                self.error_labels[DBTransfersColumns.DESCRIPTION.value],
                "Il campo non può essere vuoto.",
            ),
        )

        self.transfer_widgets[DBTransfersColumns.AMOUNT.value].bind(
            "<FocusOut>",
            lambda event: ViewUtils.validate_entry(
                self.transfer_widgets[DBTransfersColumns.AMOUNT.value],
                lambda val: re.fullmatch(r"^\d+(\.\d{2})?$", val.strip()) is not None,
                self.error_labels[DBTransfersColumns.AMOUNT.value],
                "Inserimento non valido: inserire un numero monetario con due cifre decimali (es. 123.45)",
            ),
        )

    def save_transfer_data(self):
        transfer_data = {}

        for label_text, widget in self.transfer_widgets.items():
            if isinstance(widget, (ctk.CTkEntry, ctk.CTkOptionMenu)):
                transfer_data[label_text] = widget.get().strip()

        transfer_data[DBTransfersColumns.SENDER_ACCOUNT_ID.value] = self.sender_account_id
        success, message = self.transfer_controller.save_transfer(transfer_data)

        if not success:
            ViewUtils.show_error_popup(self, "ERRORE", message)
            return

        self.update_controller.on_adding_transfer()

        if self.on_transfer_created:
            self.on_transfer_created(transfer_data)

        self.clear_class_variable()
        self._on_close()

    def clear_class_variable(self):
        self.transfer_widgets.clear()
        self.transfer_labels.clear()

    def _on_close(self):
        try:
            self.grab_release()
        except Exception:
            pass

        if self.on_close:
            self.on_close()

        self.destroy()

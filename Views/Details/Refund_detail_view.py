import re
from datetime import datetime

import customtkinter as ctk
from tkcalendar import Calendar

from App_context import AppContext
from Gestionale_Enums import*
from Views.View_utils import ViewUtils

from Controllerss.Refund_controller import RefundController
from Controllerss.Client_controller import ClientController
from Controllers import AccountController

from QueryServices.Refunds_query_service import RefundQueryService
from QueryServices.Clients_query_service import ClientQueryService



class RefundDetailView(ctk.CTkFrame):
    """
    Vista dettaglio rimborso separata dalla list view.
    """

    CLIENT_LABEL = "CLIENTE ASSOCIATO"
    ACCOUNT_LABEL = "CONTO"

    def __init__(self, parent, app_context: AppContext, back_callback, on_refund_changed=None):
        super().__init__(parent)
        self.parent = parent
        self.app_context = app_context
        self.back_callback = back_callback
        self.on_refund_changed = on_refund_changed

        self.refund_controller: RefundController = app_context.refund_controller
        self.refunds_query_service: RefundQueryService = app_context.refunds_query_service
        self.clients_query_service:ClientQueryService = app_context.clients_query_service
        self.account_controller:AccountController = app_context.account_controller
        self.current_refund_id = None

        self.configure(fg_color="transparent")

        self.head_frame = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.back_button = ctk.CTkButton(
            self.head_frame,
            text="Elenco Rimborsi",
            command=self._cleanup_and_go_back
        )
        self.title_label = ctk.CTkLabel(self.head_frame, font=("Arial", 22, "bold"))
        self.switch_modify = ctk.CTkSwitch(
            self.head_frame,
            text="Abilita la modifica",
            command=lambda: self.toggle_edit(self.content_frame)
        )
        self.content_frame = ctk.CTkScrollableFrame(self)

        self.refund_info_widgets = {}
        self.refund_info_labels = {}
        self.error_labels_refunds = {}

        self._setup_base_layout()

    def _setup_base_layout(self):
        self.head_frame.pack(fill="x", pady=5, padx=5)
        self.back_button.pack(anchor="w", side="left", pady=10, padx=10)
        self.title_label.pack(anchor="c", side="left", fill="x", expand=True, pady=10)
        self.switch_modify.pack(anchor="e", side="left", pady=10, padx=10)
        self.content_frame.pack(fill="both", expand=True, pady=20, padx=20)

    def create_detail_tab(self, refund_id):
        self.current_refund_id = refund_id
        self._clear_content()

        self.refund = self.refunds_query_service.retrieve_refund_map_by_id(refund_id)
        if not self.refund:
            return

        self.title_label.configure(text=self.refund[DBRefundsColumns.REFUND_NAME.value])
        self._create_refund_info_section(self.refund)
        self.toggle_edit(self.content_frame)

    def _create_refund_info_section(self, refund_data):
        self.entry_fields_refunds = {
            DBRefundsColumns.REFUND_NAME.value: {
                "type": ctk.CTkEntry,
                "label": "Nome Rimborso",
                "section": "Dati Generali"
            },
            DBRefundsColumns.REFUND_DATE.value: {
                "type": Calendar,
                "label": "Data Rimborso",
                "section": "Dati Generali"
            },
            DBRefundsColumns.REFUND_AMOUNT.value: {
                "type": ctk.CTkEntry,
                "label": "Importo Rimborsato (EUR)",
                "section": "Dati Fiscali"
            },
            self.CLIENT_LABEL: {
                "type": ctk.CTkOptionMenu,
                "label": "Cliente",
                "section": "Collegamenti",
                "values": [c[DBClientsColumns.NAME.value] for c in self.clients_query_service.retrieve_clients_map_list()]
            },
            self.ACCOUNT_LABEL: {
                "type": ctk.CTkOptionMenu,
                "label": "Conto",
                "section": "Collegamenti",
                "values": [a[DBAccountsColumns.NAME.value] for a in self.account_controller.retrieve_accounts_map_list()]
            },
            DBRefundsColumns.CREATED_AT.value: {
                "type": ctk.CTkLabel,
                "label": "Data Creazione",
                "section": "Note"
            },
            DBRefundsColumns.UPDATED_AT.value: {
                "type": ctk.CTkLabel,
                "label": "Ultimo Aggiornamento",
                "section": "Note"
            }
        }

        validation_rules = {
            DBRefundsColumns.REFUND_AMOUNT.value: (
                lambda val: re.fullmatch(r"^\d+(\.\d{1,2})?$", val),
                "Formato valido: 1234.56"
            ),
            DBRefundsColumns.REFUND_DATE.value: (
                lambda val: val.strip() != "",
                "Campo obbligatorio"
            ),
            DBRefundsColumns.REFUND_NAME.value: (
                lambda val: val.strip() != "",
                "Campo obbligatorio"
            )
        }

        self.refund_info_widgets = {}
        self.refund_info_labels = {}
        self.error_labels_refunds = {}
        sections = {}

        info_frame = ctk.CTkFrame(self.content_frame, border_width=2, border_color="#2659ab")
        info_frame.pack(fill="both", expand=True, pady=(5, 10), padx=(5, 25))
        info_frame.grid_columnconfigure(0, weight=1, uniform="col")
        info_frame.grid_columnconfigure(1, weight=1, uniform="col")
        self.info_frame = info_frame

        for i, section_name in enumerate(["Dati Generali", "Dati Fiscali", "Collegamenti", "Note"]):
            frame = ctk.CTkFrame(info_frame)
            frame.grid(row=i // 2, column=i % 2, sticky="nsew", padx=15, pady=15)
            frame.grid_columnconfigure(1, weight=1)
            sections[section_name] = {"frame": frame, "row": 1}
            ctk.CTkLabel(frame, text=section_name, font=("Arial", 14, "bold")).grid(
                row=0, column=0, columnspan=2, sticky="w", padx=15, pady=5
            )

        for field, config in self.entry_fields_refunds.items():
            section = sections[config["section"]]
            frame = section["frame"]
            row = section["row"]

            lbl = ctk.CTkLabel(frame, text=config["label"] + ":")
            lbl.grid(row=row, column=0, sticky="w", padx=(15, 5), pady=(5, 5))
            self.refund_info_labels[field] = lbl

            widget = self._build_widget(frame, field, config, refund_data)
            widget.grid(row=row, column=1, sticky="ew" if config["type"] != ctk.CTkLabel else "w", padx=(5, 15), pady=(5, 5))
            self.refund_info_widgets[field] = widget

            if field in validation_rules:
                validation_func, error_message = validation_rules[field]
                error_lbl = ctk.CTkLabel(frame, text="", text_color="#e8e5dc")
                error_lbl.grid(row=row + 1, column=1, sticky="w", padx=5, pady=(0, 10))
                self.error_labels_refunds[field] = error_lbl
                widget.bind(
                    "<FocusOut>",
                    lambda e, w=widget, vl=validation_func, el=error_lbl, em=error_message: ViewUtils.validate_entry(w, vl, el, em)
                )
                section["row"] += 2
            else:
                section["row"] += 1

        buttons_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        buttons_frame.grid(row=2, column=0, columnspan=2, pady=(5, 15), padx=20, sticky="nswe")

        self.save_info_btn = ctk.CTkButton(buttons_frame, text="Salva Rimborso", command=self.save_refund_mod)
        self.save_info_btn.pack(padx=(400, 10), pady=(20, 20), side="left")

        self.delete_btn = ctk.CTkButton(
            buttons_frame,
            text="Elimina Rimborso",
            fg_color="#8B0000",
            hover_color="#A52A2A",
            command=self.delete_refund
        )
        self.delete_btn.pack(padx=10, pady=(20, 20), side="right", anchor="e")

    def _build_widget(self, frame, field, config, refund_data):
        if config["type"] == ctk.CTkLabel:
            return config["type"](frame, text=str(refund_data.get(field, "")))

        if config["type"] == ctk.CTkOptionMenu:
            widget = config["type"](frame, values=config.get("values", []))
            if field == self.CLIENT_LABEL:
                client = self.clients_query_service.retrieve_client_map_by_id(refund_data.get(DBRefundsColumns.CLIENT_ID.value))
                widget.set(client[DBClientsColumns.NAME.value] if client else "")
            elif field == self.ACCOUNT_LABEL:
                account = self.account_controller.retrieve_account_map_by_id(refund_data.get(DBRefundsColumns.CONTO_ID.value))
                widget.set(account[DBAccountsColumns.NAME.value] if account else "")
            else:
                values = config.get("values", [""])
                widget.set(refund_data.get(field, values[0] if values else ""))
            return widget

        if config["type"] == Calendar:
            widget = config["type"](frame, date_pattern=ViewUtils.date_pattern)
            value = refund_data.get(field, "")
            widget.selection_set(str(value) if value else datetime.today())
            return widget

        widget = config["type"](frame)
        widget.insert(0, str(refund_data.get(field, "")))
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

    def save_refund_mod(self):
        account_name = self.refund_info_widgets[self.ACCOUNT_LABEL].get()
        account = self.account_controller.retrieve_account_map_by_name(account_name)
        client_name = self.refund_info_widgets[self.CLIENT_LABEL].get()
        client = self.clients_query_service.retrieve_client_map_by_name(client_name)

        refund_data = {
            DBRefundsColumns.REFUND_NAME.value: self.refund_info_widgets[DBRefundsColumns.REFUND_NAME.value].get().strip(),
            DBRefundsColumns.REFUND_DATE.value: self.refund_info_widgets[DBRefundsColumns.REFUND_DATE.value].get_date(),
            DBRefundsColumns.REFUND_AMOUNT.value: self.refund_info_widgets[DBRefundsColumns.REFUND_AMOUNT.value].get().strip(),
            DBRefundsColumns.CLIENT_ID.value: client[DBClientsColumns.ID.value] if client else None,
            DBRefundsColumns.CONTO_ID.value: account[DBAccountsColumns.ID.value] if account else None,
        }

        success, message = self.refund_controller.update_refund(self.current_refund_id, refund_data)
        if success:
            self.refund = self.refunds_query_service.retrieve_refund_map_by_id(self.current_refund_id)
            if self.refund:
                self.title_label.configure(text=self.refund[DBRefundsColumns.REFUND_NAME.value])
            ViewUtils.show_confirm_popup_2(self.content_frame, "SALVATAGGIO COMPLETATO", message)
            self.switch_modify.deselect()
            self.toggle_edit(self.content_frame)
            if self.on_refund_changed:
                self.on_refund_changed()
        else:
            ViewUtils.show_error_popup(self.content_frame, "ERRORE", message)

    def delete_refund(self):
        confirmation = ViewUtils.ask_confirmation_popup(
            self.content_frame,
            "Stai per eliminare questo rimborso.\nDesideri continuare ?",
            "ELIMINAZIONE RIMBORSO"
        )
        if not confirmation:
            return

        success, message = self.refund_controller.delete_refund(self.current_refund_id)
        if success:
            ViewUtils.show_confirm_popup_2(self.content_frame, "RIMBORSO ELIMINATO CON SUCCESSO", message)
            if self.on_refund_changed:
                self.on_refund_changed()
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

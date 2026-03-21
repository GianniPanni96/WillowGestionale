import customtkinter as ctk

from Model import DBClientsColumns
from Views.View_utils import FilterableComboBox, ViewUtils
from Views.Business_sector_create_view import BusinessSectorCreateView

from App_context import AppContext

from Gestionale_Enums import *


class ClientCreateView(ctk.CTkToplevel):
    def __init__(self, parent, app_context: AppContext, on_client_created=None, on_close=None):
        super().__init__(parent)

        self.app_context = app_context
        self.client_controller = app_context.client_controller
        self.clients_query_service = app_context.clients_query_service
        self.catalogo_elenchi = app_context.catalogo_elenchi
        self.config_manager = app_context.config_manager

        self.on_client_created = on_client_created
        self.on_close = on_close

        self.entry_fields = {
            DBClientsColumns.NAME.value: ctk.CTkEntry,
            DBClientsColumns.TIPOLOGIA.value: ctk.CTkOptionMenu,
            DBClientsColumns.PARTITA_IVA.value: ctk.CTkEntry,
            DBClientsColumns.EMAIL.value: ctk.CTkEntry,
            DBClientsColumns.SEDE_LEGALE.value: ctk.CTkEntry,
            DBClientsColumns.SETTORE.value: FilterableComboBox,
            DBClientsColumns.REFERENTE.value: ctk.CTkEntry,
            DBClientsColumns.CONTATTO_REFERENTE.value: ctk.CTkEntry,
            DBClientsColumns.NOTE.value: ctk.CTkTextbox,
        }
        self.error_fields = {
            DBClientsColumns.NAME.value: ctk.CTkLabel,
            DBClientsColumns.PARTITA_IVA.value: ctk.CTkLabel,
            DBClientsColumns.EMAIL.value: ctk.CTkLabel,
            DBClientsColumns.SEDE_LEGALE.value: ctk.CTkLabel,
            DBClientsColumns.SETTORE.value: ctk.CTkLabel,
        }
        self.field_labels = {}
        self.client_widgets = {}
        self.error_labels = {}
        self.business_sector_create_view = None

        self.title("Aggiungi Nuovo Cliente")
        self.geometry("400x700")
        self.lift()
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.scrollable_frame = ctk.CTkScrollableFrame(self)
        self.scrollable_frame.pack(fill="both", expand=True)

        self._build_form()
        self._bind_validations()

    def _build_form(self):
        for i, (label_text, widget_class) in enumerate(self.entry_fields.items()):
            label = ctk.CTkLabel(self.scrollable_frame, text=label_text)
            label.pack(pady=5 if i == 0 else (35, 0))
            self.field_labels[label_text] = label

            widget = self._create_field_widget(label_text, widget_class)
            widget.pack(pady=5, padx=10, fill="x", expand=True)

            if self.error_fields.get(label_text) is not None:
                error_label = ctk.CTkLabel(self.scrollable_frame, text="")
                error_label.pack(pady=(0, 15))
                self.error_labels[label_text] = error_label

            self.client_widgets[label_text] = widget

        self.save_button = ctk.CTkButton(
            self.scrollable_frame,
            text="Salva Cliente",
            command=self.save_client_data
        )
        self.save_button.pack(pady=(35, 15))

    def _create_field_widget(self, label_text, widget_class):
        if label_text == DBClientsColumns.TIPOLOGIA.value:
            widget = widget_class(
                self.scrollable_frame,
                values=[item.value for item in TipologiaCliente]
            )
            widget.set(TipologiaCliente.PRIVATO.value)
            return widget

        if label_text == DBClientsColumns.SETTORE.value:
            widget = widget_class(
                parent=self.scrollable_frame,
                placeholder="Cerca",
                autofill=True,
                values=[value for _, value in self.catalogo_elenchi["clients_business_sectors"]],
                command=self._handle_business_sector_selection
            )
            widget.set_value(BusinessSector.CREATIVE_AGENCY.value)
            return widget

        return widget_class(self.scrollable_frame)

    def _bind_validations(self):
        self.client_widgets[DBClientsColumns.NAME.value].bind(
            "<FocusOut>",
            lambda event: ViewUtils.validate_entry(
                self.client_widgets[DBClientsColumns.NAME.value],
                lambda val: val.strip() != "",
                self.error_labels[DBClientsColumns.NAME.value],
                "Il nome non puo essere vuoto."
            )
        )

    def _collect_client_data(self):
        client_data = {}

        for label_text, widget in self.client_widgets.items():
            if isinstance(widget, (ctk.CTkEntry, ctk.CTkOptionMenu)):
                client_data[label_text] = widget.get().strip()
            elif isinstance(widget, ctk.CTkTextbox):
                client_data[label_text] = widget.get("1.0", "end-1c").strip()
            elif isinstance(widget, FilterableComboBox):
                client_data[label_text] = widget.get_value()

        return client_data

    def save_client_data(self):
        selected_sector = self.client_widgets[DBClientsColumns.SETTORE.value].get_value()
        sector_dict = dict(self.catalogo_elenchi["clients_business_sectors"])
        if selected_sector == sector_dict.get("ADD_SECTOR"):
            ViewUtils.show_error_popup(self, "SALVATAGGIO NON RIUSCITO", "Settore di business non valido")
            return

        client_data = self._collect_client_data()
        success, message = self.client_controller.save_client(client_data)

        if not success:
            ViewUtils.show_error_popup(self, "ERRORE", message)
            return

        client_row = self.clients_query_service.retrieve_client_by_name(client_data[DBClientsColumns.NAME.value])
        client_id = client_row[0] if client_row else None

        if self.on_client_created:
            self.on_client_created(client_id, client_data)

        self._on_close()

    def _handle_business_sector_selection(self, selected_value):
        sector_dict = dict(self.catalogo_elenchi["clients_business_sectors"])
        if selected_value != sector_dict.get("ADD_SECTOR"):
            return

        self.after(10, self.open_add_business_sector)

    def open_add_business_sector(self):
        if self.business_sector_create_view is not None and self.business_sector_create_view.winfo_exists():
            self.business_sector_create_view.focus()
            self.business_sector_create_view.lift()
            return

        self.business_sector_create_view = BusinessSectorCreateView(
            parent=self,
            app_context=self.app_context,
            on_sector_created=self._on_business_sector_created,
            on_close=self._clear_business_sector_create_view
        )

    def _on_business_sector_created(self, sector_key, sector_value):
        sector_widget = self.client_widgets[DBClientsColumns.SETTORE.value]
        sector_widget.set_values(
            [value for _, value in self.catalogo_elenchi["clients_business_sectors"]],
            preserve_current=False
        )
        sector_widget.set_value(sector_value, safe_mode=False)
        self.grab_set()

    def _clear_business_sector_create_view(self):
        self.business_sector_create_view = None
        if self.winfo_exists():
            self.grab_set()

    def _on_close(self):
        try:
            self.grab_release()
        except Exception:
            pass

        if self.on_close:
            self.on_close()

        self.destroy()

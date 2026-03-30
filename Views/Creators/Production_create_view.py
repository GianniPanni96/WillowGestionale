import re

import customtkinter as ctk
from tkcalendar import Calendar

from Gestionale_Enums import DBClientsColumns, DBProductionsColumns, ProductionStatus
from Views.Adders.Production_output_type_adder_view import ProductionOutputTypeAdderView
from Views.Adders.Production_type_adder_view import ProductionTypeAdderView
from Views.View_utils import FilterableComboBox, ViewUtils

from App_context import AppContext


class ProductionCreateView(ctk.CTkToplevel):
    """
    Finestra modale per la creazione di una nuova produzione.

    La classe replica il workflow storico di ``ProductionsView`` ma lo porta
    nel pattern moderno dei creator dedicati:
    - costruzione dichiarativa del form;
    - validazione minima lato view;
    - raccolta dati e salvataggio tramite controller;
    - gestione modale dell'aggiunta di production type e output type.
    """

    CLIENT_NAME_FIELD = "NOME CLIENTE"

    def __init__(self, parent, app_context: AppContext, on_production_created=None, on_close=None):
        super().__init__(parent)

        self.app_context = app_context
        self.production_controller = app_context.production_controller
        self.client_controller = app_context.client_controller
        self.clients_query_service = app_context.clients_query_service
        self.productions_query_service = app_context.productions_query_service
        self.catalogo_elenchi = app_context.catalogo_elenchi

        self.on_production_created = on_production_created
        self.on_close = on_close

        self.entry_fields = {
            self.CLIENT_NAME_FIELD: FilterableComboBox,
            DBProductionsColumns.NAME.value: ctk.CTkEntry,
            DBProductionsColumns.HOURS.value: ctk.CTkEntry,
            DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value: FilterableComboBox,
            DBProductionsColumns.TIPOLOGIA_OUTPUT.value: FilterableComboBox,
            DBProductionsColumns.STATO.value: ctk.CTkOptionMenu,
            DBProductionsColumns.END_DATE.value: Calendar,
            DBProductionsColumns.TOTALE_PREVENTIVO.value: ctk.CTkEntry,
        }
        self.error_fields = {
            DBProductionsColumns.NAME.value: ctk.CTkLabel,
            DBProductionsColumns.HOURS.value: ctk.CTkLabel,
            DBProductionsColumns.TOTALE_PREVENTIVO.value: ctk.CTkLabel,
        }
        self.field_labels = {}
        self.production_widgets = {}
        self.error_labels = {}
        self.production_type_adder_view = None
        self.production_output_type_adder_view = None
        self.name_prefix_label = None

        self.title("Aggiungi Nuova Produzione")
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
        """Costruisce dinamicamente i campi del form produzione."""
        for i, (label_text, widget_class) in enumerate(self.entry_fields.items()):
            label = ctk.CTkLabel(self.scrollable_frame, text=label_text)
            label.pack(pady=5 if i == 0 else (35, 0))
            self.field_labels[label_text] = label

            widget = self._create_field_widget(label_text, widget_class)
            if label_text == DBProductionsColumns.NAME.value:
                widget.master.pack(pady=5, padx=10, fill="x", expand=True)
            else:
                widget.pack(pady=5, padx=10, fill="x", expand=True)

            if self.error_fields.get(label_text) is not None:
                error_label = ctk.CTkLabel(self.scrollable_frame, text="")
                error_label.pack(pady=(0, 15))
                self.error_labels[label_text] = error_label

            self.production_widgets[label_text] = widget

        self.save_button = ctk.CTkButton(
            self.scrollable_frame,
            text="Salva Produzione",
            command=self.save_production_data
        )
        self.save_button.pack(pady=(35, 15))

    def _create_field_widget(self, label_text, widget_class):
        """Crea e configura il widget corretto per il campo richiesto."""
        if label_text == self.CLIENT_NAME_FIELD:
            return widget_class(
                parent=self.scrollable_frame,
                placeholder="Cerca",
                autofill=True,
                values=[
                    item[DBClientsColumns.NAME.value]
                    for item in self.clients_query_service.retrieve_clients_map_list()
                ],
                command=self.auto_compile_name_entry
            )

        if label_text == DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value:
            widget = widget_class(
                self.scrollable_frame,
                values=[value for _, value in self.catalogo_elenchi["production_types"]],
                command=self._handle_production_type_selection
            )
            return widget

        if label_text == DBProductionsColumns.TIPOLOGIA_OUTPUT.value:
            widget = widget_class(
                self.scrollable_frame,
                values=[value for _, value in self.catalogo_elenchi["production_output_types"]],
                command=self._handle_production_output_type_selection
            )
            return widget

        if label_text == DBProductionsColumns.STATO.value:
            widget = widget_class(
                self.scrollable_frame,
                values=[item.value for item in ProductionStatus]
            )
            return widget

        if label_text == DBProductionsColumns.END_DATE.value:
            return widget_class(self.scrollable_frame, date_pattern=ViewUtils.date_pattern)

        if label_text == DBProductionsColumns.NAME.value:
            name_frame = ctk.CTkFrame(self.scrollable_frame)
            self.name_prefix_label = ctk.CTkLabel(name_frame, text="")
            self.name_prefix_label.pack(side="left", pady=5, padx=(10, 0))
            entry = widget_class(name_frame)
            entry.pack(side="left", pady=5, padx=(0, 10), fill="x", expand=True)
            return entry

        return widget_class(self.scrollable_frame)

    def _bind_validations(self):
        """Collega le validazioni lato interfaccia ai campi principali."""
        self.production_widgets[DBProductionsColumns.NAME.value].bind(
            "<FocusOut>",
            lambda event: ViewUtils.validate_entry(
                self.production_widgets[DBProductionsColumns.NAME.value],
                lambda val: val.strip() != "",
                self.error_labels[DBProductionsColumns.NAME.value],
                "Il campo non puo essere vuoto."
            )
        )

        self.production_widgets[DBProductionsColumns.HOURS.value].bind(
            "<FocusOut>",
            lambda event: ViewUtils.validate_entry(
                self.production_widgets[DBProductionsColumns.HOURS.value],
                lambda val: val.strip() != "" and val.isdigit(),
                self.error_labels[DBProductionsColumns.HOURS.value],
                "Il campo deve contenere un numero intero."
            )
        )

        self.production_widgets[DBProductionsColumns.TOTALE_PREVENTIVO.value].bind(
            "<FocusOut>",
            lambda event: ViewUtils.validate_entry(
                self.production_widgets[DBProductionsColumns.TOTALE_PREVENTIVO.value],
                lambda val: re.fullmatch(r"^\d+(\.\d{2})?$", val.strip()) is not None,
                self.error_labels[DBProductionsColumns.TOTALE_PREVENTIVO.value],
                "Inserimento non valido: usare un importo come 123.45"
            )
        )

    def _initialize_default_values(self):
        """Inizializza i valori di default replicando il comportamento della view legacy."""
        clients = self.clients_query_service.retrieve_clients_map_list()
        if clients:
            first_client_name = clients[0][DBClientsColumns.NAME.value]
            self.production_widgets[self.CLIENT_NAME_FIELD].set_value(first_client_name, safe_mode=False)
            self.auto_compile_name_entry(first_client_name)

        production_types = [value for _, value in self.catalogo_elenchi["production_types"]]
        if production_types:
            self.production_widgets[DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value].set(production_types[0])

        production_output_types = [value for _, value in self.catalogo_elenchi["production_output_types"]]
        if production_output_types:
            self.production_widgets[DBProductionsColumns.TIPOLOGIA_OUTPUT.value].set(production_output_types[0])

        self.production_widgets[DBProductionsColumns.STATO.value].set(ProductionStatus.START_WAITING.value)

    def _collect_production_data(self):
        """Estrae i dati del form in un dizionario compatibile col controller."""
        production_data = {}

        for label_text, widget in self.production_widgets.items():
            if isinstance(widget, (ctk.CTkEntry, ctk.CTkOptionMenu)):
                production_data[label_text] = widget.get().strip()
            elif isinstance(widget, Calendar):
                production_data[label_text] = widget.get_date()
            elif isinstance(widget, ctk.CTkTextbox):
                production_data[label_text] = widget.get("1.0", "end-1c").strip()
            elif isinstance(widget, FilterableComboBox):
                production_data[label_text] = widget.get_value()

        return production_data

    def save_production_data(self):
        """
        Valida e salva la nuova produzione tramite ``ProductionController``.

        In caso di successo notifica il chiamante con ``on_production_created`` e
        chiude la finestra; in caso di errore mostra un popup esplicativo.
        """
        if not self._validate_dynamic_catalog_selections():
            return

        production_data = self._collect_production_data()
        success, message = self.production_controller.save_production(production_data)

        if not success:
            ViewUtils.show_error_popup(self, "ERRORE", message)
            return

        production_map = self.productions_query_service.retrieve_last_production_insert_map()
        production_id = production_map[DBProductionsColumns.ID.value] if production_map else None

        if self.on_production_created:
            self.on_production_created(production_id, production_data)

        self._on_close()

    def _validate_dynamic_catalog_selections(self):
        """Blocca il salvataggio se il form punta ai trigger 'aggiungi nuova tipologia'."""
        production_type = self.production_widgets[DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value].get()
        production_output_type = self.production_widgets[DBProductionsColumns.TIPOLOGIA_OUTPUT.value].get()

        production_type_dict = dict(self.catalogo_elenchi["production_types"])
        if production_type == production_type_dict.get("ADD_PROD_TYPE"):
            ViewUtils.show_error_popup(self, "SALVATAGGIO NON RIUSCITO", "Tipologia di produzione non valida")
            return False

        production_output_type_dict = dict(self.catalogo_elenchi["production_output_types"])
        if production_output_type == production_output_type_dict.get("ADD_PROD_OUT_TYPE"):
            ViewUtils.show_error_popup(self, "SALVATAGGIO NON RIUSCITO", "Tipologia di output non valida")
            return False

        return True

    def auto_compile_name_entry(self, selected_value):
        """Aggiorna il prefisso visivo del nome produzione in base al cliente scelto."""
        if self.name_prefix_label is not None:
            self.name_prefix_label.configure(text=f"{selected_value} - ")

    def _handle_production_type_selection(self, selected_value):
        """Intercetta il trigger di aggiunta di una nuova tipologia di produzione."""
        production_type_dict = dict(self.catalogo_elenchi["production_types"])
        if selected_value != production_type_dict.get("ADD_PROD_TYPE"):
            return

        self.after(10, self.open_add_production_type)

    def _handle_production_output_type_selection(self, selected_value):
        """Intercetta il trigger di aggiunta di una nuova tipologia di output."""
        output_type_dict = dict(self.catalogo_elenchi["production_output_types"])
        if selected_value != output_type_dict.get("ADD_PROD_OUT_TYPE"):
            return

        self.after(10, self.open_add_production_output_type)

    def open_add_production_type(self):
        """Apre la modale per aggiungere una nuova tipologia di produzione."""
        if self.production_type_adder_view is not None and self.production_type_adder_view.winfo_exists():
            self.production_type_adder_view.focus()
            self.production_type_adder_view.lift()
            return

        self.production_type_adder_view = ProductionTypeAdderView(
            parent=self,
            app_context=self.app_context,
            on_item_created=self._on_production_type_created,
            on_close=self._clear_production_type_adder_view
        )

    def open_add_production_output_type(self):
        """Apre la modale per aggiungere una nuova tipologia di output."""
        if self.production_output_type_adder_view is not None and self.production_output_type_adder_view.winfo_exists():
            self.production_output_type_adder_view.focus()
            self.production_output_type_adder_view.lift()
            return

        self.production_output_type_adder_view = ProductionOutputTypeAdderView(
            parent=self,
            app_context=self.app_context,
            on_item_created=self._on_production_output_type_created,
            on_close=self._clear_production_output_type_adder_view
        )

    def _on_production_type_created(self, production_type_key, production_type_value):
        """Aggiorna il menu delle tipologie di produzione dopo la creazione di una nuova voce."""
        target_widget = self.production_widgets[DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value]
        target_widget.configure(values=[value for _, value in self.catalogo_elenchi["production_types"]])
        target_widget.set(production_type_value)
        self.grab_set()

    def _on_production_output_type_created(self, output_type_key, output_type_value):
        """Aggiorna il menu delle tipologie di output dopo la creazione di una nuova voce."""
        target_widget = self.production_widgets[DBProductionsColumns.TIPOLOGIA_OUTPUT.value]
        target_widget.configure(values=[value for _, value in self.catalogo_elenchi["production_output_types"]])
        target_widget.set(output_type_value)
        self.grab_set()

    def _clear_production_type_adder_view(self):
        """Azzera il riferimento all'adder delle tipologie di produzione."""
        self.production_type_adder_view = None
        if self.winfo_exists():
            self.grab_set()

    def _clear_production_output_type_adder_view(self):
        """Azzera il riferimento all'adder delle tipologie di output."""
        self.production_output_type_adder_view = None
        if self.winfo_exists():
            self.grab_set()

    def _on_close(self):
        """Chiude il toplevel produzione rilasciando in sicurezza l'eventuale grab."""
        try:
            self.grab_release()
        except Exception:
            pass

        if self.on_close:
            self.on_close()

        self.destroy()

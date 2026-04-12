import customtkinter as ctk
from tkcalendar import Calendar
import re
from datetime import datetime

from Model import DatabaseModel
from Controllerss.Invoice_controller import InvoiceController

from Controllerss.Client_controller import ClientController
from Controllerss.Production_controller import ProductionController
from Gestionale_Enums import*
from QueryServices.Invoices_query_service import InvoiceQueryService
from Views.Adders.Production_output_type_adder_view import ProductionOutputTypeAdderView
from Views.Adders.Production_type_adder_view import ProductionTypeAdderView
from Views.View_utils import CatalogFilterableComboBox, ViewUtils, FilterableComboBox

from App_context import AppContext
from Event_bus import EventBus
from Config import ConfigManager



class ProductionDetailView(ctk.CTkFrame):
    def __init__(self, app_context:AppContext, parent, back_callback):
        super().__init__(parent)
        self.app_context:AppContext = app_context
        self.production_query_service = app_context.productions_query_service
        self.production_analyzer_service = app_context.productions_analyzer_service
        self.client_query_service = app_context.clients_query_service
        self.invoice_query_service:InvoiceQueryService = app_context.invoices_query_service
        self.production_controller:ProductionController = app_context.production_controller
        self.db_model:DatabaseModel = app_context.db_model
        self.back_callback = back_callback
        self.event_bus:EventBus = app_context.event_bus
        self.catalogo_elenchi = app_context.catalogo_elenchi
        self.config_manager:ConfigManager = app_context.config_manager
        self.current_invoice_id = None
        self.parent = parent
        self.production_type_adder_view = None
        self.production_output_type_adder_view = None
        self.configure(fg_color="transparent")

        # Widgets persistenti (vanno creati una volta sola)
        self.head_frame = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.back_button = ctk.CTkButton(
            self.head_frame,
            text="Elenco Produzioni",
            command=self._cleanup_and_go_back
        )
        self.title_label = ctk.CTkLabel(self.head_frame, font=("Arial", 22, "bold"))

        self.payment_info_widgets: dict[str, ctk.CTkEntry | ctk.CTkOptionMenu | FilterableComboBox] = {}


        self.nome_cliente_string = "CLIENTE"

        # Container per i contenuti dinamici
        self.content_frame = ctk.CTkScrollableFrame(self)

        self.switch_modify = ctk.CTkSwitch(self.head_frame, text="Abilita la modifica", command=lambda: self.toggle_edit(self.content_frame))

        # Layout iniziale
        self._setup_base_layout()

    def _setup_base_layout(self):
        """Inizializza la struttura base del layout"""
        self.head_frame.pack(fill="x", pady=5, padx=5)
        self.back_button.pack(anchor="w", side="left", pady=10, padx=10)
        self.title_label.pack(anchor="c", side="left", fill="x", expand=True, pady=10)
        self.switch_modify.pack(anchor="e", side="left", pady=10, padx=10)
        self.content_frame.pack(fill="both", expand=True, pady=20, padx=20)

    def create_detail_tab(self, production_id):
        """Ricrea la vista dettaglio per un pagamento specifico"""
        self.current_production_id = production_id

        # 1. Pulizia dei widget precedenti
        self._clear_content()

        # 2. Caricamento dati
        self.production = self.production_query_service.retrieve_production_map_by_id(production_id)

        # prendo il nome del cliente
        id_cliente = self.production[DBProductionsColumns.CLIENT_ID.value]
        cliente = self.client_query_service.retrieve_client_map_by_id(id_cliente)
        nome_cliente = cliente[DBClientsColumns.NAME.value] if cliente else "Cliente non trovato"
        self.production[self.nome_cliente_string] = nome_cliente

        # 3. Aggiornamento elementi persistenti
        self.title_label.configure(
            text=f"{self.production[DBProductionsColumns.NAME.value]}")

        # 4. Creazione contenuti dinamici
        self._create_production_info_section(self.production)
        self.toggle_edit(self.content_frame)

        self.wrapper_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.wrapper_frame.pack(padx=15, pady=(90, 0), fill="both", expand=True)
        self.wrapper_frame2 = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.wrapper_frame2.pack(padx=15, pady=(90, 90), fill="both", expand=True)

        self._create_invoices_history()

    def _create_production_info_section(self, production_data):
        # Campi derivati per le produzioni (se necessario)
        self.derived_fields_productions = {
            # Potresti aggiungere campi calcolati qui se necessario
        }

        self.entry_fields_productions = {
            DBProductionsColumns.NAME.value: {
                "type": ctk.CTkEntry,
                "label": "Nome Produzione",
                "section": "Dati Generali"
            },
            self.nome_cliente_string: {
                "type": FilterableComboBox,
                "label": "Cliente",
                "section": "Dati Generali",
                "values": [c[DBClientsColumns.NAME.value]
                           for c in self.client_query_service.retrieve_clients_map_list()],
                "command" : self.auto_compile_name
            },
            DBProductionsColumns.STATO.value: {
                "type": ctk.CTkOptionMenu,
                "label": "Stato",
                "section": "Dati Generali",
                "values": [stato.name for stato in ProductionStatus]
            },
            DBProductionsColumns.END_DATE.value: {
                "type": Calendar,
                "label": "Data Conclusione",
                "section": "Dati Generali"
            },

            # Dati Produzione
            DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value: {
                "type": CatalogFilterableComboBox,
                "label": "Tipologia Produzione",
                "section": "Dati Produzione",
                "values": self._get_production_type_values(),
                "show_add_button": True,
                "add_button_text": "Aggiungi una tipologia",
                "add_button_command": self.open_add_production_type
            },
            DBProductionsColumns.TIPOLOGIA_OUTPUT.value: {
                "type": CatalogFilterableComboBox,
                "label": "Tipologia Output",
                "section": "Dati Produzione",
                "values": self._get_production_output_type_values(),
                "show_add_button": True,
                "add_button_text": "Aggiungi una tipologia di output",
                "add_button_command": self.open_add_production_output_type
            },
            DBProductionsColumns.HOURS.value: {
                "type": ctk.CTkEntry,
                "label": "Ore di produzione",
                "section": "Dati Produzione"
            },
            DBProductionsColumns.TOTALE_PREVENTIVO.value: {
                "type": ctk.CTkEntry,
                "label": "Totale Preventivo (€)",
                "section": "Dati Produzione"
            },

            # Campi statici
            DBProductionsColumns.CREATED_AT.value: {
                "type": ctk.CTkLabel,
                "label": "Data Creazione",
                "section": "Note"
            },
            DBProductionsColumns.UPDATED_AT.value: {
                "type": ctk.CTkLabel,
                "label": "Ultimo Aggiornamento",
                "section": "Note"
            }
        }

        self.error_fields_productions = {
            DBProductionsColumns.HOURS.value: "Valore intero positivo",
            DBProductionsColumns.TOTALE_PREVENTIVO.value: "Valore numerico con massimo 2 decimali"
        }

        validation_rules = {
            DBProductionsColumns.HOURS.value: (
                lambda val: re.fullmatch(r"^\d+(\.\d{1,2})?$", val),
                "Inserire un valore numerico"
            ),
            DBProductionsColumns.TOTALE_PREVENTIVO.value: (
                lambda val: re.fullmatch(r"^\d+(\.\d{1,2})?$", val),
                "Formato valido: 1234.56"
            )
        }

        # Inizializzazione strutture dati
        self.production_info_widgets = {}
        self.production_info_labels = {}
        self.error_labels_productions = {}
        sections = {}

        # Creazione frame principale
        self.info_frame = ctk.CTkFrame(self.content_frame, border_width=2, border_color="#2659ab")
        self.info_frame.pack(fill="both", expand=True, pady=(5, 10), padx=(5, 25))

        # Configurazione griglia a 2 colonne
        self.info_frame.grid_columnconfigure(0, weight=1, uniform="col")
        self.info_frame.grid_columnconfigure(1, weight=1, uniform="col")

        # Sezioni organizzate per colonne
        sections_order = [
            "Dati Generali",
            "Dati Produzione",
            "Note"
        ]

        # Creazione frame sezioni
        for i, section_name in enumerate(sections_order):
            frame = ctk.CTkFrame(self.info_frame)
            column = i % 2  # Solo 2 colonne
            row = i // 2  # Calcola la riga in base all'indice

            frame.grid(row=row, column=column, sticky="nsew", padx=15, pady=15)
            frame.grid_columnconfigure(1, weight=1)

            sections[section_name] = {
                "frame": frame,
                "row": 0
            }

            ctk.CTkLabel(frame, text=section_name, font=("Arial", 14, "bold")).grid(
                row=0, column=0, columnspan=2, sticky="w", padx=15, pady=5
            )
            sections[section_name]["row"] += 1

        # Popolamento sezioni
        for field, config in self.entry_fields_productions.items():
            section = sections[config["section"]]
            frame = section["frame"]
            row = section["row"]

            # Creazione label
            lbl = ctk.CTkLabel(frame, text=config["label"] + ":")
            self.production_info_labels[field] = lbl
            lbl.grid(row=row, column=0, sticky="w", padx=(15, 5), pady=(5, 5))

            # Creazione widget
            if config["type"] == ctk.CTkLabel:
                value = str(production_data.get(field, ""))
                widget = config["type"](frame, text=value)
                widget.grid(row=row, column=1, sticky="w", padx=(5, 15), pady=(5, 5))
            else:
                if issubclass(config["type"], FilterableComboBox):
                    combo_kwargs = {
                        "values": config.get("values", []),
                        "placeholder": "Cerca",
                        "autofill": True,
                        "command": config.get("command"),
                    }
                    if issubclass(config["type"], CatalogFilterableComboBox):
                        combo_kwargs["add_button_text"] = config.get("add_button_text", "")
                        combo_kwargs["add_button_command"] = config.get("add_button_command")

                    widget = config["type"](
                        frame,
                        **combo_kwargs
                    )

                    # Gestione speciale per client_id
                    if field == self.nome_cliente_string:
                        client_id = production_data[DBProductionsColumns.CLIENT_ID.value]
                        client = self.client_query_service.retrieve_client_map_by_id(client_id)
                        client_name = client[DBClientsColumns.NAME.value]
                        widget.set_value(client_name, safe_mode=False)

                    # Gestione speciale per tipologie
                    elif field == DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value:
                        current_value = production_data.get(field, "")
                        widget.set_value(current_value, safe_mode=False)

                    # Gestione speciale per tipologie
                    elif field == DBProductionsColumns.TIPOLOGIA_OUTPUT.value:
                        current_value = production_data.get(field, "")
                        widget.set_value(current_value, safe_mode=False)

                elif config["type"] == ctk.CTkOptionMenu:
                    widget = config["type"](frame, values=config.get("values", []))

                    # Gestione stato
                    if field == DBProductionsColumns.STATO.value:
                        stato = production_data.get(field, "")
                        widget.set(stato)

                    else:
                        widget.set(production_data.get(field, config.get("values", [""])[0]))

                elif config["type"] == Calendar:
                    widget = config["type"](frame, date_pattern=ViewUtils.date_pattern)
                    value = production_data.get(field, "")
                    widget.selection_set(str(value)) if value else widget.selection_set(datetime.today())

                else:
                    widget = config["type"](frame)
                    value = str(production_data.get(field, ""))
                    widget.insert(0, value)

                widget.grid(row=row, column=1, sticky="ew", padx=(5, 15), pady=(5, 5))

            self.production_info_widgets[field] = widget

            # Gestione validazione
            if field in validation_rules:
                validation_func, error_message = validation_rules[field]

                error_lbl = ctk.CTkLabel(frame, text="", text_color="#e8e5dc")
                error_lbl.grid(row=row + 1, column=1, sticky="w", padx=5, pady=(0, 10))
                self.error_labels_productions[field] = error_lbl

                widget.bind("<FocusOut>",
                            lambda e, w=widget, vl=validation_func, el=error_lbl, em=error_message:
                            ViewUtils.validate_entry(w, vl, el, em))

                section["row"] += 2
            else:
                section["row"] += 1

        buttons_frame = ctk.CTkFrame(self.info_frame, fg_color="#2b2b2b")
        buttons_frame.grid(row=2, column=0, columnspan=2, pady=(5, 15), padx=20, sticky="WE")

        # Bottone Salva
        self.save_production_btn = ctk.CTkButton(buttons_frame, text="Salva Produzione",
                                                 command=self.save_production_mod)
        self.save_production_btn.pack(padx=(400, 10), pady=(20, 20), side="left")

        # Bottone Elimina
        self.delete_btn = ctk.CTkButton(buttons_frame, text="Elimina Produzione",
                                        fg_color="#8B0000", hover_color="#A52A2A",
                                        command=self.delete_production)
        self.delete_btn.pack(padx=10, pady=(20, 20), side="right", anchor="e")

    def save_production_mod(self):

        invoices_map_list = self.invoice_query_service.retrieve_invoice_map_list_by_production(self.current_production_id)
        confirmation = True
        if len(invoices_map_list) > 0:
            confirmation = ViewUtils.ask_confirmation_popup(self.info_frame, "Questa produzione presenta una o più fatture associate.\n"
                                                                             "La sua modifica può comportare delle incongruenze tra i dati delle fatture ad essa associate.\n"
                                                                             "Desideri continuare?\n"
                                                                             "In caso affermativo ricordati di controllare i dati delle fatture associate",
                                                            "MODIFICA PRODUZIONE")

        if confirmation:
            nome_cliente = self.production_info_widgets[self.nome_cliente_string].get_value()
            cliente = self.client_query_service.retrieve_client_map_by_name(nome_cliente)
            id_cliente = cliente[DBClientsColumns.ID.value]

            production_data = {
                DBProductionsColumns.NAME.value: self.production_info_widgets[
                    DBProductionsColumns.NAME.value].get().strip(),
                DBProductionsColumns.CLIENT_ID.value: id_cliente,
                DBProductionsColumns.STATO.value: self.production_info_widgets[
                    DBProductionsColumns.STATO.value].get(),
                DBProductionsColumns.END_DATE.value: self.production_info_widgets[
                    DBProductionsColumns.END_DATE.value].get_date(),
                DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value: self.production_info_widgets[
                    DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value].get_value(),
                DBProductionsColumns.TIPOLOGIA_OUTPUT.value: self.production_info_widgets[
                    DBProductionsColumns.TIPOLOGIA_OUTPUT.value].get_value(),
                DBProductionsColumns.HOURS.value: self.production_info_widgets[
                    DBProductionsColumns.HOURS.value].get(),
                DBProductionsColumns.TOTALE_PREVENTIVO.value: self.production_info_widgets[
                    DBProductionsColumns.TOTALE_PREVENTIVO.value].get()
            }

            # Chiamata al controller per salvare i dati
            success, message = self.production_controller.update_production(self.current_production_id, production_data)
            if success:
                print(
                    f"Produzione {self.production_query_service.retrieve_production_map_by_id(self.current_production_id)[DBProductionsColumns.NAME.value]} salvata con successo")
                ViewUtils.show_confirm_popup_2(self.content_frame, "SALVATAGGIO COMPLETATO", message)
                self.switch_modify.deselect()
                self.toggle_edit(self.content_frame)

            else:
                # Mostra il messaggio d'errore
                print(message)
                ViewUtils.show_error_popup(self.content_frame, "ERRORE", message)

    def _get_production_type_values(self):
        return [
            value for key, value in self.catalogo_elenchi["production_types"]
            if key != "ADD_PROD_TYPE"
        ]

    def _get_production_output_type_values(self):
        return [
            value for key, value in self.catalogo_elenchi["production_output_types"]
            if key != "ADD_PROD_OUT_TYPE"
        ]

    def open_add_production_type(self):
        """Apre la modale riusabile per aggiungere una tipologia di produzione."""
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
        """Apre la modale riusabile per aggiungere una tipologia di output."""
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
        """Aggiorna il menu tipologie produzione del dettaglio dopo la creazione di una nuova voce."""
        target_widget = self.production_info_widgets.get(DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value)
        if target_widget is not None:
            target_widget.set_values(
                self._get_production_type_values(),
                preserve_current=False
            )
            target_widget.set_value(production_type_value, safe_mode=False)
        self.grab_set()

    def _on_production_output_type_created(self, output_type_key, output_type_value):
        """Aggiorna il menu tipologie output del dettaglio dopo la creazione di una nuova voce."""
        target_widget = self.production_info_widgets.get(DBProductionsColumns.TIPOLOGIA_OUTPUT.value)
        if target_widget is not None:
            target_widget.set_values(
                self._get_production_output_type_values(),
                preserve_current=False
            )
            target_widget.set_value(output_type_value, safe_mode=False)
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

    def delete_production(self):

        invoices_map_list = self.invoice_query_service.retrieve_invoice_map_list_by_production(self.current_production_id)
        invoices_presence = False
        if len(invoices_map_list) > 0:
            invoices_presence = True

        message = "Sei sicuro di voler eliminare questa produzione?" if not invoices_presence else ("Sei sicuro di voler eliminare questa produzione?\n"
                                                                                                    "Essa presenta delle fatture associate. Controlla eventualmente la consistenza dei dati\n"
                                                                                                    "di tali fatture a seguito dell'eliminazione")
        confirmation = ViewUtils.ask_confirmation_popup(self.info_frame, message, "ELIMINAZIONE PRODUZIONE")
        if confirmation:
            success = self.production_controller.delete_production(self.current_production_id)
            if success:
                ViewUtils.show_confirm_popup(self.info_frame)
            else:
                ViewUtils.show_error_popup(self.info_frame)


    def _create_invoices_history(self):
        """Crea la sezione fatture associate"""
        section_frame = ctk.CTkFrame(self.wrapper_frame, border_width=2, border_color="#2659ab")
        section_frame.pack(fill="both", side="left", expand=True, pady=0, padx=(0, 30))

        ctk.CTkLabel(section_frame, text="FATTURE ASSOCIATE", font=("Arial", 14, "bold")).pack(anchor="w",
                                                                                               pady=(10, 10), padx=10)

        global_infos = {
            "TOTALE SERVIZI + RIMBORSI\nFATTURE": {
                "value": self.production_analyzer_service.calcola_totale_servizi_rimborsi_per_produzione(self.current_production_id),
                "uom": "€"
            },
            "TOTALE PREVENTIVO": {
                "value": self.production_query_service.retrieve_production_map_by_id(self.current_production_id)[DBProductionsColumns.TOTALE_PREVENTIVO.value],
                "uom": "€"
            }
        }

        self.global_infos_invoices_widgets = ViewUtils.construct_global_infos_cards(section_frame, global_infos)


        invoice_frame = ctk.CTkScrollableFrame(section_frame, height=300)
        invoice_frame.pack(fill="both", expand=True, padx=(10, 20), pady=(10, 20))

        # popolo gli invoices
        invoices = self.production_query_service.retrieve_production_with_invoices_map_list(self.current_production_id)
        for invoice in invoices:
            if invoice[DBInvoicesColumns.NUMERO_FATTURA.value] is not None:
                nome_fattura = invoice[DBInvoicesColumns.NUMERO_FATTURA.value]
                id_fattura = invoice[DBInvoicesColumns.ID.value]
                fattura_button = ctk.CTkButton(invoice_frame,
                                               text=f"{nome_fattura}",
                                               command=lambda id=id_fattura: self.show_invoice_detail(id))
                fattura_button.pack(padx=10, pady=10, fill="x", expand=True)

    def show_invoice_detail(self, invoice_id):
        self.event_bus.publish(ViewUtils.EventBusKeys.SHOW_INVOICE_DETAIL, invoice_id)


    def auto_compile_name(self, event):
        client_name = self.production_info_widgets[self.nome_cliente_string].get_value()
        nome_produzione_array = self.production_info_widgets[DBProductionsColumns.NAME.value].get().split(" - ")
        new_name = client_name + " - " + nome_produzione_array[1] if len(nome_produzione_array) > 1 else client_name + " - "
        self.production_info_widgets[DBProductionsColumns.NAME.value].delete(0, ctk.END)
        self.production_info_widgets[DBProductionsColumns.NAME.value].insert(0, new_name)

    def toggle_edit(self, parent):
        """
        Abilita o disabilita la modifica dei widget nella finestra di modifica utente.
        """
        # Determina lo stato (abilitato/disabilitato) in base al valore dello switch
        state = ctk.NORMAL if self.switch_modify.get() else ctk.DISABLED

        # Cambia anche lo stato del pulsante Salva
        self.save_production_btn.configure(state=state)
        self.delete_btn.configure(state=state)

        for w in parent.winfo_children():
            # se è un Entry
            if isinstance(w, ctk.CTkEntry):
                w.configure(state=state, text_color="#636363" if state == ctk.DISABLED else "#c2c2c2")
            # se è un OptionMenu
            elif isinstance(w, ctk.CTkOptionMenu):
                w.configure(state=state)
            elif isinstance(w, FilterableComboBox):
                w.configure(state=state, text_color="#c2c2c2")
            elif isinstance(w, Calendar):
                w.configure(state=state)
            # se è un Frame/container, scendi ricorsivamente
            elif isinstance(w, (ctk.CTkFrame, ctk.CTkScrollableFrame, ctk.CTkToplevel)):
                self.toggle_edit(w)

    def _clear_content(self):
        """Distrugge tutti i widget dinamici"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        self.switch_modify.deselect()

    def _cleanup_and_go_back(self):
        """Pulizia completa prima di tornare indietro"""
        self._clear_content()
        self.pack_forget()
        self.back_callback()

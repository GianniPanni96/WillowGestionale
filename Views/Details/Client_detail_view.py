import customtkinter as ctk
from Controllers import DatabaseModel, Analyzer
from App_context import AppContext
from Model import DBClientsColumns, DBInvoicesColumns, DBProductionsColumns, DBRefundsColumns
from Views.View_utils import CatalogFilterableComboBox, ViewUtils, FilterableComboBox
import re
from datetime import datetime

from Controllerss.Client_controller import ClientController


from Gestionale_Enums import *
from QueryServices.Productions_query_service import ProductionQueryService
from QueryServices.Invoices_query_service import InvoiceQueryService
from QueryServices.Refunds_query_service import RefundQueryService
from QueryServices.Clients_query_service import ClientQueryService
from AnalyzerServices.Refund_analyzer_service import RefundAnalyzerService
from AnalyzerServices.Client_analyzer_service import ClientAnalyzerService
from AnalyzerServices.Production_analyzer_service import ProductionAnalyzerService
from Views.Adders.Business_sector_adder_view import BusinessSectorAdderView


class ClientDetailView(ctk.CTkFrame):
    def __init__(self, parent, app_context:AppContext, back_callback):
        super().__init__(parent)
        self.app_context:AppContext = app_context

        self.clients_query_service:ClientQueryService = app_context.clients_query_service
        self.invoices_query_service:InvoiceQueryService = app_context.invoices_query_service
        self.clients_analyzer_service:ClientAnalyzerService = app_context.clients_analyzer_service
        self.productions_query_service: ProductionQueryService = app_context.productions_query_service
        self.productions_analyzer_service:ProductionAnalyzerService = app_context.productions_analyzer_service
        self.refunds_analyzer_service:RefundAnalyzerService = app_context.refunds_analyzer_service
        self.refunds_query_service: RefundQueryService = app_context.refunds_query_service

        self.db_model:DatabaseModel = app_context.db_model
        self.back_callback = back_callback
        self.client_controller:ClientController = app_context.client_controller
        self.event_bus = app_context.event_bus
        self.current_client_id = None
        self.analyzer:Analyzer = app_context.analyzer
        self.catalogo_elenchi = app_context.catalogo_elenchi
        self.business_sector_adder_view = None

        self.configure(fg_color="transparent")

        # Widgets persistenti (vanno creati una volta sola)
        self.head_frame = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.back_button = ctk.CTkButton(
            self.head_frame,
            text="Elenco Clienti",
            command=self._cleanup_and_go_back
        )
        self.title_label = ctk.CTkLabel(self.head_frame, font=("Arial", 22, "bold"))

        self.user_info_widgets: dict[str, ctk.CTkEntry | ctk.CTkOptionMenu | FilterableComboBox] = {}

        self.nome_fattura_string = "FATTURA ASSOCIATA"
        self.nome_produzione_string = "PRODUZIONE ASSOCIATA"
        self.nome_rimborso_string = "RIMBORSO ASSOCIATO"


        # Container per i contenuti dinamici
        self.content_frame = ctk.CTkScrollableFrame(self)

        self.switch_modify = ctk.CTkSwitch(self.head_frame, text="Abilita la modifica", command=lambda: self.toggle_edit(self.content_frame))

        # Layout iniziale
        self._setup_base_layout()

        # Sistema per tracciare gli after()
        self._after_ids = set()
        self._orig_after = self.after
        self.after = self._track_after

    def _setup_base_layout(self):
        """Inizializza la struttura base del layout"""
        self.head_frame.pack(fill="x", pady=5, padx=5)
        self.back_button.pack(anchor="w", side="left", pady=10, padx=10)
        self.title_label.pack(anchor="c", side="left", fill="x", expand=True, pady=10)
        self.switch_modify.pack(anchor="e", side="left", pady=10, padx=10)
        self.content_frame.pack(fill="both", expand=True, pady=20, padx=20)

    def create_detail_tab(self, client_id):
        """Ricrea la vista dettaglio per un cliente specifico"""
        self.current_client_id = client_id

        # 1. Pulizia dei widget precedenti
        self._clear_content()

        # 2. Caricamento dati
        client = self.clients_query_service.retrieve_client_map_by_id(client_id)

        # 3. Aggiornamento elementi persistenti
        self.title_label.configure(
            text=f"{client[DBClientsColumns.NAME.value]}")

        # 4. Creazione contenuti dinamici
        self._create_client_info_section(client)
        self.toggle_edit(self.content_frame)

        self.wrapper_frame = ctk.CTkFrame(self.content_frame, fg_color="#333333")
        self.wrapper_frame.pack(padx=25, pady=(90, 0), fill="both", expand=True)
        #self.wrapper_frame2 = ctk.CTkFrame(self.content_frame, fg_color="#333333")
        #self.wrapper_frame2.pack(padx=25, pady=(90, 90), fill="both", expand=True)
        self._create_invoices_history()
        self._create_refunds_history()
        self._create_productions_history()

    def _create_client_info_section(self, client_data):
        # Dizionari per la configurazione
        self.entry_fields = {
            # Sezione Dati Anagrafici
            DBClientsColumns.NAME.value: {
                "type": ctk.CTkEntry,
                "label": "Nome Cliente",
                "section": "Dati Anagrafici"
            },
            DBClientsColumns.PARTITA_IVA.value: {
                "type": ctk.CTkEntry,
                "label": "Partita IVA",
                "section": "Dati Anagrafici"
            },
            DBClientsColumns.EMAIL.value: {
                "type": ctk.CTkEntry,
                "label": "Email",
                "section": "Dati Anagrafici"
            },
            DBClientsColumns.SEDE_LEGALE.value: {
                "type": ctk.CTkEntry,
                "label": "Sede Legale",
                "section": "Dati Anagrafici"
            },

            # Sezione Settore e Tipologia
            DBClientsColumns.SETTORE.value: {
                "type": CatalogFilterableComboBox,
                "label": "Settore",
                "section": "Settore & Tipologia",
                "values": self._get_business_sector_values(),
                "show_add_button": True,
                "add_button_text": "Aggiungi un settore",
                "add_button_command": self.open_add_business_sector
            },
            DBClientsColumns.TIPOLOGIA.value: {
                "type": ctk.CTkOptionMenu,
                "label": "Tipologia",
                "section": "Settore & Tipologia",
                "values": [item.value for item in TipologiaCliente]
            },

            # Sezione Referente
            DBClientsColumns.REFERENTE.value: {
                "type": ctk.CTkEntry,
                "label": "Referente",
                "section": "Referente"
            },
            DBClientsColumns.CONTATTO_REFERENTE.value: {
                "type": ctk.CTkEntry,
                "label": "Contatto Referente",
                "section": "Referente"
            },

            # Sezione Note
            DBClientsColumns.NOTE.value: {
                "type": ctk.CTkTextbox,  # Usiamo Textbox per note più lunghe
                "label": "Note",
                "section": "Note",
                "height": 100
            }
        }

        # Regole di validazione
        validation_rules = {
            DBClientsColumns.NAME.value: (
                lambda val: val.strip() != "",
                "Il nome del cliente non può essere vuoto"
            ),
            DBClientsColumns.PARTITA_IVA.value: (
                lambda val: val == "" or (len(val) == 11 and val.isdigit()),
                "Partita IVA non valida (11 cifre)"
            ),
            DBClientsColumns.EMAIL.value: (
                lambda val: val == "" or re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", val),
                "Formato email non valido"
            )
        }

        # Inizializzazione strutture dati
        self.client_info_widgets = {}
        self.error_labels = {}
        sections = {}

        # Creazione frame principale
        self.info_frame = ctk.CTkFrame(self.content_frame, border_width=2, border_color="#2659ab")
        self.info_frame.pack(fill="both", expand=True, pady=10, padx=25)

        # Configurazione griglia
        self.info_frame.grid_columnconfigure(0, weight=1, uniform="col")
        self.info_frame.grid_columnconfigure(1, weight=1, uniform="col")

        # Creazione sezioni
        sections_order = [
            "Dati Anagrafici",
            "Settore & Tipologia",
            "Referente",
            "Note"
        ]

        # Crea i frame per ogni sezione
        for i, section_name in enumerate(sections_order):
            frame = ctk.CTkFrame(self.info_frame)
            column = 0 if i % 2 == 0 else 1
            row = i // 2
            frame.grid(row=row, column=column, sticky="nsew", padx=15, pady=15)
            frame.grid_columnconfigure(1, weight=1)
            sections[section_name] = {
                "frame": frame,
                "row": 0
            }

            # Titolo della sezione
            ctk.CTkLabel(frame, text=section_name, font=("Arial", 14, "bold")).grid(
                row=0, column=0, columnspan=2, sticky="w", padx=15, pady=5
            )
            sections[section_name]["row"] += 1

        # Popolamento delle sezioni
        for field, config in self.entry_fields.items():
            section = sections[config["section"]]
            frame = section["frame"]
            row = section["row"]

            # Creazione label
            lbl = ctk.CTkLabel(frame, text=config["label"] + ":")
            lbl.grid(row=row, column=0, sticky="w", padx=(15, 5), pady=(2, 5))

            # Creazione widget
            value = str(client_data.get(field, ""))

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

                current_value = next(
                    (desc for key, desc in self.catalogo_elenchi["clients_business_sectors"] if key == value),
                    value
                )
                widget.set_value(current_value, safe_mode=False)

            elif config["type"] == ctk.CTkOptionMenu:
                widget = config["type"](frame, values=config.get("values", []))
                widget.set(value if value else config.get("values", [""])[0])

            elif config["type"] == ctk.CTkTextbox:
                widget = config["type"](frame, height=config.get("height", 50))
                widget.insert("1.0", value)
            else:
                widget = config["type"](frame)
                widget.insert(0, value)

            widget.grid(
                row=row,
                column=1,
                sticky="ew",
                padx=(5, 15),
                pady=(2, 5),
                rowspan=2 if config["type"] == ctk.CTkTextbox else 1
            )
            self.client_info_widgets[field] = widget

            # Gestione validazione
            if field in validation_rules:
                validation_func, error_message = validation_rules[field]

                error_lbl = ctk.CTkLabel(frame, text="", text_color="#e8e5dc")
                error_lbl.grid(
                    row=row + (2 if config["type"] == ctk.CTkTextbox else 1),
                    column=1,
                    sticky="w",
                    padx=5,
                    pady=(0, 10)
                )
                self.error_labels[field] = error_lbl

                if config["type"] != ctk.CTkTextbox:
                    widget.bind("<FocusOut>",
                                lambda e, w=widget, vl=validation_func, el=error_lbl, em=error_message:
                                ViewUtils.validate_entry(w, vl, el, em))
                else:
                    widget.bind("<FocusOut>",
                                lambda e, w=widget, vl=validation_func, el=error_lbl, em=error_message:
                                ViewUtils.validate_textbox(w, vl, el, em))

            # Aggiorna contatore righe
            section["row"] += 3 if config["type"] == ctk.CTkTextbox else 2

        buttons_frame = ctk.CTkFrame(self.info_frame, fg_color="#2b2b2b")
        buttons_frame.grid(row=2, column=0, columnspan=2, pady=(5, 15), padx=20, sticky="WE")

        # Bottone Salva
        self.save_info_btn = ctk.CTkButton(buttons_frame, text="Salva Cliente", command=self.save_client_mod)
        self.save_info_btn.pack(padx=(400, 10), pady=(20, 20), side="left")

        # Bottone Elimina
        self.delete_btn = ctk.CTkButton(buttons_frame, text="Elimina Cliente",
                                        fg_color="#8B0000", hover_color="#A52A2A",
                                        command=self.delete_client)
        self.delete_btn.pack(padx=10, pady=(20, 20), side="right", anchor="e")

    def save_client_mod(self):
        client_data = {
            DBClientsColumns.NAME.value: self.client_info_widgets[
                DBClientsColumns.NAME.value].get().strip(),
            DBClientsColumns.PARTITA_IVA.value: self.client_info_widgets[
                DBClientsColumns.PARTITA_IVA.value].get().strip(),
            DBClientsColumns.EMAIL.value: self.client_info_widgets[
                DBClientsColumns.EMAIL.value].get().strip(),
            DBClientsColumns.SEDE_LEGALE.value: self.client_info_widgets[
                DBClientsColumns.SEDE_LEGALE.value].get().strip(),
            DBClientsColumns.REFERENTE.value: self.client_info_widgets[
                DBClientsColumns.REFERENTE.value].get().strip(),
            DBClientsColumns.CONTATTO_REFERENTE.value: self.client_info_widgets[
                DBClientsColumns.CONTATTO_REFERENTE.value].get().strip(),
            DBClientsColumns.NOTE.value: self.client_info_widgets[
                DBClientsColumns.NOTE.value].get("1.0", "end-1c").strip(),
            DBClientsColumns.SETTORE.value: self.client_info_widgets[
                DBClientsColumns.SETTORE.value].get_value(),
            DBClientsColumns.TIPOLOGIA.value: self.client_info_widgets[
                DBClientsColumns.TIPOLOGIA.value].get()
        }

        # Chiamata al controller per salvare i dati
        success, message = self.client_controller.update_client(self.current_client_id, client_data)
        if success:
            print(
                f"Cliente {self.clients_query_service.retrieve_client_map_by_id(self.current_client_id)[DBClientsColumns.NAME.value]} salvato con successo")
            ViewUtils.show_confirm_popup_2(self.content_frame, "SALVATAGGIO COMPLETATO", message)
            self.switch_modify.deselect()
            self.toggle_edit(self.content_frame)

        else:
            # Mostra il messaggio d'errore
            print(message)
            ViewUtils.show_error_popup(self.content_frame, "ERRORE", message)

    def delete_client(self):
        confirmation = ViewUtils.ask_confirmation_popup(self.content_frame, "Stai per eliminare questo cliente.\nDesideri continuare ?", "ELIMINAZIONE CLIENTE" )
        if confirmation:
            #check if something link to this client
            invoices = self.invoices_query_service.retrieve_invoice_map_list_by_client(self.current_client_id)
            productions = self.productions_query_service.retrieve_productions_map_list_by_client_id(self.current_client_id)
            refunds = self.refunds_query_service.retrieve_refunds_map_list_by_client_id(self.current_client_id)

            if len(invoices) == 0 and len(productions) == 0 and len(refunds) == 0 :
                success, message = self.client_controller.delete_client(self.current_client_id)
                if success:
                    print(message)
                    ViewUtils.show_confirm_popup_simple(self.content_frame, "CONFERMA ELIMINAZIONE", message)
                else:
                    # Mostra il messaggio d'errore
                    print(message)
                    ViewUtils.show_error_popup(self.content_frame, "ERRORE", message)
            else:
                ViewUtils.show_error_popup(self.info_frame, message="Impossibile eliminare il cliente.\n\n"
                                                                    "Esiste un item collegato a questo cliente.\n"
                                                                    "Eliminare ogni riferimento a questo cliente per poterlo eliminare dal database.")

    def _get_business_sector_values(self):
        return [
            value for key, value in self.catalogo_elenchi["clients_business_sectors"]
            if key != "ADD_SECTOR"
        ]

    def open_add_business_sector(self):
        """Apre la modale riusabile per aggiungere un settore di business."""
        if self.business_sector_adder_view is not None and self.business_sector_adder_view.winfo_exists():
            self.business_sector_adder_view.focus()
            self.business_sector_adder_view.lift()
            return

        self.business_sector_adder_view = BusinessSectorAdderView(
            parent=self,
            app_context=self.app_context,
            on_item_created=self._on_business_sector_created,
            on_close=self._clear_business_sector_adder_view
        )

    def _on_business_sector_created(self, sector_key, sector_value):
        """Aggiorna il menu settori del dettaglio dopo la creazione di una nuova voce."""
        sector_widget = self.client_info_widgets.get(DBClientsColumns.SETTORE.value)
        if sector_widget is not None:
            sector_widget.set_values(
                self._get_business_sector_values(),
                preserve_current=False
            )
            sector_widget.set_value(sector_value, safe_mode=False)
        self.grab_set()

    def _clear_business_sector_adder_view(self):
        """Azzera il riferimento all'adder dei settori e ripristina il grab."""
        self.business_sector_adder_view = None
        if self.winfo_exists():
            self.grab_set()

    def toggle_edit(self, parent):
        """
        Abilita o disabilita la modifica dei widget nella finestra di modifica utente.
        """
        # Determina lo stato (abilitato/disabilitato) in base al valore dello switch
        state = ctk.NORMAL if self.switch_modify.get() else ctk.DISABLED

        # Cambia anche lo stato del pulsante Salva
        self.save_info_btn.configure(state=state)
        self.delete_btn.configure(state=state)

        for w in parent.winfo_children():
            # se è un Entry
            if isinstance(w, (ctk.CTkEntry, ctk.CTkTextbox)):
                w.configure(state=state, text_color="#636363" if state == ctk.DISABLED else "#c2c2c2")
            # se è un OptionMenu
            elif isinstance(w, ctk.CTkOptionMenu):
                w.configure(state=state)
            elif isinstance(w, FilterableComboBox):
                w.configure(state=state, text_color="#c2c2c2")
            # se è un Frame/container, scendi ricorsivamente
            elif isinstance(w, (ctk.CTkFrame, ctk.CTkScrollableFrame, ctk.CTkToplevel)):
                self.toggle_edit(w)

    def _create_invoices_history(self):
        """Crea la sezione storico fatture"""
        section_frame = ctk.CTkFrame(self.wrapper_frame, border_width=2, border_color="#2659ab")
        section_frame.pack(fill="both", side="left", expand=True, pady=0, padx=(0, 30))

        ctk.CTkLabel(section_frame, text="FATTURE", font=("Arial", 14, "bold")).pack(anchor="w", pady=(10, 10),
                                                                                            padx=10)

        global_infos = {
            "TOTALE FATTURATO (All Time)": {
                "value": self.clients_analyzer_service.calcola_tot_entrate_cliente(self.current_client_id, include_unpaid_invoices = True, year = -1),
                "uom": "€"
            },
            f"TOTALE FATTURATO {datetime.now().year}": {
                "value": self.clients_analyzer_service.calcola_tot_entrate_cliente(self.current_client_id, include_unpaid_invoices=False),
                "uom": "€"
            }
        }

        self.global_infos_invoices_widgets = ViewUtils.construct_global_infos_cards(section_frame, global_infos)

        ctk.CTkLabel(section_frame, text=f"- Elenco Fatture {datetime.now().year} -", font=("Arial", 14, "italic"), text_color="gray", justify="right"
                     ).pack(anchor="w", padx=10, pady=(10, 0))

        # tabella invoices
        invoices_frame = ctk.CTkScrollableFrame(section_frame, height=300)
        invoices_frame.pack(fill="both", expand=True, padx=(10, 20), pady=(10, 20))

        # popolo gli invoices
        invoices = self.clients_query_service.retrieve_client_with_invoices_map_list(self.current_client_id, include_unpaid_invoices = False) #ottimizzare se sono troppe le fatture retrievate
        for invoice in invoices:
            if invoice[DBInvoicesColumns.NUMERO_FATTURA.value] is not None:
                nome_fattura = invoice[DBInvoicesColumns.NUMERO_FATTURA.value]
                id_fattura = invoice[DBInvoicesColumns.ID.value]
                id_produzione = invoice[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value]
                produzione = self.productions_query_service.retrieve_production_map_by_id(id_produzione)
                nome_prod = produzione[DBProductionsColumns.NAME.value] if produzione else "Produzione non trovata"
                fattura_button = ctk.CTkButton(invoices_frame,
                                               text=f"{nome_fattura} - {nome_prod}",
                                               command=lambda id=id_fattura: self.show_invoice_detail(id))
                fattura_button.pack(padx=10, pady=10, fill="x", expand=True)

    def show_invoice_detail(self, invoice_id):
        self.event_bus.publish(ViewUtils.EventBusKeys.SHOW_INVOICE_DETAIL, invoice_id)

    def _create_refunds_history(self):
        """Crea la sezione storico rimborsi"""
        section_frame = ctk.CTkFrame(self.wrapper_frame, border_width=2, border_color="#2659ab")
        section_frame.pack(fill="both", side="left", expand=True, pady=0, padx=(0, 30))

        ctk.CTkLabel(section_frame, text="RIMBORSI", font=("Arial", 14, "bold")).pack(anchor="w", pady=(10, 10),
                                                                                        padx=10)

        global_infos = {
            "TOT RIMBORSI (All Time)": {
                "value": self.refunds_analyzer_service.calculate_tot_refunds_of_client(self.current_client_id, year=-1),
                "uom": "€"
            },
            f"TOT RIMBORSI {datetime.now().year}": {
                "value": self.refunds_analyzer_service.calculate_tot_refunds_of_client(self.current_client_id),
                "uom": "€"
            }
        }

        self.global_infos_refunds_widgets = ViewUtils.construct_global_infos_cards(section_frame, global_infos)

        ctk.CTkLabel(section_frame, text=f"- Elenco Rimborsi {datetime.now().year} -", font=("Arial", 14, "italic"), text_color="gray", justify="right"
                     ).pack(anchor="w", padx=10, pady=(10, 0))

        # tabella invoices
        refunds_frame = ctk.CTkScrollableFrame(section_frame, height=300)
        refunds_frame.pack(fill="both", expand=True, padx=(10, 20), pady=(10, 20))

        # popolo gli invoices
        refunds = self.refunds_query_service.retrieve_refunds_map_list_by_client_id(self.current_client_id)
        for ref in refunds:
            if ref[DBRefundsColumns.REFUND_NAME.value] is not None:
                nome_refund = ref[DBRefundsColumns.REFUND_NAME.value]
                id_refund = ref[DBRefundsColumns.ID.value]
                refund_button = ctk.CTkButton(refunds_frame,
                                                  text=f"{nome_refund}",
                                                  command=lambda id=id_refund: self.show_refund_detail(id))
                refund_button.pack(padx=10, pady=10, fill="x", expand=True)

    def show_refund_detail(self, refund_id):
        self.event_bus.publish(ViewUtils.EventBusKeys.SHOW_REFUND_DETAIL, refund_id)

    def _create_productions_history(self):
        """Crea la sezione storico fatture"""
        section_frame = ctk.CTkFrame(self.wrapper_frame, border_width=2, border_color="#2659ab")
        section_frame.pack(fill="both", side="left", expand=True, pady=0, padx=(0, 30))

        ctk.CTkLabel(section_frame, text="PRODUZIONI", font=("Arial", 14, "bold")).pack(anchor="w", pady=(10, 10),
                                                                                     padx=10)

        global_infos = {
            "# PRODUZIONI (All time)": {
                "value": self.productions_analyzer_service.count_productions_of_client(self.current_client_id, year=-1),
                "uom": ""
            },
            f"# PRODUZIONI {datetime.now().year}": {
                "value": self.productions_analyzer_service.count_productions_of_client(self.current_client_id, include_prod_with_unpaid_invoices=False),
                "uom": ""
            }
        }

        self.global_infos_productions_widgets = ViewUtils.construct_global_infos_cards(section_frame, global_infos)

        ctk.CTkLabel(section_frame, text=f"- Elenco Produzioni {datetime.now().year} -", font=("Arial", 14, "italic"), text_color="gray", justify="right"
                     ).pack(anchor="w", padx=10, pady=(10, 0))


        # tabella invoices
        productions_frame = ctk.CTkScrollableFrame(section_frame, height=300)
        productions_frame.pack(fill="both", expand=True, padx=(10, 20), pady=(10, 20))

        # popolo gli invoices
        productions = self.productions_query_service.retrieve_productions_map_list_by_client_id(self.current_client_id, include_prod_with_unpaid_invoices=False)
        for production in productions:
            if production[DBProductionsColumns.NAME.value] is not None:
                nome_produzione = production[DBProductionsColumns.NAME.value]
                id_produzione = production[DBProductionsColumns.ID.value]
                produzione_button = ctk.CTkButton(productions_frame,
                                               text=f"{nome_produzione}",
                                               command=lambda id=id_produzione: self.show_production_detail(id))
                produzione_button.pack(padx=10, pady=10, fill="x", expand=True)

    def show_production_detail(self, production_id):
        self.event_bus.publish(ViewUtils.EventBusKeys.SHOW_PRODUCTION_DETAIL, production_id)

    def _clear_content(self):
        """Distrugge tutti i widget dinamici"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def _cleanup_and_go_back(self):
        """Pulizia completa prima di tornare indietro"""
        self._clear_content()
        self.pack_forget()
        self.back_callback()

    def cleanup(self):
        """Pulizia completa per liberare memoria - DA AGGIUNGERE IN OGNI VIEW"""
        try:
            print(f"Cleanup di {self.__class__.__name__}")

            # 1. Cancella tutti gli after scheduled
            if hasattr(self, '_after_ids'):
                for after_id in self._after_ids:
                    try:
                        self.after_cancel(after_id)
                    except:
                        pass
                self._after_ids.clear()

            # 2. Distruggi tutte le card e widget dinamici
            card_lists = [
                'payment_card_list', 'invoice_card_list', 'client_card_list',
                'supplier_card_list', 'production_card_list', 'expenses_card_list',
                'salaries_card_list', 'refund_card_list', 'account_card_list'
            ]

            for card_attr in card_lists:
                if hasattr(self, card_attr):
                    card_dict = getattr(self, card_attr)
                    for card_name, card in card_dict.items():
                        try:
                            card.destroy()
                        except:
                            pass
                    card_dict.clear()

            # 3. Pulisci dizionari e liste
            data_attrs = [
                'cards_warnings', 'global_infos', 'amount_aggregate_labels',
                'payment_card_labels_status', 'invoice_card_labels_status',
                'production_card_labels_status'
            ]

            for attr in data_attrs:
                if hasattr(self, attr):
                    getattr(self, attr).clear()

            # 4. Distruggi i container principali se esistono
            container_attrs = [
                'main_container', 'detail_container', 'payments_cards_frame',
                'invoices_cards_frame', 'clients_cards_frame', 'suppliers_cards_frame',
                'productions_cards_frame', 'expenses_cards_frame', 'refunds_cards_frame',
                'accounts_cards_frame', 'salaries_cards_frame'
            ]

            for attr in container_attrs:
                if hasattr(self, attr):
                    container = getattr(self, attr)
                    try:
                        # Distruggi solo se il container esiste ancora
                        if container.winfo_exists():
                            for widget in container.winfo_children():
                                try:
                                    widget.destroy()
                                except:
                                    pass
                    except:
                        pass

            # 5. Pulisci i riferimenti ai controller (opzionale)
            if hasattr(self, 'db_model'):
                self.db_model = None

        except Exception as e:
            print(f"Errore durante il cleanup di {self.__class__.__name__}: {e}")

    def _track_after(self, ms, func, *args):
        """Versione tracciata di after()"""
        after_id = self._orig_after(ms, func, *args)
        self._after_ids.add(after_id)
        return after_id

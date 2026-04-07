import customtkinter as ctk
from tkcalendar import Calendar
import re
from datetime import datetime, timedelta

from Analyzers.Invoice_analyzer_service import InvoiceAnalyzerService
from App_context import AppContext
from Gestionale_Enums import*
from Controllerss.Invoice_controller import InvoiceController
from Event_bus import EventBus
from QueryServices.Account_query_service import AccountQueryService
from Views .View_utils import ViewUtils, FilterableComboBox
from QueryServices.Clients_query_service import ClientQueryService
from QueryServices.Productions_query_service import ProductionQueryService
from QueryServices.Invoices_query_service import InvoiceQueryService

from Controllers import UserController, UpdatesController, AccountController


class InvoiceDetailView(ctk.CTkFrame):
    def __init__(self, parent, app_context:AppContext, back_callback):
        super().__init__(parent)
        self.app_context:AppContext = app_context
        self.invoice_controller:InvoiceController = app_context.invoice_controller
        self.invoices_query_service: InvoiceQueryService = app_context.invoices_query_service
        self.invoices_analyzer_service: InvoiceAnalyzerService = app_context.invoices_analyzer_service
        self.user_controller:UserController = app_context.user_controller
        self.clients_query_service:ClientQueryService = app_context.clients_query_service
        self.productions_query_service:ProductionQueryService = app_context.productions_query_service
        self.accounts_query_service:AccountQueryService = app_context.account_query_service
        self.back_callback = back_callback
        self.update_controller:UpdatesController = app_context.update_controller
        self.event_bus:EventBus = app_context.event_bus
        self.current_invoice_id = None

        self.configure(fg_color="transparent")

        # Widgets persistenti (vanno creati una volta sola)
        self.head_frame = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.back_button = ctk.CTkButton(
            self.head_frame,
            text="Elenco Fatture",
            command=self._cleanup_and_go_back
        )
        self.title_label = ctk.CTkLabel(self.head_frame, font=("Arial", 22, "bold"))

        self.invoice_info_widgets: dict[str, ctk.CTkEntry | ctk.CTkOptionMenu] = {}

        self.nome_conto_string = "CONTO"
        self.nome_cliente_string = "CLIENTE"
        self.nome_user_string = "UTENTE"
        self.nome_fattura_associata_string = "FATTURA ASSOCIATA"
        self.nome_produzione_associata_string = "PRODUZIONE ASSOCIATA"

        # Container per i contenuti dinamici
        self.content_frame = ctk.CTkScrollableFrame(self)

        self.switch_modify = ctk.CTkSwitch(self.head_frame, text="Abilita la modifica", command=lambda: self.toggle_edit(self.content_frame))

        # Layout iniziale
        self._setup_base_layout()

        self.update_controller.register_on_adding_payment_view_cllbks(self.toggle_warning_global_info_payments)


    def _setup_base_layout(self):
        """Inizializza la struttura base del layout"""
        self.head_frame.pack(fill="x", pady=5, padx=5)
        self.back_button.pack(anchor="w", side="left", pady=10, padx=10)
        self.title_label.pack(anchor="c", side="left", fill="x", expand=True, pady=10)
        self.switch_modify.pack(anchor="e", side="left", pady=10, padx=10)
        self.content_frame.pack(fill="both", expand=True, pady=20, padx=20)

    def create_detail_tab(self, invoice_id):
        """Ricrea la vista dettaglio per una fattura specifica"""
        self.current_invoice_id = invoice_id

        # 1. Pulizia dei widget precedenti
        self._clear_content()

        # 2. Caricamento dati
        invoice = self.invoices_query_service.retrieve_invoice_map_by_id(invoice_id)

        #prendo il nome del conto:
        id_conto = invoice[DBInvoicesColumns.ID_CONTO.value]
        conto = self.accounts_query_service.retrieve_account_map_by_id(id_conto)
        nome_conto = conto[DBAccountsColumns.NAME.value] if conto else "Conto non trovato"
        invoice[self.nome_conto_string] = nome_conto

        #prendo il nome dell' utente:
        id_user = invoice[DBInvoicesColumns.ID_UTENTE.value]
        user = self.user_controller.retrieve_user_map_by_id(id_user)
        nome_user = user[DBUsersColumns.FIRST_NAME.value] + user[DBUsersColumns.LAST_NAME.value] if user else "Utente non trovato"
        invoice[self.nome_user_string] = nome_user

        #prendo il nome del cliente
        id_cliente = invoice[DBInvoicesColumns.ID_CLIENTE.value]
        cliente = self.clients_query_service.retrieve_client_map_by_id(id_cliente)
        nome_cliente = cliente[DBClientsColumns.NAME.value] if cliente else "Cliente non trovato"
        invoice[self.nome_cliente_string] = nome_cliente

        #prendo il nome della produzione associata
        id_prod = invoice[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value]
        prod = self.productions_query_service.retrieve_production_map_by_id(id_prod)
        nome_produzione = prod[DBProductionsColumns.NAME.value] if prod else "Produzione non trovata"
        invoice[self.nome_produzione_associata_string] = nome_produzione

        #prendo il nome della fattura associata
        id_fattura_ass = invoice[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value]
        fatt_ass = self.invoices_query_service.retrieve_invoice_map_by_id(id_fattura_ass)
        nome_fatt_ass = fatt_ass[DBInvoicesColumns.NUMERO_FATTURA.value] if fatt_ass else "Nessuna fattura associata"
        invoice[self.nome_fattura_associata_string] = nome_fatt_ass

        # 3. Aggiornamento elementi persistenti
        self.title_label.configure(
            text=f"{invoice[DBInvoicesColumns.NUMERO_FATTURA.value]}")

        # 4. Creazione contenuti dinamici
        self._create_invoice_info_section(invoice)
        self.toggle_edit(self.content_frame)

        self.wrapper_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.wrapper_frame.pack(padx=15, pady=(90, 0), fill="both", expand=True)
        self.wrapper_frame2 = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.wrapper_frame2.pack(padx=15, pady=(90, 90), fill="both", expand=True)

        self._create_payments_history()
        self._create_production_expenses_history()

    def _create_invoice_info_section(self, invoice_data):
        # Aggiunta campi derivati
        self.derived_fields = {
            DBInvoicesColumns.CASSA_INPS.value: "Cassa INPS (€)",
            DBInvoicesColumns.IMPONIBILE.value: "Imponibile (€)",
            DBInvoicesColumns.IVA.value: "IVA (€)",
            DBInvoicesColumns.TOT_DOCUMENTO.value: "Totale Documento (€)",
            DBInvoicesColumns.RITENUTA.value: "Ritenuta (€)",
            DBInvoicesColumns.NETTO_A_PAGARE.value: "Netto a Pagare (€)"
        }

        """self.nome_user_string: {
            "type": ctk.CTkOptionMenu,
            "label": "Utente",
            "section": "Dati Generali",
            "values": [u[DBUsersColumns.FIRST_NAME.value] + " " + u[DBUsersColumns.LAST_NAME.value] for u in
                       self.user_controller.retrieve_users_map_list()]
        },"""

        self.entry_fields = {
            # Dati Generali
            DBInvoicesColumns.DATA_CREAZIONE.value: {
                "type": Calendar,
                "label": "Data Creazione",
                "section": "Dati Generali"
            },
            self.nome_cliente_string: {
                "type": FilterableComboBox,
                "label": "Cliente",
                "section": "Dati Generali",
                "values": [c[DBClientsColumns.NAME.value] for c in self.clients_query_service.retrieve_clients_map_list()],
                "command": lambda selected_value: self.toggle_production_list(selected_value)
            },

            # Dati Fiscali
            DBInvoicesColumns.SERVIZI.value: {
                "type": ctk.CTkEntry,
                "label": "Importo Servizi (€)",
                "section": "Dati Fiscali"
            },
            DBInvoicesColumns.RIMBORSI.value: {
                "type": ctk.CTkEntry,
                "label": "Rimborsi (€)",
                "section": "Dati Fiscali"
            },
            DBInvoicesColumns.RIVALSA_INPS.value: {
                "type": ctk.CTkEntry,
                "label": "Rivalsa INPS (€)",
                "section": "Dati Fiscali"
            },

            # Campi derivati (non editabili)
            **{
                key: {
                    "type": ctk.CTkEntry,
                    "label": label,
                    "section": "Dati Fiscali"
                } for key, label in self.derived_fields.items()
            },

            DBInvoicesColumns.METODO_PAGAMENTO.value: {
                "type": ctk.CTkOptionMenu,
                "label": "Metodo Pagamento",
                "section": "Dati Fiscali",
                "values": [item.value for item in PaymentsMethods]
            },
            self.nome_conto_string: {
                "type": ctk.CTkOptionMenu,
                "label": "Conto",
                "section": "Dati Fiscali",
                "values": [c[DBAccountsColumns.NAME.value] for c in self.accounts_query_service.retrieve_accounts_map_list()]
            },

            # Dati Pagamento
            DBInvoicesColumns.NUMERO_RATE.value: {
                "type": ctk.CTkOptionMenu,
                "label": "Numero Rate",
                "section": "Dati Pagamento",
                "values": [item.value for item in Rateizzazione],
                "command": lambda selected_value: self.setup_expiration_dates(selected_value)
            },
            DBInvoicesColumns.DATA_SCADENZA_1.value: {
                "type": Calendar,
                "label": "Scadenza 1",
                "section": "Dati Pagamento"
            },
            DBInvoicesColumns.DATA_SCADENZA_2.value: {
                "type": Calendar,
                "label": "Scadenza 2",
                "section": "Dati Pagamento"
            },
            DBInvoicesColumns.DATA_SCADENZA_3.value: {
                "type": Calendar,
                "label": "Scadenza 3",
                "section": "Dati Pagamento"
            },

            # Collegamenti
            self.nome_produzione_associata_string: {
                "type": ctk.CTkOptionMenu,
                "label": "Produzione Associata",
                "section": "Collegamenti",
                "values": [p[DBProductionsColumns.NAME.value] for p in
                           self.productions_query_service.retrieve_productions_map_list_by_client_id(
                               invoice_data[DBInvoicesColumns.ID_CLIENTE.value],
                               include_prod_with_unpaid_invoices = True
                           )]
            },
            self.nome_fattura_associata_string: {
                "type": ctk.CTkLabel,
                "label": "Fattura Associata",
                "section": "Collegamenti",
                "values": [i[DBInvoicesColumns.NUMERO_FATTURA.value] for i in
                           self.invoices_query_service.retrieve_invoices_map_list(include_unpaid_invoices=True)
                           if i[DBInvoicesColumns.TIPO.value] != TipologiaFattura.NOTA_DI_CREDITO]
            },

            # Note e campi statici
            DBInvoicesColumns.NOTE.value: {
                "type": ctk.CTkEntry,
                "label": "Note",
                "section": "Note/Status"
            },
            DBInvoicesColumns.STATUS.value: {
                "type": ctk.CTkLabel,
                "label": "Status",
                "section": "Note/Status"
            },
            DBInvoicesColumns.TIPO.value: {
                "type": ctk.CTkLabel,
                "label": "Tipo Documento",
                "section": "Note/Status"
            }
        }

        self.error_fields = {
            DBInvoicesColumns.NUMERO_FATTURA.value: "Campo obbligatorio",
            DBInvoicesColumns.SERVIZI.value: "Valore numerico con massimo 2 decimali",
            DBInvoicesColumns.RIMBORSI.value: "Valore numerico con massimo 2 decimali",
            DBInvoicesColumns.RIVALSA_INPS.value: "Valore numerico con massimo 2 decimali"
        }

        validation_rules = {
            DBInvoicesColumns.NUMERO_FATTURA.value: (
                lambda val: val.strip() != "",
                "Campo obbligatorio"
            ),
            DBInvoicesColumns.SERVIZI.value: (
                lambda val: re.fullmatch(r"^\d+(\.\d{1,2})?$", val),
                "Formato valido: 1234.56"
            ),
            DBInvoicesColumns.RIMBORSI.value: (
                lambda val: re.fullmatch(r"^\d+(\.\d{1,2})?$", val),
                "Formato valido: 1234.56"
            ),
            DBInvoicesColumns.RIVALSA_INPS.value: (
                lambda val: re.fullmatch(r"^\d+(\.\d{1,2})?$", val),
                "Formato valido: 1234.56"
            )
        }

        # Inizializzazione strutture dati
        self.invoice_info_widgets = {}
        self.invoice_info_labels = {}
        self.error_labels = {}
        sections = {}

        # Creazione frame principale
        info_frame = ctk.CTkFrame(self.content_frame, border_width=2, border_color="#2659ab")
        info_frame.pack(fill="both", expand=True, pady=10, padx=25)

        # Configurazione griglia a 3 colonne
        info_frame.grid_columnconfigure(0, weight=1, uniform="col")
        info_frame.grid_columnconfigure(1, weight=1, uniform="col")
        info_frame.grid_columnconfigure(2, weight=1, uniform="col")

        # Sezioni organizzate per colonne
        sections_order = [
            "Dati Generali",
            "Dati Fiscali",
            "Dati Pagamento",
            "Collegamenti",
            "Note/Status"
        ]

        # Creazione frame sezioni
        for i, section_name in enumerate(sections_order):
            frame = ctk.CTkFrame(info_frame)
            column = i if i <= 2 else i - 3  # Per sezioni oltre la terza, riparte dalla prima colonna
            frame.grid(row=0 if i <= 2 else 1, column=column, sticky="nsew", padx=15, pady=15)
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
        for field, config in self.entry_fields.items():
            section = sections[config["section"]]
            frame = section["frame"]
            row = section["row"]

            # Creazione label
            lbl = ctk.CTkLabel(frame, text=config["label"] + ":")
            self.invoice_info_labels[field] = lbl

            if field in validation_rules:
                self.pady_value = (5, 5)
            else:
                self.pady_value = (5, 35)
            lbl.grid(row=row, column=0, sticky="w", padx=(15, 5), pady=self.pady_value)

            # Creazione widget
            if config["type"] == ctk.CTkLabel:
                value = str(invoice_data.get(field, ""))
                widget = config["type"](frame, text=value)
            else:
                if config["type"] == FilterableComboBox:
                    widget = config["type"](
                        frame,
                        values=config.get("values", []),
                        autofill=True,
                        command=config.get("command")
                    )
                    widget.set_value(str(invoice_data.get(field, "")), safe_mode=False)
                elif config["type"] == ctk.CTkOptionMenu:
                    widget = config["type"](frame, values=config.get("values", []))
                    values = config.get("values", [""])
                    if len(values) > 0:
                        widget.set(invoice_data.get(field, values[0]))

                    # Se il config ha una chiave "command", la assegna
                    if "command" in config:
                        widget.configure(command=config["command"])

                elif config["type"] == Calendar:
                    widget = config["type"](frame, date_pattern=ViewUtils.date_pattern)
                    value = invoice_data.get(field, "")
                    widget.selection_set(str(value)) if value else widget.selection_set(datetime.today())
                else:
                    widget = config["type"](frame)
                    value = str(invoice_data.get(field, ""))
                    widget.insert(0, value)


            widget.grid(row=row, column=1, sticky="ew" if config["type"] != ctk.CTkLabel else "w", padx=(5, 15), pady=self.pady_value)
            self.invoice_info_widgets[field] = widget


            # Gestione validazione
            if field in validation_rules:
                validation_func, error_message = validation_rules[field]

                error_lbl = ctk.CTkLabel(frame, text="", text_color="#e8e5dc")
                error_lbl.grid(row=row + 1, column=1, sticky="w", padx=5, pady=(0, 10))
                self.error_labels[field] = error_lbl

                widget.bind("<FocusOut>",
                            lambda e, w=widget, vl=validation_func, el=error_lbl, em=error_message:
                            ViewUtils.validate_entry(w, vl, el, em))

                section["row"] += 2
            else:
                section["row"] += 1

        self.setup_expiration_dates(self.invoice_info_widgets[DBInvoicesColumns.NUMERO_RATE.value].get())

        # Binding calcolo automatico importi derivati
        self.invoice_info_widgets[DBInvoicesColumns.SERVIZI.value].bind("<FocusOut>", lambda event: self.toggle_importi_derivati_fattura(event, False))
        self.invoice_info_widgets[DBInvoicesColumns.RIMBORSI.value].bind("<FocusOut>", lambda event: self.toggle_importi_derivati_fattura(event, False))
        self.invoice_info_widgets[DBInvoicesColumns.RIVALSA_INPS.value].bind("<FocusOut>", lambda event: self.toggle_importi_derivati_fattura(event, True))

        buttons_frame = ctk.CTkFrame(info_frame, fg_color="#2b2b2b")
        buttons_frame.grid(row=2, column=0, columnspan=3, pady=(5, 15), padx=20, sticky="WE")

        # Bottone Salva
        self.save_invoice_btn = ctk.CTkButton(buttons_frame, text="Salva Fattura", command=self.save_invoice_mod)
        self.save_invoice_btn.pack(padx= (800, 10), pady=(20, 20), side="left")

        #bottone storna
        self.storna_btn = ctk.CTkButton(buttons_frame, text="Storna Fattura", command=self.storna_invoice)
        self.storna_btn.pack(padx= 10, pady=(20, 20), side="right", anchor="e")

    def toggle_edit(self, parent):
        """
        Abilita o disabilita la modifica dei widget nella finestra di modifica utente.
        I campi derivati e il campo RIVAlSA_INPS per utenti con regime ordinario restano disabilitati.
        """
        state = ctk.NORMAL if self.switch_modify.get() else ctk.DISABLED

        # Stato del pulsante Salva
        self.save_invoice_btn.configure(state=state)
        self.storna_btn.configure(state=state)

        # Recupera il regime fiscale dell'utente corrente
        invoice = self.invoices_query_service.retrieve_invoice_map_by_id(self.current_invoice_id)
        user_map = self.user_controller.retrieve_user_map_by_id(invoice[DBInvoicesColumns.ID_UTENTE.value])
        is_ordinario = user_map[
                           DBUsersColumns.REGIME_FISCALE.value] == self.user_controller.RegimeFiscale.ORDINARIO.value

        for w in parent.winfo_children():
            # Ottieni il campo associato a questo widget, se esiste
            widget_field = next((k for k, v in self.invoice_info_widgets.items() if v == w), None)

            # Verifica se campo derivato
            is_derived = widget_field in self.derived_fields if widget_field else False
            # Verifica se è il campo Rivalsa INPS con utente ordinario
            is_rivalsa_locked = widget_field == DBInvoicesColumns.RIVALSA_INPS.value and is_ordinario

            # Imposta stato finale
            widget_state = ctk.DISABLED if is_derived or is_rivalsa_locked else state

            if isinstance(w, ctk.CTkEntry):
                w.configure(state=widget_state, text_color="#636363" if widget_state == ctk.DISABLED else "#c2c2c2")
            elif isinstance(w, FilterableComboBox):
                w.state = widget_state
                w._apply_state()
            elif isinstance(w, ctk.CTkOptionMenu):
                w.configure(state=widget_state)
            elif isinstance(w, Calendar):
                w.configure(state=widget_state)
            elif isinstance(w, (ctk.CTkFrame, ctk.CTkScrollableFrame, ctk.CTkToplevel)):
                self.toggle_edit(w)

    def toggle_importi_derivati_fattura(self, event, isRivalsaInps):
        #prendo i dati necessari al calcolo degli importi derivati
        servizi =  float(self.invoice_info_widgets[DBInvoicesColumns.SERVIZI.value].get())
        rimborsi =  float(self.invoice_info_widgets[DBInvoicesColumns.RIMBORSI.value].get())
        rivalsa_inps = float(self.invoice_info_widgets[DBInvoicesColumns.RIVALSA_INPS.value].get())
        invoice = self.invoices_query_service.retrieve_invoice_map_by_id(self.current_invoice_id)
        user = self.user_controller.retrieve_user_map_by_id(invoice[DBInvoicesColumns.ID_UTENTE.value])
        regime_fiscale = user[DBUsersColumns.REGIME_FISCALE.value]
        client = self.clients_query_service.retrieve_client_map_by_id(invoice[DBInvoicesColumns.ID_CLIENTE.value])
        tipologia_cliente = client[DBClientsColumns.TIPOLOGIA.value]

        #ottengo gli importi derivati
        importi_derivati = self.invoices_analyzer_service.calcola_derivati_fattura(regime_fiscale, tipologia_cliente, servizi, rimborsi, rivalsa_inps)

        if not isRivalsaInps:
            #self.invoice_info_widgets[DBInvoicesColumns.RIVALSA_INPS.value].configure(state = ctk.NORMAL)
            self.invoice_info_widgets[DBInvoicesColumns.RIVALSA_INPS.value].delete(0, ctk.END)
            self.invoice_info_widgets[DBInvoicesColumns.RIVALSA_INPS.value].insert(0, importi_derivati[DBInvoicesColumns.RIVALSA_INPS.value])
            #self.invoice_info_widgets[DBInvoicesColumns.RIVALSA_INPS.value].configure(state=ctk.DISABLED)

            self.invoice_info_widgets[DBInvoicesColumns.CASSA_INPS.value].configure(state = ctk.NORMAL)
            self.invoice_info_widgets[DBInvoicesColumns.CASSA_INPS.value].delete(0, ctk.END)
            self.invoice_info_widgets[DBInvoicesColumns.CASSA_INPS.value].insert(0, importi_derivati[DBInvoicesColumns.CASSA_INPS.value])
            self.invoice_info_widgets[DBInvoicesColumns.CASSA_INPS.value].configure(state=ctk.DISABLED)


            self.invoice_info_widgets[DBInvoicesColumns.IMPONIBILE.value].configure(state = ctk.NORMAL)
            self.invoice_info_widgets[DBInvoicesColumns.IMPONIBILE.value].delete(0, ctk.END)
            self.invoice_info_widgets[DBInvoicesColumns.IMPONIBILE.value].insert(0, importi_derivati[DBInvoicesColumns.IMPONIBILE.value])
            self.invoice_info_widgets[DBInvoicesColumns.IMPONIBILE.value].configure(state=ctk.DISABLED)


            self.invoice_info_widgets[DBInvoicesColumns.IVA.value].configure(state = ctk.NORMAL)
            self.invoice_info_widgets[DBInvoicesColumns.IVA.value].delete(0, ctk.END)
            self.invoice_info_widgets[DBInvoicesColumns.IVA.value].insert(0, importi_derivati[DBInvoicesColumns.IVA.value])
            self.invoice_info_widgets[DBInvoicesColumns.IVA.value].configure(state=ctk.DISABLED)


            self.invoice_info_widgets[DBInvoicesColumns.TOT_DOCUMENTO.value].configure(state = ctk.NORMAL)
            self.invoice_info_widgets[DBInvoicesColumns.TOT_DOCUMENTO.value].delete(0, ctk.END)
            self.invoice_info_widgets[DBInvoicesColumns.TOT_DOCUMENTO.value].insert(0, importi_derivati[DBInvoicesColumns.TOT_DOCUMENTO.value])
            self.invoice_info_widgets[DBInvoicesColumns.TOT_DOCUMENTO.value].configure(state=ctk.DISABLED)



            self.invoice_info_widgets[DBInvoicesColumns.RITENUTA.value].configure(state = ctk.NORMAL)
            self.invoice_info_widgets[DBInvoicesColumns.RITENUTA.value].delete(0, ctk.END)
            self.invoice_info_widgets[DBInvoicesColumns.RITENUTA.value].insert(0, importi_derivati[DBInvoicesColumns.RITENUTA.value])
            self.invoice_info_widgets[DBInvoicesColumns.RITENUTA.value].configure(state=ctk.DISABLED)



            self.invoice_info_widgets[DBInvoicesColumns.NETTO_A_PAGARE.value].configure(state = ctk.NORMAL)
            self.invoice_info_widgets[DBInvoicesColumns.NETTO_A_PAGARE.value].delete(0, ctk.END)
            self.invoice_info_widgets[DBInvoicesColumns.NETTO_A_PAGARE.value].insert(0, importi_derivati[DBInvoicesColumns.NETTO_A_PAGARE.value])
            self.invoice_info_widgets[DBInvoicesColumns.NETTO_A_PAGARE.value].configure(state=ctk.DISABLED)
        else:
            self.invoice_info_widgets[DBInvoicesColumns.CASSA_INPS.value].configure(state=ctk.NORMAL)
            self.invoice_info_widgets[DBInvoicesColumns.CASSA_INPS.value].delete(0, ctk.END)
            self.invoice_info_widgets[DBInvoicesColumns.CASSA_INPS.value].insert(0, importi_derivati[
                DBInvoicesColumns.CASSA_INPS.value])
            self.invoice_info_widgets[DBInvoicesColumns.CASSA_INPS.value].configure(state=ctk.DISABLED)

            self.invoice_info_widgets[DBInvoicesColumns.IMPONIBILE.value].configure(state=ctk.NORMAL)
            self.invoice_info_widgets[DBInvoicesColumns.IMPONIBILE.value].delete(0, ctk.END)
            self.invoice_info_widgets[DBInvoicesColumns.IMPONIBILE.value].insert(0, importi_derivati[
                DBInvoicesColumns.IMPONIBILE.value])
            self.invoice_info_widgets[DBInvoicesColumns.IMPONIBILE.value].configure(state=ctk.DISABLED)

            self.invoice_info_widgets[DBInvoicesColumns.IVA.value].configure(state=ctk.NORMAL)
            self.invoice_info_widgets[DBInvoicesColumns.IVA.value].delete(0, ctk.END)
            self.invoice_info_widgets[DBInvoicesColumns.IVA.value].insert(0,
                                                                          importi_derivati[DBInvoicesColumns.IVA.value])
            self.invoice_info_widgets[DBInvoicesColumns.IVA.value].configure(state=ctk.DISABLED)

            self.invoice_info_widgets[DBInvoicesColumns.TOT_DOCUMENTO.value].configure(state=ctk.NORMAL)
            self.invoice_info_widgets[DBInvoicesColumns.TOT_DOCUMENTO.value].delete(0, ctk.END)
            self.invoice_info_widgets[DBInvoicesColumns.TOT_DOCUMENTO.value].insert(0, importi_derivati[
                DBInvoicesColumns.TOT_DOCUMENTO.value])
            self.invoice_info_widgets[DBInvoicesColumns.TOT_DOCUMENTO.value].configure(state=ctk.DISABLED)

            self.invoice_info_widgets[DBInvoicesColumns.RITENUTA.value].configure(state=ctk.NORMAL)
            self.invoice_info_widgets[DBInvoicesColumns.RITENUTA.value].delete(0, ctk.END)
            self.invoice_info_widgets[DBInvoicesColumns.RITENUTA.value].insert(0, importi_derivati[
                DBInvoicesColumns.RITENUTA.value])
            self.invoice_info_widgets[DBInvoicesColumns.RITENUTA.value].configure(state=ctk.DISABLED)

            self.invoice_info_widgets[DBInvoicesColumns.NETTO_A_PAGARE.value].configure(state=ctk.NORMAL)
            self.invoice_info_widgets[DBInvoicesColumns.NETTO_A_PAGARE.value].delete(0, ctk.END)
            self.invoice_info_widgets[DBInvoicesColumns.NETTO_A_PAGARE.value].insert(0, importi_derivati[
                DBInvoicesColumns.NETTO_A_PAGARE.value])
            self.invoice_info_widgets[DBInvoicesColumns.NETTO_A_PAGARE.value].configure(state=ctk.DISABLED)

    def toggle_production_list(self, selected_value):
        cliente = self.clients_query_service.retrieve_client_map_by_name(selected_value)
        if cliente:
            cliente_id = cliente[DBClientsColumns.ID.value]
            productions_of_client = self.productions_query_service.retrieve_productions_map_list_by_client_id(cliente_id)
            self.invoice_info_widgets[self.nome_produzione_associata_string].configure(values=[p[DBProductionsColumns.NAME.value] for p in productions_of_client])
            self.invoice_info_widgets[self.nome_produzione_associata_string].set(productions_of_client[0][DBProductionsColumns.NAME.value])

    def setup_expiration_dates(self, selected_value):
        if str(selected_value) == Rateizzazione.UNA.value:
            self.invoice_info_labels[DBInvoicesColumns.DATA_SCADENZA_2.value].grid_forget()
            self.invoice_info_widgets[DBInvoicesColumns.DATA_SCADENZA_2.value].grid_forget()
            self.invoice_info_labels[DBInvoicesColumns.DATA_SCADENZA_3.value].grid_forget()
            self.invoice_info_widgets[DBInvoicesColumns.DATA_SCADENZA_3.value].grid_forget()
        elif str(selected_value) == Rateizzazione.TRE.value:
            self.invoice_info_labels[DBInvoicesColumns.DATA_SCADENZA_2.value].grid(row=4, column=0, sticky="w", padx=(15, 5), pady=(5, 35))
            self.invoice_info_widgets[DBInvoicesColumns.DATA_SCADENZA_2.value].grid(row=4, column=1, sticky="ew", padx=(5, 15), pady=(5, 35))
            self.invoice_info_labels[DBInvoicesColumns.DATA_SCADENZA_3.value].grid(row=5, column=0, sticky="w", padx=(15, 5), pady=(5, 35))
            self.invoice_info_widgets[DBInvoicesColumns.DATA_SCADENZA_3.value].grid(row=5, column=1, sticky="ew", padx=(5, 15), pady=(5, 35))

    def save_invoice_mod(self):
        self.toggle_importi_derivati_fattura(None, True)

        nome_conto = self.invoice_info_widgets[self.nome_conto_string].get()
        conto = self.accounts_query_service.retrieve_account_map_by_name(nome_conto)
        id_conto = conto[DBAccountsColumns.ID.value] if conto else None

        nome_cliente = self.invoice_info_widgets[self.nome_cliente_string].get_value()
        cliente = self.clients_query_service.retrieve_client_map_by_name(nome_cliente)
        id_cliente = cliente[DBClientsColumns.ID.value]

        nome_produzione = self.invoice_info_widgets[self.nome_produzione_associata_string].get()
        produzione = self.productions_query_service.retrieve_production_map_by_name(nome_produzione)
        id_produzione = produzione[DBProductionsColumns.ID.value]

        invoice_data = {
            DBInvoicesColumns.DATA_CREAZIONE.value: self.invoice_info_widgets[DBInvoicesColumns.DATA_CREAZIONE.value].get_date(),
            DBInvoicesColumns.ID_CLIENTE.value: id_cliente,
            DBInvoicesColumns.SERVIZI.value: self.invoice_info_widgets[
                DBInvoicesColumns.SERVIZI.value].get().strip(),
            DBInvoicesColumns.RIMBORSI.value: self.invoice_info_widgets[
                DBInvoicesColumns.RIMBORSI.value].get().strip(),
            DBInvoicesColumns.RIVALSA_INPS.value: self.invoice_info_widgets[
                DBInvoicesColumns.RIVALSA_INPS.value].get().strip(),
            DBInvoicesColumns.CASSA_INPS.value: self.invoice_info_widgets[
                DBInvoicesColumns.CASSA_INPS.value].get().strip(),
            DBInvoicesColumns.IMPONIBILE.value: self.invoice_info_widgets[
                DBInvoicesColumns.IMPONIBILE.value].get().strip(),
            DBInvoicesColumns.IVA.value: self.invoice_info_widgets[
                DBInvoicesColumns.IVA.value].get().strip(),
            DBInvoicesColumns.TOT_DOCUMENTO.value: self.invoice_info_widgets[
                DBInvoicesColumns.TOT_DOCUMENTO.value].get().strip(),
            DBInvoicesColumns.RITENUTA.value: self.invoice_info_widgets[
                DBInvoicesColumns.RITENUTA.value].get().strip(),
            DBInvoicesColumns.NETTO_A_PAGARE.value: self.invoice_info_widgets[
                DBInvoicesColumns.NETTO_A_PAGARE.value].get().strip(),
            DBInvoicesColumns.METODO_PAGAMENTO.value: self.invoice_info_widgets[
                DBInvoicesColumns.METODO_PAGAMENTO.value].get().strip(),
            DBInvoicesColumns.ID_CONTO.value: id_conto,
            DBInvoicesColumns.NUMERO_RATE.value: self.invoice_info_widgets[
                DBInvoicesColumns.NUMERO_RATE.value].get(),
            DBInvoicesColumns.DATA_SCADENZA_1.value: self.invoice_info_widgets[
                DBInvoicesColumns.DATA_SCADENZA_1.value].get_date(),
            DBInvoicesColumns.DATA_SCADENZA_2.value: self.invoice_info_widgets[
                DBInvoicesColumns.DATA_SCADENZA_2.value].get_date() if float(self.invoice_info_widgets[DBInvoicesColumns.NUMERO_RATE.value].get()) == float(Rateizzazione.TRE.value)
                                                                       else None,
            DBInvoicesColumns.DATA_SCADENZA_3.value: self.invoice_info_widgets[
                DBInvoicesColumns.DATA_SCADENZA_3.value].get_date() if float(self.invoice_info_widgets[DBInvoicesColumns.NUMERO_RATE.value].get()) == float(Rateizzazione.TRE.value)
                                                                       else None,
            DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value: id_produzione,
            DBInvoicesColumns.NOTE.value: self.invoice_info_widgets[
                DBInvoicesColumns.NOTE.value].get().strip()
        }

        # Chiamata al controller per salvare i dati
        success, message = self.invoice_controller.update_invoice(self.current_invoice_id, invoice_data)
        if success:
            print(f"Invoice {self.invoices_query_service.retrieve_invoice_map_by_id(self.current_invoice_id)[DBInvoicesColumns.NUMERO_FATTURA.value]} salvata con successo")
            ViewUtils.show_confirm_popup_2(self.content_frame, "SALVATAGGIO COMPLETATO", message)
            self.switch_modify.deselect()
            self.toggle_edit(self.content_frame)
            payments = self.invoices_query_service.retrieve_invoice_with_payments_map_list(self.current_invoice_id)
            for payment in payments:
                self.update_controller.launch_payment_warning(payment[DBPaymentsColumns.PAYMENT_NAME.value],
                                                                      "Questo pagamento fa riferimento ad una fattura i cui dati sono stati modificati,\n"
                                                                      "controllare la consistenza dei dati di questo pagamento.\n")

        else:
            # Mostra il messaggio d'errore
            print(message)
            ViewUtils.show_error_popup(self.content_frame, "ERRORE", message)

    def storna_invoice(self):
        invoice_data = {
            DBInvoicesColumns.STATUS.value : InvoiceSatus.STORNATA.value
        }

        confirmation = ViewUtils.ask_confirmation_popup(self.content_frame, "Stai per stornare questa fattura.\n "
                                                             "Essa non verrà più conteggiata all'interno del sistema ma potrai comunque visionarla eo modificarla\n"
                                                             "Questa operazione non è irreversibile.\n"
                                                             "desideri continuare ?")

        if confirmation is False:
            return

        success, message = self.invoice_controller.storna_invoice(self.current_invoice_id, invoice_data)
        if success:
            invoice = self.invoices_query_service.retrieve_invoice_map_by_id(self.current_invoice_id)
            print(f"Invoice {invoice[DBInvoicesColumns.NUMERO_FATTURA.value]} salvata con successo")
            ViewUtils.show_confirm_popup_2(self.content_frame, "FATTURA STORNATA CON SUCCESSO", message)
            self.invoice_info_widgets[DBInvoicesColumns.STATUS.value].configure(text=f"{InvoiceSatus.STORNATA.value}")
            self.switch_modify.deselect()
            self.toggle_edit(self.content_frame)
            payments = self.invoices_query_service.retrieve_invoice_with_payments_map_list(self.current_invoice_id)
            for payment in payments:
                self.update_controller.launch_payment_warning(payment[DBPaymentsColumns.PAYMENT_NAME.value],
                                                                "Questo pagamento fa riferimento ad una fattura stornata,\n"
                                                                "modificare i dati del pagamento per mantenere la consistenza dei dati.\n"
                                                                "Si consiglia di eliminare questo pagamento o collegarlo alla fattura corretta")
        else:
            # Mostra il messaggio d'errore
            print(message)
            ViewUtils.show_error_popup(self.content_frame, "ERRORE", message)

    def _create_payments_history(self):
        """Crea la sezione storico dei pagamenti"""
        section_frame = ctk.CTkFrame(self.wrapper_frame, border_width=2, border_color="#2659ab")
        section_frame.pack(fill="both", side="left", expand=True, pady=0, padx=(0, 30))

        ctk.CTkLabel(section_frame, text="PAGAMENTI ASSOCIATI", font=("Arial", 14, "bold")).pack(anchor="w", pady=(10, 10), padx=10)

        self.payments_global_infos = {
            "TOTALE PAGAMENTI" : {
                "value" : self.invoices_analyzer_service.calcola_totale_pagamenti_fattura(self.current_invoice_id)[0],
                "uom" : "€"
            },
            "TOTALE RATA 1": {
                "value": self.invoices_analyzer_service.calcola_totale_pagamenti_fattura(self.current_invoice_id)[1],
                "uom": "€"
            },
            "TOTALE RATA 2": {
                "value": self.invoices_analyzer_service.calcola_totale_pagamenti_fattura(self.current_invoice_id)[2],
                "uom": "€"
            },
            "TOTALE RATA 3": {
                "value": self.invoices_analyzer_service.calcola_totale_pagamenti_fattura(self.current_invoice_id)[3],
                "uom": "€"
            }
        }

        invoice = self.invoices_query_service.retrieve_invoice_map_by_id(self.current_invoice_id)
        if int(invoice[DBInvoicesColumns.NUMERO_RATE.value]) == int(Rateizzazione.UNA.value):
            self.payments_global_infos.pop("TOTALE RATA 1")
            self.payments_global_infos.pop("TOTALE RATA 2")
            self.payments_global_infos.pop("TOTALE RATA 3")


        self.global_infos_payments_widgets = ViewUtils.construct_global_infos_cards(section_frame, self.payments_global_infos)
        self.toggle_warning_global_info_payments()


        # tabella payments
        payments_frame = ctk.CTkScrollableFrame(section_frame, height=300)
        payments_frame.pack(fill="both", expand=True, padx=(10, 20), pady=(10, 20))

        # popolo i payments
        payments = self.invoices_query_service.retrieve_invoice_with_payments_map_list(self.current_invoice_id)
        for payment in payments:
            if payment[DBPaymentsColumns.PAYMENT_NAME.value] is not None:
                nome_pagamento = payment[DBPaymentsColumns.PAYMENT_NAME.value]
                id_pagamento = payment[DBPaymentsColumns.ID.value]
                pagamento_button = ctk.CTkButton(payments_frame,
                                                 text=f"{nome_pagamento}",
                                                 command=lambda id=id_pagamento: self.show_payment_detail(id))
                pagamento_button.pack(padx=10, pady=10, fill="x", expand=True)

    def show_payment_detail(self, payment_id):
        self.event_bus.publish(ViewUtils.EventBusKeys.SHOW_PAYMENT_DETAIL, payment_id)

    def _create_production_expenses_history(self):
        """Crea la sezione storico delle spese di produzione"""
        section_frame = ctk.CTkFrame(self.wrapper_frame, border_width=2, border_color="#2659ab")
        section_frame.pack(fill="both", side="left", expand=True, pady=0, padx=(0, 30))

        ctk.CTkLabel(section_frame, text="SPESE DI PRODUZIONE ASSOCIATE", font=("Arial", 14, "bold")).pack(anchor="w", pady=(10, 10), padx=10)

        global_infos = {
            "TOTALE SPESE" : {
                "value" : self.invoices_analyzer_service.calcola_totale_spese_produzione_fattura(self.current_invoice_id),
                "uom" : "€"
            }
        }

        self.global_infos_payments_widgets = ViewUtils.construct_global_infos_cards(section_frame, global_infos)

        # tabella payments
        expenses_frame = ctk.CTkScrollableFrame(section_frame, height=300)
        expenses_frame.pack(fill="both", expand=True, padx=(10, 20), pady=(10, 20))

        # popolo i payments
        expenses = self.invoices_query_service.retrieve_invoice_with_expenses_map_list(self.current_invoice_id)
        for expense in expenses:
            if expense[DBExpensesColumns.NAME.value] is not None:
                nome_spesa = expense[DBExpensesColumns.NAME.value]
                id_spesa = expense[DBExpensesColumns.ID.value]
                spesa_button = ctk.CTkButton(expenses_frame,
                                             text=f"{nome_spesa}",
                                             command=lambda id=id_spesa: self.show_production_expense_detail(id))
                spesa_button.pack(padx=10, pady=10, fill="x", expand=True)

    def show_production_expense_detail(self, expense_id):
        self.event_bus.publish(ViewUtils.EventBusKeys.SHOW_EXPENSE_DETAIL, expense_id)

    #da salvare come callback alla modifica/aggiunta di un pagamento
    def toggle_warning_global_info_payments(self):
        if not hasattr(self, "global_infos_payments_widgets"):
            return  # L'oggetto non esiste ancora, esco silenziosamente

        # Ricalcola i nuovi valori delle rate
        totali = self.invoices_analyzer_service.calcola_totale_pagamenti_fattura(self.current_invoice_id)
        invoice = self.invoices_query_service.retrieve_invoice_map_by_id(self.current_invoice_id)
        totale_fattura = float(invoice[DBInvoicesColumns.NETTO_A_PAGARE.value])
        tot_rata = totale_fattura if str(invoice[DBInvoicesColumns.NUMERO_RATE.value]) == str(Rateizzazione.UNA.value) else totale_fattura/3

        warning = "Il totale dei pagamenti relativi a questa rata eccede il totale della rata segnata in fattura.\n"\
                   "Controllare i pagamenti legati a questa fattura."

        # Aggiorna ogni card, se presente
        if "TOTALE PAGAMENTI" in self.global_infos_payments_widgets:
            valore = totali[0]
            label = self.global_infos_payments_widgets["TOTALE PAGAMENTI"]["label"]
            card = self.global_infos_payments_widgets["TOTALE PAGAMENTI"]["card"]
            label.configure(text=f"{valore} €")
            if totali[0] > tot_rata + 5:
                card.configure(border_width=2, border_color="#e6c719")
                ViewUtils.add_tooltip(label, warning)


        if "TOTALE RATA 1" in self.global_infos_payments_widgets:
            valore = totali[1]
            label = self.global_infos_payments_widgets["TOTALE RATA 1"]["label"]
            card = self.global_infos_payments_widgets["TOTALE RATA 1"]["card"]
            label.configure(text=f"{valore} €")
            if totali[1] > tot_rata + 5:
                card.configure(border_width=2, border_color="#e6c719")
                ViewUtils.add_tooltip(label, warning)

        if "TOTALE RATA 2" in self.global_infos_payments_widgets:
            valore = totali[2]
            label = self.global_infos_payments_widgets["TOTALE RATA 2"]["label"]
            card = self.global_infos_payments_widgets["TOTALE RATA 2"]["card"]
            label.configure(text=f"{valore} €")
            if totali[2] > tot_rata + 5:
                card.configure(border_width=2, border_color="#e6c719")
                ViewUtils.add_tooltip(label, warning)

        if "TOTALE RATA 3" in self.global_infos_payments_widgets:
            valore = totali[3]
            label = self.global_infos_payments_widgets["TOTALE RATA 3"]["label"]
            card = self.global_infos_payments_widgets["TOTALE RATA 3"]["card"]
            label.configure(text=f"{valore} €")
            if totali[3] > tot_rata + 5:
                card.configure(border_width=2, border_color="#e6c719")
                ViewUtils.add_tooltip(label, warning)





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

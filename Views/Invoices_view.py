import customtkinter as ctk
import tkinter as tk
from tkcalendar import Calendar, DateEntry
from Views.View_utils import ViewUtils
from Controllers import ValidationUtils, InvoiceController, UserController, ControllerUtils
from Model import DBInvoicesColumns, DBUsersColumns, DBClientsColumns, DBProductionsColumns, DBPaymentsColumns, DBAccountsColumns, DBExpensesColumns
from datetime import datetime
import re
from enum import Enum

class InvoicesView(ctk.CTk):

    class InvoicesStatusColors(Enum):
        CRITICAL = "#f52f2f"
        WARNING = "#e39e27"
        NORMAL = ctk.ThemeManager.theme["CTkLabel"]["text_color"]
        GOOD = "#2ca31c"
        STORNATA = "#2444d4"
        NOT_EXISTING = "#424242"

    def __init__(self, db_model, invoice_controller, user_controller, client_controller, production_controller, payment_controller, account_controller, update_controller, tabview, fiscal_settings, historical_financial_data_settings, event_bus):
        super().__init__()

        self.db_model = db_model
        self.invoice_controller = invoice_controller
        self.user_controller = user_controller
        self.client_controller = client_controller
        self.production_controller = production_controller
        self.payment_controller = payment_controller
        self.account_controller = account_controller
        self.update_controller = update_controller
        self.tabview = tabview
        self.tab = tabview.tab("Fatture")
        self.fiscal_settings = fiscal_settings
        self.historical_financial_data_settings = historical_financial_data_settings
        self.event_bus = event_bus

        self.event_bus.subscribe(ViewUtils.EventBusKeys.SHOW_INVOICE_DETAIL, self.handle_show_invoice_detail)

        self.invoices_card_list = {}
        self.invoice_card_labels_status = {}
        self.invoice_card_rate_frames = {}
        self.amount_aggregate_labels = {}

        self.global_infos_lordi = {}
        self.global_infos_netti = {}
        self.lordo_netto_switch_var = tk.BooleanVar(value=False)  # false è Lordo

        self.invoices_list_of_user = self.invoice_controller.retrieve_invoices_map_list_by_user(1, True) #inizializzo la lista delle fatture con le sole fatture dell'utente con ID 1
        self.productions_list_of_client = {}
        if len(self.client_controller.retrieve_clients_map_list()) > 0:
            self.populate_production_list_by_selected_client(self.client_controller.retrieve_clients_map_list()[0][DBClientsColumns.NAME.value])

        #self.payment_controller.register_on_adding_payment_callbacks(self.toggle_specific_invoice_status_color, self.toggle_specific_invoice_rate_color)
        self.invoice_controller.register_on_updating_invoice_controller_callbacks(self.toggle_specific_invoice_status, self.toggle_specific_invoice_status_color, self.toggle_specific_invoice_rate_color_2, self.toggle_aggregate_data)

        # Container principale
        self.main_container = ctk.CTkFrame(self.tab)
        self.detail_container = ctk.CTkFrame(self.tab)

        # Vista dettaglio
        self.invoice_detail_view = InvoiceDetailView(
            parent=self.tab,
            invoice_controller=self.invoice_controller,
            back_callback=self.show_main_view,
            user_controller=user_controller,
            client_controller=self.client_controller,
            account_controller=account_controller,
            production_controller=production_controller,
            update_controller=self.update_controller,
            db_model=db_model,
            fiscal_settings=self.fiscal_settings,
            historical_financial_data_settings = self.historical_financial_data_settings,
            event_bus = self.event_bus
        )

        # Inizializza la vista principale
        self.create_invoices_tab()
        self.show_main_view()

    def create_invoices_tab(self):

        self.switch_frame = ctk.CTkFrame(self.main_container, fg_color="#2b2b2b")
        self.switch_frame.pack(fill="x")
        ctk.CTkLabel(self.switch_frame, text="LORDI   ", font=("Arial", 20)).pack(pady=(10,0), padx=(10, 0), anchor="w", side=ctk.LEFT)
        self.lordo_netto_switch = ctk.CTkSwitch(self.switch_frame,
                                                text="  NETTI", font=("Arial", 20),
                                                command=self.switch_lordo_netto,
                                                width=200, switch_width=60,
                                                height=48, switch_height=20,
                                                variable=self.lordo_netto_switch_var)
        self.lordo_netto_switch.pack(pady=(10,0), anchor="w")

        self.search_bar_frame = ctk.CTkFrame(self.main_container, fg_color="#2b2b2b")
        self.search_bar_frame.pack(pady=(5, 10), fill="x", anchor="n")
        self.search_bar = ctk.CTkEntry(self.search_bar_frame)
        self.search_bar.pack(padx=(5,35), anchor="s", side="right")
        self.search_bar_option_menu_values = {"NOME FATTURA" : "NOME FATTURA", "NOME CLIENTE" : "NOME CLIENTE", "NOME UTENTE" : "NOME UTENTE", "NOME PRODUZIONE" : "NOME PRODUZIONE"}
        self.search_bar_optionMenu = ctk.CTkOptionMenu(self.search_bar_frame, values=list(self.search_bar_option_menu_values.values()))
        self.search_bar_optionMenu.pack(padx=5, anchor="s", side="right")
        self.search_bar_label = ctk.CTkLabel(self.search_bar_frame, text="Filtra per ", font=("Arial", 14))
        self.search_bar_label.pack(padx=5, anchor="s", side="right")

        # Aggiungi evento alla barra di ricerca
        self.search_bar.bind("<KeyRelease>", self.filter_cards)

        # Ottieni il valore di default dei corner radius dai pulsanti
        default_corner_radius = ctk.ThemeManager.theme["CTkButton"]["corner_radius"]
        self.populate_global_infos()
        i = 0

        #costruisco i capi delle informazioni aggregate
        for key, value in self.global_infos_lordi.items():
            card = ctk.CTkFrame(self.search_bar_frame, fg_color="#333333")

            if i == 6:
                global_info_unità_di_misura = "€/h"
            elif i == 0 :
                global_info_unità_di_misura = ""
            else:
                global_info_unità_di_misura = "€"

            title = ctk.CTkLabel(card, text=f"{key}", font=("Arial", 12), bg_color="#1F6AA5", corner_radius=default_corner_radius)
            amount = ctk.CTkLabel(card, text=f"{value} {global_info_unità_di_misura}", font=("Arial", 16))

            card.pack(side="left", anchor="w", padx=10, pady=(10,5))
            title.pack(anchor="n", padx=10, pady=(10, 5), ipadx=7, ipady=5)
            amount.pack(anchor="s", padx=10, pady=5)

            self.amount_aggregate_labels[f"{key}"] = amount

            i = i + 1

        self.invoices_table_frame = ctk.CTkFrame(self.main_container, fg_color="#2b2b2b")
        self.invoices_table_frame.pack(pady=(20, 0), padx=(10,15), fill="x", anchor="n")

        self.headers = ["NOME", "CLIENTE", "UTENTE", "PRODUZIONE\nASSOCIATA", "DATA EMISSIONE", "STATO",
                   "RATE", ViewUtils.split_string_by_length("NETTO A PAGARE", 6), "TIPOLOGIA"]

        for i, header in enumerate(self.headers):
            # crea il container
            column = ctk.CTkFrame(self.invoices_table_frame, fg_color="#333333")
            column.grid(row=0, column=i, sticky="nsew", padx=(0, 5), pady=5)

            # imposta peso e uniformità: tutte le colonne "col" si dividono equamente
            self.invoices_table_frame.grid_columnconfigure(i, weight=1, uniform="col")

            # la label riempie il suo container
            label = ctk.CTkLabel(column,
                                 text=header,
                                 font=("Arial", 14))
            label.pack(fill="both", expand=True, padx=5, pady=15)

        # Creazione del frame delle cards
        self.invoices_cards_frame = ctk.CTkScrollableFrame(self.main_container)
        self.invoices_cards_frame.pack(padx=0, pady=10, fill="both", expand=True)

        self.add_invoice_frame = ctk.CTkFrame(self.main_container, fg_color="#2b2b2b")
        self.add_invoice_frame.pack(padx=0, pady=(5, 20))

        self.save_button = ctk.CTkButton(self.add_invoice_frame, text="Aggiungi una fattura",
                                         command=self.open_add_invoice_window)
        self.save_button.pack(side="left", padx=20)

        self.suggest_user = ctk.CTkButton(self.add_invoice_frame, text="Suggerisci partita iva",
                                         command=self.open_suggest_user_window)
        self.suggest_user.pack(padx=20)

        #aggiungo una tab per ogni fattura presente nel database
        invoice_map_list = self.invoice_controller.retrieve_invoices_map_list(True)
        # Ordina la lista in ordine decrescente (dal più recente al più vecchio)
        invoice_map_list.sort(
            key=lambda x: datetime.strptime(
                x[DBInvoicesColumns.UPDATED_AT.value],
                "%Y-%m-%d %H:%M:%S"
            ) if " " in x[DBInvoicesColumns.UPDATED_AT.value] else datetime.strptime(
                x[DBInvoicesColumns.UPDATED_AT.value],
                "%Y-%m-%d"
            ),
            reverse=True
        )
        for invoice in invoice_map_list:
            invoice_id = invoice[DBInvoicesColumns.ID.value]
            invoice_name = invoice[DBInvoicesColumns.NUMERO_FATTURA.value]
            invoice_client_ID = invoice[DBInvoicesColumns.ID_CLIENTE.value]
            invoice_client_name = self.client_controller.retrieve_client_map_by_id(invoice_client_ID)[DBClientsColumns.NAME.value]
            invoice_user_id = invoice[DBInvoicesColumns.ID_UTENTE.value]
            invoice_user_name = self.user_controller.retrieve_user_map_by_id(invoice_user_id)[DBUsersColumns.FIRST_NAME.value] + " " + self.user_controller.retrieve_user_map_by_id(invoice_user_id)[DBUsersColumns.LAST_NAME.value]
            invoice_creation_date = invoice[DBInvoicesColumns.DATA_CREAZIONE.value]
            invoice_state = invoice[DBInvoicesColumns.STATUS.value]
            invoice_rate = invoice[DBInvoicesColumns.NUMERO_RATE.value]
            invoice_tot_documento = invoice[DBInvoicesColumns.NETTO_A_PAGARE.value]
            invoice_tipologia = invoice[DBInvoicesColumns.TIPO.value]
            invoice_production_id = invoice[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value]
            production = self.production_controller.retrieve_production_map_by_id(invoice_production_id)
            invoice_production_name = production[DBProductionsColumns.NAME.value] if production else "Produzione non trovata"

            self.add_invoice_card(invoice_id, invoice_name, invoice_client_name, invoice_user_name, invoice_production_name, invoice_creation_date, invoice_state, invoice_rate, invoice_tot_documento, invoice_tipologia)
            self.toggle_specific_invoice_rate_color_2(invoice_id)
            self.toggle_specific_invoice_status_color(invoice_id)

    def show_main_view(self):
        """Torna alla vista principale"""
        self.invoice_detail_view.pack_forget()
        self.main_container.pack(fill='both', expand=True)

    def open_user_detail_tab(self, invoice_id):
        """Mostra la vista dettaglio utente"""
        self.main_container.pack_forget()
        self.invoice_detail_view.pack(fill='both', expand=True)
        self.invoice_detail_view.create_detail_tab(invoice_id)  # Ricrea i contenuti ogni volta

    def handle_show_invoice_detail(self, invoice_id):
        self.tabview.set("Fatture")  # Cambia tab
        self.open_user_detail_tab(invoice_id)  # Mostra il dettaglio

    def populate_global_infos(self):
        self.global_infos_lordi["# FATTURE"] = self.invoice_controller.current_year_invoices_aggregated_data[
            InvoiceController.InvoiceAggregatedData.NUMERO_FATTURE.value]
        self.global_infos_lordi["FATTURATO"] = self.invoice_controller.current_year_invoices_aggregated_data[
            InvoiceController.InvoiceAggregatedData.FATT_LORDO.value]
        self.global_infos_lordi["CREDITI"] = self.invoice_controller.current_year_invoices_aggregated_data[
            InvoiceController.InvoiceAggregatedData.CREDITI_LORDO.value]
        self.global_infos_lordi["MEDIA FATTURE"] = self.invoice_controller.current_year_invoices_aggregated_data[
            InvoiceController.InvoiceAggregatedData.MEDIA_FATTURA_LORDO.value]
        #self.global_infos_lordi["PAGAMENTO \n ORARIO"] = 0

        self.global_infos_netti["# FATTURE"] = self.invoice_controller.current_year_invoices_aggregated_data[
            InvoiceController.InvoiceAggregatedData.NUMERO_FATTURE.value]
        self.global_infos_netti["FATTURATO"] = self.invoice_controller.current_year_invoices_aggregated_data[
            InvoiceController.InvoiceAggregatedData.FATT_NETTO.value]
        self.global_infos_netti["CREDITI"] = self.invoice_controller.current_year_invoices_aggregated_data[
            InvoiceController.InvoiceAggregatedData.CREDITI_NETTO.value]
        self.global_infos_netti["MEDIA FATTURE"] = self.invoice_controller.current_year_invoices_aggregated_data[
            InvoiceController.InvoiceAggregatedData.MEDIA_FATTURA_NETTO.value]
        #self.global_infos_netti["PAGAMENTO \n ORARIO"] = 0

    def open_add_invoice_window(self):
        """Apre una finestra per aggiungere un nuovo cliente"""

        self.add_invoice_window = ctk.CTkToplevel(self)
        self.add_invoice_window.title("Aggiungi Nuova Fattura")

        # Assicurati che la finestra rimanga sopra
        self.add_invoice_window.lift()  # Porta la finestra sopra quella principale
        self.add_invoice_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

        self.add_invoice_window.geometry("550x700")

        self.invoice_window_scrollableFrame = ctk.CTkScrollableFrame(self.add_invoice_window)
        self.invoice_window_scrollableFrame.pack(fill="both", expand=True)

        self.nome_utente_string = "NOME UTENTE"
        self.nome_cliente_string = "NOME CLIENTE"
        self.nome_produzione_string = "NOME PRODUZIONE"
        self.nome_conto_string = "CONTO"

        self.entry_fields = {
            self.nome_utente_string: ctk.CTkOptionMenu,
            self.nome_cliente_string: ctk.CTkOptionMenu,
            self.nome_produzione_string: ctk.CTkOptionMenu,
            DBInvoicesColumns.NUMERO_FATTURA.value: ctk.CTkEntry,
            DBInvoicesColumns.DATA_CREAZIONE.value: Calendar,
            DBInvoicesColumns.SERVIZI.value: ctk.CTkEntry,
            DBInvoicesColumns.RIMBORSI.value: ctk.CTkEntry,
            DBInvoicesColumns.RIVALSA_INPS.value: ctk.CTkEntry,
            DBInvoicesColumns.METODO_PAGAMENTO.value: ctk.CTkOptionMenu,
            DBInvoicesColumns.NUMERO_RATE.value: ctk.CTkOptionMenu,
            DBInvoicesColumns.TIPO.value: ctk.CTkOptionMenu,
            DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value: ctk.CTkOptionMenu,
            self.nome_conto_string: ctk.CTkOptionMenu,
            DBInvoicesColumns.NOTE.value: ctk.CTkTextbox
        }

        self.error_fields = {
            self.nome_produzione_string : ctk.CTkLabel,
            DBInvoicesColumns.NUMERO_FATTURA.value: ctk.CTkLabel,
            DBInvoicesColumns.RIMBORSI.value: ctk.CTkLabel,
            DBInvoicesColumns.SERVIZI.value: ctk.CTkLabel,
            DBInvoicesColumns.RIVALSA_INPS.value: ctk.CTkLabel
        }

        self.invoice_widgets = {}
        self.error_labels = {}
        self.invoice_labels = {}


        #istanzio label e widgets iniziali e comuni a ordinaria e forfettaria
        for i, (label_text, widget_class) in enumerate(self.entry_fields.items()):
            # Etichetta
            label = ctk.CTkLabel(self.invoice_window_scrollableFrame, text=label_text)
            #disegno i labels
            if i == 0 and label_text != DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value:
                label.pack(pady=5)
            elif i > 0 and label_text != DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value:
                label.pack(pady=(35, 0))

            self.invoice_labels[label_text] = label

            #widget
            if label_text == self.nome_utente_string:
                widget = widget_class(self.invoice_window_scrollableFrame,
                                      values=[f"{item[DBUsersColumns.FIRST_NAME.value]} {item[DBUsersColumns.LAST_NAME.value]}" for item in self.user_controller.retrieve_users_map_list()],
                                      command=lambda selected_value: self.update_entries_on_regime_fiscale(selected_value))
            elif label_text == self.nome_cliente_string:
                widget = widget_class(self.invoice_window_scrollableFrame,
                                      values=[f"{item[DBClientsColumns.NAME.value]}" for item in self.client_controller.retrieve_clients_map_list()],
                                      command=lambda selected_value: self.update_productions_list(selected_value))
            elif label_text == self.nome_produzione_string:
                widget = widget_class(self.invoice_window_scrollableFrame,
                                      values=[f"{item[DBProductionsColumns.NAME.value]}" for item in self.production_controller.retrieve_productions_map_list(True)],
                                      command=lambda selected_value : self.prod_already_invoiced_control(selected_value))
            elif label_text == DBInvoicesColumns.NUMERO_FATTURA.value:
                self.name_frame = ctk.CTkFrame(self.invoice_window_scrollableFrame)
                self.name_frame.pack(pady=0, padx=0, fill="x", expand=True)
                last_part_name_label = ctk.CTkLabel(self.name_frame, text=f"{datetime.today().date().year}")
                last_part_name_label.pack(side=tk.RIGHT, pady=5, padx=(0, 40))
                widget = widget_class(self.name_frame)
            elif label_text == DBInvoicesColumns.DATA_CREAZIONE.value:
                widget = widget_class(self.invoice_window_scrollableFrame, date_pattern=ViewUtils.date_pattern)
            elif label_text == DBInvoicesColumns.METODO_PAGAMENTO.value:
                widget = widget_class(self.invoice_window_scrollableFrame,
                                      values=[item.value for item in InvoiceController.PaymentsMethods])
            elif label_text == DBInvoicesColumns.NUMERO_RATE.value:
                widget = widget_class(self.invoice_window_scrollableFrame,
                                      values=[item.value for item in InvoiceController.Rateizzazione])
            elif label_text == DBInvoicesColumns.TIPO.value:
                widget = widget_class(self.invoice_window_scrollableFrame,
                                      values=[item.value for item in InvoiceController.Tipologia],
                                      command = lambda selected_value: self.toggle_id_fattura_associata(selected_value))
                widget.set(InvoiceController.Tipologia.FATTURA.value)
            elif label_text == DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value:
                widget = widget_class(self.invoice_window_scrollableFrame,
                                      values=[f"{item[DBInvoicesColumns.NUMERO_FATTURA.value]}" for item in
                                              self.invoices_list_of_user],
                                      command = lambda selected_value: self.auto_set_importi_for_nota_di_credito(selected_value))
            elif label_text ==self.nome_conto_string:
                widget = widget_class(self.invoice_window_scrollableFrame,
                                      values=[f"{item[DBAccountsColumns.NAME.value]}" for item in
                                              self.account_controller.retrieve_accounts_map_list()])
            else:
                widget = widget_class(self.invoice_window_scrollableFrame)

            #disegno i widgets che non sono fattura associata
            if label_text != DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value:
                widget.pack(pady=5, padx=10, fill="x", expand=True)

            self.invoice_widgets[label_text] = widget #aggiungo i widgets alla lista celle referenze

            if self.error_fields.get(label_text) is not None:
                error_label = ctk.CTkLabel(self.invoice_window_scrollableFrame, text="")
                error_label.pack(pady=(0,15))
                self.error_labels[label_text] = error_label

        self.auto_compile_invoice_name(self.invoice_widgets[self.nome_utente_string].get())
        self.update_productions_list(self.client_controller.retrieve_clients_map_list()[0][DBClientsColumns.NAME.value])
        self.prod_already_invoiced_control(self.invoice_widgets[self.nome_produzione_string].get())

        self.selected_user = self.invoice_widgets[self.nome_utente_string].get()
        users_regime_fiscale = self.get_regime_fiscale_from_view(self.selected_user)
        if users_regime_fiscale == UserController.RegimeFiscale.ORDINARIO.value:
            self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].configure(state=ctk.DISABLED,
                                                                                 border_color=ViewUtils.disabled_label_color,
                                                                                 text_color=ViewUtils.disabled_label_color)
            self.invoice_labels[DBInvoicesColumns.RIVALSA_INPS.value].configure(
                text_color=ViewUtils.disabled_label_color)

        # Se la lista delle fatture dell'utente è vuota allora disabilita la possibilità di creare una nota di credito
        if len(self.invoices_list_of_user) == 0:
            self.invoice_widgets[DBInvoicesColumns.TIPO.value].configure(state=ctk.DISABLED)
            self.invoice_widgets[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].configure(state=ctk.DISABLED)
            self.invoice_labels[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].configure(text_color=ViewUtils.disabled_label_color)

        # Bottone per salvare
        self.save_button = ctk.CTkButton(
            self.invoice_window_scrollableFrame,
            text="Salva Fattura",
            command=self.save_invoice_data
        )
        self.save_button.pack(pady=(35, 15))

        # Aggiungi validazione agli eventi di perdita del focus
        self.invoice_widgets[DBInvoicesColumns.NUMERO_FATTURA.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.invoice_widgets[DBInvoicesColumns.NUMERO_FATTURA.value],
            lambda val: val.strip() != "",
            self.error_labels[DBInvoicesColumns.NUMERO_FATTURA.value],
            "Il campo non può essere vuoto."
        ))

        self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.invoice_widgets[DBInvoicesColumns.SERVIZI.value],
            lambda val: re.fullmatch(r"^\d+(\.\d{2})?$", val.strip()) is not None,
            self.error_labels[DBInvoicesColumns.SERVIZI.value],
            "Inserimento non valido: inserire un numero monetario con due cifre decimali (es. 123.45)"
        ))

        self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].bind(
            "<FocusOut>",
            lambda event: self.populate_rivalsa_INPS(),
            add="+"
        )

        self.invoice_widgets[DBInvoicesColumns.RIMBORSI.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
                self.invoice_widgets[DBInvoicesColumns.RIMBORSI.value],
                lambda val: re.fullmatch(r"^\d+(\.\d{2})?$", val.strip()) is not None,
                self.error_labels[DBInvoicesColumns.RIMBORSI.value],
                "Inserimento non valido: inserire un numero monetario con due cifre decimali (es. 123.45)"
        ))

        self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].bind(
            "<FocusOut>",
            lambda event: ViewUtils.validate_entry(
                self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value],
                lambda val: re.fullmatch(r"^\d+(\.\d{2})?$", val.strip()) is not None,
                self.error_labels[DBInvoicesColumns.RIVALSA_INPS.value],
                "Inserimento non valido: inserire un numero monetario con due cifre decimali (es. 123.45)"
            )
        )

    def add_invoice_card(self, invoice_id, nome, cliente, utente, produzione, data_creazione, stato, rate, tot_documento, tipologia):
        """
        Aggiunge una singola card con i dati forniti alla scrollable frame,
        disponendo i widget in N colonne di uguale larghezza.
        """
        # Creazione della card
        card = ctk.CTkFrame(self.invoices_cards_frame, fg_color="dimgray")
        card.pack(pady=10, padx=5, fill="x", expand=True)

        # Dati da visualizzare: prima il bottone 'nome', poi le 8 colonne
        data = [nome, cliente, utente,
                produzione,
                ViewUtils.invert_data_string(data_creazione),
                stato, rate, round(tot_documento, 2), tipologia]
        # Il primo elemento (nome) sarà un Button, gli altri Label o un piccolo Frame
        n_cols = len(data)

        # Configuro il grid della card: una sola riga, n_cols colonne
        for col in range(n_cols):
            card.grid_columnconfigure(col, weight=1, uniform="cardcol")
        card.grid_rowconfigure(0, weight=1)

        # 0) Bottone "nome"
        btn = ctk.CTkButton(card,
                            text=nome,
                            command=lambda: self.open_user_detail_tab(invoice_id))
        btn.grid(row=0, column=0, sticky="nsew", padx=(10,5), pady=10)

        # 1) CLIENTE, 2) UTENTE, 3) PRODUZIONE, 4) DATA, 5) STATO, 6) RATE, 7) NETTO, 8) TIPOLOGIA
        # parte da colonna 1
        for idx, val in enumerate(data[1:], start=1):
            if idx != 6:
                # normale label
                text = f"{val}" if idx != 7 else f"{val}€"  # idx 7 = tot_documento -> aggiungo €
                lbl = ctk.CTkLabel(card, text=text, font=("Arial", 14))
                lbl.grid(row=0, column=idx, sticky="nsew", padx=5, pady=10)
                # Salvo il label di stato
                if idx == 5:
                    self.invoice_card_labels_status[invoice_id] = lbl

            else:
                # colonna "rate": crea un frame interno con 3 label che si ridimensionano uguali
                rate_frame = ctk.CTkFrame(card)
                rate_frame.grid(row=0, column=idx, sticky="nsew", padx=(10, 5), pady=10, ipadx=10)
                # configura 3 colonne uniformi dentro rate_frame
                for c in range(3):
                    rate_frame.grid_columnconfigure(c, weight=1, uniform="ratecol")
                rate_frame.grid_rowconfigure(0, weight=1)

                for c, txt in enumerate(["1", "2", "3"]):
                    rlbl = ctk.CTkLabel(rate_frame, text=txt, font=("Arial", 14))
                    rlbl.grid(row=0, column=c, sticky="nsew", padx=2)

                self.invoice_card_rate_frames[invoice_id] = rate_frame

        # Inserisci nella mappa per il filtraggio
        self.invoices_card_list[nome] = card
        self.toggle_specific_invoice_rate_color_2(invoice_id)
        self.toggle_specific_invoice_status_color(invoice_id)

    def filter_cards(self, event):
        """Filtra le card in base al testo della barra di ricerca e al tipo di filtro scelto."""
        search_text = self.search_bar.get().lower()
        search_type = self.search_bar_optionMenu.get()

        # Mappatura: ogni chiave associa una tupla (indice, classe_attesa) del widget da cui prelevare il testo
        filter_mapping = {
            "NOME FATTURA": (0, ctk.CTkButton),  # Bottone
            "NOME CLIENTE": (1, ctk.CTkLabel),
            "NOME UTENTE": (2, ctk.CTkLabel),
            "NOME PRODUZIONE": (3, ctk.CTkLabel),
        }

        mapping = filter_mapping.get(search_type)

        # Prima rimuovo tutte le card dal container per avere un "canvas" pulito
        for card in self.invoices_card_list.values():
            card.pack_forget()

        # Se il tipo di ricerca non è riconosciuto, riposiziona tutte le card
        if mapping is None:
            for card in self.invoices_card_list.values():
                card.pack(pady=10, padx=10, fill="x", expand=True)
            return

        idx, expected_class = mapping

        # Itera sulle card nell’ordine originale (grazie al dizionario ordinato)
        for key, card in self.invoices_card_list.items():
            children = card.winfo_children()  # Lista dei widget figli
            widget_text = ""
            if len(children) > idx and isinstance(children[idx], expected_class):
                widget_text = children[idx].cget("text")
            # Se il testo (in lowercase) contiene il testo di ricerca, riposiziona la card
            if search_text in widget_text.lower():
                card.pack(pady=10, padx=10, fill="x", expand=True)
            # Se non corrisponde, non viene ripacchettata (è già stata "distrutta" dal pack_forget())

    def save_invoice_data(self):
        invoice_data = {}

        #riempi il dizionario con i dati dei widgets primari
        for label_text, widget in self.invoice_widgets.items():
            if isinstance(widget, ctk.CTkEntry) or isinstance(widget, ctk.CTkOptionMenu):
                invoice_data[label_text] = widget.get().strip() if isinstance(widget.get(), str) else widget.get()
            elif isinstance(widget, Calendar):
                invoice_data[label_text] = widget.get_date()
            elif isinstance(widget, ctk.CTkTextbox):
                invoice_data[label_text] = widget.get("1.0", "end-1c").strip()  # Recupera il testo dal Textbox

        invoice_data[DBInvoicesColumns.NUMERO_FATTURA.value] = invoice_data[DBInvoicesColumns.NUMERO_FATTURA.value] + " - " + str(datetime.today().date().year)

        if invoice_data[DBInvoicesColumns.TIPO.value] == InvoiceController.Tipologia.FATTURA.value: #se non è una nota di credito non serve prendere la fattura associata
            invoice_data.pop(DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value)

        #chiamata al controller per salvare i dati
        success, message = self.invoice_controller.save_invoice(invoice_data)
        if success:
            #prendo l'ID della fattura appena creata
            invoice_map = self.invoice_controller.retrieve_last_invoice_insert_map()
            print(f"Fattura {invoice_data[DBInvoicesColumns.NUMERO_FATTURA.value]} salvato con successo")

            self.add_invoice_card(
                invoice_map[DBInvoicesColumns.ID.value],
                invoice_data[DBInvoicesColumns.NUMERO_FATTURA.value],
                invoice_data[self.nome_cliente_string],
                invoice_data[self.nome_utente_string],
                invoice_data[self.nome_produzione_string],
                invoice_data[DBInvoicesColumns.DATA_CREAZIONE.value],
                invoice_map[DBInvoicesColumns.STATUS.value],
                invoice_data[DBInvoicesColumns.NUMERO_RATE.value],
                invoice_map[DBInvoicesColumns.NETTO_A_PAGARE.value],
                invoice_data[DBInvoicesColumns.TIPO.value]
            )

            #self.invoices_list[invoice_map[DBInvoicesColumns.ID.value]] = invoice_map
            self.invoice_controller.print_invoices()
            self.clear_class_variable()
            self.add_invoice_window.destroy()
        else:
            print(message)
            ViewUtils.show_error_popup(self.add_invoice_window, "ERRORE", message)

    def update_entries_on_regime_fiscale(self, selected_value=None):
        if selected_value != self.selected_user: #se l'utente è cambiato rispetto a prima eseguo, altrimenti non faccio nulla
            #setto il nuovo utente selezionato
            self.selected_user = self.invoice_widgets[self.nome_utente_string].get()
            #prima updato la lista delle fatture relative all'utente selezionato
            self.populate_invoice_list_by_selected_user(selected_value)

            regime_fiscale = self.get_regime_fiscale_from_view(selected_value) #valorizzato con il regime fiscale del nuovo utente a seguito del focus out

            if regime_fiscale ==  UserController.RegimeFiscale.ORDINARIO.value:
                self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].delete(0, tk.END)
                self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].insert(0, "0")
                self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].configure(state=ctk.DISABLED, border_color=ViewUtils.disabled_label_color, text_color=ViewUtils.disabled_label_color)
                self.invoice_labels[DBInvoicesColumns.RIVALSA_INPS.value].configure(text_color=ViewUtils.disabled_label_color)

            elif regime_fiscale ==  UserController.RegimeFiscale.FORFETTARIO.value:
                self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].delete(0, tk.END)
                self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].configure(state=ctk.NORMAL)
                self.invoice_labels[DBInvoicesColumns.RIVALSA_INPS.value].configure(text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"])
                self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].configure(text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"])
                self.populate_rivalsa_INPS()

            if len(self.invoices_list_of_user) == 0:
                self.invoice_widgets[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].pack_forget()
                self.invoice_labels[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].pack_forget()
                self.invoice_widgets[DBInvoicesColumns.TIPO.value].configure(state=ctk.DISABLED)
                self.invoice_widgets[DBInvoicesColumns.TIPO.value].set(InvoiceController.Tipologia.FATTURA.value)
            else:
                self.invoice_widgets[DBInvoicesColumns.TIPO.value].configure(state=ctk.ACTIVE)
                self.invoice_widgets[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].configure(state=ctk.ACTIVE)
                self.invoice_labels[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].configure(
                    text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"])
                self.invoice_widgets[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].set(
                    self.invoices_list_of_user[0][DBInvoicesColumns.NUMERO_FATTURA.value])

            self.invoice_widgets[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].configure(require_redraw=ctk.TRUE, values=[f"{item[DBInvoicesColumns.NUMERO_FATTURA.value]}" for item in
                                              self.invoices_list_of_user])

            #cambio il suggerimento del nome della fattura
            self.auto_compile_invoice_name(selected_value)
        else:
            return

    def update_productions_list(self, selected_value=None):
        self.populate_production_list_by_selected_client(selected_value)
        self.invoice_widgets[self.nome_produzione_string].configure(values=[f"{item[DBProductionsColumns.NAME.value]}" for item in self.productions_list_of_client])
        if len(self.productions_list_of_client) > 0:
            self.invoice_widgets[self.nome_produzione_string].set(self.productions_list_of_client[0][DBProductionsColumns.NAME.value])
            self.prod_already_invoiced_control(self.invoice_widgets[self.nome_produzione_string].get())
        else:
            #se il cliente non ha nessuna produzione associata
            self.invoice_widgets[self.nome_produzione_string].set(" - ")
            self.error_labels[self.nome_produzione_string].configure(text="IL CLIENTE SELEZIONATO NON HA ANCORA NESSUNA PRODUZIONE ASSOOCIATA", text_color="#d62929")

    def populate_invoice_list_by_selected_user(self, user_full_name):
        # Svuota la lista prima di ricaricarla
        self.invoices_list_of_user.clear()

        # Dividi la stringa in una lista usando lo spazio come separatore
        user_name = user_full_name.split(" ")

        # Verifica di avere almeno due elementi (nome e cognome)
        if len(user_name) >= 2:
            user_first_name = user_name[0]
            user_last_name = user_name[1]
        else:
            # Se il formato non è corretto, potresti loggare un errore o uscire dalla funzione
            print("Formato nome utente non valido:", user_full_name)
            return

        # Ottieni l'ID utente usando il metodo della user_controller (assicurati che funzioni correttamente)
        user_id = self.user_controller.retrieve_user_by_fullname(user_first_name, user_last_name)[0]

        # Rileva dal database la lista delle fatture relative a questo utente.
        self.invoices_list_of_user = self.invoice_controller.retrieve_invoices_map_list_by_user(user_id, True)

    def populate_production_list_by_selected_client(self, client_name):
        #pulisco la lista prima di riempirla
        self.productions_list_of_client.clear()

        #ottengo l'ID del cliente in funzione del nome
        client = self.client_controller.retrieve_client_map_by_name(client_name)
        client_id = client[DBClientsColumns.ID.value]
        #retrievo la lista delle produzioni associate allo specifico cliente
        self.productions_list_of_client = self.production_controller.retrieve_productions_map_list_by_client_id(client_id)

    def get_regime_fiscale_from_view(self, user_full_name):
        user_name = user_full_name.split(" ")
        if len(user_name) >= 2:
            regime_fiscale = self.user_controller.get_regime_fiscale_by_full_name(user_name[0], user_name[1])

        return regime_fiscale

    def populate_rivalsa_INPS(self):
        importo_servizi = self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].get()
        aliquota_rivalsa_inps = float(self.fiscal_settings.partita_iva_forfettaria.aliquota_rivalsa_inps)
        if importo_servizi != "" and importo_servizi.isdigit():
            rivalsa = float(importo_servizi)*aliquota_rivalsa_inps
            formatted_rivalsa = format(rivalsa, ".2f")
            self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].delete(0, tk.END)
            self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].insert(0, formatted_rivalsa)

    def toggle_id_fattura_associata(self, selected_value=None):
        if selected_value == InvoiceController.Tipologia.FATTURA.value:
            self.invoice_widgets[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].pack_forget()
            self.invoice_labels[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].pack_forget()

            self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].delete(0, tk.END)
            self.invoice_widgets[DBInvoicesColumns.RIMBORSI.value].delete(0, tk.END)
            self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].delete(0, tk.END)

        elif selected_value == InvoiceController.Tipologia.NOTA_DI_CREDITO.value:
            self.invoice_widgets[DBInvoicesColumns.NOTE.value].pack_forget()
            self.invoice_labels[DBInvoicesColumns.NOTE.value].pack_forget()
            self.save_button.pack_forget()

            self.invoice_labels[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].pack(pady=(35, 15))
            self.invoice_widgets[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].pack(pady=5, padx=10, fill="x", expand=True)
            self.invoice_labels[DBInvoicesColumns.NOTE.value].pack(pady=(35, 0))
            self.invoice_widgets[DBInvoicesColumns.NOTE.value].pack(pady=5, padx=10, fill="x", expand=True)
            self.save_button.pack(pady=(35, 15))

            self.auto_set_importi_for_nota_di_credito(self.invoice_widgets[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value].get())

    def auto_set_importi_for_nota_di_credito(self, selected_value=None):
        invoice = self.invoice_controller.retrieve_invoice_map_by_name(selected_value)
        user_name = self.invoice_widgets[self.nome_utente_string].get()
        user_full_name = user_name.split(" ")
        user_first = user_full_name[0]
        user_last = user_full_name[1]
        user = self.user_controller.retrieve_user_by_fullname(user_first, user_last)
        user_id = user[0]

        nome_fattura = invoice[DBInvoicesColumns.NUMERO_FATTURA.value] + " - NDC"
        servizi = invoice[DBInvoicesColumns.SERVIZI.value]
        id_cliente = invoice[DBInvoicesColumns.ID_CLIENTE.value]
        nome_cliente = self.client_controller.retrieve_client_map_by_id(id_cliente)[DBClientsColumns.NAME.value]
        id_produzione = invoice[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value]
        nome_produzione = self.production_controller.retrieve_production_map_by_id(id_produzione)[DBProductionsColumns.NAME.value]
        rimborsi = invoice[DBInvoicesColumns.RIMBORSI.value]
        rivalsa = invoice[DBInvoicesColumns.RIVALSA_INPS.value]
        metodo_pagamento = invoice[DBInvoicesColumns.METODO_PAGAMENTO.value]
        numero_rate = invoice[DBInvoicesColumns.NUMERO_RATE.value]
        self.invoice_widgets[DBInvoicesColumns.NUMERO_FATTURA.value].delete(0, tk.END)
        self.invoice_widgets[DBInvoicesColumns.NUMERO_FATTURA.value].insert(0, nome_fattura)
        self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].delete(0, tk.END)
        self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].insert(0, servizi)
        self.invoice_widgets[DBInvoicesColumns.RIMBORSI.value].delete(0, tk.END)
        self.invoice_widgets[DBInvoicesColumns.RIMBORSI.value].insert(0, rimborsi)
        self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].delete(0, tk.END)
        self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].insert(0, rivalsa) if rivalsa else 0
        self.invoice_widgets[self.nome_cliente_string].set(nome_cliente)
        self.invoice_widgets[self.nome_produzione_string].set(nome_produzione)
        self.invoice_widgets[DBInvoicesColumns.METODO_PAGAMENTO.value].set(metodo_pagamento)
        self.invoice_widgets[DBInvoicesColumns.NUMERO_RATE.value].set(numero_rate)

        """else:
            self.select_correct_invoice_window = ctk.CTkToplevel(self)
            self.select_correct_invoice_window.title("Seleziona la fattura corretta")

            # Assicurati che la finestra rimanga sopra
            self.select_correct_invoice_window.lift()  # Porta la finestra sopra quella principale
            self.select_correct_invoice_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

            self.select_correct_invoice_window.geometry("800x900")

            title = ctk.CTkLabel(self.select_correct_invoice_window, text="ATTENZIONE\nTROVATE MOLTEPLICI FATTURE CON LO STESSO NOME\nSelezionare la fattura corretta")
            title.pack(pady=25)
            global_frame = ctk.CTkScrollableFrame(self.select_correct_invoice_window)
            global_frame.pack(pady=5)

            for invoice in invoice:
                invoice_frame = ctk.CTkFrame(global_frame)
                invoice_frame.pack(side=ctk.LEFT)
                invoice_content = "\n".join(
                    f"{column.value}: {invoice.get(column.value, 'N/A')}"
                    for column in DBInvoicesColumns
                )
                ctk.CTkLabel(invoice_frame, text = invoice_content).pack(pady=5, padx=5)
                ctk.CTkButton(invoice_frame, text="Seleziona", command=lambda: self.select_correct_invoice(invoice))"""

    def auto_compile_invoice_name(self, user_name):
        user_full_name = user_name.split(" ")
        user_id = self.user_controller.retrieve_user_by_fullname(user_full_name[0], user_full_name[1])[0]
        user_invoices = self.invoice_controller.retrieve_invoices_map_list_by_user(user_id)

        user_invoice_numbers = []
        for invoice in user_invoices:
            invoice_name = invoice[DBInvoicesColumns.NUMERO_FATTURA.value]
            invoice_number = invoice_name.split("FPR")[1]
            user_invoice_numbers.append(int(invoice_number))

        last_invoice_number = max(user_invoice_numbers) + 1 if len(user_invoice_numbers) != 0 else 0
        last_invoice_number_str = str(last_invoice_number)
        if len(last_invoice_number_str) < 2 and last_invoice_number != 0:
            last_invoice_number_str = "0" + last_invoice_number_str
        else:
            last_invoice_number_str = "01"

        self.invoice_widgets[DBInvoicesColumns.NUMERO_FATTURA.value].delete(0, tk.END)
        self.invoice_widgets[DBInvoicesColumns.NUMERO_FATTURA.value].insert(0, f"{user_full_name[1]} - FPR" + last_invoice_number_str)

    def select_correct_invoice(self, invoice):
        servizi = invoice[DBInvoicesColumns.SERVIZI.value]
        rimborsi = invoice[DBInvoicesColumns.RIMBORSI.value]
        rivalsa = invoice[DBInvoicesColumns.RIVALSA_INPS.value]
        self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].delete(0, tk.END)
        self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].insert(0, servizi)
        self.invoice_widgets[DBInvoicesColumns.RIMBORSI.value].delete(0, tk.END)
        self.invoice_widgets[DBInvoicesColumns.RIMBORSI.value].insert(0, rimborsi)
        self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].delete(0, tk.END)
        self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].insert(0, rivalsa) if rivalsa else 0

        self.select_correct_invoice_window.destroy()

    def toggle_specific_invoice_status(self, invoice_id):
        fattura = self.invoice_controller.retrieve_invoice_map_by_id(invoice_id)
        label = self.invoice_card_labels_status[invoice_id]

        label.configure(text=fattura[DBInvoicesColumns.STATUS.value])

    def toggle_invoices_status_color(self):
        """
        Funzione che assegna un colore al label relativo allo stato delle cards delle fatture

        """
        for (key, label) in self.invoice_card_labels_status.items():
            #cerco la fattura associata
            for invoice in self.invoice_controller.retrieve_invoices_map_list(True):
                if invoice[DBInvoicesColumns.ID.value] == key:
                    fattura = invoice
                    break

            stato = fattura[DBInvoicesColumns.STATUS.value]
            rateizzazione = fattura[DBInvoicesColumns.NUMERO_RATE.value]

            #configure per il label se la fattura è rateizzata
            if rateizzazione == int(InvoiceController.Rateizzazione.TRE.value):
                if stato == InvoiceController.InvoiceRateizzSatus.EMESSA.value:
                    label.configure(text_color=InvoicesView.InvoicesStatusColors.NORMAL.value)
                elif stato == InvoiceController.InvoiceRateizzSatus.PAGATA.value:
                    label.configure(text_color=InvoicesView.InvoicesStatusColors.GOOD.value)
                elif stato == InvoiceController.InvoiceRateizzSatus.DA_EMETTERE.value:
                    label.configure(text_color=InvoicesView.InvoicesStatusColors.NORMAL.value)
                elif stato == InvoiceController.InvoiceRateizzSatus.PARZIALMENTE_SALDATA.value:
                    label.configure(text_color=InvoicesView.InvoicesStatusColors.NORMAL.value)
                elif stato == InvoiceController.InvoiceRateizzSatus.CRITICA.value:
                    label.configure(text_color=InvoicesView.InvoicesStatusColors.WARNING.value)
                elif stato == InvoiceController.InvoiceRateizzSatus.SCADUTA.value:
                    label.configure(text_color=InvoicesView.InvoicesStatusColors.CRITICAL.value)
                elif stato == InvoiceController.InvoiceRateizzSatus.STORNATA.value:
                    label.configure(text_color=InvoicesView.InvoicesStatusColors.NORMAL.value)
                elif stato == InvoiceController.InvoiceSatus.STORNATA.value:
                    label.configure(text_color=InvoicesView.InvoicesStatusColors.STORNATA.value)

            elif rateizzazione == int(InvoiceController.Rateizzazione.UNA.value):
                if stato == InvoiceController.InvoiceSatus.EMESSA.value:
                    label.configure(text_color=InvoicesView.InvoicesStatusColors.NORMAL.value)
                elif stato == InvoiceController.InvoiceRateizzSatus.PAGATA.value:
                    label.configure(text_color=InvoicesView.InvoicesStatusColors.GOOD.value)
                elif stato == InvoiceController.InvoiceSatus.DA_EMETTERE.value:
                    label.configure(text_color=InvoicesView.InvoicesStatusColors.NORMAL.value)
                elif stato == InvoiceController.InvoiceSatus.STORNATA.value:
                    label.configure(text_color=InvoicesView.InvoicesStatusColors.NORMAL.value)
                elif stato == InvoiceController.InvoiceSatus.SCADUTA.value:
                    label.configure(text_color=InvoicesView.InvoicesStatusColors.CRITICAL.value)
                elif stato == InvoiceController.InvoiceSatus.STORNATA.value:
                    label.configure(text_color=InvoicesView.InvoicesStatusColors.STORNATA.value)

    #callback da registrare nel controller
    def toggle_specific_invoice_status_color(self, invoice_id):
        fattura = self.invoice_controller.retrieve_invoice_map_by_id(invoice_id)
        label = self.invoice_card_labels_status[invoice_id]
        stato = fattura[DBInvoicesColumns.STATUS.value]
        rateizzazione = fattura[DBInvoicesColumns.NUMERO_RATE.value]

        # configure per il label se la fattura è rateizzata
        if rateizzazione == int(InvoiceController.Rateizzazione.TRE.value):
            if stato == InvoiceController.InvoiceRateizzSatus.EMESSA.value:
                label.configure(text_color=InvoicesView.InvoicesStatusColors.NORMAL.value)
            elif stato == InvoiceController.InvoiceRateizzSatus.PAGATA.value:
                label.configure(text_color=InvoicesView.InvoicesStatusColors.GOOD.value)
            elif stato == InvoiceController.InvoiceRateizzSatus.DA_EMETTERE.value:
                label.configure(text_color=InvoicesView.InvoicesStatusColors.NORMAL.value)
            elif stato == InvoiceController.InvoiceRateizzSatus.PARZIALMENTE_SALDATA.value:
                label.configure(text_color=InvoicesView.InvoicesStatusColors.NORMAL.value)
            elif stato == InvoiceController.InvoiceRateizzSatus.CRITICA.value:
                label.configure(text_color=InvoicesView.InvoicesStatusColors.WARNING.value)
            elif stato == InvoiceController.InvoiceRateizzSatus.SCADUTA.value:
                label.configure(text_color=InvoicesView.InvoicesStatusColors.CRITICAL.value)
            elif stato == InvoiceController.InvoiceRateizzSatus.STORNATA.value:
                label.configure(text_color=InvoicesView.InvoicesStatusColors.NORMAL.value)
            elif stato == InvoiceController.InvoiceSatus.STORNATA.value:
                label.configure(text_color=InvoicesView.InvoicesStatusColors.STORNATA.value)

        elif rateizzazione == int(InvoiceController.Rateizzazione.UNA.value):
            if stato == InvoiceController.InvoiceSatus.EMESSA.value:
                label.configure(text_color=InvoicesView.InvoicesStatusColors.NORMAL.value)
            elif stato == InvoiceController.InvoiceSatus.SALDATA.value:
                label.configure(text_color=InvoicesView.InvoicesStatusColors.GOOD.value)
            elif stato == InvoiceController.InvoiceSatus.DA_EMETTERE.value:
                label.configure(text_color=InvoicesView.InvoicesStatusColors.NORMAL.value)
            elif stato == InvoiceController.InvoiceSatus.STORNATA.value:
                label.configure(text_color=InvoicesView.InvoicesStatusColors.NORMAL.value)
            elif stato == InvoiceController.InvoiceSatus.SCADUTA.value:
                label.configure(text_color=InvoicesView.InvoicesStatusColors.CRITICAL.value)
            elif stato == InvoiceController.InvoiceSatus.STORNATA.value:
                label.configure(text_color=InvoicesView.InvoicesStatusColors.STORNATA.value)
            elif stato == InvoiceController.InvoiceRateizzSatus.PAGATA.value:
                label.configure(text_color=InvoicesView.InvoicesStatusColors.GOOD.value)

    # callback da registrare nel controller
    def toggle_specific_invoice_rate_color(self, invoice_id):
        """
        Funzione che assegna un colore ai labels relativi allo stato dei pagamenti delle rate

        """
        today = datetime.today().date()

        fattura = self.invoice_controller.retrieve_invoice_map_by_id(invoice_id)

        # cerco i pagamenti associati a questa fattura
        pagamenti = []
        for payment in self.payment_controller.retrieve_payments_map_list(current_year=True):
            if int(payment[DBPaymentsColumns.INVOICE_ID.value]) == int(invoice_id):
                pagamenti.append(payment)

        pagamento_1 = None
        pagamento_2 = None
        pagamento_3 = None

        for p in pagamenti:
            if p and int(p[DBPaymentsColumns.LINKED_RATA.value]) == 1:
                pagamento_1 = p[DBPaymentsColumns.LINKED_RATA.value]
            if p and int(p[DBPaymentsColumns.LINKED_RATA.value]) == 2:
                pagamento_2 = p[DBPaymentsColumns.LINKED_RATA.value]
            if p and int(p[DBPaymentsColumns.LINKED_RATA.value]) == 3:
                pagamento_3 = p[DBPaymentsColumns.LINKED_RATA.value]

        frame = self.invoice_card_rate_frames[invoice_id]

        scadenza_1 = fattura[DBInvoicesColumns.DATA_SCADENZA_1.value]
        scadenza_2 = fattura[DBInvoicesColumns.DATA_SCADENZA_2.value]
        scadenza_3 = fattura[DBInvoicesColumns.DATA_SCADENZA_3.value]

        labels = frame.winfo_children()

        if pagamento_1 != None:
            labels[0].configure(text_color=InvoicesView.InvoicesStatusColors.GOOD.value)
        else:
            if today > ControllerUtils.parse_date(scadenza_1):
                labels[0].configure(text_color=InvoicesView.InvoicesStatusColors.CRITICAL.value)
            elif today == ControllerUtils.parse_date(scadenza_1):
                labels[0].configure(text_color=InvoicesView.InvoicesStatusColors.WARNING.value)
            else:
                labels[0].configure(text_color=InvoicesView.InvoicesStatusColors.NORMAL.value)

        if scadenza_2 != None and scadenza_3 != None:
                if pagamento_2 != None:
                    labels[1].configure(text_color=InvoicesView.InvoicesStatusColors.GOOD.value)
                else:
                    if today > ControllerUtils.parse_date(scadenza_2):
                        labels[1].configure(text_color=InvoicesView.InvoicesStatusColors.CRITICAL.value)
                    elif today == ControllerUtils.parse_date(scadenza_2):
                        labels[1].configure(text_color=InvoicesView.InvoicesStatusColors.WARNING.value)
                    else:
                        labels[1].configure(text_color=InvoicesView.InvoicesStatusColors.NORMAL.value)

                if pagamento_3 != None:
                    labels[2].configure(text_color=InvoicesView.InvoicesStatusColors.GOOD.value)
                else:
                    if today > ControllerUtils.parse_date(scadenza_3):
                        labels[2].configure(text_color=InvoicesView.InvoicesStatusColors.CRITICAL.value)
                    elif today == ControllerUtils.parse_date(scadenza_3):
                        labels[2].configure(text_color=InvoicesView.InvoicesStatusColors.WARNING.value)
                    else:
                        labels[2].configure(text_color=InvoicesView.InvoicesStatusColors.NORMAL.value)

        else:
            labels[1].configure(text_color=InvoicesView.InvoicesStatusColors.NOT_EXISTING.value)
            labels[2].configure(text_color=InvoicesView.InvoicesStatusColors.NOT_EXISTING.value)

    def toggle_specific_invoice_rate_color_2(self, invoice_id):
        """
        Assegna un colore ai label relativi allo stato dei pagamenti delle rate di una fattura.
        Ora, se una rata è parzialmente pagata (la somma dei pagamenti è inferiore al dovuto),
        il colore sarà warning anziché good.
        """

        today = datetime.today().date()

        # Recupera la lista di dizionari con i dati della fattura e dei pagamenti tramite left join
        invoice_with_payments = self.invoice_controller.retrieve_invoice_with_payments_map_list(invoice_id)

        # Se non abbiamo risultati, esci
        if not invoice_with_payments:
            return

        # I dati della fattura sono presenti in ogni riga; usiamo il primo per i dati comuni
        fattura = invoice_with_payments[0]

        # Recupera le date di scadenza per le rate
        scadenza_1 = fattura[DBInvoicesColumns.DATA_SCADENZA_1.value]
        scadenza_2 = fattura[DBInvoicesColumns.DATA_SCADENZA_2.value]
        scadenza_3 = fattura[DBInvoicesColumns.DATA_SCADENZA_3.value]

        # Calcola l'importo dovuto per rata
        try:
            netto = float(fattura[DBInvoicesColumns.NETTO_A_PAGARE.value])
            num_rate = int(fattura[DBInvoicesColumns.NUMERO_RATE.value])
            importo_per_rata = netto / num_rate
        except Exception as e:
            print(f"Errore nel calcolo dell'importo per rata: {e}")
            return

        # Raggruppa e somma i pagamenti per rata
        # Creiamo un dizionario per tenere la somma dei pagamenti per ciascuna rata
        pagamenti_per_rata = {1: 0.0, 2: 0.0, 3: 0.0}
        for payment in invoice_with_payments:
            try:
                linked_rata = int(payment[DBPaymentsColumns.LINKED_RATA.value])
                pagamento_amount = float(payment[DBPaymentsColumns.PAYMENT_AMOUNT.value])
                if linked_rata in pagamenti_per_rata:
                    pagamenti_per_rata[linked_rata] += pagamento_amount
            except Exception as e:
                #print(f"Errore nel processare un pagamento: {e}")
                continue

        # Recupera i label contenuti nel frame delle rate per questa fattura
        frame = self.invoice_card_rate_frames[invoice_id]
        labels = frame.winfo_children()  # Supponiamo: labels[0] per rata 1, labels[1] per rata 2, labels[2] per rata 3

        # Funzione di utilità per impostare il colore in base alla presenza di pagamento o al ritardo
        def configura_label(rate_idx, due_date_str, pagamento_sum):
            # Se esiste almeno un pagamento per la rata
            if pagamento_sum > 0:
                if pagamento_sum >= importo_per_rata or (importo_per_rata - pagamento_sum) < 5:
                    # Pagamento intero
                    labels[rate_idx].configure(text_color=InvoicesView.InvoicesStatusColors.GOOD.value)
                else:
                    # Pagamento parziale
                    labels[rate_idx].configure(text_color=InvoicesView.InvoicesStatusColors.WARNING.value)
            else:
                # Nessun pagamento: confronta con la data di scadenza
                try:
                    due_date = ControllerUtils.parse_date(due_date_str)
                except Exception as e:
                    print(f"Errore nel parsing della data {due_date_str}: {e}")
                    labels[rate_idx].configure(text_color=InvoicesView.InvoicesStatusColors.NOT_EXISTING.value)
                    return

                if today > due_date:
                    labels[rate_idx].configure(text_color=InvoicesView.InvoicesStatusColors.CRITICAL.value)
                elif today == due_date:
                    labels[rate_idx].configure(text_color=InvoicesView.InvoicesStatusColors.WARNING.value)
                else:
                    labels[rate_idx].configure(text_color=InvoicesView.InvoicesStatusColors.NORMAL.value)

        # Imposta il colore per la rata 1
        configura_label(0, scadenza_1, pagamenti_per_rata[1])

        # Per rate 2 e 3, controlla che le date di scadenza siano presenti
        if scadenza_2 is not None and scadenza_3 is not None:
            configura_label(1, scadenza_2, pagamenti_per_rata[2])
            configura_label(2, scadenza_3, pagamenti_per_rata[3])
        else:
            # Se non esistono scadenze per le rate 2 e 3, segnala che non sono presenti
            labels[1].configure(text_color=InvoicesView.InvoicesStatusColors.NOT_EXISTING.value)
            labels[2].configure(text_color=InvoicesView.InvoicesStatusColors.NOT_EXISTING.value)

    def toggle_aggregate_data(self):
        self.populate_global_infos()
        self.switch_lordo_netto()

    def switch_lordo_netto(self):
        if not self.lordo_netto_switch_var.get(): #se è falsa allora mostro i lordi
            for (key,label) in self.amount_aggregate_labels.items():
                self.amount_aggregate_labels[key].configure(text=f"{self.global_infos_lordi[key]}")

        else: # se è vero allora mostro i netti
            for (key,label) in self.amount_aggregate_labels.items():
                self.amount_aggregate_labels[key].configure(text=f"{self.global_infos_netti[key]}")

    def prod_already_invoiced_control(self, selected_value):
        production = self.production_controller.retrieve_production_map_by_name(selected_value)
        fatture_associate = self.invoice_controller.retrieve_invoice_map_list_by_production(production[DBProductionsColumns.ID.value])

        if len(fatture_associate) > 0:
            # Estrai i nomi dalle fatture associate
            nomi_fatture = [fattura[DBInvoicesColumns.NUMERO_FATTURA.value] for fattura in fatture_associate]
            # Unisci i nomi separandoli con una virgola (o un altro separatore)
            nomi_str = ", ".join(nomi_fatture)

            self.error_labels[self.nome_produzione_string].configure(text=f"Questa produzione ha già una o più fatture associate: \n ({nomi_str})", text_color="#e39e27")
        else:
            self.error_labels[self.nome_produzione_string].configure(text="")

    def clear_class_variable(self):  #potrebbe non servire in quanto vengono inizializzate all'apertura della funzione
        self.invoice_widgets.clear()
        self.invoice_labels.clear()

    def open_suggest_user_window(self):
        """Apre una finestra per farsi suggerire l'utente che deve fatturare"""

        self.suggest_invoicer_window = ctk.CTkToplevel(self)
        self.suggest_invoicer_window.title("Suggeritore di fatturatore")

        # Assicurati che la finestra rimanga sopra
        self.suggest_invoicer_window.lift()  # Porta la finestra sopra quella principale
        self.suggest_invoicer_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

        #self.suggest_invoicer_window.geometry("550x700")


        self.suggest_invoicer_window_Frame = ctk.CTkFrame(self.suggest_invoicer_window)
        self.suggest_invoicer_window_Frame.pack(fill="x", expand=True)

        info_label = ctk.CTkLabel(self.suggest_invoicer_window_Frame, text="    ℹ️", font=("Arial", 16), bg_color="#4287f5")
        info_label.pack(padx=10, pady=10, anchor="w")
        ViewUtils.add_tooltip(info_label, "Questa funzionalità prevede che esista una singola partita iva ordinaria tra tante forfettarie.\n"
                                          "L'ordinaria è incaricata di dedurre le spese deducibili.\n"
                                          "Il suggeritore cerca di far fatturare l'ordinaria fino al raggiungimento delle spese deducibili effettuate finora,\n"
                                          "Se le spese deducibili sono già coperte allora viene prediletta la forfettaria con minor fatturato.")

        self.new_invoice_import_label = ctk.CTkLabel(self.suggest_invoicer_window_Frame, text="IMPORTO DA FATTURARE")
        self.new_invoice_import_label.pack(padx=10, pady=(20,5), fill="x")

        self.new_invoice_import_entry = ctk.CTkEntry(self.suggest_invoicer_window_Frame, width=520)
        self.new_invoice_import_entry.pack(padx=10, pady=(0,5), fill="x")

        self.new_invoice_import_error = ctk.CTkLabel(self.suggest_invoicer_window_Frame, text="", text_color="red")
        self.new_invoice_import_error.pack(padx=10, pady=(0,15), fill="x")

        self.show_suggestion_button = ctk.CTkButton(self.suggest_invoicer_window_Frame, text="SUGGERISCI", command=self.get_invoicer_suggestion)
        self.show_suggestion_button.pack(padx=10, pady=(20, 25))

        self.ranking_header_frame = ctk.CTkFrame(self.suggest_invoicer_window, fg_color="#2b2b2b")
        self.ranking_header_frame.pack(fill="x", expand=True, padx=10, pady=(25, 0))
        header1 = ctk.CTkFrame(self.ranking_header_frame, fg_color="#333333")
        header1.grid(row=0, column=0, sticky="nsew", padx=(5, 5), pady=5)
        header2 = ctk.CTkFrame(self.ranking_header_frame, fg_color="#333333")
        header2.grid(row=0, column=1, sticky="nsew", padx=(0, 5), pady=5)
        self.ranking_header_frame.grid_columnconfigure(0, weight=1, uniform="col")
        self.ranking_header_frame.grid_columnconfigure(1, weight=1, uniform="col")
        ctk.CTkLabel(header1, text="UTENTE", font=("Arial", 12)).pack(fill="x", expand=True, padx=5, pady=15)
        ctk.CTkLabel(header2, text="PUNTEGGIO", font=("Arial", 12)).pack(fill="x", expand=True, padx=5, pady=15)


        self.invoicers_ranking_frame = ctk.CTkScrollableFrame(self.suggest_invoicer_window, height=100)
        self.invoicers_ranking_frame.pack(fill="both", expand=True, padx=10, pady=(0, 25))

        self.new_invoice_import_entry.bind("<KeyRelease>", lambda event: ViewUtils.validate_entry(
            self.new_invoice_import_entry,
            lambda val: len(val.strip()) >= 3 and re.fullmatch(r"^\d+(\.\d{2})?$", val.strip()) is not None,
            self.new_invoice_import_error,
            "Inserimento non valido: inserire un numero monetario con due cifre decimali (es. 123.45)"
        ))

    def get_invoicer_suggestion(self):
        try:
            new_import = float(self.new_invoice_import_entry.get())
        except Exception as e:
            ViewUtils.show_error_popup(self.suggest_invoicer_window, "Errore", f"Inserimento non valido")
            return

        try:
            users_rank = self.invoice_controller.select_best_invoicer(new_import)
            #pulisco prima il ranking presente
            for widget in self.invoicers_ranking_frame.winfo_children():
                widget.destroy()

            #ricreo il ranking
            for user_name, score in users_rank.items():
                user_card = ctk.CTkFrame(self.invoicers_ranking_frame)
                user_card.pack(padx=10, pady=5, fill="x", expand=True)

                # Frame interno per il nome
                name_frame = ctk.CTkFrame(user_card, fg_color="transparent")
                name_frame.pack(side="left", fill="x", expand=True, padx=(5), pady=5)
                ctk.CTkLabel(name_frame, text=f"{user_name}", anchor="w").pack(fill="x", expand=True, padx=10, pady=5)

                # Frame interno per il punteggio
                score_frame = ctk.CTkFrame(user_card, fg_color="transparent")
                score_frame.pack(side="right", fill="x", expand=True, padx=(5), pady=5)
                ctk.CTkLabel(score_frame, text=f"{score}", anchor="e").pack(fill="x", expand=True, padx=10, pady=5)

            self.invoicers_ranking_frame.winfo_children()[0].configure(border_width=2, border_color="#3c60b5")

        except ValueError as ve:
            ViewUtils.show_error_popup(self.suggest_invoicer_window, "Errore", f"Predizione non possibile: {str(ve)}")


class InvoiceDetailView(ctk.CTkFrame):
    def __init__(self, parent, back_callback, invoice_controller, user_controller, client_controller, account_controller, production_controller, update_controller, db_model, fiscal_settings, historical_financial_data_settings, event_bus):
        super().__init__(parent)
        self.invoice_controller = invoice_controller
        self.user_controller = user_controller
        self.client_controller = client_controller
        self.account_controller = account_controller
        self.db_model = db_model
        self.back_callback = back_callback
        self.production_controller = production_controller
        self.update_controller = update_controller
        self.fiscal_settings = fiscal_settings
        self.historical_financial_data_settings = historical_financial_data_settings
        self.event_bus = event_bus
        self.current_invoice_id = None

        # Widgets persistenti (vanno creati una volta sola)
        self.head_frame = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.back_button = ctk.CTkButton(
            self.head_frame,
            text="Indietro",
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
        invoice = self.invoice_controller.retrieve_invoice_map_by_id(invoice_id)

        #prendo il nome del conto:
        id_conto = invoice[DBInvoicesColumns.ID_CONTO.value]
        conto = self.account_controller.retrieve_account_map_by_id(id_conto)
        nome_conto = conto[DBAccountsColumns.NAME.value] if conto else "Conto non trovato"
        invoice[self.nome_conto_string] = nome_conto

        #prendo il nome dell' utente:
        id_user = invoice[DBInvoicesColumns.ID_UTENTE.value]
        user = self.user_controller.retrieve_user_map_by_id(id_user)
        nome_user = user[DBUsersColumns.FIRST_NAME.value] + user[DBUsersColumns.LAST_NAME.value] if user else "Utente non trovato"
        invoice[self.nome_user_string] = nome_user

        #prendo il nome del cliente
        id_cliente = invoice[DBInvoicesColumns.ID_CLIENTE.value]
        cliente = self.client_controller.retrieve_client_map_by_id(id_cliente)
        nome_cliente = cliente[DBClientsColumns.NAME.value] if cliente else "Cliente non trovato"
        invoice[self.nome_cliente_string] = nome_cliente

        #prendo il nome della produzione associata
        id_prod = invoice[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value]
        prod = self.production_controller.retrieve_production_map_by_id(id_prod)
        nome_produzione = prod[DBProductionsColumns.NAME.value] if prod else "Produzione non trovata"
        invoice[self.nome_produzione_associata_string] = nome_produzione

        #prendo il nome della fattura associata
        id_fattura_ass = invoice[DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value]
        fatt_ass = self.invoice_controller.retrieve_invoice_map_by_id(id_fattura_ass)
        nome_fatt_ass = fatt_ass[DBInvoicesColumns.NUMERO_FATTURA.value] if fatt_ass else "Nessuna fattura associata"
        invoice[self.nome_fattura_associata_string] = nome_fatt_ass

        # 3. Aggiornamento elementi persistenti
        self.title_label.configure(
            text=f"{invoice[DBInvoicesColumns.NUMERO_FATTURA.value]}")

        # 4. Creazione contenuti dinamici
        self._create_invoice_info_section(invoice)
        self.toggle_edit(self.content_frame)

        self.wrapper_frame = ctk.CTkFrame(self.content_frame, fg_color="#333333")
        self.wrapper_frame.pack(padx=25, pady=(90, 0), fill="both", expand=True)
        self.wrapper_frame2 = ctk.CTkFrame(self.content_frame, fg_color="#333333")
        self.wrapper_frame2.pack(padx=25, pady=(90, 90), fill="both", expand=True)

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
                "type": ctk.CTkOptionMenu,
                "label": "Cliente",
                "section": "Dati Generali",
                "values": [c[DBClientsColumns.NAME.value] for c in self.client_controller.retrieve_clients_map_list()],
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
                "values": [item.value for item in self.invoice_controller.PaymentsMethods]
            },
            self.nome_conto_string: {
                "type": ctk.CTkOptionMenu,
                "label": "Conto",
                "section": "Dati Fiscali",
                "values": [c[DBAccountsColumns.NAME.value] for c in self.account_controller.retrieve_accounts_map_list()]
            },

            # Dati Pagamento
            DBInvoicesColumns.NUMERO_RATE.value: {
                "type": ctk.CTkOptionMenu,
                "label": "Numero Rate",
                "section": "Dati Pagamento",
                "values": [item.value for item in self.invoice_controller.Rateizzazione],
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
                           self.production_controller.retrieve_productions_map_list_by_client_id(invoice_data[DBInvoicesColumns.ID_CLIENTE.value])]
            },
            self.nome_fattura_associata_string: {
                "type": ctk.CTkLabel,
                "label": "Fattura Associata",
                "section": "Collegamenti",
                "values": [i[DBInvoicesColumns.NUMERO_FATTURA.value] for i in
                           self.invoice_controller.retrieve_invoices_map_list()
                           if i[DBInvoicesColumns.TIPO.value] != self.invoice_controller.Tipologia.NOTA_DI_CREDITO]
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
                if config["type"] == ctk.CTkOptionMenu:
                    widget = config["type"](frame, values=config.get("values", []))
                    widget.set(invoice_data.get(field, config.get("values", [""])[0]))

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
        invoice = self.invoice_controller.retrieve_invoice_map_by_id(self.current_invoice_id)
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
        invoice = self.invoice_controller.retrieve_invoice_map_by_id(self.current_invoice_id)
        user = self.user_controller.retrieve_user_map_by_id(invoice[DBInvoicesColumns.ID_UTENTE.value])
        regime_fiscale = user[DBUsersColumns.REGIME_FISCALE.value]
        client = self.client_controller.retrieve_client_map_by_id(invoice[DBInvoicesColumns.ID_CLIENTE.value])
        tipologia_cliente = client[DBClientsColumns.TIPOLOGIA.value]

        #ottengo gli importi derivati
        importi_derivati = self.invoice_controller.calcola_derivati_fattura(regime_fiscale, tipologia_cliente, servizi, rimborsi, rivalsa_inps)

        if not isRivalsaInps:
            #self.invoice_info_widgets[DBInvoicesColumns.RIVALSA_INPS.value].configure(state = tk.NORMAL)
            self.invoice_info_widgets[DBInvoicesColumns.RIVALSA_INPS.value].delete(0, tk.END)
            self.invoice_info_widgets[DBInvoicesColumns.RIVALSA_INPS.value].insert(0, importi_derivati[DBInvoicesColumns.RIVALSA_INPS.value])
            #self.invoice_info_widgets[DBInvoicesColumns.RIVALSA_INPS.value].configure(state=tk.DISABLED)

            self.invoice_info_widgets[DBInvoicesColumns.CASSA_INPS.value].configure(state = tk.NORMAL)
            self.invoice_info_widgets[DBInvoicesColumns.CASSA_INPS.value].delete(0, tk.END)
            self.invoice_info_widgets[DBInvoicesColumns.CASSA_INPS.value].insert(0, importi_derivati[DBInvoicesColumns.CASSA_INPS.value])
            self.invoice_info_widgets[DBInvoicesColumns.CASSA_INPS.value].configure(state=tk.DISABLED)


            self.invoice_info_widgets[DBInvoicesColumns.IMPONIBILE.value].configure(state = tk.NORMAL)
            self.invoice_info_widgets[DBInvoicesColumns.IMPONIBILE.value].delete(0, tk.END)
            self.invoice_info_widgets[DBInvoicesColumns.IMPONIBILE.value].insert(0, importi_derivati[DBInvoicesColumns.IMPONIBILE.value])
            self.invoice_info_widgets[DBInvoicesColumns.IMPONIBILE.value].configure(state=tk.DISABLED)


            self.invoice_info_widgets[DBInvoicesColumns.IVA.value].configure(state = tk.NORMAL)
            self.invoice_info_widgets[DBInvoicesColumns.IVA.value].delete(0, tk.END)
            self.invoice_info_widgets[DBInvoicesColumns.IVA.value].insert(0, importi_derivati[DBInvoicesColumns.IVA.value])
            self.invoice_info_widgets[DBInvoicesColumns.IVA.value].configure(state=tk.DISABLED)


            self.invoice_info_widgets[DBInvoicesColumns.TOT_DOCUMENTO.value].configure(state = tk.NORMAL)
            self.invoice_info_widgets[DBInvoicesColumns.TOT_DOCUMENTO.value].delete(0, tk.END)
            self.invoice_info_widgets[DBInvoicesColumns.TOT_DOCUMENTO.value].insert(0, importi_derivati[DBInvoicesColumns.TOT_DOCUMENTO.value])
            self.invoice_info_widgets[DBInvoicesColumns.TOT_DOCUMENTO.value].configure(state=tk.DISABLED)



            self.invoice_info_widgets[DBInvoicesColumns.RITENUTA.value].configure(state = tk.NORMAL)
            self.invoice_info_widgets[DBInvoicesColumns.RITENUTA.value].delete(0, tk.END)
            self.invoice_info_widgets[DBInvoicesColumns.RITENUTA.value].insert(0, importi_derivati[DBInvoicesColumns.RITENUTA.value])
            self.invoice_info_widgets[DBInvoicesColumns.RITENUTA.value].configure(state=tk.DISABLED)



            self.invoice_info_widgets[DBInvoicesColumns.NETTO_A_PAGARE.value].configure(state = tk.NORMAL)
            self.invoice_info_widgets[DBInvoicesColumns.NETTO_A_PAGARE.value].delete(0, tk.END)
            self.invoice_info_widgets[DBInvoicesColumns.NETTO_A_PAGARE.value].insert(0, importi_derivati[DBInvoicesColumns.NETTO_A_PAGARE.value])
            self.invoice_info_widgets[DBInvoicesColumns.NETTO_A_PAGARE.value].configure(state=tk.DISABLED)
        else:
            self.invoice_info_widgets[DBInvoicesColumns.CASSA_INPS.value].configure(state=tk.NORMAL)
            self.invoice_info_widgets[DBInvoicesColumns.CASSA_INPS.value].delete(0, tk.END)
            self.invoice_info_widgets[DBInvoicesColumns.CASSA_INPS.value].insert(0, importi_derivati[
                DBInvoicesColumns.CASSA_INPS.value])
            self.invoice_info_widgets[DBInvoicesColumns.CASSA_INPS.value].configure(state=tk.DISABLED)

            self.invoice_info_widgets[DBInvoicesColumns.IMPONIBILE.value].configure(state=tk.NORMAL)
            self.invoice_info_widgets[DBInvoicesColumns.IMPONIBILE.value].delete(0, tk.END)
            self.invoice_info_widgets[DBInvoicesColumns.IMPONIBILE.value].insert(0, importi_derivati[
                DBInvoicesColumns.IMPONIBILE.value])
            self.invoice_info_widgets[DBInvoicesColumns.IMPONIBILE.value].configure(state=tk.DISABLED)

            self.invoice_info_widgets[DBInvoicesColumns.IVA.value].configure(state=tk.NORMAL)
            self.invoice_info_widgets[DBInvoicesColumns.IVA.value].delete(0, tk.END)
            self.invoice_info_widgets[DBInvoicesColumns.IVA.value].insert(0,
                                                                          importi_derivati[DBInvoicesColumns.IVA.value])
            self.invoice_info_widgets[DBInvoicesColumns.IVA.value].configure(state=tk.DISABLED)

            self.invoice_info_widgets[DBInvoicesColumns.TOT_DOCUMENTO.value].configure(state=tk.NORMAL)
            self.invoice_info_widgets[DBInvoicesColumns.TOT_DOCUMENTO.value].delete(0, tk.END)
            self.invoice_info_widgets[DBInvoicesColumns.TOT_DOCUMENTO.value].insert(0, importi_derivati[
                DBInvoicesColumns.TOT_DOCUMENTO.value])
            self.invoice_info_widgets[DBInvoicesColumns.TOT_DOCUMENTO.value].configure(state=tk.DISABLED)

            self.invoice_info_widgets[DBInvoicesColumns.RITENUTA.value].configure(state=tk.NORMAL)
            self.invoice_info_widgets[DBInvoicesColumns.RITENUTA.value].delete(0, tk.END)
            self.invoice_info_widgets[DBInvoicesColumns.RITENUTA.value].insert(0, importi_derivati[
                DBInvoicesColumns.RITENUTA.value])
            self.invoice_info_widgets[DBInvoicesColumns.RITENUTA.value].configure(state=tk.DISABLED)

            self.invoice_info_widgets[DBInvoicesColumns.NETTO_A_PAGARE.value].configure(state=tk.NORMAL)
            self.invoice_info_widgets[DBInvoicesColumns.NETTO_A_PAGARE.value].delete(0, tk.END)
            self.invoice_info_widgets[DBInvoicesColumns.NETTO_A_PAGARE.value].insert(0, importi_derivati[
                DBInvoicesColumns.NETTO_A_PAGARE.value])
            self.invoice_info_widgets[DBInvoicesColumns.NETTO_A_PAGARE.value].configure(state=tk.DISABLED)

    def toggle_production_list(self, selected_value):
        cliente = self.client_controller.retrieve_client_map_by_name(selected_value)
        if cliente:
            cliente_id = cliente[DBClientsColumns.ID.value]
            productions_of_client = self.production_controller.retrieve_productions_map_list_by_client_id(cliente_id)
            self.invoice_info_widgets[self.nome_produzione_associata_string].configure(values=[p[DBProductionsColumns.NAME.value] for p in productions_of_client])
            self.invoice_info_widgets[self.nome_produzione_associata_string].set(productions_of_client[0][DBProductionsColumns.NAME.value])

    def setup_expiration_dates(self, selected_value):
        if str(selected_value) == self.invoice_controller.Rateizzazione.UNA.value:
            self.invoice_info_labels[DBInvoicesColumns.DATA_SCADENZA_2.value].grid_forget()
            self.invoice_info_widgets[DBInvoicesColumns.DATA_SCADENZA_2.value].grid_forget()
            self.invoice_info_labels[DBInvoicesColumns.DATA_SCADENZA_3.value].grid_forget()
            self.invoice_info_widgets[DBInvoicesColumns.DATA_SCADENZA_3.value].grid_forget()
        elif str(selected_value) == self.invoice_controller.Rateizzazione.TRE.value:
            self.invoice_info_labels[DBInvoicesColumns.DATA_SCADENZA_2.value].grid(row=4, column=0, sticky="w", padx=(15, 5), pady=(5, 35))
            self.invoice_info_widgets[DBInvoicesColumns.DATA_SCADENZA_2.value].grid(row=4, column=1, sticky="ew", padx=(5, 15), pady=(5, 35))
            self.invoice_info_labels[DBInvoicesColumns.DATA_SCADENZA_3.value].grid(row=5, column=0, sticky="w", padx=(15, 5), pady=(5, 35))
            self.invoice_info_widgets[DBInvoicesColumns.DATA_SCADENZA_3.value].grid(row=5, column=1, sticky="ew", padx=(5, 15), pady=(5, 35))

    def save_invoice_mod(self):
        self.toggle_importi_derivati_fattura(None, True)

        nome_conto = self.invoice_info_widgets[self.nome_conto_string].get()
        conto = self.account_controller.retrieve_account_map_by_name(nome_conto)
        id_conto = conto[DBAccountsColumns.ID.value] if conto else None

        nome_cliente = self.invoice_info_widgets[self.nome_cliente_string].get()
        cliente = self.client_controller.retrieve_client_map_by_name(nome_cliente)
        id_cliente = cliente[DBClientsColumns.ID.value]

        nome_produzione = self.invoice_info_widgets[self.nome_produzione_associata_string].get()
        produzione = self.production_controller.retrieve_production_map_by_name(nome_produzione)
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
                DBInvoicesColumns.DATA_SCADENZA_2.value].get_date() if float(self.invoice_info_widgets[DBInvoicesColumns.NUMERO_RATE.value].get()) == float(self.invoice_controller.Rateizzazione.TRE.value)
                                                                       else None,
            DBInvoicesColumns.DATA_SCADENZA_3.value: self.invoice_info_widgets[
                DBInvoicesColumns.DATA_SCADENZA_3.value].get_date() if float(self.invoice_info_widgets[DBInvoicesColumns.NUMERO_RATE.value].get()) == float(self.invoice_controller.Rateizzazione.TRE.value)
                                                                       else None,
            DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value: id_produzione,
            DBInvoicesColumns.NOTE.value: self.invoice_info_widgets[
                DBInvoicesColumns.NOTE.value].get().strip()
        }

        # Chiamata al controller per salvare i dati
        success, message = self.invoice_controller.update_invoice(self.current_invoice_id, invoice_data)
        if success:
            print(f"Invoice {self.invoice_controller.retrieve_invoice_map_by_id(self.current_invoice_id)[DBInvoicesColumns.NUMERO_FATTURA.value]} salvata con successo")
            ViewUtils.show_confirm_popup_2(self.content_frame, "SALVATAGGIO COMPLETATO", message)
            self.switch_modify.deselect()
            self.toggle_edit(self.content_frame)
            payments = self.invoice_controller.retrieve_invoice_with_payments_map_list(self.current_invoice_id)
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
            DBInvoicesColumns.STATUS.value : self.invoice_controller.InvoiceSatus.STORNATA.value
        }

        confirmation = ViewUtils.ask_confirmation_popup(self.content_frame, "Stai per stornare questa fattura.\n "
                                                             "Essa non verrà più conteggiata all'interno del sistema ma potrai comunque visionarla eo modificarla\n"
                                                             "Questa operazione non è irreversibile.\n"
                                                             "desideri continuare ?")

        if confirmation is False:
            return

        success, message = self.invoice_controller.storna_invoice(self.current_invoice_id, invoice_data)
        if success:
            invoice = self.invoice_controller.retrieve_invoice_map_by_id(self.current_invoice_id)
            print(f"Invoice {invoice[DBInvoicesColumns.NUMERO_FATTURA.value]} salvata con successo")
            ViewUtils.show_confirm_popup_2(self.content_frame, "FATTURA STORNATA CON SUCCESSO", message)
            self.invoice_info_widgets[DBInvoicesColumns.STATUS.value].configure(text=f"{self.invoice_controller.InvoiceSatus.STORNATA.value}")
            self.switch_modify.deselect()
            self.toggle_edit(self.content_frame)
            payments = self.invoice_controller.retrieve_invoice_with_payments_map_list(self.current_invoice_id)
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
                "value" : self.invoice_controller.calcola_totale_pagamenti_fattura(self.current_invoice_id)[0],
                "uom" : "€"
            },
            "TOTALE RATA 1": {
                "value": self.invoice_controller.calcola_totale_pagamenti_fattura(self.current_invoice_id)[1],
                "uom": "€"
            },
            "TOTALE RATA 2": {
                "value": self.invoice_controller.calcola_totale_pagamenti_fattura(self.current_invoice_id)[2],
                "uom": "€"
            },
            "TOTALE RATA 3": {
                "value": self.invoice_controller.calcola_totale_pagamenti_fattura(self.current_invoice_id)[3],
                "uom": "€"
            }
        }

        invoice = self.invoice_controller.retrieve_invoice_map_by_id(self.current_invoice_id)
        if(int(invoice[DBInvoicesColumns.NUMERO_RATE.value]) == int(self.invoice_controller.Rateizzazione.UNA.value)):
            self.payments_global_infos.pop("TOTALE RATA 1")
            self.payments_global_infos.pop("TOTALE RATA 2")
            self.payments_global_infos.pop("TOTALE RATA 3")


        self.global_infos_payments_widgets = ViewUtils.construct_global_infos_cards(section_frame, self.payments_global_infos)
        self.toggle_warning_global_info_payments()


        # tabella payments
        payments_frame = ctk.CTkScrollableFrame(section_frame, height=300)
        payments_frame.pack(fill="both", expand=True, padx=(10, 20), pady=(10, 20))

        # popolo i payments
        payments = self.invoice_controller.retrieve_invoice_with_payments_map_list(self.current_invoice_id)
        for payment in payments:
            if payment[DBPaymentsColumns.PAYMENT_NAME.value] is not None:
                nome_pagamento = payment[DBPaymentsColumns.PAYMENT_NAME.value]
                id_pagamento = payment[DBPaymentsColumns.ID.value]
                pagamento_button = ctk.CTkButton(payments_frame, text=f"{nome_pagamento}")
                pagamento_button.pack(padx=10, pady=10, fill="x", expand=True)

    #da salvare come callback alla modifica/aggiunta di un pagamento
    def toggle_warning_global_info_payments(self):
        if not hasattr(self, "global_infos_payments_widgets"):
            return  # L'oggetto non esiste ancora, esco silenziosamente

        # Ricalcola i nuovi valori delle rate
        totali = self.invoice_controller.calcola_totale_pagamenti_fattura(self.current_invoice_id)
        invoice = self.invoice_controller.retrieve_invoice_map_by_id(self.current_invoice_id)
        totale_fattura = float(invoice[DBInvoicesColumns.NETTO_A_PAGARE.value])
        tot_rata = totale_fattura if str(invoice[DBInvoicesColumns.NUMERO_RATE.value]) == str(self.invoice_controller.Rateizzazione.UNA.value) else totale_fattura/3

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

    def _create_production_expenses_history(self):
        """Crea la sezione storico delle spese di produzione"""
        section_frame = ctk.CTkFrame(self.wrapper_frame, border_width=2, border_color="#2659ab")
        section_frame.pack(fill="both", side="left", expand=True, pady=0, padx=(0, 30))

        ctk.CTkLabel(section_frame, text="SPESE DI PRODUZIONE ASSOCIATE", font=("Arial", 14, "bold")).pack(anchor="w", pady=(10, 10), padx=10)

        global_infos = {
            "TOTALE SPESE" : {
                "value" : self.invoice_controller.calcola_totale_spese_produzione_fattura(self.current_invoice_id),
                "uom" : "€"
            }
        }

        self.global_infos_payments_widgets = ViewUtils.construct_global_infos_cards(section_frame, global_infos)

        # tabella payments
        expenses_frame = ctk.CTkScrollableFrame(section_frame, height=300)
        expenses_frame.pack(fill="both", expand=True, padx=(10, 20), pady=(10, 20))

        # popolo i payments
        expenses = self.invoice_controller.retrieve_invoice_with_expenses_map_list(self.current_invoice_id)
        for expense in expenses:
            if expense[DBExpensesColumns.NAME.value] is not None:
                nome_spesa = expense[DBExpensesColumns.NAME.value]
                id_spesa = expense[DBExpensesColumns.ID.value]
                spesa_button = ctk.CTkButton(expenses_frame, text=f"{nome_spesa}")
                spesa_button.pack(padx=10, pady=10, fill="x", expand=True)


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
import customtkinter as ctk
import tkinter as tk
from tkcalendar import Calendar
from Views.View_utils import ViewUtils
from Controllers import ValidationUtils, InvoiceController, UserController, ControllerUtils
from Model import DBInvoicesColumns, DBUsersColumns, DBClientsColumns, DBProductionsColumns, DBPaymentsColumns, DBAccountsColumns
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

    def __init__(self, db_model, invoice_controller, user_controller, client_controller, production_controller, payment_controller, account_controller, tab, fiscal_settings):
        super().__init__()

        self.db_model = db_model
        self.invoice_controller = invoice_controller
        self.user_controller = user_controller
        self.client_controller = client_controller
        self.production_controller = production_controller
        self.payment_controller = payment_controller
        self.account_controller = account_controller
        self.tab = tab
        self.fiscal_settings = fiscal_settings

        #aggiorno lo stato delle fatture in funzione della data di oggi e dei pagamenti effettuati
        #self.invoice_controller.update_stato_fatture()

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

    def create_invoices_tab(self):

        self.switch_frame = ctk.CTkFrame(self.tab)
        self.switch_frame.pack(fill="x")
        ctk.CTkLabel(self.switch_frame, text="LORDI   ", font=("Arial", 20)).pack(pady=(10,0), padx=(10, 0), anchor="w", side=ctk.LEFT)
        self.lordo_netto_switch = ctk.CTkSwitch(self.switch_frame,
                                                text="  NETTI", font=("Arial", 20),
                                                command=self.switch_lordo_netto,
                                                width=200, switch_width=60,
                                                height=48, switch_height=20,
                                                variable=self.lordo_netto_switch_var)
        self.lordo_netto_switch.pack(pady=(10,0), anchor="w")

        self.search_bar_frame = ctk.CTkFrame(self.tab)
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
            card = ctk.CTkFrame(self.search_bar_frame)

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

        self.invoices_table_frame = ctk.CTkFrame(self.tab)
        self.invoices_table_frame.pack(pady=(20, 0), padx=(10,15), fill="x", anchor="n")

        self.headers = ["NOME", "CLIENTE", "UTENTE", "PRODUZIONE\nASSOCIATA", "DATA EMISSIONE", "STATO",
                   "RATE", ViewUtils.split_string_by_length("NETTO A PAGARE", 6), "TIPOLOGIA"]

        for i, header in enumerate(self.headers):
            # crea il container
            column = ctk.CTkFrame(self.invoices_table_frame)
            column.grid(row=0, column=i, sticky="nsew", padx=(0, 5), pady=5)

            # imposta peso e uniformità: tutte le colonne "col" si dividono equamente
            self.invoices_table_frame.grid_columnconfigure(i, weight=1, uniform="col")

            # la label riempie il suo container
            label = ctk.CTkLabel(column,
                                 text=header,
                                 font=("Arial", 14))
            label.pack(fill="both", expand=True, padx=5, pady=15)

        # Creazione del frame delle cards
        self.invoices_cards_frame = ctk.CTkScrollableFrame(self.tab)
        self.invoices_cards_frame.pack(padx=0, pady=10, fill="both", expand=True)

        self.add_invoice_frame = ctk.CTkFrame(self.tab)
        self.add_invoice_frame.pack(padx=0, pady=(5, 20), fill="x")

        self.save_button = ctk.CTkButton(self.add_invoice_frame, text="Aggiungi una fattura",
                                         command=self.open_add_invoice_window)
        self.save_button.pack()

        #aggiungo una tab per ogni fattura presente nel database
        for invoice in self.invoice_controller.retrieve_invoices_map_list(True):
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
                            command=lambda: self.open_invoice_detail(invoice_id))
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
                invoice_data[label_text] = widget.get().strip()
            elif isinstance(widget, Calendar):
                invoice_data[label_text] = widget.get_date()
            elif isinstance(widget, ctk.CTkTextbox):
                invoice_data[label_text] = widget.get("1.0", "end-1c").strip()  # Recupera il testo dal Textbox

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

    def open_invoice_detail(self, invoice_id):
        """self.client_details_window = ctk.CTkToplevel(self)
        invoice_db_info = self.client_controller.retrieve_client_map_by_id(invoice_id)
        self.client_details_window.title(f"Dettaglio del cliente: {invoice_db_info[DBClientsColumns.NAME.value]}")

        # Assicurati che la finestra rimanga sopra
        self.client_details_window.lift()  # Porta la finestra sopra quella principale
        self.client_details_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

        self.client_details_window.geometry("700x700")"""

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


import customtkinter as ctk
import tkinter as tk
from tkcalendar import Calendar
from Views.View_utils import ViewUtils
from Controllers import ValidationUtils, InvoiceController, UserController, ControllerUtils
from Model import DBInvoicesColumns, DBUsersColumns, DBClientsColumns, DBProductionsColumns
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

    def __init__(self, db_model, invoice_controller, user_controller, client_controller, production_controller, tab, fiscal_settings):
        super().__init__()

        self.db_model = db_model
        self.invoice_controller = invoice_controller
        self.user_controller = user_controller
        self.client_controller = client_controller
        self.production_controller = production_controller
        self.tab = tab
        self.fiscal_settings = fiscal_settings

        #aggiorno lo stato delle fatture in funzione della data di oggi e dei pagamenti effettuati
        self.invoice_controller.update_stato_fatture()

        self.invoices_card_list = {}
        self.invoice_card_labels_status = {}
        self.invoice_card_rate_frames = {}
        self.amount_aggregate_labels = {}

        self.invoices_list_of_user = self.invoice_controller.retrieve_invoices_map_list_by_user(1, True) #inizializzo la lista delle fatture con le sole fatture dell'utente con ID 1
        self.productions_list_of_client = {}
        self.populate_production_list_by_selected_client(self.client_controller.clients_list[0][DBClientsColumns.NAME.value])

        #self.invoice_controller.register_on_modify_invoice_callbacks(self.toggle_specific_invoice_status_color, self.toggle_specific_invoice_rate_color)

    def create_invoices_tab(self):

        def populate_global_infos():
            self.global_infos_lordi["# FATTURE"] = self.invoice_controller.current_year_invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.NUMERO_FATTURE.value]
            self.global_infos_lordi["FATTURATO"] = self.invoice_controller.current_year_invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.FATT_LORDO.value]
            self.global_infos_lordi["CREDITI"] = self.invoice_controller.current_year_invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.CREDITI_LORDO.value]
            self.global_infos_lordi["MEDIA FATTURE"] = self.invoice_controller.current_year_invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.MEDIA_FATTURA_LORDO.value]
            self.global_infos_lordi["PAGAMENTO \n ORARIO"] = 0

            self.global_infos_netti["# FATTURE"] = self.invoice_controller.current_year_invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.NUMERO_FATTURE.value]
            self.global_infos_netti["FATTURATO"] = self.invoice_controller.current_year_invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.FATT_NETTO.value]
            self.global_infos_netti["CREDITI"] = self.invoice_controller.current_year_invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.CREDITI_NETTO.value]
            self.global_infos_netti["MEDIA FATTURE"] = self.invoice_controller.current_year_invoices_aggregated_data[InvoiceController.InvoiceAggregatedData.MEDIA_FATTURA_NETTO.value]
            self.global_infos_netti["PAGAMENTO \n ORARIO"] = 0

        self.lordo_netto_switch_var = tk.BooleanVar(value=False) #false è Lordo

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

        self.global_infos_lordi = {}
        self.global_infos_netti = {}
        self.search_bar_frame = ctk.CTkFrame(self.tab)
        self.search_bar_frame.pack(pady=(5, 10), fill="x", anchor="n")
        self.search_bar = ctk.CTkEntry(self.search_bar_frame)
        self.search_bar.pack(padx=(5,35), anchor="s", side="right")
        self.search_bar_label = ctk.CTkLabel(self.search_bar_frame, text="Filtra per nome:", font=("Arial", 14))
        self.search_bar_label.pack(padx=5, anchor="s", side="right")

        # Ottieni il valore di default dei corner radius dai pulsanti
        default_corner_radius = ctk.ThemeManager.theme["CTkButton"]["corner_radius"]
        populate_global_infos()
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

        self.headers = ["NOME", "CLIENTE", "UTENTE", "DATA EMISSIONE", "STATO",
                   "RATE", ViewUtils.split_string_by_length("NETTO A PAGARE", 6), "TIPOLOGIA"]

        for i, header in enumerate(self.headers):
            column = ctk.CTkFrame(self.invoices_table_frame)
            label = ctk.CTkLabel(column, text=f"{header}", font=("Arial", 14), width=210)
            column.pack(padx=(0,5), pady=5, fill="y", expand=True, side="left")
            label.pack(padx=5, pady=15, anchor="n")

        # Creazione del frame delle cards
        self.invoices_cards_frame = ctk.CTkScrollableFrame(self.tab)
        self.invoices_cards_frame.pack(padx=0, pady=10, fill="both", expand=True)

        self.add_invoice_frame = ctk.CTkFrame(self.tab)
        self.add_invoice_frame.pack(padx=0, pady=(5, 20), fill="x")

        self.save_button = ctk.CTkButton(self.add_invoice_frame, text="Aggiungi una fattura",
                                         command=self.open_add_invoice_window)
        self.save_button.pack()

        #aggiungo una tab per ogni fattura presente nel database
        for invoice in self.invoice_controller.current_year_invoices_list:
            invoice_id = invoice[DBInvoicesColumns.ID.value]
            invoice_name = invoice[DBInvoicesColumns.NUMERO_FATTURA.value]
            invoice_client_ID = invoice[DBInvoicesColumns.ID_CLIENTE.value]
            invoice_client_name = self.client_controller.retrieve_client_map_by_id(invoice_client_ID)[DBClientsColumns.NAME.value]
            invoice_user_id = invoice[DBInvoicesColumns.ID_UTENTE.value]
            invoice_user_name = self.user_controller.retrieve_user_map_by_id(invoice_user_id)[DBUsersColumns.FIRST_NAME.value] + self.user_controller.retrieve_user_map_by_id(invoice_user_id)[DBUsersColumns.LAST_NAME.value]
            invoice_creation_date = invoice[DBInvoicesColumns.DATA_CREAZIONE.value]
            invoice_state = invoice[DBInvoicesColumns.STATUS.value]
            invoice_rate = invoice[DBInvoicesColumns.NUMERO_RATE.value]
            invoice_tot_documento = invoice[DBInvoicesColumns.NETTO_A_PAGARE.value]
            invoice_tipologia = invoice[DBInvoicesColumns.TIPO.value]

            self.add_invoice_card(invoice_id, invoice_name, invoice_client_name, invoice_user_name, invoice_creation_date, invoice_state, invoice_rate, invoice_tot_documento, invoice_tipologia)

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
            DBInvoicesColumns.NOTE.value: ctk.CTkTextbox
        }

        self.error_fields = {
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
                                      values=[f"{item[DBUsersColumns.FIRST_NAME.value]} {item[DBUsersColumns.LAST_NAME.value]}" for item in self.user_controller.users_list],
                                      command=lambda selected_value: self.update_entries_on_regime_fiscale(selected_value))
            elif label_text == self.nome_cliente_string:
                widget = widget_class(self.invoice_window_scrollableFrame,
                                      values=[f"{item[DBClientsColumns.NAME.value]}" for item in self.client_controller.clients_list],
                                      command=lambda selected_value: self.update_productions_list(selected_value))
            elif label_text == self.nome_produzione_string:
                widget = widget_class(self.invoice_window_scrollableFrame,
                                      values=[f"{item[DBProductionsColumns.NAME.value]}" for item in self.production_controller.CY_production_list])
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

        self.selected_user = self.invoice_widgets[self.nome_utente_string].get()

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

    def add_invoice_card(self, invoice_id, nome, cliente, utente, data_creazione, stato, rate, tot_documento, tipologia):
        """
          Aggiunge una singola card con i dati forniti alla scrollable frame.

          :param invoice_id: ID della fattura associato dal database
          :param nome: Nome della fattura
          :param cliente: nome del cliente
          :param utente: nome dell'utente
          :param data_creazione: data di emissiione della fattura
          :param stato: da InvoiceController.InvoiceSatus o InvoiceController.InvoiceRateizzazSatus
          :param rate: da InvoiceController.Rateizzazione
          :param tot_documento: Importo totale sul documento
          :param tipologia: da InvoiceController.Tipologia
          """
        # Creazione della card
        card = ctk.CTkFrame(self.invoices_cards_frame, fg_color="dimgray")
        card.pack(pady=10, padx=14, fill="x", expand=True)  # Spaziatura tra le card

        ctk.CTkButton(card, text=f"{nome}", width=200, command=lambda: self.open_invoice_detail(invoice_id)).pack(
            padx=(10, 0), pady=10, fill="both", side="left")


        # Dati da visualizzare nella card
        data = [cliente, utente, ViewUtils.invert_data_string(data_creazione), stato, rate, tot_documento, tipologia]
        units = ["", "", "", "", "", "€", ""]
        i = 0
        # Aggiunta dei dati alla card
        for value in data:
            if i != 4: #per tutti tranne che per le rate
                label = ctk.CTkLabel(card, text=f"{value} {units[i]}", font=("Arial", 14), width=200)
                label.pack(padx=0, pady=5, fill="both", expand=True, side="left")
            else:
                rate_frame = ctk.CTkFrame(card, width=200)
                rate_frame.pack(padx=5, pady=5, fill="both", expand=True, side="left")
                label_1 = ctk.CTkLabel(rate_frame, text="1", font=("Arial", 14), width=60)
                label_1.pack(padx=0, pady=5, fill="both", expand=True, side="left")
                label_2 = ctk.CTkLabel(rate_frame, text="2", font=("Arial", 14), width=60)
                label_2.pack(padx=0, pady=5, fill="both", expand=True, side="left")
                label_3 = ctk.CTkLabel(rate_frame, text="3", font=("Arial", 14), width=60)
                label_3.pack(padx=0, pady=5, fill="both", expand=True, side="left")

            #salvo i labels dello stato per poter eseguire dei configure per cambiare il colore
            if i == 3:
                self.invoice_card_labels_status[invoice_id] = label
            elif i == 4:
                self.invoice_card_rate_frames[invoice_id] = rate_frame

            i = i + 1

        self.toggle_invoices_status_color()
        self.toggle_invoices_rate_color()

        self.invoices_card_list[nome] = card

    def save_invoice_data(self):
        invoice_data = {}

        #riempi il dizionario con i dati dei widgets primari
        for label_text, widget in self.invoice_widgets.items():
            if isinstance(widget, ctk.CTkEntry) or isinstance(widget, ctk.CTkOptionMenu):
                invoice_data[label_text] = widget.get()
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
        self.invoice_widgets[self.nome_produzione_string].configure(values=[f"{item[DBProductionsColumns.NAME.value]}" for item in self.production_controller.CY_production_list])

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
        invoices = self.invoice_controller.retrieve_invoice_map_by_name(selected_value)
        user_name = self.invoice_widgets[self.nome_utente_string].get()
        user_full_name = user_name.split(" ")
        user_first = user_full_name[0]
        user_last = user_full_name[1]
        user = self.user_controller.retrieve_user_by_fullname(user_first, user_last)
        user_id = user[0]
        #tengo solo le fatture relative all'utente in questione
        for i, d in enumerate(invoices):
            if d[DBInvoicesColumns.ID_UTENTE.value] != user_id:
                elemento_rimosso = invoices.pop(i)
                break

        if len(invoices) == 1:
            nome_fattura = invoices[0][DBInvoicesColumns.NUMERO_FATTURA.value] + " - NDC"
            servizi = invoices[0][DBInvoicesColumns.SERVIZI.value]
            id_cliente = invoices[0][DBInvoicesColumns.ID_CLIENTE.value]
            nome_cliente = self.client_controller.retrieve_client_map_by_id(id_cliente)[DBClientsColumns.NAME.value]
            rimborsi = invoices[0][DBInvoicesColumns.RIMBORSI.value]
            rivalsa = invoices[0][DBInvoicesColumns.RIVALSA_INPS.value]
            metodo_pagamento = invoices[0][DBInvoicesColumns.METODO_PAGAMENTO.value]
            numero_rate = invoices[0][DBInvoicesColumns.NUMERO_RATE.value]
            self.invoice_widgets[DBInvoicesColumns.NUMERO_FATTURA.value].delete(0, tk.END)
            self.invoice_widgets[DBInvoicesColumns.NUMERO_FATTURA.value].insert(0, nome_fattura)
            self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].delete(0, tk.END)
            self.invoice_widgets[DBInvoicesColumns.SERVIZI.value].insert(0, servizi)
            self.invoice_widgets[DBInvoicesColumns.RIMBORSI.value].delete(0, tk.END)
            self.invoice_widgets[DBInvoicesColumns.RIMBORSI.value].insert(0, rimborsi)
            self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].delete(0, tk.END)
            self.invoice_widgets[DBInvoicesColumns.RIVALSA_INPS.value].insert(0, rivalsa) if rivalsa else 0
            self.invoice_widgets[self.nome_cliente_string].set(nome_cliente)
            self.invoice_widgets[DBInvoicesColumns.METODO_PAGAMENTO.value].set(metodo_pagamento)
            self.invoice_widgets[DBInvoicesColumns.NUMERO_RATE.value].set(numero_rate)

        else:
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

            for invoice in invoices:
                invoice_frame = ctk.CTkFrame(global_frame)
                invoice_frame.pack(side=ctk.LEFT)
                invoice_content = "\n".join(
                    f"{column.value}: {invoice.get(column.value, 'N/A')}"
                    for column in DBInvoicesColumns
                )
                ctk.CTkLabel(invoice_frame, text = invoice_content).pack(pady=5, padx=5)
                ctk.CTkButton(invoice_frame, text="Seleziona", command=lambda: self.select_correct_invoice(invoice))

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

    def toggle_invoices_status_color(self):
        """
        Funzione che assegna un colore al label relativo allo stato delle cards delle fatture

        """
        for (key, label) in self.invoice_card_labels_status.items():
            #cerco la fattura associata
            for invoice in self.invoice_controller.current_year_invoices_list:
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

        return

    #callback da registrare nel controller
    def toggle_specific_invoice_status_color(self, invoice_id):
        fattura = self.invoice_controller.retrieve_invoice_map_by_id(invoice_id)
        label = self.invoices_card_list[fattura[DBInvoicesColumns.NUMERO_FATTURA.value]]
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

    def toggle_invoices_rate_color(self):
        """
        Funzione che assegna un colore ai labels relativi allo stato dei pagamenti delle rate

        """
        today = datetime.today().date()

        for (key, frame) in self.invoice_card_rate_frames.items():
            #cerco la fattura associata
            for invoice in self.invoice_controller.current_year_invoices_list:
                if invoice[DBInvoicesColumns.ID.value] == key:
                    fattura = invoice
                    break

            pagamento_1 = fattura[DBInvoicesColumns.DATA_PAGAMENTO_1.value]
            pagamento_2 = fattura[DBInvoicesColumns.DATA_PAGAMENTO_2.value]
            pagamento_3 = fattura[DBInvoicesColumns.DATA_PAGAMENTO_3.value]
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

    # callback da registrare nel controller
    def toggle_specific_invoice_rate_color(self, invoice_id):
        """
        Funzione che assegna un colore ai labels relativi allo stato dei pagamenti delle rate

        """
        today = datetime.today().date()

        fattura = self.invoice_controller.retrieve_invoice_map_by_id(invoice_id)
        frame = self.invoice_card_rate_frames[invoice_id]

        pagamento_1 = fattura[DBInvoicesColumns.DATA_PAGAMENTO_1.value]
        pagamento_2 = fattura[DBInvoicesColumns.DATA_PAGAMENTO_2.value]
        pagamento_3 = fattura[DBInvoicesColumns.DATA_PAGAMENTO_3.value]
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

    def switch_lordo_netto(self):
        if not self.lordo_netto_switch_var.get(): #se è falsa allora mostro i lordi
            for (key,label) in self.amount_aggregate_labels.items():
                self.amount_aggregate_labels[key].configure(text=f"{self.global_infos_lordi[key]}")

        else: # se è vero allora mostro i netti
            for (key,label) in self.amount_aggregate_labels.items():
                self.amount_aggregate_labels[key].configure(text=f"{self.global_infos_netti[key]}")


    def clear_class_variable(self):  #potrebbe non servire in quanto vengono inizializzate all'apertura della funzione
        self.invoice_widgets.clear()
        self.invoice_labels.clear()


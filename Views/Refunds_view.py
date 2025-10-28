import customtkinter as ctk
import tkinter as tk
from tkcalendar import Calendar
from Views.View_utils import ViewUtils
from Controllers import PaymentsController, InvoiceController, UserController, ControllerUtils, RefundController
from Model import DBInvoicesColumns, DBUsersColumns, DBClientsColumns, DBPaymentsColumns, DBProductionsColumns, DBAccountsColumns, DBRefundsColumns
from datetime import datetime
import re
from enum import Enum

class RefundsView(ctk.CTkFrame):

    def __init__(self, db_model, refunds_controller, client_controller,
                 account_controller, update_controller, tab_view,
                 analyzer, event_bus, initial_refund_id=None):
        super().__init__(tab_view.tab("Rimborsi"))

        self.db_model = db_model
        self.refunds_controller = refunds_controller
        self.client_controller = client_controller
        self.account_controller = account_controller
        self.update_controller = update_controller
        self.tab_view = tab_view
        self.tab = tab_view.tab("Rimborsi")
        self.analyzer = analyzer
        self.event_bus = event_bus

        self.global_infos = {}
        self.amount_aggregate_labels = {}

        self.refund_card_list = {}
        self.refund = {}
        self.cards_warnings = {}

        #self.event_bus.subscribe(ViewUtils.EventBusKeys.SHOW_REFUND_DETAIL, self.handle_show_refund_detail)

        # Container principale
        self.main_container = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.detail_container = ctk.CTkFrame(self, fg_color="#2b2b2b")

        # Vista dettaglio
        self.refund_detail_view = RefundDetailView(
            parent=self,
            back_callback=self.show_main_view,
            client_controller=self.client_controller,
            account_controller=account_controller,
            refund_controller=refunds_controller,
            db_model=db_model,
            analyzer=self.analyzer,
            event_bus = self.event_bus,
        )

        self.create_refunds_tab()

        if initial_refund_id is not None:
            self.after(100, lambda: self.open_refund_detail_tab(initial_refund_id))
        else:
            self.show_main_view()


    def create_refunds_tab(self):

        self.search_bar_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.search_bar_frame.pack(pady=(5, 10), fill="x", anchor="s")
        self.search_bar = ctk.CTkEntry(self.search_bar_frame)
        self.search_bar.pack(padx=(5, 35), anchor="s", side="right")
        self.search_bar_option_menu_values = {"NOME RIMBORSO": "NOME RIMBORSO", "NOME CLIENTE": "NOME CLIENTE", "CONTO": "CONTO"}

        self.search_bar_optionMenu = ctk.CTkOptionMenu(self.search_bar_frame,
                                                       values=list(self.search_bar_option_menu_values.values()))
        self.search_bar_optionMenu.pack(padx=5, anchor="s", side="right")
        self.search_bar_label = ctk.CTkLabel(self.search_bar_frame, text="Filtra per ", font=("Arial", 14))
        self.search_bar_label.pack(padx=5, anchor="s", side="right")

        self.order_bar_option_menu_values = {"DATA CREAZIONE": "DATA CREAZIONE",
                                             "ULTIMA MODIFICA": "ULTIMA MODIFICA",
                                              "TOTALE": "TOTALE",
                                             "DATA EMISSIONE": "DATA EMISSIONE"}
        self.order_bar_option_menu_values_types = {"DECRESCENTE": "DECRESCENTE", "CRESCENTE": "CRESCENTE"}
        self.order_bar_optionMenu_types = ctk.CTkOptionMenu(self.search_bar_frame,
                                                       values=list(self.order_bar_option_menu_values_types.values()))
        self.order_bar_optionMenu_types.pack(padx=(5, 100), anchor="s", side="right")
        self.order_bar_optionMenu = ctk.CTkOptionMenu(self.search_bar_frame,
                                                       values=list(self.order_bar_option_menu_values.values()))
        self.order_bar_optionMenu.pack(padx=5, anchor="s", side="right")
        self.order_bar_label = ctk.CTkLabel(self.search_bar_frame, text="Ordina per ", font=("Arial", 14))
        self.order_bar_label.pack(padx=5, anchor="s", side="right")

        # Aggiungi evento alla barra di ricerca
        self.search_bar.bind("<KeyRelease>", self.filter_cards)

        self.order_bar_optionMenu.configure(command=lambda _: self.sort_cards())
        self.order_bar_optionMenu_types.configure(command=lambda _: self.sort_cards())

        self.populate_global_infos()

        for (key, info) in self.global_infos.items():
            card = ctk.CTkFrame(self.search_bar_frame, fg_color="#333333")

            if key == RefundController.RefundsAggregateData.NUMERO_RIMBORSI.value:
                global_info_unità_di_misura = ""
            elif key == RefundController.RefundsAggregateData.TOT_RIMBORSI.value:
                global_info_unità_di_misura = "€"

            title = ctk.CTkLabel(card, text=f"{key}", font=("Arial", 12), bg_color="#1F6AA5")
            amount = ctk.CTkLabel(card, text=f"{info} {global_info_unità_di_misura}", font=("Arial", 16))

            card.pack(side="left", anchor="w", padx=10, pady=(10, 5))
            title.pack(anchor="n", padx=10, pady=(10, 5), ipadx=7, ipady=5)
            amount.pack(anchor="s", padx=10, pady=5)

            # salvo i dati che potrebbero avere bisogno di configure successivamente
            self.amount_aggregate_labels[f"{key}"] = amount

        self.refunds_table_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.refunds_table_frame.pack(pady=(20, 0), padx=(10, 15), fill="x", anchor="n")

        self.table_headers = ["NOME", "CLIENTE", "TOTALE", "DATA\nEMISSIONE", "CONTO\nCORRENTE"]

        for i, header in enumerate(self.table_headers):
            # crea il container
            column = ctk.CTkFrame(self.refunds_table_frame, fg_color="#333333")
            column.grid(row=0, column=i, sticky="nsew", padx=(0, 5), pady=5)

            # imposta peso e uniformità: tutte le colonne "col" si dividono equamente
            self.refunds_table_frame.grid_columnconfigure(i, weight=1, uniform="col")

            # la label riempie il suo container
            label = ctk.CTkLabel(column,
                                 text=header,
                                 font=("Arial", 14))
            label.pack(fill="both", expand=True, padx=5, pady=15)

        # Creazione del frame delle cards
        self.refunds_cards_frame = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")
        self.refunds_cards_frame.pack(padx=0, pady=10, fill="both", expand=True)

        self.add_refund_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.add_refund_frame.pack(padx=0, pady=(5, 20), fill="x")

        self.save_button = ctk.CTkButton(self.add_refund_frame, text="Aggiungi un rimborso",
                                         command=self.open_add_refund_window)
        self.save_button.pack()

        # Sistema per tracciare gli after()
        self._after_ids = set()
        self._orig_after = self.after
        self.after = self._track_after

        self.load_refunds_chunked()

        self.sort_cards()

        # warnings launch
        for card in self.refund_card_list.values():
            ViewUtils.toggle_warning_on_card(card, self.cards_warnings)

    def show_main_view(self):
        """Torna alla vista principale"""
        self.refund_detail_view.pack_forget()
        self.main_container.pack(fill='both', expand=True)

    def open_refund_detail_tab(self, refund_id):
        """Mostra la vista dettaglio rimborso con controlli di sicurezza"""
        try:
            # Verifica che i widget esistano
            if hasattr(self, 'main_container') and self.main_container.winfo_exists():
                self.main_container.pack_forget()

            # Se refund_detail_view non esiste, crealo
            if not hasattr(self, 'refund_detail_view') or not self.refund_detail_view.winfo_exists():
                self.refund_detail_view = RefundDetailView(
                    parent=self,
                    back_callback=self.show_main_view,
                    client_controller=self.client_controller,
                    account_controller=self.account_controller,
                    refund_controller=self.refunds_controller,
                    db_model=self.db_model,
                    analyzer=self.analyzer,
                    event_bus=self.event_bus,
                )

            # Mostra il dettaglio
            self.refund_detail_view.pack(fill='both', expand=True)
            self.refund_detail_view.create_detail_tab(refund_id)  # Ricrea i contenuti ogni volta

        except Exception as e:
            print(f"Errore in open_refund_detail_tab: {e}")
            # Fallback: mostra la vista principale
            self.show_main_view()


    def handle_show_refund_detail(self, refund_id):
        self.tab_view.set("Rimborsi")  # Cambia tab
        self.open_refund_detail_tab(refund_id)  # Mostra il dettaglio

    def filter_cards(self, event):
        """Filtra le card in base al testo della barra di ricerca e al tipo di filtro scelto."""
        search_text = self.search_bar.get().lower()
        search_type = self.search_bar_optionMenu.get()

        # Mappatura: ogni chiave associa una tupla (indice, classe_attesa) del widget da cui prelevare il testo
        filter_mapping = {
            "NOME RIMBORSO": (0, ctk.CTkButton),  # Bottone
            "NOME CLIENTE": (1, ctk.CTkLabel),
            "CONTO": (4, ctk.CTkLabel)
        }

        mapping = filter_mapping.get(search_type)

        # Rimuovo tutte le card dal container per avere un layout pulito
        for card in self.refund_card_list.values():
            card.pack_forget()

        # Se il tipo di ricerca non è riconosciuto, riposiziono tutte le card nell'ordine originale
        if mapping is None:
            for card in self.refund_card_list.values():
                card.pack(pady=10, padx=10, fill="x", expand=True)
            return

        idx, expected_class = mapping

        # Itera sulle card nell’ordine originale
        for key, card in self.refund_card_list.items():
            children = card.winfo_children()  # Lista dei widget figli
            widget_text = ""
            if len(children) > idx and isinstance(children[idx], expected_class):
                widget = children[idx]
                # Per CTkOptionMenu, usa il metodo get() anziché cget("text")
                if isinstance(widget, ctk.CTkOptionMenu):
                    widget_text = widget.get()
                else:
                    widget_text = widget.cget("text")
            # Se il testo estratto (in lowercase) contiene il testo di ricerca, riposiziona la card
            if search_text in widget_text.lower():
                card.pack(pady=10, padx=10, fill="x", expand=True)

    def sort_cards(self):
        """Ordina le cards dei rimborsi in base ai criteri selezionati nei menu di ordinamento."""

        # Funzioni di supporto per la conversione dei valori
        def _convert_to_currency(currency_str):
            """Converte una stringa di valuta in un numero float per l'ordinamento."""
            # Rimuovi il simbolo dell'euro, gli spazi, e gestisci separatori
            cleaned = currency_str.strip().replace('€', '').replace(' ', '').replace('.', '').replace(',', '.')
            return float(cleaned)

        def _convert_to_datetime(datetime_str):
            """Converte una stringa in formato yyyy-mm-dd hh:mm:ss in un oggetto datetime per l'ordinamento."""
            from datetime import datetime
            return datetime.strptime(datetime_str.strip(), "%Y-%m-%d %H:%M:%S")

        def _convert_to_date(date_str):
            """Converte una stringa in formato dd-mm-yyyy in un oggetto date per l'ordinamento."""
            from datetime import datetime
            return datetime.strptime(date_str.strip(), "%d-%m-%Y")

        # Ottieni i criteri di ordinamento
        sort_by = self.order_bar_optionMenu.get()
        sort_order = self.order_bar_optionMenu_types.get()

        # Mappatura: ogni criterio associa una tupla (tipo_di_accesso, parametro, funzione_di_conversione, colonna_db)
        sort_mapping = {
            "TOTALE": ("direct", 2, _convert_to_currency, None),
            "DATA EMISSIONE": ("direct", 3, _convert_to_date, None),
            "DATA CREAZIONE": ("database", 0, _convert_to_datetime, "created_at"),
            "ULTIMA MODIFICA": ("database", 0, _convert_to_datetime, "updated_at")
        }

        mapping = sort_mapping.get(sort_by)

        # Se il tipo di ordinamento non è riconosciuto, non fare nulla
        if mapping is None:
            return

        access_type, param, converter, db_column = mapping
        reverse = (sort_order == "DECRESCENTE")

        # Correzione per TOTALE: inverti l'ordinamento
        #if sort_by == "TOTALE":
            #reverse = not reverse

        # Raccogli tutte le cards e i loro valori di ordinamento
        cards_with_values = []
        for key, card in self.refund_card_list.items():  # Assumendo che la lista si chiami refunds_card_list
            children = card.winfo_children()
            sort_value = ""

            if access_type == "direct":
                # Accesso diretto al valore nella card
                if len(children) > param:
                    sort_value = children[param].cget("text")
            elif access_type == "database":
                # Accesso al valore tramite database
                if len(children) > 0:
                    refund_name = children[0].cget("text")  # Nome rimborso dal primo child
                    # Assumendo che esista un controller per i rimborsi con un metodo retrieve_refund_map_by_name
                    refund_map = self.refunds_controller.retrieve_refund_map_by_name(refund_name)
                    if refund_map and db_column:
                        sort_value = refund_map.get(db_column, "")

            # Converti il valore nel tipo appropriato (applicando strip per rimuovere spazi)
            try:
                converted_value = converter(sort_value) if sort_value.strip() else None
            except (ValueError, TypeError):
                converted_value = None

            cards_with_values.append((key, card, converted_value))

        # Ordina le cards in base al valore convertito
        # Gestisci i valori None posizionandoli alla fine in entrambi i casi
        cards_with_values.sort(
            key=lambda x: (x[2] is not None, x[2]) if x[2] is not None else (False, None),
            reverse=reverse
        )

        # Nascondi temporaneamente tutte le cards
        for card in self.refund_card_list.values():
            card.pack_forget()

        # Riposiziona le cards nell'ordine ordinato
        for _, card, _ in cards_with_values:
            card.pack(pady=10, padx=10, fill="x", expand=True)

        # Forza l'aggiornamento dell'interfaccia
        self.update_idletasks()

    def populate_global_infos(self):
        self.global_infos[f"{RefundController.RefundsAggregateData.NUMERO_RIMBORSI.value}"] = self.refunds_controller.count_refunds(True)
        self.global_infos[f"{RefundController.RefundsAggregateData.TOT_RIMBORSI.value}"] = self.refunds_controller.calculate_tot_refunds(True)

    def open_add_refund_window(self):
        self.add_refund_window = ctk.CTkToplevel(self)
        self.add_refund_window.title("Aggiungi Nuovo Rimborso")

        # Assicurati che la finestra rimanga sopra
        self.add_refund_window.lift()  # Porta la finestra sopra quella principale
        self.add_refund_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

        self.add_refund_window.geometry("550x700")

        self.refund_window_scrollableFrame = ctk.CTkScrollableFrame(self.add_refund_window)
        self.refund_window_scrollableFrame.pack(fill="both", expand=True)

        self.nome_cliente_string = "NOME CLIENTE"
        self.nome_conto_string = "NOME CONTO"

        self.entry_fields = {
            DBRefundsColumns.REFUND_NAME.value: ctk.CTkEntry,
            DBRefundsColumns.REFUND_AMOUNT.value: ctk.CTkEntry,
            DBRefundsColumns.REFUND_DATE.value: Calendar,
            self.nome_cliente_string: ctk.CTkOptionMenu,
            self.nome_conto_string: ctk.CTkOptionMenu,
        }

        self.error_fields = {
            DBRefundsColumns.REFUND_NAME.value: ctk.CTkLabel,
            DBRefundsColumns.REFUND_AMOUNT.value: ctk.CTkLabel
        }

        self.refund_widgets = {}
        self.error_labels = {}
        self.refund_labels = {}

        # Creo i labels e i widgets
        for i, (label_text, widget_class) in enumerate(self.entry_fields.items()):
            # Etichetta
            label = ctk.CTkLabel(self.refund_window_scrollableFrame, text=label_text)
            # disegno i labels
            if i == 0:
                label.pack(pady=5)
            else:
                label.pack(pady=(35, 0))

            self.refund_labels[label_text] = label

            # creo i widgets
            if label_text == self.nome_conto_string:
                widget = widget_class(self.refund_window_scrollableFrame,
                                      values=[f"{item[DBAccountsColumns.NAME.value]}" for item in
                                              self.account_controller.retrieve_accounts_map_list()])
            elif label_text == self.nome_cliente_string:
                widget = widget_class(self.refund_window_scrollableFrame,
                                      values=[f"{item[DBClientsColumns.NAME.value]}" for item in
                                              self.client_controller.retrieve_clients_map_list()])
            elif label_text == DBRefundsColumns.REFUND_DATE.value:
                widget = widget_class(self.refund_window_scrollableFrame, date_pattern=ViewUtils.date_pattern)
            else:
                widget = widget_class(self.refund_window_scrollableFrame)

            widget.pack(pady=5, padx=10, fill="x", expand=True)

            self.refund_widgets[label_text] = widget

            if self.error_fields.get(label_text) is not None:
                error_label = ctk.CTkLabel(self.refund_window_scrollableFrame, text="")
                error_label.pack(pady=(0, 15))
                self.error_labels[label_text] = error_label

        # Bottone per salvare
        self.save_button = ctk.CTkButton(
            self.refund_window_scrollableFrame,
            text="Salva Rimborso",
            command=self.save_refund_data
        )
        self.save_button.pack(pady=(35, 15))

        # Aggiungi validazione agli eventi di perdita del focus
        self.refund_widgets[DBRefundsColumns.REFUND_NAME.value].bind("<FocusOut>",
                                                                        lambda event: ViewUtils.validate_entry(
                                                                            self.refund_widgets[
                                                                                DBRefundsColumns.REFUND_NAME.value],
                                                                            lambda val: val.strip() != "",
                                                                            self.error_labels[
                                                                                DBRefundsColumns.REFUND_NAME.value],
                                                                            "Il campo non può essere vuoto."
                                                                        ))

        self.refund_widgets[DBRefundsColumns.REFUND_AMOUNT.value].bind("<FocusOut>",
                                                                          lambda event: ViewUtils.validate_entry(
                                                                              self.refund_widgets[
                                                                                  DBRefundsColumns.REFUND_AMOUNT.value],
                                                                              lambda val: re.fullmatch(
                                                                                  r"^\d+(\.\d{2})?$",
                                                                                  val.strip()) is not None,
                                                                              self.error_labels[
                                                                                  DBRefundsColumns.REFUND_AMOUNT.value],
                                                                              "Inserimento non valido: inserire un numero monetario con due cifre decimali (es. 123.45)"
                                                                          ))

    def load_refunds_chunked(self):
        refunds_map_list = self.refunds_controller.retrieve_refunds_map_list(current_year=True)

        # Ordina la lista in ordine decrescente (dal più recente al più vecchio)
        refunds_map_list.sort(
            key=lambda x: datetime.strptime(
                x[DBRefundsColumns.UPDATED_AT.value],
                "%Y-%m-%d %H:%M:%S"
            ) if " " in x[DBRefundsColumns.UPDATED_AT.value] else datetime.strptime(
                x[DBRefundsColumns.UPDATED_AT.value],
                "%Y-%m-%d"
            ),
            reverse=True
        )

        extractor = ViewUtils.create_extractor_for_refunds(
            self.refunds_controller,
            self.client_controller,
            self.account_controller
        )

        ViewUtils.process_items_in_chunks(
            widget=self,
            items_list=refunds_map_list,
            add_card_callback=self.add_refund_card,
            extract_args_callback=extractor
        )

    def add_refund_card(self, refund_id, refund_name, amount, refund_date, client_name, nome_conto):
        """
        Aggiunge una card di rimborso alla scrollable frame con i dati specificati.

        :param refund_id: ID univoco del rimborso nel database.
        :param refund_name: Nome del rimborso.
        :param amount: Importo del rimborso.
        :param refund_date: Data in cui è stato effettuato il rimborso.
        :param client_name: Nome del cliente associato al rimborso.
        :param nome_conto: Nome del conto bancario associato al rimborso.
        """
        # Creazione della card
        card = ctk.CTkFrame(self.refunds_cards_frame, fg_color="dimgray")
        card.pack(pady=10, padx=8, fill="x", expand=True)  # Spaziatura tra le card

        # Dati da visualizzare nella card
        data = [refund_name, client_name, round(amount, 2), ViewUtils.invert_data_string(refund_date), nome_conto]
        units = ["", "", "€", "", ""]
        n_cols = len(data)  # 8 colonne totali

        # Configura il grid della card: 1 riga, n_cols colonne uguali
        for c in range(n_cols):
            card.grid_columnconfigure(c, weight=1, uniform="clientcol")
        card.grid_rowconfigure(0, weight=1)

        # 0) Bottone "nome"
        btn = ctk.CTkButton(
            card,
            text=refund_name,
            command=lambda rid=refund_id: self.open_refund_detail_tab(rid)
        )
        btn.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        # 1..7) Le altre colonne
        for idx, val in enumerate(data[1:], start=1):
            text = f"{val} {units[idx]}"
            lbl = ctk.CTkLabel(card, text=text, font=("Arial", 14))
            lbl.grid(row=0, column=idx, sticky="nsew", padx=5, pady=10)

        # Salva la card per eventuale successivo accesso
        self.refund_card_list[refund_name] = card

        # Se esiste un warning associato al nome del pagamento, aggiungi il tooltip
        if refund_name in self.cards_warnings:
            ViewUtils.add_tooltip(btn, self.cards_warnings[refund_name])

    def open_modify_payment(self, refund_id):
        return

    def save_refund_data(self):
        refund_data = {}

        # riempi il dizionario con i dati dei widgets primari
        for label_text, widget in self.refund_widgets.items():
            if isinstance(widget, ctk.CTkEntry) or isinstance(widget, ctk.CTkOptionMenu):
                refund_data[label_text] = widget.get().strip()
            elif isinstance(widget, Calendar):
                refund_data[label_text] = widget.get_date()
            elif isinstance(widget, ctk.CTkTextbox):
                refund_data[label_text] = widget.get("1.0", "end-1c").strip()  # Recupera il testo dal Textbox

        success, message = self.refunds_controller.save_refund(refund_data)

        if success:
            # prendo l'ID della fattura appena creata
            refund_map = self.refunds_controller.retrieve_last_refund_insert_map()
            print(f"Rimborso {refund_data[DBRefundsColumns.REFUND_NAME.value]} salvato con successo")


            client = self.client_controller.retrieve_client_map_by_id(refund_map[DBRefundsColumns.CLIENT_ID.value])
            client_name = client[DBClientsColumns.NAME.value]
            conto = self.account_controller.retrieve_account_map_by_id(refund_map[DBRefundsColumns.CONTO_ID.value])
            nome_conto = conto[DBAccountsColumns.NAME.value]

            self.add_refund_card(
                refund_map[DBRefundsColumns.ID.value],
                refund_map[DBRefundsColumns.REFUND_NAME.value],
                refund_map[DBRefundsColumns.REFUND_AMOUNT.value],
                refund_map[DBRefundsColumns.REFUND_DATE.value],
                client_name,
                nome_conto
            )

            self.clear_class_variable()
            self.add_refund_window.destroy()
        else:
            print(message)
            ViewUtils.show_error_popup(self.add_refund_window, "ERRORE", message)

    def clear_class_variable(self):
        self.refund_widgets.clear()
        self.refund_widgets.clear()

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




class RefundDetailView(ctk.CTkFrame):
    def __init__(self, parent, back_callback, client_controller, account_controller, refund_controller, db_model, analyzer, event_bus):
        super().__init__(parent)
        self.parent = parent
        self.refund_controller = refund_controller
        self.db_model = db_model
        self.back_callback = back_callback
        self.client_controller = client_controller
        self.account_controller = account_controller
        self.event_bus = event_bus
        self.current_refund_id = None
        self.analyzer = analyzer

        self.configure(fg_color="transparent")

        # Widgets persistenti (vanno creati una volta sola)
        self.head_frame = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.back_button = ctk.CTkButton(
            self.head_frame,
            text="Elenco Rimborsi",
            command=self._cleanup_and_go_back
        )
        self.title_label = ctk.CTkLabel(self.head_frame, font=("Arial", 22, "bold"))

        self.user_info_widgets: dict[str, ctk.CTkEntry | ctk.CTkOptionMenu] = {}

        self.nome_cliente_string = "CLIENTE ASSOCIATO"
        self.nome_conto_string = "CONTO"


        # Container per i contenuti dinamici
        self.content_frame = ctk.CTkFrame(self)

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

    def create_detail_tab(self, refund_id):
        """Ricrea la vista dettaglio per un rimborso specifico"""
        self.current_refund_id = refund_id

        # 1. Pulizia dei widget precedenti
        self._clear_content()

        # 2. Caricamento dati
        self.refund = self.refund_controller.retrieve_refund_map_by_id(refund_id)

        # 3. Aggiornamento elementi persistenti
        self.title_label.configure(
            text=f"{self.refund[DBRefundsColumns.REFUND_NAME.value]}")

        # 4. Creazione contenuti dinamici
        self._create_refund_info_section(self.refund)
        self.toggle_edit(self.content_frame)

        #self.wrapper_frame = ctk.CTkFrame(self.content_frame, fg_color="#333333")
        #self.wrapper_frame.pack(padx=25, pady=(90, 0), fill="both", expand=True)

    def _create_refund_info_section(self, refund_data):
        # Campi derivati per i rimborsi
        self.derived_fields_refunds = {
            # Potresti aggiungere campi calcolati qui se necessario
        }

        self.entry_fields_refunds = {
            # Dati Generali
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

            # Dati Fiscali
            DBRefundsColumns.REFUND_AMOUNT.value: {
                "type": ctk.CTkEntry,
                "label": "Importo Rimborsato (€)",
                "section": "Dati Fiscali"
            },

            # Collegamenti
            self.nome_cliente_string: {
                "type": ctk.CTkOptionMenu,
                "label": "Cliente",
                "section": "Collegamenti",
                "values": [c[DBClientsColumns.NAME.value] for c in self.client_controller.retrieve_clients_map_list()]
            },
            self.nome_conto_string: {
                "type": ctk.CTkOptionMenu,
                "label": "Conto",
                "section": "Collegamenti",
                "values": [c[DBAccountsColumns.NAME.value] for c in
                           self.account_controller.retrieve_accounts_map_list()]
            },

            # Campi statici
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

        self.error_fields_refunds = {
            DBRefundsColumns.REFUND_NAME.value: "Nome obbligatorio",
            DBRefundsColumns.REFUND_AMOUNT.value: "Valore numerico con massimo 2 decimali",
            DBRefundsColumns.REFUND_DATE.value: "Data obbligatoria"
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

        # Inizializzazione strutture dati
        self.refund_info_widgets = {}
        self.refund_info_labels = {}
        self.error_labels_refunds = {}
        sections = {}

        refund_name = refund_data[DBRefundsColumns.REFUND_NAME.value]
        warning = self.parent.cards_warnings.get(refund_name)
        border_color = "#2659ab" if warning is None else "#fcba03"

        # Warning frame
        self.warning_frame = ctk.CTkFrame(self.content_frame, border_width=2, border_color=border_color)
        self.toggle_warning_frame(refund_data[DBRefundsColumns.REFUND_NAME.value])
        ctk.CTkLabel(self.warning_frame, text=warning if warning is not None else "", font=("Arial", 16)).pack(padx=30,
                                                                                                               pady=(
                                                                                                               20, 20),
                                                                                                               side="left")
        self.remove_warning_btn = ctk.CTkButton(self.warning_frame, text="OK, è tutto in ordine",
                                                command=lambda: self.remove_warning(refund_name))
        self.remove_warning_btn.pack(padx=30, pady=(20, 20), side="right")

        # Creazione frame principale
        self.info_frame = ctk.CTkFrame(self.content_frame, border_width=2, border_color=border_color)
        self.info_frame.pack(fill="both", expand=True, pady=(5, 10), padx=(5, 25))

        # Configurazione griglia a 2 colonne
        self.info_frame.grid_columnconfigure(0, weight=1, uniform="col")
        self.info_frame.grid_columnconfigure(1, weight=1, uniform="col")

        # Sezioni organizzate per colonne
        sections_order = [
            "Dati Generali",
            "Dati Fiscali",
            "Collegamenti",
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
        for field, config in self.entry_fields_refunds.items():
            section = sections[config["section"]]
            frame = section["frame"]
            row = section["row"]

            # Creazione label
            lbl = ctk.CTkLabel(frame, text=config["label"] + ":")
            self.refund_info_labels[field] = lbl
            lbl.grid(row=row, column=0, sticky="w", padx=(15, 5), pady=(5, 5))

            # Creazione widget
            if config["type"] == ctk.CTkLabel:
                value = str(refund_data.get(field, ""))
                widget = config["type"](frame, text=value)
                widget.grid(row=row, column=1, sticky="w", padx=(5, 15), pady=(5, 5))
            else:
                if config["type"] == ctk.CTkOptionMenu:
                    widget = config["type"](frame, values=config.get("values", []))

                    # Imposta il valore corrente per il cliente
                    if field == self.nome_cliente_string:
                        client_id = refund_data.get(DBRefundsColumns.CLIENT_ID.value)
                        client = self.client_controller.retrieve_client_map_by_id(client_id)
                        client_name = client[DBClientsColumns.NAME.value] if client else ""
                        widget.set(client_name)

                    # Imposta il valore corrente per il conto
                    elif field == self.nome_conto_string:
                        account_id = refund_data.get(DBRefundsColumns.CONTO_ID.value)
                        account = self.account_controller.retrieve_account_map_by_id(account_id)
                        account_name = account[DBAccountsColumns.NAME.value] if account else ""
                        widget.set(account_name)

                    else:
                        widget.set(refund_data.get(field, config.get("values", [""])[0]))

                elif config["type"] == Calendar:
                    widget = config["type"](frame, date_pattern=ViewUtils.date_pattern)
                    value = refund_data.get(field, "")
                    widget.selection_set(str(value)) if value else widget.selection_set(datetime.today())
                else:
                    widget = config["type"](frame)
                    value = str(refund_data.get(field, ""))
                    widget.insert(0, value)

                widget.grid(row=row, column=1, sticky="ew", padx=(5, 15), pady=(5, 5))

            self.refund_info_widgets[field] = widget

            # Gestione validazione
            if field in validation_rules:
                validation_func, error_message = validation_rules[field]

                error_lbl = ctk.CTkLabel(frame, text="", text_color="#e8e5dc")
                error_lbl.grid(row=row + 1, column=1, sticky="w", padx=5, pady=(0, 10))
                self.error_labels_refunds[field] = error_lbl

                widget.bind("<FocusOut>",
                            lambda e, w=widget, vl=validation_func, el=error_lbl, em=error_message:
                            ViewUtils.validate_entry(w, vl, el, em))

                section["row"] += 2
            else:
                section["row"] += 1

        # Frame per i bottoni
        buttons_frame = ctk.CTkFrame(self.info_frame, fg_color="transparent")
        buttons_frame.grid(row=2, column=0, columnspan=2, pady=(5, 15), padx=20, sticky="NSWE")

        # Bottone Salva
        self.save_info_btn = ctk.CTkButton(buttons_frame, text="Salva Rimborso", command=self.save_refund_mod)
        self.save_info_btn.pack(padx=(400, 10), pady=(20, 20), side="left")

        # Bottone Elimina
        self.delete_btn = ctk.CTkButton(buttons_frame, text="Elimina Rimborso",
                                        fg_color="#8B0000", hover_color="#A52A2A",
                                        command=self.delete_refund)
        self.delete_btn.pack(padx=10, pady=(20, 20), side="right", anchor="e")

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
            elif isinstance(w, Calendar):
                w.configure(state=state)
            # se è un Frame/container, scendi ricorsivamente
            elif isinstance(w, (ctk.CTkFrame, ctk.CTkScrollableFrame, ctk.CTkToplevel)):
                self.toggle_edit(w)

    def toggle_warning_frame(self, refund_name):
        warning = self.parent.cards_warnings.get(refund_name)
        if warning is not None:
            self.warning_frame.pack(fill="both", expand=True, pady=10, padx=(5, 25))
        else:
            self.warning_frame.pack_forget()

    def remove_warning(self, refund_name):
        self.save_refund_mod()
        self.parent.cards_warnings.pop(refund_name)
        self.info_frame.configure(border_color="#2659ab")
        #retrieve the card
        card = self.parent.refund_card_list[refund_name]
        ViewUtils.toggle_warning_on_card(card, self.parent.cards_warnings)
        self.toggle_warning_frame(refund_name)
        self.remove_warning_btn.configure(state=ctk.DISABLED)

    def save_refund_mod(self):
        nome_conto = self.refund_info_widgets[self.nome_conto_string].get()
        conto = self.account_controller.retrieve_account_map_by_name(nome_conto)
        id_conto = conto[DBAccountsColumns.ID.value] if conto else None

        nome_cliente = self.refund_info_widgets[self.nome_cliente_string].get()
        cliente = self.client_controller.retrieve_client_map_by_name(nome_cliente)
        id_cliente = cliente[DBClientsColumns.ID.value]

        refund_data = {
            DBRefundsColumns.REFUND_NAME.value: self.refund_info_widgets[
                DBRefundsColumns.REFUND_NAME.value].get().strip(),
            DBRefundsColumns.REFUND_DATE.value: self.refund_info_widgets[
                DBRefundsColumns.REFUND_DATE.value].get_date(),
            DBRefundsColumns.REFUND_AMOUNT.value: self.refund_info_widgets[
                DBRefundsColumns.REFUND_AMOUNT.value].get().strip(),
            DBRefundsColumns.CLIENT_ID.value: id_cliente,
            DBRefundsColumns.CONTO_ID.value: id_conto
        }

        # Chiamata al controller per salvare i dati
        success, message = self.refund_controller.update_refund(self.current_refund_id, refund_data)
        if success:
            print(
                f"Rimborso {self.refund_controller.retrieve_refund_map_by_id(self.current_refund_id)[DBRefundsColumns.REFUND_NAME.value]} salvato con successo")
            ViewUtils.show_confirm_popup_2(self.content_frame, "SALVATAGGIO COMPLETATO", message)
            self.switch_modify.deselect()
            self.toggle_edit(self.content_frame)

        else:
            # Mostra il messaggio d'errore
            print(message)
            ViewUtils.show_error_popup(self.content_frame, "ERRORE", message)

    def delete_refund(self):
        confirmation = ViewUtils.ask_confirmation_popup(self.content_frame,
                                                        "Stai per eliminare questo rimborso.\nDesideri continuare ?",
                                                        "ELIMINAZIONE Rimborso")
        if confirmation:
            success, message = self.refund_controller.delete_refund(self.current_refund_id)
            if success:
                ViewUtils.show_confirm_popup_2(self.content_frame, "RIMBORSO ELIMINATO CON SUCCESSO", message)
                print(f"Rimborso {self.refund[DBRefundsColumns.REFUND_NAME.value]} eliminato correttamente")
            else:
                # Mostra il messaggio d'errore
                print(message)
                ViewUtils.show_error_popup(self.content_frame, "ERRORE", message)

    def _clear_content(self):
        """Distrugge tutti i widget dinamici"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def _cleanup_and_go_back(self):
        """Pulizia completa prima di tornare indietro"""
        self._clear_content()
        self.pack_forget()
        self.back_callback()


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

    def __init__(self, db_model, refunds_controller, client_controller, account_controller, update_controller, tab_view, analyzer, event_bus):
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

        # Aggiungi evento alla barra di ricerca
        self.search_bar.bind("<KeyRelease>", self.filter_cards)

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

        self.table_headers = ["NOME", "CLIENTE", "TOTALE", "DATA", "CONTO\nCORRENTE"]

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

        # aggiungo una tab per ogni fattura presente nel database
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

        for refund in refunds_map_list:
            if refund:
                refund_id = refund[DBRefundsColumns.ID.value]
                refund_name = refund[DBRefundsColumns.REFUND_NAME.value]
                amount = refund[DBRefundsColumns.REFUND_AMOUNT.value]
                refund_date = refund[DBRefundsColumns.REFUND_DATE.value]
                cliente_id = refund[DBRefundsColumns.CLIENT_ID.value]
                client = self.client_controller.retrieve_client_map_by_id(cliente_id)
                client_name = client[DBClientsColumns.NAME.value]
                conto = self.account_controller.retrieve_account_map_by_id(refund[DBRefundsColumns.CONTO_ID.value])
                nome_conto = conto[DBAccountsColumns.NAME.value] if conto else "conto non trovato"

                # warnings attachments

                self.add_refund_card(refund_id, refund_name, amount, refund_date, client_name, nome_conto)

        # warnings launch
        for card in self.refund_card_list.values():
            ViewUtils.toggle_warning_on_card(card, self.cards_warnings)

    def show_main_view(self):
        """Torna alla vista principale"""
        self.refund_detail_view.pack_forget()
        self.main_container.pack(fill='both', expand=True)

    def open_refund_detail_tab(self, refund_id):
        """Mostra la vista dettaglio del rimborso"""
        self.main_container.pack_forget()
        self.refund_detail_view.pack(fill='both', expand=True)
        self.refund_detail_view.create_detail_tab(refund_id)  # Ricrea i contenuti ogni volta

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
            command=lambda rid=refund_id: self.open_modify_payment(rid)
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




class RefundDetailView(ctk.CTkFrame):
    def __init__(self, parent, back_callback, client_controller, account_controller, refund_controller, db_model, analyzer, event_bus):
        super().__init__(parent)
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
            text="Elenco Clienti",
            command=self._cleanup_and_go_back
        )
        self.title_label = ctk.CTkLabel(self.head_frame, font=("Arial", 22, "bold"))

        self.user_info_widgets: dict[str, ctk.CTkEntry | ctk.CTkOptionMenu] = {}

        self.nome_cliente_string = "CLIENTE ASSOCIATo"
        self.nome_conto_string = "CONTO"


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

        self.wrapper_frame = ctk.CTkFrame(self.content_frame, fg_color="#333333")
        self.wrapper_frame.pack(padx=25, pady=(90, 0), fill="both", expand=True)
        #self.wrapper_frame2 = ctk.CTkFrame(self.content_frame, fg_color="#333333")
        #self.wrapper_frame2.pack(padx=25, pady=(90, 90), fill="both", expand=True)


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
            # se è un Frame/container, scendi ricorsivamente
            elif isinstance(w, (ctk.CTkFrame, ctk.CTkScrollableFrame, ctk.CTkToplevel)):
                self.toggle_edit(w)

    def _clear_content(self):
        """Distrugge tutti i widget dinamici"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def _cleanup_and_go_back(self):
        """Pulizia completa prima di tornare indietro"""
        self._clear_content()
        self.pack_forget()
        self.back_callback()


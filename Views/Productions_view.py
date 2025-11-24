import customtkinter as ctk
import tkinter as tk
from tkcalendar import Calendar
from Views.View_utils import ViewUtils, FilterableComboBox
from Controllers import ProductionController, PaymentsController, InvoiceController, UserController, ControllerUtils
from Model import DBProductionsColumns, DBUsersColumns, DBClientsColumns, DBPaymentsColumns, DBInvoicesColumns
from datetime import datetime
import re
from enum import Enum

class ProductionsView(ctk.CTkFrame):

    def __init__(self, db_model, production_controller, payment_controller,
                 invoice_controller, user_controller, client_controller,
                 catalogo_elenchi, config_manager, tabview,
                 event_bus, update_controller, initial_production_id=None):
        super().__init__(tabview.tab("Produzioni"))

        self.db_model = db_model
        self.production_controller = production_controller
        self.invoice_controller = invoice_controller
        self.user_controller = user_controller
        self.client_controller = client_controller
        self.payment_controller = payment_controller
        self.catalogo_elenchi = catalogo_elenchi
        self.config_manager = config_manager
        self.tabview = tabview
        self.tab = self.tabview.tab("Produzioni")
        self.event_bus = event_bus
        self.update_controller = update_controller

        #self.event_bus.subscribe(ViewUtils.EventBusKeys.SHOW_PRODUCTION_DETAIL, self.handle_show_production_detail)

        self.global_infos = {}
        self.amount_aggregate_labels = {}
        self.aggregate_UOM = {
            ProductionController.ProductionsAggregateData.NUMERO_PRODUZIONI.value : "",
            ProductionController.ProductionsAggregateData.NUMERO_PRODUZIONI_ATTIVE.value : "",
            ProductionController.ProductionsAggregateData.NUMERO_PRODUZIONI_CHIUSE.value : "",
            ProductionController.ProductionsAggregateData.MEDIA_ORE_PRODUZIONE.value : "h",
            ProductionController.ProductionsAggregateData.MEDIA_PREZZO_ORARIO.value : "€/h"
        }
        self.production_labels = {}
        self.production_widgets = {}
        self.production_card_labels_status = {}
        self.production_card_list = {}

        # Container principale
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.detail_container = ctk.CTkFrame(self, fg_color="transparent")

        self.production_detail_view = ProductionDetailView(
            parent=self,
            invoice_controller=self.invoice_controller,
            back_callback=self.show_main_view,
            client_controller=self.client_controller,
            production_controller=self.production_controller,
            catalogo_elenchi=self.catalogo_elenchi,
            config_manager=self.config_manager,
            db_model=db_model,
            update_controller=self.update_controller,
            event_bus=self.event_bus
        )

        self.create_productions_tab()

        if initial_production_id is not None:
            self.after(100, lambda: self.open_production_detail_tab(initial_production_id))
        else:
            self.show_main_view()

    def show_main_view(self):
        """Torna alla vista principale"""
        self.production_detail_view.pack_forget()
        self.main_container.pack(fill='both', expand=True)

    def handle_show_production_detail(self, production_id):
        self.tabview.set("Produzioni")  # Cambia tab
        self.after(150, lambda: self.open_production_detail_tab(production_id))

    def open_production_detail_tab(self, production_id):
        """Mostra la vista dettaglio produzione con controlli di sicurezza"""
        try:
            # Verifica che i widget esistano
            if hasattr(self, 'main_container') and self.main_container.winfo_exists():
                self.main_container.pack_forget()

            # Se production_detail_view non esiste, crealo
            if not hasattr(self, 'production_detail_view') or not self.production_detail_view.winfo_exists():
                self.production_detail_view = ProductionDetailView(
                    parent=self,
                    invoice_controller=self.invoice_controller,
                    back_callback=self.show_main_view,
                    client_controller=self.client_controller,
                    production_controller=self.production_controller,
                    catalogo_elenchi=self.catalogo_elenchi,
                    config_manager=self.config_manager,
                    db_model=self.db_model,
                    update_controller=self.update_controller,
                    event_bus=self.event_bus
                )

            # Mostra il dettaglio
            self.production_detail_view.pack(fill='both', expand=True)
            self.production_detail_view.create_detail_tab(production_id)  # Ricrea i contenuti ogni volta

        except Exception as e:
            print(f"Errore in open_production_detail_tab: {e}")
            # Fallback: mostra la vista principale
            self.show_main_view()

    def create_productions_tab(self):

        self.search_bar_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.search_bar_frame.pack(pady=(5, 10), fill="x", anchor="s")
        self.search_bar = ctk.CTkEntry(self.search_bar_frame)
        self.search_bar.pack(padx=(5, 35), anchor="s", side="right")
        self.search_bar_option_menu_values = {"NOME PROD.": "NOME PROD.", "NOME CLIENTE": "NOME CLIENTE",
                                              "TIPO PRODUZIONE": "TIPO PRODUZIONE", "TIPO OUTPUT": "TIPO OUTPUT", "STATO": "STATO"}
        self.search_bar_optionMenu = ctk.CTkOptionMenu(self.search_bar_frame,
                                                       values=list(self.search_bar_option_menu_values.values()))
        self.search_bar_optionMenu.pack(padx=5, anchor="s", side="right")
        self.search_bar_label = ctk.CTkLabel(self.search_bar_frame, text="Filtra per ", font=("Arial", 14))
        self.search_bar_label.pack(padx=5, anchor="s", side="right")


        self.order_bar_option_menu_values = {"DATA CREAZIONE": "DATA CREAZIONE",
                                             "ULTIMA MODIFICA": "ULTIMA MODIFICA",
                                              "TOTALE PREVENTIVO": "TOTALE PREVENTIVO"}
        self.order_bar_option_menu_values_types = {"DECRESCENTE": "DECRESCENTE", "CRESCENTE": "CRESCENTE"}
        self.order_bar_optionMenu_types = ctk.CTkOptionMenu(self.search_bar_frame,
                                                       values=list(self.order_bar_option_menu_values_types.values()))
        self.order_bar_optionMenu_types.pack(padx=(5, 50), anchor="s", side="right")
        self.order_bar_optionMenu = ctk.CTkOptionMenu(self.search_bar_frame,
                                                       values=list(self.order_bar_option_menu_values.values()))
        self.order_bar_optionMenu.pack(padx=5, anchor="s", side="right")
        self.order_bar_label = ctk.CTkLabel(self.search_bar_frame, text="Ordina per ", font=("Arial", 14))
        self.order_bar_label.pack(padx=5, anchor="s", side="right")

        self.show_last_cards_optionMenu_values = {
            "30 GG": "30 GG",
            "60 GG": "60 GG",
            "90 GG": "90 GG",
            "365 GG": "365 GG"
        }
        self.show_last_cards_optionMenu = ctk.CTkOptionMenu(self.search_bar_frame,
                                                       values=list(self.show_last_cards_optionMenu_values.values()))
        self.show_last_cards_optionMenu.pack(padx=(5, 50), anchor="s", side="right")
        self.show_last_cards_label = ctk.CTkLabel(self.search_bar_frame, text="Mostra gli ultimi ", font=("Arial", 14))
        self.show_last_cards_label.pack(padx=5, anchor="s", side="right")

        # Aggiungi evento alla barra di ricerca
        self.search_bar.bind("<KeyRelease>", self.filter_cards)

        self.order_bar_optionMenu.configure(command=lambda _: self.sort_cards())
        self.order_bar_optionMenu_types.configure(command=lambda _: self.sort_cards())
        self.show_last_cards_optionMenu.configure(command=lambda _: self.show_last_cards())

        self.populate_global_infos()

        for (key, info) in self.global_infos.items():
            card = ctk.CTkFrame(self.search_bar_frame, fg_color="#333333")

            if key == ProductionController.ProductionsAggregateData.NUMERO_PRODUZIONI.value or \
                key == ProductionController.ProductionsAggregateData.NUMERO_PRODUZIONI_ATTIVE.value or \
                key == ProductionController.ProductionsAggregateData.NUMERO_PRODUZIONI_CHIUSE.value:
                    global_info_unità_di_misura = ""
            elif key == ProductionController.ProductionsAggregateData.MEDIA_ORE_PRODUZIONE.value:
                global_info_unità_di_misura = "h"
            elif key == ProductionController.ProductionsAggregateData.MEDIA_PREZZO_ORARIO.value:
                global_info_unità_di_misura = "€/h"

            title = ctk.CTkLabel(card, text=f"{key}", font=("Arial", 12), bg_color="#1F6AA5")
            amount = ctk.CTkLabel(card, text=f"{info} {global_info_unità_di_misura}", font=("Arial", 16))

            card.pack(side="left", anchor="w", padx=10, pady=(10, 5))
            title.pack(anchor="n", padx=10, pady=(10, 5), ipadx=7, ipady=5)
            amount.pack(anchor="s", padx=10, pady=5)

            #salvo i dati che potrebbero avere bisogno di configure successivamente
            self.amount_aggregate_labels[f"{key}"] = amount

        self.productions_table_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.productions_table_frame.pack(pady=(20, 0), padx=(10, 15), fill="x", anchor="n")

        self.table_headers = ["NOME", "CLIENTE", ViewUtils.split_string_by_length("TIPOLOGIA DI PRODUZIONE", 12),
                              ViewUtils.split_string_by_length("TIPOLOGIA DI OUTPUT", 10), "STATO",
                              ViewUtils.split_string_by_length("DATA DI CONSEGNA", 8),
                              ViewUtils.split_string_by_length("TOTALE PREVENTIVO", 8),
                              ViewUtils.split_string_by_length("DURATA PRODUZIONE", 8),
                              ViewUtils.split_string_by_length("PREZZO ORARIO", 8)
                              ]

        for i, header in enumerate(self.table_headers):
            # crea il container
            column = ctk.CTkFrame(self.productions_table_frame, fg_color="#333333")
            column.grid(row=0, column=i, sticky="nsew", padx=(0, 5), pady=5)

            # imposta peso e uniformità: tutte le colonne "col" si dividono equamente
            self.productions_table_frame.grid_columnconfigure(i, weight=1, uniform="col")

            # la label riempie il suo container
            label = ctk.CTkLabel(column,
                                 text=header,
                                 font=("Arial", 14))
            label.pack(fill="both", expand=True, padx=5, pady=15)

        # Creazione del frame delle cards
        self.productions_cards_frame = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")
        self.productions_cards_frame.pack(padx=0, pady=10, fill="both", expand=True)

        self.add_production_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.add_production_frame.pack(padx=0, pady=(5, 20), fill="x")

        self.save_button = ctk.CTkButton(self.add_production_frame, text="Aggiungi una produzione",
                                         command=self.open_add_production_window)
        self.save_button.pack()

        self.show_last_cards()

        # Sistema per tracciare gli after()
        self._after_ids = set()
        self._orig_after = self.after
        self.after = self._track_after

    def show_last_cards(self):
        """Mostra solo le fatture degli ultimi giorni selezionati dall'utente"""
        # Ottieni il valore selezionato dal menu
        selected = self.show_last_cards_optionMenu.get()

        # Mappa la selezione al numero di giorni
        days_map = {
            "30 GG": 30,
            "60 GG": 60,
            "90 GG": 90,
            "365 GG": 365
        }
        days = days_map.get(selected, 30)

        # Calcola la data limite (oggi - giorni)
        from datetime import datetime, timedelta
        limit_date = datetime.now() - timedelta(days=days)

        # Recupera tutte le fatture dell'anno corrente
        all_productions = self.production_controller.retrieve_productions_map_list(True)

        # Filtra le fatture: solo quelle con data di emissione >= limit_date
        filtered_productions = []
        for production in all_productions:
            date_str = production.get(DBProductionsColumns.CREATED_AT.value)
            if date_str:
                try:
                    # Prova a parsare la data in formato yyyy-mm-dd o yyyy-mm-dd hh:mm:ss
                    try:
                        production_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        production_date = datetime.strptime(date_str, "%Y-%m-%d")

                    if production_date >= limit_date:
                        filtered_productions.append(production)
                except Exception as e:
                    print(f"Errore nel parsare la data {date_str}: {e}")

        # Svuota le cards attuali
        for card in self.production_card_list.values():
            card.destroy()
        self.production_card_list.clear()

        # Ricarica le cards con le fatture filtrate
        self.load_productions_chunked(filtered_productions)

        self.sort_cards()


    def populate_global_infos(self):
        #self.global_infos[f"{ProductionController.ProductionsAggregateData.NUMERO_PRODUZIONI.value}"] = self.production_controller.count_productions(True)
        self.global_infos[f"{ProductionController.ProductionsAggregateData.NUMERO_PRODUZIONI_ATTIVE.value}"] = self.production_controller.count_active_productions(True)
        self.global_infos[f"{ProductionController.ProductionsAggregateData.NUMERO_PRODUZIONI_CHIUSE.value}"] = self.production_controller.count_closed_productions(True)
        self.global_infos[f"{ProductionController.ProductionsAggregateData.MEDIA_ORE_PRODUZIONE.value}"] = round(self.production_controller.mean_hours_for_production(True), 2)
        self.global_infos[f"{ProductionController.ProductionsAggregateData.MEDIA_PREZZO_ORARIO.value}"] = round(self.production_controller.mean_prezzo_orario(True), 2)

    def open_add_production_window(self):
        """Apre una finestra per aggiungere una nuova produzione"""

        self.add_production_window = ctk.CTkToplevel(self)
        self.add_production_window.title("Aggiungi Nuova Produzione")

        # Assicurati che la finestra rimanga sopra
        self.add_production_window.lift()  # Porta la finestra sopra quella principale
        self.add_production_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

        self.add_production_window.geometry("550x700")

        self.production_window_scrollableFrame = ctk.CTkScrollableFrame(self.add_production_window)
        self.production_window_scrollableFrame.pack(fill="both", expand=True)

        self.nome_utente_string = "NOME UTENTE"
        self.nome_cliente_string = "NOME CLIENTE"
        self.nome_produzione_string = "NOME PRODUZIONE"

        self.entry_fields = {
            self.nome_cliente_string : FilterableComboBox,
            DBProductionsColumns.NAME.value: ctk.CTkEntry,
            DBProductionsColumns.HOURS.value : ctk.CTkEntry,
            DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value: ctk.CTkOptionMenu,
            DBProductionsColumns.TIPOLOGIA_OUTPUT.value: ctk.CTkOptionMenu,
            DBProductionsColumns.STATO.value: ctk.CTkOptionMenu,
            DBProductionsColumns.END_DATE.value: Calendar,
            DBProductionsColumns.TOTALE_PREVENTIVO.value: ctk.CTkEntry
        }

        self.error_fields = {
            DBProductionsColumns.NAME.value : ctk.CTkLabel,
            DBProductionsColumns.HOURS.value : ctk.CTkLabel,
            DBProductionsColumns.TOTALE_PREVENTIVO.value: ctk.CTkLabel
        }

        self.error_labels = {}


        #Creo i labels e i widgets
        for i, (label_text, widget_class) in enumerate(self.entry_fields.items()):
            # Etichetta
            label = ctk.CTkLabel(self.production_window_scrollableFrame, text=label_text)
            #disegno i labels
            if i == 0:
                label.pack(pady=5)
            else:
                label.pack(pady=(35, 0))

            self.production_labels[label_text] = label

            #creo i widgets
            if label_text == self.nome_cliente_string:
                widget = widget_class(parent=self.production_window_scrollableFrame, placeholder="Cerca", autofill=True,
                                      values=[f"{item[DBClientsColumns.NAME.value]}" for item in self.client_controller.retrieve_clients_map_list()],
                                      command=lambda selected_value: self.auto_compile_name_entry(selected_value))
            elif label_text == DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value:
                widget = widget_class(self.production_window_scrollableFrame,
                                      values=[value for key, value in self.catalogo_elenchi["production_types"]],
                                      command = lambda selected_value : self.open_add_prod_type(selected_value))
            elif label_text == DBProductionsColumns.TIPOLOGIA_OUTPUT.value:
                widget = widget_class(self.production_window_scrollableFrame,
                                      values=[value for key, value in self.catalogo_elenchi["production_output_types"]],
                                      command = lambda selected_value : self.open_add_prod_out_type(selected_value))
            elif label_text == DBProductionsColumns.STATO.value:
                widget = widget_class(self.production_window_scrollableFrame,
                                      values=[item.value for item in ProductionController.Stato])
            elif label_text == DBProductionsColumns.END_DATE.value:
                widget = widget_class(self.production_window_scrollableFrame, date_pattern=ViewUtils.date_pattern)
            elif label_text == DBProductionsColumns.NAME.value:
                self.name_frame = ctk.CTkFrame(self.production_window_scrollableFrame)
                self.name_frame.pack(pady=0, padx=0, fill="x", expand=True)
                first_part_name_label = ctk.CTkLabel(self.name_frame, text="bandur")
                first_part_name_label.pack(side=tk.LEFT, pady=5, padx=(10, 0))
                widget = widget_class(self.name_frame)
            else:
                widget = widget_class(self.production_window_scrollableFrame)

            widget.pack(pady=5, padx=(0, 10) if label_text == DBProductionsColumns.NAME.value else 10, fill="x", expand=True)

            self.production_widgets[label_text] = widget

            if self.error_fields.get(label_text) is not None:
                error_label = ctk.CTkLabel(self.production_window_scrollableFrame, text="")
                error_label.pack(pady=(0,15))
                self.error_labels[label_text] = error_label

        button_frame = ctk.CTkFrame(self.production_window_scrollableFrame, bg_color="transparent")
        button_frame.pack()

        # Bottone per salvare
        self.save_button = ctk.CTkButton(
            button_frame,
            text="Salva Produzione",
            command=self.save_production_data
        )
        self.save_button.pack(pady=(35, 15))

        self.delete_button = ctk.CTkButton(
            button_frame,
            text="Elimina Produzione",
            fg_color="red",
            command=self.delete_production
        )
        #self.delete_button.pack_forget()

        self.name_frame.winfo_children()[0].configure(text=f"{self.client_controller.retrieve_clients_map_list()[0][DBClientsColumns.NAME.value]} - ")
        #self.production_widgets[DBProductionsColumns.NAME.value].insert(0, f"{self.client_controller.clients_list[0][DBClientsColumns.NAME.value]}-")

        # Aggiungi validazione agli eventi di perdita del focus
        self.production_widgets[DBProductionsColumns.NAME.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.production_widgets[DBProductionsColumns.NAME.value],
            lambda val: val.strip() != "",
            self.error_labels[DBProductionsColumns.NAME.value],
            "Il campo non può essere vuoto."
        ))

        self.production_widgets[DBProductionsColumns.HOURS.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.production_widgets[DBProductionsColumns.HOURS.value],
            lambda val: val.strip() != "" and val.isdigit(),
            self.error_labels[DBProductionsColumns.HOURS.value],
            "Il campo deve contenere un numero intero."
        ))

        self.production_widgets[DBProductionsColumns.TOTALE_PREVENTIVO.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.production_widgets[DBProductionsColumns.TOTALE_PREVENTIVO.value],
            lambda val: re.fullmatch(r"^\d+(\.\d{2})?$", val.strip()) is not None,
            self.error_labels[DBProductionsColumns.TOTALE_PREVENTIVO.value],
            "Inserimento non valido: inserire un numero monetario con due cifre decimali (es. 123.45)"
        ))

    def filter_cards(self, event):
        """Filtra le card in base al testo della barra di ricerca e al tipo di filtro scelto."""
        search_text = self.search_bar.get().lower()
        search_type = self.search_bar_optionMenu.get()

        # Mappatura: ogni chiave associa una tupla (indice, classe_attesa) del widget da cui prelevare il testo
        filter_mapping = {
            "NOME PROD.": (0, ctk.CTkButton),  # Bottone
            "NOME CLIENTE": (1, ctk.CTkLabel),
            "TIPO PRODUZIONE": (2, ctk.CTkLabel),
            "TIPO OUTPUT": (3, ctk.CTkLabel),
            "STATO": (4, ctk.CTkOptionMenu),
        }

        mapping = filter_mapping.get(search_type)

        # Rimuovo tutte le card dal container per avere un layout pulito
        for card in self.production_card_list.values():
            card.pack_forget()

        # Se il tipo di ricerca non è riconosciuto, riposiziono tutte le card nell'ordine originale
        if mapping is None:
            for card in self.production_card_list.values():
                card.pack(pady=10, padx=10, fill="x", expand=True)
            return

        idx, expected_class = mapping

        # Itera sulle card nell’ordine originale
        for key, card in self.production_card_list.items():
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
        """Ordina le cards in base ai criteri selezionati nei menu di ordinamento."""

        # Funzioni di supporto per la conversione dei valori
        def _convert_to_currency(currency_str):
            """Converte una stringa di valuta in un numero float per l'ordinamento."""
            # Rimuovi il simbolo dell'euro, gli spazi, e gestisci separatori
            cleaned = currency_str.replace('€', '').replace(' ', '').replace('.', '').replace(',', '.')
            return float(cleaned)

        def _convert_to_datetime(date_str):
            """Converte una stringa in formato yyyy-mm-dd hh:mm:ss in un oggetto datetime per l'ordinamento."""
            from datetime import datetime
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")

        # Ottieni i criteri di ordinamento
        sort_by = self.order_bar_optionMenu.get()
        sort_order = self.order_bar_optionMenu_types.get()

        # Mappatura: ogni criterio associa una tupla (indice, funzione_di_conversione, tipo_di_accesso, colonna_db)
        sort_mapping = {
            "TOTALE PREVENTIVO": (6, _convert_to_currency, "direct", None),
            "DATA CREAZIONE": (0, _convert_to_datetime, "database", DBProductionsColumns.CREATED_AT.value),
            "ULTIMA MODIFICA": (0, _convert_to_datetime, "database", DBProductionsColumns.UPDATED_AT.value)
        }

        mapping = sort_mapping.get(sort_by)

        # Se il tipo di ordinamento non è riconosciuto, non fare nulla
        if mapping is None:
            return

        idx, converter, access_type, db_column = mapping
        reverse = (sort_order == "DECRESCENTE")

        # Raccogli tutte le cards e i loro valori di ordinamento
        cards_with_values = []
        for key, card in self.production_card_list.items():
            children = card.winfo_children()
            sort_value = ""

            if access_type == "direct":
                # Accesso diretto al valore nella card
                if len(children) > idx:
                    sort_value = children[idx].cget("text")
            elif access_type == "database":
                # Accesso al valore tramite database
                if len(children) > 0:  # Assicurati che ci sia almeno un child
                    production_name = children[0].cget("text")  # Nome produzione dal primo child
                    production_map = self.production_controller.retrieve_production_map_by_name(production_name)
                    if production_map and db_column:
                        sort_value = production_map.get(db_column, "")

            # Converti il valore nel tipo appropriato
            try:
                converted_value = converter(sort_value) if sort_value else None
            except (ValueError, TypeError):
                converted_value = None  # Gestisci i valori non convertibili

            cards_with_values.append((key, card, converted_value))

        # Ordina le cards in base al valore convertito
        # Gestisci i valori None posizionandoli alla fine in entrambi i casi
        cards_with_values.sort(
            key=lambda x: (x[2] is not None, x[2]) if x[2] is not None else (False, None),
            reverse=reverse
        )

        # Nascondi temporaneamente tutte le cards
        for card in self.production_card_list.values():
            card.pack_forget()

        # Riposiziona le cards nell'ordine ordinato
        for _, card, _ in cards_with_values:
            card.pack(pady=10, padx=10, fill="x", expand=True)

    def load_productions_chunked(self, productions_list):

        # Ordina la lista in ordine decrescente (dal più recente al più vecchio)
        productions_list.sort(
            key=lambda x: datetime.strptime(
                x[DBProductionsColumns.UPDATED_AT.value],
                "%Y-%m-%d %H:%M:%S"
            ) if " " in x[DBProductionsColumns.UPDATED_AT.value] else datetime.strptime(
                x[DBProductionsColumns.UPDATED_AT.value],
                "%Y-%m-%d"
            ),
            reverse=True
        )

        extractor = ViewUtils.create_extractor_for_productions(
            self.production_controller,
            self.client_controller
        )

        ViewUtils.process_items_in_chunks(
            widget=self,
            items_list=productions_list,
            add_card_callback=self.add_production_card,
            extract_args_callback=extractor,
            cards_frame=self.productions_cards_frame

        )

    def add_production_card(self, production_id, production_name, client_name, tipologia_produzione, tipologia_output, produzione_stato, data_di_consegna, totale_preventivo, durata_produzione, prezzo_orario):
        """
        Aggiunge una singola card con i dati forniti alla scrollable frame,
        disponendo i widget in colonne di ugual larghezza.
        """
        # Creazione della card
        card = ctk.CTkFrame(self.productions_cards_frame, fg_color="dimgray")
        card.pack(pady=10, padx=8, fill="x", expand=True)

        # Dati da visualizzare: escludiamo production_name perché sarà un Button in colonna 0
        data = [
            client_name,
            tipologia_produzione,
            tipologia_output,
            produzione_stato,
            ViewUtils.invert_data_string(data_di_consegna),
            round(totale_preventivo, 2),
            durata_produzione,
            round(prezzo_orario, 2),
        ]
        units = ["", "", "", "", "", "€", "h", "€/h"]

        n_cols = 1 + len(data)  # 1 bottone + 8 campi

        # Configuro il grid della card: 1 riga, n_cols colonne uniformi
        for c in range(n_cols):
            card.grid_columnconfigure(c, weight=1, uniform="prodcol")
        card.grid_rowconfigure(0, weight=1)

        # 0) Bottone con il nome della produzione
        btn = ctk.CTkButton(
            card,
            text=production_name,
            command=lambda pid=production_id: self.open_production_detail_tab(pid)
        )
        btn.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        # 1..8) Le altre colonne
        for idx, val in enumerate(data, start=1):
            if idx == 4:
                # Colonna "stato": OptionMenu con selezione automatica al cambiamento
                opt = ctk.CTkOptionMenu(
                    card,
                    values=[s.value for s in ProductionController.Stato],
                    command=lambda sel, pid=production_id: self.auto_save_production_status(pid, sel)
                )
                opt.set(produzione_stato)
                opt.grid(row=0, column=idx, sticky="nsew", padx=5, pady=10)
                # salvo l'OptionMenu per poterne cambiare aspetto in seguito
                self.production_card_labels_status[production_id] = opt
            else:
                text = f"{val} {units[idx - 1]}"
                lbl = ctk.CTkLabel(card, text=text, font=("Arial", 14))
                lbl.grid(row=0, column=idx, sticky="nsew", padx=5, pady=10)

        # Mantieni il riferimento alla card
        self.production_card_list[production_name] = card

    def save_production_data(self):
        production_data = {}

        # riempi il dizionario con i dati dei widgets primari
        for label_text, widget in self.production_widgets.items():
            if isinstance(widget, ctk.CTkEntry) or isinstance(widget, ctk.CTkOptionMenu):
                production_data[label_text] = widget.get().strip()
            elif isinstance(widget, Calendar):
                production_data[label_text] = widget.get_date()
            elif isinstance(widget, ctk.CTkTextbox):
                production_data[label_text] = widget.get("1.0", "end-1c").strip()  # Recupera il testo dal Textbox

        # chiamata al controller per salvare i dati
        success, message = self.production_controller.save_production(production_data)

        if success:
            #prendo l'ID della fattura appena creata
            production_map = self.production_controller.retrieve_last_production_insert_map()
            print(f"Fattura {production_data[DBProductionsColumns.NAME.value]} salvato con successo")

            client_name = self.client_controller.retrieve_client_map_by_id(production_map[DBProductionsColumns.CLIENT_ID.value])[DBClientsColumns.NAME.value]

            self.add_production_card(
                production_map[DBProductionsColumns.ID.value],
                production_map[DBProductionsColumns.NAME.value],
                client_name,
                production_map[DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value],
                production_map[DBProductionsColumns.TIPOLOGIA_OUTPUT.value],
                production_map[DBProductionsColumns.STATO.value],
                production_map[DBProductionsColumns.END_DATE.value],
                production_map[DBProductionsColumns.TOTALE_PREVENTIVO.value],
                production_map[DBProductionsColumns.HOURS.value],
                self.production_controller.calculate_production_cost_per_hour(production_map[DBProductionsColumns.ID.value])
            )

            self.clear_class_variable()
            self.add_production_window.destroy()
            self.update_global_infos()
        else:
            print(message)
            ViewUtils.show_error_popup(self.add_production_window, "ERRORE", message)

    def open_modify_production(self, production_id):

        #prendo i dati della produzione
        production = self.production_controller.retrieve_production_map_by_id(production_id, True)
        client_name = self.client_controller.retrieve_client_map_by_id(production[DBProductionsColumns.CLIENT_ID.value])[DBClientsColumns.NAME.value]

        production_name = production[DBProductionsColumns.NAME.value].split(" - ")
        production_name = production_name[1]


        self.open_add_production_window()

        #configuro la finestra
        #self.add_production_window.configure(title=f"Modifica i dati della produzione {production[DBProductionsColumns.NAME.value]}")
        self.add_production_window.title(f"Modifica i dati della produzione {production[DBProductionsColumns.NAME.value]}")
        self.save_button.configure(text="Salva Modifiche", command=self.modify_production_data)
        self.save_button.pack_forget()
        self.save_button.pack(side="left", pady=(35, 15), padx=10)
        self.delete_button.pack(pady=(35, 15), padx=10, side="right")
        self.production_widgets[self.nome_cliente_string].set(client_name)
        self.production_widgets[DBProductionsColumns.NAME.value].delete(0, tk.END)
        self.production_widgets[DBProductionsColumns.NAME.value].insert(0, production_name)
        self.name_frame.winfo_children()[0].configure(text=f"{client_name} - ")
        self.production_widgets[DBProductionsColumns.HOURS.value].delete(0, tk.END)
        self.production_widgets[DBProductionsColumns.HOURS.value].insert(0, int(production[DBProductionsColumns.HOURS.value]))
        self.production_widgets[DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value].set(production[DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value])
        self.production_widgets[DBProductionsColumns.TIPOLOGIA_OUTPUT.value].set(production[DBProductionsColumns.TIPOLOGIA_OUTPUT.value])
        self.production_widgets[DBProductionsColumns.STATO.value].set(production[DBProductionsColumns.STATO.value])
        self.production_widgets[DBProductionsColumns.END_DATE.value].selection_set(production[DBProductionsColumns.END_DATE.value])
        self.production_widgets[DBProductionsColumns.TOTALE_PREVENTIVO.value].delete(0, tk.END)
        self.production_widgets[DBProductionsColumns.TOTALE_PREVENTIVO.value].insert(0, f"{production[DBProductionsColumns.TOTALE_PREVENTIVO.value]:.2f}")

    def auto_compile_name_entry(self, selected_value):
        #self.production_widgets[DBProductionsColumns.NAME.value].delete(0, tk.END)
        #self.production_widgets[DBProductionsColumns.NAME.value].insert(0, f"{selected_value}-")
        self.name_frame.winfo_children()[0].configure(
            text=f"{selected_value} - ")

    def open_add_prod_type(self, selected_value):
        prod_type_dict = dict(self.catalogo_elenchi["production_types"])
        if selected_value == prod_type_dict.get("ADD_PROD_TYPE"):
            self.add_prod_type_window = ctk.CTkToplevel(self)
            self.add_prod_type_window.title("Aggiungi una nuova tipologia di produzione")

            # Assicurati che la finestra rimanga sopra
            self.add_prod_type_window.lift()  # Porta la finestra sopra quella principale
            self.add_prod_type_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

            self.add_prod_type_window.geometry("400x300")

            self.prod_type_window_Frame = ctk.CTkFrame(self.add_prod_type_window)
            self.prod_type_window_Frame.pack(fill="both", expand=True)

            ctk.CTkLabel(self.prod_type_window_Frame, text="Aggiungi una nuova tipologia di produzione\nsepara parole diverse solo tramite spazio").pack(padx=10, pady=(25, 0))

            self.add_prod_type_entry = ctk.CTkEntry(self.prod_type_window_Frame)
            self.add_prod_type_entry.pack(padx=10, pady=5, fill="x", expand=True)

            ctk.CTkButton(self.prod_type_window_Frame, text="Aggiungi tipologia produzione", command=self.save_prod_type).pack(padx=10, pady=(15, 10))

        else: return

    def save_prod_type(self):
        new_prod_type = self.add_prod_type_entry.get()
        new_prod_type_key = ControllerUtils.normalize_string_for_key(new_prod_type)
        try:
            self.config_manager.update_list_field("production_types", new_prod_type_key, new_prod_type, "update")
        except Exception as e:
            ViewUtils.show_error_popup(self.add_prod_type_window, "Errore", f"Impossibile aggiungere il nuovo settore: {str(e)}")
            return

        self.production_widgets[DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value].set(new_prod_type)
        self.add_prod_type_window.destroy()

    def open_add_prod_out_type(self, selected_value):
        prod_out_type_dict = dict(self.catalogo_elenchi["production_output_types"])
        if selected_value == prod_out_type_dict.get("ADD_PROD_OUT_TYPE"):
            self.add_prod_out_type_window = ctk.CTkToplevel(self)
            self.add_prod_out_type_window.title("Aggiungi una nuova tipologia di output")

            # Assicurati che la finestra rimanga sopra
            self.add_prod_out_type_window.lift()  # Porta la finestra sopra quella principale
            self.add_prod_out_type_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

            self.add_prod_out_type_window.geometry("400x300")

            self.prod_out_type_window_Frame = ctk.CTkFrame(self.add_prod_out_type_window)
            self.prod_out_type_window_Frame.pack(fill="both", expand=True)

            ctk.CTkLabel(self.prod_out_type_window_Frame, text="Aggiungi una nuova tipologia di output di produzione\nsepara parole diverse solo tramite spazio").pack(padx=10, pady=(25, 0))

            self.add_prod_out_type_entry = ctk.CTkEntry(self.prod_out_type_window_Frame)
            self.add_prod_out_type_entry.pack(padx=10, pady=5, fill="x", expand=True)

            ctk.CTkButton(self.prod_out_type_window_Frame, text="Aggiungi tipologia di output", command=self.save_prod_out_type).pack(padx=10, pady=(15, 10))

        else: return

    def save_prod_out_type(self):
        new_prod_out_type = self.add_prod_out_type_entry.get()
        new_prod_out_type_key = ControllerUtils.normalize_string_for_key(new_prod_out_type)
        try:
            self.config_manager.update_list_field("production_output_types", new_prod_out_type_key, new_prod_out_type, "update")
        except Exception as e:
            ViewUtils.show_error_popup(self.add_prod_out_type_window, "Errore", f"Impossibile aggiungere la nuova tipologia di output: {str(e)}")
            return

        self.production_widgets[DBProductionsColumns.TIPOLOGIA_OUTPUT.value].set(new_prod_out_type)
        self.add_prod_out_type_window.destroy()

    def auto_save_production_status(self, production_id, selected_value):
        production_data = {}
        production_data[DBProductionsColumns.STATO.value] = selected_value
        self.production_controller.update_specific_production_data(production_id, production_data)

        #aggiorno i dati aggregati, sia lita che interfaccia
        self.update_global_infos()

    def update_global_infos(self):
        self.populate_global_infos()
        # Per ogni chiave (identica in entrambi i dizionari) aggiorna il testo della label
        for key, label in self.amount_aggregate_labels.items():
            new_value = self.global_infos.get(key, "")
            label.configure(text=str(new_value) + " " + self.aggregate_UOM[key])

    def clear_class_variable(self):  #potrebbe non servire in quanto vengono inizializzate all'apertura della funzione
        self.production_widgets.clear()
        self.production_labels.clear()

    def delete_production(self):
        return

    # da implementare
    def modify_production_data(self):
        """
        salva le modifiche apportate alla produzione tramite i widgets dell'interfaccia
        :return:
        """

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




class ProductionDetailView(ctk.CTkFrame):
    def __init__(self, parent, back_callback, client_controller, invoice_controller, production_controller, update_controller, db_model, catalogo_elenchi, config_manager, event_bus):
        super().__init__(parent)
        self.client_controller = client_controller
        self.invoice_controller = invoice_controller
        self.production_controller = production_controller
        self.db_model = db_model
        self.back_callback = back_callback
        self.update_controller = update_controller
        self.event_bus = event_bus
        self.catalogo_elenchi = catalogo_elenchi
        self.config_manager = config_manager
        self.current_invoice_id = None
        self.parent = parent

        self.configure(fg_color="transparent")

        # Widgets persistenti (vanno creati una volta sola)
        self.head_frame = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.back_button = ctk.CTkButton(
            self.head_frame,
            text="Elenco Produzioni",
            command=self._cleanup_and_go_back
        )
        self.title_label = ctk.CTkLabel(self.head_frame, font=("Arial", 22, "bold"))

        self.payment_info_widgets: dict[str, ctk.CTkEntry | ctk.CTkOptionMenu] = {}


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
        self.production = self.production_controller.retrieve_production_map_by_id(production_id)

        # prendo il nome del cliente
        id_cliente = self.production[DBProductionsColumns.CLIENT_ID.value]
        cliente = self.client_controller.retrieve_client_map_by_id(id_cliente)
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
                "type": ctk.CTkOptionMenu,
                "label": "Cliente",
                "section": "Dati Generali",
                "values": [c[DBClientsColumns.NAME.value]
                           for c in self.client_controller.retrieve_clients_map_list()],
                "command" : self.auto_compile_name
            },
            DBProductionsColumns.STATO.value: {
                "type": ctk.CTkOptionMenu,
                "label": "Stato",
                "section": "Dati Generali",
                "values": [stato.name for stato in self.production_controller.Stato]
            },
            DBProductionsColumns.END_DATE.value: {
                "type": Calendar,
                "label": "Data Conclusione",
                "section": "Dati Generali"
            },

            # Dati Produzione
            DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value: {
                "type": ctk.CTkOptionMenu,
                "label": "Tipologia Produzione",
                "section": "Dati Produzione",
                "values": [tipo[1] for tipo in self.catalogo_elenchi["production_types"]],
                "command": self.parent.open_add_prod_type
            },
            DBProductionsColumns.TIPOLOGIA_OUTPUT.value: {
                "type": ctk.CTkOptionMenu,
                "label": "Tipologia Output",
                "section": "Dati Produzione",
                "values": [tipo[1] for tipo in self.catalogo_elenchi["production_output_types"]],
                "command": self.parent.open_add_prod_out_type
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
                if config["type"] == ctk.CTkOptionMenu:
                    widget = config["type"](frame, values=config.get("values", []))

                    # Gestione speciale per client_id
                    if field == self.nome_cliente_string:
                        client_id = production_data[DBProductionsColumns.CLIENT_ID.value]
                        client = self.client_controller.retrieve_client_map_by_id(client_id)
                        client_name = client[DBClientsColumns.NAME.value]
                        widget.configure(command = config.get("command"))
                        widget.set(client_name)

                    # Gestione speciale per tipologie
                    elif field == DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value:
                        current_value = production_data.get(field, "")
                        command_function = config.get("command")
                        widget.configure(command=lambda selected_value: command_function(selected_value))
                        widget.set(current_value)

                    # Gestione speciale per tipologie
                    elif field == DBProductionsColumns.TIPOLOGIA_OUTPUT.value:
                        current_value = production_data.get(field, "")
                        command_function = config.get("command")
                        widget.configure(command=lambda selected_value: command_function(selected_value))
                        widget.set(current_value)

                    # Gestione stato
                    elif field == DBProductionsColumns.STATO.value:
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


        self.production_info_widgets[DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value].configure(command=lambda selected_value: self.parent.open_add_prod_type(selected_value))

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

        invoices_map_list = self.invoice_controller.retrieve_invoice_map_list_by_production(self.current_production_id)
        confirmation = True
        if len(invoices_map_list) > 0:
            confirmation = ViewUtils.ask_confirmation_popup(self.info_frame, "Questa produzione presenta una o più fatture associate.\n"
                                                                             "La sua modifica può comportare delle incongruenze tra i dati delle fatture ad essa associate.\n"
                                                                             "Desideri continuare?\n"
                                                                             "In caso affermativo ricordati di controllare i dati delle fatture associate",
                                                            "MODIFICA PRODUZIONE")

        if confirmation:
            nome_cliente = self.production_info_widgets[self.nome_cliente_string].get()
            cliente = self.client_controller.retrieve_client_map_by_name(nome_cliente)
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
                    DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value].get(),
                DBProductionsColumns.TIPOLOGIA_OUTPUT.value: self.production_info_widgets[
                    DBProductionsColumns.TIPOLOGIA_OUTPUT.value].get(),
                DBProductionsColumns.HOURS.value: self.production_info_widgets[
                    DBProductionsColumns.HOURS.value].get(),
                DBProductionsColumns.TOTALE_PREVENTIVO.value: self.production_info_widgets[
                    DBProductionsColumns.TOTALE_PREVENTIVO.value].get()
            }

            # Chiamata al controller per salvare i dati
            success, message = self.production_controller.update_production(self.current_production_id, production_data)
            if success:
                print(
                    f"Produzione {self.production_controller.retrieve_production_map_by_id(self.current_production_id)[DBProductionsColumns.NAME.value]} salvata con successo")
                ViewUtils.show_confirm_popup_2(self.content_frame, "SALVATAGGIO COMPLETATO", message)
                self.switch_modify.deselect()
                self.toggle_edit(self.content_frame)

            else:
                # Mostra il messaggio d'errore
                print(message)
                ViewUtils.show_error_popup(self.content_frame, "ERRORE", message)

    def delete_production(self):

        invoices_map_list = self.invoice_controller.retrieve_invoice_map_list_by_production(self.current_production_id)
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
                "value": self.production_controller.calcola_totale_servizi_rimborsi_per_produzione(self.current_production_id),
                "uom": "€"
            },
            "TOTALE PREVENTIVO": {
                "value": self.production_controller.retrieve_production_map_by_id(self.current_production_id)[DBProductionsColumns.TOTALE_PREVENTIVO.value],
                "uom": "€"
            }
        }

        self.global_infos_invoices_widgets = ViewUtils.construct_global_infos_cards(section_frame, global_infos)


        invoice_frame = ctk.CTkScrollableFrame(section_frame, height=300)
        invoice_frame.pack(fill="both", expand=True, padx=(10, 20), pady=(10, 20))

        # popolo gli invoices
        invoices = self.production_controller.retrieve_production_with_invoices_map_list(self.current_production_id)
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
        client_name = self.production_info_widgets[self.nome_cliente_string].get()
        nome_produzione_array = self.production_info_widgets[DBProductionsColumns.NAME.value].get().split(" - ")
        new_name = client_name + " - " + nome_produzione_array[1] if len(nome_produzione_array) > 1 else client_name + " - "
        self.production_info_widgets[DBProductionsColumns.NAME.value].delete(0, tk.END)
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
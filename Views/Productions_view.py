import customtkinter as ctk
import tkinter as tk
from tkcalendar import Calendar
from Views.View_utils import ViewUtils
from Controllers import ProductionController, PaymentsController, InvoiceController, UserController, ControllerUtils
from Model import DBProductionsColumns, DBUsersColumns, DBClientsColumns, DBPaymentsColumns
from datetime import datetime
import re
from enum import Enum

class ProductionsView(ctk.CTk):

    def __init__(self, db_model, production_controller, payment_controller, invoice_controller, user_controller, client_controller, catalogo_elenchi, config_manager, tab, event_bus):
        super().__init__()

        self.db_model = db_model
        self.production_controller = production_controller
        self.invoice_controller = invoice_controller
        self.user_controller = user_controller
        self.client_controller = client_controller
        self.payment_controller = payment_controller
        self.catalogo_elenchi = catalogo_elenchi
        self.config_manager = config_manager
        self.tab = tab
        self.event_bus = event_bus

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

    def create_productions_tab(self):

        self.search_bar_frame = ctk.CTkFrame(self.tab)
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

        # Aggiungi evento alla barra di ricerca
        self.search_bar.bind("<KeyRelease>", self.filter_cards)

        self.populate_global_infos()

        for (key, info) in self.global_infos.items():
            card = ctk.CTkFrame(self.search_bar_frame)

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

        self.productions_table_frame = ctk.CTkFrame(self.tab)
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
            column = ctk.CTkFrame(self.productions_table_frame)
            column.grid(row=0, column=i, sticky="nsew", padx=(0, 5), pady=5)

            # imposta peso e uniformità: tutte le colonne "col" si dividono equamente
            self.productions_table_frame.grid_columnconfigure(i, weight=1, uniform="col")

            # la label riempie il suo container
            label = ctk.CTkLabel(column,
                                 text=header,
                                 font=("Arial", 14))
            label.pack(fill="both", expand=True, padx=5, pady=15)

        # Creazione del frame delle cards
        self.productions_cards_frame = ctk.CTkScrollableFrame(self.tab)
        self.productions_cards_frame.pack(padx=0, pady=10, fill="both", expand=True)

        self.add_production_frame = ctk.CTkFrame(self.tab)
        self.add_production_frame.pack(padx=0, pady=(5, 20), fill="x")

        self.save_button = ctk.CTkButton(self.add_production_frame, text="Aggiungi una produzione",
                                         command=self.open_add_production_window)
        self.save_button.pack()

        #aggiungo una tab per ogni fattura presente nel database
        production_map_list = self.production_controller.retrieve_productions_map_list(True)
        # Ordina la lista in ordine decrescente (dal più recente al più vecchio)
        production_map_list.sort(
            key=lambda x: datetime.strptime(
                x[DBProductionsColumns.UPDATED_AT.value],
                "%Y-%m-%d %H:%M:%S"
            ) if " " in x[DBProductionsColumns.UPDATED_AT.value] else datetime.strptime(
                x[DBProductionsColumns.UPDATED_AT.value],
                "%Y-%m-%d"
            ),
            reverse=True
        )
        for production in production_map_list:
            production_id = production[DBProductionsColumns.ID.value]
            production_name = production[DBProductionsColumns.NAME.value]
            client_id = production[DBProductionsColumns.CLIENT_ID.value]
            client_name = self.client_controller.retrieve_client_map_by_id(client_id)[DBClientsColumns.NAME.value]
            tipologia_produzione = production[DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value]
            tipologia_output = production[DBProductionsColumns.TIPOLOGIA_OUTPUT.value]
            produzione_stato = production[DBProductionsColumns.STATO.value]
            data_di_consegna = production[DBProductionsColumns.END_DATE.value]
            totale_preventivo = production[DBProductionsColumns.TOTALE_PREVENTIVO.value]
            durata_produzione = production[DBProductionsColumns.HOURS.value]
            prezzo_orario = self.production_controller.calculate_production_cost_per_hour(production_id)

            self.add_production_card(production_id, production_name, client_name, tipologia_produzione, tipologia_output, produzione_stato, data_di_consegna, totale_preventivo, durata_produzione, prezzo_orario)

    def populate_global_infos(self):
        self.global_infos[f"{ProductionController.ProductionsAggregateData.NUMERO_PRODUZIONI.value}"] = self.production_controller.count_productions(True)
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
            self.nome_cliente_string : ctk.CTkOptionMenu,
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
                widget = widget_class(self.production_window_scrollableFrame,
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

        # Bottone per salvare
        self.save_button = ctk.CTkButton(
            self.production_window_scrollableFrame,
            text="Salva Produzione",
            command=self.save_production_data
        )
        self.save_button.pack(pady=(35, 15))

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
            command=lambda pid=production_id: self.open_modify_production(pid)
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

    # da implementare
    def modify_production_data(self):
        """
        salva le modifiche apportate alla produzione tramite i widgets dell'interfaccia
        :return:
        """
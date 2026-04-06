import customtkinter as ctk
import tkinter as tk
from tkcalendar import Calendar
from Views.View_utils import ViewUtils
from Controllers import AccountController, Analyzer, UserController, ControllerUtils, \
    SalaryController, UpdatesController
from Controllerss.Expense_controller import ExpenseController
from Model import DatabaseModel, DBInvoicesColumns, DBUsersColumns, DBClientsColumns, DBPaymentsColumns, DBProductionsColumns, DBAccountsColumns, DBExpensesColumns, DBSuppliersColumns, DBSalariesColumns
import re
from datetime import datetime


from Config import ConfigManager
from App_context import AppContext
from Event_bus import EventBus

class SalariesView(ctk.CTkFrame):

    def __init__(self, app_context:AppContext, tab_view, initial_salary_id=None):
        super().__init__(tab_view.tab("Salario"))

        self.app_context:AppContext = app_context
        self.db_model:DatabaseModel = app_context.db_model
        self.salary_controller:SalaryController = app_context.salary_controller
        self.user_controller:UserController = app_context.user_controller
        self.account_controller:AccountController = app_context.account_controller
        self.update_controller:UpdatesController = app_context.update_controller
        self.analyzer:Analyzer = app_context.analyzer
        self.fiscal_settings = app_context.fiscal_settings
        self.catalogo_elenchi = app_context.catalogo_elenchi
        self.config_manager:ConfigManager = app_context.config_manager
        self.tab_view = tab_view
        self.tab = tab_view.tab("Salario")
        self.event_bus:EventBus = app_context.event_bus

        #self.event_bus.subscribe(ViewUtils.EventBusKeys.SHOW_SALARY_DETAIL, self.handle_show_salary_detail)

        self.global_infos = {}
        self.amount_aggregate_labels = {}
        self.aggregate_UOM = {
            ExpenseController.ExpensesAggregateData.NUMERO_SPESE.value: "",
            ExpenseController.ExpensesAggregateData.TOT_SPESE.value: "€"
        }

        self.today = datetime.now()

        self.salaries_card_list = {}
        self.salary_card_labels_status = {}

        # Container principale
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.detail_container = ctk.CTkFrame(self, fg_color="transparent")

        # Vista dettaglio
        self.salary_detail_view = SalaryDetailView(
            parent=self,
            salary_controller=self.salary_controller,
            back_callback=self.show_main_view,
            account_controller=self.account_controller,
            user_controller=self.user_controller,
            update_controller=self.update_controller,
            db_model=self.db_model,
            event_bus = self.event_bus,
            catalogo_elenchi=self.catalogo_elenchi
        )

        self.create_salaries_tab()

        if initial_salary_id is not None:
            self.after(100, lambda: self.open_salary_detail_tab(initial_salary_id))
        else:
            self.show_main_view()

    def show_main_view(self):
        """Torna alla vista principale"""
        self.salary_detail_view.pack_forget()
        self.main_container.pack(fill='both', expand=True)

    def create_salaries_tab(self):
        self.search_bar_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.search_bar_frame.pack(pady=(5, 10), fill="x", anchor="s")
        self.search_bar = ctk.CTkEntry(self.search_bar_frame)
        self.search_bar.pack(padx=(5, 35), anchor="s", side="right")
        self.search_bar_option_menu_values = {"NOME SALARIO": "NOME SALARIO", "NOME UTENTE" : "NOME UTENTE", "CONTO": "CONTO"}
        self.search_bar_optionMenu = ctk.CTkOptionMenu(self.search_bar_frame,
                                                       values=list(self.search_bar_option_menu_values.values()))
        self.search_bar_optionMenu.pack(padx=5, anchor="s", side="right")
        self.search_bar_label = ctk.CTkLabel(self.search_bar_frame, text="Filtra per ", font=("Arial", 14))
        self.search_bar_label.pack(padx=5, anchor="s", side="right")

        self.order_bar_option_menu_values = {"DATA CREAZIONE": "DATA CREAZIONE",
                                             "ULTIMA MODIFICA": "ULTIMA MODIFICA",
                                             "DATA EMISSIONE": "DATA EMISSIONE",
                                              "IMPORTO": "IMPORTO"}
        self.order_bar_option_menu_values_types = {"DECRESCENTE": "DECRESCENTE", "CRESCENTE": "CRESCENTE"}
        self.order_bar_optionMenu_types = ctk.CTkOptionMenu(self.search_bar_frame,
                                                       values=list(self.order_bar_option_menu_values_types.values()))
        self.order_bar_optionMenu_types.pack(padx=(5, 100), anchor="s", side="right")
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
        self.show_last_cards_optionMenu.set("60 GG")
        self.show_last_cards_optionMenu.pack(padx=(5, 100), anchor="s", side="right")
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

            if key == SalaryController.SalariesAggregateData.NUMERO_SALARI.value:
                global_info_unità_di_misura = ""
            elif key == SalaryController.SalariesAggregateData.TOT_SALARI.value:
                global_info_unità_di_misura = "€"

            title = ctk.CTkLabel(card, text=f"{key}", font=("Arial", 12), bg_color="#1F6AA5")
            amount = ctk.CTkLabel(card, text=f"{info} {global_info_unità_di_misura}", font=("Arial", 16))

            card.pack(side="left", anchor="w", padx=10, pady=(10, 5))
            title.pack(anchor="n", padx=10, pady=(10, 5), ipadx=7, ipady=5)
            amount.pack(anchor="s", padx=10, pady=5)

            # salvo i dati che potrebbero avere bisogno di configure successivamente
            self.amount_aggregate_labels[f"{key}"] = amount

        self.salaries_table_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.salaries_table_frame.pack(pady=(20, 0), padx=(10, 15), fill="x", anchor="n")

        self.table_headers = ["NOME", "UTENTE", "IMPORTO", "DATA\nEMISSIONE", "CONTO\nCORRENTE"]

        for i, header in enumerate(self.table_headers):
            # crea il container
            column = ctk.CTkFrame(self.salaries_table_frame, fg_color="#333333")
            column.grid(row=0, column=i, sticky="nsew", padx=(0, 5), pady=5)

            # imposta peso e uniformità: tutte le colonne "col" si dividono equamente
            self.salaries_table_frame.grid_columnconfigure(i, weight=1, uniform="col")

            # la label riempie il suo container
            label = ctk.CTkLabel(column,
                                 text=header,
                                 font=("Arial", 14))
            label.pack(fill="both", expand=True, padx=5, pady=15)

        # Creazione del frame delle cards
        self.cards_frame = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")
        self.cards_frame.pack(padx=0, pady=10, fill="both", expand=True)

        self.add_salary_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.add_salary_frame.pack(padx=0, pady=(5, 20), fill="x")

        self.save_button = ctk.CTkButton(self.add_salary_frame, text="Aggiungi un salario",
                                         command=self.open_add_salary_window)
        self.save_button.pack()

        # Sistema per tracciare gli after()
        self._after_ids = set()
        self._orig_after = self.after
        self.after = self._track_after

        self.show_last_cards()

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
        all_salaries = self.salary_controller.retrieve_salaries_map_list()

        # Filtra le fatture: solo quelle con data di emissione >= limit_date
        filtered_salaries = []
        for salary in all_salaries:
            date_str = salary.get(DBSalariesColumns.DATE.value)
            if date_str:
                try:
                    # Prova a parsare la data in formato yyyy-mm-dd o yyyy-mm-dd hh:mm:ss
                    try:
                        salary_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        salary_date = datetime.strptime(date_str, "%Y-%m-%d")

                    if salary_date >= limit_date:
                        filtered_salaries.append(salary)
                except Exception as e:
                    print(f"Errore nel parsare la data {date_str}: {e}")

        # Svuota le cards attuali
        for card in self.salaries_card_list.values():
            card.destroy()
        self.salaries_card_list.clear()

        # Ricarica le cards con le fatture filtrate
        self.load_salaries_chunked(filtered_salaries)

        self.sort_cards()

    def filter_cards(self, event):
        """Filtra le card in base al testo della barra di ricerca e al tipo di filtro scelto."""
        search_text = self.search_bar.get().lower()
        search_type = self.search_bar_optionMenu.get()

        # Mappatura: ogni chiave associa una tupla (indice, classe_attesa) del widget da cui prelevare il testo
        filter_mapping = {
            "NOME SALARIO": (0, ctk.CTkButton),  # Bottone
            "NOME UTENTE": (1, ctk.CTkLabel),
            "CONTO": (4, ctk.CTkLabel)
        }

        mapping = filter_mapping.get(search_type)

        # Prima rimuovo tutte le card dal container per avere un layout pulito
        for card in self.salaries_card_list.values():
            card.pack_forget()

        # Se il tipo di ricerca non è riconosciuto, riposiziona tutte le card nell'ordine originale
        if mapping is None:
            for card in self.salaries_card_list.values():
                card.pack(pady=10, padx=10, fill="x", expand=True)
            return

        idx, expected_class = mapping

        # Itera sulle card nell’ordine originale (grazie al dizionario ordinato)
        for key, card in self.salaries_card_list.items():
            children = card.winfo_children()  # Lista dei widget figli
            widget_text = ""
            if len(children) > idx and isinstance(children[idx], expected_class):
                widget_text = children[idx].cget("text")
            # Se il testo (in lowercase) contiene il testo di ricerca, riposiziona la card
            if search_text in widget_text.lower():
                card.pack(pady=10, padx=10, fill="x", expand=True)

    def sort_cards(self):
        """Ordina le cards degli stipendi in base ai criteri selezionati nei menu di ordinamento."""

        # Funzioni di supporto per la conversione dei valori
        def _convert_to_date(date_str):
            """Converte una stringa in formato dd-mm-yyyy in un oggetto date per l'ordinamento."""
            from datetime import datetime
            try:
                return datetime.strptime(date_str.strip(), "%d-%m-%Y")
            except (ValueError, TypeError):
                return None

        def _convert_to_currency(currency_str):
            """Converte una stringa di valuta in un numero float per l'ordinamento."""
            if not currency_str or not currency_str.strip():
                return None

            try:
                # Rimuovi il simbolo dell'euro e gli spazi
                cleaned = currency_str.strip().replace('€', '').replace(' ', '')

                # Gestione dei numeri negativi
                negative = False
                if cleaned.startswith('-'):
                    negative = True
                    cleaned = cleaned[1:]

                # Gestione di formati con separatori delle migliaia e decimali
                # Cerca l'ultimo separatore (potrebbe essere punto o virgola per i decimali)
                last_comma = cleaned.rfind(',')
                last_dot = cleaned.rfind('.')

                # Determina il separatore decimale (l'ultimo punto o virgola)
                if last_comma > last_dot:
                    # Virgola come separatore decimale, punti come separatori delle migliaia
                    cleaned = cleaned.replace('.', '').replace(',', '.')
                elif last_dot > last_comma:
                    # Punto come separatore decimale, virgole come separatori delle migliaia
                    cleaned = cleaned.replace(',', '').replace('.', '.')
                else:
                    # Nessun separatore decimale, rimuovi tutti i separatori
                    cleaned = cleaned.replace(',', '').replace('.', '')

                # Converti in float e gestisci il segno
                result = float(cleaned) * (-1 if negative else 1)
                return result

            except (ValueError, TypeError):
                return None

        def _convert_to_datetime(datetime_str):
            """Converte una stringa in formato yyyy-mm-dd hh:mm:ss in un oggetto datetime per l'ordinamento."""
            from datetime import datetime
            try:
                return datetime.strptime(datetime_str.strip(), "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                return None

        # Ottieni i criteri di ordinamento
        sort_by = self.order_bar_optionMenu.get()
        sort_order = self.order_bar_optionMenu_types.get()

        # Mappatura: ogni criterio associa una tupla (tipo_di_accesso, parametro, funzione_di_conversione, colonna_db)
        sort_mapping = {
            "IMPORTO": ("direct", 2, _convert_to_currency, None),
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

        # Raccogli tutte le cards e i loro valori di ordinamento
        cards_with_values = []
        for key, card in self.salaries_card_list.items():  # Assumendo che la lista si chimi salaries_card_list
            children = card.winfo_children()
            sort_value = ""

            if access_type == "direct":
                # Accesso diretto al valore nella card
                if len(children) > param:
                    sort_value = children[param].cget("text")
            elif access_type == "database":
                # Accesso al valore tramite database
                if len(children) > 0:
                    salary_name = children[0].cget("text")  # Nome stipendio dal primo child
                    # Assumendo che esista un controller per gli stipendi con un metodo retrieve_salary_map_by_name
                    salary_map = self.salary_controller.retrieve_salary_map_by_name(salary_name)
                    if salary_map and db_column:
                        sort_value = salary_map.get(db_column, "")

            # Converti il valore nel tipo appropriato (applicando strip per rimuovere spazi)
            converted_value = None
            if sort_value and sort_value.strip():
                try:
                    converted_value = converter(sort_value)
                except Exception:
                    converted_value = None

            cards_with_values.append((key, card, converted_value))

        # Ordina le cards in base al valore convertito
        # Gestisci i valori None posizionandoli alla fine in entrambi i casi
        cards_with_values.sort(
            key=lambda x: (x[2] is not None, x[2]) if x[2] is not None else (False, None),
            reverse=reverse
        )

        # Nascondi temporaneamente tutte le cards
        for card in self.salaries_card_list.values():
            card.pack_forget()

        # Riposiziona le cards nell'ordine ordinato
        for _, card, _ in cards_with_values:
            card.pack(pady=10, padx=10, fill="x", expand=True)

        # Forza l'aggiornamento dell'interfaccia
        self.update_idletasks()

    def populate_global_infos(self):
        numero_salari = self.salary_controller.count_salaries(True)
        totale_salari = round(self.salary_controller.calculate_tot_salaries(), 2)
        self.global_infos[f"{SalaryController.SalariesAggregateData.NUMERO_SALARI.value}"] = numero_salari
        self.global_infos[f"{SalaryController.SalariesAggregateData.TOT_SALARI.value}"] = f"{totale_salari:.2f}"

    def load_salaries_chunked(self, salaries_list):

        extractor = ViewUtils.create_extractor_for_salaries(
            self.user_controller,
            self.account_controller
        )

        ViewUtils.process_items_in_chunks(
            widget=self,
            items_list=salaries_list,
            add_card_callback=self.add_salary_card,
            extract_args_callback=extractor,
            cards_frame=self.cards_frame

        )

    def add_salary_card(self, salary_id, salary_name, user_name, amount, date, account_name):
        card = ctk.CTkFrame(self.cards_frame, fg_color="dimgray")
        card.pack(pady=10, padx=8, fill="x", expand=True)  # Spaziatura tra le card

        # Dati da visualizzare nella card
        data = [salary_name, user_name, round(amount, 2), ViewUtils.invert_data_string(date), account_name]
        units = ["", "", "€", "", ""]
        n_cols = len(data)  # 8 colonne totali

        # Configura il grid della card: 1 riga, n_cols colonne uguali
        for c in range(n_cols):
            card.grid_columnconfigure(c, weight=1, uniform="clientcol")

        card.grid_rowconfigure(0, weight=1)

        # 0) Bottone "nome"
        btn = ctk.CTkButton(
            card,
            text=salary_name,
            command=lambda sid=salary_id: self.open_salary_detail_tab(sid)
        )
        btn.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        # 1..7) Le altre colonne
        for idx, val in enumerate(data[1:], start=1):
            text = f"{val} {units[idx]}"
            lbl = ctk.CTkLabel(card, text=text, font=("Arial", 14))
            lbl.grid(row=0, column=idx, sticky="nsew", padx=5, pady=10)

        # Salva la card per eventuale successivo accesso
        self.salaries_card_list[salary_name] = card

    def open_add_salary_window(self):
        self.add_salary_window = ctk.CTkToplevel(self)
        self.add_salary_window.title("Aggiungi Nuovo Salario")

        # Assicurati che la finestra rimanga sopra
        self.add_salary_window.lift()  # Porta la finestra sopra quella principale
        self.add_salary_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

        self.add_salary_window.geometry("550x700")

        self.salary_window_scrollableFrame = ctk.CTkScrollableFrame(self.add_salary_window)
        self.salary_window_scrollableFrame.pack(fill="both", expand=True)

        self.nome_conto_string = "CONTO"
        self.nome_utente_string = "NOME UTENTE"

        self.entry_fields = {
            self.nome_utente_string: ctk.CTkOptionMenu,
            DBSalariesColumns.NAME.value: ctk.CTkEntry,
            DBSalariesColumns.DATE.value: Calendar,
            DBSalariesColumns.AMOUNT.value: ctk.CTkEntry,
            self.nome_conto_string: ctk.CTkOptionMenu,
        }

        self.error_fields = {
            DBSalariesColumns.NAME.value: ctk.CTkLabel,
            DBSalariesColumns.AMOUNT.value: ctk.CTkLabel,
        }

        self.salaries_widgets = {}
        self.error_labels = {}
        self.salaries_labels = {}

        # Creo i labels e i widgets
        for i, (label_text, widget_class) in enumerate(self.entry_fields.items()):
            # Etichetta
            label = ctk.CTkLabel(self.salary_window_scrollableFrame, text=label_text)
            # disegno i labels
            if i == 0:
                label.pack(pady=5)
            elif i != 0 :
                label.pack(pady=(35, 0))

            self.salaries_labels[label_text] = label

            # creo i widgets
            if label_text == self.nome_utente_string:
                # recupero gli utenti
                users = self.user_controller.retrieve_users_map_list()
                widget = widget_class(self.salary_window_scrollableFrame,
                                      values=[user[DBUsersColumns.FIRST_NAME.value] + " " + user[
                                          DBUsersColumns.LAST_NAME.value] for user in users],
                                      command=lambda selected_value: self.toggle_widgets_on_user_selection(selected_value))


            elif label_text == DBSalariesColumns.DATE.value:
                widget = widget_class(self.salary_window_scrollableFrame, date_pattern=ViewUtils.date_pattern)


            elif label_text == self.nome_conto_string:
                # recupero i conti
                accounts = self.account_controller.retrieve_accounts_map_list()
                widget = widget_class(self.salary_window_scrollableFrame,
                                      values=[account[DBAccountsColumns.NAME.value] for account in accounts])

            else:
                widget = widget_class(self.salary_window_scrollableFrame)


            #packing widget
            widget.pack(pady=5, padx=10, fill="x", expand=True)

            self.salaries_widgets[label_text] = widget

            if self.error_fields.get(label_text) is not None:
                error_label = ctk.CTkLabel(self.salary_window_scrollableFrame, text="")
                error_label.pack(pady=(0, 15))
                self.error_labels[label_text] = error_label

        user_name_at_window_opening = self.salaries_widgets[self.nome_utente_string].get()
        self.toggle_widgets_on_user_selection(user_name_at_window_opening)

        # Bottone per salvare
        self.save_button = ctk.CTkButton(
            self.salary_window_scrollableFrame,
            text="Salva Salario",
            command=self.save_salary_data
        )
        self.save_button.pack(pady=(50, 15))



        # Aggiungi validazione agli eventi di perdita del focus
        self.salaries_widgets[DBSalariesColumns.NAME.value].bind("<FocusOut>",
             lambda event: ViewUtils.validate_entry(
                 self.salaries_widgets[
                     DBSalariesColumns.NAME.value],
                 lambda val: val.strip() != "",
                 self.error_labels[
                     DBSalariesColumns.NAME.value],
                 "Il campo non può essere vuoto."
             ))

        self.salaries_widgets[DBSalariesColumns.AMOUNT.value].bind("<FocusOut>",
            lambda event: ViewUtils.validate_entry(
                self.salaries_widgets[
                   DBSalariesColumns.AMOUNT.value],
                lambda val: re.fullmatch(
                   r"^\d+(\.\d{2})?$",
                   val.strip()) is not None,
                self.error_labels[
                   DBSalariesColumns.AMOUNT.value],
                "Inserimento non valido: inserire un numero monetario con due cifre decimali (es. 123.45)"
            ))

    def toggle_widgets_on_user_selection(self, selected_value):
        user = self.user_controller.retrieve_user_map_by_extended_name(selected_value.strip())
        if user:
            account = self.account_controller.retrieve_account_map_by_id(user[DBUsersColumns.CONTO_CORRENTE_ID.value])
            self.salaries_widgets[DBSalariesColumns.NAME.value].delete(0, tk.END)
            self.salaries_widgets[DBSalariesColumns.NAME.value].insert(0, f"{selected_value.strip()} - {self.today.strftime("%m/%Y")}")
            self.salaries_widgets[self.nome_conto_string].set(account[DBAccountsColumns.NAME.value])

    def save_salary_data(self):
        salary_data = {}

        # riempi il dizionario con i dati dei widgets primari
        for label_text, widget in self.salaries_widgets.items():
            if isinstance(widget, ctk.CTkEntry) or isinstance(widget, ctk.CTkOptionMenu):
                salary_data[label_text] = widget.get().strip()
            elif isinstance(widget, Calendar):
                salary_data[label_text] = widget.get_date()
            elif isinstance(widget, ctk.CTkTextbox):
                salary_data[label_text] = widget.get("1.0", "end-1c").strip()  # Recupera il testo dal Textbox

        # chiamata al controller per salvare i dati
        success, message = self.salary_controller.save_salary(salary_data)

        if success:

            # prendo l'ID della sesa appena creata
            salary_map = self.salary_controller.retrieve_last_salary_insert_map()
            print(f"Salario {salary_data[DBSalariesColumns.NAME.value]} salvato con successo")

            user = self.user_controller.retrieve_user_map_by_id(salary_map[DBSalariesColumns.USER_ID.value])
            user_first = user[DBUsersColumns.FIRST_NAME.value]
            user_last = user[DBUsersColumns.LAST_NAME.value]
            user_full = user_first + " " + user_last

            account_name = \
            self.account_controller.retrieve_account_map_by_id(salary_map[DBExpensesColumns.ACCOUNT_ID.value])[
                DBAccountsColumns.NAME.value]

            self.add_salary_card(
                salary_map[DBSalariesColumns.ID.value],
                salary_map[DBSalariesColumns.NAME.value],
                user_full,
                salary_map[DBSalariesColumns.AMOUNT.value],
                salary_map[DBSalariesColumns.DATE.value],
                account_name
            )

            self.clear_class_variable()
            self.add_salary_window.destroy()
            self.show_last_cards()
            self.update_global_infos()
        else:
            print(message)
            ViewUtils.show_error_popup(self.add_salary_window, "ERRORE", message)

    def open_salary_detail_tab(self, salary_id):
        """Mostra la vista dettaglio stipendio con controlli di sicurezza"""
        try:
            # Verifica che i widget esistano
            if hasattr(self, 'main_container') and self.main_container.winfo_exists():
                self.main_container.pack_forget()

            # Se salary_detail_view non esiste, crealo
            if not hasattr(self, 'salary_detail_view') or not self.salary_detail_view.winfo_exists():
                self.salary_detail_view = SalaryDetailView(
                    parent=self,
                    salary_controller=self.salary_controller,
                    back_callback=self.show_main_view,
                    account_controller=self.account_controller,
                    user_controller=self.user_controller,
                    update_controller=self.update_controller,
                    db_model=self.db_model,
                    event_bus=self.event_bus,
                    catalogo_elenchi=self.catalogo_elenchi
                )

            # Mostra il dettaglio
            self.salary_detail_view.pack(fill='both', expand=True)
            self.salary_detail_view.create_detail_tab(salary_id)  # Ricrea i contenuti ogni volta

        except Exception as e:
            print(f"Errore in open_salary_detail_tab: {e}")
            # Fallback: mostra la vista principale
            self.show_main_view()

    def handle_show_salary_detail(self, salary_id):
        self.tab_view.set("Salario")  # Cambia tab
        self.after(150, lambda: self.open_salary_detail_tab(salary_id))

    def clear_class_variable(self):
        self.salaries_widgets.clear()
        self.salaries_labels.clear()

    def update_global_infos(self):
        return

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





class SalaryDetailView(ctk.CTkFrame):
    def __init__(self, parent, back_callback, salary_controller, user_controller, account_controller, update_controller, db_model, event_bus, catalogo_elenchi):
        super().__init__(parent)
        self.salary_controller = salary_controller
        self.user_controller = user_controller
        self.account_controller = account_controller
        self.db_model = db_model
        self.back_callback = back_callback
        self.update_controller = update_controller
        self.event_bus = event_bus
        self.current_expense_id = None
        self.catalogo_elenchi = catalogo_elenchi
        self.parent = parent

        self.configure(fg_color="transparent")



        # Widgets persistenti (vanno creati una volta sola)
        self.head_frame = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.back_button = ctk.CTkButton(
            self.head_frame,
            text="Elenco Stipendi",
            command=self._cleanup_and_go_back
        )
        self.title_label = ctk.CTkLabel(self.head_frame, font=("Arial", 22, "bold"))

        self.expense_info_widgets: dict[str, ctk.CTkEntry | ctk.CTkOptionMenu] = {}

        self.nome_conto_string = "CONTO"
        self.nome_user_string = "UTENTE"


        # Container per i contenuti dinamici
        self.content_frame = ctk.CTkFrame(self)

        self.switch_modify = ctk.CTkSwitch(self.head_frame, text="Abilita la modifica", command=lambda: self.toggle_edit(self.content_frame))

        # Layout iniziale
        self._setup_base_layout()

    def create_detail_tab(self, salary_id):
        """Ricrea la vista dettaglio per una spesa specifica"""
        self.current_salary_id = salary_id

        # 1. Pulizia dei widget precedenti
        self._clear_content()

        # 2. Caricamento dati
        self.salary = self.salary_controller.retrieve_salary_map_by_id(salary_id)

        # prendo il nome del conto:
        id_conto = self.salary[DBSalariesColumns.ACCOUNT_ID.value]
        conto = self.account_controller.retrieve_account_map_by_id(id_conto)
        if conto is not None:
            nome_conto = conto[DBAccountsColumns.NAME.value]
            self.salary[self.nome_conto_string] = nome_conto

        # prendo il nome dell'utente
        id_user = self.salary[DBSalariesColumns.USER_ID.value]
        user = self.user_controller.retrieve_user_map_by_id(id_user)
        if user is not None:
            nome_user = user[DBUsersColumns.FIRST_NAME.value] + " " + user[DBUsersColumns.LAST_NAME.value]
            self.salary[self.nome_user_string] = nome_user

        # 3. Aggiornamento elementi persistenti
        self.title_label.configure(
            text=f"{self.salary[DBSalariesColumns.NAME.value]}")

        # 4. Creazione contenuti dinamici
        self._create_salary_info_section(self.salary)
        self.toggle_edit(self.content_frame)

        self.wrapper_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.wrapper_frame.pack(padx=15, pady=(90, 0), fill="both", expand=True)

    def _create_salary_info_section(self, salary_data):
        # Dizionario per la configurazione dei campi
        self.entry_fields_salaries = {
            # Dati Generali
            DBSalariesColumns.NAME.value: {
                "type": ctk.CTkEntry,
                "label": "Nome Stipendio",
                "section": "Dati Generali"
            },
            DBSalariesColumns.DATE.value: {
                "type": Calendar,
                "label": "Data Stipendio",
                "section": "Dati Generali"
            },
            DBSalariesColumns.AMOUNT.value: {
                "type": ctk.CTkEntry,
                "label": "Importo (€)",
                "section": "Dati Generali"
            },

            # Collegamenti
            self.nome_conto_string: {
                "type": ctk.CTkOptionMenu,
                "label": "Conto",
                "section": "Collegamenti",
                "values": [c[DBAccountsColumns.NAME.value] for c in
                           self.account_controller.retrieve_accounts_map_list()]
            },
            self.nome_user_string: {
                "type": ctk.CTkOptionMenu,
                "label": "Utente",
                "section": "Collegamenti",
                "values": [f"{u[DBUsersColumns.FIRST_NAME.value]} {u[DBUsersColumns.LAST_NAME.value]}"
                           for u in self.user_controller.retrieve_users_map_list()]
            },

            # Campi statici
            DBSalariesColumns.CREATED_AT.value: {
                "type": ctk.CTkLabel,
                "label": "Data Creazione",
                "section": "Note"
            },
            DBSalariesColumns.UPDATED_AT.value: {
                "type": ctk.CTkLabel,
                "label": "Ultimo Aggiornamento",
                "section": "Note"
            }
        }

        # Regole di validazione
        validation_rules = {
            DBSalariesColumns.NAME.value: (
                lambda val: val.strip() != "",
                "Nome obbligatorio"
            ),
            DBSalariesColumns.DATE.value: (
                lambda val: val.strip() != "",
                "Data obbligatoria"
            ),
            DBSalariesColumns.AMOUNT.value: (
                lambda val: re.fullmatch(r"^\d+(\.\d{1,2})?$", val),
                "Formato valido: 1234.56"
            )
        }

        # Inizializzazione strutture dati
        self.salary_info_widgets = {}
        self.salary_info_labels = {}
        self.error_labels_salaries = {}
        sections = {}

        # Creazione frame principale
        self.info_frame = ctk.CTkFrame(self.content_frame, border_width=2, border_color="#2659ab")
        self.info_frame.pack(fill="both", expand=True, pady=(5, 10), padx=(5, 25))

        # Configurazione griglia a 2 colonne
        self.info_frame.grid_columnconfigure(0, weight=1, uniform="col")
        self.info_frame.grid_columnconfigure(1, weight=1, uniform="col")

        # Sezioni organizzate
        sections_order = [
            "Dati Generali",
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
        for field, config in self.entry_fields_salaries.items():
            section = sections[config["section"]]
            frame = section["frame"]
            row = section["row"]

            # Creazione label
            lbl = ctk.CTkLabel(frame, text=config["label"] + ":")
            self.salary_info_labels[field] = lbl
            lbl.grid(row=row, column=0, sticky="w", padx=(15, 5), pady=(5, 5))

            # Creazione widget
            if config["type"] == ctk.CTkLabel:
                value = str(salary_data.get(field, ""))
                widget = config["type"](frame, text=value)
                widget.grid(row=row, column=1, sticky="w", padx=(5, 15), pady=(5, 5))
            else:
                if config["type"] == ctk.CTkOptionMenu:
                    widget = config["type"](frame, values=config.get("values", []))

                    # Imposta il valore corrente per il conto
                    if field == "nome_conto":
                        account_id = salary_data.get(DBSalariesColumns.ACCOUNT_ID.value, "")
                        account_name = next(
                            (a[DBAccountsColumns.NAME.value] for a in
                             self.account_controller.retrieve_accounts_map_list()
                             if a[DBAccountsColumns.ID.value] == account_id),
                            "")
                        widget.set(account_name)

                    # Imposta il valore corrente per il dipendente
                    elif field == "nome_utente":
                        user_id = salary_data.get(DBSalariesColumns.USER_ID.value, "")
                        user_name = next(
                            (f"{u[DBUsersColumns.FIRST_NAME.value]} {u[DBUsersColumns.LAST_NAME.value]}"
                             for u in self.user_controller.retrieve_users_map_list()
                             if u[DBUsersColumns.ID.value] == user_id),
                            "")
                        widget.set(user_name)
                    else:
                        value = salary_data.get(field, config.get("values", [""])[0])
                        widget.set(value)

                elif config["type"] == Calendar:
                    widget = config["type"](frame, date_pattern=ViewUtils.date_pattern)
                    value = salary_data.get(field, "")
                    widget.selection_set(str(value)) if value else widget.selection_set(datetime.today())
                else:
                    widget = config["type"](frame)
                    value = str(salary_data.get(field, ""))
                    widget.insert(0, value)

                widget.grid(row=row, column=1, sticky="ew", padx=(5, 15), pady=(5, 5))

            self.salary_info_widgets[field] = widget

            # Gestione validazione
            if field in validation_rules:
                validation_func, error_message = validation_rules[field]

                error_lbl = ctk.CTkLabel(frame, text="", text_color="#e8e5dc")
                error_lbl.grid(row=row + 1, column=1, sticky="w", padx=5, pady=(0, 10))
                self.error_labels_salaries[field] = error_lbl

                widget.bind("<FocusOut>",
                            lambda e, w=widget, vl=validation_func, el=error_lbl, em=error_message:
                            ViewUtils.validate_entry(w, vl, el, em))

                section["row"] += 2
            else:
                section["row"] += 1

        # Frame per i bottoni
        buttons_frame = ctk.CTkFrame(self.info_frame, fg_color="#2b2b2b")
        buttons_frame.grid(row=2, column=0, columnspan=2, pady=(5, 15), padx=20, sticky="WE")

        # Bottone Salva
        self.save_info_btn = ctk.CTkButton(buttons_frame, text="Salva Stipendio", command=self.save_salary_mod)
        self.save_info_btn.pack(padx=(400, 10), pady=(20, 20), side="left")

        # Bottone Elimina
        self.delete_btn = ctk.CTkButton(buttons_frame, text="Elimina Stipendio",
                                        fg_color="#8B0000", hover_color="#A52A2A",
                                        command=self.delete_salary)
        self.delete_btn.pack(padx=10, pady=(20, 20), side="right", anchor="e")

    def save_salary_mod(self):
        # Recupera e converte il nome del conto in ID
        nome_conto = self.salary_info_widgets[self.nome_conto_string].get()
        conto = self.account_controller.retrieve_account_map_by_name(nome_conto)
        id_conto = conto[DBAccountsColumns.ID.value] if conto else None

        # Recupera e converte il nome dell'utente in ID
        nome_utente = self.salary_info_widgets[self.nome_user_string].get()
        id_utente = None
        if nome_utente != "":
            # Divide nome e cognome (assumendo formato "Nome Cognome")
            parts = nome_utente.split(" ", 1)
            first_name = parts[0] if len(parts) > 0 else ""
            last_name = parts[1] if len(parts) > 1 else ""

            utente = self.user_controller.retrieve_user_map_by_fullname(first_name, last_name)
            id_utente = utente[DBUsersColumns.ID.value] if utente else None

        # Costruisci i dati dello stipendio
        salary_data = {
            DBSalariesColumns.NAME.value: self.salary_info_widgets[
                DBSalariesColumns.NAME.value].get().strip(),
            DBSalariesColumns.DATE.value: self.salary_info_widgets[
                DBSalariesColumns.DATE.value].get_date(),
            DBSalariesColumns.AMOUNT.value: self.salary_info_widgets[
                DBSalariesColumns.AMOUNT.value].get().strip(),
            DBSalariesColumns.ACCOUNT_ID.value: id_conto,
            DBSalariesColumns.USER_ID.value: id_utente
        }

        # Chiamata al controller per salvare i dati
        success, message = self.salary_controller.update_salary(self.current_salary_id, salary_data)

        if success:
            salary_name = self.salary_controller.retrieve_salary_map_by_id(self.current_salary_id)[DBSalariesColumns.NAME.value]
            print(f"Stipendio {salary_name} salvato con successo")
            ViewUtils.show_confirm_popup_2(self.content_frame, "SALVATAGGIO COMPLETATO", message)

            self.switch_modify.deselect()
            self.toggle_edit(self.content_frame)

        else:
            print(f"Errore salvataggio stipendio: {message}")
            ViewUtils.show_error_popup(self.content_frame, "ERRORE", message)

    def delete_salary(self):
        confirmation = ViewUtils.ask_confirmation_popup(
            self.content_frame,
            "Stai per eliminare questo stipendio.\nDesideri continuare?",
            "ELIMINAZIONE Stipendio"
        )

        if confirmation:
            success, message = self.salary_controller.delete_salary(self.current_salary_id)

            if success:
                # Recupera il nome dello stipendio prima dell'eliminazione per il messaggio
                salary_name = self.salary[DBSalariesColumns.NAME.value]
                ViewUtils.show_confirm_popup_2(
                    self.content_frame,
                    "STIPENDIO ELIMINATO CON SUCCESSO",
                    message
                )
                print(f"Stipendio {salary_name} eliminato correttamente")

                self.switch_modify.deselect()
                self.toggle_edit(self.content_frame)

            else:
                print(f"Errore eliminazione stipendio: {message}")
                ViewUtils.show_error_popup(
                    self.content_frame,
                    "ERRORE",
                    message
                )

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

    def _setup_base_layout(self):
        """Inizializza la struttura base del layout"""
        self.head_frame.pack(fill="x", pady=5, padx=5)
        self.back_button.pack(anchor="w", side="left", pady=10, padx=10)
        self.title_label.pack(anchor="c", side="left", fill="x", expand=True, pady=10)
        self.switch_modify.pack(anchor="e", side="left", pady=10, padx=10)
        self.content_frame.pack(fill="both", expand=True, pady=20, padx=20)

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

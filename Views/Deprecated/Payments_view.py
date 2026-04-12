import customtkinter as ctk
import tkinter as tk
from tkcalendar import Calendar
from Views.View_utils import ViewUtils
from Views.CustomWidgets.Filterable_combo_box import FilterableComboBox
from Controllers import AccountController
from Updates_controller import UpdatesController
from Controllerss.User_controller import UserController
from Model import DatabaseModel, DBInvoicesColumns, DBUsersColumns, DBClientsColumns, DBPaymentsColumns, DBProductionsColumns, DBAccountsColumns
from datetime import datetime
import re

from Gestionale_Enums import*

from Controllerss.Client_controller import ClientController
from Controllerss.Production_controller import ProductionController
from Controllerss.Invoice_controller import InvoiceController


from Event_bus import EventBus
from App_context import AppContext

from QueryServices.Clients_query_service import ClientQueryService
from QueryServices.Invoices_query_service import InvoiceQueryService


class PaymentsView(ctk.CTkFrame):

    def __init__(self, app_context:AppContext, tab_view, initial_payment_id=None):

        super().__init__(tab_view.tab("Pagamenti"))

        self.app_context:AppContext = app_context
        self.db_model:DatabaseModel = app_context.db_model
        self.invoice_controller:InvoiceController = app_context.invoice_controller
        self.user_controller:UserController = app_context.user_controller
        self.client_controller:ClientController = app_context.client_controller
        self.clients_query_service:ClientQueryService = app_context.clients_query_service
        self.invoices_query_service:InvoiceQueryService = app_context.invoices_query_service
        self.payment_controller:PaymentsController = app_context.payment_controller
        self.production_controller:ProductionController = app_context.production_controller
        self.account_controller:AccountController = app_context.account_controller
        self.update_controller:UpdatesController = app_context.update_controller
        self.tab_view = tab_view
        self.tab = tab_view.tab("Pagamenti")
        self.event_bus:EventBus = app_context.event_bus

        self.global_infos = {}
        self.amount_aggregate_labels = {}

        self.payment_card_list = {}
        self.payment_card_labels_status = {}
        self.cards_warnings = {}

        self.update_controller.register_on_modify_invoice_view_cllbks(self.attach_warning_on_a_card)

        # Container principale
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.detail_container = ctk.CTkFrame(self, fg_color="transparent")

        # Vista dettaglio
        self.payment_detail_view = PaymentDetailView(
            parent=self,
            invoice_controller=self.invoice_controller,
            payment_controller=self.payment_controller,
            back_callback=self.show_main_view,
            account_controller=self.account_controller,
            client_controller=self.client_controller,
            production_controller=self.production_controller,
            update_controller=self.update_controller,
            db_model=self.db_model,
            event_bus = self.event_bus
        )

        self.create_payments_tab()

        if initial_payment_id is not None:
            self.after(100, lambda: self.open_payment_detail_tab(initial_payment_id))
        else:
            self.show_main_view()

    def show_main_view(self):
        """Torna alla vista principale"""
        self.payment_detail_view.pack_forget()
        self.main_container.pack(fill='both', expand=True)

    def open_payment_detail_tab(self, payment_id):
        """Mostra la vista dettaglio pagamento con controlli di sicurezza"""
        try:
            # Verifica che i widget esistano
            if hasattr(self, 'main_container') and self.main_container.winfo_exists():
                self.main_container.pack_forget()

            # Se payment_detail_view non esiste, crealo
            if not hasattr(self, 'payment_detail_view') or not self.payment_detail_view.winfo_exists():
                self.payment_detail_view = PaymentDetailView(
                    parent=self,
                    invoice_controller=self.invoice_controller,
                    payment_controller=self.payment_controller,
                    back_callback=self.show_main_view,
                    account_controller=self.account_controller,
                    client_controller=self.client_controller,
                    production_controller=self.production_controller,
                    update_controller=self.update_controller,
                    db_model=self.db_model,
                    event_bus=self.event_bus
                )

            # Mostra il dettaglio
            self.payment_detail_view.pack(fill='both', expand=True)
            self.payment_detail_view.create_detail_tab(payment_id)  # Ricrea i contenuti ogni volta

        except Exception as e:
            print(f"Errore in open_payment_detail_tab: {e}")
            # Fallback: mostra la vista principale
            self.show_main_view()

    def create_payments_tab(self):

        self.search_bar_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.search_bar_frame.pack(pady=(5, 10), fill="x", anchor="s")
        self.search_bar = ctk.CTkEntry(self.search_bar_frame)
        self.search_bar.pack(padx=(5, 35), anchor="s", side="right")
        self.search_bar_option_menu_values = {"NOME PAGAM.": "NOME PAGAM.", "NOME CLIENTE": "NOME CLIENTE",
                                              "NOME PRODUZIONE": "NOME PRODUZIONE", "CONTO": "CONTO"}
        self.search_bar_optionMenu = ctk.CTkOptionMenu(self.search_bar_frame,
                                                       values=list(self.search_bar_option_menu_values.values()))
        self.search_bar_optionMenu.pack(padx=5, anchor="s", side="right")
        self.search_bar_label = ctk.CTkLabel(self.search_bar_frame, text="Filtra per ", font=("Arial", 14))
        self.search_bar_label.pack(padx=5, anchor="s", side="right")

        self.order_bar_option_menu_values = {"DATA CREAZIONE": "DATA CREAZIONE",
                                             "ULTIMA MODIFICA": "ULTIMA MODIFICA",
                                             "DATA CONTABILIZZAZIONE": "DATA CONTABILIZZAZIONE",
                                              "TOTALE": "TOTALE"}
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

            if key == PaymentsController.PaymentsAggregateData.NUMERO_PAGAMENTI.value:
                global_info_unità_di_misura = ""
            elif key == PaymentsController.PaymentsAggregateData.TOT_PAGAMENTI.value:
                global_info_unità_di_misura = "€"

            title = ctk.CTkLabel(card, text=f"{key}", font=("Arial", 12), bg_color="#1F6AA5")
            amount = ctk.CTkLabel(card, text=f"{info} {global_info_unità_di_misura}", font=("Arial", 16))

            card.pack(side="left", anchor="w", padx=10, pady=(10, 5))
            title.pack(anchor="n", padx=10, pady=(10, 5), ipadx=7, ipady=5)
            amount.pack(anchor="s", padx=10, pady=5)

            #salvo i dati che potrebbero avere bisogno di configure successivamente
            self.amount_aggregate_labels[f"{key}"] = amount

        self.payments_table_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.payments_table_frame.pack(pady=(20, 0), padx=(10, 15), fill="x", anchor="n")

        self.table_headers = ["NOME", "CLIENTE", "PRODUZIONE", "FATTURA", "TOTALE", "DATA\nCONTABILIZZAZIONE", "RATA\nFATTURA", "CONTO\nCORRENTE"]

        for i, header in enumerate(self.table_headers):
            # crea il container
            column = ctk.CTkFrame(self.payments_table_frame, fg_color="#333333")
            column.grid(row=0, column=i, sticky="nsew", padx=(0, 5), pady=5)

            # imposta peso e uniformità: tutte le colonne "col" si dividono equamente
            self.payments_table_frame.grid_columnconfigure(i, weight=1, uniform="col")

            # la label riempie il suo container
            label = ctk.CTkLabel(column,
                                 text=header,
                                 font=("Arial", 14))
            label.pack(fill="both", expand=True, padx=5, pady=15)

        # Creazione del frame delle cards
        self.payments_cards_frame = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")
        self.payments_cards_frame.pack(padx=0, pady=10, fill="both", expand=True)

        self.add_payment_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.add_payment_frame.pack(padx=0, pady=(5, 20), fill="x")

        self.save_button = ctk.CTkButton(self.add_payment_frame, text="Aggiungi un pagamento",
                                         command=self.open_add_payment_window)
        self.save_button.pack()

        self.show_last_cards()

        #warnings launch
        for card in self.payment_card_list.values():
            ViewUtils.toggle_warning_on_card(card, self.cards_warnings)

    def show_last_cards(self):
        """Mostra solo le spese degli ultimi giorni selezionati dall'utente"""
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

        # Recupera tutte le spese dell'anno corrente
        all_payments = self.payment_controller.retrieve_payments_map_list(include_unpaid_invoice_payments=True)

        # Filtra le spese: solo quelle con data di emissione >= limit_date
        filtered_payments = []
        for payment in all_payments:
            date_str = payment.get(DBPaymentsColumns.PAYMENT_DATE.value)
            if date_str:
                try:
                    # Prova a parsare la data in formato yyyy-mm-dd o yyyy-mm-dd hh:mm:ss
                    try:
                        payment_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        payment_date = datetime.strptime(date_str, "%Y-%m-%d")

                    if payment_date >= limit_date:
                        filtered_payments.append(payment)
                except Exception as e:
                    print(f"Errore nel parsare la data {date_str}: {e}")

        # Svuota le cards attuali
        for card in self.payment_card_list.values():
            card.destroy()
        self.payment_card_list.clear()

        # Ricarica le cards con le spese filtrate
        self.load_payments_chunked(filtered_payments)

        self.sort_cards()

    def handle_show_payment_detail(self, payment_id):
        self.tab_view.set("Pagamenti")  # Cambia tab
        self.open_payment_detail_tab(payment_id)  # Mostra il dettaglio

    def populate_global_infos(self):
        numero_pagamenti = self.payment_controller.count_payments(include_unpaid_invoice_payments = False)
        totale_pagamenti = round(self.payment_controller.calculate_tot_payments(include_unpaid_invoice_payments = False), 2)
        self.global_infos[f"{PaymentsController.PaymentsAggregateData.NUMERO_PAGAMENTI.value}"] = numero_pagamenti
        self.global_infos[f"{PaymentsController.PaymentsAggregateData.TOT_PAGAMENTI.value}"] = f"{totale_pagamenti:.2f}"

    def filter_cards(self, event):
        """Filtra le card in base al testo della barra di ricerca e al tipo di filtro scelto."""
        search_text = self.search_bar.get().lower()
        search_type = self.search_bar_optionMenu.get()

        # Mappatura: ogni chiave associa una tupla (indice, classe_attesa) del widget da cui prelevare il testo
        filter_mapping = {
            "NOME PAGAM.": (0, ctk.CTkButton),  # Bottone
            "NOME CLIENTE": (1, ctk.CTkLabel),
            "NOME PRODUZIONE": (2, ctk.CTkLabel),
            "CONTO": (3, ctk.CTkLabel),
        }

        mapping = filter_mapping.get(search_type)

        # Prima rimuovo tutte le card dal container per avere un layout pulito
        for card in self.payment_card_list.values():
            card.pack_forget()

        # Se il tipo di ricerca non è riconosciuto, riposiziona tutte le card nell'ordine originale
        if mapping is None:
            for card in self.payment_card_list.values():
                card.pack(pady=10, padx=10, fill="x", expand=True)
            return

        idx, expected_class = mapping

        # Itera sulle card nell’ordine originale (grazie al dizionario ordinato)
        for key, card in self.payment_card_list.items():
            children = card.winfo_children()  # Lista dei widget figli
            widget_text = ""
            if len(children) > idx and isinstance(children[idx], expected_class):
                widget_text = children[idx].cget("text")
            # Se il testo (in lowercase) contiene il testo di ricerca, riposiziona la card
            if search_text in widget_text.lower():
                card.pack(pady=10, padx=10, fill="x", expand=True)

    def sort_cards(self):
        """Ordina le cards in base ai criteri selezionati nei menu di ordinamento."""

        # Funzioni di supporto per la conversione dei valori
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

        def _convert_to_date(date_str):
            """Converte una stringa in formato dd-mm-yyyy in un oggetto date per l'ordinamento."""
            from datetime import datetime
            try:
                return datetime.strptime(date_str.strip(), "%d-%m-%Y")
            except (ValueError, TypeError):
                return None

        # Ottieni i criteri di ordinamento
        sort_by = self.order_bar_optionMenu.get()
        sort_order = self.order_bar_optionMenu_types.get()

        # Mappatura: ogni criterio associa una tupla (tipo_di_accesso, parametro, funzione_di_conversione, colonna_db)
        sort_mapping = {
            "TOTALE": ("direct", 4, _convert_to_currency, None),
            "DATA CONTABILIZZAZIONE": ("direct", 5, _convert_to_date, None),
            "DATA CREAZIONE": ("database", 0, _convert_to_datetime, "created_at"),
            # Sostituisci con il nome reale della colonna
            "ULTIMA MODIFICA": ("database", 0, _convert_to_datetime, "updated_at")
            # Sostituisci con il nome reale della colonna
        }

        mapping = sort_mapping.get(sort_by)

        # Se il tipo di ordinamento non è riconosciuto, non fare nulla
        if mapping is None:
            return

        access_type, param, converter, db_column = mapping
        reverse = (sort_order == "DECRESCENTE")

        # Correzione per TOTALE: inverti l'ordinamento
        if sort_by == "TOTALE":
            reverse = not reverse

        # Raccogli tutte le cards e i loro valori di ordinamento
        cards_with_values = []
        for key, card in self.payment_card_list.items():  # Assumendo che si chiami payment_card_list
            children = card.winfo_children()
            sort_value = ""

            if access_type == "direct":
                # Accesso diretto al valore nella card
                if len(children) > param:
                    sort_value = children[param].cget("text")
            elif access_type == "database":
                # Accesso al valore tramite database
                if len(children) > 0:  # Assicurati che ci sia almeno un child
                    payment_name = children[0].cget("text")  # Nome pagamento dal primo child
                    payment_map = self.payment_controller.retrieve_payment_map_by_name(payment_name)
                    if payment_map and db_column:
                        sort_value = payment_map.get(db_column, "")

            # Converti il valore nel tipo appropriato
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
        for card in self.payment_card_list.values():
            card.pack_forget()

        # Riposiziona le cards nell'ordine ordinato
        for _, card, _ in cards_with_values:
            card.pack(pady=10, padx=10, fill="x", expand=True)

    def load_payments_chunked(self, payment_list):

        # Ordina la lista in ordine decrescente (dal più recente al più vecchio)
        payment_list.sort(
            key=lambda x: datetime.strptime(
                x[DBPaymentsColumns.UPDATED_AT.value],
                "%Y-%m-%d %H:%M:%S"
            ) if " " in x[DBPaymentsColumns.UPDATED_AT.value] else datetime.strptime(
                x[DBPaymentsColumns.UPDATED_AT.value],
                "%Y-%m-%d"
            ),
            reverse=True
        )

        # Pre-processing: raccogli i warnings per i pagamenti
        self.collect_payment_warnings(payment_list)

        extractor = ViewUtils.create_extractor_for_payments(
            self.invoices_query_service,
            self.clients_query_service,
            self.productions_query_service,
            self.account_controller
        )

        ViewUtils.process_items_in_chunks(
            widget=self,
            items_list=payment_list,
            add_card_callback=self.add_payment_card,
            extract_args_callback=extractor,
            cards_frame=self.payments_cards_frame
        )

        for pay_name, warning in self.cards_warnings.items():
            self.attach_warning_on_a_card(pay_name, warning)

    def collect_payment_warnings(self, payments_map_list):
        """Raccoglie tutti i warnings per i pagamenti prima del processing"""
        for payment in payments_map_list:
            if payment:
                payment_name = payment[DBPaymentsColumns.PAYMENT_NAME.value]
                invoice_id = payment[DBPaymentsColumns.INVOICE_ID.value]
                invoice = self.invoices_query_service.retrieve_invoice_map_by_id(invoice_id)
                Invoice_creation_date = datetime.strptime(invoice.get(DBInvoicesColumns.DATA_CREAZIONE.value),
                                                          "%Y-%m-%d")

                # Warning 1: fattura stornata
                if invoice[DBInvoicesColumns.STATUS.value] == InvoiceSatus.STORNATA.value:
                    self.cards_warnings[payment_name] = "Questo pagamento fa riferimento ad una fattura stornata,\n" \
                                                        "modificare i dati del pagamento per mantenere la consistenza dei dati.\n" \
                                                        "Si consiglia di eliminare questo pagamento o collegarlo alla fattura corretta."

                # Warning 2: fattura modificata dopo il pagamento
                else:
                    invoice_update_date = datetime.strptime(invoice[DBInvoicesColumns.UPDATED_AT.value],
                                                            "%Y-%m-%d %H:%M:%S")
                    payment_update_date = datetime.strptime(payment[DBPaymentsColumns.UPDATED_AT.value],
                                                            "%Y-%m-%d %H:%M:%S")
                    if invoice_update_date > payment_update_date:
                        self.cards_warnings[payment_name] = (
                            "Questo pagamento fa riferimento ad una fattura i cui dati sono stati modificati.\n"
                            "Controllare la consistenza dei dati di questo pagamento.\n"
                        )

                if  Invoice_creation_date.year != datetime.now().year:
                        self.cards_warnings[payment_name] = (
                            f"Questo pagamento riguarda l'anno contabile {Invoice_creation_date.year}.\n"
                            "Stai visualizzando questo pagamento perchè è collegato ad una fattura non interamente "
                            "saldata durante il suo anno contabile di riferimento.\n"
                            "Questo pagamento non viene conteggiato all'interno di questo anno contabile."
                        )



    def open_add_payment_window(self):
        self.add_payment_window = ctk.CTkToplevel(self)
        self.add_payment_window.title("Aggiungi Nuovo Pagamento")

        # Assicurati che la finestra rimanga sopra
        self.add_payment_window.lift()  # Porta la finestra sopra quella principale
        self.add_payment_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

        self.add_payment_window.geometry("550x700")

        self.payment_window_scrollableFrame = ctk.CTkScrollableFrame(self.add_payment_window)
        self.payment_window_scrollableFrame.pack(fill="both", expand=True)

        self.nome_fattura_string = "NOME FATTURA"
        self.nome_conto_string = "NOME CONTO"

        self.entry_fields = {
            self.nome_fattura_string: FilterableComboBox,
            DBPaymentsColumns.LINKED_RATA.value: ctk.CTkOptionMenu,
            DBPaymentsColumns.PAYMENT_NAME.value: ctk.CTkEntry,
            DBPaymentsColumns.PAYMENT_AMOUNT.value: ctk.CTkEntry,
            DBPaymentsColumns.PAYMENT_DATE.value: Calendar,
            self.nome_conto_string: ctk.CTkOptionMenu,
        }

        self.error_fields = {
            DBPaymentsColumns.PAYMENT_NAME.value: ctk.CTkLabel,
            DBPaymentsColumns.PAYMENT_AMOUNT.value: ctk.CTkLabel,
            DBPaymentsColumns.LINKED_RATA.value: ctk.CTkLabel
        }

        self.payment_widgets = {}
        self.error_labels = {}
        self.payment_labels = {}

        # Creo i labels e i widgets
        for i, (label_text, widget_class) in enumerate(self.entry_fields.items()):
            # Etichetta
            label = ctk.CTkLabel(self.payment_window_scrollableFrame, text=label_text)
            # disegno i labels
            if i == 0:
                label.pack(pady=5)
            else:
                label.pack(pady=(35, 0))

            self.payment_labels[label_text] = label

            # creo i widgets
            if label_text == self.nome_fattura_string:
                VF_invoice_list = self.construct_invoices_list_view_friendly()
                reversed_invoices = list(VF_invoice_list.values())[::-1]
                widget = widget_class(parent=self.payment_window_scrollableFrame, placeholder="Cerca", autofill=True,
                                      values=reversed_invoices, command=lambda selected_value: self.toggle_linked_rata(selected_value))
            elif label_text == self.nome_conto_string:
                widget = widget_class(self.payment_window_scrollableFrame,
                                      values=[f"{item[DBAccountsColumns.NAME.value]}" for item in
                                              self.account_controller.retrieve_accounts_map_list()])
            elif label_text == DBPaymentsColumns.LINKED_RATA.value:
                widget = widget_class(self.payment_window_scrollableFrame,
                                      values=["1", "2", "3"],
                                      command = lambda selected_value: self.control_linked_rata(selected_value))
            elif label_text == DBPaymentsColumns.PAYMENT_DATE.value:
                widget = widget_class(self.payment_window_scrollableFrame, date_pattern=ViewUtils.date_pattern)
            else:
                widget = widget_class(self.payment_window_scrollableFrame)

            widget.pack(pady=5, padx=10, fill="x", expand=True)

            self.payment_widgets[label_text] = widget

            if self.error_fields.get(label_text) is not None:
                error_label = ctk.CTkLabel(self.payment_window_scrollableFrame, text="")
                error_label.pack(pady=(0, 15))
                self.error_labels[label_text] = error_label

        self.autofill_payment_amount()
        self.control_linked_rata("1")

        # Bottone per salvare
        self.save_button = ctk.CTkButton(
            self.payment_window_scrollableFrame,
            text="Salva Pagamento",
            command=self.save_payment_data
        )
        self.save_button.pack(pady=(35, 15))

        self.toggle_linked_rata(self.payment_widgets[self.nome_fattura_string].get_value())

        # Aggiungi validazione agli eventi di perdita del focus
        self.payment_widgets[DBPaymentsColumns.PAYMENT_NAME.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.payment_widgets[DBPaymentsColumns.PAYMENT_NAME.value],
            lambda val: val.strip() != "",
            self.error_labels[DBPaymentsColumns.PAYMENT_NAME.value],
            "Il campo non può essere vuoto."
        ))

        self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value],
            lambda val: re.fullmatch(r"^\d+(\.\d{2})?$", val.strip()) is not None,
            self.error_labels[DBPaymentsColumns.PAYMENT_AMOUNT.value],
            "Inserimento non valido: inserire un numero monetario con due cifre decimali (es. 123.45)"
        ))

    def add_payment_card(self, payment_id, payment_name, amount, payment_date, linked_rata, client_name, production_name, invoice_name, nome_conto):
        """
        Aggiunge una card di pagamento alla scrollable frame con i dati specificati.

        :param payment_id: ID univoco del pagamento nel database.
        :param payment_name: Nome del pagamento.
        :param amount: Importo del pagamento.
        :param payment_date: Data in cui è stato effettuato il pagamento.
        :param linked_rata: Identificativo o numero della rata collegata, se applicabile.
        :param client_name: Nome del cliente associato al pagamento.
        :param production_name: Nome della produzione correlata al pagamento.
        :param invoice_name: Nome della fattura correlata al pagamento.
        :param nome_conto: Nome del conto bancario associato al pagamento.
        """
        # Creazione della card
        card = ctk.CTkFrame(self.payments_cards_frame, fg_color="dimgray")
        card.pack(pady=10, padx=8, fill="x", expand=True)  # Spaziatura tra le card

        # Dati da visualizzare nella card
        data = [payment_name, client_name, production_name, invoice_name, round(amount, 2), ViewUtils.invert_data_string(payment_date), linked_rata, nome_conto]
        units = ["", "", "", "", "€", "", "", ""]
        n_cols = len(data)  # 8 colonne totali

        # Configura il grid della card: 1 riga, n_cols colonne uguali
        for c in range(n_cols):
            card.grid_columnconfigure(c, weight=1, uniform="clientcol")
        card.grid_rowconfigure(0, weight=1)

        # 0) Bottone "nome"
        btn = ctk.CTkButton(
            card,
            text=payment_name,
            command=lambda pid=payment_id: self.open_payment_detail_tab(pid)
        )
        btn.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        # 1..7) Le altre colonne
        for idx, val in enumerate(data[1:], start=1):
            text = f"{val} {units[idx]}"
            lbl = ctk.CTkLabel(card, text=text, font=("Arial", 14))
            lbl.grid(row=0, column=idx, sticky="nsew", padx=5, pady=10)

        # Salva la card per eventuale successivo accesso
        self.payment_card_list[payment_name] = card

        # Se esiste un warning associato al nome del pagamento, aggiungi il tooltip
        if payment_name in self.cards_warnings:
            ViewUtils.add_tooltip(btn, self.cards_warnings[payment_name])

    def auto_compile_name_entry(self, selected_value):
        return

    def save_payment_data(self):
        payment_data = {}

        # riempi il dizionario con i dati dei widgets primari
        for label_text, widget in self.payment_widgets.items():
            if isinstance(widget, ctk.CTkEntry) or isinstance(widget, ctk.CTkOptionMenu):
                payment_data[label_text] = widget.get().strip()
            elif isinstance(widget, Calendar):
                payment_data[label_text] = widget.get_date()
            elif isinstance(widget, ctk.CTkTextbox):
                payment_data[label_text] = widget.get("1.0", "end-1c").strip()  # Recupera il testo dal Textbox
            elif isinstance(widget, FilterableComboBox):
                payment_data[label_text] = widget.get_value()

        #sistemo il nome della fattura che è ViewFriendly:
        nome_fattura_array = payment_data[self.nome_fattura_string].strip().split(" - ")
        nome_fattura_ricostruito = nome_fattura_array[0] + " - " + nome_fattura_array[1] + " - " + nome_fattura_array[2]
        invoice_id = self.invoices_query_service.retrieve_invoice_map_by_name(nome_fattura_ricostruito)[DBInvoicesColumns.ID.value]
        payment_data[DBPaymentsColumns.INVOICE_ID.value] = invoice_id

        ctrl_linked_rata = self.control_linked_rata(payment_data[DBPaymentsColumns.LINKED_RATA.value])
        confirmation = True

        if ctrl_linked_rata:
            confirmation = ViewUtils.ask_confirmation_popup(self.add_payment_window, "La rata selezionata presenta già un pagamento associato\nsei sicuro di voler continuare?", "CONFERMA OPERAZIONE")

        if confirmation:
            # chiamata al controller per salvare i dati
            success, message = self.payment_controller.save_payment(payment_data)

        if success:
            #aggiorno il controller delle fatture
            self.update_controller.update_invoices(invoice_id)
            self.update_controller.on_adding_payment()

            # prendo l'ID della fattura appena creata
            payment_map = self.payment_controller.retrieve_last_payment_insert_map()
            print(f"Pagamento {payment_data[DBPaymentsColumns.PAYMENT_NAME.value]} salvato con successo")

            invoice = self.invoices_query_service.retrieve_invoice_map_by_id(payment_map[DBPaymentsColumns.INVOICE_ID.value])
            invoice_name = invoice[DBInvoicesColumns.NUMERO_FATTURA.value]
            client = self.clients_query_service.retrieve_client_map_by_id(invoice[DBInvoicesColumns.ID_CLIENTE.value])
            client_name = client[DBClientsColumns.NAME.value]
            production = self.production_controller.retrieve_production_map_by_id(invoice[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value])
            production_name = production[DBProductionsColumns.NAME.value]
            conto = self.account_controller.retrieve_account_map_by_id(payment_map[DBPaymentsColumns.CONTO_ID.value])
            nome_conto = conto[DBAccountsColumns.NAME.value]

            self.add_payment_card(
                payment_map[DBPaymentsColumns.ID.value],
                payment_map[DBPaymentsColumns.PAYMENT_NAME.value],
                payment_map[DBPaymentsColumns.PAYMENT_AMOUNT.value],
                payment_map[DBPaymentsColumns.PAYMENT_DATE.value],
                payment_map[DBPaymentsColumns.LINKED_RATA.value],
                client_name,
                production_name,
                invoice_name,
                nome_conto
            )

            self.clear_class_variable()
            self.add_payment_window.destroy()
            self.show_last_cards()
        else:
            print(message)
            ViewUtils.show_error_popup(self.add_payment_window, "ERRORE", message)

    def construct_invoices_list_view_friendly(self, year:int = None):
        VF_invoice_list = {}

        for invoice in self.invoices_query_service.retrieve_invoices_map_list(year=year):
            invoicer_second_name = self.user_controller.retrieve_user_map_by_id(invoice[DBInvoicesColumns.ID_UTENTE.value])[DBUsersColumns.LAST_NAME.value]
            client_name = self.clients_query_service.retrieve_client_map_by_id(invoice[DBInvoicesColumns.ID_CLIENTE.value])[DBClientsColumns.NAME.value]

            VF_invoice_list[invoice[DBInvoicesColumns.ID.value]] =  invoice[DBInvoicesColumns.NUMERO_FATTURA.value] + " - " + client_name

        return VF_invoice_list

    def toggle_linked_rata(self, selected_value):
        invoice_name = selected_value.split(" - ")
        invoice_name_reconstructed = invoice_name[0] + " - " + invoice_name[1] + " - " + invoice_name[2]
        invoice = self.invoices_query_service.retrieve_invoice_map_by_name(invoice_name_reconstructed)
        rateizzazione = int(invoice[DBInvoicesColumns.NUMERO_RATE.value])
        widget = self.payment_widgets[DBPaymentsColumns.LINKED_RATA.value]
        if rateizzazione == int(InvoiceController.Rateizzazione.UNA.value):
            widget.set("1")
            widget.configure(state=tk.DISABLED)
        if rateizzazione == int(InvoiceController.Rateizzazione.TRE.value):
            widget.configure(values=["1", "2", "3"], state=tk.NORMAL)

        self.autofill_payment_amount()
        selected_rata = self.payment_widgets[DBPaymentsColumns.LINKED_RATA.value].get()
        self.control_linked_rata(selected_rata)

    def clear_class_variable(self):  #potrebbe non servire in quanto vengono inizializzate all'apertura della funzione
        self.payment_widgets.clear()
        self.payment_widgets.clear()

    def autofill_payment_amount(self):
        # prendo la fattura di riferimento del pagamento
        VF_invoice_name = self.payment_widgets[self.nome_fattura_string].get_value()
        invoice_name_array = VF_invoice_name.split(" - ")
        invoice_name = invoice_name_array[0] + " - " + invoice_name_array[1] + " - " + invoice_name_array[2] if len(invoice_name_array) == 4 else invoice_name_array[0] + " - " + invoice_name_array[1]
        invoice = self.invoices_query_service.retrieve_invoice_map_by_name(invoice_name)
        invoice_amount = float(invoice[DBInvoicesColumns.NETTO_A_PAGARE.value])
        invoice_rateiz = invoice[DBInvoicesColumns.NUMERO_RATE.value]

        self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].delete(0, tk.END)
        if int(invoice_rateiz) == int(InvoiceController.Rateizzazione.UNA.value):
            self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].insert(0, f"{invoice_amount:.2f}")
        elif int(invoice_rateiz) == int(InvoiceController.Rateizzazione.TRE.value):
            amount = round(invoice_amount/3, 2)
            self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].insert(0, f"{amount:.2f}")

    def control_linked_rata(self, selected_value):
        # prendo la fattura di riferimento del pagamento
        VF_invoice_name = self.payment_widgets[self.nome_fattura_string].get_value()
        invoice_name_array = VF_invoice_name.split(" - ")
        invoice_name = invoice_name_array[0] + " - " + invoice_name_array[1] + " - " + invoice_name_array[2]
        invoice = self.invoices_query_service.retrieve_invoice_map_by_name(invoice_name)

        netto_rate_fattura = {
            "1" : 0.0,
            "2" : 0.0,
            "3" : 0.0
        }

        netto_rate_pagate = {
            "1": 0.0,
            "2": 0.0,
            "3": 0.0
        }

        if int(invoice[DBInvoicesColumns.NUMERO_RATE.value]) == int(InvoiceController.Rateizzazione.UNA.value):
            netto_rate_fattura["1"] = float(invoice[DBInvoicesColumns.NETTO_A_PAGARE.value])
            netto_rate_fattura["2"] = 0.0
            netto_rate_fattura["3"] = 0.0
        elif int(invoice[DBInvoicesColumns.NUMERO_RATE.value]) == int(InvoiceController.Rateizzazione.TRE.value):
            rata = float(invoice[DBInvoicesColumns.NETTO_A_PAGARE.value]) / 3
            netto_rate_fattura["1"] = rata
            netto_rate_fattura["2"] = rata
            netto_rate_fattura["3"] = rata

        rate_saldate = {
            "1" : False,
            "2" : False,
            "3" : False
        }

        #calcolo il totale dei pagamenti per rata
        payments = self.payment_controller.retrieve_payments_map_list_by_invoice_id(invoice[DBInvoicesColumns.ID.value])
        for payment in payments:
            if int(payment[DBPaymentsColumns.LINKED_RATA.value]) == 1:
                netto_rate_pagate["1"] = netto_rate_pagate["1"] + float(payment[DBPaymentsColumns.PAYMENT_AMOUNT.value])
            elif int(payment[DBPaymentsColumns.LINKED_RATA.value]) == 2:
                netto_rate_pagate["2"] = netto_rate_pagate["2"] + float(payment[DBPaymentsColumns.PAYMENT_AMOUNT.value])
            elif int(payment[DBPaymentsColumns.LINKED_RATA.value]) == 3:
                netto_rate_pagate["3"] = netto_rate_pagate["3"] + float(payment[DBPaymentsColumns.PAYMENT_AMOUNT.value])

        for i in ["1", "2", "3"]:
            tot_mancante = netto_rate_fattura[i] - netto_rate_pagate[i]
            if netto_rate_pagate[i] >= netto_rate_fattura[i] or (5 > tot_mancante > 0):
                rate_saldate[i] = True

        if rate_saldate[str(selected_value)]:
            self.error_labels[DBPaymentsColumns.LINKED_RATA.value].configure(
                text=f"La rata {selected_value} è già interamente saldata ({round(netto_rate_pagate[str(selected_value)], 2)}€)", text_color="#e39e27")
            self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].delete(0, tk.END)
            self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].insert(0, "0.00")
            self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].configure(border_color="#e39e27")
            return True
        else:
            tot_mancante = (netto_rate_fattura[str(selected_value)] - netto_rate_pagate[str(selected_value)])
            self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].configure(border_color="gray")
            if netto_rate_pagate[str(selected_value)] > 0 and tot_mancante >= 5:
                self.error_labels[DBPaymentsColumns.LINKED_RATA.value].configure(
                    text=f"Totale mancante da saldare della rata {selected_value}: {round(tot_mancante, 2)}€", text_color="#e39e27")
                self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].delete(0, tk.END)
                self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].insert(0, round(tot_mancante, 2))
            else:
                self.error_labels[DBPaymentsColumns.LINKED_RATA.value].configure(text="", text_color="#e39e27")
                self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].configure(border_color="gray")
                self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].delete(0, tk.END)
                self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].insert(0, round(tot_mancante, 2))

    def open_modify_payment(self, payment_id):

        #prendo i dati della produzione
        payment = self.payment_controller.retrieve_payment_map_by_id(payment_id, True)
        invoice = self.invoices_query_service.retrieve_invoice_map_by_id(payment[DBPaymentsColumns.INVOICE_ID.value])
        invoice_name = invoice[DBInvoicesColumns.NUMERO_FATTURA.value]
        client_name = self.clients_query_service.retrieve_client_map_by_id(invoice[DBInvoicesColumns.ID_CLIENTE.value])[DBClientsColumns.NAME.value]
        invoice_name = invoice_name + " - " + client_name
        conto_name = self.account_controller.retrieve_account_map_by_id(payment[DBPaymentsColumns.CONTO_ID.value])[DBAccountsColumns.NAME.value]

        self.open_add_payment_window()

        #configuro la finestra
        #self.add_production_window.configure(title=f"Modifica i dati della produzione {production[DBProductionsColumns.NAME.value]}")
        self.add_payment_window.title(f"Modifica i dati del pagamento {payment[DBPaymentsColumns.PAYMENT_NAME.value]}")
        self.save_button.configure(text="Salva Modifiche", command=self.modify_payment_data)
        self.payment_widgets[DBPaymentsColumns.PAYMENT_NAME.value].delete(0, tk.END)
        self.payment_widgets[DBPaymentsColumns.PAYMENT_NAME.value].insert(0, payment[DBPaymentsColumns.PAYMENT_NAME.value])
        self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].delete(0, tk.END)
        self.payment_widgets[DBPaymentsColumns.PAYMENT_AMOUNT.value].insert(0, payment[DBPaymentsColumns.PAYMENT_AMOUNT.value])
        self.payment_widgets[DBPaymentsColumns.PAYMENT_DATE.value].selection_set(payment[DBPaymentsColumns.PAYMENT_DATE.value])
        self.payment_widgets[self.nome_fattura_string].set(invoice_name)
        self.payment_widgets[DBPaymentsColumns.LINKED_RATA.value].set(payment[DBPaymentsColumns.LINKED_RATA.value])
        self.payment_widgets[self.nome_conto_string].set(conto_name)

    def modify_payment_data(self):
        return

    # funzione da passare all'updater come callback
    def attach_warning_on_a_card(self, payment_name, warning):
        #cerco tra le cards quella che mi interessa
        for card in self.payment_card_list.values():
            children = card.winfo_children()
            for child in children:
                if isinstance(child, ctk.CTkButton):
                    button_text = child.cget("text")  # oppure child["text"]
                    if button_text == payment_name:
                        self.cards_warnings[payment_name] = warning
                        card = card
                        continue

        ViewUtils.toggle_warning_on_card(card, self.cards_warnings)

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



class PaymentDetailView(ctk.CTkFrame):
    def __init__(self, parent, back_callback, invoice_controller, payment_controller,
                 account_controller, client_controller, production_controller,
                 update_controller, db_model, event_bus):
        super().__init__(parent)
        self.invoice_controller = invoice_controller
        self.payment_controller = payment_controller
        self.account_controller = account_controller
        self.client_controller = client_controller
        self.production_controller = production_controller
        self.db_model = db_model
        self.back_callback = back_callback
        self.update_controller = update_controller
        self.event_bus = event_bus
        self.current_invoice_id = None
        self.parent = parent

        self.configure(fg_color="transparent")

        # Widgets persistenti (vanno creati una volta sola)
        self.head_frame = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.back_button = ctk.CTkButton(
            self.head_frame,
            text="Elenco Pagamenti",
            command=self._cleanup_and_go_back
        )
        self.title_label = ctk.CTkLabel(self.head_frame, font=("Arial", 22, "bold"))

        self.payment_info_widgets: dict[str, ctk.CTkEntry | ctk.CTkOptionMenu] = {}

        self.nome_conto_string = "CONTO"
        self.nome_cliente_string = "CLIENTE"
        self.nome_user_string = "UTENTE"
        self.nome_fattura_string = "FATTURA ASSOCIATA"
        self.nome_produzione_associata_string = "PRODUZIONE ASSOCIATA"

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

    def create_detail_tab(self, payment_id):
        """Ricrea la vista dettaglio per un pagamento specifico"""
        self.current_payment_id = payment_id

        # 1. Pulizia dei widget precedenti
        self._clear_content()

        # 2. Caricamento dati
        self.payment = self.payment_controller.retrieve_payment_map_by_id(payment_id)

        #prendo i dati della fattura associata
        invoice = self.invoices_query_service.retrieve_invoice_map_by_id(self.payment[DBPaymentsColumns.INVOICE_ID.value])

        # prendo il nome del conto:
        id_conto = self.payment[DBPaymentsColumns.CONTO_ID.value]
        conto = self.account_controller.retrieve_account_map_by_id(id_conto)
        nome_conto = conto[DBAccountsColumns.NAME.value] if conto else "Conto non trovato"
        self.payment[self.nome_conto_string] = nome_conto

        # prendo il nome del cliente
        id_cliente = invoice[DBInvoicesColumns.ID_CLIENTE.value]
        cliente = self.clients_query_service.retrieve_client_map_by_id(id_cliente)
        nome_cliente = cliente[DBClientsColumns.NAME.value] if cliente else "Cliente non trovato"
        invoice[self.nome_cliente_string] = nome_cliente

        # prendo il nome della produzione associata
        id_prod = invoice[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value]
        prod = self.productions_query_service.retrieve_production_map_by_id(id_prod)
        nome_produzione = prod[DBProductionsColumns.NAME.value] if prod else "Produzione non trovata"
        invoice[self.nome_produzione_associata_string] = nome_produzione

        # 3. Aggiornamento elementi persistenti
        self.title_label.configure(
            text=f"{self.payment[DBPaymentsColumns.PAYMENT_NAME.value]}")

        # 4. Creazione contenuti dinamici
        self._create_payment_info_section(self.payment)
        self.toggle_edit(self.content_frame)

        self.wrapper_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.wrapper_frame.pack(padx=15, pady=(90, 0), fill="both", expand=True)
        self.wrapper_frame2 = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.wrapper_frame2.pack(padx=15, pady=(90, 90), fill="both", expand=True)

        #self._create_payments_history()
        #self._create_production_expenses_history()

    def _create_payment_info_section(self, payment_data):
        # Campi derivati per i pagamenti (se necessario)
        self.derived_fields_payments = {
            # Potresti aggiungere campi calcolati qui se necessario
        }

        self.entry_fields_payments = {
            DBPaymentsColumns.PAYMENT_DATE.value: {
                "type": Calendar,
                "label": "Data Pagamento",
                "section": "Dati Generali"
            },

            # Dati Fiscali
            DBPaymentsColumns.PAYMENT_AMOUNT.value: {
                "type": ctk.CTkEntry,
                "label": "Importo Pagato (€)",
                "section": "Dati Fiscali"
            },

            # Collegamenti
            self.nome_fattura_string: {
                "type": ctk.CTkOptionMenu,
                "label": "Fattura Associata",
                "section": "Collegamenti",
                "values": [f"{i[DBInvoicesColumns.NUMERO_FATTURA.value]}"
                           for i in self.invoices_query_service.retrieve_invoices_map_list()]
            },
            DBPaymentsColumns.LINKED_RATA.value: {
                "type": ctk.CTkOptionMenu,
                "label": "Rata Associata",
                "section": "Collegamenti"
            },
            self.nome_produzione_associata_string: {
                "type": ctk.CTkLabel,
                "label": "Produzione Associata",
                "section": "Collegamenti",
                "values": ["1", "2", "3"]
            },
            self.nome_conto_string: {
                "type": ctk.CTkOptionMenu,
                "label": "Conto",
                "section": "Collegamenti",
                "values": [c[DBAccountsColumns.NAME.value] for c in
                           self.account_controller.retrieve_accounts_map_list()]
            },

            # Campi statici
            DBPaymentsColumns.CREATED_AT.value: {
                "type": ctk.CTkLabel,
                "label": "Data Creazione",
                "section": "Note"
            },
            DBPaymentsColumns.UPDATED_AT.value: {
                "type": ctk.CTkLabel,
                "label": "Ultimo Aggiornamento",
                "section": "Note"
            }
        }

        self.error_fields_payments = {
            DBPaymentsColumns.PAYMENT_AMOUNT.value: "Valore numerico con massimo 2 decimali",
            DBPaymentsColumns.PAYMENT_DATE.value: "Data obbligatoria"
        }

        validation_rules = {
            DBPaymentsColumns.PAYMENT_AMOUNT.value: (
                lambda val: re.fullmatch(r"^\d+(\.\d{1,2})?$", val),
                "Formato valido: 1234.56"
            ),
            DBPaymentsColumns.PAYMENT_DATE.value: (
                lambda val: val.strip() != "",
                "Campo obbligatorio"
            )
        }

        # Inizializzazione strutture dati
        self.payment_info_widgets = {}
        self.payment_info_labels = {}
        self.error_labels_payments = {}
        sections = {}

        payment_name = payment_data[DBPaymentsColumns.PAYMENT_NAME.value]
        warning = self.parent.cards_warnings.get(payment_name)
        border_color = "#2659ab" if warning is None else "#fcba03"

        #warning frame
        self.warning_frame = ctk.CTkFrame(self.content_frame, border_width=2, border_color=border_color)
        self.toggle_warning_frame(payment_data[DBPaymentsColumns.PAYMENT_NAME.value])
        ctk.CTkLabel(self.warning_frame, text=warning if warning is not None else "", font=("Arial", 16)).pack(padx=30, pady=(20, 20), side="left")
        self.remove_warning_btn = ctk.CTkButton(self.warning_frame, text="OK, è tutto in ordine", command=lambda: self.remove_warning(payment_name))
        self.remove_warning_btn.pack(padx=30, pady=(20, 20), side="right")

        # Creazione frame principale
        self.info_frame = ctk.CTkFrame(self.content_frame, border_width=2, border_color=border_color)
        self.info_frame.pack(fill="both", expand=True, pady=(5, 10), padx=(5, 25))

        # Configurazione griglia a 2 colonne (meno campi)
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
        for field, config in self.entry_fields_payments.items():
            section = sections[config["section"]]
            frame = section["frame"]
            row = section["row"]

            # Creazione label
            lbl = ctk.CTkLabel(frame, text=config["label"] + ":")
            self.payment_info_labels[field] = lbl

            lbl.grid(row=row, column=0, sticky="w", padx=(15, 5), pady=(5, 5))

            # Creazione widget
            if config["type"] == ctk.CTkLabel:
                value = str(payment_data.get(field, ""))
                widget = config["type"](frame, text=value)
                widget.grid(row=row, column=1, sticky="w", padx=(5, 15), pady=(5, 5))
            else:
                if config["type"] == ctk.CTkOptionMenu:
                    widget = config["type"](frame, values=config.get("values", []))
                    widget.set(payment_data.get(field, config.get("values", [""])[0]))

                elif config["type"] == Calendar:
                    widget = config["type"](frame, date_pattern=ViewUtils.date_pattern)
                    value = payment_data.get(field, "")
                    widget.selection_set(str(value)) if value else widget.selection_set(datetime.today())
                else:
                    widget = config["type"](frame)
                    value = str(payment_data.get(field, ""))
                    widget.insert(0, value)

                widget.grid(row=row, column=1, sticky="ew", padx=(5, 15), pady=(5, 5))

            self.payment_info_widgets[field] = widget

            # Gestione validazione
            if field in validation_rules:
                validation_func, error_message = validation_rules[field]

                error_lbl = ctk.CTkLabel(frame, text="", text_color="#e8e5dc")
                error_lbl.grid(row=row + 1, column=1, sticky="w", padx=5, pady=(0, 10))
                self.error_labels_payments[field] = error_lbl

                widget.bind("<FocusOut>",
                            lambda e, w=widget, vl=validation_func, el=error_lbl, em=error_message:
                            ViewUtils.validate_entry(w, vl, el, em))

                section["row"] += 2
            else:
                section["row"] += 1


        invoice_id = self.payment[DBPaymentsColumns.INVOICE_ID.value]
        invoice = self.invoices_query_service.retrieve_invoice_map_by_id(invoice_id)
        prod_id = invoice[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value]
        production = self.productions_query_service.retrieve_production_map_by_id(prod_id)
        self.payment_info_widgets[self.nome_produzione_associata_string].configure(
            text=production[DBProductionsColumns.NAME.value])

        buttons_frame = ctk.CTkFrame(self.info_frame, fg_color="#2b2b2b")
        buttons_frame.grid(row=2, column=0, columnspan=2, pady=(5, 15), padx=20, sticky="WE")

        # Bottone Salva
        self.save_payment_btn = ctk.CTkButton(buttons_frame, text="Salva Pagamento", command=self.save_payment_mod)
        self.save_payment_btn.pack(padx=(400, 10), pady=(20, 20), side="left")

        # Bottone Elimina
        self.delete_btn = ctk.CTkButton(buttons_frame, text="Elimina Pagamento",
                                        fg_color="#8B0000", hover_color="#A52A2A",
                                        command=self.delete_payment)
        self.delete_btn.pack(padx=10, pady=(20, 20), side="right", anchor="e")

    def save_payment_mod(self):
        nome_conto = self.payment_info_widgets[self.nome_conto_string].get()
        conto = self.account_controller.retrieve_account_map_by_name(nome_conto)
        id_conto = conto[DBAccountsColumns.ID.value] if conto else None

        nome_fattura = self.payment_info_widgets[self.nome_fattura_string].get()
        fattura = self.invoices_query_service.retrieve_invoice_map_by_name(nome_fattura)
        id_fattura = fattura[DBInvoicesColumns.ID.value]

        payment_data = {
            DBPaymentsColumns.PAYMENT_NAME.value: self.payment[
                DBPaymentsColumns.PAYMENT_NAME.value],
            DBPaymentsColumns.PAYMENT_AMOUNT.value: self.payment_info_widgets[
                DBPaymentsColumns.PAYMENT_AMOUNT.value].get().strip(),
            DBPaymentsColumns.PAYMENT_DATE.value: self.payment_info_widgets[
                DBPaymentsColumns.PAYMENT_DATE.value].get_date(),
            DBPaymentsColumns.LINKED_RATA.value: self.payment_info_widgets[
                DBPaymentsColumns.LINKED_RATA.value].get(),
            DBPaymentsColumns.INVOICE_ID.value: id_fattura,
            DBPaymentsColumns.CONTO_ID.value: id_conto,
        }

        # Chiamata al controller per salvare i dati
        success, message = self.payment_controller.update_payment(self.current_payment_id, payment_data)
        if success:
            print(
                f"Pagamento {self.payment_controller.retrieve_payment_map_by_id(self.current_payment_id)[DBPaymentsColumns.PAYMENT_NAME.value]} salvato con successo")
            ViewUtils.show_confirm_popup_2(self.content_frame, "SALVATAGGIO COMPLETATO", message)
            self.switch_modify.deselect()
            self.toggle_edit(self.content_frame)

        else:
            # Mostra il messaggio d'errore
            print(message)
            ViewUtils.show_error_popup(self.content_frame, "ERRORE", message)

    def delete_payment(self):
        confirmation = ViewUtils.ask_confirmation_popup(self.content_frame, "Stai per eliminare questo pagamento.\nDesideri continuare ?", "ELIMINAZIONE PAGAMENTO" )
        if confirmation:
            success, message = self.payment_controller.delete_payment(self.current_payment_id)
            if success:
                ViewUtils.show_confirm_popup_2(self.content_frame, "PAGAMENTO ELIMINATO CON SUCCESSO", message)
                print(f"Pagamento {self.payment[DBPaymentsColumns.PAYMENT_NAME.value]} eliminato correttamente")
            else:
                # Mostra il messaggio d'errore
                print(message)
                ViewUtils.show_error_popup(self.content_frame, "ERRORE", message)

    def toggle_edit(self, parent):
        """
        Abilita o disabilita la modifica dei widget nella finestra di modifica utente.
        """
        # Determina lo stato (abilitato/disabilitato) in base al valore dello switch
        state = ctk.NORMAL if self.switch_modify.get() else ctk.DISABLED

        # Cambia anche lo stato del pulsante Salva
        self.save_payment_btn.configure(state=state)
        self.delete_btn.configure(state=state)
        self.remove_warning_btn.configure(state=state)

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

    def toggle_warning_frame(self, payment_name):
        warning = self.parent.cards_warnings.get(payment_name)
        if warning is not None:
            self.warning_frame.pack(fill="both", expand=True, pady=10, padx=(5, 25))
        else:
            self.warning_frame.pack_forget()

    def remove_warning(self, payment_name):
        self.save_payment_mod()
        self.parent.cards_warnings.pop(payment_name)
        self.info_frame.configure(border_color="#2659ab")
        #retrieve the card
        card = self.parent.payment_card_list[payment_name]
        ViewUtils.toggle_warning_on_card(card, self.parent.cards_warnings)
        self.toggle_warning_frame(payment_name)
        self.remove_warning_btn.configure(state=ctk.DISABLED)

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

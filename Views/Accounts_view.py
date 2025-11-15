import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
from tkcalendar import Calendar
from Views.View_utils import ViewUtils
from Controllers import PaymentsController, InvoiceController, UserController, ControllerUtils, SupplierController
from Model import DBInvoicesColumns, DBUsersColumns, DBClientsColumns, DBPaymentsColumns, DBProductionsColumns, DBAccountsColumns, DBTransfersColumns
from datetime import datetime
import re
from enum import Enum

class AccountsView(ctk.CTkFrame):

    def __init__(self, db_model, account_controller, update_controller, transfer_controller, config_manager, catalogo_elenchi, analyzer, tabview, event_bus):
        super().__init__(tabview.tab("Conti"))

        self.db_model = db_model
        self.account_controller = account_controller
        self.update_controller = update_controller
        self.config_manager = config_manager
        self.transfer_controller = transfer_controller
        self.catalogo_elenchi = catalogo_elenchi
        self.analyzer = analyzer
        self.tabview = tabview
        self.tab = tabview.tab("Conti")
        self.event_bus = event_bus

        self.transfers_view = TransfersView(self.db_model, self.account_controller, self.update_controller, self.transfer_controller, self.config_manager, self.catalogo_elenchi, self.analyzer)

        self.global_infos = {}
        self.amount_aggregate_labels = {}
        self.balance_labels = {}
        self.number_of_account_cards = 0
        self.account_cards = {}

        self.account_widgets = {}
        self.account_labels = {}

        self.update_controller.register_on_adding_payment_view_cllbks(self.update_accounts_balances)
        self.update_controller.register_on_adding_expense_view_cllbks(self.update_accounts_balances)
        self.update_controller.register_on_adding_transfer_view_cllbks(self.update_accounts_balances)

        # Container principale
        self.main_container = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.detail_container = ctk.CTkFrame(self, fg_color="#2b2b2b")

        # Vista dettaglio
        self.account_detail_view = AccountDetailView(
            parent=self,
            back_callback=self.show_main_view,
            account_controller=self.account_controller,
            update_controller= self.update_controller,
            db_model=db_model,
            analyzer=self.analyzer,
            event_bus = self.event_bus,
            catalogo_elenchi=catalogo_elenchi
        )

        # Sistema per tracciare gli after()
        self._after_ids = set()
        self._orig_after = self.after
        self.after = self._track_after

        # Inizializza la vista principale
        self.create_accounts_tab()
        self.show_main_view()

    def create_accounts_tab(self):
        """Crea la UI per la gestione dei conti bancari"""
        self.account_description = ctk.CTkLabel(self.main_container, text="Gestisci i conti correnti", font=("Arial", 14))
        self.account_description.pack(pady=(70, 45))

        # Area per le cards degli utenti (simulata qui per ora)
        self.account_card_area = ctk.CTkFrame(self.main_container, fg_color="#2b2b2b")
        self.account_card_area.pack(fill= "y", expand=True, pady=20)

        self.account_card_area1 = ctk.CTkFrame(self.main_container, fg_color="#2b2b2b")
        self.account_card_area1.pack(fill= "y", expand=True, pady=20)

        # Bottone per aggiungere un nuovo utente
        self.add_account_button = ctk.CTkButton(self.main_container, text="Aggiungi Nuovo Conto", font=("Arial", 15, "bold"),
                                             command=self.open_add_account_window)
        self.add_account_button.configure(width=200, height=50)
        self.add_account_button.pack(anchor="s", pady=20)

        # aggiungo una card per ogni utente
        for account in self.account_controller.retrieve_accounts_map_list():
            id =  account[DBAccountsColumns.ID.value]
            name = account[DBAccountsColumns.NAME.value]
            balance = self.analyzer.calculate_account_balance_by_account_id(id)

            self.add_account_card(id, name, balance)

    def show_main_view(self):
        """Torna alla vista principale"""
        self.account_detail_view.pack_forget()
        self.main_container.pack(fill='both', expand=True)

    def open_account_detail_tab(self, account_id):
        """Mostra la vista dettaglio del conto"""
        self.main_container.pack_forget()
        self.account_detail_view.pack(fill='both', expand=True)
        self.account_detail_view.create_detail_tab(account_id)  # Ricrea i contenuti ogni volta

    def open_add_account_window(self):
        """Apre una finestra per aggiungere un nuovo conto"""

        self.add_account_window = ctk.CTkToplevel(self)
        self.add_account_window.title("Aggiungi Nuova Produzione")

        # Assicurati che la finestra rimanga sopra
        self.add_account_window.lift()  # Porta la finestra sopra quella principale
        self.add_account_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

        self.add_account_window.geometry("350x400")

        self.account_window_scrollableFrame = ctk.CTkScrollableFrame(self.add_account_window)
        self.account_window_scrollableFrame.pack(fill="both", expand=True)

        self.entry_fields = {
            DBAccountsColumns.NAME.value: ctk.CTkEntry,
            DBAccountsColumns.INIT_BALANCE.value: ctk.CTkEntry,
        }

        self.error_fields = {
            DBAccountsColumns.NAME.value: ctk.CTkLabel,
            DBAccountsColumns.INIT_BALANCE.value: ctk.CTkLabel,
        }

        self.error_labels = {}

        for i, (label_text, widget_class) in enumerate(self.entry_fields.items()):
            # Etichetta
            label = ctk.CTkLabel(self.account_window_scrollableFrame, text=label_text)
            #disegno i labels
            if i == 0:
                label.pack(pady=5)
            else:
                label.pack(pady=(35, 0))

            self.account_labels[label_text] = label

            #creo i widgets
            widget = widget_class(self.account_window_scrollableFrame)

            widget.pack(pady=5, padx=(0, 10), fill="x", expand=True)

            self.account_widgets[label_text] = widget

            if self.error_fields.get(label_text) is not None:
                error_label = ctk.CTkLabel(self.account_window_scrollableFrame, text="")
                error_label.pack(pady=(0,15))
                self.error_labels[label_text] = error_label

        # Bottone per salvare
        self.save_button = ctk.CTkButton(
            self.account_window_scrollableFrame,
            text="Salva Conto Corrente",
            command=self.save_account_data
        )
        self.save_button.pack(pady=(35, 15))

        # Aggiungi validazione agli eventi di perdita del focus
        self.account_widgets[DBAccountsColumns.NAME.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.account_widgets[DBAccountsColumns.NAME.value],
            lambda val: val.strip() != "",
            self.error_labels[DBAccountsColumns.NAME.value],
            "Il campo non può essere vuoto."
        ))

        self.account_widgets[DBAccountsColumns.INIT_BALANCE.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.account_widgets[DBAccountsColumns.INIT_BALANCE.value],
            lambda val: re.fullmatch(r"^\d+(\.\d{2})?$", val.strip()) is not None,
            self.error_labels[DBAccountsColumns.INIT_BALANCE.value],
            "Inserimento non valido: inserire un numero monetario con due cifre decimali (es. 123.45)"
        ))

    def add_account_card(self, id, name, balance):
        """Aggiungi una card per un conto alla lista"""

        account_card = ctk.CTkFrame(self.account_card_area if self.number_of_account_cards < 4 else self.account_card_area1, fg_color="#333333")
        account_card.pack(side="left", pady=5, padx=25)
        self.account_cards[id] = account_card

        info_frame = ctk.CTkFrame(account_card)
        info_frame.pack(fill= "y", expand=True, side="left", padx=10, pady=10)

        # Nome, balance
        user_info_name = ctk.CTkLabel(info_frame, text=f"{name}", font=("Arial", 20))
        user_info_name.pack(anchor="n", expand=True, padx=10, pady=5)
        user_info_balance = ctk.CTkLabel(info_frame, text=f"{balance:.2f} €", font=("Arial", 16))
        user_info_balance.pack(anchor="s", padx=10, pady=10)

        buttons_frame = ctk.CTkFrame(account_card)
        buttons_frame.pack(padx=10, pady=(10, 10))

        self.balance_labels[id] = user_info_balance

        self.detail_button = ctk.CTkButton(buttons_frame, text="Dettaglio", command=lambda: self.open_account_detail_tab(id))
        self.detail_button.pack(pady=10, padx=10)

        self.bonifico_button = ctk.CTkButton(buttons_frame, text="Esegui Bonifico", command=lambda: self.transfers_view.open_add_transfer_window(id))
        self.bonifico_button.pack(pady=10)

        self.number_of_account_cards += 1

    def open_modify_account_window(self, account_id):
        return

    def open_confirm_popup(self, id, operation):
        self.confirm_window = ctk.CTkToplevel(self)
        self.confirm_window.title(
            f"Pop-up di conferma")

        # Assicurati che la finestra rimanga sopra
        self.confirm_window.lift()  # Porta la finestra sopra quella principale
        self.confirm_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

        self.confirm_window.geometry("400x150")

        confirm_label = ctk.CTkLabel(self.confirm_window, text=f"{operation}\nSei sicuro di voler proseguire con l'operazione?")
        confirm_label.pack(pady=20, padx=5)

        self.confirm_window_Frame = ctk.CTkFrame(self.confirm_window)
        self.confirm_window_Frame.pack(pady=15)

        confirm_button = ctk.CTkButton(self.confirm_window_Frame, text="conferma", command= lambda: self.delete_account(id))
        confirm_button.pack(pady=10, padx=5, side="left")

        cancel_button = ctk.CTkButton(self.confirm_window_Frame, text="cancella", command=lambda: self.confirm_window.destroy())
        cancel_button.pack(pady=10, padx=5)

    def delete_account(self, account_id):
        success, message = self.account_controller.delete_account_by_ID(account_id)
        if success and account_id in self.account_cards:
            self.account_cards[account_id].destroy()  # Rimuovi la card dalla UI
            del self.account_cards[account_id]  # Rimuovi dal dizionario
            self.number_of_account_cards -= 1
        else:
            print(f"impossibile eliminare il conto: {message}")
            ViewUtils.show_error_popup("ERRORE", message)

    def update_accounts_balances(self):
        for account_id, label in self.balance_labels.items():
            new_balance = self.analyzer.calculate_account_balance_by_account_id(account_id)
            label.configure(text=f"{new_balance:.2f} €")

    def save_account_data(self):
        account_data = {}

        # riempi il dizionario con i dati dei widgets primari
        for label_text, widget in self.account_widgets.items():
            if isinstance(widget, ctk.CTkEntry) or isinstance(widget, ctk.CTkOptionMenu):
                account_data[label_text] = widget.get().strip()
            elif isinstance(widget, Calendar):
                account_data[label_text] = widget.get_date()
            elif isinstance(widget, ctk.CTkTextbox):
                account_data[label_text] = widget.get("1.0", "end-1c").strip()  # Recupera il testo dal Textbox

        # chiamata al controller per salvare i dati
        success, message = self.account_controller.save_account(account_data)

        if success:
            #prendo l'ID del conto appena creato
            account_map = self.account_controller.retrieve_last_account_insert_map()
            print(f"Conto {account_data[DBAccountsColumns.NAME.value]} salvato con successo")

            self.add_account_card(
                account_map[DBAccountsColumns.ID.value],
                account_map[DBAccountsColumns.NAME.value],
                account_map[DBAccountsColumns.INIT_BALANCE.value]
            )

            self.clear_class_variable()
            self.add_account_window.destroy()
            self.update_global_infos()
        else:
            print(message)
            ViewUtils.show_error_popup(self.add_account_window, "ERRORE", message)

    def clear_class_variable(self):
        self.account_widgets.clear()
        self.account_labels.clear()

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











class AccountDetailView(ctk.CTkFrame):
    def __init__(self, parent, back_callback, account_controller, update_controller, db_model, event_bus, catalogo_elenchi, analyzer):
        super().__init__(parent)
        self.account_controller = account_controller
        self.analyzer = analyzer
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
            text="Torna ai conti",
            command=self._cleanup_and_go_back
        )
        self.title_label = ctk.CTkLabel(self.head_frame, font=("Arial", 22, "bold"))

        self.expense_info_widgets: dict[str, ctk.CTkEntry | ctk.CTkOptionMenu] = {}

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

    def create_detail_tab(self, account_id):
        """Ricrea la vista dettaglio per un conto specifico"""
        self.current_account_id = account_id

        # 1. Pulizia dei widget precedenti
        self._clear_content()

        # 2. Caricamento dati
        self.account = self.account_controller.retrieve_account_map_by_id(account_id)

        # 3. Aggiornamento elementi persistenti
        self.title_label.configure(
            text=f"{self.account[DBAccountsColumns.NAME.value]}")

        # 4. Creazione contenuti dinamici
        self._create_account_info_section(self.account)
        self.toggle_edit(self.content_frame)


    def _create_account_info_section(self, account_data):
        # Recupera i movimenti del conto
        movements = self.analyzer.retrieve_account_movements_by_account_id(self.current_account_id)

        # Calcola il saldo corrente
        current_balance = float(account_data[DBAccountsColumns.INIT_BALANCE.value])
        for mov in movements:
            if mov['sign'] == '+':
                current_balance += mov['amount']
            else:
                current_balance -= mov['amount']

        # Dizionari per la configurazione
        self.entry_fields = {
            # Sezione Dati Conto
            DBAccountsColumns.NAME.value: {
                "type": ctk.CTkEntry,
                "label": "Nome Conto",
                "section": "Dati Conto"
            },
            DBAccountsColumns.INIT_BALANCE.value: {
                "type": ctk.CTkEntry,
                "label": "Saldo Iniziale",
                "section": "Dati Conto"
            },
            "current_balance": {
                "type": ctk.CTkLabel,
                "label": "Saldo Corrente",
                "section": "Dati Conto"
            }
        }

        # Formatta i saldi per la visualizzazione
        account_data[
            DBAccountsColumns.INIT_BALANCE.value] = f"{float(account_data[DBAccountsColumns.INIT_BALANCE.value]):.2f} "
        account_data["current_balance"] = f"{current_balance:.2f} €"

        # Regole di validazione
        validation_rules = {
            DBAccountsColumns.NAME.value: (
                lambda val: val.strip() != "",
                "Il nome del conto non può essere vuoto"
            )
        }

        # Inizializzazione strutture dati
        self.account_info_widgets = {}
        self.error_labels = {}
        sections = {}

        # Creazione frame principale
        self.info_frame = ctk.CTkFrame(self.content_frame, border_width=2, border_color="#2659ab")
        self.info_frame.pack(pady=10, padx=10, side="left", anchor="n", fill="y", expand=False)

        # Non serve più configurare la griglia poiché useremo pack
        # sections_order rimane lo stesso
        sections_order = ["Dati Conto"]

        sections = {}
        container_frame = ctk.CTkFrame(self.info_frame, fg_color="transparent")
        container_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Crea i frame per ogni sezione
        for section_name in sections_order:
            # Frame principale per la sezione
            section_frame = ctk.CTkFrame(container_frame)
            section_frame.pack(fill="x", padx=5, pady=5, side="top")

            # Titolo della sezione
            ctk.CTkLabel(section_frame, text=section_name, font=("Arial", 14, "bold")).pack(
                anchor="w", padx=15, pady=(5, 10)
            )

            # Frame per i campi
            fields_frame = ctk.CTkFrame(section_frame)
            fields_frame.pack(fill="x", padx=10, pady=5)

            sections[section_name] = {
                "frame": fields_frame,
                "row": 0
            }

        # Popolamento delle sezioni
        for field, config in self.entry_fields.items():
            section = sections[config["section"]]
            frame = section["frame"]

            # Frame per ogni campo
            field_frame = ctk.CTkFrame(frame, fg_color="transparent")
            field_frame.pack(fill="x", pady=3)

            # Creazione label
            lbl = ctk.CTkLabel(field_frame, text=config["label"] + ":", width=150, anchor="nw")
            lbl.pack(side="left", padx=(15, 5), pady=2)

            # Frame per widget e errori
            widget_frame = ctk.CTkFrame(field_frame, fg_color="transparent")
            widget_frame.pack(side="right", fill="x", expand=True, padx=(0, 15))

            # Creazione widget
            value = str(account_data.get(field, ""))

            if config["type"] == ctk.CTkOptionMenu:
                widget = config["type"](widget_frame, values=config.get("values", []))
                widget.set(value if value else config.get("values", [""])[0])
            elif config["type"] == ctk.CTkTextbox:
                widget = config["type"](widget_frame, height=config.get("height", 50))
                widget.insert("1.0", value)
            elif config["type"] == ctk.CTkLabel:
                widget = config["type"](widget_frame, text=value)
            else:
                widget = config["type"](widget_frame)
                if value:
                    widget.insert(0, value)

            widget.pack(fill="x", padx=(5, 0), pady=2)

            # Gestione errori
            if field in validation_rules:
                error_frame = ctk.CTkFrame(widget_frame, fg_color="transparent")
                error_frame.pack(fill="x", pady=(0, 5))

                # Spaziatore vuoto per allineamento
                ctk.CTkLabel(error_frame, text="", width=150).pack(side="left")

                error_lbl = ctk.CTkLabel(error_frame, text="", text_color="#e8e5dc", anchor="w")
                error_lbl.pack(side="left", fill="x", expand=True)
                self.error_labels[field] = error_lbl

                # Binding per validazione
                if config["type"] != ctk.CTkTextbox:
                    widget.bind("<FocusOut>",
                                lambda e, w=widget,
                                       vl=validation_rules[field][0],
                                       el=error_lbl,
                                       em=validation_rules[field][1]:
                                ViewUtils.validate_entry(w, vl, el, em))
                else:
                    widget.bind("<FocusOut>",
                                lambda e, w=widget,
                                       vl=validation_rules[field][0],
                                       el=error_lbl,
                                       em=validation_rules[field][1]:
                                ViewUtils.validate_textbox(w, vl, el, em))

            self.account_info_widgets[field] = widget

        # Frame per i bottoni
        buttons_frame = ctk.CTkFrame(container_frame, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=20, pady=(15, 5), side="bottom")

        # Bottone Salva
        self.save_info_btn = ctk.CTkButton(buttons_frame, text="Salva Conto", command=self.save_account_mod)
        self.save_info_btn.pack(side="left", padx=(0, 10), pady=5)

        # Sezione Storico Movimenti (non editabile)
        movements_frame = ctk.CTkFrame(self.content_frame, border_width=2, border_color="#2659ab")
        movements_frame.pack(fill="both", expand=True, pady=10, padx=25)

        # Configura il grid per espandere la riga dello scrollable frame
        movements_frame.grid_columnconfigure(0, weight=1)
        movements_frame.grid_rowconfigure(2, weight=1)  # IMPORTANTE: rende la riga espandibile

        # Titolo sezione
        ctk.CTkLabel(movements_frame, text="Storico Movimenti", font=("Arial", 14, "bold")).grid(
            row=0, column=0, sticky="nw", padx=15, pady=10
        )

        # Frame per l'intestazione
        header_frame = ctk.CTkFrame(movements_frame, fg_color="#3b3b3b")
        header_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 5))

        # Intestazioni
        headers = ["Data", "Descrizione", "Tipo", "Importo"]
        header_widths = [300, 400, 300, 300]
        for col, (header, width) in enumerate(zip(headers, header_widths)):
            ctk.CTkLabel(header_frame, text=header, font=("Arial", 12, "bold"),
                         width=width).grid(row=0, column=col, padx=5, pady=5)

        # Frame scrollabile per i movimenti - RIMOSSO L'ALTEZZA FISSA
        scrollable_frame = ctk.CTkScrollableFrame(movements_frame)
        scrollable_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        scrollable_frame.grid_columnconfigure(1, weight=1)

        # Aggiungi i movimenti
        for row, mov in enumerate(movements):
            # Crea un frame per ogni riga
            row_frame = ctk.CTkFrame(scrollable_frame)
            row_frame.grid(row=row, column=0, sticky="ew", pady=2)

            # Alterna il colore di sfondo per migliorare la leggibilità
            if row % 2 == 0:
                row_frame.configure(fg_color="#2a2d2e")
            else:
                row_frame.configure(fg_color="#333333")

            # Data
            date_label = ctk.CTkLabel(row_frame, text=mov["date"], width=header_widths[0])
            date_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

            # Descrizione
            desc_label = ctk.CTkLabel(row_frame, text=mov["name"], width=header_widths[1], anchor="center")
            desc_label.grid(row=0, column=1, padx=5, pady=5, sticky="w")

            # Tipo
            type_label = ctk.CTkLabel(row_frame, text=mov["type"], width=header_widths[2])
            type_label.grid(row=0, column=2, padx=5, pady=5, sticky="w")

            # Importo
            amount_text = f"{mov['sign']}{mov['amount']:.2f} €"
            amount_color = "#2ECC71" if mov['sign'] == '+' else "#E74C3C"
            amount_label = ctk.CTkLabel(row_frame, text=amount_text, width=header_widths[3],
                                        text_color=amount_color)
            amount_label.grid(row=0, column=3, padx=5, pady=5, sticky="e")

            # Configura le colonne
            for col in range(4):
                row_frame.grid_columnconfigure(col, weight=1 if col == 1 else 0)

    def save_account_mod(self):
        account_data = {
            DBAccountsColumns.NAME.value: self.account_info_widgets[
                DBAccountsColumns.NAME.value].get().strip(),
            DBAccountsColumns.INIT_BALANCE.value: self.account_info_widgets[
                DBAccountsColumns.INIT_BALANCE.value].get().strip()
        }

        # Chiamata al controller per salvare i dati
        success, message = self.account_controller.update_account(self.current_account_id, account_data)
        if success:
            print(
                f"Conto {self.account_controller.retrieve_account_map_by_id(self.current_account_id)[DBAccountsColumns.NAME.value]} salvato con successo")
            ViewUtils.show_confirm_popup_2(self.content_frame, "SALVATAGGIO COMPLETATO", message)
            self.switch_modify.deselect()
            self.toggle_edit(self.content_frame)
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
        self.save_info_btn.configure(state=state)

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

        self.switch_modify.deselect()

    def _cleanup_and_go_back(self):
        """Pulizia completa prima di tornare indietro"""
        self._clear_content()
        self.pack_forget()
        self.back_callback()
















class TransfersView(ctk.CTk):

    def __init__(self, db_model, account_controller, update_controller, transfer_controller, config_manager, catalogo_elenchi, analyzer):
        super().__init__()

        self.db_model = db_model
        self.account_controller = account_controller
        self.update_controller = update_controller
        self.transfer_controller = transfer_controller
        self.config_manager = config_manager
        self.catalogo_elenchi = catalogo_elenchi
        self.analyzer = analyzer

        self.transfer_widgets = {}
        self.transfer_labels = {}

    def open_add_transfer_window(self, sender_account_id):
        """
        funzione per spostare finanze da un conto a un altro

        """

        self.bonifico_window = ctk.CTkToplevel(self)
        self.bonifico_window.title("Esegui Bonifico")

        # Assicurati che la finestra rimanga sopra
        self.bonifico_window.lift()  # Porta la finestra sopra quella principale
        self.bonifico_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

        self.bonifico_window.geometry("550x500")

        self.bonifico_window_scrollableFrame = ctk.CTkScrollableFrame(self.bonifico_window)
        self.bonifico_window_scrollableFrame.pack(fill="both", expand=True)

        self.nome_receiver_account_string = "CONTO RICEVENTE"

        self.entry_fields = {
            DBTransfersColumns.DESCRIPTION.value: ctk.CTkEntry,
            DBTransfersColumns.AMOUNT.value: ctk.CTkEntry,
            self.nome_receiver_account_string: ctk.CTkOptionMenu,
        }

        self.error_fields = {
            DBTransfersColumns.DESCRIPTION.value: ctk.CTkLabel,
            DBTransfersColumns.AMOUNT.value: ctk.CTkLabel,
        }

        self.error_labels = {}

        for i, (label_text, widget_class) in enumerate(self.entry_fields.items()):
            # Etichetta
            label = ctk.CTkLabel(self.bonifico_window_scrollableFrame, text=label_text)
            # disegno i labels
            if i == 0:
                label.pack(pady=5)
            else:
                label.pack(pady=(35, 0))

            self.transfer_labels[label_text] = label

            # creo i widgets
            if label_text == self.nome_receiver_account_string:
                accounts_map_list = self.account_controller.retrieve_accounts_map_list()
                accounts_name_list = [account[DBAccountsColumns.NAME.value] for account in accounts_map_list if account[DBAccountsColumns.ID.value] != sender_account_id]
                widget = widget_class(self.bonifico_window_scrollableFrame,
                                      values=accounts_name_list)
            else:
                widget = widget_class(self.bonifico_window_scrollableFrame)

            widget.pack(pady=5, padx=(0, 10), fill="x", expand=True)

            self.transfer_widgets[label_text] = widget

            if self.error_fields.get(label_text) is not None:
                error_label = ctk.CTkLabel(self.bonifico_window_scrollableFrame, text="")
                error_label.pack(pady=(0, 15))
                self.error_labels[label_text] = error_label

        # Bottone per salvare
        self.save_button = ctk.CTkButton(
            self.bonifico_window_scrollableFrame,
            text="Esegui Bonifico",
            command=lambda: self.save_transfer_data(sender_account_id)
        )
        self.save_button.pack(pady=(85, 15))

        if len(accounts_name_list) == 0:
            self.transfer_widgets[self.nome_receiver_account_string].set("Nessun altro conto esistente nel sistema")
            self.save_button.configure(state=ctk.DISABLED)

        # Aggiungi validazione agli eventi di perdita del focus
        self.transfer_widgets[DBTransfersColumns.DESCRIPTION.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.transfer_widgets[DBTransfersColumns.DESCRIPTION.value],
            lambda val: val.strip() != "",
            self.error_labels[DBTransfersColumns.DESCRIPTION.value],
            "Il campo non può essere vuoto."
        ))

        self.transfer_widgets[DBTransfersColumns.AMOUNT.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.transfer_widgets[DBTransfersColumns.AMOUNT.value],
            lambda val: re.fullmatch(r"^\d+(\.\d{2})?$", val.strip()) is not None,
            self.error_labels[DBTransfersColumns.AMOUNT.value],
            "Inserimento non valido: inserire un numero monetario con due cifre decimali (es. 123.45)"
        ))

    def save_transfer_data(self, sender_account_id):
        transfer_data = {}

        # riempi il dizionario con i dati dei widgets primari
        for label_text, widget in self.transfer_widgets.items():
            if isinstance(widget, ctk.CTkEntry) or isinstance(widget, ctk.CTkOptionMenu):
                transfer_data[label_text] = widget.get().strip()
            elif isinstance(widget, Calendar):
                transfer_data[label_text] = widget.get_date()
            elif isinstance(widget, ctk.CTkTextbox):
                transfer_data[label_text] = widget.get("1.0", "end-1c").strip()  # Recupera il testo dal Textbox

        transfer_data[DBTransfersColumns.SENDER_ACCOUNT_ID.value] = sender_account_id

        # chiamata al controller per salvare i dati
        success, message = self.transfer_controller.save_transfer(transfer_data)

        if success:
            self.update_controller.on_adding_transfer()

            self.clear_class_variable()
            self.bonifico_window.destroy()
        else:
            print(message)
            ViewUtils.show_error_popup(self.bonifico_window, "ERRORE", message)

    def clear_class_variable(self):
        self.transfer_widgets.clear()
        self.transfer_labels.clear()

import customtkinter as ctk

from datetime import datetime, timedelta

from App_context import AppContext
from AnalyzerServices.Monthly_report_analyzer_service import SupplierController
from Model import DBExpensesColumns, DBSuppliersColumns
from Views.Creators.Supplier_create_view import SupplierCreateView
from Views.Details.Supplier_detail_view import SupplierDetailView
from Views.View_utils import ViewUtils


class SuppliersView(ctk.CTkFrame):

    def __init__(self, app_context: AppContext, tab_view):
        super().__init__(tab_view.tab("Fornitori"))

        self.app_context: AppContext = app_context
        self.db_model = app_context.db_model
        self.update_controller = app_context.update_controller
        self.supplier_controller = app_context.supplier_controller
        self.config_manager = app_context.config_manager
        self.analyzer = app_context.analyzer
        self.expense_controller = app_context.expense_controller
        self.catalogo_elenchi = app_context.catalogo_elenchi
        self.tab_view = tab_view
        self.tab = tab_view.tab("Fornitori")
        self.event_bus = app_context.event_bus

        self.global_infos = {}
        self.amount_aggregate_labels = {}

        self.suppliers_card_list = {}
        self.supplier_card_labels_status = {}
        self.supplier_create_view = None

        self.main_container = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.detail_container = ctk.CTkFrame(self, fg_color="#2b2b2b")

        self.supplier_detail_view = SupplierDetailView(
            parent=self,
            app_context=self.app_context,
            back_callback=self.show_main_view
        )

        self._after_ids = set()
        self._orig_after = self.after
        self.after = self._track_after

        self.create_suppliers_tab()
        self.show_main_view()

    def create_suppliers_tab(self):

        self.search_bar_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.search_bar_frame.pack(pady=30, fill="x", anchor="n")
        self.search_bar = ctk.CTkEntry(self.search_bar_frame)
        self.search_bar.pack(padx=(5, 35), anchor="e", side="right")
        self.search_bar_label = ctk.CTkLabel(self.search_bar_frame, text="Filtra per nome:", font=("Arial", 14))
        self.search_bar_label.pack(padx=5, anchor="s", side="right")

        self.show_last_cards_optionMenu_values = {
            "30 GG": "30 GG",
            "60 GG": "60 GG",
            "90 GG": "90 GG",
            "365 GG": "365 GG"
        }
        self.show_last_cards_optionMenu = ctk.CTkOptionMenu(
            self.search_bar_frame,
            values=list(self.show_last_cards_optionMenu_values.values())
        )
        self.show_last_cards_optionMenu.set("60 GG")
        self.show_last_cards_optionMenu.pack(padx=(5, 200), anchor="s", side="right")
        self.show_last_cards_label = ctk.CTkLabel(self.search_bar_frame, text="Mostra gli ultimi ", font=("Arial", 14))
        self.show_last_cards_label.pack(padx=5, anchor="s", side="right")

        self.show_last_cards_optionMenu.configure(command=lambda _: self.show_last_cards())

        self.search_bar.bind("<KeyRelease>", self.filter_cards)

        self.suppliers_table_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.suppliers_table_frame.pack(pady=(20, 0), padx=(10, 15), fill="x", anchor="n")

        self.headers = ["NOME", "PARTITA IVA", "TOT. SPESE", "# SPESE", "SPESA MEDIA", "NOTE", "CONTATTO"]

        for i, header in enumerate(self.headers):
            column = ctk.CTkFrame(self.suppliers_table_frame, fg_color="#333333")
            column.grid(row=0, column=i, sticky="nsew", padx=(0, 5), pady=5)

            self.suppliers_table_frame.grid_columnconfigure(i, weight=1, uniform="col")

            label = ctk.CTkLabel(column, text=header, font=("Arial", 14))
            label.pack(fill="both", expand=True, padx=5, pady=15)

        self.suppliers_cards_frame = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")
        self.suppliers_cards_frame.pack(padx=0, pady=10, fill="both", expand=True)

        self.add_supplier_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.add_supplier_frame.pack(padx=0, pady=(5, 20), fill="x")

        self.save_button = ctk.CTkButton(
            self.add_supplier_frame,
            text="Aggiungi Fornitore",
            command=self.open_add_supplier_window
        )
        self.save_button.pack()

        self.show_last_cards()

    def show_last_cards(self):
        """Mostra solo i supplier con almeno una spesa negli ultimi giorni selezionati."""
        selected = self.show_last_cards_optionMenu.get()

        days_map = {
            "30 GG": 30,
            "60 GG": 60,
            "90 GG": 90,
            "365 GG": 365
        }
        days = days_map.get(selected, 30)

        limit_date = datetime.now() - timedelta(days=days)

        all_suppliers = self.supplier_controller.retrieve_suppliers_map_list(year=-1)

        filtered_suppliers = []
        for supplier in all_suppliers:
            supplier_id = supplier[DBSuppliersColumns.ID.value]
            supplier_expenses = self.supplier_controller.retrieve_supplier_with_expenses_map_list(supplier_id, year=-1)

            has_recent_expense = False
            for expense in supplier_expenses:
                date_str = expense.get(DBExpensesColumns.DATE.value)
                if date_str:
                    try:
                        try:
                            expense_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            expense_date = datetime.strptime(date_str, "%Y-%m-%d")

                        if expense_date >= limit_date:
                            has_recent_expense = True
                            break
                    except Exception as e:
                        print(f"Errore nel parsare la data {date_str}: {e}")

            supplier_creation_date = datetime.strptime(
                supplier.get(DBSuppliersColumns.CREATED_AT.value),
                "%Y-%m-%d %H:%M:%S"
            )
            is_just_created = False
            if datetime.now() - supplier_creation_date <= timedelta(days=30):
                is_just_created = True

            if has_recent_expense or is_just_created:
                filtered_suppliers.append(supplier)

        for card in self.suppliers_card_list.values():
            card.destroy()
        self.suppliers_card_list.clear()

        self.load_suppliers_chunked(filtered_suppliers)

    def show_main_view(self):
        """Torna alla vista principale."""
        self.supplier_detail_view.pack_forget()
        self.main_container.pack(fill="both", expand=True)

    def open_add_supplier_window(self):
        """Apre la creator view del fornitore assicurando una sola istanza attiva."""
        if self.supplier_create_view is not None and self.supplier_create_view.winfo_exists():
            self.supplier_create_view.focus()
            self.supplier_create_view.lift()
            return

        self.supplier_create_view = SupplierCreateView(
            parent=self,
            app_context=self.app_context,
            on_supplier_created=self._on_supplier_created,
            on_close=self._clear_supplier_create_view
        )

    def load_suppliers_chunked(self, suppliers_list):

        extractor = ViewUtils.create_extractor_for_suppliers(
            self.supplier_controller
        )

        ViewUtils.process_items_in_chunks(
            widget=self,
            items_list=suppliers_list,
            add_card_callback=self.add_supplier_card,
            extract_args_callback=extractor,
            cards_frame=self.suppliers_cards_frame
        )

    def add_supplier_card(self, supplier_id, supplier_name, partita_iva, num_spese, spesa_media, tot_spese, note, contatto):
        card = ctk.CTkFrame(self.suppliers_cards_frame, fg_color="dimgray")
        card.pack(pady=10, padx=10, fill="x", expand=True)

        data = [supplier_name, partita_iva, f"{tot_spese:.2f}", num_spese, f"{spesa_media:.2f}", note, contatto]
        units = ["", "", "€", "", "€", "", ""]
        n_cols = len(data)

        for c in range(n_cols):
            card.grid_columnconfigure(c, weight=1, uniform="clientcol")
        card.grid_rowconfigure(0, weight=1)

        btn = ctk.CTkButton(
            card,
            text=supplier_name,
            command=lambda sid=supplier_id: self.open_supplier_detail_tab(sid)
        )
        btn.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        for idx, val in enumerate(data[1:], start=1):
            text = f"{val} {units[idx]}"
            lbl = ctk.CTkLabel(card, text=text, font=("Arial", 14))
            lbl.grid(row=0, column=idx, sticky="nsew", padx=5, pady=10)

        self.suppliers_card_list[supplier_name] = card

    def _on_supplier_created(self, supplier_id, supplier_data):
        """Aggiorna la lista dopo il salvataggio di un nuovo fornitore."""
        self.show_last_cards()
        self.filter_cards(None)

    def filter_cards(self, event):
        """Filtra le card in base al testo della barra di ricerca."""
        search_text = self.search_bar.get().lower()

        for nome, card in self.suppliers_card_list.items():
            if search_text in nome.lower():
                card.pack(pady=10, padx=10, fill="x", expand=True)
            else:
                card.pack_forget()

    def open_supplier_detail_tab(self, supplier_id):
        """Mostra la vista dettaglio utente."""
        self.main_container.pack_forget()
        self.supplier_detail_view.pack(fill="both", expand=True)
        self.supplier_detail_view.create_detail_tab(supplier_id)

    def _clear_supplier_create_view(self):
        """Pulisce il riferimento alla creator view quando la finestra viene chiusa."""
        self.supplier_create_view = None

    def cleanup(self):
        """Pulizia completa per liberare memoria - DA AGGIUNGERE IN OGNI VIEW"""
        try:
            print(f"Cleanup di {self.__class__.__name__}")

            if hasattr(self, "_after_ids"):
                for after_id in self._after_ids:
                    try:
                        self.after_cancel(after_id)
                    except Exception:
                        pass
                self._after_ids.clear()

            card_lists = [
                "payment_card_list", "invoice_card_list", "client_card_list",
                "supplier_card_list", "production_card_list", "expenses_card_list",
                "salaries_card_list", "refund_card_list", "account_card_list"
            ]

            for card_attr in card_lists:
                if hasattr(self, card_attr):
                    card_dict = getattr(self, card_attr)
                    for card_name, card in card_dict.items():
                        try:
                            card.destroy()
                        except Exception:
                            pass
                    card_dict.clear()

            data_attrs = [
                "cards_warnings", "global_infos", "amount_aggregate_labels",
                "payment_card_labels_status", "invoice_card_labels_status",
                "production_card_labels_status"
            ]

            for attr in data_attrs:
                if hasattr(self, attr):
                    getattr(self, attr).clear()

            container_attrs = [
                "main_container", "detail_container", "payments_cards_frame",
                "invoices_cards_frame", "clients_cards_frame", "suppliers_cards_frame",
                "productions_cards_frame", "expenses_cards_frame", "refunds_cards_frame",
                "accounts_cards_frame", "salaries_cards_frame"
            ]

            for attr in container_attrs:
                if hasattr(self, attr):
                    container = getattr(self, attr)
                    try:
                        if container.winfo_exists():
                            for widget in container.winfo_children():
                                try:
                                    widget.destroy()
                                except Exception:
                                    pass
                    except Exception:
                        pass

            if hasattr(self, "db_model"):
                self.db_model = None

        except Exception as e:
            print(f"Errore durante il cleanup di {self.__class__.__name__}: {e}")

    def _track_after(self, ms, func, *args):
        """Versione tracciata di after()."""
        after_id = self._orig_after(ms, func, *args)
        self._after_ids.add(after_id)
        return after_id

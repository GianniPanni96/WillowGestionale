import customtkinter as ctk
import re, os
from Views.View_utils import ViewUtils, customTKMenuButton
from datetime import datetime


from Controllers import ExpenseController, ControllerUtils
from Model import DBSuppliersColumns, DBAccountsColumns, DBUsersColumns

from Book_closer import BookCloser

from Views.Users_view import UsersView
from Views.Clients_view import ClientsView
from Views.Invoices_view import InvoicesView
from Views.Payments_view import PaymentsView
from Views.Productions_view import ProductionsView
from Views.Expenses_view import ExpensesView
from Views.Suppliers_view import SuppliersView
from Views.Accounts_view import AccountsView
from Views.Salaries_view import SalariesView
from Views.Iva_trimes_view import IvaTrimesView
from Views.Refunds_view import RefundsView
from Views.Taxes_view import TaxesView
from Views.Report_view import ReportView
from Plot_view import PlotView


class MainWindow(ctk.CTk):
    def __init__(self, app_context):
        super().__init__()

        self._after_ids = set()

        # Override di after per tracciare gli ID
        self._orig_after = self.after
        self.after = self._track_after

        self.app_context = app_context
        self.event_bus = app_context.event_bus

        # ConfigManager per la gestione della configurazione
        self.config_manager = app_context.config_manager
        self.backup_importer = app_context.backup_importer

        self.fiscal_settings = app_context.fiscal_settings
        self.catalogo_elenchi = app_context.catalogo_elenchi
        self.recurring_expenses_settings = app_context.recurring_expenses_settings
        self.historical_financial_data_settings = app_context.historical_financial_data_settings

        self.data_path = app_context.data_path
        self.images_path = app_context.images_path

        #Imposta l'icona della finestra
        try:
            self.iconbitmap(os.path.join(self.images_path, "WillowLogo.ico"))
        except Exception as e:
            print(f"Errore nell'impostazione dell'icona della finestra: {e}")

        self.login_status = False
        self.logged_user_id = -1


        self.db_model = app_context.db_model  # Istanzia il modello
        self.user_controller = app_context.user_controller  # Crea il controller per gli utenti
        self.account_controller = app_context.account_controller
        self.salary_controller = app_context.salary_controller
        self.transfer_controller = app_context.transfer_controller
        self.client_controller = app_context.client_controller
        self.supplier_controller = app_context.supplier_controller
        self.payment_controller = app_context.payment_controller
        self.production_controller = app_context.production_controller
        self.invoice_controller = app_context.invoice_controller
        self.expense_controller = app_context.expense_controller
        self.refund_controller = app_context.refund_controller
        self.update_controller = app_context.update_controller
        self.analyzer = app_context.analyzer

        self.title("Gestionale Willow")

        # Toolbar simulata con pulsanti
        self.toolbar_frame = ctk.CTkFrame(self)
        self.toolbar_frame.pack(side="top", fill="x")

        self.backup_menu = customTKMenuButton(
            self.toolbar_frame,
            text="Gestione Backup",
            items=[
                ("Impostazioni backup", self.open_backups_window),
                ("Carica un backup", self.open_load_backup),
            ],
        )
        self.backup_menu.pack(side="left", padx=15, pady=15)


        self.fiscal_settings_menu_button = customTKMenuButton(
            self.toolbar_frame,
            text="Gestione Dati Fiscali",
            items=[
                ("Modifica dati fiscali", self.open_fiscal_settings_window)
            ],
        )
        self.fiscal_settings_menu_button.pack(side="left", padx=(0, 15), pady=15)

        self.recurring_expenses_menu_button = customTKMenuButton(
            self.toolbar_frame,
            text="Gestione Spese Ricorrenti",
            items=[
                ("Modifica Spese Ricorrenti", self.open_recurring_expenses_window)
            ],
        )
        self.recurring_expenses_menu_button.pack(side="left", padx=(0, 15), pady=15)

        self.recurring_expenses_menu_button = customTKMenuButton(
            self.toolbar_frame,
            text="Gestione Esercizio",
            items=[
                (f"Chiusura Esercizio {datetime.now().strftime('%Y')}", self.open_fiscal_year_closer_window)
            ],
        )
        self.recurring_expenses_menu_button.pack(side="left", padx=(0, 15), pady=15)


        self.refresh_view_button = ctk.CTkButton(self.toolbar_frame, text="🔄", font=("Segoe UI Emoji", 20), command=self.refresh_tabviews, width=30)
        self.refresh_view_button.pack(side="right", padx=15, pady=15)

        # Carica l'icona utente
        convert_succ, self.generic_user_icon_image = ViewUtils.create_PIL_image_from_path(os.path.join(self.images_path, "user.png"))
        if convert_succ:
            self.user_icon = ctk.CTkImage(dark_image=self.generic_user_icon_image, size=(40, 40))

            # Crea una label con l'icona invece di un button
            self.user_icon_label = ctk.CTkLabel(self.toolbar_frame, image=self.user_icon, text="", bg_color="transparent")
            self.user_icon_label.pack(side="right", padx=5, pady=15)  # padx più piccolo per avvicinare ai bottoni


        self.login_button = ctk.CTkButton(self.toolbar_frame, text="Login", command=self.manage_login)
        self.login_button.pack(side="right", padx=15, pady=15)

        # Creazione di un popup menu simulato
        self.file_menu_frame = None

        # Creazione delle tabs (frame)
        self.tabview = ctk.CTkTabview(self, width=500, height=500)
        self.tabview.pack(padx=20, pady=20, fill="both", expand=True)

        self.tabview.add("Utenti")
        self.tabview.add("Clienti")
        self.tabview.add("Fornitori")
        self.tabview.add("Produzioni")
        self.tabview.add("Conti")
        self.tabview.add("Fatture")
        self.tabview.add("Pagamenti")
        self.tabview.add("Rimborsi")
        self.tabview.add("Spese")
        self.tabview.add("Iva")
        self.tabview.add("Salario")
        self.tabview.add("Tasse")
        self.tabview.add(f"Report {datetime.now().strftime('%Y')}")
        self.tabview.add("Plots")



        self.custom_font = ctk.CTkFont("Arial", 20)
        self.tabview._segmented_button.configure(font=self.custom_font)

        self.construct_tabviews()

        self.update_idletasks()
        self.after(100, lambda: self.state("zoomed"))

        self._setup_event_subscriptions()

    def _track_after(self, ms, callback=None, *args):
        after_id = self._orig_after(ms, callback, *args)
        self._after_ids.add(after_id)
        return after_id

    def _cancel_all_after(self):
        for aid in self._after_ids:
            try:
                self.after_cancel(aid)
            except Exception:
                pass
        self._after_ids.clear()

    def construct_tabviews(self):
        """Crea solo la struttura delle tab, non il contenuto - Lazy Loading"""
        self.tab_instances = {}
        self.current_tab = "Utenti"  # Tab iniziale

        # Definisci la factory per le view
        self.view_factory = {
            "Utenti": lambda tab: UsersView(
                self.db_model, self.user_controller, self.account_controller,
                self.production_controller, self.fiscal_settings, tab,
                self.analyzer, self.event_bus, self.logged_user_id, self.login_status
            ),
            "Clienti": lambda tab: ClientsView(
                self.db_model, self.client_controller, self.production_controller,
                self.invoice_controller, self.refund_controller, self.catalogo_elenchi,
                self.config_manager, tab, self.event_bus, self.analyzer
            ),
            "Fatture": lambda tab, invoice_id=None: InvoicesView(
                self.db_model, self.invoice_controller, self.user_controller,
                self.client_controller, self.production_controller, self.payment_controller,
                self.account_controller, self.update_controller, self.tabview, self.fiscal_settings,
                self.historical_financial_data_settings, self.event_bus, self.analyzer,
                initial_invoice_id=invoice_id  # Nuovo parametro
            ),
            "Pagamenti": lambda tab, payment_id=None: PaymentsView(
                self.db_model, self.payment_controller, self.invoice_controller,
                self.user_controller, self.client_controller, self.production_controller,
                self.account_controller, self.update_controller, self.tabview,
                self.event_bus, initial_payment_id=payment_id
            ),
            "Rimborsi": lambda tab, refund_id=None: RefundsView(
                self.db_model, self.refund_controller, self.client_controller,
                self.account_controller, self.update_controller, self.tabview, self.analyzer,
                self.event_bus, initial_refund_id=refund_id
            ),
            "Produzioni": lambda tab, production_id=None: ProductionsView(
                self.db_model, self.production_controller, self.payment_controller,
                self.invoice_controller, self.user_controller, self.client_controller,
                self.catalogo_elenchi, self.config_manager,
                self.tabview, self.event_bus, self.update_controller,
                initial_production_id=production_id
            ),
            "Spese": lambda tab, expense_id=None: ExpensesView(
                self.db_model, self.expense_controller, self.user_controller,
                self.account_controller, self.supplier_controller, self.invoice_controller,
                self.update_controller, self.analyzer, self.fiscal_settings, self.catalogo_elenchi,
                self.config_manager, self.tabview, self.event_bus, initial_expense_id = expense_id
            ),
            "Fornitori": lambda tab: SuppliersView(
                self.db_model, self.supplier_controller, self.expense_controller, self.update_controller,
                self.config_manager, self.catalogo_elenchi, self.tabview,
                self.event_bus, self.analyzer
            ),
            "Conti": lambda tab: AccountsView(
                self.db_model, self.account_controller, self.update_controller,
                self.transfer_controller, self.config_manager, self.catalogo_elenchi,
                self.analyzer, self.tabview, self.event_bus
            ),
            "Salario": lambda tab, salary_id=None: SalariesView(
                self.db_model, self.salary_controller, self.user_controller,
                self.account_controller, self.update_controller, self.analyzer, self.fiscal_settings,
                self.catalogo_elenchi, self.config_manager, self.tabview, self.event_bus,
                initial_salary_id=salary_id
            ),

            "Iva": lambda tab: IvaTrimesView(self.app_context, self.tabview),

            "Tasse": lambda tab: TaxesView(self.app_context, self.tabview),

            f"Report {datetime.now().strftime('%Y')}": lambda tab: ReportView(
                self.db_model, self.fiscal_settings, self.tabview, self.analyzer,
                self.event_bus, self.update_controller
            ),
            "Plots": lambda tab: PlotView(
                self.app_context, self.tabview
            )
        }

        # MONITORAGGIO DEL CAMBIO TAB - APPROCCIO ALTERNATIVO
        self._setup_tab_monitoring()

        # Carica solo la tab iniziale
        self.load_tab(self.current_tab)

    def refresh_tabviews(self):
        """Aggiorna solo la tab corrente invece di tutte le tab"""
        if self.current_tab in self.tab_instances:
            print(f"Ricarico tab: {self.current_tab}")
            # Ricarica solo la tab corrente
            current_tab_name = self.current_tab
            self.destroy_tab(current_tab_name)
            self.load_tab(current_tab_name)

            # Forza l'aggiornamento della GUI
            self.update_idletasks()

    def _on_tab_click(self, event):
        """Gestisce il click sulle tab per il lazy loading"""
        # Ottieni l'indice del tab cliccato
        tab_index = self.tabview._segmented_button.index(f"@{event.x},{event.y}")
        if tab_index is not None:
            tab_names = list(self.view_factory.keys())
            if tab_index < len(tab_names):
                new_tab = tab_names[tab_index]
                self._switch_to_tab(new_tab)

    def load_tab(self, tab_name, **kwargs):
        """Carica una tab solo se non è già caricata, con parametri aggiuntivi"""
        if tab_name not in self.tab_instances and tab_name in self.view_factory:
            print(f"Caricamento tab: {tab_name} con parametri: {kwargs}")
            tab_frame = self.tabview.tab(tab_name)

            # Pulisci il frame della tab prima di aggiungere nuovi widget
            for widget in tab_frame.winfo_children():
                widget.destroy()

            # Crea l'istanza della view passando i kwargs
            instance = self.view_factory[tab_name](tab_frame, **kwargs)
            instance.pack(in_=tab_frame, fill="both", expand=True)
            self.tab_instances[tab_name] = instance

            # Forza il rendering
            self.update_idletasks()

    def destroy_tab(self, tab_name):
        """Distrugge completamente una tab per liberare memoria"""
        if tab_name in self.tab_instances:
            print(f"Distruzione tab: {tab_name}")
            try:
                instance = self.tab_instances[tab_name]

                # Chiama cleanup se esiste
                if hasattr(instance, 'cleanup'):
                    instance.cleanup()

                # Distruggi l'istanza
                instance.destroy()

            except Exception as e:
                print(f"Errore nel distruggere {tab_name}: {e}")
            finally:
                # Rimuovi dal dizionario
                del self.tab_instances[tab_name]

                # Forza garbage collection
                import gc
                gc.collect()

    def _setup_tab_monitoring(self):
        """Configura il monitoraggio del cambio tab usando un approccio alternativo"""
        # Crea una variabile per tracciare il tab precedente
        self._previous_tab = self.current_tab

        # Avvia il monitoraggio periodico
        self._monitor_tab_changes()

    def _monitor_tab_changes(self):
        """Monitora i cambi di tab periodicamente"""
        current_tab = self.tabview.get()

        # Se il tab è cambiato
        if current_tab != self._previous_tab:
            self._switch_to_tab(current_tab)
            self._previous_tab = current_tab

        # Continua il monitoraggio ogni 100ms
        self.after(100, self._monitor_tab_changes)

    def _switch_to_tab(self, new_tab):
        """Cambia tab con lazy loading"""
        if new_tab != self.current_tab:
            print(f"Cambio tab: {self.current_tab} -> {new_tab}")

            # Distruggi la tab precedente per liberare memoria
            if self.current_tab in self.tab_instances:
                self.destroy_tab(self.current_tab)

            # Carica la nuova tab
            self.load_tab(new_tab)
            self.current_tab = new_tab

            # Aggiorna la selezione del tabview
            self.tabview.set(new_tab)

            # Forza l'aggiornamento dell'interfaccia
            self.update_idletasks()




    def _setup_event_subscriptions(self):
        """Configura tutte le sottoscrizioni agli eventi nella MainWindow"""
        self.event_bus.subscribe(ViewUtils.EventBusKeys.SHOW_INVOICE_DETAIL, self._handle_show_invoice_detail)
        self.event_bus.subscribe(ViewUtils.EventBusKeys.SHOW_SALARY_DETAIL, self._handle_show_salary_detail)
        self.event_bus.subscribe(ViewUtils.EventBusKeys.SHOW_PRODUCTION_DETAIL, self._handle_show_production_detail)
        self.event_bus.subscribe(ViewUtils.EventBusKeys.SHOW_PAYMENT_DETAIL, self._handle_show_payment_detail)
        self.event_bus.subscribe(ViewUtils.EventBusKeys.SHOW_REFUND_DETAIL, self._handle_show_refund_detail)
        self.event_bus.subscribe(ViewUtils.EventBusKeys.SHOW_EXPENSE_DETAIL, self._handle_show_expense_detail)



    def _handle_show_invoice_detail(self, invoice_id):
        """Gestisce la navigazione verso una fattura - APRE DIRETTAMENTE IL DETTAGLIO"""
        print(f"Navigazione diretta a dettaglio fattura: {invoice_id}")

        # 1. Cambia VISIBILMENTE alla tab Fatture
        self.tabview.set("Fatture")

        # 2. Se la tab Fatture è già caricata, apri il dettaglio
        if "Fatture" in self.tab_instances:
            invoices_view = self.tab_instances["Fatture"]
            if hasattr(invoices_view, 'open_invoice_detail_tab'):
                invoices_view.open_invoice_detail_tab(invoice_id)
        else:
            # 3. Se non è caricata, caricala DIRETTAMENTE con il dettaglio
            self.load_tab("Fatture", invoice_id=invoice_id)

    def _forward_to_invoice_detail(self, invoice_id):
        """Inoltra la richiesta alla InvoicesView una volta caricata"""
        if "Fatture" in self.tab_instances:
            invoices_view = self.tab_instances["Fatture"]
            if hasattr(invoices_view, 'open_invoice_detail_tab'):
                invoices_view.open_invoice_detail_tab(invoice_id)
        else:
            # Se ancora non caricata, riprova dopo un altro breve ritardo
            self.after(100, lambda: self._forward_to_invoice_detail(invoice_id))

    def _handle_show_salary_detail(self, salary_id):
        """Gestisce la navigazione verso uno stipendio - APRE DIRETTAMENTE IL DETTAGLIO"""
        print(f"Navigazione diretta a dettaglio Salario: {salary_id}")

        # 1. Cambia VISIBILMENTE alla tab Stipendi
        self.tabview.set("Salario")

        # 2. Se la tab Salario è già caricata, apri il dettaglio
        if "Salario" in self.tab_instances:
            salaries_view = self.tab_instances["Salario"]
            if hasattr(salaries_view, 'open_salary_detail_tab'):
                salaries_view.open_salary_detail_tab(salary_id)
        else:
            # 3. Se non è caricata, caricala DIRETTAMENTE con il dettaglio
            self.load_tab("Salario", salary_id=salary_id)

    def _forward_to_salary_detail(self, salary_id):
        """Inoltra la richiesta alla SalariesView una volta caricata"""
        if "Salario" in self.tab_instances:
            salaries_view = self.tab_instances["Salario"]
            if hasattr(salaries_view, 'open_salary_detail_tab'):
                salaries_view.open_salary_detail_tab(salary_id)
        else:
            # Se ancora non caricata, riprova dopo un altro breve ritardo
            self.after(100, lambda: self._forward_to_salary_detail(salary_id))

    def _handle_show_production_detail(self, production_id):
        """Gestisce la navigazione verso una produzione - APRE DIRETTAMENTE IL DETTAGLIO"""
        print(f"Navigazione diretta a dettaglio Produzione: {production_id}")

        # 1. Cambia VISIBILMENTE alla tab Produzioni
        self.tabview.set("Produzioni")

        # 2. Se la tab Produzioni è già caricata, apri il dettaglio
        if "Produzioni" in self.tab_instances:
            productions_view = self.tab_instances["Produzioni"]
            if hasattr(productions_view, 'open_production_detail_tab'):
                productions_view.open_production_detail_tab(production_id)
        else:
            # 3. Se non è caricata, caricala DIRETTAMENTE con il dettaglio
            self.load_tab("Produzioni", production_id=production_id)

    def _forward_to_production_detail(self, production_id):
        """Inoltra la richiesta alla ProductionsView una volta caricata"""
        if "Produzioni" in self.tab_instances:
            productions_view = self.tab_instances["Produzioni"]
            if hasattr(productions_view, 'open_production_detail_tab'):
                productions_view.open_production_detail_tab(production_id)
        else:
            # Se ancora non caricata, riprova dopo un altro breve ritardo
            self.after(100, lambda: self._forward_to_production_detail(production_id))

    def _handle_show_payment_detail(self, payment_id):
        """Gestisce la navigazione verso un pagamento - APRE DIRETTAMENTE IL DETTAGLIO"""
        print(f"Navigazione diretta a dettaglio Pagamento: {payment_id}")

        # 1. Cambia VISIBILMENTE alla tab Pagamenti
        self.tabview.set("Pagamenti")

        # 2. Se la tab Pagamenti è già caricata, apri il dettaglio
        if "Pagamenti" in self.tab_instances:
            payments_view = self.tab_instances["Pagamenti"]
            if hasattr(payments_view, 'open_payment_detail_tab'):
                payments_view.open_payment_detail_tab(payment_id)
        else:
            # 3. Se non è caricata, caricala DIRETTAMENTE con il dettaglio
            self.load_tab("Pagamenti", payment_id=payment_id)

    def _forward_to_payment_detail(self, payment_id):
        """Inoltra la richiesta alla PaymentsView una volta caricata"""
        if "Pagamenti" in self.tab_instances:
            payments_view = self.tab_instances["Pagamenti"]
            if hasattr(payments_view, 'open_payment_detail_tab'):
                payments_view.open_payment_detail_tab(payment_id)
        else:
            # Se ancora non caricata, riprova dopo un altro breve ritardo
            self.after(100, lambda: self._forward_to_payment_detail(payment_id))

    def _handle_show_refund_detail(self, refund_id):
        """Gestisce la navigazione verso un rimborso - APRE DIRETTAMENTE IL DETTAGLIO"""
        print(f"Navigazione diretta a dettaglio Rimborso: {refund_id}")

        # 1. Cambia VISIBILMENTE alla tab Rimborsi
        self.tabview.set("Rimborsi")

        # 2. Se la tab Rimborsi è già caricata, apri il dettaglio
        if "Rimborsi" in self.tab_instances:
            refunds_view = self.tab_instances["Rimborsi"]
            if hasattr(refunds_view, 'open_refund_detail_tab'):
                refunds_view.open_refund_detail_tab(refund_id)
        else:
            # 3. Se non è caricata, caricala DIRETTAMENTE con il dettaglio
            self.load_tab("Rimborsi", refund_id=refund_id)

    def _forward_to_refund_detail(self, refund_id):
        """Inoltra la richiesta alla RefundsView una volta caricata"""
        if "Rimborsi" in self.tab_instances:
            refunds_view = self.tab_instances["Rimborsi"]
            if hasattr(refunds_view, 'open_refund_detail_tab'):
                refunds_view.open_refund_detail_tab(refund_id)
        else:
            # Se ancora non caricata, riprova dopo un altro breve ritardo
            self.after(100, lambda: self._forward_to_refund_detail(refund_id))

    def _handle_show_expense_detail(self, expense_id):
        """Gestisce la navigazione verso una spesa - APRE DIRETTAMENTE IL DETTAGLIO"""
        print(f"Navigazione diretta a dettaglio Spesa: {expense_id}")

        # 1. Cambia VISIBILMENTE alla tab Spese
        self.tabview.set("Spese")

        # 2. Se la tab Spese è già caricata, apri il dettaglio
        if "Spese" in self.tab_instances:
            expenses_view = self.tab_instances["Spese"]
            if hasattr(expenses_view, 'open_expense_detail_tab'):
                expenses_view.open_expense_detail_tab(expense_id)
        else:
            # 3. Se non è caricata, caricala DIRETTAMENTE con il dettaglio
            self.load_tab("Spese", expense_id=expense_id)

    def _forward_to_expense_detail(self, expense_id):
        """Inoltra la richiesta alla ExpensesView una volta caricata"""
        if "Spese" in self.tab_instances:
            expenses_view = self.tab_instances["Spese"]
            if hasattr(expenses_view, 'open_expense_detail_tab'):
                expenses_view.open_expense_detail_tab(expense_id)
        else:
            # Se ancora non caricata, riprova dopo un altro breve ritardo
            self.after(100, lambda: self._forward_to_expense_detail(expense_id))






    # funzioni per il login
    def manage_login(self):
        if self.login_status is not True:
            self.open_login_window()
        else:
            confirmation = ViewUtils.ask_confirmation_popup(self, "Vuoi eseguire il logout?")
            if confirmation:
                self.login_status = False
                self.logged_user_id = -1
                self.toggle_login_widgets()
                self.event_bus.publish(ViewUtils.EventBusKeys.LOGIN_STATUS_CHANGED.value, {
                    "login_status": False,
                    "logged_user_id": -1
                })

    def open_login_window(self):
        """Apre una finestra per fare il login."""
        # Finestra di dialogo
        self.login_window = ctk.CTkToplevel(self)
        self.login_window.title("Esegui il login")
        self.login_window.geometry("350x500")
        self.login_window.lift()
        self.login_window.grab_set()

        ctk.CTkLabel(self.login_window, text="SCEGLI L'UTENTE E INSERISCI LA PASSWORD").pack(pady=60, padx=20, fill="x", expand=True)

        #retrieve users
        users = self.user_controller.retrieve_users_map_list()

        self.login_username = ctk.CTkOptionMenu(self.login_window, values = [user[DBUsersColumns.FIRST_NAME.value] +
                                                       " " + user[DBUsersColumns.LAST_NAME.value] for user in users])
        self.login_username.pack(pady=(5,10), padx=20, fill="x", expand=True)

        ctk.CTkLabel(self.login_window, text="Password:").pack(pady=(10, 0), padx=20, fill="x", expand=True)

        self.login_password = ctk.CTkEntry(self.login_window)
        self.login_password.pack(pady=(5, 20), padx=20, fill="x", expand=True)

        ctk.CTkButton(self.login_window, text="Esegui il login",
                      command=lambda: self.try_to_login(self.login_username.get(), self.login_password.get())
                      ).pack(pady=(40, 20), padx=20)

    def try_to_login(self, username, password):
        success, message, user_id = self.user_controller.check_password_for_login(username, password)
        if success:
            ViewUtils.show_confirm_popup(self.login_window, message=message)
            self.login_status = True
            self.logged_user_id = user_id
            self.toggle_login_widgets()
            self.event_bus.publish(ViewUtils.EventBusKeys.LOGIN_STATUS_CHANGED.value, {
                "login_status": True,
                "logged_user_id": user_id
            })

        if success is not True:
            ViewUtils.show_error_popup(self.login_window, message=message)

    def toggle_login_widgets(self):
        if self.login_status is True:
            self.login_button.configure(text="Esegui Logout")

            #creo un'immagine PIL da inserire nell'icona a partire dall'immagine dell'utente
            #prendo il path dell'immagine dell'utente loggato
            logged_user_image_path = self.user_controller.retrieve_user_map_by_id(self.logged_user_id
                                                                                  ).get(DBUsersColumns.PHOTO_PATH.value)

            if logged_user_image_path is not None and logged_user_image_path != "":
                convert_succ, user_icon_image = ViewUtils.create_PIL_image_from_path(logged_user_image_path)
                if convert_succ:
                    self.user_icon.configure(dark_image=user_icon_image)

        else:
            self.login_button.configure(text="Login")
            self.user_icon.configure(dark_image=self.generic_user_icon_image)







    # Funzioni per la gestione dei backups
    def open_backups_window(self):
        """Apre una finestra per gestire i backup."""
        # Finestra di dialogo
        self.backup_window = ctk.CTkToplevel(self)
        self.backup_window.title("Impostazioni di backup")
        self.backup_window.geometry("500x420")
        self.backup_window.lift()
        self.backup_window.grab_set()

        # Leggi la configurazione attuale
        current_config = self.config_manager.load_config()
        backup_settings = current_config.get("backup_settings", {})

        # Titolo
        title = ctk.CTkLabel(self.backup_window, text="Modifica Impostazioni di Backup", font=("Arial", 18))
        title.pack(pady=20)

        # Campi per ogni impostazione
        self.entries = {}

        # Backup base path
        self.add_field(
            label="Percorso base backup",
            default_value=backup_settings.get("backup_base_path", {}).get("value", ""),
            key="backup_base_path",
            parent=self.backup_window,
            tooltip="Cartella principale dove verranno archiviati tutti i backup."
        )

        # Interval in minuti
        self.add_slider_field(
            label="Frequenza esecuzione backup (minuti)",
            default_value=backup_settings.get("interval_minutes", {}).get("value", 15),
            key="interval_minutes",
            parent=self.backup_window,
            tooltip="Imposta l'intervallo di tempo (in minuti) tra ogni backup.",
            min_val=1,
            max_val=120
        )

        # Numero massimo di backup
        self.add_slider_field(
            label="Numero massimo di backup per cartella",
            default_value=backup_settings.get("max_backups", {}).get("value", 35),
            key="max_backups",
            parent=self.backup_window,
            tooltip="Specifica il numero massimo di backup da conservare.",
            min_val=1,
            max_val=100
        )

        # Delta giorni
        self.add_slider_field(
            label="Frequenza generazione nuova cartella (giorni)",
            default_value=backup_settings.get("delta_days", {}).get("value", 7),
            key="delta_days",
            parent=self.backup_window,
            tooltip="Indica quanti giorni di differenza tra i backup da mantenere.",
            min_val=1,
            max_val=30
        )

        # Pulsante Salva
        save_button = ctk.CTkButton(self.backup_window, text="Salva Impostazioni", command=self.save_backup_settings)
        save_button.pack(pady=20)

    def add_field(self, label, default_value, key, parent, tooltip):
        """Crea un campo di input per una configurazione."""
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", pady=5, padx=10)

        label_widget = ctk.CTkLabel(frame, text=label, anchor="w")
        label_widget.pack(side="top", fill="x")

        entry = ctk.CTkEntry(frame)
        entry.insert(0, default_value)
        entry.pack(fill="x", pady=2)
        self.entries[key] = entry

    def add_slider_field(self, label, default_value, key, parent, tooltip, min_val, max_val):
        """Crea un campo slider per una configurazione numerica con una scala visibile."""
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", pady=5, padx=10)

        # Label per il titolo
        label_widget = ctk.CTkLabel(frame, text=label, anchor="w")
        label_widget.pack(side="top", fill="x")

        # Frame per slider e valore numerico
        slider_frame = ctk.CTkFrame(frame)
        slider_frame.pack(fill="x", pady=2)

        # Slider
        slider = ctk.CTkSlider(
            slider_frame,
            from_=min_val,
            to=max_val,
            number_of_steps=max_val - min_val,
            command=lambda value: self.update_slider_label(value, value_label)
        )
        slider.set(default_value)
        slider.pack(side="left", fill="x", expand=True)

        # Valore numerico accanto allo slider
        value_label = ctk.CTkLabel(slider_frame, text=f"{int(default_value)}")
        value_label.pack(side="right", padx=10)
        self.entries[key] = slider

    def update_slider_label(self, value, label_widget):
        """Aggiorna la label con il valore attuale dello slider."""
        label_widget.configure(text=f"{int(float(value))}")

    def save_backup_settings(self):
        """Salva le impostazioni di backup aggiornate nel file di configurazione."""
        new_backup_settings = {}

        # Raccogli i nuovi valori dai widget (CTkEntry e CTkSlider)
        for key, widget in self.entries.items():
            if isinstance(widget, ctk.CTkEntry):
                new_backup_settings[key] = widget.get()
            elif isinstance(widget, ctk.CTkSlider):
                new_backup_settings[key] = int(widget.get())

        try:
            # Prova ad aggiornare la sezione "backup_settings" del file di configurazione
            self.config_manager.update_config_section("backup_settings", new_backup_settings)

            # Se l'aggiornamento ha successo, chiudi la finestra e notifica l'utente
            self.backup_window.destroy()
            ViewUtils.show_error_popup(
                self,
                "Salvataggio configurazione",
                "La configurazione è stata salvata con successo.\nLe nuove impostazioni saranno ricaricate al prossimo avvio dell'app."
            )

        except Exception as e:
            # In caso di errore (es. file bloccato da un'altra applicazione), mostra un popup con il messaggio d'errore
            ViewUtils.show_error_popup(
                self,
                "Errore salvataggio configurazione",
                f"Impossibile salvare la configurazione: {str(e)}"
            )

    def open_load_backup(self):
        """Apre la finestra per selezionare e importare un backup dell'anno corrente."""

        # Evita doppia apertura
        if hasattr(self, "backup_window") and self.backup_window.winfo_exists():
            self.backup_window.lift()
            return

        self.backup_window = ctk.CTkToplevel(self)
        self.backup_window.title("Carica un vecchio database tra i backup")
        self.backup_window.geometry("720x650")
        self.backup_window.grab_set()
        self.backup_window.lift()

        # ---------- Frame principale ----------
        main_frame = ctk.CTkFrame(self.backup_window, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=12, pady=12)

        title_label = ctk.CTkLabel(
            main_frame,
            text="Seleziona un backup dell'anno corrente da importare",
            anchor="w",
            font=("Segoe UI", 14, "bold")
        )
        title_label.pack(fill="x", pady=(0, 10))

        # ---------- Lista backup (scrollabile CTk) ----------
        list_frame = ctk.CTkScrollableFrame(main_frame)
        list_frame.pack(fill="both", expand=True)

        # Stato selezione
        selected_backup = {
            "path": None,
            "datetime": None
        }

        selected_bk_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        selected_bk_frame.pack(pady=10, fill="x")
        selected_label_1 = ctk.CTkLabel(selected_bk_frame, text="Backup selezionato: ")
        selected_label_1.pack(side="left", pady=10)
        selected_label_2 = ctk.CTkLabel(selected_bk_frame, text="", font=("Arial", 16))
        selected_label_2.pack(side="left", pady=10, padx=(15, 0))

        # ---------- Bottoni ----------
        buttons_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        buttons_frame.pack(fill="x", pady=(10, 0))

        refresh_btn = ctk.CTkButton(
            buttons_frame,
            text="Aggiorna lista"
        )
        refresh_btn.pack(side="left", padx=(6, 0))

        import_btn = ctk.CTkButton(
            buttons_frame,
            text="Importa backup selezionato",
            state="disabled"
        )
        import_btn.pack(side="right", padx=(6, 0))

        # ---------- Helpers UI ----------
        def format_interval_name(interval_name):
            """Formatta il nome dell'intervallo nel formato '10-20 Dec'"""
            try:
                # Estrai le date dal nome della cartella
                # Formato: YYYYMMDD_to_YYYYMMDD
                parts = interval_name.split("_to_")
                if len(parts) != 2:
                    return interval_name

                start_date = datetime.strptime(parts[0], "%Y%m%d")
                end_date = datetime.strptime(parts[1], "%Y%m%d")

                # Formatta nel formato "10-20 Dec"
                month_names_ita = {
                    1: "Gen", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mag", 6: "Giu",
                    7: "Lug", 8: "Ago", 9: "Set", 10: "Ott", 11: "Nov", 12: "Dic"
                }

                # Se è lo stesso mese: "10-20 Ott"
                if start_date.month == end_date.month:
                    return f"{start_date.day}-{end_date.day} {month_names_ita[start_date.month]}"
                # Altrimenti: "20 Ott - 30 Nov"
                else:
                    return f"{start_date.day} {month_names_ita[start_date.month]} - {end_date.day} {month_names_ita[end_date.month]}"

            except Exception as e:
                return interval_name

        def clear_list():
            for widget in list_frame.winfo_children():
                widget.destroy()
            selected_backup["path"] = None
            selected_backup["datetime"] = None
            import_btn.configure(state="disabled")

        def populate_list():
            clear_list()
            year = datetime.now().year
            backups = self.backup_importer.list_backups_for_year(year)

            if not backups:
                ctk.CTkLabel(
                    list_frame,
                    text=f"Nessun backup trovato per l'anno {year}",
                    anchor="w"
                ).pack(fill="x", padx=6, pady=6)
                return

            # Raggruppa i backup per cartella di intervallo
            backups_by_interval = {}

            for entry in backups:
                # Estrai il nome della cartella di intervallo dal path
                # Il path è strutturato come: .../intervallo_folder/sub_folder/file
                path_parts = entry["path"].split(os.sep)
                if len(path_parts) >= 2:
                    interval_folder = path_parts[-2]  # -2 perché: .../interval_folder/sub_folder/file.db
                else:
                    interval_folder = "Unknown"

                if interval_folder not in backups_by_interval:
                    backups_by_interval[interval_folder] = []
                backups_by_interval[interval_folder].append(entry)

            # Ordina gli intervalli per data (dal più recente)
            sorted_intervals = sorted(
                backups_by_interval.keys(),
                key=lambda x: datetime.strptime(x.split("_to_")[0], "%Y%m%d") if "_to_" in x else datetime.min,
                reverse=True
            )

            # Per ogni intervallo, crea un label separatore e poi i bottoni dei backup
            for interval in sorted_intervals:
                # Label separatore per l'intervallo
                formatted_interval = format_interval_name(interval)
                separator_label = ctk.CTkLabel(
                    list_frame,
                    text=f"--------------------------       {formatted_interval}       --------------------------",
                    font=("Segoe UI", 15, "italic"),
                    text_color="#808080"  # Grigio per differenziare
                )
                separator_label.pack(fill="x", padx=6, pady=(15, 5))

                # Ordina i backup di questo intervallo per data (dal più recente)
                interval_backups = sorted(
                    backups_by_interval[interval],
                    key=lambda x: x["datetime"],
                    reverse=True
                )

                # Aggiungi i bottoni per ogni backup in questo intervallo
                for entry in interval_backups:
                    dt = entry["datetime"]
                    label_text = dt.strftime("%Y-%m-%d %H:%M:%S")

                    btn = ctk.CTkButton(
                        list_frame,
                        text=f"    {label_text}",  # Indentazione per differenziare
                        anchor="w",
                        fg_color="transparent",
                        hover_color="#212121",
                        command=lambda e=entry: on_select(e)
                    )
                    btn.pack(fill="x", padx=10, pady=2)

        def on_select(entry):
            selected_backup["path"] = entry["path"]
            selected_backup["datetime"] = entry["datetime"]
            import_btn.configure(state="normal")
            selected_label_2.configure(text=f"{selected_backup['datetime']}")

        def do_import():
            if not selected_backup["path"]:
                return

            backup_date = selected_backup["datetime"].strftime("%d/%m/%Y %H:%M")

            confirm = ViewUtils.ask_confirmation_popup(
                parent=self.backup_window,
                message=(
                    f"Importare questo backup comporta la perdita dei dati inseriti "
                    f"da {backup_date} ad oggi.\n\n"
                    f"Desideri continuare?"
                ),
                title="CONFERMA IMPORT BACKUP"
            )

            if not confirm:
                return

            success, msg = self.backup_importer.import_backup(selected_backup["path"])

            if success:
                ViewUtils.show_confirm_popup(self.backup_window)
            else:
                ViewUtils.show_error_popup(self.backup_window, "", f"Si è verificato un errore: {msg}")

        # ---------- Bind ----------
        import_btn.configure(command=do_import)
        refresh_btn.configure(command=populate_list)

        populate_list()



    # Funzioni per la gestione dei dati fiscali
    def open_fiscal_settings_window(self):
        """Apre una finestra per gestire i dati fiscali."""
        # Crea la finestra di dialogo
        self.fiscal_settings_window = ctk.CTkToplevel(self)
        self.fiscal_settings_window.title("Dati Fiscali")
        self.fiscal_settings_window.geometry("850x950+0+0")
        self.fiscal_settings_window.lift()
        self.fiscal_settings_window.grab_set()

        # Inizializza i dizionari per salvare i riferimenti ai widget
        self.iva_labels = {}
        self.iva_entries = {}
        self.forfettaria_labels = {}
        self.forfettaria_entries = {}
        self.ordinaria_labels = {}
        self.ordinaria_entries = {}
        self.ordinaria_irpef_entries = {}  # per gli scaglioni dinamici "aliquota_irpef_..."
        self.ordinaria_imponibili_entries = {}
        self.ordinaria_rateizzazione_entries = {}
        self.forfettaria_rateizzazione_entries = {}
        self.scaglioni_containers = {}
        self.title_frames = {}

        # Carica la configurazione corrente e prendi la sezione "fiscal_settings"
        current_config = self.config_manager.load_config()
        fiscal_settings = current_config.get("fiscal_settings", {})

        # Titolo principale
        title = ctk.CTkLabel(
            self.fiscal_settings_window,
            text="Modifica i dati fiscali in base alla legge vigente",
            font=("Arial", 22)
        )
        title.pack(pady=20)

        # Crea le tabs
        tabview = ctk.CTkTabview(self.fiscal_settings_window, width=500, height=500)
        tabview.pack(padx=20, pady=20, fill="both", expand=True)
        tabview.add("FORFETTARIA")
        tabview.add("ORDINARIA")
        tabview.add("IVA")
        tabview._segmented_button.configure(font=ctk.CTkFont("Arial", 16))

        # Crea i container scrollabili per ciascuna tab
        container_forfettaria = ctk.CTkScrollableFrame(tabview.tab("FORFETTARIA"))
        container_forfettaria.pack(fill="both", expand=True, padx=20, pady=10)
        container_ordinaria = ctk.CTkScrollableFrame(tabview.tab("ORDINARIA"))
        container_ordinaria.pack(fill="both", expand=True, padx=20, pady=10)
        container_iva = ctk.CTkScrollableFrame(tabview.tab("IVA"))
        container_iva.pack(fill="both", expand=True, padx=20, pady=10)

        # --- Sezione IVA ---
        iva_data = fiscal_settings.get("iva", {})  # Ora la sezione si chiama "iva"
        section_iva = ctk.CTkFrame(container_iva)
        section_iva.pack(fill="x", pady=(5, 70), padx=10)

        # Titolo della sezione IVA
        self.iva_labels["title"] = ctk.CTkLabel(section_iva, text="Aliquote IVA", font=("Arial", 18, "bold"))
        self.iva_labels["title"].pack(anchor="w", padx=10)

        # Lista delle chiavi in ordine desiderato
        iva_keys = [
            "no_iva",
            "aliquota_iva_ordinaria",
            "aliquota_iva_ridotta_1",
            "aliquota_iva_ridotta_2",
            "aliquota_iva_minima"
        ]

        # Per ogni aliquota IVA si crea una label e un entry
        for key in iva_keys:
            # Crea una label per il titolo dell'aliquota con un testo leggibile
            label_text = key.replace("_", " ").capitalize()
            label = ctk.CTkLabel(section_iva, text=label_text, font=("Arial", 14))
            label.pack(anchor="w", padx=10, pady=(15, 5) if key == "aliquota_iva_ordinaria" else 5)

            # Crea l'entry e inserisce il valore della chiave (se esistente)
            entry = ctk.CTkEntry(section_iva)
            entry.insert(0, str(iva_data.get(key, {}).get("value", "")))
            entry.pack(anchor="w", fill="x", padx=10, pady=(5, 2))
            self.iva_entries[key] = entry

            # Aggiungi una label per la descrizione corrispondente
            description = iva_data.get(key, {}).get("description", "")
            desc_label = ctk.CTkLabel(section_iva, text=description, font=("Arial", 12, "italic"), text_color="gray")
            desc_label.pack(anchor="w", padx=10, pady=(0, 15))

        # --- Sezione Forfettaria ---
        piva_forf_data = fiscal_settings.get("partita_iva_forfettaria", {})
        section_forf = ctk.CTkFrame(container_forfettaria)
        section_forf.pack(fill="x", pady=(5, 70), padx=10)
        self.forfettaria_labels["title"] = ctk.CTkLabel(section_forf, text="Partita IVA Forfettaria",
                                                        font=("Arial", 18, "bold"))
        self.forfettaria_labels["title"].pack(anchor="w", pady=(0, 5), padx=10)

        # Sottosezione: Aliquote & Parametri
        frame_forf_aliquote = ctk.CTkFrame(section_forf, corner_radius=2)
        frame_forf_aliquote.pack(fill="x", pady=(5, 5), padx=(0, 10))
        self.forfettaria_labels["aliquote_title"] = ctk.CTkLabel(frame_forf_aliquote, text="Aliquote & Parametri",
                                                                 font=("Arial", 16, "bold"))
        self.forfettaria_labels["aliquote_title"].pack(anchor="w", pady=(5, 15), padx=10)
        for key in ["aliquota_irpef_min", "aliquota_irpef_max", "anni_agevolazione", "aliquota_inps", "aliquota_rivalsa_inps"]:
            data = piva_forf_data.get(key, {})
            value = data.get("value", "")
            description = data.get("description", key)
            lbl = ctk.CTkLabel(frame_forf_aliquote, text=description, font=("Arial", 16))
            lbl.pack(anchor="w", padx=10, pady=5)
            self.forfettaria_labels[key] = lbl
            ent = ctk.CTkEntry(frame_forf_aliquote)
            ent.insert(0, str(value))
            ent.pack(anchor="w", fill="x", pady=(5, 15), padx=10)
            self.forfettaria_entries[key] = ent

        # Sottosezione: Imponibile
        frame_forf_imponibili = ctk.CTkFrame(section_forf, corner_radius=2)
        frame_forf_imponibili.pack(fill="x", pady=(35, 5), padx=(0, 10))
        self.forfettaria_labels["imponibile_title"] = ctk.CTkLabel(frame_forf_imponibili, text="Imponibile",
                                                                   font=("Arial", 16, "bold"))
        self.forfettaria_labels["imponibile_title"].pack(anchor="w", pady=(5, 15), padx=10)
        data = piva_forf_data.get("imponibile", {})
        value = data.get("value", "")
        description = data.get("description", "Imponibile")
        self.forfettaria_labels["imponibile_desc"] = ctk.CTkLabel(frame_forf_imponibili, text=description,
                                                                  font=("Arial", 16))
        self.forfettaria_labels["imponibile_desc"].pack(anchor="w", padx=10, pady=5)
        self.forfettaria_entries["imponibile"] = ctk.CTkEntry(frame_forf_imponibili)
        self.forfettaria_entries["imponibile"].insert(0, str(value))
        self.forfettaria_entries["imponibile"].pack(anchor="w", fill="x", pady=(5, 15), padx=10)


        # Sottosezione: versamenti
        frame_forf_rateizzazione = ctk.CTkFrame(section_forf, corner_radius=2)
        frame_forf_rateizzazione.pack(fill="x", pady=(35, 5), padx=(0, 10))
        self.forfettaria_labels["rateizzazione_title"] = ctk.CTkLabel(frame_forf_rateizzazione, text="Rateizzazione Tasse",
                                                                 font=("Arial", 16, "bold"))
        self.forfettaria_labels["rateizzazione_title"].pack(anchor="w", pady=(5, 15), padx=10)
        for key in ["percentuale_acconto_imposta_primo", "percentuale_acconto_imposta_secondo", "percentuale_acconto_inps_forfettario", "percentuale_rata_acconto_inps_forfettario"]:
            if key in piva_forf_data:
                data = piva_forf_data.get(key, {})
                value = data.get("value", "")
                description = data.get("description", key)
                lbl = ctk.CTkLabel(frame_forf_rateizzazione, text=description, font=("Arial", 14))
                lbl.pack(anchor="w", padx=10, pady=5)
                self.forfettaria_labels[key] = lbl
                ent = ctk.CTkEntry(frame_forf_rateizzazione)
                ent.insert(0, str(value))
                ent.pack(anchor="w", fill="x", pady=(5, 15), padx=10)
                self.forfettaria_rateizzazione_entries[key] = ent





        # --- Sezione Ordinaria ---
        piva_ord_data = fiscal_settings.get("partita_iva_ordinaria", {})
        section_ord = ctk.CTkFrame(container_ordinaria)
        section_ord.pack(fill="x", pady=(5, 70), padx=10)
        self.ordinaria_labels["title"] = ctk.CTkLabel(section_ord, text="Partita IVA Ordinaria",
                                                      font=("Arial", 18, "bold"))
        self.ordinaria_labels["title"].pack(anchor="w", pady=(0, 5), padx=10)

        # Sottosezione: Aliquote
        frame_ord_aliquote = ctk.CTkFrame(section_ord, corner_radius=2)
        frame_ord_aliquote.pack(fill="x", pady=(5, 5), padx=(0, 10))
        self.ordinaria_labels["aliquote_title"] = ctk.CTkLabel(frame_ord_aliquote, text="Aliquote",
                                                               font=("Arial", 16, "bold"))
        self.ordinaria_labels["aliquote_title"].pack(anchor="w", pady=(5, 15), padx=10)
        # Frame dedicato agli scaglioni IRPEF (dinamici)
        self.frame_ord_aliquote_irpef = ctk.CTkFrame(frame_ord_aliquote, corner_radius=2)
        self.frame_ord_aliquote_irpef.pack(anchor="w", pady=(5, 15), padx=10, fill="x")
        # Itera in modo dinamico per gli scaglioni "aliquota_irpef_..."
        pattern = re.compile(r'^aliquota_irpef_(\d+)$')
        aliquote_keys = []
        for key in piva_ord_data.keys():
            match = pattern.match(key)
            if match:
                idx = int(match.group(1))
                aliquote_keys.append((idx, key))
        aliquote_keys.sort(key=lambda x: x[0])
        for idx_scaglione, key_scaglione in aliquote_keys:
            data = piva_ord_data.get(key_scaglione, {})
            value = data.get("value", "")
            reddito_min = data.get("reddito_min", "")
            reddito_max = data.get("reddito_max", "")
            description = data.get("description", key_scaglione)

            # Crea un container per questo scaglione
            scaglione_container = ctk.CTkFrame(self.frame_ord_aliquote_irpef, corner_radius=2)
            scaglione_container.pack(pady=5, fill="x", expand=True, padx=10)
            title_frame = ctk.CTkFrame(scaglione_container)
            title_frame.pack(fill="x", expand=True)
            lbl = ctk.CTkLabel(title_frame, text=description, font=("Arial", 16))
            lbl.pack(side=ctk.LEFT, anchor="w", padx=10, pady=5)

            #Aggiungo il container alla lista dei containers degli scaglioni
            self.scaglioni_containers[key_scaglione] = scaglione_container

            # Bottone per cancellare l'ultimo scaglione
            if idx_scaglione == len(aliquote_keys):
                self.delete_scaglione_button = ctk.CTkButton(title_frame, text="Cancella",
                                            command=lambda key=key_scaglione: self.delete_scaglione_irpef(key))

                self.delete_scaglione_button.pack(side=ctk.RIGHT, anchor="e", padx=10, pady=5)


            # Salva il riferimento al label
            self.ordinaria_labels[key_scaglione] = lbl
            self.title_frames[key_scaglione] = title_frame

            entries_frame = ctk.CTkFrame(scaglione_container)
            entries_frame.pack(pady=(0, 35), fill="x", expand=True)
            # Entry per "value"
            value_lbl = ctk.CTkLabel(entries_frame, text="Valore:")
            value_lbl.pack(side=ctk.LEFT, fill="x", expand=True)
            value_ent = ctk.CTkEntry(entries_frame)
            value_ent.insert(0, str(value))
            value_ent.pack(pady=(5, 15), padx=(5, 20), side=ctk.LEFT, fill="x", expand=True)
            # Entry per "reddito_min"
            min_lbl = ctk.CTkLabel(entries_frame, text="Reddito\nMinimo:")
            min_lbl.pack(side=ctk.LEFT, fill="x", expand=True)
            min_ent = ctk.CTkEntry(entries_frame)
            min_ent.insert(0, str(reddito_min))
            min_ent.pack(pady=(5, 15), padx=(5, 20), side=ctk.LEFT, fill="x", expand=True)
            # Entry per "reddito_max"
            max_lbl = ctk.CTkLabel(entries_frame, text="Reddito\nMassimo:")
            max_lbl.pack(side=ctk.LEFT, fill="x", expand=True)
            max_ent = ctk.CTkEntry(entries_frame)
            max_ent.insert(0, str(reddito_max))
            max_ent.pack(pady=(5, 15), padx=(5, 20), side=ctk.LEFT, fill="x", expand=True)
            # Salva i riferimenti in un dizionario usando la chiave dello scaglione
            self.ordinaria_irpef_entries[key_scaglione] = {
                "value": value_ent,
                "reddito_min": min_ent,
                "reddito_max": max_ent,
                "description": description
            }
        # Bottone per aggiungere un nuovo scaglione IRPEF
        self.add_scaglione_button = ctk.CTkButton(self.frame_ord_aliquote_irpef, text="Aggiungi Scaglione",
                                             command=lambda: self.add_scaglione_irpef())
        self.add_scaglione_button.pack(pady=(0, 20))

        # Sottosezione: Altri parametri (es. aliquota_inps, aliquota_cassa_inps, aliquota_ritenuta)
        for key in ["aliquota_inps", "aliquota_cassa_inps", "aliquota_ritenuta"]:
            if key in piva_ord_data:
                data = piva_ord_data.get(key, {})
                value = data.get("value", "")
                description = data.get("description", key)
                lbl = ctk.CTkLabel(frame_ord_aliquote, text=description, font=("Arial", 16))
                lbl.pack(anchor="w", padx=10, pady=5)
                self.ordinaria_labels[key] = lbl
                ent = ctk.CTkEntry(frame_ord_aliquote)
                ent.insert(0, str(value))
                ent.pack(anchor="w", fill="x", pady=(5, 15), padx=10)
                self.ordinaria_entries[key] = ent

        # Sottosezione: Imponibili
        frame_ord_imponibili = ctk.CTkFrame(section_ord, corner_radius=2)
        frame_ord_imponibili.pack(fill="x", pady=(35, 5), padx=(0, 10))
        self.ordinaria_labels["imponibili_title"] = ctk.CTkLabel(frame_ord_imponibili, text="Imponibili",
                                                                 font=("Arial", 16, "bold"))
        self.ordinaria_labels["imponibili_title"].pack(anchor="w", pady=(5, 15), padx=10)
        for key in ["imponibile_iva", "imponibile_ritenuta_acconto", "imponibile_cassa_inps", "imponibile_inps",
                    "imponibile_irpef"]:
            if key in piva_ord_data:
                data = piva_ord_data.get(key, {})
                value = data.get("value", "")
                description = data.get("description", key)
                lbl = ctk.CTkLabel(frame_ord_imponibili, text=description, font=("Arial", 16))
                lbl.pack(anchor="w", padx=10, pady=5)
                self.ordinaria_labels[key] = lbl
                ent = ctk.CTkEntry(frame_ord_imponibili)
                ent.insert(0, str(value))
                ent.pack(anchor="w", fill="x", pady=(5, 15), padx=10)
                self.ordinaria_imponibili_entries[key] = ent


        # Sottosezione: Rateizzazione tasse
        frame_ord_rateizzazione = ctk.CTkFrame(section_ord, corner_radius=2)
        frame_ord_rateizzazione.pack(fill="x", pady=(35, 5), padx=(0, 10))
        self.ordinaria_labels["rateizzazione_title"] = ctk.CTkLabel(frame_ord_rateizzazione, text="Rateizzazione Tasse",
                                                                 font=("Arial", 16, "bold"))
        self.ordinaria_labels["rateizzazione_title"].pack(anchor="w", pady=(5, 15), padx=10)
        for key in ["percentuale_acconto_irpef_primo", "percentuale_acconto_irpef_secondo", "percentuale_acconto_inps", "percentuale_rata_acconto_inps"]:
            if key in piva_ord_data:
                data = piva_ord_data.get(key, {})
                value = data.get("value", "")
                description = data.get("description", key)
                lbl = ctk.CTkLabel(frame_ord_rateizzazione, text=description, font=("Arial", 16))
                lbl.pack(anchor="w", padx=10, pady=5)
                self.ordinaria_labels[key] = lbl
                ent = ctk.CTkEntry(frame_ord_rateizzazione)
                ent.insert(0, str(value))
                ent.pack(anchor="w", fill="x", pady=(5, 15), padx=10)
                self.ordinaria_rateizzazione_entries[key] = ent

        # Pulsante per salvare (command vuoto per ora)
        self.save_button = ctk.CTkButton(self.fiscal_settings_window, text="Salva Dati Fiscali", command=lambda: self.save_fiscal_settings())
        self.save_button.pack(pady=20)

    def add_scaglione_irpef(self):
        self.add_scaglione_button.pack_forget()
        description = ""
        key_scaglione = ""
        if len(self.scaglioni_containers) == 0:
            description = "Aliquota IRPEF per il primo scaglione di reddito"
            key_scaglione = "aliquota_irpef_1"
        elif len(self.scaglioni_containers) == 1:
            description = "Aliquota IRPEF per il secondo scaglione di reddito"
            key_scaglione = "aliquota_irpef_2"
        elif len(self.scaglioni_containers) == 2:
            description = "Aliquota IRPEF per il terzo scaglione di reddito"
            key_scaglione = "aliquota_irpef_3"
        elif len(self.scaglioni_containers) == 3:
            description = "Aliquota IRPEF per il quarto scaglione di reddito"
            key_scaglione = "aliquota_irpef_4"
        elif len(self.scaglioni_containers) == 4:
            description = "Aliquota IRPEF per il quinto scaglione di reddito"
            key_scaglione = "aliquota_irpef_5"
        elif len(self.scaglioni_containers) == 5:
            description = "Aliquota IRPEF per il sesto scaglione di reddito"
            key_scaglione = "aliquota_irpef_6"
        elif len(self.scaglioni_containers) == 6:
            ViewUtils.show_error_popup(self, "ERRORE", "Raggiunto numero massimo di scaglioni inseribili")
            self.add_scaglione_button.pack(pady=(0, 20))
            self.add_scaglione_button.configure(state=ctk.DISABLED)
            return

        # Crea un container per questo scaglione
        scaglione_container = ctk.CTkFrame(self.frame_ord_aliquote_irpef, corner_radius=2)
        scaglione_container.pack(pady=5, fill="x", expand=True, padx=10)
        title_frame = ctk.CTkFrame(scaglione_container)
        title_frame.pack(fill="x", expand=True)
        lbl = ctk.CTkLabel(title_frame, text=description, font=("Arial", 16))
        lbl.pack(side=ctk.LEFT, anchor="w", padx=10, pady=5)

        # Aggiungo il container alla lista dei containers degli scaglioni
        self.scaglioni_containers[key_scaglione] = scaglione_container

        # Salva il riferimento al label e al titolo
        self.ordinaria_labels[key_scaglione] = lbl
        self.title_frames[key_scaglione] = title_frame

        entries_frame = ctk.CTkFrame(scaglione_container)
        entries_frame.pack(pady=(0, 35), fill="x", expand=True)
        # Entry per "value"
        value_lbl = ctk.CTkLabel(entries_frame, text="Valore:")
        value_lbl.pack(side=ctk.LEFT, fill="x", expand=True)
        value_ent = ctk.CTkEntry(entries_frame)
        value_ent.insert(0, str(0))
        value_ent.pack(pady=(5, 15), padx=(5, 20), side=ctk.LEFT, fill="x", expand=True)
        # Entry per "reddito_min"
        min_lbl = ctk.CTkLabel(entries_frame, text="Reddito\nMinimo:")
        min_lbl.pack(side=ctk.LEFT, fill="x", expand=True)
        min_ent = ctk.CTkEntry(entries_frame)
        min_ent.insert(0, str(0))
        min_ent.pack(pady=(5, 15), padx=(5, 20), side=ctk.LEFT, fill="x", expand=True)
        # Entry per "reddito_max"
        max_lbl = ctk.CTkLabel(entries_frame, text="Reddito\nMassimo:")
        max_lbl.pack(side=ctk.LEFT, fill="x", expand=True)
        max_ent = ctk.CTkEntry(entries_frame)
        max_ent.insert(0, str(0))
        max_ent.pack(pady=(5, 15), padx=(5, 20), side=ctk.LEFT, fill="x", expand=True)
        # Salva i riferimenti in un dizionario usando la chiave dello scaglione
        self.ordinaria_irpef_entries[key_scaglione] = {
            "value": value_ent,
            "reddito_min": min_ent,
            "reddito_max": max_ent,
            "description": description
        }

        self.add_scaglione_button.pack(pady=(0, 20))
        self.delete_scaglione_button.pack_forget()
        self.delete_scaglione_button = ctk.CTkButton(self.title_frames[key_scaglione], text="Cancella", command=lambda: self.delete_scaglione_irpef(key_scaglione))
        self.delete_scaglione_button.pack(side=ctk.RIGHT, anchor="e", padx=10, pady=5)

    def delete_scaglione_irpef(self, key):
        self.scaglioni_containers[key].pack_forget()
        self.scaglioni_containers.pop(key)
        self.title_frames.pop(key)
        self.ordinaria_irpef_entries.pop(key)
        last_key = list(self.scaglioni_containers)[-1]

        self.delete_scaglione_button = ctk.CTkButton(self.title_frames[last_key], text="Cancella", command=lambda: self.delete_scaglione_irpef(last_key))
        self.delete_scaglione_button.pack(side=ctk.RIGHT, anchor="e", padx=10, pady=5)

        if len(self.scaglioni_containers) < 7:
            self.add_scaglione_button.configure(state=ctk.ACTIVE)

    def save_fiscal_settings(self):
        """
        Raccoglie tutti i valori presenti nelle entry delle tre tab (IVA, Forfettaria e Ordinaria)
        e li organizza in un dizionario strutturato in modo da poterlo passare al ConfigManager.

        La struttura restituita sarà simile a:
        {
          "iva": {
               "aliquota_iva_ordinaria": {"value": ..., "description": ...},
               "aliquota_iva_ridotta_1": {"value": ..., "description": ...},
               "aliquota_iva_ridotta_2": {"value": ..., "description": ...},
               "aliquota_iva_minima": {"value": ..., "description": ...}
          },
          "partita_iva_forfettaria": {
                "aliquota_irpef_min": {"value": ...},
                "aliquota_irpef_max": {"value": ...},
                "anni_agevolazione": {"value": ...},
                "aliquota_inps": {"value": ...},
                "aliquota_rivalsa_inps": {"value": ...},
                "imponibile": {"value": ...}
          },
          "partita_iva_ordinaria": {
                // Scaglioni dinamici IRPEF:
                "aliquota_irpef_1": {"value": ..., "reddito_min": ..., "reddito_max": ..., "description": ...},
                "aliquota_irpef_2": {"value": ..., "reddito_min": ..., "reddito_max": ..., "description": ...},
                // Altri parametri:
                "aliquota_inps": {"value": ...},
                "aliquota_cassa_inps": {"value": ...},
                "aliquota_ritenuta": {"value": ...},
                // Imponibili:
                "imponibile_iva": {"value": ...},
                "imponibile_ritenuta_acconto": {"value": ...},
                "imponibile_cassa_inps": {"value": ...},
                "imponibile_inps": {"value": ...},
                "imponibile_irpef": {"value": ...}
          }
        }
        """
        fiscal_data = {}

        # --- Sezione IVA ---
        iva_data = {}
        iva_keys = [
            "aliquota_iva_ordinaria",
            "aliquota_iva_ridotta_1",
            "aliquota_iva_ridotta_2",
            "aliquota_iva_minima"
        ]
        for key in iva_keys:
            if key in self.iva_entries:
                value = self.iva_entries[key].get()
                iva_data[key] = {"value": value}
            else:
                iva_data[key] = {"value": ""}
        fiscal_data["iva"] = iva_data


        # --- Sezione Partita IVA Forfettaria ---
        forf_data = {}
        for key in ["aliquota_irpef_min", "aliquota_irpef_max", "anni_agevolazione", "aliquota_inps",
                    "aliquota_rivalsa_inps", "imponibile", "percentuale_acconto_imposta_primo",
                    "percentuale_acconto_imposta_secondo", "percentuale_acconto_inps_forfettario",
                    "percentuale_rata_acconto_inps_forfettario"]:
            if key in self.forfettaria_entries:
                forf_data[key] = {"value": self.forfettaria_entries[key].get()}
            else:
                forf_data[key] = {"value": ""}
        fiscal_data["partita_iva_forfettaria"] = forf_data

        # --- Sezione Partita IVA Ordinaria ---
        ord_data = {}
        # Scaglioni IRPEF (dinamici)
        for key, widgets in self.ordinaria_irpef_entries.items():
            ord_data[key] = {
                "value": widgets["value"].get(),
                "reddito_min": widgets["reddito_min"].get(),
                "reddito_max": widgets["reddito_max"].get(),
                "description": widgets.get("description", "")
            }
        # Altri parametri fissi (es. aliquota_inps, aliquota_cassa_inps, aliquota_ritenuta)
        for key, widget in self.ordinaria_entries.items():
            ord_data[key] = {"value": widget.get()}
        # Imponibili
        for key, widget in self.ordinaria_imponibili_entries.items():
            ord_data[key] = {"value": widget.get()}
        fiscal_data["partita_iva_ordinaria"] = ord_data
        # Rateizzazione
        for key, widget in self.ordinaria_rateizzazione_entries.items():
            ord_data[key] = {"value": widget.get()}
        fiscal_data["partita_iva_ordinaria"] = ord_data

        try:
            self.config_manager.update_fiscal_settings(fiscal_data)
            ViewUtils.show_confirm_popup(self.fiscal_settings_window, "INFO", "Dati fiscali aggiornati con successo")
        except Exception as e:
            ViewUtils.show_error_popup(self.fiscal_settings_window, "ERRORE",
                                       f"Impossibile aggiornare i dati fiscali: {str(e)}")




    #funzioni per la gestione delle spese ricorrenti
    def open_recurring_expenses_window(self):
        """Apre una finestra per gestire le spese ricorrenti."""
        # Crea la finestra di dialogo
        self.recurring_expenses_window = ctk.CTkToplevel(self)
        self.recurring_expenses_window.title("Gestione Spese Ricorrenti")
        self.recurring_expenses_window.geometry("1000x800+0+0")
        self.recurring_expenses_window.lift()
        self.recurring_expenses_window.grab_set()

        # Configurazione font
        self.label_font = ctk.CTkFont("Arial", size=16)  # Font più grande per i labels
        self.entry_font = ctk.CTkFont("Arial", size=14)
        self.button_font = ctk.CTkFont("Arial", size=16, weight="bold")

        # Dizionario per memorizzare i widget
        self.expense_widgets = {}

        # Bottone di salvataggio unico
        add_expense_button = ctk.CTkButton(
            self.recurring_expenses_window,
            text="Aggiungi una spesa ricorrente",
            command=self.add_recurring_expenses,
            font=self.button_font
        )
        add_expense_button.pack(pady=20)

        # Crea le tabs per ogni spesa
        self.expenses_tabview = ctk.CTkTabview(self.recurring_expenses_window)
        self.expenses_tabview.pack(padx=20, pady=20, fill="both", expand=True)

        # Aggiungi una tab per ogni spesa esistente
        for expense_key, expense in self.recurring_expenses_settings.items():
            tab_name = expense.description
            self.expenses_tabview.add(tab_name)
            tab = self.expenses_tabview.tab(tab_name)
            self.expenses_tabview._segmented_button.configure(font=self.button_font)

            # Crea il container scrollabile
            container = ctk.CTkScrollableFrame(tab)
            container.pack(fill="both", expand=True, padx=20, pady=10)

            # Memorizza i widget in un dizionario annidato
            self.expense_widgets[expense_key] = {}

            suppliers_map_list = self.supplier_controller.retrieve_suppliers_map_list()

            aliquote_list = [
                self.fiscal_settings.aliquota_iva.no_iva,
                self.fiscal_settings.aliquota_iva.aliquota_iva_ordinaria,
                self.fiscal_settings.aliquota_iva.aliquota_iva_ridotta_1,
                self.fiscal_settings.aliquota_iva.aliquota_iva_ridotta_2,
                self.fiscal_settings.aliquota_iva.aliquota_iva_minima
            ]

            accounts = self.account_controller.retrieve_accounts_map_list()

            users = self.user_controller.retrieve_users_map_list()

            # Campi modificabili
            fields = [
                ('amount', 'Importo:', 'entry', float),
                ('supplier', 'Fornitore:', 'dropdown', [supplier[DBSuppliersColumns.NAME.value] for supplier in suppliers_map_list]),
                ('category', 'Categoria:', 'dropdown', [value for key, value in self.catalogo_elenchi["expenses_category"]]),
                ('iva', 'IVA:', 'dropdown', [str(aliquota) for aliquota in aliquote_list]),
                ('deductor', 'Deduzione a\ncarico di:', 'dropdown', [user[DBUsersColumns.FIRST_NAME.value] + " " + user[DBUsersColumns.LAST_NAME.value] for user in users]),
                ('account', 'Conto:', 'dropdown', [account[DBAccountsColumns.NAME.value] for account in accounts]),
                ('frequency', 'Frequenza:', 'dropdown', [freq.value for freq in ExpenseController.RecurringExpensesFrequencies])
            ]

            for field, label_text, field_type, options in fields:
                frame = ctk.CTkFrame(container)
                frame.pack(fill="x", pady=15)

                lbl = ctk.CTkLabel(frame, text=label_text, width=120, font=self.label_font)
                lbl.pack(side="left", padx=5)

                if field_type == 'entry':
                    widget = ctk.CTkEntry(frame, font=self.entry_font)
                    widget.insert(0, str(getattr(expense, field)))
                elif field_type == 'dropdown':
                    # per la categoria, aggiungo l'opzione ADD e il command
                    if field == 'category':
                        widget = ctk.CTkOptionMenu(
                            master=frame,
                            values=options,
                            font=self.entry_font,
                            dropdown_font=self.entry_font,
                            command=lambda sel, ek=expense_key: self.open_add_expense_category(ek, sel)
                        )
                        # imposto valore corrente
                        current = getattr(expense, field)
                        widget.set(current if current in options else options[0])
                    elif field == "deductor":
                        current_id = getattr(expense, field)
                        current_deductor = self.user_controller.retrieve_user_map_by_id(current_id)
                        widget = ctk.CTkOptionMenu(
                            master=frame,
                            values=options,
                            font=self.entry_font,
                            dropdown_font=self.entry_font
                        )
                        if expense.deductible:
                            deductor_name = current_deductor[DBUsersColumns.FIRST_NAME.value] + " " + current_deductor[DBUsersColumns.LAST_NAME.value]
                        else:
                            deductor_name = "Nessuno"
                        widget.set(deductor_name)
                    else:
                        widget = ctk.CTkOptionMenu(
                            master=frame,
                            values=options,
                            font=self.entry_font,
                            dropdown_font=self.entry_font
                        )
                        current = getattr(expense, field)
                        widget.set(current)

                widget.pack(fill="x", expand=True, padx=5)
                self.expense_widgets[expense_key][field] = widget

            # Campi booleani con radio button
            for field, label_text in [('deductible', 'Deduzione:')]:
                frame = ctk.CTkFrame(container)
                frame.pack(fill="x", pady=15)

                lbl = ctk.CTkLabel(frame, text=label_text, width=120, font=self.label_font)
                lbl.pack(side="left", padx=5)

                radio_frame = ctk.CTkFrame(frame)
                radio_frame.pack(side="left", fill="x", expand=True)

                var = ctk.StringVar(value="Sì" if getattr(expense,field) else "No")

                for option in ["Sì", "No"]:
                    rb = ctk.CTkRadioButton(
                        radio_frame,
                        text=option,
                        variable=var,
                        value=option,
                        font=self.entry_font
                    )
                    rb.pack(side="left", padx=10)

                self.expense_widgets[expense_key][field] = var


            for field, label_text in [('status', 'Stato:')]:
                frame = ctk.CTkFrame(container)
                frame.pack(fill="x", pady=15)

                lbl = ctk.CTkLabel(frame, text=label_text, width=120, font=self.label_font)
                lbl.pack(side="left", padx=5)

                radio_frame = ctk.CTkFrame(frame)
                radio_frame.pack(side="left", fill="x", expand=True)

                var = ctk.StringVar(value=ExpenseController.RecurringExpensesStatus.ATTIVA.value if getattr(expense, field) else ExpenseController.RecurringExpensesStatus.SOSPESA.value)

                for option in [stati.value for stati in ExpenseController.RecurringExpensesStatus]:
                    rb = ctk.CTkRadioButton(
                        radio_frame,
                        text=option,
                        variable=var,
                        value=option,
                        font=self.entry_font
                    )
                    rb.pack(side="left", padx=10)

                self.expense_widgets[expense_key][field] = var

        # Bottone di salvataggio unico
        save_button = ctk.CTkButton(
            self.recurring_expenses_window,
            text="Salva Tutte le Modifiche",
            command=self.save_recurring_expenses,
            font=self.button_font
        )
        save_button.pack(pady=20)

    def save_recurring_expenses(self):
        """Salva tutte le modifiche, comprese le nuove spese ricorrenti."""
        new_data = {}

        for expense_key, widgets in self.expense_widgets.items():

            deductible = widgets["deductible"].get()

            deductor_name = widgets["deductor"].get()
            deductor = self.user_controller.retrieve_user_map_by_extended_name(deductor_name) if deductible == "Sì" else None
            deductor_id = deductor[DBUsersColumns.ID.value] if deductor is not None else None

            # Se è la tab “Nuova Spesa”, creo un nuovo key
            if expense_key == "Nuova Spesa":
                raw_name = widgets["name"].get().strip()
                if not raw_name:
                    continue  # nulla da salvare se non c'è nome

                # description scalare in uppercase
                description = raw_name.upper()

                # chiave normalizzata per il JSON
                new_key = raw_name.lower().replace(" ", "_")

                # campi basati sui widget della nuova tab
                fields = {
                    "description": description,
                    "amount": widgets["amount"].get(),
                    "supplier": widgets["supplier"].get(),
                    "deductible": widgets["deductible"].get(),
                    "category": widgets["category"].get(),
                    "deductor": deductor_id if deductible == "Sì" else None,
                    "iva": widgets["iva"].get(),
                    "account": widgets["account"].get(),
                    "frequency": widgets["frequency"].get(),
                    "status": widgets["status"].get(),
                }
                new_data[new_key] = fields

            else:
                # Spesa già esistente: mantengo la chiave e la description
                desc = self.recurring_expenses_settings[expense_key].description
                fields = {
                    "description": desc,
                    "amount": widgets["amount"].get(),
                    "supplier": widgets["supplier"].get(),
                    "deductible": widgets["deductible"].get(),
                    "category": widgets["category"].get(),
                    "deductor": deductor_id if deductible == "Sì" else None,
                    "iva": widgets["iva"].get(),
                    "account": widgets["account"].get(),
                    "frequency": widgets["frequency"].get(),
                    "status": widgets["status"].get(),
                }
                new_data[expense_key] = fields

        try:
            # usa la funzione ad hoc che gestisce description scalar e value dict
            self.config_manager.update_recurring_expenses(new_data)
            ViewUtils.show_confirm_popup(
                self.recurring_expenses_window,
                title="Successo",
                message="Modifiche salvate correttamente!"
            )
        except Exception as e:
            ViewUtils.show_error_popup(
                self.recurring_expenses_window,
                title="Errore",
                message=f"Salvataggio fallito: {str(e)}"
            )

    def open_add_expense_category(self, expense_key, selected_value):
        sector_dict = dict(self.catalogo_elenchi["expenses_category"])
        if selected_value == sector_dict.get("ADD_CATEGORY"):
            self.current_expense_for_category = expense_key
            self.add_category_window = ctk.CTkToplevel(self)
            self.add_category_window.title("Aggiungi una nuova categoria di spesa")

            # Assicurati che la finestra rimanga sopra
            self.add_category_window.lift()  # Porta la finestra sopra quella principale
            self.add_category_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

            self.add_category_window.geometry("400x300")

            self.expense_category_window_Frame = ctk.CTkFrame(self.add_category_window)
            self.expense_category_window_Frame.pack(fill="both", expand=True)

            ctk.CTkLabel(self.expense_category_window_Frame, text="Aggiungi una caategoria di spesa alla lista\nsepara parole diverse solo tramite spazio").pack(padx=10, pady=(25, 0))

            self.add_category_entry = ctk.CTkEntry(self.expense_category_window_Frame)
            self.add_category_entry.pack(padx=10, pady=5, fill="x", expand=True)

            ctk.CTkButton(self.expense_category_window_Frame, text="Aggiungi una categoria", command=self.save_expense_category).pack(padx=10, pady=(15, 10))

        else: return

    def save_expense_category(self):
        new_category = self.add_category_entry.get()
        new_category_key = ControllerUtils.normalize_string_for_key(new_category)
        try:
            self.config_manager.update_list_field("expenses_category", new_category_key, new_category, "update")
        except Exception as e:
            ViewUtils.show_error_popup(self.add_category_window, "Errore", f"Impossibile aggiungere il nuovo settore: {str(e)}")
            return

        widget = self.expense_widgets[self.current_expense_for_category]["category"]
        widget.configure(values=widget._values + [new_category])  # aggiorno la lista delle opzioni
        widget.set(new_category)
        self.add_category_window.destroy()

    def add_recurring_expenses(self):
        tab_name = "Nuova Spesa"
        self.expenses_tabview.add(tab_name)
        tab = self.expenses_tabview.tab(tab_name)

        # Container scrollabile
        container = ctk.CTkScrollableFrame(tab)
        container.pack(fill="both", expand=True, padx=20, pady=10)

        # Creiamo un expense_key unico per questa nuova spesa
        expense_key = tab_name
        self.expense_widgets[expense_key] = {}

        # Prepara i valori per dropdown
        suppliers_map_list = self.supplier_controller.retrieve_suppliers_map_list()
        suppliers_opts = [s[DBSuppliersColumns.NAME.value] for s in suppliers_map_list]

        aliquote_list = [
            self.fiscal_settings.aliquota_iva.aliquota_iva_ordinaria,
            self.fiscal_settings.aliquota_iva.aliquota_iva_ridotta_1,
            self.fiscal_settings.aliquota_iva.aliquota_iva_ridotta_2,
            self.fiscal_settings.aliquota_iva.aliquota_iva_minima
        ]
        iva_opts = [str(a) for a in aliquote_list]

        accounts = self.account_controller.retrieve_accounts_map_list()
        account_opts = [a[DBAccountsColumns.NAME.value] for a in accounts]

        category_opts = [v for _, v in self.catalogo_elenchi["expenses_category"]]
        freq_opts = [f.value for f in ExpenseController.RecurringExpensesFrequencies]

        users = self.user_controller.retrieve_users_map_list()

        # Definizione dei campi, con type e options
        fields = [
            ('name', 'Nome Spesa:', 'entry', None),
            ('amount', 'Importo:', 'entry', None),
            ('supplier', 'Fornitore:', 'dropdown', suppliers_opts),
            ('category', 'Categoria:', 'dropdown', category_opts),
            ('iva', 'IVA:', 'dropdown', iva_opts),
            ('deductor', 'Deduzione a\ncarico di:', 'dropdown',
             [user[DBUsersColumns.FIRST_NAME.value] + " " + user[DBUsersColumns.LAST_NAME.value] for user in users]),
            ('account', 'Conto:', 'dropdown', account_opts),
            ('frequency', 'Frequenza:', 'dropdown', freq_opts),
            ('deductible', 'Deducibile:', 'radio', ["Sì", "No"]),
            ('status', 'Stato:', 'radio', [st.value for st in ExpenseController.RecurringExpensesStatus]),
        ]

        for field, label_text, field_type, options in fields:
            frame = ctk.CTkFrame(container)
            frame.pack(fill="x", pady=10)

            lbl = ctk.CTkLabel(frame, text=label_text, width=140, font=self.label_font)
            lbl.pack(side="left", padx=5)

            # Entry
            if field_type == 'entry':
                widget = ctk.CTkEntry(frame, font=self.entry_font)
                # vuoto di default
            # Dropdown
            elif field_type == 'dropdown':
                widget = ctk.CTkOptionMenu(
                    master=frame,
                    values=options,
                    font=self.entry_font,
                    dropdown_font=self.entry_font
                )
                widget.set(options[0] if options else "")
            # Radio
            else:  # 'radio'
                var = ctk.StringVar(value=options[0] if options else "")
                radio_frame = ctk.CTkFrame(frame)
                radio_frame.pack(side="left", fill="x", expand=True)
                for opt in options:
                    rb = ctk.CTkRadioButton(
                        radio_frame, text=opt,
                        variable=var, value=opt,
                        font=self.entry_font
                    )
                    rb.pack(side="left", padx=10)
                widget = var

            # Pack widget (entry or dropdown)
            if field_type in ('entry', 'dropdown'):
                widget.pack(fill="x", expand=True, padx=5)

            self.expense_widgets[expense_key][field] = widget


    #funzioni per la chiusura dell'esercizio contabile
    def open_fiscal_year_closer_window(self):
        """Apre una finestra per gestire la chiusura dell'anno contabile."""
        # Crea la finestra di dialogo
        self.fiscal_year_closer_window = ctk.CTkToplevel(self)
        self.fiscal_year_closer_window.title("Chiusura anno contabile")
        self.fiscal_year_closer_window.lift()
        self.fiscal_year_closer_window.grab_set()

        # ---------- helper function -----------
        def determine_current_exercise_year() -> int:
            """
            Determina l'anno dell'esercizio corrente in base alla data odierna.
            Se siamo a dicembre: anno corrente
            Se siamo a gennaio o febbraio: anno precedente
            Altrimenti: anno corrente
            """
            now = datetime.now()
            current_month = now.month

            if current_month == 12:  # Dicembre
                return now.year
            elif current_month in [1, 2]:  # Gennaio o Febbraio
                return now.year - 1
            else:  # Marzo-Novembre
                # Per sicurezza usiamo l'anno precedente se siamo nei primi mesi
                # ma non gennaio/febbraio (questa logica può essere modificata)
                return now.year

        # ---------- Frame principale ----------
        self.current_exercise_year = determine_current_exercise_year()
        main_frame = ctk.CTkFrame(self.fiscal_year_closer_window, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=12, pady=12)

        title_label = ctk.CTkLabel(
            main_frame,
            text=f"Stai per eseguire la chiusura dell'anno fiscale {self.current_exercise_year}.",
            anchor="w",
            font=("Segoe UI", 18, "bold")
        )
        title_label.pack(fill="x", pady=(0, 10), padx=5)

        description_label_1 = ctk.CTkLabel(
            main_frame,
            text="Quest'operazione comporta:\n\n"
                 "- esportazione dei dati aggregati annuali su file .csv\n"
                 "- esportazione dei dati aggregati mensili su file .csv\n"
                 "- salvataggio e aggiornamento del saldo dei conti al 31/12\n"
                 "- esportazione del'elenco dei movimenti bancari su file .csv\n",
            justify="left",
            anchor="w",
            font=("Segoe UI", 15)
        )
        description_label_1.pack(fill="x", pady=(15, 15), padx=5)

        description_label_2 = ctk.CTkLabel(
            main_frame,
            text="A PARTIRE DAL 01/12 ed indipendentemente dall'avvenuta chiusura contabile dell'anno:\n\n"
                 "- non sarà più possibile modificare i campi di oggetti relativi all'anno contabile passato\n"
                 "- l'interfaccia mostrerà solo i dati relativi al nuovo esercizio contabile\n"
                 "- il database in backend rimarrà sempre lo stesso, contenente tutti i campi inseriti, \n di tutti gli anni contabili\n"
                 "- sarà possibile visualizzare i vecchi esercizi contabili tramite un software \n di time machine per la sola lettura/consultazione\n"
                 "- i dati aggregati esportati saranno utilizzati per il plotting dell'andamento nella tab apposita\n"
                 "- NON SPOSTARE I FILE DEI DATI ESPORTATI DALLA LORO CARTELLA\n",
            justify="left",
            anchor="w",
            font=("Segoe UI", 15)
        )
        description_label_2.pack(fill="x", pady=(15, 10), padx=5)

        ctk.CTkLabel(main_frame, text="Desideri continuare?", font=("Segoe UI", 16, "bold")).pack(fill="x", pady=(15, 15), padx=5)
        ctk.CTkButton(main_frame, text="Non ora", command=lambda: self.fiscal_year_closer_window.destroy(), fg_color="gray").pack(
            fill="x", pady=(15, 20), padx=55, side="left")
        ctk.CTkButton(main_frame, text="Avanti", command=self.close_fiscal_year).pack(fill="x", pady=(15, 20), padx=(0, 55), side="right")


    def close_fiscal_year(self):
        book_closer = BookCloser(self, self.app_context)
        book_closer.set_current_exercise_year(self.current_exercise_year)

        # Lista delle operazioni con descrizioni
        operations = [
            ("Esportazione movimenti bancari", book_closer.export_accounts_movements),
            ("Aggiornamento dati finanziari storici", book_closer.update_historical_financial_data),
            ("Esportazione dati annuali aggregati", book_closer.export_annual_data),
            ("Esportazione dati mensili aggregati", book_closer.export_monthly_data),
            ("Esportazione dati IVA aggregati", book_closer.export_trimestral_iva_data),
            ("Esportazione dati TASSE aggregati", book_closer.export_tax_data),
            ("Impoprtazione saldi bancari iniziali", book_closer.import_initial_balances)
        ]

        results = []

        # Esegui ogni operazione e cattura il risultato
        for description, operation in operations:
            try:
                # Esegui l'operazione
                result = operation()

                # Considera l'operazione riuscita se:
                # 1. Non ci sono state eccezioni
                # 2. Per export_accounts_movements: deve restituire un percorso (non None)
                if description == "Esportazione movimenti bancari" and result is None:
                    results.append((description, False, "Restituito None"))
                else:
                    results.append((description, True, "Successo"))

            except Exception as e:
                results.append((description, False, str(e)))

        # Calcola statistiche
        success_count = sum(1 for _, success, _ in results if success)
        total_count = len(results)

        # Mostra popup riepilogativo finale
        if success_count == total_count:
            # Crea messaggio dettagliato con risultati
            details = "\n".join([
                f"✓ {desc}" if success else f"✗ {desc}: {msg}"
                for desc, success, msg in results
            ])

            ViewUtils.show_confirm_popup(
                self.fiscal_year_closer_window,
                f"Chiusura esercizio completata ({success_count}/{total_count})",
                f"Operazioni completate:\n\n{details}"
            )
        else:
            # Crea messaggio dettagliato con risultati
            details = "\n".join([
                f"✓ {desc}" if success else f"✗ {desc}: {msg}"
                for desc, success, msg in results
            ])

            ViewUtils.show_error_popup(
                self.fiscal_year_closer_window,
                f"Chiusura esercizio parziale ({success_count}/{total_count})",
                f"Operazioni completate:\n\n{details}"
            )

        # Stampa log dettagliato nella console
        print("\n" + "=" * 60)
        print("RIEPILOGO CHIUSURA ESERCIZIO")
        print("=" * 60)
        for desc, success, msg in results:
            status = "✓ SUCCESSO" if success else "✗ FALLITO"
            print(f"{status}: {desc}")
            if not success and msg:
                print(f"  Motivo: {msg}")
        print("=" * 60)
        print(f"Operazioni completate con successo: {success_count}/{total_count}")

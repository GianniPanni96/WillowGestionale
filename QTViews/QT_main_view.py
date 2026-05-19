from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QStackedWidget,
    QTabWidget,
    QToolButton,
    QWidget,
)

from Utils.View_utils import ViewUtils
from Model import DBUsersColumns

from QTViews.Details.QT_account_detail_view import QTAccountDetailViewH
from QTViews.Details.QT_client_detail_view import QTClientDetailViewH
from QTViews.Details.QT_invoice_detail_view import QTInvoiceDetailViewH
from QTViews.Details.QT_expense_detail_view import QTExpenseDetailViewH
from QTViews.Details.QT_payment_detail_view import QTPaymentDetailViewH
from QTViews.Details.QT_production_detail_view import QTProductionDetailViewH
from QTViews.Details.QT_refund_detail_view import QTRefundDetailViewH
from QTViews.Details.QT_salary_detail_view import QTSalaryDetailViewH
from QTViews.Details.QT_supplier_detail_view import QTSupplierDetailViewH
from QTViews.Details.QT_user_detail_view import QTUserDetailViewH
from QTViews.QT_accounts_view import QTAccountsViewH
from QTViews.ListViews.QT_clients_view import QTClientsViewH
from QTViews.QT_iva_view import QTIvaViewH
from QTViews.QT_plot_view import QTPlotViewH
from QTViews.QT_report_view import QTReportViewH
from QTViews.QT_taxes_view import QTTaxesViewH
from QTViews.ListViews.QT_expenses_view import QTExpensesViewH
from QTViews.ListViews.QT_invoices_view import QTInvoicesViewH
from QTViews.ListViews.QT_payments_view import QTPaymentsViewH
from QTViews.ListViews.QT_productions_view import QTProductionsViewH
from QTViews.ListViews.QT_refunds_view import QTRefundsViewH
from QTViews.ListViews.QT_salaries_view import QTSalariesViewH
from QTViews.ListViews.QT_suppliers_view import QTSuppliersViewH
from QTViews.ListViews.QT_users_view import QTUsersViewH
from QTViews.MenuWindows.QT_backup_runner import QTBackupRunner
from QTViews.MenuWindows.QT_backup_settings_dialog import QTBackupSettingsDialog
from QTViews.MenuWindows.QT_collective_name_dialog import QTCollectiveNameDialog
from QTViews.MenuWindows.QT_fiscal_settings_dialog import QTFiscalSettingsDialog
from QTViews.MenuWindows.QT_fiscal_year_closer_dialog import QTFiscalYearCloserDialog
from QTViews.MenuWindows.QT_warnings_settings_dialog import QTWarningsSettingsDialog
from QTViews.MenuWindows.QT_load_backup_dialog import QTLoadBackupDialog
from QTViews.LoginViews.QT_login_dialog import QTLoginDialog
from QTViews.MenuWindows.QT_recurring_expenses_dialog import QTRecurringExpensesDialog

if TYPE_CHECKING:
    from App_context import AppContext


class QTMainWindow(QMainWindow):
    """
    Main window QT.

    Replica l'architettura della MainWindow customtkinter:
    - una QMenuBar in alto con i menu "Gestione …";
    - un QTabWidget centrale con tutte le tab dell'applicazione;
    - una barra superiore con menu a sinistra e Login / icona utente /
      refresh a destra.

    Ad oggi le tab "Fatture" e "Clienti" sono funzionanti; le altre sono
    presenti per rispecchiare la struttura della view legacy ma non sono
    interagibili finché le rispettive view non saranno portate su Qt.

    Le voci dei menu in alto sono invece pienamente operative: ognuna apre
    la propria finestra dedicata (in QTViews/MenuWindows/), che eredita
    la logica della MainWindow legacy ma è ora estratta in classi separate.

    Ogni tab gestisce internamente il flusso "elenco / dettaglio" con uno
    stack dedicato, cosi' la barra delle tab resta sempre visibile anche
    quando l'utente apre una vista di dettaglio.
    """

    TAB_INVOICES = "Fatture"
    TAB_CLIENTS = "Clienti"
    TAB_SUPPLIERS = "Fornitori"
    TAB_PRODUCTIONS = "Produzioni"
    TAB_PAYMENTS = "Pagamenti"
    TAB_REFUNDS = "Rimborsi"
    TAB_EXPENSES = "Spese"
    TAB_SALARIES = "Salario"
    TAB_USERS = "Utenti"
    TAB_ACCOUNTS = "Conti"
    TAB_IVA = "Iva"
    TAB_TAXES = "Tasse"
    TAB_REPORT_PREFIX = "Report"
    TAB_PLOTS = "Plots"

    @classmethod
    def _tab_names(cls):
        # L'ordine rispecchia quello della MainWindow legacy.
        return [
            cls.TAB_USERS,
            cls.TAB_CLIENTS,
            cls.TAB_SUPPLIERS,
            cls.TAB_PRODUCTIONS,
            cls.TAB_ACCOUNTS,
            cls.TAB_INVOICES,
            cls.TAB_PAYMENTS,
            cls.TAB_REFUNDS,
            cls.TAB_EXPENSES,
            cls.TAB_IVA,
            cls.TAB_SALARIES,
            cls.TAB_TAXES,
            f"Report {datetime.now().year}",
            "Plots",
        ]

    def __init__(self, app_context: "AppContext", initial_invoice_id=None):
        super().__init__()

        self.app_context = app_context

        self.setWindowTitle("Gestionale Willow")
        self.resize(1400, 800)
        self._set_window_icon()

        self._build_menu_bar()

        self.tabview = QTabWidget()
        self.tabview.setObjectName("MainTabView")
        self.tabview.setContentsMargins(0, 12, 0, 0)
        self.tabview.setStyleSheet("""
            #MainTabView::pane {
                border-top: 1px solid palette(mid);
            }

            #MainTabView QTabBar::tab {
                min-width: 60px;
                min-height: 24px;
                padding: 8px 14px;
                font-size: 11pt;
            }

            #MainTabView QTabBar::tab:selected {
                background-color: palette(highlight);
                color: palette(highlighted-text);
            }

            #MainTabView QTabBar::tab:!selected {
                background-color: palette(button);
                color: palette(button-text);
            }
        """)
        self.invoices_view = None
        self.clients_view = None
        self.suppliers_view = None
        self.productions_view = None
        self.payments_view = None
        self.refunds_view = None
        self.expenses_view = None
        self.salaries_view = None
        self.users_view = None
        self.accounts_view = None
        self.iva_view = None
        self.taxes_view = None
        self.report_view = None
        self.plots_view = None
        self.invoices_page = None
        self.clients_page = None
        self.suppliers_page = None
        self.productions_page = None
        self.payments_page = None
        self.refunds_page = None
        self.expenses_page = None
        self.salaries_page = None
        self.users_page = None
        self.accounts_page = None
        self.iva_page = None
        self.taxes_page = None
        self.report_page = None
        self.plots_page = None
        self.invoice_detail_view = None
        self.client_detail_view = None
        self.supplier_detail_view = None
        self.production_detail_view = None
        self.payment_detail_view = None
        self.refund_detail_view = None
        self.expense_detail_view = None
        self.salary_detail_view = None
        self.user_detail_view = None
        self.account_detail_view = None
        self.login_status = False
        self.logged_user_id = -1
        self.is_admin = False
        self.persist_session_enabled: bool = False
        self.persist_session_minutes: int = 30
        self.user_icon_label = None
        self.backup_runner = QTBackupRunner(app_context=app_context, parent=self)

        self._build_tabs(initial_invoice_id)
        self._build_menu_corner()
        self.setCentralWidget(self.tabview)

        # Cablaggio della navigazione cross-domain: le card / pulsanti
        # "linked item" nelle detail view pubblicano sull'event bus la
        # richiesta di aprire un dettaglio in un altro dominio. Senza
        # questo subscribe i click rimangono inerti.
        self._subscribe_cross_domain_navigation()

        if self.invoices_page is not None:
            self.tabview.setCurrentWidget(self.invoices_page)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _set_window_icon(self):
        try:
            images_path = Path(self.app_context.images_path)
            for candidate in ("WillowLogo.ico", "user.png"):
                path = images_path / candidate
                if path.exists():
                    self.setWindowIcon(QIcon(str(path)))
                    return
        except Exception as exc:
            print(f"Errore nel caricamento dell'icona: {exc}")

    def _build_menu_bar(self):
        top_bar = QWidget(self)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(0, 0, 8, 0)
        top_layout.setSpacing(8)

        menubar = QMenuBar(top_bar)
        menubar.setStyleSheet(
            """
            QMenuBar {
                padding-top: 10px;
            }
            """
        )
        top_layout.addWidget(menubar, stretch=1)

        self.menu_actions_widget = QWidget(top_bar)
        self.menu_actions_layout = QHBoxLayout(self.menu_actions_widget)
        self.menu_actions_layout.setContentsMargins(4, 2, 4, 2)
        self.menu_actions_layout.setSpacing(8)
        top_layout.addWidget(
            self.menu_actions_widget, alignment=Qt.AlignRight | Qt.AlignVCenter
        )
        self.setMenuWidget(top_bar)

        backup = menubar.addMenu("Backup")
        backup.addAction("Impostazioni backup").triggered.connect(self._open_backup_settings)
        backup.addAction("Esegui un backup manuale del Database").triggered.connect(
            self._execute_db_backup
        )
        backup.addAction("Esegui un backup manuale dei libri contabili").triggered.connect(
            self._execute_books_backup
        )
        backup.addAction("Carica un backup del Database").triggered.connect(self._open_load_backup)

        fiscal = menubar.addMenu("Dati Fiscali")
        fiscal.addAction("Modifica dati fiscali").triggered.connect(self._open_fiscal_settings)

        recurring = menubar.addMenu("Spese Ricorrenti")
        recurring.addAction("Modifica Spese Ricorrenti").triggered.connect(
            self._open_recurring_expenses
        )

        fiscal_year = menubar.addMenu("Esercizio")
        fiscal_year.addAction(
            f"Chiusura Esercizio {datetime.now().year}"
        ).triggered.connect(self._open_fiscal_year_closer)

        warnings_menu = menubar.addMenu("GUI")
        warnings_menu.addAction("Visibilità warnings").triggered.connect(
            self._open_warnings_settings
        )
        warnings_menu.addAction("Nome del collettivo").triggered.connect(
            self._open_collective_name_settings
        )

        self.admin_menu = menubar.addMenu("ADMIN")
        self.admin_menu.addAction("Log Accessi").triggered.connect(self._open_admin_audit_log)

    def _build_tab_page(self, list_view):
        page = QStackedWidget()
        page.setContentsMargins(0, 0, 0, 0)
        page.addWidget(list_view)
        return page

    def _build_tabs(self, initial_invoice_id):
        for name in self._tab_names():
            if name == self.TAB_INVOICES:
                self.invoices_view = QTInvoicesViewH(
                    app_context=self.app_context,
                    initial_invoice_id=initial_invoice_id,
                    on_open_detail=self._open_invoice_detail,
                    parent=self,
                )
                self.invoices_page = self._build_tab_page(self.invoices_view)
                self.tabview.addTab(self.invoices_page, name)
            elif name == self.TAB_CLIENTS:
                self.clients_view = QTClientsViewH(
                    app_context=self.app_context,
                    initial_client_id=None,
                    on_open_detail=self._open_client_detail,
                    parent=self,
                )
                self.clients_page = self._build_tab_page(self.clients_view)
                self.tabview.addTab(self.clients_page, name)
            elif name == self.TAB_SUPPLIERS:
                self.suppliers_view = QTSuppliersViewH(
                    app_context=self.app_context,
                    initial_supplier_id=None,
                    on_open_detail=self._open_supplier_detail,
                    parent=self,
                )
                self.suppliers_page = self._build_tab_page(self.suppliers_view)
                self.tabview.addTab(self.suppliers_page, name)
            elif name == self.TAB_PRODUCTIONS:
                self.productions_view = QTProductionsViewH(
                    app_context=self.app_context,
                    initial_production_id=None,
                    on_open_detail=self._open_production_detail,
                    parent=self,
                )
                self.productions_page = self._build_tab_page(self.productions_view)
                self.tabview.addTab(self.productions_page, name)
            elif name == self.TAB_PAYMENTS:
                self.payments_view = QTPaymentsViewH(
                    app_context=self.app_context,
                    initial_payment_id=None,
                    on_open_detail=self._open_payment_detail,
                    parent=self,
                )
                self.payments_page = self._build_tab_page(self.payments_view)
                self.tabview.addTab(self.payments_page, name)
            elif name == self.TAB_REFUNDS:
                self.refunds_view = QTRefundsViewH(
                    app_context=self.app_context,
                    initial_refund_id=None,
                    on_open_detail=self._open_refund_detail,
                    parent=self,
                )
                self.refunds_page = self._build_tab_page(self.refunds_view)
                self.tabview.addTab(self.refunds_page, name)
            elif name == self.TAB_EXPENSES:
                self.expenses_view = QTExpensesViewH(
                    app_context=self.app_context,
                    initial_expense_id=None,
                    on_open_detail=self._open_expense_detail,
                    parent=self,
                )
                self.expenses_page = self._build_tab_page(self.expenses_view)
                self.tabview.addTab(self.expenses_page, name)
            elif name == self.TAB_SALARIES:
                self.salaries_view = QTSalariesViewH(
                    app_context=self.app_context,
                    initial_salary_id=None,
                    on_open_detail=self._open_salary_detail,
                    parent=self,
                )
                self.salaries_page = self._build_tab_page(self.salaries_view)
                self.tabview.addTab(self.salaries_page, name)
            elif name == self.TAB_USERS:
                self.users_view = QTUsersViewH(
                    app_context=self.app_context,
                    on_open_detail=self._open_user_detail,
                    parent=self,
                )
                self.users_page = self._build_tab_page(self.users_view)
                self.tabview.addTab(self.users_page, name)
            elif name == self.TAB_ACCOUNTS:
                self.accounts_view = QTAccountsViewH(
                    app_context=self.app_context,
                    on_open_detail=self._open_account_detail,
                    parent=self,
                )
                self.accounts_page = self._build_tab_page(self.accounts_view)
                self.tabview.addTab(self.accounts_page, name)
            elif name == self.TAB_IVA:
                self.iva_view = QTIvaViewH(
                    app_context=self.app_context,
                    parent=self,
                )
                self.iva_page = self._build_tab_page(self.iva_view)
                self.tabview.addTab(self.iva_page, name)
            elif name == self.TAB_TAXES:
                self.taxes_view = QTTaxesViewH(
                    app_context=self.app_context,
                    parent=self,
                )
                self.taxes_page = self._build_tab_page(self.taxes_view)
                self.tabview.addTab(self.taxes_page, name)
            elif name.startswith(self.TAB_REPORT_PREFIX):
                self.report_view = QTReportViewH(
                    app_context=self.app_context,
                    parent=self,
                )
                self.report_page = self._build_tab_page(self.report_view)
                self.tabview.addTab(self.report_page, name)
            elif name == self.TAB_PLOTS:
                self.plots_view = QTPlotViewH(
                    app_context=self.app_context,
                    parent=self,
                )
                self.plots_page = self._build_tab_page(self.plots_view)
                self.tabview.addTab(self.plots_page, name)
            else:
                placeholder = QLabel(f"{name}\nNon ancora portata su Qt.")
                placeholder.setAlignment(Qt.AlignCenter)
                placeholder.setStyleSheet("color: palette(mid); font-size: 14pt;")
                idx = self.tabview.addTab(placeholder, name)
                self.tabview.setTabEnabled(idx, False)

    USER_ICON_SIZE = 40

    def _build_menu_corner(self):
        layout = self.menu_actions_layout

        # Bottone-icona dell'utente: trigger del menu utente (login,
        # logout, switch account). Stile "tool button" arrotondato con
        # hover/pressed evidenti per chiarire l'affordance cliccabile.
        self.user_icon_button = QToolButton()
        self.user_icon_button.setPopupMode(QToolButton.InstantPopup)
        self.user_icon_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.user_icon_button.setIconSize(QSize(self.USER_ICON_SIZE, self.USER_ICON_SIZE))
        self.user_icon_button.setFixedSize(self.USER_ICON_SIZE + 12, self.USER_ICON_SIZE + 12)
        self.user_icon_button.setCursor(Qt.PointingHandCursor)
        self.user_icon_button.setToolTip("Menu utente")
        self.user_icon_button.setAutoRaise(False)
        self.user_icon_button.setStyleSheet(
            f"""
            QToolButton {{
                border: 1px solid palette(mid);
                border-radius: {(self.USER_ICON_SIZE + 12) // 2}px;
                padding: 2px;
                background-color: palette(window);
            }}
            QToolButton:hover {{
                border: 1px solid palette(highlight);
                background-color: palette(alternate-base);
            }}
            QToolButton:pressed {{
                background-color: palette(highlight);
            }}
            QToolButton::menu-indicator {{ image: none; width: 0px; }}
            """
        )

        self.user_menu = QMenu(self.user_icon_button)
        self.login_action = QAction("Esegui il login", self)
        self.login_action.triggered.connect(self._manage_login)
        self.user_menu.addAction(self.login_action)
        self.switch_account_action = QAction("Cambia utente", self)
        self.switch_account_action.triggered.connect(self._switch_account)
        self.switch_account_action.setEnabled(False)
        self.user_menu.addAction(self.switch_account_action)
        self.user_menu.addSeparator()
        self.admin_login_action = QAction("Login come amministratore", self)
        self.admin_login_action.triggered.connect(self._login_as_admin)
        self.user_menu.addAction(self.admin_login_action)
        self.user_icon_button.setMenu(self.user_menu)

        # Per retrocompatibilita' con _set_user_icon_from_path /
        # _refresh_logged_user_icon manteniamo l'attributo come riferimento
        # al QToolButton: il setter capisce di che widget si tratta.
        self.user_icon_label = self.user_icon_button

        layout.addWidget(self.user_icon_button)
        self._set_user_icon_from_path(self._default_user_icon_path())

    # ------------------------------------------------------------------
    # Azioni
    # ------------------------------------------------------------------

    def _refresh_current_tab(self):
        widget = self.tabview.currentWidget()
        if widget is self.invoices_page and self.invoices_view is not None:
            # Ricarica la lista fatture rispettando la time window selezionata.
            self.invoices_view._on_window_changed()
        elif widget is self.clients_page and self.clients_view is not None:
            self.clients_view._on_window_changed()
        elif widget is self.suppliers_page and self.suppliers_view is not None:
            self.suppliers_view._on_window_changed()
        elif widget is self.productions_page and self.productions_view is not None:
            self.productions_view._on_window_changed()
        elif widget is self.payments_page and self.payments_view is not None:
            self.payments_view._on_window_changed()
        elif widget is self.refunds_page and self.refunds_view is not None:
            self.refunds_view._on_window_changed()
        elif widget is self.expenses_page and self.expenses_view is not None:
            self.expenses_view._on_window_changed()
        elif widget is self.salaries_page and self.salaries_view is not None:
            self.salaries_view._on_window_changed()
        elif widget is self.users_page and self.users_view is not None:
            self.users_view.refresh()
        elif widget is self.accounts_page and self.accounts_view is not None:
            self.accounts_view.refresh()
        elif widget is self.iva_page and self.iva_view is not None:
            self.iva_view.refresh()
        elif widget is self.taxes_page and self.taxes_view is not None:
            self.taxes_view.refresh()
        elif widget is self.report_page and self.report_view is not None:
            self.report_view.refresh()
        elif widget is self.plots_page and self.plots_view is not None:
            self.plots_view.refresh()
        self._refresh_logged_user_icon()

    def _default_user_icon_path(self):
        try:
            path = Path(self.app_context.images_path) / "user.png"
            if path.exists():
                return str(path)
        except Exception:
            pass
        return ""

    def _admin_icon_path(self) -> str:
        try:
            path = Path(self.app_context.images_path) / "ADMIN.png"
            if path.exists():
                return str(path)
        except Exception:
            pass
        return ""

    def _set_user_icon_from_path(self, image_path):
        if getattr(self, "user_icon_button", None) is None:
            return

        pix = QPixmap(str(image_path)) if image_path else QPixmap()
        if pix.isNull():
            self.user_icon_button.setIcon(QIcon())
            return

        size = self.USER_ICON_SIZE
        # Scale to cover the square, then crop to center
        scaled = pix.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        if scaled.width() != size or scaled.height() != size:
            x = (scaled.width() - size) // 2
            y = (scaled.height() - size) // 2
            scaled = scaled.copy(x, y, size, size)

        # Paint into a circular mask
        circular = QPixmap(size, size)
        circular.fill(Qt.transparent)
        painter = QPainter(circular)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, scaled)
        painter.end()

        self.user_icon_button.setIcon(QIcon(circular))

    def _refresh_logged_user_icon(self):
        if self.login_status and self.is_admin:
            admin_icon = self._admin_icon_path()
            if admin_icon:
                self._set_user_icon_from_path(admin_icon)
                return

        image_path = self._default_user_icon_path()
        if self.login_status and self.logged_user_id != -1:
            try:
                user = self.app_context.user_query_service.retrieve_user_map_by_id(
                    self.logged_user_id
                )
                photo_path = user.get(DBUsersColumns.PHOTO_PATH.value, "") if user else ""
                if photo_path and Path(photo_path).exists():
                    image_path = photo_path
            except Exception:
                pass
        self._set_user_icon_from_path(image_path)

    # ------------------------------------------------------------------
    # Navigazione cross-domain via event bus
    # ------------------------------------------------------------------

    def _subscribe_cross_domain_navigation(self):
        """Collega le chiavi ``SHOW_*_DETAIL`` dell'event bus alle azioni
        di apertura del dettaglio corrispondente.

        Le detail view pubblicano questi eventi quando l'utente clicca
        su una card / pulsante che rappresenta un item di un altro
        dominio (es. dal cliente → fattura, dalla fattura → pagamento).
        La main view e' l'unico punto in cui si conoscono i tab e gli
        handler ``_open_*_detail``, quindi e' qui che si fa il routing.
        """
        bus = self.app_context.event_bus
        keys = ViewUtils.EventBusKeys
        # Wrap in lambdas che ignorano payload non int (None / dict) per
        # robustezza: gli handler ``_open_*_detail`` si aspettano un id.
        bus.subscribe(keys.SHOW_INVOICE_DETAIL.value, self._on_show_invoice_detail)
        bus.subscribe(keys.SHOW_SALARY_DETAIL.value, self._on_show_salary_detail)
        bus.subscribe(keys.SHOW_PRODUCTION_DETAIL.value, self._on_show_production_detail)
        bus.subscribe(keys.SHOW_REFUND_DETAIL.value, self._on_show_refund_detail)
        bus.subscribe(keys.SHOW_EXPENSE_DETAIL.value, self._on_show_expense_detail)
        bus.subscribe(keys.SHOW_PAYMENT_DETAIL.value, self._on_show_payment_detail)
        bus.subscribe(keys.SHOW_ACCOUNT_TAB.value, self._on_show_account_detail)

    def _on_show_invoice_detail(self, invoice_id):
        if invoice_id is None:
            return
        self._open_invoice_detail(invoice_id)

    def _on_show_salary_detail(self, salary_id):
        if salary_id is None:
            return
        self._open_salary_detail(salary_id)

    def _on_show_production_detail(self, production_id):
        if production_id is None:
            return
        self._open_production_detail(production_id)

    def _on_show_refund_detail(self, refund_id):
        if refund_id is None:
            return
        self._open_refund_detail(refund_id)

    def _on_show_expense_detail(self, expense_id):
        if expense_id is None:
            return
        self._open_expense_detail(expense_id)

    def _on_show_payment_detail(self, payment_id):
        if payment_id is None:
            return
        self._open_payment_detail(payment_id)

    def _on_show_account_detail(self, account_id):
        if account_id is None:
            return
        self._open_account_detail(account_id)

    def _show_detail_view(self, page_stack, detail_attr, detail_view):
        old_detail = getattr(self, detail_attr)
        if old_detail is not None:
            page_stack.removeWidget(old_detail)
            old_detail.deleteLater()

        setattr(self, detail_attr, detail_view)
        page_stack.addWidget(detail_view)
        page_stack.setCurrentWidget(detail_view)
        self.tabview.setCurrentWidget(page_stack)

    def _back_to_list_view(self, page_stack, list_view, detail_attr):
        if page_stack is not None and list_view is not None:
            page_stack.setCurrentWidget(list_view)
            self.tabview.setCurrentWidget(page_stack)

        detail_view = getattr(self, detail_attr)
        if detail_view is not None:
            page_stack.removeWidget(detail_view)
            detail_view.deleteLater()
            setattr(self, detail_attr, None)

    def _open_invoice_detail(self, invoice_id):
        detail_view = QTInvoiceDetailViewH(
            app_context=self.app_context,
            invoice_id=invoice_id,
            on_back=self._back_to_invoices_list,
            parent=self,
        )
        self._show_detail_view(self.invoices_page, "invoice_detail_view", detail_view)

    def _open_client_detail(self, client_id):
        detail_view = QTClientDetailViewH(
            app_context=self.app_context,
            client_id=client_id,
            on_back=self._back_to_clients_list,
            parent=self,
        )
        self._show_detail_view(self.clients_page, "client_detail_view", detail_view)

    def _open_supplier_detail(self, supplier_id):
        detail_view = QTSupplierDetailViewH(
            app_context=self.app_context,
            supplier_id=supplier_id,
            on_back=self._back_to_suppliers_list,
            parent=self,
        )
        self._show_detail_view(self.suppliers_page, "supplier_detail_view", detail_view)

    def _open_production_detail(self, production_id):
        detail_view = QTProductionDetailViewH(
            app_context=self.app_context,
            production_id=production_id,
            on_back=self._back_to_productions_list,
            parent=self,
        )
        self._show_detail_view(self.productions_page, "production_detail_view", detail_view)

    def _open_payment_detail(self, payment_id):
        detail_view = QTPaymentDetailViewH(
            app_context=self.app_context,
            payment_id=payment_id,
            on_back=self._back_to_payments_list,
            parent=self,
        )
        self._show_detail_view(self.payments_page, "payment_detail_view", detail_view)

    def _open_refund_detail(self, refund_id):
        detail_view = QTRefundDetailViewH(
            app_context=self.app_context,
            refund_id=refund_id,
            on_back=self._back_to_refunds_list,
            parent=self,
        )
        self._show_detail_view(self.refunds_page, "refund_detail_view", detail_view)

    def _open_expense_detail(self, expense_id):
        detail_view = QTExpenseDetailViewH(
            app_context=self.app_context,
            expense_id=expense_id,
            on_back=self._back_to_expenses_list,
            parent=self,
        )
        self._show_detail_view(self.expenses_page, "expense_detail_view", detail_view)

    def _open_salary_detail(self, salary_id):
        detail_view = QTSalaryDetailViewH(
            app_context=self.app_context,
            salary_id=salary_id,
            on_back=self._back_to_salaries_list,
            parent=self,
        )
        self._show_detail_view(self.salaries_page, "salary_detail_view", detail_view)

    def _open_user_detail(self, user_id):
        detail_view = QTUserDetailViewH(
            app_context=self.app_context,
            user_id=user_id,
            on_back=self._back_to_users_list,
            parent=self,
        )
        self._show_detail_view(self.users_page, "user_detail_view", detail_view)

    def _open_account_detail(self, account_id):
        detail_view = QTAccountDetailViewH(
            app_context=self.app_context,
            account_id=account_id,
            on_back=self._back_to_accounts_list,
            parent=self,
        )
        self._show_detail_view(self.accounts_page, "account_detail_view", detail_view)

    def _back_to_invoices_list(self):
        self._back_to_list_view(
            self.invoices_page, self.invoices_view, "invoice_detail_view"
        )

    def _back_to_clients_list(self):
        self._back_to_list_view(
            self.clients_page, self.clients_view, "client_detail_view"
        )

    def _back_to_suppliers_list(self):
        self._back_to_list_view(
            self.suppliers_page, self.suppliers_view, "supplier_detail_view"
        )

    def _back_to_productions_list(self):
        self._back_to_list_view(
            self.productions_page, self.productions_view, "production_detail_view"
        )

    def _back_to_payments_list(self):
        self._back_to_list_view(
            self.payments_page, self.payments_view, "payment_detail_view"
        )

    def _back_to_refunds_list(self):
        self._back_to_list_view(
            self.refunds_page, self.refunds_view, "refund_detail_view"
        )

    def _back_to_expenses_list(self):
        self._back_to_list_view(
            self.expenses_page, self.expenses_view, "expense_detail_view"
        )

    def _back_to_salaries_list(self):
        self._back_to_list_view(
            self.salaries_page, self.salaries_view, "salary_detail_view"
        )

    def _back_to_users_list(self):
        self._back_to_list_view(
            self.users_page, self.users_view, "user_detail_view"
        )
        if self.users_view is not None:
            # Il detail può aver modificato/eliminato l'utente: ricarica
            # le card per riflettere lo stato corrente.
            self.users_view.refresh()
        self._refresh_logged_user_icon()

    def _back_to_accounts_list(self):
        self._back_to_list_view(
            self.accounts_page, self.accounts_view, "account_detail_view"
        )
        if self.accounts_view is not None:
            # Il detail può aver modificato/eliminato il conto: ricarica
            # le card per riflettere lo stato corrente.
            self.accounts_view.refresh()

    # ------------------------------------------------------------------
    # Menu handlers — istanziano la finestra dedicata
    # ------------------------------------------------------------------

    def _open_backup_settings(self):
        QTBackupSettingsDialog(app_context=self.app_context, parent=self).exec()

    def _execute_db_backup(self):
        self.backup_runner.run_db_backup()

    def _execute_books_backup(self):
        self.backup_runner.run_books_backup()

    def _open_load_backup(self):
        QTLoadBackupDialog(app_context=self.app_context, parent=self).exec()

    def _open_fiscal_settings(self):
        QTFiscalSettingsDialog(app_context=self.app_context, parent=self).exec()

    def _open_recurring_expenses(self):
        QTRecurringExpensesDialog(app_context=self.app_context, parent=self).exec()

    def _open_fiscal_year_closer(self):
        if not QTFiscalYearCloserDialog.is_closer_available_now():
            QMessageBox.warning(
                self,
                "",
                "Impossibile eseguire la chiusura del corrente esercizio tra marzo e novembre",
            )
            return
        QTFiscalYearCloserDialog(app_context=self.app_context, parent=self).exec()

    def _open_warnings_settings(self):
        dialog = QTWarningsSettingsDialog(app_context=self.app_context, parent=self)
        if dialog.exec() == QTWarningsSettingsDialog.Accepted:
            # Ricarica la tab corrente per riflettere le nuove regole di
            # visibilita' (in genere il refresh manuale non e' necessario,
            # ma evitiamo all'utente di doverlo fare a mano).
            self._refresh_current_tab()

    def _open_collective_name_settings(self):
        dialog = QTCollectiveNameDialog(app_context=self.app_context, parent=self)
        if dialog.exec() == QTCollectiveNameDialog.Accepted:
            # Forza il refresh della tab corrente per propagare subito il
            # nuovo nome alle label che lo leggono al build.
            self._refresh_current_tab()

    def _switch_account(self):
        """Logout della sessione corrente + apertura login dialog utente.
        Se l'utente annulla la nuova login resta in stato "non loggato"."""
        if not self.login_status:
            return
        self._do_logout(publish=True)

        dialog = QTLoginDialog(app_context=self.app_context, parent=self)
        dialog.exec()
        if dialog.success:
            self.login_status = True
            self.logged_user_id = dialog.user_id
            self.is_admin = False
            self._record_persist_prefs(dialog)
            self._toggle_login_widgets()
            self.app_context.event_bus.publish(
                ViewUtils.EventBusKeys.LOGIN_STATUS_CHANGED.value,
                {"login_status": True, "logged_user_id": dialog.user_id, "is_admin": False},
            )
            self._refresh_current_tab()

    def _open_admin_audit_log(self):
        from QTViews.MenuWindows.QT_admin_audit_log_dialog import QTAdminAuditLogDialog
        dialog = QTAdminAuditLogDialog(app_context=self.app_context, parent=self)
        dialog.exec()

    def _login_as_admin(self):
        """Voce di menu "Login come amministratore": chiude eventuale
        sessione corrente e apre il dialog di login admin dedicato."""
        from QTViews.LoginViews.QT_admin_login_dialog import QTAdminLoginDialog

        if self.login_status:
            self._do_logout(publish=True)

        dialog = QTAdminLoginDialog(app_context=self.app_context, parent=self)
        dialog.exec()
        if dialog.success:
            self.login_status = True
            self.logged_user_id = -1
            self.is_admin = True
            self._record_persist_prefs(dialog)
            self._toggle_login_widgets()
            self.app_context.event_bus.publish(
                ViewUtils.EventBusKeys.LOGIN_STATUS_CHANGED.value,
                {"login_status": True, "logged_user_id": -1, "is_admin": True},
            )
            self._refresh_current_tab()

    def _manage_login(self):
        if self.login_status:
            confirm = QMessageBox.question(
                self,
                "Logout",
                "Vuoi eseguire il logout?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if confirm == QMessageBox.Yes:
                self._do_logout(publish=True)
            return

        dialog = QTLoginDialog(app_context=self.app_context, parent=self)
        dialog.exec()
        if dialog.success:
            self.login_status = True
            self.logged_user_id = dialog.user_id
            self.is_admin = False
            self._record_persist_prefs(dialog)
            self._toggle_login_widgets()
            self.app_context.event_bus.publish(
                ViewUtils.EventBusKeys.LOGIN_STATUS_CHANGED.value,
                {"login_status": True, "logged_user_id": dialog.user_id, "is_admin": False},
            )

    def _record_persist_prefs(self, dialog) -> None:
        """Cattura preferenze 'mantieni l'accesso' dal dialog di login."""
        self.persist_session_enabled = bool(getattr(dialog, "persist_enabled", False))
        self.persist_session_minutes = int(getattr(dialog, "persist_minutes", 30))

    def _do_logout(self, publish: bool = True) -> None:
        """Helper: chiude qualsiasi sessione attiva (utente o admin).
        Cancella anche eventuale sessione persistita: un logout esplicito
        e' la cancellazione di consenso a restare loggati."""
        self.login_status = False
        self.logged_user_id = -1
        self.is_admin = False
        self.persist_session_enabled = False
        self.app_context.session_persistence_service.clear_session()
        self.app_context.user_auth_service.logout()
        self._toggle_login_widgets()
        if publish:
            self.app_context.event_bus.publish(
                ViewUtils.EventBusKeys.LOGIN_STATUS_CHANGED.value,
                {"login_status": False, "logged_user_id": -1, "is_admin": False},
            )

    def _toggle_login_widgets(self):
        if self.login_status:
            self.login_action.setText("Esegui il logout")
            # Switch utente: ha senso anche da admin (porta a login utente).
            self.switch_account_action.setEnabled(True)
            # Disabilita "Login come admin" se gia' loggato come admin.
            self.admin_login_action.setEnabled(not self.is_admin)
        else:
            self.login_action.setText("Esegui il login")
            self.switch_account_action.setEnabled(False)
            self.admin_login_action.setEnabled(True)
        self._refresh_logged_user_icon()

    # ------------------------------------------------------------------

    def closeEvent(self, event):
        self._maybe_persist_session()
        scheduler = getattr(self.app_context, "backup_scheduler", None)
        if scheduler is not None:
            try:
                scheduler.stop()
            except Exception as exc:
                print(f"Errore nello stop del backup scheduler: {exc}")
        super().closeEvent(event)

    def _maybe_persist_session(self) -> None:
        """Se l'utente ha abilitato il "mantieni l'accesso" al login,
        chiede conferma e salva la sessione persistente prima di chiudere.
        """
        if not (self.login_status and self.persist_session_enabled):
            return

        service = self.app_context.session_persistence_service
        if not service.is_supported():
            return

        minutes = int(self.persist_session_minutes)
        reply = QMessageBox.question(
            self,
            "Mantieni l'accesso",
            (
                f"Vuoi rimanere loggato per {minutes} minuti dopo la chiusura "
                "dell'app?\n\nAlla prossima apertura entro questo intervallo "
                "non ti verra' chiesta la password."
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            service.clear_session()
            return

        if self.is_admin:
            service.save_admin_session(minutes)
        else:
            key_hex = self.app_context.user_crypto_service.active_key_hex
            if key_hex is None:
                print("[session] crypto session non attiva: salvataggio annullato")
                return
            service.save_user_session(self.logged_user_id, key_hex, minutes)

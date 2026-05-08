from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QWidget,
)

from Views.View_utils import ViewUtils

from QTViews.Details.QT_invoice_detail_view import QTInvoiceDetailViewH
from QTViews.ListViews.QT_clients_view import QTClientsViewH
from QTViews.ListViews.QT_invoices_view import QTInvoicesViewH
from QTViews.MenuWindows.QT_backup_runner import QTBackupRunner
from QTViews.MenuWindows.QT_backup_settings_dialog import QTBackupSettingsDialog
from QTViews.MenuWindows.QT_fiscal_settings_dialog import QTFiscalSettingsDialog
from QTViews.MenuWindows.QT_fiscal_year_closer_dialog import QTFiscalYearCloserDialog
from QTViews.MenuWindows.QT_load_backup_dialog import QTLoadBackupDialog
from QTViews.MenuWindows.QT_login_dialog import QTLoginDialog
from QTViews.MenuWindows.QT_recurring_expenses_dialog import QTRecurringExpensesDialog

if TYPE_CHECKING:
    from App_context import AppContext


class QTMainWindow(QMainWindow):
    """
    Main window QT.

    Replica l'architettura della MainWindow customtkinter:
    - una QMenuBar in alto con i menu "Gestione …";
    - un QTabWidget centrale con tutte le tab dell'applicazione;
    - un corner widget sul tabbar con il bottone di Login, l'icona utente
      e il refresh della tab corrente.

    Ad oggi le tab "Fatture" e "Clienti" sono funzionanti; le altre sono
    presenti per rispecchiare la struttura della view legacy ma non sono
    interagibili finché le rispettive view non saranno portate su Qt.

    Le voci dei menu in alto sono invece pienamente operative: ognuna apre
    la propria finestra dedicata (in QTViews/MenuWindows/), che eredita
    la logica della MainWindow legacy ma è ora estratta in classi separate.

    Quando l'utente apre il dettaglio di una fattura, la finestra commuta
    via QStackedWidget dalla tabview alla detail view, mantenendo coerente
    il flusso "Elenco Fatture / Dettaglio fattura" della versione legacy.
    """

    TAB_INVOICES = "Fatture"
    TAB_CLIENTS = "Clienti"

    @classmethod
    def _tab_names(cls):
        # L'ordine rispecchia quello della MainWindow legacy.
        return [
            "Utenti",
            cls.TAB_CLIENTS,
            "Fornitori",
            "Produzioni",
            "Conti",
            cls.TAB_INVOICES,
            "Pagamenti",
            "Rimborsi",
            "Spese",
            "Iva",
            "Salario",
            "Tasse",
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

        self.stack = QStackedWidget(self)
        self.stack.setContentsMargins(0, 12, 0, 0)
        self.setCentralWidget(self.stack)

        self.tabview = QTabWidget()
        self.tabview.setObjectName("MainTabView")
        self.tabview.setStyleSheet("""
            #MainTabView::pane {
                border-top: 1px solid #3a3a3a;
            }

            #MainTabView QTabBar::tab {
                min-width: 60px;
                min-height: 24px;
                padding: 8px 14px;
                font-size: 11pt;
            }

            #MainTabView QTabBar::tab:selected {
                background-color: #1F6AA5;
                color: white;
            }

            #MainTabView QTabBar::tab:!selected {
                background-color: #333333;
                color: #dddddd;
            }
        """)
        self.invoices_view = None
        self.clients_view = None
        self.invoice_detail_view = None
        self.login_status = False
        self.logged_user_id = -1
        self.backup_runner = QTBackupRunner(app_context=app_context, parent=self)

        self._build_tabs(initial_invoice_id)
        self._build_tab_corner()
        self.stack.addWidget(self.tabview)

        if self.invoices_view is not None:
            self.tabview.setCurrentWidget(self.invoices_view)

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
        menubar = self.menuBar()
        menubar.setStyleSheet(
            """
            QMenuBar {
                padding-top: 10px;
            }
            """
        )
        backup = menubar.addMenu("Gestione Backup")
        backup.addAction("Impostazioni backup").triggered.connect(self._open_backup_settings)
        backup.addAction("Esegui un backup manuale del Database").triggered.connect(
            self._execute_db_backup
        )
        backup.addAction("Esegui un backup manuale dei libri contabili").triggered.connect(
            self._execute_books_backup
        )
        backup.addAction("Carica un backup del Database").triggered.connect(self._open_load_backup)

        fiscal = menubar.addMenu("Gestione Dati Fiscali")
        fiscal.addAction("Modifica dati fiscali").triggered.connect(self._open_fiscal_settings)

        recurring = menubar.addMenu("Gestione Spese Ricorrenti")
        recurring.addAction("Modifica Spese Ricorrenti").triggered.connect(
            self._open_recurring_expenses
        )

        fiscal_year = menubar.addMenu("Gestione Esercizio")
        fiscal_year.addAction(
            f"Chiusura Esercizio {datetime.now().year}"
        ).triggered.connect(self._open_fiscal_year_closer)

    def _build_tabs(self, initial_invoice_id):
        for name in self._tab_names():
            if name == self.TAB_INVOICES:
                self.invoices_view = QTInvoicesViewH(
                    app_context=self.app_context,
                    initial_invoice_id=initial_invoice_id,
                    on_open_detail=self._open_invoice_detail,
                    parent=self,
                )
                self.tabview.addTab(self.invoices_view, name)
            elif name == self.TAB_CLIENTS:
                # La detail view dei clienti non e' ancora portata su Qt:
                # passiamo on_open_detail=None cosi' il doppio click sulla
                # riga e' un no-op finche' la detail non sara' pronta.
                self.clients_view = QTClientsViewH(
                    app_context=self.app_context,
                    initial_client_id=None,
                    on_open_detail=None,
                    parent=self,
                )
                self.tabview.addTab(self.clients_view, name)
            else:
                placeholder = QLabel(f"{name}\nNon ancora portata su Qt.")
                placeholder.setAlignment(Qt.AlignCenter)
                placeholder.setStyleSheet("color: #888888; font-size: 14pt;")
                idx = self.tabview.addTab(placeholder, name)
                self.tabview.setTabEnabled(idx, False)

    def _build_tab_corner(self):
        corner = QWidget()
        layout = QHBoxLayout(corner)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        self.login_button = QPushButton("Login")
        self.login_button.clicked.connect(self._manage_login)
        layout.addWidget(self.login_button)

        try:
            user_icon_path = Path(self.app_context.images_path) / "user.png"
            if user_icon_path.exists():
                icon_label = QLabel()
                pix = QPixmap(str(user_icon_path)).scaled(
                    28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                icon_label.setPixmap(pix)
                layout.addWidget(icon_label)
        except Exception:
            pass

        self.refresh_button = QPushButton("🔄")
        self.refresh_button.setFixedWidth(36)
        self.refresh_button.setToolTip("Aggiorna la tab corrente")
        self.refresh_button.clicked.connect(self._refresh_current_tab)
        layout.addWidget(self.refresh_button)

        self.tabview.setCornerWidget(corner, Qt.TopRightCorner)

    # ------------------------------------------------------------------
    # Azioni
    # ------------------------------------------------------------------

    def _refresh_current_tab(self):
        widget = self.tabview.currentWidget()
        if widget is self.invoices_view and self.invoices_view is not None:
            # Ricarica la lista fatture rispettando la time window selezionata.
            self.invoices_view._on_window_changed()
        elif widget is self.clients_view and self.clients_view is not None:
            self.clients_view._on_window_changed()

    def _open_invoice_detail(self, invoice_id):
        if self.invoice_detail_view is not None:
            self.stack.removeWidget(self.invoice_detail_view)
            self.invoice_detail_view.deleteLater()
            self.invoice_detail_view = None

        self.invoice_detail_view = QTInvoiceDetailViewH(
            app_context=self.app_context,
            invoice_id=invoice_id,
            on_back=self._back_to_list,
            parent=self,
        )
        self.stack.addWidget(self.invoice_detail_view)
        self.stack.setCurrentWidget(self.invoice_detail_view)

    def _back_to_list(self):
        self.stack.setCurrentWidget(self.tabview)
        if self.invoices_view is not None:
            self.tabview.setCurrentWidget(self.invoices_view)
        if self.invoice_detail_view is not None:
            self.stack.removeWidget(self.invoice_detail_view)
            self.invoice_detail_view.deleteLater()
            self.invoice_detail_view = None

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

    def _manage_login(self):
        if self.login_status:
            confirm = QMessageBox.question(
                self,
                "Logout",
                "Vuoi eseguire il logout?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if confirm == QMessageBox.Yes:
                self.login_status = False
                self.logged_user_id = -1
                self._toggle_login_widgets()
                self.app_context.event_bus.publish(
                    ViewUtils.EventBusKeys.LOGIN_STATUS_CHANGED.value,
                    {"login_status": False, "logged_user_id": -1},
                )
            return

        dialog = QTLoginDialog(app_context=self.app_context, parent=self)
        dialog.exec()
        if dialog.success:
            self.login_status = True
            self.logged_user_id = dialog.user_id
            self._toggle_login_widgets()

    def _toggle_login_widgets(self):
        self.login_button.setText("Esegui Logout" if self.login_status else "Login")

    # ------------------------------------------------------------------

    def closeEvent(self, event):
        scheduler = getattr(self.app_context, "backup_scheduler", None)
        if scheduler is not None:
            try:
                scheduler.stop()
            except Exception as exc:
                print(f"Errore nello stop del backup scheduler: {exc}")
        super().closeEvent(event)

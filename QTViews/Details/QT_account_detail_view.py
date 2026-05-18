"""
Vista dettaglio conto corrente, versione Qt.

Replica ``Views/Details/Account_detail_view.py`` (legacy CustomTkinter):
- sezione "Dati Conto" editabile: nome conto, saldo iniziale
  (al 31-12 dell'anno precedente) e saldo corrente (read-only,
  calcolato);
- sezione "Storico Movimenti" read-only con la tabella dei movimenti
  (data, descrizione, tipo, importo) ordinati dal piu' recente;
- toggle "Abilita la modifica" che, come nella legacy, abilita/disabilita
  i campi editabili e il bottone Salva.

Differenze dalla legacy:
- aggiunto un bottone "Elimina Conto" nella action bar, coerente con il
  pattern di ``QTUserDetailViewH`` (la logica di delete esiste gia' nel
  controller, la legacy aveva solo un popup di conferma non cablato);
- il saldo corrente viene calcolato con
  ``AccountAnalyzerService.calculate_account_balance_by_account_id``,
  invece di ricalcolarlo a mano dai movimenti.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from Gestionale_Enums import DBAccountsColumns

if TYPE_CHECKING:
    from App_context import AppContext


class QTAccountDetailViewH(QWidget):
    """QWidget dettaglio conto corrente."""

    def __init__(self, app_context: "AppContext", account_id, on_back, parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.account_controller = app_context.account_controller
        self.accounts_query_service = app_context.account_query_service
        self.account_analyzer_service = app_context.account_analyzer_service

        self.current_account_id = account_id
        self.account: dict | None = None
        self.on_back = on_back

        self._widgets: dict = {}
        # Stato admin: la gestione conti (modifica/eliminazione) e'
        # un'azione amministrativa, quindi i pulsanti restano disabilitati
        # per gli utenti normali anche col toggle "Abilita la modifica".
        self._is_admin: bool = getattr(parent, "is_admin", False)
        if self._is_admin is False and parent is not None:
            # Fallback: chiede a tutta la finestra principale.
            parent_window = parent.window() if hasattr(parent, "window") else parent
            self._is_admin = getattr(parent_window, "is_admin", False)
        try:
            app_context.event_bus.subscribe(
                "LOGIN_STATUS_CHANGED",
                self._on_login_changed,
            )
        except Exception:
            pass

        self._build_ui()
        self.load_account(account_id)

    def _on_login_changed(self, data):
        if isinstance(data, dict):
            self._is_admin = bool(data.get("is_admin", False))
        if hasattr(self, "modify_switch"):
            self._on_modify_toggled(self.modify_switch.isChecked())

    # ------------------------------------------------------------------
    # UI base (head bar + content + action bar)
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # Head bar.
        head = QFrame()
        head.setObjectName("AccountDetailHead")
        head.setStyleSheet(
            "#AccountDetailHead { background-color: palette(window); border-radius: 6px; }"
        )
        head_layout = QHBoxLayout(head)
        head_layout.setContentsMargins(10, 6, 10, 6)

        self.back_button = QPushButton("Torna ai conti")
        self.back_button.clicked.connect(self._cleanup_and_go_back)
        head_layout.addWidget(self.back_button)

        self.title_label = QLabel("")
        f = self.title_label.font()
        f.setPointSize(16)
        f.setBold(True)
        self.title_label.setFont(f)
        self.title_label.setAlignment(Qt.AlignCenter)
        head_layout.addWidget(self.title_label, stretch=1)

        self.modify_switch = QCheckBox("Abilita la modifica")
        self.modify_switch.toggled.connect(self._on_modify_toggled)
        head_layout.addWidget(self.modify_switch)

        root.addWidget(head)

        self.content = QWidget()
        root.addWidget(self.content, stretch=1)
        self.content_layout = QHBoxLayout(self.content)
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        self.content_layout.setSpacing(15)

        # Action bar: Salva / Elimina.
        self.action_bar = QFrame()
        self.action_bar.setObjectName("AccountDetailActions")
        self.action_bar.setStyleSheet(
            "#AccountDetailActions { background-color: palette(window); border-radius: 6px; }"
        )
        action_layout = QHBoxLayout(self.action_bar)
        action_layout.setContentsMargins(15, 8, 15, 8)

        self.save_btn = QPushButton("Salva Conto")
        self.save_btn.clicked.connect(self._save_account_mod)
        self.save_btn.setEnabled(False)
        action_layout.addWidget(self.save_btn)

        action_layout.addStretch(1)

        self.delete_btn = QPushButton("Elimina Conto")
        self.delete_btn.setStyleSheet(
            "QPushButton { background-color: #8B0000; color: palette(highlighted-text); }"
            "QPushButton:hover { background-color: #A52A2A; }"
            "QPushButton:disabled { background-color: #4a2727; color: palette(mid); }"
        )
        self.delete_btn.clicked.connect(self._delete_account)
        self.delete_btn.setEnabled(False)
        action_layout.addWidget(self.delete_btn)

    # ------------------------------------------------------------------
    # Sezione "Dati Conto"
    # ------------------------------------------------------------------

    def _build_info_section(self, account_data: dict, current_balance: float):
        frame = QFrame()
        frame.setObjectName("AccountInfoFrame")
        frame.setStyleSheet(
            "#AccountInfoFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
        )
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(15, 15, 15, 15)
        outer.setSpacing(10)

        section_title = QLabel("Dati Conto")
        tf = section_title.font()
        tf.setBold(True)
        tf.setPointSize(12)
        section_title.setFont(tf)
        outer.addWidget(section_title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        # Nome conto (editabile).
        name_edit = QLineEdit(str(account_data.get(DBAccountsColumns.NAME.value, "") or ""))
        grid.addWidget(QLabel("Nome Conto:"), 0, 0, alignment=Qt.AlignLeft)
        grid.addWidget(name_edit, 0, 1)
        self._widgets[DBAccountsColumns.NAME.value] = name_edit

        # Saldo iniziale (editabile).
        init_balance = float(account_data.get(DBAccountsColumns.INIT_BALANCE.value, 0) or 0)
        init_edit = QLineEdit(f"{init_balance:.2f}")
        grid.addWidget(
            QLabel(f"Saldo Iniziale (31-12-{datetime.now().year - 1}):"),
            1, 0, alignment=Qt.AlignLeft,
        )
        grid.addWidget(init_edit, 1, 1)
        self._widgets[DBAccountsColumns.INIT_BALANCE.value] = init_edit

        # Saldo corrente (read-only).
        current_lbl = QLabel(f"{current_balance:.2f} €")
        cf = current_lbl.font()
        cf.setBold(True)
        current_lbl.setFont(cf)
        current_lbl.setStyleSheet(
            f"color: {'#2ECC71' if current_balance >= 0 else '#E74C3C'};"
        )
        grid.addWidget(QLabel("Saldo Corrente:"), 2, 0, alignment=Qt.AlignLeft)
        grid.addWidget(current_lbl, 2, 1)

        grid.setColumnStretch(1, 1)
        outer.addLayout(grid)

        outer.addWidget(self.action_bar)

        self.content_layout.addWidget(frame, stretch=1, alignment=Qt.AlignTop)

    # ------------------------------------------------------------------
    # Sezione "Storico Movimenti"
    # ------------------------------------------------------------------

    def _build_movements_section(self, movements: list[dict]):
        frame = QFrame()
        frame.setObjectName("AccountMovementsFrame")
        frame.setStyleSheet(
            "#AccountMovementsFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
        )
        v = QVBoxLayout(frame)
        v.setContentsMargins(15, 12, 15, 12)
        v.setSpacing(8)

        title = QLabel("Storico Movimenti")
        tf = title.font()
        tf.setBold(True)
        tf.setPointSize(12)
        title.setFont(tf)
        v.addWidget(title)

        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Data", "Descrizione", "Tipo", "Importo"])
        table.setRowCount(len(movements))
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(42)
        table.setAlternatingRowColors(True)
        table.setStyleSheet(
            """
            QTableWidget {
                font-size: 11pt;
            }

            QTableWidget::item {
                padding: 8px 10px;
            }

            QHeaderView::section {
                font-size: 11pt;
                font-weight: bold;
                padding: 8px 10px;
            }
            """
        )

        header = table.horizontalHeader()
        header.setMinimumSectionSize(120)
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        table.setColumnWidth(0, 150)
        table.setColumnWidth(2, 150)
        table.setColumnWidth(3, 140)

        for row, mov in enumerate(movements):
            date_item = QTableWidgetItem(str(mov.get("date", "")))
            desc_item = QTableWidgetItem(str(mov.get("name", "")))
            type_item = QTableWidgetItem(str(mov.get("type", "")))

            sign = mov.get("sign", "+")
            amount = float(mov.get("amount", 0) or 0)
            amount_item = QTableWidgetItem(f"{sign}{amount:.2f} €")
            amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            amount_item.setForeground(
                Qt.green if sign == "+" else Qt.red
            )

            table.setItem(row, 0, date_item)
            table.setItem(row, 1, desc_item)
            table.setItem(row, 2, type_item)
            table.setItem(row, 3, amount_item)

        table.setMinimumHeight(300)
        v.addWidget(table, stretch=1)

        self.content_layout.addWidget(frame, stretch=3)

    # ------------------------------------------------------------------
    # Caricamento conto
    # ------------------------------------------------------------------

    def load_account(self, account_id):
        self.current_account_id = account_id
        self._clear_content()

        account = self.accounts_query_service.retrieve_account_map_by_id(account_id)
        if not account:
            self.title_label.setText("Conto non trovato")
            return

        self.account = account
        self.title_label.setText(str(account.get(DBAccountsColumns.NAME.value, "") or "Conto"))

        current_balance = self.account_analyzer_service.calculate_account_balance_by_account_id(
            account_id
        )
        movements = self.account_analyzer_service.retrieve_account_movements_by_account_id(
            account_id
        )

        self._build_info_section(account, current_balance)
        self._build_movements_section(movements)

        self._on_modify_toggled(self.modify_switch.isChecked())

    def _clear_content(self):
        if hasattr(self, "action_bar"):
            self.action_bar.setParent(None)
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._widgets.clear()
        self.modify_switch.blockSignals(True)
        self.modify_switch.setChecked(False)
        self.modify_switch.blockSignals(False)

    # ------------------------------------------------------------------
    # Toggle edit
    # ------------------------------------------------------------------

    def _on_modify_toggled(self, enabled: bool):
        if not hasattr(self, "save_btn"):
            return
        # Gestione conti: solo admin puo' salvare/eliminare.
        admin_enabled = enabled and self._is_admin
        self.save_btn.setEnabled(admin_enabled)
        self.delete_btn.setEnabled(admin_enabled)
        for widget in self._widgets.values():
            widget.setEnabled(admin_enabled)
        if not self._is_admin:
            tooltip = "Solo l'amministratore puo' modificare i conti correnti."
            self.save_btn.setToolTip(tooltip)
            self.delete_btn.setToolTip(tooltip)
        else:
            self.save_btn.setToolTip("")
            self.delete_btn.setToolTip("")

    # ------------------------------------------------------------------
    # Salvataggio / eliminazione
    # ------------------------------------------------------------------

    def _save_account_mod(self):
        if self.account is None:
            return

        name = self._widgets[DBAccountsColumns.NAME.value].text().strip()
        init_balance = self._widgets[DBAccountsColumns.INIT_BALANCE.value].text().strip()

        if not name:
            QMessageBox.critical(self, "ERRORE", "Il nome del conto non può essere vuoto.")
            return

        account_data = {
            DBAccountsColumns.NAME.value: name,
            DBAccountsColumns.INIT_BALANCE.value: init_balance,
        }

        success, message = self.account_controller.update_account(
            self.current_account_id, account_data
        )
        if not success:
            QMessageBox.critical(self, "ERRORE", message)
            return

        QMessageBox.information(self, "SALVATAGGIO COMPLETATO", message)
        self.modify_switch.setChecked(False)
        self.load_account(self.current_account_id)

    def _delete_account(self):
        confirm = QMessageBox.question(
            self,
            "ELIMINAZIONE CONTO",
            "Stai per eliminare questo conto.\nDesideri continuare?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        success, message = self.account_controller.delete_account_by_ID(
            self.current_account_id
        )
        if not success:
            QMessageBox.critical(self, "ERRORE", message)
            return

        QMessageBox.information(self, "CONTO ELIMINATO", message)
        self._cleanup_and_go_back()

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _cleanup_and_go_back(self):
        if self.on_back is not None:
            self.on_back()

"""
List view conti correnti, versione Qt.

Replica ``Views/Accounts_view.py`` (legacy CustomTkinter):
- la legacy mostrava le card con ``pack(side='left')`` e un wrap manuale
  a 4 per riga; qui usiamo un ``QFlowLayout`` dentro una ``QScrollArea``
  che riposiziona le card automaticamente in base alla larghezza, come
  fa gia' ``QTUsersViewH``;
- il saldo di ogni conto viene calcolato con
  ``AccountAnalyzerService.calculate_account_balance_by_account_id``,
  esattamente come la legacy;
- la creazione di un nuovo conto avviene tramite il dialog
  ``QTAccountCreateViewH``;
- aggiunta una ricerca incrementale per filtrare per nome conto (la
  legacy non ce l'aveva, ma e' coerente con le altre list view Qt).

Il bottone "Esegui Bonifico" della legacy non e' replicato: la view di
creazione bonifico non e' ancora stata portata su Qt.
"""

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from Gestionale_Enums import DBAccountsColumns
from QTViews.CustomWidgets.QT_account_card import QTAccountCard

if TYPE_CHECKING:
    from App_context import AppContext


class QTAccountsViewH(QWidget):
    """List view conti basata su flow layout di card."""

    def __init__(
        self,
        app_context: "AppContext",
        on_open_detail=None,
        parent=None,
    ):
        super().__init__(parent)
        self.app_context = app_context
        self.on_open_detail = on_open_detail

        self.accounts_query_service = app_context.account_query_service
        self.account_controller = app_context.account_controller
        self.account_analyzer_service = app_context.account_analyzer_service

        # Cache dei map conto caricati: la ricerca filtra in memoria.
        self._accounts: list[dict] = []
        self._cards: dict[int, QTAccountCard] = {}

        self._build_ui()
        self._reload_accounts()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 20, 10, 10)
        root.setSpacing(12)

        title = QLabel("Gestisci i conti correnti")
        f = title.font()
        f.setPointSize(15)
        f.setBold(True)
        title.setFont(f)
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        # Barra di controllo: ricerca + numero conti.
        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(QLabel("Cerca:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Nome conto…")
        self.search_edit.textChanged.connect(self._apply_filter)
        controls.addWidget(self.search_edit, stretch=1)

        controls.addStretch(1)
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: palette(mid);")
        controls.addWidget(self.count_label)

        root.addLayout(controls)

        # Scroll area + layout centrato per le card (max 3 per riga).
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        root.addWidget(self.scroll, stretch=1)

        self.cards_container = QWidget()
        self.scroll.setWidget(self.cards_container)
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(24, 24, 24, 24)
        self.cards_layout.setSpacing(20)

        # Bottom bar: bottone "Aggiungi".
        bottom = QHBoxLayout()
        self.add_button = QPushButton("Aggiungi Nuovo Conto")
        self.add_button.setMinimumSize(200, 40)
        self.add_button.clicked.connect(self._on_add_account)
        bottom.addStretch(1)
        bottom.addWidget(self.add_button)
        bottom.addStretch(1)
        root.addLayout(bottom)

    # ------------------------------------------------------------------
    # Pipeline dati
    # ------------------------------------------------------------------

    def _reload_accounts(self):
        self._accounts = self.accounts_query_service.retrieve_accounts_map_list() or []
        self._rebuild_cards()

    def _rebuild_cards(self):
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._cards.clear()

        cards: list[QTAccountCard] = []
        for account in self._iter_filtered_accounts():
            card = self._make_card_for_account(account)
            self._cards[card.account_id] = card
            cards.append(card)

        # Righe di max 3 card, centrate orizzontalmente.
        for i in range(0, len(cards), 3):
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(24)
            row_layout.addStretch(1)
            for card in cards[i:i + 3]:
                row_layout.addWidget(card)
            row_layout.addStretch(1)
            self.cards_layout.addWidget(row_widget)

        self.cards_layout.addStretch(1)

        n = len(self._cards)
        total = len(self._accounts)
        self.count_label.setText(
            f"{n} di {total} conti" if n != total else f"{n} conti"
        )

    def _iter_filtered_accounts(self):
        needle = self.search_edit.text().strip().lower() if hasattr(self, "search_edit") else ""
        if not needle:
            yield from self._accounts
            return
        for account in self._accounts:
            name = str(account.get(DBAccountsColumns.NAME.value, "") or "").lower()
            if needle in name:
                yield account

    def _make_card_for_account(self, account: dict) -> QTAccountCard:
        account_id = account[DBAccountsColumns.ID.value]
        balance = self.account_analyzer_service.calculate_account_balance_by_account_id(account_id)
        card = QTAccountCard(
            account_id=account_id,
            name=account.get(DBAccountsColumns.NAME.value, "") or "",
            balance=balance,
        )
        card.clicked.connect(self._on_card_clicked)
        card.bonifico_requested.connect(self._on_bonifico_requested)
        return card

    # ------------------------------------------------------------------
    # Eventi UI
    # ------------------------------------------------------------------

    def _apply_filter(self, _text=None):
        self._rebuild_cards()

    def _on_card_clicked(self, account_id: int):
        if self.on_open_detail is not None:
            self.on_open_detail(account_id)

    def _on_bonifico_requested(self, sender_account_id: int):
        # Import locale per evitare cicli.
        from QTViews.Creators.QT_transfer_create_view import QTTransferCreateViewH
        from QTViews.QT_creator_session import launch_creator

        dialog = QTTransferCreateViewH(
            app_context=self.app_context,
            sender_account_id=sender_account_id,
            parent=self,
        )

        def _on_finished(_result=None):
            if dialog.transfer_saved:
                # I saldi sono cambiati: ricarica le card.
                self._reload_accounts()

        # Connesso prima di launch_creator, così viene eseguito prima del
        # cleanup della sessione (che fa deleteLater del dialog).
        dialog.finished.connect(_on_finished)
        launch_creator(self, self.app_context, dialog)

    def _on_add_account(self):
        # Import locale per evitare cicli.
        from QTViews.Creators.QT_account_create_view import QTAccountCreateViewH
        from QTViews.QT_creator_session import launch_creator

        dialog = QTAccountCreateViewH(
            app_context=self.app_context,
            parent=self,
        )

        def _on_accepted():
            self._reload_accounts()
            new_id = dialog.created_account_id
            if new_id is not None and self.on_open_detail is not None:
                self.on_open_detail(new_id)

        dialog.accepted.connect(_on_accepted)
        launch_creator(self, self.app_context, dialog)

    # ------------------------------------------------------------------
    # API esterna per la main view (refresh dopo edit)
    # ------------------------------------------------------------------

    def refresh(self):
        """Da chiamare dalla main view dopo un update/delete del detail."""
        self._reload_accounts()

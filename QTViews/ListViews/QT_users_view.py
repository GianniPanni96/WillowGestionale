"""
List view utenti, versione Qt.

Differenze rispetto alla legacy CustomTkinter:
- non eredita da ``QTBaseListView`` perche' il dominio utenti non e'
  tabellare (mostriamo card "fisiche" con foto + dati anagrafici);
- usa un ``QFlowLayout`` dentro una ``QScrollArea``: le card si
  riposizionano automaticamente in piu' righe in base alla larghezza
  della finestra. Cosi' la view resta usabile anche con molti utenti
  (la legacy era pack ``side='left'`` con wrap manuale a 4: non
  scalava);
- ricerca incrementale per filtrare per nome/cognome/partita iva/email
  senza ricaricare il DB;
- ogni card e' un ``QTUserCard`` con layout interno adattivo
  all'aspect ratio della foto (vedi quel modulo).
"""

import os
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from Gestionale_Enums import DBUsersColumns
from QTViews.CustomWidgets.QT_user_card import QTUserCard

if TYPE_CHECKING:
    from App_context import AppContext


class QTUsersViewH(QWidget):
    """List view utenti basata su flow layout di card."""

    def __init__(
        self,
        app_context: "AppContext",
        on_open_detail=None,
        parent=None,
    ):
        super().__init__(parent)
        self.app_context = app_context
        self.on_open_detail = on_open_detail

        self.user_query_service = app_context.user_query_service
        self.user_controller = app_context.user_controller
        self.accounts_query_service = app_context.account_query_service

        # Cache dei map utente caricati al boot (anagrafica completa, una
        # entry per utente). La ricerca filtra in memoria, senza altri
        # round-trip al DB.
        self._users: list[dict] = []
        # Mappa user_id -> widget card per gestire rimozione/refresh
        # incrementale senza distruggere l'intero flow layout.
        self._cards: dict[int, QTUserCard] = {}

        self._build_ui()
        self._reload_users()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 20, 10, 10)
        root.setSpacing(12)

        title = QLabel("Gestione utenti")
        f = title.font()
        f.setPointSize(15)
        f.setBold(True)
        title.setFont(f)
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        # Barra di controllo: ricerca + numero utenti.
        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(QLabel("Cerca:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Nome, cognome, P. IVA, email…")
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
        self.add_button = QPushButton("Aggiungi Nuovo Utente")
        self.add_button.setMinimumSize(200, 40)
        self.add_button.clicked.connect(self._on_add_user)
        bottom.addStretch(1)
        bottom.addWidget(self.add_button)
        bottom.addStretch(1)
        root.addLayout(bottom)

    # ------------------------------------------------------------------
    # Pipeline dati
    # ------------------------------------------------------------------

    def _reload_users(self):
        self._users = self.user_query_service.retrieve_users_map_list() or []
        self._rebuild_cards()

    def _rebuild_cards(self):
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._cards.clear()

        cards: list[QTUserCard] = []
        for user in self._iter_filtered_users():
            card = self._make_card_for_user(user)
            self._cards[card.user_id] = card
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
        total = len(self._users)
        self.count_label.setText(
            f"{n} di {total} utenti" if n != total else f"{n} utenti"
        )

    def _iter_filtered_users(self):
        needle = (self.search_edit.text() if hasattr(self, "search_edit") else "").strip().lower()
        if not needle:
            yield from self._users
            return
        for user in self._users:
            hay = " ".join(
                str(user.get(col.value, "") or "")
                for col in (
                    DBUsersColumns.FIRST_NAME,
                    DBUsersColumns.LAST_NAME,
                    DBUsersColumns.PARTITA_IVA,
                    DBUsersColumns.CODICE_FISCALE,
                    DBUsersColumns.EMAIL,
                    DBUsersColumns.TELEFONO,
                )
            ).lower()
            if needle in hay:
                yield user

    def _make_card_for_user(self, user: dict) -> QTUserCard:
        photo_path = user.get(DBUsersColumns.PHOTO_PATH.value) or ""
        if photo_path and not os.path.exists(photo_path):
            photo_path = ""
        card = QTUserCard(
            user_id=user[DBUsersColumns.ID.value],
            first_name=user.get(DBUsersColumns.FIRST_NAME.value, "") or "",
            last_name=user.get(DBUsersColumns.LAST_NAME.value, "") or "",
            partita_iva=user.get(DBUsersColumns.PARTITA_IVA.value, "") or "",
            email=user.get(DBUsersColumns.EMAIL.value, "") or "",
            photo_path=photo_path,
        )
        card.clicked.connect(self._on_card_clicked)
        return card

    # ------------------------------------------------------------------
    # Eventi UI
    # ------------------------------------------------------------------

    def _apply_filter(self, _text=None):
        self._rebuild_cards()

    def _on_card_clicked(self, user_id: int):
        if self.on_open_detail is not None:
            self.on_open_detail(user_id)

    def _on_add_user(self):
        # Senza almeno un conto corrente la creazione utente non e' possibile
        # (FK su conto_corrente_id): replichiamo il check della legacy.
        accounts = self.accounts_query_service.retrieve_accounts_map_list() or []
        if not accounts:
            QMessageBox.warning(
                self,
                "Operazione non disponibile",
                "Prima di creare un utente è necessario creare almeno un conto corrente.",
            )
            return

        # Import locale per evitare cicli (la classe Creator e' nel modulo
        # ``Creators`` che a sua volta non importa nulla di questa view).
        from QTViews.Creators.QT_user_create_view import QTUserCreateViewH

        dialog = QTUserCreateViewH(
            app_context=self.app_context,
            parent=self,
        )
        if dialog.exec() == QTUserCreateViewH.Accepted:
            self._reload_users()
            new_id = dialog.created_user_id
            if new_id is not None and self.on_open_detail is not None:
                self.on_open_detail(new_id)

    # ------------------------------------------------------------------
    # API esterna per la main view (refresh dopo edit)
    # ------------------------------------------------------------------

    def refresh(self):
        """Da chiamare dalla main view dopo un update/delete del detail."""
        self._reload_users()

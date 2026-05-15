"""
Card conto corrente per la list view conti Qt.

Equivalente di ``QTUserCard`` ma per il dominio conti: la legacy
(``Views/Accounts_view.py``) mostrava una card con nome + saldo e i
bottoni "Dettaglio" / "Esegui Bonifico". Qui la card ha dimensione
fissa (così il flow layout resta uniforme), l'intera area testuale e'
cliccabile per aprire il dettaglio (come fa ``QTUserCard``), e in
fondo c'e' un bottone dedicato per avviare un bonifico in uscita.

Signal:
- ``clicked(int)`` -> ``account_id``: l'utente vuole aprire il dettaglio.
- ``bonifico_requested(int)`` -> ``account_id``: l'utente vuole avviare
  un bonifico in uscita da questo conto.

Il click sul bottone "Esegui Bonifico" non propaga al ``mousePressEvent``
della card (QPushButton consuma il left-click), quindi i due flussi
restano distinti.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout


class QTAccountCard(QFrame):
    """Card conto con nome, saldo e bottone bonifico."""

    CARD_W = 420
    CARD_H = 270

    clicked = Signal(int)
    bonifico_requested = Signal(int)

    def __init__(self, account_id: int, name: str, balance: float, parent=None):
        super().__init__(parent)
        self._account_id = account_id

        self.setObjectName("QTAccountCard")
        self.setFixedSize(self.CARD_W, self.CARD_H)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            "#QTAccountCard {"
            " background-color: palette(alternate-base);"
            " border: 1px solid palette(mid);"
            " border-radius: 8px;"
            "}"
            "#QTAccountCard:hover { border: 2px solid palette(highlight); }"
        )

        self._build_layout(name or "(senza nome)", balance)

    @property
    def account_id(self) -> int:
        return self._account_id

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._account_id)
        super().mousePressEvent(event)

    def _build_layout(self, name: str, balance: float):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(9)

        name_lbl = QLabel(name)
        name_font = QFont()
        name_font.setBold(True)
        name_font.setPointSize(18)
        name_lbl.setFont(name_font)
        name_lbl.setWordWrap(True)
        name_lbl.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        name_lbl.setStyleSheet("color: palette(text);")
        layout.addWidget(name_lbl)

        layout.addStretch(1)

        balance_lbl = QLabel(f"{balance:.2f} €")
        balance_font = QFont()
        balance_font.setPointSize(21)
        balance_lbl.setFont(balance_font)
        balance_lbl.setAlignment(Qt.AlignCenter)
        balance_lbl.setStyleSheet(
            f"color: {'#2ECC71' if balance >= 0 else '#E74C3C'};"
        )
        layout.addWidget(balance_lbl)

        layout.addStretch(1)

        hint = QLabel("Clicca per il dettaglio")
        hint_font = QFont()
        hint_font.setPointSize(11)
        hint_font.setItalic(True)
        hint.setFont(hint_font)
        hint.setStyleSheet("color: palette(mid);")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

        # Bottone dedicato per il bonifico in uscita. Il click viene
        # consumato dal bottone e NON propaga alla card, quindi non
        # innesca anche l'apertura del dettaglio.
        self._bonifico_btn = QPushButton("Esegui Bonifico")
        btn_font = QFont()
        btn_font.setPointSize(12)
        self._bonifico_btn.setFont(btn_font)
        self._bonifico_btn.setMinimumHeight(36)
        self._bonifico_btn.setCursor(Qt.PointingHandCursor)
        self._bonifico_btn.clicked.connect(
            lambda: self.bonifico_requested.emit(self._account_id)
        )
        layout.addWidget(self._bonifico_btn)

"""
Card utente "adattiva" per la list view utenti Qt.

Caratteristiche chiave:
- la card ha **dimensione totale fissa** (CARD_W × CARD_H), così la
  griglia/flow resta uniforme indipendentemente dalla foto scelta;
- la **disposizione interna** (foto vs blocco testi) cambia in funzione
  dell'aspect ratio della foto: foto landscape -> layout verticale
  (foto sopra, testi sotto); foto portrait o quadrata -> layout
  orizzontale (foto a sinistra, testi a destra);
- la foto **non viene mai stretchata**: viene scalata mantenendo l'aspect
  ratio originale e centrata dentro l'area che le compete.

Il widget espone un signal ``clicked(int)`` con l'``user_id`` per
permettere alla list view di aprire il dettaglio.
"""

import os

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class QTUserCard(QFrame):
    """Card utente con layout interno adattivo all'aspect ratio della foto."""

    # Dimensione "esterna" della card, uniforme per tutte le card.
    CARD_W = 540
    CARD_H = 300

    # Soglia per scegliere il layout: foto con aspect ratio > 1.05 -> landscape.
    LANDSCAPE_THRESHOLD = 1.05

    # Quote di superficie destinate alla foto rispetto al totale della card.
    PHOTO_W_HORIZONTAL = 225   # zona foto in layout orizzontale (porzione sinistra)
    PHOTO_H_VERTICAL = 150     # zona foto in layout verticale (porzione superiore)

    clicked = Signal(int)

    def __init__(
        self,
        user_id: int,
        first_name: str,
        last_name: str,
        partita_iva: str,
        email: str,
        photo_path: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._user_id = user_id

        self.setObjectName("QTUserCard")
        self.setFixedSize(self.CARD_W, self.CARD_H)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            "#QTUserCard {"
            " background-color: palette(alternate-base);"
            " border: 1px solid palette(mid);"
            " border-radius: 8px;"
            "}"
            "#QTUserCard:hover { border: 2px solid palette(highlight); }"
        )

        # Carichiamo la foto (se valida) e decidiamo il layout in base al
        # suo aspect ratio. ``_load_photo`` ritorna anche un flag per dire
        # se l'immagine e' effettivamente landscape.
        photo_pixmap, is_landscape = self._load_photo(photo_path)
        self._build_layout(
            photo_pixmap=photo_pixmap,
            is_landscape=is_landscape,
            first_name=first_name or "",
            last_name=last_name or "",
            partita_iva=partita_iva or "",
            email=email or "",
        )

    # ------------------------------------------------------------------
    # API esterna
    # ------------------------------------------------------------------

    @property
    def user_id(self) -> int:
        return self._user_id

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._user_id)
        super().mousePressEvent(event)

    # ------------------------------------------------------------------
    # Costruzione interna
    # ------------------------------------------------------------------

    def _load_photo(self, photo_path: str):
        """Restituisce ``(pixmap_o_None, is_landscape)``. ``pixmap`` e'
        None se il path non esiste o l'immagine non si carica; in quel
        caso ``is_landscape`` viene impostato a False (default verticale
        sembra piu' uniforme, ma in assenza di foto si usa un layout
        landscape con placeholder testuale)."""
        if not photo_path or not os.path.exists(photo_path):
            return None, True  # placeholder banda orizzontale superiore

        pixmap = QPixmap(photo_path)
        if pixmap.isNull():
            return None, True

        aspect = pixmap.width() / max(1, pixmap.height())
        is_landscape = aspect >= self.LANDSCAPE_THRESHOLD
        return pixmap, is_landscape

    def _build_layout(
        self,
        photo_pixmap,
        is_landscape: bool,
        first_name: str,
        last_name: str,
        partita_iva: str,
        email: str,
    ):
        if is_landscape:
            self._build_vertical_layout(photo_pixmap, first_name, last_name, partita_iva, email)
        else:
            self._build_horizontal_layout(photo_pixmap, first_name, last_name, partita_iva, email)

    # --- Variante landscape: foto sopra, testi sotto ----------------

    def _build_vertical_layout(self, pixmap, first_name, last_name, partita_iva, email):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        photo_area = self._make_photo_label(
            pixmap,
            QSize(self.CARD_W - 16, self.PHOTO_H_VERTICAL),
        )
        layout.addWidget(photo_area)

        info = self._make_info_block(first_name, last_name, partita_iva, email)
        layout.addWidget(info, stretch=1)

    # --- Variante portrait/quadrata: foto a sinistra, testi a destra -

    def _build_horizontal_layout(self, pixmap, first_name, last_name, partita_iva, email):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(18)

        photo_area = self._make_photo_label(
            pixmap,
            QSize(self.PHOTO_W_HORIZONTAL, self.CARD_H - 16),
        )
        layout.addWidget(photo_area)

        info = self._make_info_block(first_name, last_name, partita_iva, email)
        layout.addWidget(info, stretch=1)

    # ------------------------------------------------------------------
    # Building blocks
    # ------------------------------------------------------------------

    def _make_photo_label(self, pixmap, target_size: QSize) -> QLabel:
        """Restituisce un QLabel di dimensione fissa ``target_size`` che
        contiene la foto scalata mantenendo l'aspect ratio. In assenza
        di foto valida mostra un placeholder testuale."""
        lbl = QLabel()
        lbl.setFixedSize(target_size)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            "QLabel {"
            " background-color: palette(window);"
            " border-radius: 6px;"
            " color: palette(mid);"
            "}"
        )
        if pixmap is not None and not pixmap.isNull():
            scaled = pixmap.scaled(
                target_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            lbl.setPixmap(scaled)
        else:
            lbl.setText("Nessuna\nfoto")
        return lbl

    def _make_info_block(self, first_name, last_name, partita_iva, email) -> QWidget:
        wrapper = QWidget()
        wrapper.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        vbox = QVBoxLayout(wrapper)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(4)

        name_lbl = QLabel(f"{first_name} {last_name}".strip() or "(senza nome)")
        f = QFont()
        f.setBold(True)
        f.setPointSize(16)
        name_lbl.setFont(f)
        name_lbl.setStyleSheet("color: palette(text);")
        name_lbl.setWordWrap(True)
        vbox.addWidget(name_lbl)

        piva_lbl = QLabel(f"P. IVA: {partita_iva}" if partita_iva else "P. IVA: —")
        pf = QFont()
        pf.setPointSize(13)
        piva_lbl.setFont(pf)
        piva_lbl.setStyleSheet("color: palette(text);")
        piva_lbl.setWordWrap(True)
        vbox.addWidget(piva_lbl)

        email_lbl = QLabel(f"Email: {email}" if email else "Email: —")
        ef = QFont()
        ef.setPointSize(13)
        email_lbl.setFont(ef)
        email_lbl.setStyleSheet("color: palette(text);")
        email_lbl.setWordWrap(True)
        email_lbl.setToolTip(email or "")
        vbox.addWidget(email_lbl)

        vbox.addStretch(1)

        hint = QLabel("Clicca per il dettaglio")
        hf = QFont()
        hf.setPointSize(11)
        hf.setItalic(True)
        hint.setFont(hf)
        hint.setStyleSheet("color: palette(mid);")
        hint.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        vbox.addWidget(hint)

        return wrapper

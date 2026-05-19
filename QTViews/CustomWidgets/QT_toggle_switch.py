"""
Switch toggle custom in stile customTkinter (CTkSwitch).

Widget binario disegnato via ``paintEvent``: una "track" arrotondata e
un "thumb" circolare che scivola tra i due lati. Cambia stato al singolo
click sinistro. Espone:

- ``is_on()`` per leggere lo stato corrente come bool;
- ``set_on(value)`` per impostare lo stato a freddo (no callback);
- ``toggled`` signal (``Signal(bool)``) per chi preferisce lo stile Qt;
- ``on_change`` callback opzionale passata al costruttore, invocata dopo
  ogni cambio di stato innescato dall'utente.

Il widget non ospita un testo: la label descrittiva va affiancata da
fuori con un ``QLabel`` separato, cosi' il chiamante sceglie posizione
e stile.

Affordance: cursore a manina, bordo sottile sul track, contrasto netto
ON (palette highlight) vs OFF (grigio), thumb bianco con leggera ombra
quando il widget e' enabled.
"""

from typing import Callable, Optional

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class QTToggleSwitch(QWidget):
    """Switch on/off in stile CTkSwitch."""

    DEFAULT_WIDTH = 46
    DEFAULT_HEIGHT = 24
    PADDING = 3

    TRACK_OFF_COLOR = "#5a5a5a"
    TRACK_ON_COLOR = "#2659ab"
    THUMB_COLOR = "#ffffff"
    BORDER_COLOR = "#3a3a3a"
    DISABLED_TRACK_COLOR = "#3d3d3d"
    DISABLED_THUMB_COLOR = "#888888"

    toggled = Signal(bool)

    def __init__(
        self,
        on_change: Optional[Callable[[bool], None]] = None,
        initial: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._on = bool(initial)
        self._on_change = on_change
        self.setFixedSize(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)
        self.setCursor(Qt.PointingHandCursor)

    # ------------------------------------------------------------------
    # API pubblica
    # ------------------------------------------------------------------

    def is_on(self) -> bool:
        return self._on

    def set_on(self, value: bool, *, notify: bool = False):
        new_state = bool(value)
        if new_state == self._on:
            return
        self._on = new_state
        self.update()
        if notify:
            self._fire()

    def toggle(self, *, notify: bool = True):
        self._on = not self._on
        self.update()
        if notify:
            self._fire()

    # ------------------------------------------------------------------
    # Eventi
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if self.isEnabled() and event.button() == Qt.LeftButton:
            self.toggle()
            event.accept()
            return
        super().mousePressEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)

        if not self.isEnabled():
            track_color = QColor(self.DISABLED_TRACK_COLOR)
            thumb_color = QColor(self.DISABLED_THUMB_COLOR)
        else:
            track_color = QColor(self.TRACK_ON_COLOR if self._on else self.TRACK_OFF_COLOR)
            thumb_color = QColor(self.THUMB_COLOR)

        # Track
        pen = QPen(QColor(self.BORDER_COLOR))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(track_color)
        radius = rect.height() / 2
        painter.drawRoundedRect(rect, radius, radius)

        # Thumb
        thumb_diameter = rect.height() - 2 * self.PADDING
        thumb_y = self.PADDING
        if self._on:
            thumb_x = rect.width() - self.PADDING - thumb_diameter
        else:
            thumb_x = self.PADDING
        painter.setBrush(thumb_color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(int(thumb_x), int(thumb_y), int(thumb_diameter), int(thumb_diameter))

    def sizeHint(self) -> QSize:
        return QSize(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _fire(self):
        self.toggled.emit(self._on)
        if self._on_change is not None:
            self._on_change(self._on)

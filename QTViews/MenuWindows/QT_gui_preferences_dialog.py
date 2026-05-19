"""
Dialog di configurazione delle preferenze GUI persistenti dell'app.

Due dialog separati:

- ``QTStartupTabDialog``: permette di scegliere la tab di avvio
  dell'app (default: Utenti).

- ``QTListViewFiltersDialog``: permette di personalizzare la finestra
  temporale di default (``Mostra ultimi``) per ciascuna list view
  dell'app (clienti, fatture, pagamenti, …).

I dati vengono persistiti in ``gui_preferences.json`` via
``GuiPreferencesManager``; eventuali valori non validi o assenti
ricadono sui default hardcoded delle rispettive view.
"""

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from QTViews.ListViews.QT_clients_view import QTClientsViewH
from QTViews.ListViews.QT_expenses_view import QTExpensesViewH
from QTViews.ListViews.QT_invoices_view import QTInvoicesViewH
from QTViews.ListViews.QT_payments_view import QTPaymentsViewH
from QTViews.ListViews.QT_productions_view import QTProductionsViewH
from QTViews.ListViews.QT_refunds_view import QTRefundsViewH
from QTViews.ListViews.QT_salaries_view import QTSalariesViewH
from QTViews.ListViews.QT_suppliers_view import QTSuppliersViewH

if TYPE_CHECKING:
    from App_context import AppContext


# (label visualizzata, classe della list view).
# La classe viene letta per ricavare ``LIST_VIEW_KEY``,
# ``TIME_WINDOWS`` e ``DEFAULT_WINDOW_INDEX``.
_LIST_VIEW_REGISTRY = [
    ("Clienti", QTClientsViewH),
    ("Fornitori", QTSuppliersViewH),
    ("Produzioni", QTProductionsViewH),
    ("Fatture", QTInvoicesViewH),
    ("Pagamenti", QTPaymentsViewH),
    ("Rimborsi", QTRefundsViewH),
    ("Spese", QTExpensesViewH),
    ("Salario", QTSalariesViewH),
]


def _resolve_tab_names(parent) -> list[str]:
    """Legge i nomi delle tab dal QTabWidget della mainview se disponibile."""
    tab_widget = getattr(parent, "tabview", None) if parent is not None else None
    if tab_widget is not None:
        return [tab_widget.tabText(i) for i in range(tab_widget.count())]
    try:
        from QTViews.QT_main_view import QTMainWindowH
        return list(QTMainWindowH._tab_names())
    except Exception:
        return []


def _section_frame(object_name: str) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName(object_name)
    frame.setStyleSheet(
        f"#{object_name} {{ border: 2px solid palette(highlight); border-radius: 6px; }}"
    )
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 10, 14, 14)
    layout.setSpacing(8)
    return frame, layout


def _section_title(text: str, layout: QVBoxLayout) -> None:
    lbl = QLabel(text)
    f = lbl.font()
    f.setBold(True)
    f.setPointSize(13)
    lbl.setFont(f)
    layout.addWidget(lbl)


class QTStartupTabDialog(QDialog):
    """Dialog per scegliere la tab di avvio dell'app."""

    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.manager = app_context.gui_preferences_manager

        self.setWindowTitle("Tab di avvio")
        self.resize(460, 260)
        self.setModal(True)

        self._tab_combo: QComboBox | None = None
        self._tab_names: list[str] = _resolve_tab_names(parent)

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Tab di avvio")
        f = title.font()
        f.setPointSize(15)
        f.setBold(True)
        title.setFont(f)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("padding: 12px;")
        root.addWidget(title)

        frame, layout = _section_frame("StartupTabFrame")
        _section_title("Tab di avvio", layout)

        hint = QLabel("La tab selezionata sara' quella attiva all'apertura dell'app.")
        hint.setStyleSheet("color: palette(mid);")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)

        self._tab_combo = QComboBox()
        if self._tab_names:
            self._tab_combo.addItems(self._tab_names)
        else:
            self._tab_combo.setEnabled(False)

        try:
            current = self.manager.get_startup_tab()
        except Exception:
            current = ""
        idx = self._tab_combo.findText(current)
        if idx >= 0:
            self._tab_combo.setCurrentIndex(idx)

        form.addRow("Tab di avvio:", self._tab_combo)
        layout.addLayout(form)

        root.addWidget(frame)
        root.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _on_save(self):
        try:
            if self._tab_combo is not None and self._tab_combo.isEnabled():
                selected = self._tab_combo.currentText().strip()
                if selected:
                    self.manager.set_startup_tab(selected)
        except Exception as exc:
            print(f"[gui_preferences] errore salvataggio tab avvio: {exc}")
        self.accept()


class QTListViewFiltersDialog(QDialog):
    """Dialog per personalizzare la finestra temporale di default per ciascuna list view."""

    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.manager = app_context.gui_preferences_manager

        self.setWindowTitle("Filtri temporali liste")
        self.resize(520, 480)
        self.setModal(True)

        self._window_combos: dict[str, QComboBox] = {}

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Filtri temporali liste")
        f = title.font()
        f.setPointSize(15)
        f.setBold(True)
        title.setFont(f)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("padding: 12px;")
        root.addWidget(title)

        intro = QLabel(
            "Per ogni elenco scegli la finestra temporale preselezionata "
            "all'apertura. Le scelte vengono salvate in ``gui_preferences.json`` "
            "e applicate alla prossima apertura delle view interessate."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("padding: 0 16px 8px 16px; color: palette(text);")
        root.addWidget(intro)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root.addWidget(scroll, stretch=1)

        container = QWidget()
        scroll.setWidget(container)
        body = QVBoxLayout(container)
        body.setContentsMargins(16, 8, 16, 16)
        body.setSpacing(14)

        body.addWidget(self._build_list_views_section())
        body.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _build_list_views_section(self) -> QFrame:
        frame, layout = _section_frame("ListViewFiltersFrame")
        _section_title("\"Mostra ultimi\" per list view", layout)

        hint = QLabel(
            "Il selettore in alto dentro la view resta modificabile come prima."
        )
        hint.setStyleSheet("color: palette(mid);")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)

        for display_label, view_cls in _LIST_VIEW_REGISTRY:
            key = getattr(view_cls, "LIST_VIEW_KEY", None)
            time_windows = getattr(view_cls, "TIME_WINDOWS", ())
            if not key or not time_windows:
                continue
            fallback_idx = int(getattr(view_cls, "DEFAULT_WINDOW_INDEX", 0))

            combo = QComboBox()
            for w_label, _ in time_windows:
                combo.addItem(w_label)
            try:
                current_idx = self.manager.get_list_view_window_index(key, default=fallback_idx)
            except Exception:
                current_idx = fallback_idx
            if not (0 <= current_idx < combo.count()):
                current_idx = fallback_idx
            combo.setCurrentIndex(current_idx)

            self._window_combos[key] = combo
            form.addRow(f"{display_label}:", combo)

        layout.addLayout(form)
        return frame

    def _on_save(self):
        try:
            for key, combo in self._window_combos.items():
                self.manager.set_list_view_window_index(key, combo.currentIndex())
        except Exception as exc:
            print(f"[gui_preferences] errore salvataggio filtri: {exc}")
        self.accept()


# Kept for any leftover import that may reference it; can be removed later.
QTGuiPreferencesDialog = QTListViewFiltersDialog

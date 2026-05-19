"""
View "Report <anno>", versione Qt.

Replica ``Views/Report_view.py`` (legacy CustomTkinter):
- contenitore con un ``QTabWidget`` interno che espone due sottotab,
  "Dati Mensili" e "Analisi Annuale";
- come la legacy, le sottoview vengono istanziate "lazy" al primo
  switch su una tab: cosi' all'apertura della view principale non
  carichiamo matplotlib (la sezione annuale e' costosa);
- al cambio di sottotab la precedente viene distrutta (incluse le
  figure matplotlib), esattamente come fa la legacy via
  ``_destroy_subtab``.

Espone un ``refresh()`` che delega alla sottoview attualmente visibile
(usato dal bottone "Aggiorna" della main view).
"""

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from QTViews.QT_monthly_report_view import QTMonthlyReportViewH

if TYPE_CHECKING:
    from App_context import AppContext


SUBTAB_MONTHLY = "Dati Mensili"
SUBTAB_ANNUAL = "Analisi Annuale"


class QTReportViewH(QWidget):
    """Container per le sottoview del report (mensile / annuale)."""

    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context

        # Sottoview correntemente caricate (chiave = nome sottotab).
        self._subviews: dict[str, QWidget] = {}
        self._current_tab: str | None = None

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(5, 5, 5, 5)
        root.setSpacing(0)

        self.tabview = QTabWidget()
        self.tabview.setObjectName("ReportSubTabView")
        self.tabview.setStyleSheet(
            "#ReportSubTabView QTabBar::tab {"
            " font-weight: bold; padding: 8px 16px;"
            "}"
        )

        # Le tab vengono create con un placeholder vuoto: la sottoview
        # vera viene istanziata al primo switch.
        self._monthly_page = QWidget()
        QVBoxLayout(self._monthly_page).setContentsMargins(0, 0, 0, 0)
        self.tabview.addTab(self._monthly_page, SUBTAB_MONTHLY)

        self._annual_page = QWidget()
        QVBoxLayout(self._annual_page).setContentsMargins(0, 0, 0, 0)
        self.tabview.addTab(self._annual_page, SUBTAB_ANNUAL)

        self.tabview.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self.tabview)

        # Carica la sottotab di default (la prima).
        self._on_tab_changed(0)

    # ------------------------------------------------------------------
    # Lifecycle sottotab
    # ------------------------------------------------------------------

    def _on_tab_changed(self, index: int):
        tab_name = self.tabview.tabText(index)
        previous = self._current_tab
        self._current_tab = tab_name

        if previous and previous != tab_name:
            self._destroy_subtab(previous)
        self._load_subtab(tab_name)

    def _load_subtab(self, tab_name: str):
        if tab_name in self._subviews:
            return

        if tab_name == SUBTAB_MONTHLY:
            page = self._monthly_page
            instance = QTMonthlyReportViewH(app_context=self.app_context, parent=page)
        elif tab_name == SUBTAB_ANNUAL:
            # Import locale: matplotlib viene importato solo se l'utente
            # apre davvero la sottotab annuale.
            from QTViews.QT_annual_report_charts_view import (
                QTAnnualReportChartsViewH,
            )

            page = self._annual_page
            instance = QTAnnualReportChartsViewH(app_context=self.app_context, parent=page)
        else:
            return

        page.layout().addWidget(instance)
        self._subviews[tab_name] = instance

    def _destroy_subtab(self, tab_name: str):
        instance = self._subviews.pop(tab_name, None)
        if instance is None:
            return
        try:
            if hasattr(instance, "cleanup"):
                instance.cleanup()
        except Exception as exc:
            print(f"Errore nel cleanup della sottoview '{tab_name}': {exc}")
        try:
            instance.setParent(None)
            instance.deleteLater()
        except Exception as exc:
            print(f"Errore nel distruggere la sottoview '{tab_name}': {exc}")

    # ------------------------------------------------------------------
    # API esterna
    # ------------------------------------------------------------------

    def refresh(self):
        if not self._current_tab:
            return
        instance = self._subviews.get(self._current_tab)
        if instance is None:
            return
        if hasattr(instance, "refresh"):
            instance.refresh()

    def cleanup(self):
        for tab_name in list(self._subviews.keys()):
            self._destroy_subtab(tab_name)

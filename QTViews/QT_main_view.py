from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMainWindow, QStackedWidget

from QTViews.Details.QT_invoice_detail_view import QTInvoiceDetailViewH
from QTViews.ListViews.QT_invoices_view import QTInvoicesViewH

if TYPE_CHECKING:
    from App_context import AppContext


class QTMainWindow(QMainWindow):
    """
    Main window QT minimale per il test prestazionale.

    Contiene la list view delle fatture e il dettaglio fattura, gestiti
    via QStackedWidget. Quando l'utente apre una fattura dalla list view
    si naviga sul dettaglio; il bottone "Elenco Fatture" del dettaglio
    riporta alla lista.
    """

    def __init__(self, app_context: "AppContext", initial_invoice_id=None):
        super().__init__()

        self.app_context = app_context

        self.setWindowTitle("Gestionale Willow — QT (test prestazionale)")
        self.resize(1400, 800)

        self.stack = QStackedWidget(self)
        self.setCentralWidget(self.stack)

        self.invoices_view = QTInvoicesViewH(
            app_context=app_context,
            initial_invoice_id=initial_invoice_id,
            on_open_detail=self._open_invoice_detail,
            parent=self,
        )
        self.stack.addWidget(self.invoices_view)

        self.invoice_detail_view = None

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
        self.stack.setCurrentWidget(self.invoices_view)
        if self.invoice_detail_view is not None:
            self.stack.removeWidget(self.invoice_detail_view)
            self.invoice_detail_view.deleteLater()
            self.invoice_detail_view = None

    def closeEvent(self, event):
        scheduler = getattr(self.app_context, "backup_scheduler", None)
        if scheduler is not None:
            try:
                scheduler.stop()
            except Exception as exc:
                print(f"Errore nello stop del backup scheduler: {exc}")
        super().closeEvent(event)

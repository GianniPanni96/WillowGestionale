"""
Entry-point della UI Qt (PySide6).

Esegue il bootstrap condiviso (config + AppContext + backup scheduler) e
avvia la QTMainWindow. La logica di costruzione del context e' identica a
quella usata dalla entry-point Tkinter, per garantire che le due UI
operino sullo stesso stato.
"""

import sys

from Main_bootstrap import build_app_context

# ID della fattura su cui posizionarsi all'avvio (utile per i test
# prestazionali della tab "Fatture"). Mettere a None per partire dalla
# lista non selezionata.
QT_INITIAL_INVOICE_ID = 2


def main():
    app_context, scheduler = build_app_context()

    from PySide6.QtWidgets import QApplication

    from QTViews.QT_main_view import QTMainWindow
    from QTViews.QT_palette_Manager import QTPaletteManager

    qt_app = QApplication.instance() or QApplication(sys.argv)
    qt_app.palette_manager = QTPaletteManager.install(qt_app)

    window = QTMainWindow(
        app_context=app_context,
        initial_invoice_id=QT_INITIAL_INVOICE_ID,
    )
    window.show()

    try:
        exit_code = qt_app.exec()
    except KeyboardInterrupt:
        print("Interruzione manuale. Fermando il backup...")
        scheduler.stop()
        raise

    scheduler.stop()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

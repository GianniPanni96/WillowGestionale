"""
Entry-point della UI Qt (PySide6).

Esegue il bootstrap condiviso (config + AppContext + backup scheduler),
poi gestisce l'autenticazione obbligatoria prima di mostrare la
QTMainWindow:

- se nel DB non esistono utenti, lancia il wizard di onboarding che
  crea il primo conto + il primo utente con password (anche la chiave
  crypto per-utente nasce qui);
- altrimenti mostra una QTLoginDialog "mandatory" (X/ESC disabilitati)
  che sblocca la crypto session dell'utente selezionato.

La main window e' istanziata e mostrata solo dopo che l'utente e'
loggato; questo garantisce che la crypto session sia attiva e che la
UI rifletta lo stato di login fin dal primo frame.
"""

import sys

# matplotlib.pyplot va importato qui (prima di PySide6) perche'
# trascina dateutil -> six in sys.modules. Senza questo, l'hook di
# shibokensupport di PySide6 intercetta il primo import di six durante
# il caricamento di matplotlib.dates e crasha su
# ``_SixMetaPathImporter._path`` mancante.
import matplotlib.pyplot  # noqa: F401

from Main_bootstrap import build_app_context

# ID della fattura su cui posizionarsi all'avvio (utile per i test
# prestazionali della tab "Fatture"). Mettere a None per partire dalla
# lista non selezionata.
QT_INITIAL_INVOICE_ID = 2


def _force_authentication(app_context) -> tuple[bool, int]:
    """Garantisce che ci sia un utente loggato prima di entrare in app.

    Returns:
        (success, user_id). Se ``success`` e' False l'app deve terminare.
    """
    from PySide6.QtWidgets import QMessageBox

    from QTViews.MenuWindows.QT_login_dialog import QTLoginDialog
    from QTViews.MenuWindows.QT_onboarding_dialog import QTOnboardingDialog

    users = app_context.user_query_service.retrieve_users_map_list() or []

    if not users:
        onboarding = QTOnboardingDialog(app_context=app_context)
        if onboarding.exec() != QTOnboardingDialog.Accepted or onboarding.created_user_id is None:
            QMessageBox.critical(None, "Avvio interrotto", "Configurazione iniziale annullata.")
            return False, -1
        # Onboarding ha creato l'utente e impostato la password, ma non
        # ha ancora sbloccato la crypto session: facciamo un login
        # programmatico ora cosi' la sessione e' attiva.
        success, _msg, user_id = app_context.user_auth_service.check_password_for_login(
            onboarding.created_user_name,
            onboarding.created_user_password,
        )
        if not success:
            QMessageBox.critical(None, "Errore", "Impossibile autenticare il nuovo utente.")
            return False, -1
        return True, user_id

    # Esistono utenti: login forzato.
    login = QTLoginDialog(app_context=app_context, mandatory=True)
    if login.exec() != QTLoginDialog.Accepted or not login.success:
        QMessageBox.critical(None, "Avvio interrotto", "Login obbligatorio non completato.")
        return False, -1
    return True, login.user_id


def main():
    app_context, scheduler = build_app_context()

    from PySide6.QtWidgets import QApplication

    from QTViews.QT_main_view import QTMainWindow
    from QTViews.QT_palette_Manager import QTPaletteManager
    from Utils.View_utils import ViewUtils

    qt_app = QApplication.instance() or QApplication(sys.argv)
    qt_app.palette_manager = QTPaletteManager.install(qt_app)

    ok, user_id = _force_authentication(app_context)
    if not ok:
        scheduler.stop()
        sys.exit(1)

    window = QTMainWindow(
        app_context=app_context,
        initial_invoice_id=QT_INITIAL_INVOICE_ID,
    )
    # Allinea lo stato di login della main window al risultato del
    # forced auth, cosi' la UI parte gia' "loggata" senza richiedere
    # un secondo click sul bottone Login.
    window.login_status = True
    window.logged_user_id = user_id
    # Aggiorna testo bottone login + icona utente nel corner della
    # main window (altrimenti l'icona di default resta finche' non si
    # cambia tab).
    window._toggle_login_widgets()
    app_context.event_bus.publish(
        ViewUtils.EventBusKeys.LOGIN_STATUS_CHANGED.value,
        {"login_status": True, "logged_user_id": user_id},
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

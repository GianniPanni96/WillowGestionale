"""
Entry-point della UI Qt (PySide6).

Esegue il bootstrap condiviso (config + AppContext + backup scheduler),
poi gestisce l'autenticazione obbligatoria prima di mostrare la
QTMainWindow. Sequenza al boot:

1. Se non esiste l'amministratore di sistema (tabella ``admin`` vuota),
   forza la creazione dell'admin tramite ``QTAdminCreateDialog``.
2. Se nel DB non esistono utenti, lancia l'onboarding che crea il primo
   conto + il primo utente con password.
3. Se esistono utenti ma nessuno ha password (installazione esistente
   appena migrata), apre il bootstrap dialog per impostare la prima
   password a un utente — oppure permette di proseguire come admin.
4. Altrimenti mostra la login dialog mandatory, da cui si puo' anche
   accedere come admin.
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


def _ensure_admin_exists(app_context) -> bool:
    """Se la tabella admin e' vuota, forza la creazione del singolo admin.
    Returns True se ora un admin esiste (creato adesso o gia' presente).
    """
    if app_context.admin_query_service.admin_exists():
        return True

    from PySide6.QtWidgets import QMessageBox
    from QTViews.MenuWindows.QT_admin_create_dialog import QTAdminCreateDialog

    dialog = QTAdminCreateDialog(app_context=app_context)
    if dialog.exec() != QTAdminCreateDialog.Accepted or not dialog.created:
        QMessageBox.critical(
            None,
            "Avvio interrotto",
            "Creazione amministratore annullata. L'app non puo' partire.",
        )
        return False
    return True


def _users_have_any_password(app_context) -> bool:
    from Gestionale_Enums import DBUsersColumns
    users = app_context.user_query_service.retrieve_users_map_list() or []
    return any(u.get(DBUsersColumns.PASSWORD_LOGIN.value) for u in users)


def _force_authentication(app_context) -> tuple[bool, int, bool]:
    """Garantisce che ci sia un utente o un admin loggato prima di entrare.

    Returns:
        (success, user_id, is_admin). Se ``success`` e' False l'app
        deve terminare. ``user_id`` vale -1 quando si entra come admin.
    """
    from PySide6.QtWidgets import QMessageBox

    from QTViews.MenuWindows.QT_admin_login_dialog import QTAdminLoginDialog
    from QTViews.MenuWindows.QT_first_password_setup_dialog import QTFirstPasswordSetupDialog
    from QTViews.MenuWindows.QT_login_dialog import QTLoginDialog
    from QTViews.MenuWindows.QT_onboarding_dialog import QTOnboardingDialog

    users = app_context.user_query_service.retrieve_users_map_list() or []

    # Caso 1: DB vuoto di utenti -> onboarding.
    if not users:
        onboarding = QTOnboardingDialog(app_context=app_context)
        if onboarding.exec() != QTOnboardingDialog.Accepted or onboarding.created_user_id is None:
            QMessageBox.critical(None, "Avvio interrotto", "Configurazione iniziale annullata.")
            return False, -1, False
        success, _msg, user_id = app_context.user_auth_service.check_password_for_login(
            onboarding.created_user_name,
            onboarding.created_user_password,
        )
        if not success:
            QMessageBox.critical(None, "Errore", "Impossibile autenticare il nuovo utente.")
            return False, -1, False
        return True, user_id, False

    # Caso 2: utenti esistenti ma nessuno con password -> bootstrap.
    if not _users_have_any_password(app_context):
        boot = QTFirstPasswordSetupDialog(app_context=app_context)
        boot.exec()
        if boot.success and boot.target_user_id is not None:
            # Setup password riuscito: login programmatico come quell'utente.
            ok, _msg, user_id = app_context.user_auth_service.check_password_for_login(
                boot.target_user_name,
                boot.target_password,
            )
            if ok:
                return True, user_id, False
            QMessageBox.critical(None, "Errore", "Impossibile autenticare l'utente appena impostato.")
            return False, -1, False
        # Skip: l'utente ha scelto di proseguire come admin.
        admin_login = QTAdminLoginDialog(app_context=app_context, mandatory=True)
        if admin_login.exec() != QTAdminLoginDialog.Accepted or not admin_login.success:
            QMessageBox.critical(None, "Avvio interrotto", "Login admin obbligatorio non completato.")
            return False, -1, False
        return True, -1, True

    # Caso 3: scenario normale -> login utente (con opzione admin).
    login = QTLoginDialog(app_context=app_context, mandatory=True)
    if login.exec() != QTLoginDialog.Accepted or not login.success:
        QMessageBox.critical(None, "Avvio interrotto", "Login obbligatorio non completato.")
        return False, -1, False
    return True, login.user_id, bool(getattr(login, "logged_as_admin", False))


def main():
    app_context, scheduler = build_app_context()

    from PySide6.QtWidgets import QApplication

    from QTViews.QT_main_view import QTMainWindow
    from QTViews.QT_palette_Manager import QTPaletteManager
    from Utils.View_utils import ViewUtils

    qt_app = QApplication.instance() or QApplication(sys.argv)
    qt_app.palette_manager = QTPaletteManager.install(qt_app)

    # Step preliminare: assicura che esista l'admin di sistema.
    if not _ensure_admin_exists(app_context):
        scheduler.stop()
        sys.exit(1)

    ok, user_id, is_admin = _force_authentication(app_context)
    if not ok:
        scheduler.stop()
        sys.exit(1)

    window = QTMainWindow(
        app_context=app_context,
        initial_invoice_id=QT_INITIAL_INVOICE_ID,
    )
    window.login_status = True
    window.logged_user_id = user_id
    window.is_admin = is_admin
    window._toggle_login_widgets()
    app_context.event_bus.publish(
        ViewUtils.EventBusKeys.LOGIN_STATUS_CHANGED.value,
        {"login_status": True, "logged_user_id": user_id, "is_admin": is_admin},
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

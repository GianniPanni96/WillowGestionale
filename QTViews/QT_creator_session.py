"""
Sessione di creazione condivisa per le creator view del gestionale.

Le creator view (nuova fattura, nuovo pagamento, nuovo cliente, …) erano
aperte in modalità application-modal via ``QDialog.exec()``: questo bloccava
l'intera interfaccia sottostante finché la finestra restava aperta.

Per consentire la navigazione tra le tab, lo scorrimento delle liste e
l'apertura dei dettagli mentre una creator view è aperta — senza però
permettere di alterare lo stato dei dati con azioni potenzialmente
pericolose — le creator view vengono ora mostrate in modalità NON modale e
coordinate da un'unica ``CreatorSession``:

- è ammessa una sola creator view aperta alla volta;
- mentre una creator view è aperta, la barra dei menu in alto viene
  disabilitata;
- alla chiusura della creator view (conferma, annullamento o chiusura
  finestra) lo stato viene ripristinato automaticamente.
"""

from PySide6.QtWidgets import QMessageBox


class CreatorSession:
    """Coordina l'apertura non modale delle creator view.

    Tiene il riferimento alla creator attualmente aperta (mantenendola in
    vita, dato che è non modale) e abilita/disabilita la barra dei menu.
    """

    def __init__(self):
        self._active = None
        self._menu_bar = None

    def bind_menu_bar(self, menu_bar):
        """Registra la barra dei menu da disabilitare durante una sessione."""
        self._menu_bar = menu_bar

    def is_active(self) -> bool:
        return self._active is not None

    def begin(self, dialog) -> bool:
        """Mostra ``dialog`` in modalità non modale e ne prende il controllo.

        Ritorna False se un'altra creator view è già aperta (in tal caso il
        dialog NON viene mostrato).
        """
        if self._active is not None:
            return False

        self._active = dialog
        self._set_menu_enabled(False)

        dialog.setModal(False)
        dialog.finished.connect(self._on_finished)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        return True

    def _on_finished(self, _result=None):
        dialog = self._active
        self._active = None
        self._set_menu_enabled(True)
        # La creator era tenuta in vita solo da questa sessione: ora che è
        # chiusa può essere distrutta.
        if dialog is not None:
            dialog.deleteLater()

    def _set_menu_enabled(self, enabled: bool):
        if self._menu_bar is not None:
            self._menu_bar.setEnabled(enabled)


def launch_creator(parent, app_context, dialog) -> bool:
    """Apre ``dialog`` come creator view non modale tramite la CreatorSession.

    - Se un'altra creator view è già aperta, avvisa l'utente e non apre nulla.
    - Se la sessione non è disponibile (contesti senza main window), ricade
      sul vecchio comportamento modale ``exec()``.

    Ritorna True se la creator è stata aperta (o eseguita in fallback).
    """
    session = getattr(app_context, "creator_session", None)
    if session is None:
        dialog.exec()
        return True

    if session.is_active():
        QMessageBox.information(
            parent,
            "Operazione non disponibile",
            "È già aperta una finestra di creazione.\n"
            "Chiudila prima di aprirne un'altra.",
        )
        dialog.deleteLater()
        return False

    return session.begin(dialog)

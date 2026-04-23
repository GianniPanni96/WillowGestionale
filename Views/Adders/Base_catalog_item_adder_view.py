import customtkinter as ctk

from App_context import AppContext
from Utils.Controller_utils import ControllerUtils
from Views.View_utils import ViewUtils


class BaseCatalogItemAdderView(ctk.CTkToplevel):
    """
    Modale base per aggiungere una nuova voce a una lista di configurazione.

    Le classi figlie dichiarano solo i metadati statici della lista da
    manipolare, mentre questa classe gestisce apertura, salvataggio e chiusura.
    """

    SECTION_NAME = None
    TITLE = "Aggiungi nuova voce"
    DESCRIPTION = "Inserisci il nuovo valore"
    BUTTON_TEXT = "Salva"
    GEOMETRY = "400x300"

    def __init__(self, parent, app_context: AppContext, on_item_created=None, on_close=None):
        super().__init__(parent)

        self.app_context = app_context
        self.config_manager = app_context.config_manager
        self.catalogo_elenchi = app_context.catalogo_elenchi
        self.on_item_created = on_item_created
        self.on_close = on_close

        self.title(self.TITLE)
        self.geometry(self.GEOMETRY)
        self.lift()
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.container = ctk.CTkFrame(self)
        self.container.pack(fill="both", expand=True)

        ctk.CTkLabel(self.container, text=self.DESCRIPTION).pack(padx=10, pady=(25, 0))

        self.value_entry = ctk.CTkEntry(self.container)
        self.value_entry.pack(padx=10, pady=5, fill="x", expand=True)

        self.save_button = ctk.CTkButton(
            self.container,
            text=self.BUTTON_TEXT,
            command=self.save_item
        )
        self.save_button.pack(padx=10, pady=(15, 10))

    def save_item(self):
        """Salva il nuovo valore nella configurazione condivisa."""
        new_value = self.value_entry.get().strip()
        if not new_value:
            ViewUtils.show_error_popup(self, "Errore", "Il valore non puo essere vuoto")
            return

        new_key = ControllerUtils.normalize_string_for_key(new_value)
        try:
            self.config_manager.update_list_field(self.SECTION_NAME, new_key, new_value, "update")
        except Exception as exc:
            ViewUtils.show_error_popup(self, "Errore", str(exc))
            return

        if self.on_item_created:
            self.on_item_created(new_key, new_value)

        self._on_close()

    def _on_close(self):
        """Chiude il toplevel rilasciando in sicurezza l'eventuale grab."""
        try:
            self.grab_release()
        except Exception:
            pass

        if self.on_close:
            self.on_close()

        self.destroy()

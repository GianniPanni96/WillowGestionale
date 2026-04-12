import customtkinter as ctk

from Controllers import ControllerUtils
from Views.View_utils import ViewUtils

from App_context import AppContext


class BusinessSectorCreateView(ctk.CTkToplevel):
    """
    Finestra modale dedicata alla creazione di un nuovo settore di business.

    La classe centralizza l'intero flusso di aggiunta del settore:
    raccoglie l'input utente, valida il valore, aggiorna la configurazione
    persistente, sincronizza il catalogo in memoria e notifica il chiamante.
    """

    SECTION_NAME = "clients_business_sectors"

    def __init__(self, parent, app_context: AppContext, on_sector_created=None, on_close=None):
        """
        Inizializza il toplevel e costruisce i widget del form.

        Args:
            parent: widget Tk padre della finestra.
            app_context: contesto applicativo condiviso.
            on_sector_created: callback opzionale invocata dopo il salvataggio.
            on_close: callback opzionale invocata alla chiusura della finestra.
        """
        super().__init__(parent)

        self.app_context = app_context
        self.config_manager = app_context.config_manager
        self.catalogo_elenchi = app_context.catalogo_elenchi

        self.on_sector_created = on_sector_created
        self.on_close = on_close

        self.title("Aggiungi un nuovo settore di business")
        self.geometry("400x300")
        self.lift()
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.content_frame = ctk.CTkFrame(self)
        self.content_frame.pack(fill="both", expand=True)

        ctk.CTkLabel(
            self.content_frame,
            text="Aggiungi un settore di business alla lista\nsepara parole diverse solo tramite spazio"
        ).pack(padx=10, pady=(25, 0))

        self.sector_entry = ctk.CTkEntry(self.content_frame)
        self.sector_entry.pack(padx=10, pady=5, fill="x", expand=True)
        self.sector_entry.focus_set()

        self.error_label = ctk.CTkLabel(self.content_frame, text="")
        self.error_label.pack(padx=10, pady=(0, 10))

        ctk.CTkButton(
            self.content_frame,
            text="Aggiungi settore",
            command=self.save_business_sector
        ).pack(padx=10, pady=(15, 10))

    def save_business_sector(self):
        """
        Valida l'input e salva il nuovo settore nella configurazione.

        In caso di successo:
        - aggiorna il catalogo condiviso in memoria;
        - invoca l'eventuale callback del chiamante;
        - chiude la finestra.
        """
        new_sector = self.sector_entry.get().strip()
        if not new_sector:
            self.error_label.configure(text="Inserisci un nome valido.", text_color="#e8e5dc")
            return

        sector_key = ControllerUtils.normalize_string_for_key(new_sector)
        sector_dict = dict(self.catalogo_elenchi[self.SECTION_NAME])

        if sector_key in sector_dict:
            ViewUtils.show_error_popup(self, "Errore", "Questo settore esiste gia nella lista.")
            return

        try:
            self.config_manager.update_list_field(
                self.SECTION_NAME,
                sector_key,
                new_sector,
                "update"
            )
        except Exception as exc:
            ViewUtils.show_error_popup(
                self,
                "Errore",
                f"Impossibile aggiungere il nuovo settore: {str(exc)}"
            )
            return

        self._refresh_catalog_lists(sector_key, new_sector)

        if self.on_sector_created:
            self.on_sector_created(sector_key, new_sector)

        self._on_close()

    def _refresh_catalog_lists(self, sector_key, sector_value):
        """
        Aggiorna il catalogo in memoria mantenendo il trigger ``ADD_SECTOR`` in coda.

        ``ConfigManager`` salva il file di configurazione, ma le view aperte
        leggono anche la struttura condivisa in ``app_context.catalogo_elenchi``.
        Per questo la lista viene aggiornata anche in memoria.
        """
        sectors = self.catalogo_elenchi[self.SECTION_NAME]
        trigger_item = None

        for item in sectors[:]:
            if item[0] == sector_key:
                sectors.remove(item)

        if sectors and sectors[-1][0] == "ADD_SECTOR":
            trigger_item = sectors.pop()

        sectors.insert(0, (sector_key, sector_value))

        if trigger_item is not None:
            sectors.append(trigger_item)

    def _on_close(self):
        """
        Chiude il toplevel rilasciando in sicurezza il grab modale.

        Il ``grab_release`` e' protetto per evitare errori se il grab e' gia'
        stato rilasciato da Tk.
        """
        try:
            self.grab_release()
        except Exception:
            pass

        if self.on_close:
            self.on_close()

        self.destroy()

import customtkinter as ctk

from Controllers import ControllerUtils
from Views.View_utils import ViewUtils

from App_context import AppContext


class BusinessSectorCreateView(ctk.CTkToplevel):
    SECTION_NAME = "clients_business_sectors"

    def __init__(self, parent, app_context: AppContext, on_sector_created=None, on_close=None):
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
        try:
            self.grab_release()
        except Exception:
            pass

        if self.on_close:
            self.on_close()

        self.destroy()

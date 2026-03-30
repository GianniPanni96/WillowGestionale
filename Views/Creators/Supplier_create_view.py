import customtkinter as ctk

from Model import DBSuppliersColumns
from Views.View_utils import CatalogFilterableComboBox, FilterableComboBox, ViewUtils
from Views.Adders.Business_sector_adder_view import BusinessSectorAdderView

from App_context import AppContext


class SupplierCreateView(ctk.CTkToplevel):
    """
    Finestra modale per la creazione di un nuovo fornitore.

    La classe incapsula l'intero workflow di inserimento:
    - costruzione del form;
    - validazione minima lato view;
    - raccolta dei dati dai widget;
    - invocazione del controller di salvataggio;
    - eventuale creazione dinamica di un nuovo settore di business.
    """

    def __init__(self, parent, app_context: AppContext, on_supplier_created=None, on_close=None):
        """
        Inizializza la creator view del fornitore.

        Args:
            parent: widget padre.
            app_context: contesto applicativo condiviso.
            on_supplier_created: callback opzionale invocata dopo il salvataggio.
            on_close: callback opzionale invocata alla chiusura del toplevel.
        """
        super().__init__(parent)

        self.app_context = app_context
        self.supplier_controller = app_context.supplier_controller
        self.catalogo_elenchi = app_context.catalogo_elenchi

        self.on_supplier_created = on_supplier_created
        self.on_close = on_close

        self.entry_fields = {
            DBSuppliersColumns.NAME.value: ctk.CTkEntry,
            DBSuppliersColumns.PARTITA_IVA.value: ctk.CTkEntry,
            DBSuppliersColumns.SEDE.value: ctk.CTkEntry,
            DBSuppliersColumns.CONTATTO.value: ctk.CTkEntry,
            DBSuppliersColumns.CATEGORIA.value: CatalogFilterableComboBox,
            DBSuppliersColumns.NOTE.value: ctk.CTkTextbox,
        }
        self.error_fields = {
            DBSuppliersColumns.NAME.value: ctk.CTkLabel,
        }
        self.field_labels = {}
        self.supplier_widgets = {}
        self.error_labels = {}
        self.business_sector_adder_view = None

        self.title("Aggiungi Nuovo Fornitore")
        self.geometry("400x700")
        self.lift()
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.scrollable_frame = ctk.CTkScrollableFrame(self)
        self.scrollable_frame.pack(fill="both", expand=True)

        self._build_form()
        self._bind_validations()

    def _build_form(self):
        """Costruisce dinamicamente tutti i campi del form fornitore."""
        for i, (label_text, widget_class) in enumerate(self.entry_fields.items()):
            label = ctk.CTkLabel(self.scrollable_frame, text=label_text)
            label.pack(pady=5 if i == 0 else (35, 0))
            self.field_labels[label_text] = label

            widget = self._create_field_widget(label_text, widget_class)
            widget.pack(pady=5, padx=10, fill="x", expand=True)

            if self.error_fields.get(label_text) is not None:
                error_label = ctk.CTkLabel(self.scrollable_frame, text="")
                error_label.pack(pady=(0, 15))
                self.error_labels[label_text] = error_label

            self.supplier_widgets[label_text] = widget

        self.save_button = ctk.CTkButton(
            self.scrollable_frame,
            text="Salva Fornitore",
            command=self.save_supplier_data
        )
        self.save_button.pack(pady=(35, 15))

    def _create_field_widget(self, label_text, widget_class):
        """Crea il widget corretto per il campo richiesto."""
        if label_text == DBSuppliersColumns.CATEGORIA.value:
            widget = widget_class(
                parent=self.scrollable_frame,
                placeholder="Cerca",
                autofill=True,
                values=self._get_business_sector_values(),
                add_button_text="Aggiungi un settore",
                add_button_command=self.open_add_business_sector
            )
            default_value = dict(self.catalogo_elenchi["clients_business_sectors"]).get("ENERGY")
            if default_value:
                widget.set_value(default_value)
            return widget

        return widget_class(self.scrollable_frame)

    def _bind_validations(self):
        """Collega le validazioni lato interfaccia ai campi principali."""
        self.supplier_widgets[DBSuppliersColumns.NAME.value].bind(
            "<FocusOut>",
            lambda event: ViewUtils.validate_entry(
                self.supplier_widgets[DBSuppliersColumns.NAME.value],
                lambda val: val.strip() != "",
                self.error_labels[DBSuppliersColumns.NAME.value],
                "Il nome non puo essere vuoto."
            )
        )

    def _collect_supplier_data(self):
        """Estrae i dati del form in un dizionario compatibile col controller."""
        supplier_data = {}

        for label_text, widget in self.supplier_widgets.items():
            if isinstance(widget, (ctk.CTkEntry, ctk.CTkOptionMenu)):
                supplier_data[label_text] = widget.get().strip()
            elif isinstance(widget, ctk.CTkTextbox):
                supplier_data[label_text] = widget.get("1.0", "end-1c").strip()
            elif isinstance(widget, FilterableComboBox):
                supplier_data[label_text] = widget.get_value()

        return supplier_data

    def save_supplier_data(self):
        """
        Valida e salva il nuovo fornitore tramite ``SupplierController``.

        In caso di successo notifica il chiamante con ``on_supplier_created`` e
        chiude la finestra; in caso di errore mostra un popup esplicativo.
        """
        supplier_data = self._collect_supplier_data()
        success, message = self.supplier_controller.save_supplier(supplier_data)

        if not success:
            ViewUtils.show_error_popup(self, "ERRORE", message)
            return

        supplier_row = self.supplier_controller.retrieve_last_supplier_insert_map()
        supplier_id = supplier_row[DBSuppliersColumns.ID.value] if supplier_row else None

        if self.on_supplier_created:
            self.on_supplier_created(supplier_id, supplier_data)

        self._on_close()

    def _get_business_sector_values(self):
        return [
            value for key, value in self.catalogo_elenchi["clients_business_sectors"]
            if key != "ADD_SECTOR"
        ]

    def open_add_business_sector(self):
        """Apre la finestra modale per creare un nuovo settore, una sola volta."""
        if self.business_sector_adder_view is not None and self.business_sector_adder_view.winfo_exists():
            self.business_sector_adder_view.focus()
            self.business_sector_adder_view.lift()
            return

        self.business_sector_adder_view = BusinessSectorAdderView(
            parent=self,
            app_context=self.app_context,
            on_item_created=self._on_business_sector_created,
            on_close=self._clear_business_sector_adder_view
        )

    def _on_business_sector_created(self, sector_key, sector_value):
        """
        Aggiorna la combo dei settori dopo la creazione di un nuovo elemento.

        La lista dei valori viene ricaricata dal catalogo condiviso e la nuova
        voce viene selezionata automaticamente nel form fornitore.
        """
        sector_widget = self.supplier_widgets[DBSuppliersColumns.CATEGORIA.value]
        sector_widget.set_values(
            self._get_business_sector_values(),
            preserve_current=False
        )
        sector_widget.set_value(sector_value, safe_mode=False)
        self.grab_set()

    def _clear_business_sector_adder_view(self):
        """Azzera il riferimento alla finestra settore e ripristina il grab sul parent."""
        self.business_sector_adder_view = None
        if self.winfo_exists():
            self.grab_set()

    def _on_close(self):
        """Chiude il toplevel fornitore rilasciando in sicurezza l'eventuale grab."""
        try:
            self.grab_release()
        except Exception:
            pass

        if self.on_close:
            self.on_close()

        self.destroy()

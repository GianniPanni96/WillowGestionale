import customtkinter as ctk

from Gestionale_Enums import *
from Views.View_utils import ViewUtils
from Views.CustomWidgets.Catalog_filterable_combo_box import CatalogFilterableComboBox
from Views.CustomWidgets.Filterable_combo_box import FilterableComboBox
from Views.Adders.Business_sector_adder_view import BusinessSectorAdderView

from App_context import AppContext

from Gestionale_Enums import *


class ClientCreateView(ctk.CTkToplevel):
    """
    Finestra modale per la creazione di un nuovo cliente.

    La classe incapsula l'intero workflow di inserimento:
    - costruzione del form;
    - validazione minima lato view;
    - raccolta dei dati dai widget;
    - invocazione del controller di salvataggio;
    - eventuale creazione dinamica di un nuovo settore di business.
    """

    def __init__(self, parent, app_context: AppContext, on_client_created=None, on_close=None):
        """
        Inizializza la creator view del cliente.

        Args:
            parent: widget padre.
            app_context: contesto applicativo condiviso.
            on_client_created: callback opzionale invocata dopo il salvataggio.
            on_close: callback opzionale invocata alla chiusura del toplevel.
        """
        super().__init__(parent)

        self.app_context = app_context
        self.client_controller = app_context.client_controller
        self.clients_query_service = app_context.clients_query_service
        self.catalogo_elenchi = app_context.catalogo_elenchi
        self.config_manager = app_context.config_manager

        self.on_client_created = on_client_created
        self.on_close = on_close

        # Definisce il form in modo dichiarativo: ogni chiave corrisponde a un
        # campo DB e viene associata al widget da usare per l'input.
        self.entry_fields = {
            DBClientsColumns.NAME.value: ctk.CTkEntry,
            DBClientsColumns.TIPOLOGIA.value: ctk.CTkOptionMenu,
            DBClientsColumns.PARTITA_IVA.value: ctk.CTkEntry,
            DBClientsColumns.EMAIL.value: ctk.CTkEntry,
            DBClientsColumns.SEDE_LEGALE.value: ctk.CTkEntry,
            DBClientsColumns.SETTORE.value: CatalogFilterableComboBox,
            DBClientsColumns.REFERENTE.value: ctk.CTkEntry,
            DBClientsColumns.CONTATTO_REFERENTE.value: ctk.CTkEntry,
            DBClientsColumns.NOTE.value: ctk.CTkTextbox,
        }
        self.error_fields = {
            DBClientsColumns.NAME.value: ctk.CTkLabel,
            DBClientsColumns.PARTITA_IVA.value: ctk.CTkLabel,
            DBClientsColumns.EMAIL.value: ctk.CTkLabel,
            DBClientsColumns.SEDE_LEGALE.value: ctk.CTkLabel,
            DBClientsColumns.SETTORE.value: ctk.CTkLabel,
        }
        self.field_labels = {}
        self.client_widgets = {}
        self.error_labels = {}
        self.business_sector_adder_view = None

        self.title("Aggiungi Nuovo Cliente")
        self.geometry("400x700")
        self.lift()
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.scrollable_frame = ctk.CTkScrollableFrame(self)
        self.scrollable_frame.pack(fill="both", expand=True)

        self._build_form()
        self._bind_validations()

    def _build_form(self):
        """
        Costruisce dinamicamente tutti i campi del form cliente.

        Le definizioni dei campi partono dai dizionari ``entry_fields`` ed
        ``error_fields``, cosi' la struttura del form resta centralizzata.
        """
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

            self.client_widgets[label_text] = widget

        self.save_button = ctk.CTkButton(
            self.scrollable_frame,
            text="Salva Cliente",
            command=self.save_client_data
        )
        self.save_button.pack(pady=(35, 15))

    def _create_field_widget(self, label_text, widget_class):
        """
        Crea il widget corretto per il campo richiesto.

        I campi speciali, come tipologia e settore, richiedono configurazioni
        aggiuntive rispetto ai semplici ``CTkEntry``.
        """
        if label_text == DBClientsColumns.TIPOLOGIA.value:
            widget = widget_class(
                self.scrollable_frame,
                values=[item.value for item in TipologiaCliente]
            )
            widget.set(TipologiaCliente.PRIVATO.value)
            return widget

        if label_text == DBClientsColumns.SETTORE.value:
            widget = widget_class(
                parent=self.scrollable_frame,
                placeholder="Cerca",
                autofill=True,
                values=self._get_business_sector_values(),
                add_button_text="Aggiungi un settore",
                add_button_command=self.open_add_business_sector
            )
            widget.set_value(BusinessSector.CREATIVE_AGENCY.value)
            return widget

        return widget_class(self.scrollable_frame)

    def _bind_validations(self):
        """Collega le validazioni lato interfaccia ai campi principali."""
        self.client_widgets[DBClientsColumns.NAME.value].bind(
            "<FocusOut>",
            lambda event: ViewUtils.validate_entry(
                self.client_widgets[DBClientsColumns.NAME.value],
                lambda val: val.strip() != "",
                self.error_labels[DBClientsColumns.NAME.value],
                "Il nome non puo essere vuoto."
            )
        )

    def _collect_client_data(self):
        """
        Estrae i dati del form in un dizionario compatibile col controller.

        Ogni widget espone un'API leggermente diversa, quindi il metodo centralizza
        la lettura dei valori e normalizza l'output.
        """
        client_data = {}

        for label_text, widget in self.client_widgets.items():
            if isinstance(widget, (ctk.CTkEntry, ctk.CTkOptionMenu)):
                client_data[label_text] = widget.get().strip()
            elif isinstance(widget, ctk.CTkTextbox):
                client_data[label_text] = widget.get("1.0", "end-1c").strip()
            elif isinstance(widget, FilterableComboBox):
                client_data[label_text] = widget.get_value()

        return client_data

    def save_client_data(self):
        """
        Valida e salva il nuovo cliente tramite ``ClientController``.

        In caso di successo notifica il chiamante con ``on_client_created`` e
        chiude la finestra; in caso di errore mostra un popup esplicativo.
        """
        client_data = self._collect_client_data()
        success, message = self.client_controller.save_client(client_data)

        if not success:
            ViewUtils.show_error_popup(self, "ERRORE", message)
            return

        client_row = self.clients_query_service.retrieve_client_by_name(client_data[DBClientsColumns.NAME.value])
        client_id = client_row[0] if client_row else None

        if self.on_client_created:
            self.on_client_created(client_id, client_data)

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
        voce viene selezionata automaticamente nel form cliente.
        """
        sector_widget = self.client_widgets[DBClientsColumns.SETTORE.value]
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
        """Chiude il toplevel cliente rilasciando in sicurezza l'eventuale grab."""
        try:
            self.grab_release()
        except Exception:
            pass

        if self.on_close:
            self.on_close()

        self.destroy()

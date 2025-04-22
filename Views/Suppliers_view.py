import customtkinter as ctk
import tkinter as tk
from tkcalendar import Calendar
from Views.View_utils import ViewUtils
from Controllers import PaymentsController, InvoiceController, UserController, ControllerUtils, SupplierController
from Model import DBInvoicesColumns, DBUsersColumns, DBClientsColumns, DBPaymentsColumns, DBProductionsColumns, DBAccountsColumns, DBSuppliersColumns
from datetime import datetime
import re
from enum import Enum

class SuppliersView(ctk.CTk):

    def __init__(self, db_model, supplier_controller, update_controller,  config_manager, catalogo_elenchi, tab):
        super().__init__()

        self.db_model = db_model
        self.update_controller = update_controller
        self.supplier_controller = supplier_controller
        self.config_manager = config_manager
        self.catalogo_elenchi = catalogo_elenchi
        self.tab = tab

        self.global_infos = {}
        self.amount_aggregate_labels = {}

        self.suppliers_card_list = {}
        self.supplier_card_labels_status = {}

    def create_suppliers_tab(self):

        self.search_bar_frame = ctk.CTkFrame(self.tab)
        self.search_bar_frame.pack(pady=10, fill="x", anchor="n")
        self.search_bar = ctk.CTkEntry(self.search_bar_frame)
        self.search_bar.pack(padx=(5,35), anchor="e", side="right")
        self.search_bar_label = ctk.CTkLabel(self.search_bar_frame, text="Filtra per nome:", font=("Arial", 14))
        self.search_bar_label.pack(padx=5, anchor="e")


        # Aggiungi evento alla barra di ricerca
        self.search_bar.bind("<KeyRelease>", self.filter_cards)


        self.suppliers_table_frame = ctk.CTkFrame(self.tab)
        self.suppliers_table_frame.pack(pady=(20, 0), padx=(10,15), fill="x", anchor="n")

        self.headers = ["NOME", "PARTITA IVA", "TOT. SPESE", "# SPESE", "SPESA MEDIA", "NOTE", "CONTATTO"]

        for i, header in enumerate(self.headers):
            # crea il container
            column = ctk.CTkFrame(self.suppliers_table_frame)
            column.grid(row=0, column=i, sticky="nsew", padx=(0, 5), pady=5)

            # imposta peso e uniformità: tutte le colonne "col" si dividono equamente
            self.suppliers_table_frame.grid_columnconfigure(i, weight=1, uniform="col")

            # la label riempie il suo container
            label = ctk.CTkLabel(column,
                                 text=header,
                                 font=("Arial", 14))
            label.pack(fill="both", expand=True, padx=5, pady=15)

        # Creazione del frame delle cards
        self.suppliers_cards_frame = ctk.CTkScrollableFrame(self.tab)
        self.suppliers_cards_frame.pack(padx=0, pady=10, fill="both", expand=True)

        self.add_supplier_frame = ctk.CTkFrame(self.tab)
        self.add_supplier_frame.pack(padx=0, pady=(5, 20), fill="x")

        self.save_button = ctk.CTkButton(self.add_supplier_frame, text="Aggiungi Fornitore", command=self.open_add_supplier_window)
        self.save_button.pack()

        supplier_list = self.supplier_controller.retrieve_suppliers_map_list()

        for supplier in supplier_list:
            #costruisco i dati aggregati per singolo cliente
            aggregate_data = self.supplier_controller.construct_supplier_map_aggregate_data(supplier[DBSuppliersColumns.ID.value])

            self.add_supplier_card(supplier[f"{DBSuppliersColumns.ID.value}"],
                                   supplier[f"{DBSuppliersColumns.NAME.value}"],
                                   supplier[f"{DBSuppliersColumns.PARTITA_IVA.value}"],
                                   aggregate_data[SupplierController.Aggregate_data.NUM_SPESE.value],
                                   round(aggregate_data[SupplierController.Aggregate_data.MEDIA_SPESE.value], 2),
                                   round(aggregate_data[SupplierController.Aggregate_data.TOT_SPESE.value], 2),
                                   supplier[f"{DBSuppliersColumns.NOTE.value}"],
                                   supplier[f"{DBSuppliersColumns.CONTATTO.value}"]
                                   )

    def open_add_supplier_window(self):
        """Apre una finestra per aggiungere un nuovo fornitore"""

        self.add_supplier_window = ctk.CTkToplevel(self)
        self.add_supplier_window.title("Aggiungi Nuovo Fornitore")

        # Assicurati che la finestra rimanga sopra
        self.add_supplier_window.lift()  # Porta la finestra sopra quella principale
        self.add_supplier_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

        self.add_supplier_window.geometry("400x700")

        self.supplier_window_scrollableFrame = ctk.CTkScrollableFrame(self.add_supplier_window)
        self.supplier_window_scrollableFrame.pack(fill="both", expand=True)

        # Campi per il form
        self.entry_fields = {
            DBSuppliersColumns.NAME.value: ctk.CTkEntry,
            DBSuppliersColumns.PARTITA_IVA.value: ctk.CTkEntry,
            DBSuppliersColumns.SEDE.value: ctk.CTkEntry,
            DBSuppliersColumns.CONTATTO.value: ctk.CTkEntry,
            DBSuppliersColumns.CATEGORIA.value: ctk.CTkOptionMenu,
            DBSuppliersColumns.NOTE.value: ctk.CTkTextbox,
        }

        self.error_fields = {
            DBSuppliersColumns.NAME.value: ctk.CTkLabel,
        }

        # Dizionario per conservare i riferimenti ai widget
        self.suppliers_widgets = {}
        self.error_labels = {}

        # Creazione dei widget
        for i, (label_text, widget_class) in enumerate(self.entry_fields.items()):
            # Etichetta
            label = ctk.CTkLabel(self.supplier_window_scrollableFrame, text=label_text)
            if i == 0:
                label.pack(pady=5)
            else:
                label.pack(pady=(35, 0))

            # Widget
            if label_text == DBSuppliersColumns.CATEGORIA.value:
                widget = widget_class(self.supplier_window_scrollableFrame,
                                      values=[value for key, value in
                                              self.catalogo_elenchi["clients_business_sectors"]],
                                      command=lambda selected_value: self.open_add_business_sector(selected_value))

            else:
                widget = widget_class(self.supplier_window_scrollableFrame)

            if widget_class == ctk.CTkTextbox:
                widget.pack(pady=5, padx=10, fill="x", expand=True)
            else:
                widget.pack(pady=5, padx=10, fill="x", expand=True)

            if self.error_fields.get(label_text) is not None:
                error_label = ctk.CTkLabel(self.supplier_window_scrollableFrame, text="")
                error_label.pack(pady=(0, 15))
                self.error_labels[label_text] = error_label

            self.suppliers_widgets[label_text] = widget

        # Bottone per salvare
        save_button = ctk.CTkButton(
            self.supplier_window_scrollableFrame,
            text="Salva Fornitore",
            command=self.save_supplier_data
        )
        save_button.pack(pady=(35, 15))

        # Aggiungi validazione agli eventi di perdita del focus
        self.suppliers_widgets[DBSuppliersColumns.NAME.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.suppliers_widgets[DBSuppliersColumns.NAME.value],
            lambda val: val.strip() != "",
            self.error_labels[DBSuppliersColumns.NAME.value],
            "Il nome non può essere vuoto."
        ))

    def add_supplier_card(self, supplier_id, supplier_name, partita_iva, num_spese, spesa_media, tot_spese, note, contatto):
        # Creazione della card
        card = ctk.CTkFrame(self.suppliers_cards_frame, fg_color="dimgray")
        card.pack(pady=10, padx=10, fill="x", expand=True)  # Spaziatura tra le card

        # Dati da visualizzare nella card
        data = [supplier_name, partita_iva, f"{tot_spese:.2f}", num_spese, f"{spesa_media:.2f}", note, contatto]
        units = ["","", "€", "", "€", "", ""]
        n_cols = len(data)  # 8 colonne totali

        # Configura il grid della card: 1 riga, n_cols colonne uguali
        for c in range(n_cols):
            card.grid_columnconfigure(c, weight=1, uniform="clientcol")
        card.grid_rowconfigure(0, weight=1)

        # 0) Bottone "nome"
        btn = ctk.CTkButton(
            card,
            text=supplier_name,
            command=lambda sid=supplier_id: self.open_supplier_detail(sid)
        )
        btn.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        # 1..7) Le altre colonne
        for idx, val in enumerate(data[1:], start=1):
            text = f"{val} {units[idx]}"
            lbl = ctk.CTkLabel(card, text=text, font=("Arial", 14))
            lbl.grid(row=0, column=idx, sticky="nsew", padx=5, pady=10)

        # Salva la card per eventuale successivo accesso
        self.suppliers_card_list[supplier_name] = card

    def save_supplier_data(self):
        supplier_data = {}

        # Riempi il dizionario con i dati dai widget
        for label_text, widget in self.suppliers_widgets.items():
            if isinstance(widget, ctk.CTkEntry) or isinstance(widget, ctk.CTkOptionMenu):
                supplier_data[label_text] = widget.get().strip()  # Recupera il testo o il valore selezionato
            elif isinstance(widget, ctk.CTkTextbox):
                supplier_data[label_text] = widget.get("1.0", "end-1c").strip()  # Recupera il testo dal Textbox

        print("Dati fornitore:", supplier_data)

        supplier_id  = -1

        #chiamata al controller per salvare i dati
        success, message = self.supplier_controller.save_supplier(supplier_data)
        if success:
            supplier_id = self.supplier_controller.retrieve_last_supplier_insert_map()[DBSuppliersColumns.ID.value]
            print(f"Supplier {supplier_data[DBSuppliersColumns.NAME.value]} salvato con successo")
            self.add_supplier_card(
                supplier_id,
                supplier_data[DBSuppliersColumns.NAME.value],
                supplier_data[DBSuppliersColumns.PARTITA_IVA.value],
                0,
                0,
                0,
                supplier_data[DBSuppliersColumns.NOTE.value],
                supplier_data[DBSuppliersColumns.CONTATTO.value],
            )
            self.add_supplier_window.destroy()
        else:
            print(message)
            ViewUtils.show_error_popup(self.add_supplier_window, "ERRORE", message)

    def filter_cards(self, event):
        """Filtra le card in base al testo della barra di ricerca."""
        search_text = self.search_bar.get().lower()

        # Cicla attraverso tutte le card dei clienti
        for nome, card in self.suppliers_card_list.items():
            # Se il nome del cliente contiene il testo della ricerca (ignorando maiuscole/minuscole)
            if search_text in nome.lower():
                # Rendi visibile la card
                card.pack(pady=10, padx=10, fill="x", expand=True)
            else:
                # Nascondi la card
                card.pack_forget()

    def open_supplier_detail(self, supplier_id):
        return

    def open_add_business_sector(self, selected_value):
        sector_dict = dict(self.catalogo_elenchi["clients_business_sectors"])
        if selected_value == sector_dict.get("ADD_SECTOR"):
            self.add_sector_window = ctk.CTkToplevel(self)
            self.add_sector_window.title("Aggiungi un nuovo settore di business")

            # Assicurati che la finestra rimanga sopra
            self.add_sector_window.lift()  # Porta la finestra sopra quella principale
            self.add_sector_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

            self.add_sector_window.geometry("400x300")

            self.business_sector_window_Frame = ctk.CTkFrame(self.add_sector_window)
            self.business_sector_window_Frame.pack(fill="both", expand=True)

            ctk.CTkLabel(self.business_sector_window_Frame, text="Aggiungi un settore di business alla lista\nsepara parole diverse solo tramite spazio").pack(padx=10, pady=(25, 0))

            self.add_sector_entry = ctk.CTkEntry(self.business_sector_window_Frame)
            self.add_sector_entry.pack(padx=10, pady=5, fill="x", expand=True)

            ctk.CTkButton(self.business_sector_window_Frame, text="Aggiungi settore", command=self.save_business_sector).pack(padx=10, pady=(15, 10))

        else: return

    def save_business_sector(self):
        new_sector = self.add_sector_entry.get()
        new_sector_key = ControllerUtils.normalize_string_for_key(new_sector)
        try:
            self.config_manager.update_list_field("clients_business_sectors", new_sector_key, new_sector, "update")
        except Exception as e:
            ViewUtils.show_error_popup(self.add_sector_window, "Errore", f"Impossibile aggiungere il nuovo settore: {str(e)}")
            return

        self.suppliers_widgets[DBSuppliersColumns.CATEGORIA.value].set(new_sector)
        self.add_sector_window.destroy()

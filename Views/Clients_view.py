import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
from datetime import datetime
import re
from enum import Enum

from Views.View_utils import ViewUtils
from Controllers import ControllerUtils, ClientController
from Model import DBClientsColumns


class ClientsView(ctk.CTk):
    def __init__(self, db_model, client_controller, catalogo_elenchi, config_manager, tab, event_bus):
        super().__init__()

        self.db_model = db_model
        self.client_controller = client_controller
        self.tab = tab
        self.catalogo_elenchi = catalogo_elenchi
        self.config_manager = config_manager
        self.event_bus = event_bus

        self.clients_card_list = {}


    def create_client_tab(self):

        self.search_bar_frame = ctk.CTkFrame(self.tab)
        self.search_bar_frame.pack(pady=10, fill="x", anchor="n")
        self.search_bar = ctk.CTkEntry(self.search_bar_frame)
        self.search_bar.pack(padx=(5,35), anchor="e", side="right")
        self.search_bar_label = ctk.CTkLabel(self.search_bar_frame, text="Filtra per nome:", font=("Arial", 14))
        self.search_bar_label.pack(padx=5, anchor="e")


        # Aggiungi evento alla barra di ricerca
        self.search_bar.bind("<KeyRelease>", self.filter_cards)


        self.clients_table_frame = ctk.CTkFrame(self.tab)
        self.clients_table_frame.pack(pady=(20, 0), padx=(10,15), fill="x", anchor="n")

        self.headers = ["NOME", "TOT. ENTRATE", "# FATTURE", "FATTURA MEDIA", "TOT. CREDITI",
                   "PAGAMENTO \n ORARIO MEDIO", "TOT. GIORNI \n RITARDO", "MEDIA RITARDO"]

        for i, header in enumerate(self.headers):
            # crea il container
            column = ctk.CTkFrame(self.clients_table_frame)
            column.grid(row=0, column=i, sticky="nsew", padx=(0, 5), pady=5)

            # imposta peso e uniformità: tutte le colonne "col" si dividono equamente
            self.clients_table_frame.grid_columnconfigure(i, weight=1, uniform="col")

            # la label riempie il suo container
            label = ctk.CTkLabel(column,
                                 text=header,
                                 font=("Arial", 14))
            label.pack(fill="both", expand=True, padx=5, pady=15)

        # Creazione del frame delle cards
        self.clients_cards_frame = ctk.CTkScrollableFrame(self.tab)
        self.clients_cards_frame.pack(padx=0, pady=10, fill="both", expand=True)

        self.add_client_frame = ctk.CTkFrame(self.tab)
        self.add_client_frame.pack(padx=0, pady=(5, 20), fill="x")

        self.save_button = ctk.CTkButton(self.add_client_frame, text="Aggiungi Cliente", command=self.open_add_client_window)
        self.save_button.pack()

        for client in self.client_controller.retrieve_clients_map_list():
            #costruisco i dati aggregati per singolo cliente
            aggregate_data = self.client_controller.construct_client_map_aggregate_data(client[DBClientsColumns.ID.value])

            self.add_client_card(client[f"{DBClientsColumns.ID.value}"], client[f"{DBClientsColumns.NAME.value}"],
                                 round(aggregate_data[ClientController.Aggregate_data.TOT_ENTRATE.value], 2),
                                 aggregate_data[ClientController.Aggregate_data.NUM_FATTURE.value],
                                 round(aggregate_data[ClientController.Aggregate_data.MEDIA_FATTURE.value], 2),
                                 round(aggregate_data[ClientController.Aggregate_data.TOT_CREDITI.value], 2),
                                 round(aggregate_data[ClientController.Aggregate_data.PAGAM_ORARIO_MEDIO.value], 2),
                                 aggregate_data[ClientController.Aggregate_data.TOT_GIORNI_RIT.value],
                                 round(aggregate_data[ClientController.Aggregate_data.MEDIA_RITARDO.value], 2))

    def add_client_card(self, client_id, nome, tot_entrate, num_fatture, fattura_media, tot_crediti, pagam_orario, giorni_rit, media_rit):
        """
        Aggiunge una singola card con i dati forniti alla scrollable frame,
        disponendo i widget in colonne di ugual larghezza.
        """
        # Creazione della card
        card = ctk.CTkFrame(self.clients_cards_frame, fg_color="dimgray")
        card.pack(pady=10, padx=10, fill="x", expand=True)

        # Dati da visualizzare: bottone + 7 colonne di dati
        data = [
            nome,
            f"{tot_entrate:.2f}",
            num_fatture,
            f"{fattura_media:.2f}",
            f"{tot_crediti:.2f}",
            f"{pagam_orario:.2f}",
            giorni_rit,
            f"{media_rit:.2f}"
        ]
        units = ["", "€", "", "€", "€", "€/h", "gg", "gg"]

        n_cols = len(data)  # 8 colonne totali

        # Configura il grid della card: 1 riga, n_cols colonne uguali
        for c in range(n_cols):
            card.grid_columnconfigure(c, weight=1, uniform="clientcol")
        card.grid_rowconfigure(0, weight=1)

        # 0) Bottone "nome"
        btn = ctk.CTkButton(
            card,
            text=nome,
            command=lambda cid=client_id: self.open_client_detail(cid)
        )
        btn.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        # 1..7) Le altre colonne
        for idx, val in enumerate(data[1:], start=1):
            text = f"{val} {units[idx]}"
            lbl = ctk.CTkLabel(card, text=text, font=("Arial", 14))
            lbl.grid(row=0, column=idx, sticky="nsew", padx=5, pady=10)

        # Salva la card per eventuale successivo accesso
        self.clients_card_list[nome] = card

    def filter_cards(self, event):
        """Filtra le card in base al testo della barra di ricerca."""
        search_text = self.search_bar.get().lower()

        # Cicla attraverso tutte le card dei clienti
        for nome, card in self.clients_card_list.items():
            # Se il nome del cliente contiene il testo della ricerca (ignorando maiuscole/minuscole)
            if search_text in nome.lower():
                # Rendi visibile la card
                card.pack(pady=10, padx=10, fill="x", expand=True)
            else:
                # Nascondi la card
                card.pack_forget()

    def open_add_client_window(self):
        """Apre una finestra per aggiungere un nuovo cliente"""

        self.add_client_window = ctk.CTkToplevel(self)
        self.add_client_window.title("Aggiungi Nuovo Cliente")

        # Assicurati che la finestra rimanga sopra
        self.add_client_window.lift()  # Porta la finestra sopra quella principale
        self.add_client_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

        self.add_client_window.geometry("400x700")

        self.client_window_scrollableFrame = ctk.CTkScrollableFrame(self.add_client_window)
        self.client_window_scrollableFrame.pack(fill="both", expand=True)

        # Campi per il form
        self.entry_fields = {
            DBClientsColumns.NAME.value: ctk.CTkEntry,
            DBClientsColumns.TIPOLOGIA.value: ctk.CTkOptionMenu,
            DBClientsColumns.PARTITA_IVA.value: ctk.CTkEntry,
            DBClientsColumns.EMAIL.value: ctk.CTkEntry,
            DBClientsColumns.SEDE_LEGALE.value: ctk.CTkEntry,
            DBClientsColumns.SETTORE.value: ctk.CTkOptionMenu,
            DBClientsColumns.REFERENTE.value: ctk.CTkEntry,
            DBClientsColumns.CONTATTO_REFERENTE.value: ctk.CTkEntry,
            DBClientsColumns.NOTE.value: ctk.CTkTextbox,
        }

        self.error_fields = {
            DBClientsColumns.NAME.value: ctk.CTkLabel,
            DBClientsColumns.PARTITA_IVA.value: ctk.CTkLabel,
            DBClientsColumns.EMAIL.value: ctk.CTkLabel,
            DBClientsColumns.SEDE_LEGALE.value: ctk.CTkLabel,
            DBClientsColumns.SETTORE.value: ctk.CTkLabel
        }

        # Dizionario per conservare i riferimenti ai widget
        self.client_widgets = {}
        self.error_labels = {}

        # Creazione dei widget
        for i, (label_text, widget_class) in enumerate(self.entry_fields.items()):
            # Etichetta
            label = ctk.CTkLabel(self.client_window_scrollableFrame, text=label_text)
            if i == 0:
                label.pack(pady=5)
            else:
                label.pack(pady=(35, 0))

            # Widget
            if label_text == DBClientsColumns.TIPOLOGIA.value:
                widget = widget_class(self.client_window_scrollableFrame,
                                      values=[item.value for item in self.client_controller.TipologiaCliente])
                widget.set(self.client_controller.TipologiaCliente.PRIVATO.value)  # Imposta valore predefinito
            elif label_text == DBClientsColumns.SETTORE.value:
                widget = widget_class(self.client_window_scrollableFrame,
                                      values=[value for key, value in self.catalogo_elenchi["clients_business_sectors"]],
                                      command = lambda selected_value : self.open_add_business_sector(selected_value))
                widget.set(self.client_controller.BusinessSector.CREATIVE_AGENCY.value)  # Imposta valore predefinito
            else:
                widget = widget_class(self.client_window_scrollableFrame)

            if widget_class == ctk.CTkTextbox:
                widget.pack(pady=5, padx=10, fill="x", expand=True)
            else:
                widget.pack(pady=5, padx=10, fill="x", expand=True)

            if self.error_fields.get(label_text) is not None:
                error_label = ctk.CTkLabel(self.client_window_scrollableFrame, text="")
                error_label.pack(pady=(0,15))
                self.error_labels[label_text] = error_label

            self.client_widgets[label_text] = widget


        # Bottone per salvare
        save_button = ctk.CTkButton(
            self.client_window_scrollableFrame,
            text="Salva Cliente",
            command=self.save_client_data
        )
        save_button.pack(pady=(35, 15))

        # Aggiungi validazione agli eventi di perdita del focus
        self.client_widgets[DBClientsColumns.NAME.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.client_widgets[DBClientsColumns.NAME.value],
            lambda val: val.strip() != "",
            self.error_labels[DBClientsColumns.NAME.value],
            "Il nome non può essere vuoto."
        ))

        """self.client_widgets[DBClientsColumns.PARTITA_IVA.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.client_widgets[DBClientsColumns.PARTITA_IVA.value],
            lambda val: val.isdigit() and ValidationUtils.validate_partita_iva(val),
            self.error_labels[DBClientsColumns.PARTITA_IVA.value],
            "La partita IVA deve essere un numero di 11 cifre."
        ))"""

        """self.client_widgets[DBClientsColumns.EMAIL.value].bind("<FocusOut>", lambda event: ViewUtils.validate_entry(
            self.client_widgets[DBClientsColumns.EMAIL.value],
            lambda val: ValidationUtils.validate_email(val),
            self.error_labels[DBClientsColumns.EMAIL.value],
            "Inserisci una e-mail valida."
        ))"""

    def save_client_data(self):
        client_data = {}

        # Riempi il dizionario con i dati dai widget
        for label_text, widget in self.client_widgets.items():
            if isinstance(widget, ctk.CTkEntry) or isinstance(widget, ctk.CTkOptionMenu):
                client_data[label_text] = widget.get().strip()  # Recupera il testo o il valore selezionato
            elif isinstance(widget, ctk.CTkTextbox):
                client_data[label_text] = widget.get("1.0", "end-1c").strip()  # Recupera il testo dal Textbox

        print("Dati cliente:", client_data)

        client_id  = -1

        #chiamata al controller per salvare i dati
        success, message = self.client_controller.save_client(client_data)
        if success:
            client_id = self.client_controller.retrieve_client_by_name(client_data[DBClientsColumns.NAME.value])[0]
            print(f"Client {client_data[DBClientsColumns.NAME.value]} salvato con successo")
            self.add_client_card(
                client_id,
                client_data[DBClientsColumns.NAME.value],
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            )
            #self.clients_list.append(self.client_controller.retrieve_client_map_by_id(client_id))
            self.client_controller.print_clienti()

            self.add_client_window.destroy()
        else:
            print(message)
            ViewUtils.show_error_popup(self.add_client_window, "ERRORE", message)

    def open_client_detail(self, client_id):
        self.client_details_window = ctk.CTkToplevel(self)
        client_db_info = self.client_controller.retrieve_client_map_by_id(client_id)
        self.client_details_window.title(f"Dettaglio del cliente: {client_db_info[DBClientsColumns.NAME.value]}")

        # Assicurati che la finestra rimanga sopra
        self.client_details_window.lift()  # Porta la finestra sopra quella principale
        self.client_details_window.grab_set()  # Rende la finestra modale (bloccando l'interazione con la finestra principale)

        self.client_details_window.geometry("700x700")

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

        self.client_widgets[DBClientsColumns.SETTORE.value].set(new_sector)
        self.add_sector_window.destroy()
from enum import Enum

from Analyzers.Production_analyzer_service import ProductionAnalyzerService
from Gestionale_Enums import*
import customtkinter as ctk
import tkinter as tk
from tkinter import Toplevel
from PIL import Image
import os

from Model import DBExpensesColumns, DBSuppliersColumns, DBUsersColumns, DBAccountsColumns, DBSalariesColumns, DBRefundsColumns
from Model import DBProductionsColumns, DBPaymentsColumns, DBInvoicesColumns, DBClientsColumns, DBTransfersColumns

from Analyzers.Client_analyzer_service import  ClientAnalyzerService
from Analyzers.Supplier_analyzer_service import  SupplierAnalyzerService
from QueryServices.Clients_query_service import ClientQueryService
from QueryServices.Suppliers_query_service import SupplierQueryService

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from Controllers import ClientController
    from Controllers import UserController
    from Controllers import AccountController
    from Controllers import TransfersController
    from Controllers import PaymentsController
    from Controllers import ExpenseController
    from Controllers import SupplierController
    from Controllers import SalaryController
    from Controllers import RefundController
    from Controllers import InvoiceController
    from Controllers import ProductionController
    from Controllers import Analyzer


class ViewUtils(ctk.CTk):

    class InterfaceOperations(Enum):
        AGGIUNTA_UTENTE = "AGGIUNTA UTENTE"
        ELIMINAZIONE_UTENTE = "ELIMINAZIONE UTENTE"
        MODIFICA_UTENTE = "MODIFICA UTENTE"

        AGGIUNTA_CLIENTE = "AGGIUNTA CLIENTE"
        ELIMINAZIONE_CLIENTE = "ELIMINAZIONE CLIENTE"
        MODIFICA_CLIENTE = "MODIFICA CLIENTE"

        AGGIUNTA_FATTURA = "AGGIUNTA FATTURA"
        ELIMINAZIONE_FATTURA = "ELIMINAZIONE FATTURA"
        MODIFICA_FATTURA = "MODIFICA FATTURA"

    class EventBusKeys(Enum):
        SHOW_INVOICE_DETAIL = "SHOW_INVOICE_DETAIL"
        SHOW_SALARY_DETAIL = "SHOW_SALARY_DETAIL"
        SHOW_PRODUCTION_DETAIL = "SHOW_PRODUCTION_DETAIL"
        SHOW_REFUND_DETAIL = "SHOW_REFUND_DETAIL"
        SHOW_EXPENSE_DETAIL = "SHOW_EXPENSE_DETAIL"
        SHOW_PAYMENT_DETAIL = "SHOW_PAYMENT_DETAIL"
        LOGIN_STATUS_CHANGED = "LOGIN_STATUS_CHANGED"

    date_pattern = "yyyy-mm-dd"

    disabled_label_color = "#4a4948"

    @staticmethod
    def validate_entry(entry_widget, validation_func, error_label, error_message):
        """
        Valida un campo specifico.
        :param entry_widget: Il widget dell'entry da validare.
        :param validation_func: La funzione di validazione da applicare.
        :param error_label: Il widget dove mostrare il messaggio di errore.
        :param error_message: Il messaggio di errore da mostrare.
        """
        value = entry_widget.get()
        if validation_func(value):
            entry_widget.configure(border_color="green")  # Sfondo normale
            error_label.configure(text="")  # Nessun messaggio di errore
        else:
            entry_widget.configure(border_color="red")  # Sfondo rosso per errore
            error_label.configure(text_color="#e8e5dc", text=error_message)  # Mostra il messaggio di errore

    @staticmethod
    def validate_textbox(textbox_widget, validation_func, error_label, error_message):
        """
        Valida un campo di testo multilinea.
        :param textbox_widget: Il widget CTkTextbox da validare.
        :param validation_func: La funzione di validazione da applicare.
        :param error_label: Il widget dove mostrare il messaggio di errore.
        :param error_message: Il messaggio di errore da mostrare.
        """
        # Ottieni il contenuto del textbox (dall'inizio alla fine, escludendo il carattere di nuova riga finale)
        value = textbox_widget.get("1.0", "end-1c")

        if validation_func(value):
            # Se la validazione ha successo
            textbox_widget.configure(border_color="#565B5E")  # Colore bordo normale
            error_label.configure(text="")  # Nessun messaggio di errore
        else:
            # Se la validazione fallisce
            textbox_widget.configure(border_color="red")  # Bordo rosso per errore
            error_label.configure(text_color="#e8e5dc", text=error_message)  # Mostra messaggio di errore

    @staticmethod
    def show_error_popup(parent, title="Errore", message="Si è verificato un errore"):
        """
        Genera un pop-up di errore.
        :param parent: La finestra principale da cui viene lanciato il pop-up.
        :param title: Il titolo del pop-up.
        :param message: Il messaggio di errore da mostrare.
        """
        error_popup = ctk.CTkToplevel(parent)
        error_popup.title(title)
        error_popup.geometry("300x150")

        # Assicurati che il pop-up sia modale
        error_popup.grab_set()
        error_popup.lift()

        # Etichetta per il messaggio di errore
        error_label = ctk.CTkLabel(error_popup, text=message, wraplength=250, font=("Arial", 14))
        error_label.pack(pady=(20, 10))

        # Bottone per chiudere il pop-up
        close_button = ctk.CTkButton(error_popup, text="Chiudi", command=error_popup.destroy)
        close_button.pack(pady=(10, 20))

    @staticmethod
    def show_confirm_popup(parent, title="CONFERMA", message="L'operazione è andata a buon fine"):
        """
        Genera un pop-up di errore.
        :param parent: La finestra principale da cui viene lanciato il pop-up.
        :param title: Il titolo del pop-up.
        :param message: Il messaggio di errore da mostrare.
        """
        confirm_popup = ctk.CTkToplevel(parent)
        confirm_popup.title(title)
        confirm_popup.geometry("350x190")

        # Assicurati che il pop-up sia modale
        confirm_popup.grab_set()
        confirm_popup.lift()

        # Etichetta per il messaggio di errore
        confirm_label = ctk.CTkLabel(confirm_popup, text=message, wraplength=250, font=("Arial", 14))
        confirm_label.pack(pady=(20, 10))

        # Bottone per chiudere il pop-up
        close_button = ctk.CTkButton(confirm_popup, text="Chiudi", command=lambda: on_closing_popup(confirm_popup, parent))
        close_button.pack(pady=(10, 20))

        def on_closing_popup(pop_up, parent):
            pop_up.destroy()
            parent.destroy()

    @staticmethod
    def show_confirm_popup_2(parent, title="CONFERMA", message="L'operazione è andata a buon fine"):
        """
        Genera un pop-up di errore.
        :param parent: La finestra principale da cui viene lanciato il pop-up.
        :param title: Il titolo del pop-up.
        :param message: Il messaggio di errore da mostrare.
        """
        confirm_popup = ctk.CTkToplevel(parent)
        confirm_popup.title(title)
        confirm_popup.geometry("350x190")

        # Assicurati che il pop-up sia modale
        confirm_popup.grab_set()
        confirm_popup.lift()

        # Etichetta per il messaggio di errore
        confirm_label = ctk.CTkLabel(confirm_popup, text=message, wraplength=250, font=("Arial", 14))
        confirm_label.pack(pady=(20, 10))

        # Bottone per chiudere il pop-up
        close_button = ctk.CTkButton(confirm_popup, text="Chiudi",
                                     command=lambda: on_closing_popup(confirm_popup))
        close_button.pack(pady=(10, 20))

        def on_closing_popup(pop_up):
            pop_up.destroy()

    @staticmethod
    def show_confirm_popup_simple(parent, title="CONFERMA", message="L'operazione è andata a buon fine"):
        """
        Genera un pop-up di errore.
        :param parent: La finestra principale da cui viene lanciato il pop-up.
        :param title: Il titolo del pop-up.
        :param message: Il messaggio di errore da mostrare.
        """
        confirm_popup = ctk.CTkToplevel(parent)
        confirm_popup.title(title)
        confirm_popup.geometry("400x100")

        # Assicurati che il pop-up sia modale
        confirm_popup.grab_set()
        confirm_popup.lift()

        # Etichetta per il messaggio di errore
        confirm_label = ctk.CTkLabel(confirm_popup, text=message, wraplength=250, font=("Arial", 14))
        confirm_label.pack(pady=(20, 10))


    @staticmethod
    def ask_confirmation_popup(parent, message, title="CONFERMA OPERAZIONE"):
        """
        Crea un pop-up che chiede conferma all'utente per proseguire un'operazione.

        :param parent: La finestra principale da cui viene lanciato il pop-up.
        :param message: Il messaggio di conferma da mostrare.
        :param title: Il titolo del pop-up.
        :return: True se l'utente conferma, False se annulla.
        """
        # Dizionario per memorizzare il risultato della scelta
        result = {"confirmed": False}

        # Creazione del Toplevel e impostazioni iniziali
        popup = ctk.CTkToplevel(parent)
        popup.title(title)
        #popup.geometry("350x190")
        popup.grab_set()  # Rende il pop-up modale
        popup.lift()  # Porta il pop-up in primo piano

        # Etichetta per il messaggio
        label = ctk.CTkLabel(popup, text=message, wraplength=250, font=("Arial", 14))
        label.pack(pady=(20, 10))

        # Funzioni per la gestione dei bottoni
        def on_confirm():
            result["confirmed"] = True
            popup.destroy()

        def on_cancel():
            result["confirmed"] = False
            popup.destroy()

        # Creazione dei bottoni
        # Puoi posizionarli affiancati usando un frame, oppure direttamente con il pack
        buttons_frame = ctk.CTkFrame(popup)
        buttons_frame.pack(pady=(10, 20))

        confirm_button = ctk.CTkButton(buttons_frame, text="Conferma", command=on_confirm)
        confirm_button.pack(side="left", padx=10)

        cancel_button = ctk.CTkButton(buttons_frame, text="Annulla", command=on_cancel)
        cancel_button.pack(side="left", padx=10)

        # Attendi la chiusura del pop-up prima di restituire il risultato
        popup.wait_window()

        return result["confirmed"]

    @staticmethod
    def invert_data_string(data):
        date = data.split("-")
        return date[2] + "-" + date[1] + "-" + date[0]

    @staticmethod
    def split_string_by_length(text: str, max_length: int) -> str:
        """
        Divide la stringa `text` aggiungendo un '\n' vicino alla metà, ma solo tra parole,
        se la stringa eccede `max_length`.

        :param text: La stringa da processare.
        :param max_length: La lunghezza massima prima di spezzare la stringa.
        :return: La stringa modificata con un '\n' se necessario.
        """
        if len(text) <= max_length:
            return text  # Se la stringa è già corta, non c'è bisogno di modificarla

        words = text.split()  # Divide la stringa in parole
        current_length = 0
        split_index = -1

        # Trova il miglior punto di divisione
        for i, word in enumerate(words):
            current_length += len(word) + 1  # Aggiunge la lunghezza della parola e lo spazio
            if current_length >= max_length // 2:
                split_index = i
                break

        if split_index == -1 or split_index == len(words) - 1:
            return text  # Nessun punto valido per la divisione

        return " ".join(words[:split_index + 1]) + "\n" + " ".join(words[split_index + 1:])

    @staticmethod
    def construct_global_infos_cards(frame, infos_dict) -> dict:
        """
        Costruisce delle "cards" per ogni elemento di infos_dict e le inserisce nel frame fornito.

        :param frame: ctk.CTkFrame in cui inserire le cards
        :param infos_dict: dizionario con struttura:
            {
              nome_info: {"value": valore (int|float), "uom": unità di misura (str)},
              ...
            }
        :return: dizionario di cards {nome_info: {"card": frame, "label": ctk.CTkLabel}}
        """
        cards = {}
        cards_container = ctk.CTkFrame(frame, fg_color="#2b2b2b")
        cards_container.pack(fill="x", expand=True, padx=5, pady=5)
        for name, info in infos_dict.items():
            # crea la card container
            card = ctk.CTkFrame(cards_container, border_width=2, border_color="#2659ab")
            card.pack(anchor="w", padx=10, pady=(5, 5), side="left")

            # titolo
            title = ctk.CTkLabel(
                card,
                text=ViewUtils.split_string_by_length(str(name), 8),
                font=("Arial", 12, "bold"),
                bg_color="#1F6AA5"
            )
            title.pack(anchor="n", padx=10, pady=(10, 5), ipadx = 5, ipady = 5)

            # valore con unità di misura
            value = info.get("value", 0)
            uom = info.get("uom", "")
            amount = ctk.CTkLabel(
                card,
                text=f"{value} {uom}",
                font=("Arial", 14)
            )
            amount.pack(anchor="s", padx=10, pady=(0, 10))

            # conserva la card e la label in output per aggiornamenti futuri
            cards[name] = {"card": card, "label": amount}

        return cards

    @staticmethod
    def construct_tasse_infos_cards(frame, infos_dict) -> dict:
        """
        Costruisce delle "cards" per ogni elemento di infos_dict e le inserisce nel frame fornito.

        :param frame: ctk.CTkFrame in cui inserire le cards
        :param infos_dict: dizionario con struttura:
            {
              nome_info: {"value": valore (int|float), "uom": unità di misura (str)},
              ...
            }
        :return: dizionario di cards {nome_info: {"card": frame, "label": ctk.CTkLabel}}
        """
        cards = {}
        cards_container = ctk.CTkFrame(frame, fg_color="#2b2b2b")
        cards_container.pack(fill="x", expand=True, padx=5, pady=5, anchor="n")
        i = 0
        for name, info in infos_dict.items():
            # crea la card container
            color = "#2659ab" if i > 1 else "gray"
            card = ctk.CTkFrame(cards_container, border_width=2, border_color=color)
            card.pack(anchor="w", padx=10, pady=(5, 5), side="left", fill="both", expand=True)

            # titolo
            title = ctk.CTkLabel(
                card,
                text=ViewUtils.split_string_by_length(str(name), 8),
                font=("Arial", 12, "bold"),
                bg_color=color
            )
            title.pack(anchor="n", padx=10, pady=(10, 25), ipadx = 10, ipady = 10, fill="x")

            # valore con unità di misura
            value = info.get("value", 0)
            uom = info.get("uom", "")
            amount = ctk.CTkLabel(
                card,
                text=f"{value} {uom}",
                font=("Arial", 14)
            )
            amount.pack(anchor="s", padx=10, pady=(0, 10))

            # conserva la card e la label in output per aggiornamenti futuri
            cards[name] = {"card": card, "label": amount}

            i = i + 1

        return cards

    @staticmethod
    def hide_widgets(keys, labels_dict, widgets_dict, save_button):
        """Nasconde i widget e le label specificate."""
        for key in reversed(keys):
            labels_dict[key].pack_forget()
            widgets_dict[key].pack_forget()
        save_button.pack_forget()

    @staticmethod
    def show_widgets(keys, labels_dict, widgets_dict, save_button, label_pady=(35, 0), widget_pady=5):
        """Mostra i widget e le label specificate."""
        for key in keys:
            labels_dict[key].pack(pady=label_pady)
            widgets_dict[key].pack(pady=widget_pady, padx=10, fill="x", expand=True)
        save_button.pack(pady=(50, 15))

    @staticmethod
    def toggle_warning_on_card(card: ctk.CTkFrame, cards_warnings: dict):
        # Cerca il bottone figlio del frame
        button = next((child for child in card.winfo_children() if isinstance(child, ctk.CTkButton)), None)

        if not button:
            return  # Nessun bottone trovato, esce silenziosamente

        button_text = button.cget("text").replace(" ⚠️", "")  # Rimuove warning se già presente

        if button_text in cards_warnings:
            # Applica il warning
            button.configure(text=f"{button_text} ⚠️")
            card.configure(border_width=2, border_color="#e6c719")
        else:
            # Ripristina lo stato normale
            button.configure(text=button_text)
            card.configure(border_width=0)

    @staticmethod
    def add_tooltip(widget, text):
        tooltip = None
        horizontal_offset = 14
        vertical_offset = 18
        screen_margin = 8

        def place_tooltip(event):
            nonlocal tooltip
            if tooltip is None:
                return

            tooltip.update_idletasks()

            tooltip_width = tooltip.winfo_reqwidth()
            tooltip_height = tooltip.winfo_reqheight()
            screen_width = widget.winfo_screenwidth()
            screen_height = widget.winfo_screenheight()

            # Posizione preferita: subito a destra e sotto il puntatore.
            x = event.x_root + horizontal_offset
            y = event.y_root + vertical_offset

            # Se il tooltip uscirebbe a destra, prova a posizionarlo a sinistra.
            if x + tooltip_width + screen_margin > screen_width:
                x = event.x_root - tooltip_width - horizontal_offset

            # Se il tooltip uscirebbe in basso, prova a posizionarlo sopra.
            if y + tooltip_height + screen_margin > screen_height:
                y = event.y_root - tooltip_height - vertical_offset

            # Clamp finale per evitare qualsiasi uscita dallo schermo.
            x = max(screen_margin, min(x, screen_width - tooltip_width - screen_margin))
            y = max(screen_margin, min(y, screen_height - tooltip_height - screen_margin))

            tooltip.wm_geometry(f"+{int(x)}+{int(y)}")

        def show_tooltip(event):
            nonlocal tooltip
            if tooltip or not text:
                return

            tooltip = tk.Toplevel(widget)
            tooltip.wm_overrideredirect(True)
            tooltip.configure(bg="#2a2a2a")

            frame = tk.Frame(tooltip, bg="#2a2a2a", bd=0, highlightthickness=1, highlightbackground="#3a3a3a")
            frame.pack()

            label = tk.Label(frame,
                             text=text,
                             justify="left",
                             bg="#2a2a2a",
                             fg="#f2f2f2",
                             wraplength=500,
                             font=("Segoe UI", 10, "normal"),
                             padx=10,
                             pady=6)
            label.pack()

            place_tooltip(event)

        def hide_tooltip(event):
            nonlocal tooltip
            if tooltip:
                tooltip.destroy()
                tooltip = None

        widget.bind("<Enter>", show_tooltip, add="+")
        widget.bind("<Motion>", place_tooltip, add="+")
        widget.bind("<Leave>", hide_tooltip, add="+")

    @staticmethod
    def create_PIL_image_from_path(path):
        """
        Crea un'immagine PIL dal percorso specificato.

        Args:
            path (str): Percorso del file immagine

        Returns:
            tuple: (success (bool), image (PIL.Image or None))
        """
        # Estensioni supportate da PIL
        supported_extensions = {'.ico', '.png', '.jpg', '.jpeg', '.webp'}

        # Verifica che il file esista
        if not os.path.isfile(path):
            return False, None

        # Verifica l'estensione del file
        file_ext = os.path.splitext(path)[1].lower()
        if file_ext not in supported_extensions:
            return False, None

        try:
            # Apri l'immagine con PIL
            image = Image.open(path)

            # Conserva la trasparenza per formati che la supportano
            if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
                # Mantieni la modalità originale per preservare il canale alfa
                # Non convertire in RGB per immagini con trasparenza
                pass
            elif image.mode != 'RGB':
                # Per immagini senza trasparenza, converti in RGB
                image = image.convert('RGB')

            return True, image

        except Exception as e:
            print(f"Errore nel caricamento dell'immagine {path}: {str(e)}")
            return False, None

    @staticmethod
    def toggle_entry_visibility(entry_widget):
        """
        Alterna tra la visualizzazione del testo normale e asterischi per un entry widget.

        Args:
            entry_widget: Il widget CTkEntry di cui alternare la visibilità
        """
        current_show = entry_widget.cget("show")
        if current_show == "":
            entry_widget.configure(show="*")  # Nascondi il testo
        else:
            entry_widget.configure(show="")  # Mostra il testo in chiaro

    @staticmethod
    def process_items_in_chunks(widget, items_list, add_card_callback, extract_args_callback,
                                chunk_size=25, delay=50, cleanup_callback=None, cards_frame=None):
        """
        Versione migliorata con cleanup e gestione memoria
        """
        # Rimuovi tutti i widget figli esistenti solo dal frame delle cards
        for child in cards_frame.winfo_children():
            child.destroy()

        if not items_list or len(items_list) == 0:
            if cards_frame is not None:
                # Mostra messaggio per lista vuota
                empty_label = ctk.CTkLabel(
                    cards_frame,
                    text="Nessun item presente nel periodo di tempo selezionato",
                    font=("Arial", 16),
                    text_color="gray",
                    height=100
                )
                empty_label.pack(fill="both", expand=True, pady=50)
            return

        chunks = [
            items_list[i:i + chunk_size]
            for i in range(0, len(items_list), chunk_size)
        ]

        current_chunk_index = 0
        processed_items = 0

        def process_next_chunk():
            nonlocal current_chunk_index, processed_items

            if current_chunk_index >= len(chunks):
                if cleanup_callback:
                    cleanup_callback()
                return

            current_chunk = chunks[current_chunk_index]

            for item in current_chunk:
                try:
                    args = extract_args_callback(item)
                    add_card_callback(*args)
                    processed_items += 1
                except Exception as e:
                    print(f"Errore nel processare item: {e}")

            # Force UI update
            widget.update_idletasks()

            # Cleanup periodico ogni 3 chunk
            if current_chunk_index % 3 == 0 and cleanup_callback:
                cleanup_callback()

            current_chunk_index += 1
            if current_chunk_index < len(chunks):
                widget.after(delay, process_next_chunk)
            else:
                if cleanup_callback:
                    cleanup_callback()
                print(f"Processati {processed_items} elementi in {len(chunks)} chunk")

        process_next_chunk()

    @staticmethod
    def create_extractor_for_expenses(supplier_controller:"SupplierController", user_controller:"UserController", account_controller:"AccountController"):
        """
        Crea una funzione di estrazione parametri specifica per le spese
        Restituisce una funzione che può essere usata come extract_args_callback
        """

        def extract_expense_args(expense):
            expense_id = expense[DBExpensesColumns.ID.value]
            name = expense[DBExpensesColumns.NAME.value]
            net_amount = expense[DBExpensesColumns.NET_AMOUNT.value]
            amount = expense[DBExpensesColumns.TOT_AMOUNT.value]
            supplier_id = expense[DBExpensesColumns.SUPPLIER_ID.value]
            supplier = supplier_controller.retrieve_supplier_map_by_id(supplier_id)
            supplier_name = supplier[DBSuppliersColumns.NAME.value]
            date = expense[DBExpensesColumns.DATE.value]
            category = expense[DBExpensesColumns.CATEGORY.value]
            deducibile = expense[DBExpensesColumns.DEDUCIBILE.value]
            user_id = expense[DBExpensesColumns.USER_ID_DEDUZIONE.value]

            if user_id:
                user = user_controller.retrieve_user_map_by_id(user_id)
                user_first = user[DBUsersColumns.FIRST_NAME.value]
                user_second = user[DBUsersColumns.LAST_NAME.value]
                user_name = user_first + " " + user_second
            else:
                user_name = " ---- "

            account = account_controller.retrieve_account_map_by_id(
                expense[DBExpensesColumns.ACCOUNT_ID.value]
            )
            account_name = account[DBAccountsColumns.NAME.value] if account else "conto non trovato"

            return (expense_id, name, supplier_name, net_amount, amount,
                    category, date, deducibile, user_name, account_name)

        return extract_expense_args

    @staticmethod
    def create_extractor_for_clients(client_analyzer_service:"ClientAnalyzerService"):
        """
        Crea una funzione di estrazione parametri specifica per i clienti
        """

        def extract_client_args(client):
            client_id = client[DBClientsColumns.ID.value]
            name = client[DBClientsColumns.NAME.value]

            # Costruisci i dati aggregati per singolo cliente
            aggregate_data = client_analyzer_service.construct_client_map_aggregate_data(client_id, year=-1)

            return (
                client_id,
                name,
                round(aggregate_data[ClientsAggregateData.TOT_ENTRATE.value], 2),
                aggregate_data[ClientsAggregateData.NUM_FATTURE.value],
                round(aggregate_data[ClientsAggregateData.MEDIA_FATTURE.value], 2),
                round(aggregate_data[ClientsAggregateData.TOT_CREDITI.value], 2),
                round(aggregate_data[ClientsAggregateData.TOT_RIMBORSI.value], 2),
                round(aggregate_data[ClientsAggregateData.PAGAM_ORARIO_MEDIO.value], 2),
                aggregate_data[ClientsAggregateData.TOT_GIORNI_RIT.value],
                round(aggregate_data[ClientsAggregateData.MEDIA_RITARDO.value], 2)
            )

        return extract_client_args

    @staticmethod
    def create_extractor_for_invoices(clients_query_service:"ClientQueryService", user_controller:"UserController", production_controller:"ProductionController"):
        """
        Crea una funzione di estrazione parametri specifica per le fatture
        """

        def extract_invoice_args(invoice):
            invoice_id = invoice[DBInvoicesColumns.ID.value]
            invoice_name = invoice[DBInvoicesColumns.NUMERO_FATTURA.value]
            invoice_client_ID = invoice[DBInvoicesColumns.ID_CLIENTE.value]
            invoice_client_name = clients_query_service.retrieve_client_map_by_id(invoice_client_ID)[
                DBClientsColumns.NAME.value]
            invoice_user_id = invoice[DBInvoicesColumns.ID_UTENTE.value]
            user_map = user_controller.retrieve_user_map_by_id(invoice_user_id)
            invoice_user_name = f"{user_map[DBUsersColumns.FIRST_NAME.value]} {user_map[DBUsersColumns.LAST_NAME.value]}"
            invoice_creation_date = invoice[DBInvoicesColumns.DATA_CREAZIONE.value]
            invoice_state = invoice[DBInvoicesColumns.STATUS.value]
            invoice_rate = invoice[DBInvoicesColumns.NUMERO_RATE.value]
            invoice_tot_documento = invoice[DBInvoicesColumns.NETTO_A_PAGARE.value]
            invoice_tipologia = invoice[DBInvoicesColumns.TIPO.value]
            invoice_production_id = invoice[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value]

            production = production_controller.retrieve_production_map_by_id(invoice_production_id)
            if production:
                invoice_production_name = production[DBProductionsColumns.NAME.value]
            else:
                invoice_production_name = "Produzione non trovata"

            return (
                invoice_id,
                invoice_name,
                invoice_client_name,
                invoice_user_name,
                invoice_production_name,
                invoice_creation_date,
                invoice_state,
                invoice_rate,
                invoice_tot_documento,
                invoice_tipologia
            )

        return extract_invoice_args

    @staticmethod
    def create_extractor_for_payments(invoice_controller:"InvoiceController", clients_query_service:"ClientQueryService", production_controller:"ProductionController",
                                      account_controller:"AccountController"):
        """
        Crea una funzione di estrazione parametri specifica per i pagamenti
        """

        def extract_payment_args(payment):
            payment_id = payment[DBPaymentsColumns.ID.value]
            name = payment[DBPaymentsColumns.PAYMENT_NAME.value]
            amount = payment[DBPaymentsColumns.PAYMENT_AMOUNT.value]
            payment_date = payment[DBPaymentsColumns.PAYMENT_DATE.value]
            linked_rata = payment[DBPaymentsColumns.LINKED_RATA.value]
            invoice_id = payment[DBPaymentsColumns.INVOICE_ID.value]
            invoice = invoice_controller.retrieve_invoice_map_by_id(invoice_id)
            invoice_name = invoice[DBInvoicesColumns.NUMERO_FATTURA.value]
            cliente_id = invoice[DBInvoicesColumns.ID_CLIENTE.value]
            client = clients_query_service.retrieve_client_map_by_id(cliente_id)
            client_name = client[DBClientsColumns.NAME.value]
            production_id = invoice[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value]
            production = production_controller.retrieve_production_map_by_id(production_id)
            production_name = production[DBProductionsColumns.NAME.value] if production else "Produzione non trovata"
            conto = account_controller.retrieve_account_map_by_id(payment[DBPaymentsColumns.CONTO_ID.value])
            nome_conto = conto[DBAccountsColumns.NAME.value] if conto else "conto non trovato"

            return (
                payment_id,
                name,
                amount,
                payment_date,
                linked_rata,
                client_name,
                production_name,
                invoice_name,
                nome_conto
            )

        return extract_payment_args

    @staticmethod
    def create_extractor_for_productions(production_analyzer_service:"ProductionAnalyzerService", clients_query_service:"ClientQueryService"):
        """
        Crea una funzione di estrazione parametri specifica per le produzioni
        """

        def extract_production_args(production):
            production_id = production[DBProductionsColumns.ID.value]
            production_name = production[DBProductionsColumns.NAME.value]
            client_id = production[DBProductionsColumns.CLIENT_ID.value]
            client_name = clients_query_service.retrieve_client_map_by_id(client_id)[DBClientsColumns.NAME.value]
            tipologia_produzione = production[DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value]
            tipologia_output = production[DBProductionsColumns.TIPOLOGIA_OUTPUT.value]
            produzione_stato = production[DBProductionsColumns.STATO.value]
            data_di_consegna = production[DBProductionsColumns.END_DATE.value]
            totale_preventivo = production[DBProductionsColumns.TOTALE_PREVENTIVO.value]
            durata_produzione = production[DBProductionsColumns.HOURS.value]
            prezzo_orario = production_analyzer_service.calculate_production_cost_per_hour(production_id)

            return (
                production_id,
                production_name,
                client_name,
                tipologia_produzione,
                tipologia_output,
                produzione_stato,
                data_di_consegna,
                totale_preventivo,
                durata_produzione,
                prezzo_orario
            )

        return extract_production_args

    @staticmethod
    def create_extractor_for_refunds(clients_query_service:"ClientQueryService", account_controller:"AccountController"):
        """
        Crea una funzione di estrazione parametri specifica per i rimborsi
        """

        def extract_refund_args(refund):
            refund_id = refund[DBRefundsColumns.ID.value]
            refund_name = refund[DBRefundsColumns.REFUND_NAME.value]
            amount = refund[DBRefundsColumns.REFUND_AMOUNT.value]
            refund_date = refund[DBRefundsColumns.REFUND_DATE.value]
            cliente_id = refund[DBRefundsColumns.CLIENT_ID.value]
            client = clients_query_service.retrieve_client_map_by_id(cliente_id)
            client_name = client[DBClientsColumns.NAME.value]
            conto = account_controller.retrieve_account_map_by_id(refund[DBRefundsColumns.CONTO_ID.value])
            nome_conto = conto[DBAccountsColumns.NAME.value] if conto else "conto non trovato"

            return (
                refund_id,
                refund_name,
                amount,
                refund_date,
                client_name,
                nome_conto
            )

        return extract_refund_args

    @staticmethod
    def create_extractor_for_salaries(user_controller:"UserController", account_controller:"AccountController"):
        """
        Crea una funzione di estrazione parametri specifica per gli stipendi
        """

        def extract_salary_args(salary):
            salary_id = salary[DBSalariesColumns.ID.value]
            salary_name = salary[DBSalariesColumns.NAME.value]
            amount = salary[DBSalariesColumns.AMOUNT.value]
            date = salary[DBSalariesColumns.DATE.value]
            user_id = salary[DBSalariesColumns.USER_ID.value]

            if user_id:
                user = user_controller.retrieve_user_map_by_id(user_id)
                user_first = user[DBUsersColumns.FIRST_NAME.value]
                user_second = user[DBUsersColumns.LAST_NAME.value]
                user_name = user_first + " " + user_second
            else:
                user_name = " ---- "

            account = account_controller.retrieve_account_map_by_id(salary[DBSalariesColumns.ACCOUNT_ID.value])
            account_name = account[DBAccountsColumns.NAME.value] if account else "conto non trovato"

            return (
                salary_id,
                salary_name,
                user_name,
                amount,
                date,
                account_name
            )

        return extract_salary_args

    @staticmethod
    def create_extractor_for_suppliers(suppliers_analyzer_service: "SupplierAnalyzerService"):
        """
        Crea una funzione di estrazione parametri specifica per i fornitori
        """

        def extract_supplier_args(supplier):
            supplier_id = supplier[DBSuppliersColumns.ID.value]
            supplier_name = supplier[DBSuppliersColumns.NAME.value]
            partita_iva = supplier[DBSuppliersColumns.PARTITA_IVA.value]
            note = supplier[DBSuppliersColumns.NOTE.value]
            contatto = supplier[DBSuppliersColumns.CONTATTO.value]

            # Costruisci i dati aggregati per singolo fornitore
            aggregate_data = suppliers_analyzer_service.construct_supplier_map_aggregate_data(supplier_id)

            return (
                supplier_id,
                supplier_name,
                partita_iva,
                aggregate_data[SupplierAggregateData.NUM_SPESE.value],
                round(aggregate_data[SupplierAggregateData.MEDIA_SPESE.value], 2),
                round(aggregate_data[SupplierAggregateData.TOT_SPESE.value], 2),
                note,
                contatto
            )

        return extract_supplier_args


class FilterableComboBox(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        values,
        placeholder="Seleziona...",
        autofill=False,
        command=None,
        show_add_button=False,
        add_button_text="",
        add_button_command=None,
        state=ctk.NORMAL,
        **kwargs
    ):
        super().__init__(parent, **kwargs)

        self.state = state
        self._text_color = "#c2c2c2"
        self._disabled_text_color = "#636363"

        self.all_values = self._sort_values(values)
        self.filtered_values = self.all_values.copy()
        self.autofill = autofill
        self.command = command
        self.show_add_button = show_add_button
        self.add_button_text = add_button_text
        self.add_button_command = add_button_command
        self.current_value = ""
        self.parent = parent

        self.y_shift = 27

        self.interaction_frame = ctk.CTkFrame(self)
        self.interaction_frame.pack(fill="x")
        # Entry per la ricerca
        if not autofill:
            self.entry = ctk.CTkEntry(self.interaction_frame, placeholder_text=placeholder)
        else:
            try:
                self.entry = ctk.CTkEntry(self.interaction_frame)
                self.current_value = self.all_values[0]
                self.entry.insert(0, self.all_values[0])

            except IndexError:
                self.entry = ctk.CTkEntry(self, placeholder_text="NO VALUES")
                return

        self.entry.pack(fill="x", expand=True, side="left")

        self.dropdown_button_status = False

        self.dropdown_button = ctk.CTkButton(self.interaction_frame, text=">", command=self._on_dropdown_icon_click, width=30)
        self.dropdown_button.pack(fill="x", side="right")

        self.message_label = ctk.CTkLabel(self, text="", anchor="w")
        self.message_label.pack(fill="x", expand=True)


        self.entry.bind("<KeyRelease>", self._on_key_release)
        # apri dropdown anche su click esplicito nell'entry
        self.entry.bind("<Button-1>", self._on_entry_click, add="+")
        self.entry.bind("<FocusOut>", self._on_focus_out)

        #colors
        self.default_border_color = self.entry.cget("border_color")
        self.warning_color = "#e39e27"

        # Dropdown
        self.dropdown_window = None
        self.dropdown_container = None
        self.dropdown_frame = None
        self.dropdown_add_button = None
        self.dropdown_visible = False
        self.current_selection_index = -1
        self.dropdown_buttons = []

        # Tracciamento movimento
        self._last_x = None
        self._last_y = None
        self._tracking_movement = False

        # Per gestire i bind mousewheel fatti sul dropdown e figli (per poterli rimuovere)
        self._mousewheel_bound_widgets = []

        # Per bind di eventi sul parent (bind una tantum)
        self._parent_events_bound = False

        self._apply_state()

    def _sort_values(self, values):
        return sorted(values, key=lambda value: str(value).casefold()) if values else []

    def _is_disabled(self):
        return self.state == ctk.DISABLED

    def _apply_state(self):
        entry_text_color = self._disabled_text_color if self._is_disabled() else self._text_color
        self.entry.configure(state=self.state, text_color=entry_text_color)
        self.dropdown_button.configure(state=self.state)
        if self.dropdown_add_button is not None:
            self.dropdown_add_button.configure(state=self.state)
        if self._is_disabled() and self.dropdown_visible:
            self._hide_dropdown()
            self._configure_dropdown_button()

    # --- Entry click: mostra sempre il dropdown (evita dipendere solo da focus events) ---
    def _on_entry_click(self, event):
        if self._is_disabled():
            return "break"
        self._show_dropdown_with_current_filter()
        return None

    def _on_dropdown_icon_click(self):
        if self._is_disabled():
            return

        if not self.dropdown_visible:
            self._show_dropdown_with_current_filter()
        else:
            self._close_dropdown()

    def _configure_dropdown_button(self):
        if self.dropdown_visible:
            self.dropdown_button.configure(text="<")
        else:
            self.dropdown_button.configure(text=">")

    def _on_focus_out(self, event):
        if self._is_disabled():
            return
        # Ritarda la chiusura per permettere click su elementi del dropdown
        self.after(200, self._check_focus)

    def _check_focus(self):
        focused_widget = self.focus_get()

        entry_has_focus = (focused_widget == self.entry)
        dropdown_has_focus = focused_widget in self._get_dropdown_widgets()

        # Se né entry né dropdown hanno focus → chiudi dropdown
        if not entry_has_focus and not dropdown_has_focus:

            # Ora chiudiamo il dropdown
            self._close_dropdown()

    def _close_dropdown(self):
        # Prima di chiudere: validiamo il contenuto dell'entry
        self._validate_or_autofix_entry_value()

        # Ora chiudiamo il dropdown
        x, y = self.winfo_pointerx(), self.winfo_pointery()
        widget_under_pointer = self.winfo_containing(x, y)

        if widget_under_pointer is None or widget_under_pointer not in self._get_dropdown_widgets():
            self._hide_dropdown()

        self._configure_dropdown_button()

    def _validate_or_autofix_entry_value(self):
        current = self.entry.get().strip()

        # Lista dei valori compatibili col filtro attuale
        valid_values = self.filtered_values

        if current not in valid_values:
            # Imposta il primo valore valido
            self.entry.delete(0, ctk.END)
            self.entry.insert(0, valid_values[0] if valid_values else self.all_values[0])
            self.entry.configure(border_color=self.warning_color)
            self.message_label.configure(text="Selezione dell'utente assente: valore selezionato in automatico dalla lista", text_color=self.warning_color)
        else:
            self.entry.configure(border_color=self.default_border_color)
            self.message_label.configure(text="",
                                         text_color="white")


    def _on_key_release(self, event):
        if self._is_disabled():
            return
        search_text = self.entry.get().lower()
        if not search_text:
            self.filtered_values = self.all_values.copy()
        else:
            self.filtered_values = [v for v in self.all_values if search_text in v.lower()]

        self._update_dropdown()
        if self.dropdown_visible:
            self._update_dropdown_position()
        if not self.dropdown_visible and self.filtered_values:
            self._show_dropdown()

    def _show_dropdown_with_current_filter(self):
        if self._is_disabled():
            return
        current_text = self.entry.get().lower()
        if not current_text:
            self.filtered_values = self.all_values.copy()
        else:
            self.filtered_values = [value for value in self.all_values if current_text in value.lower()]

        self._update_dropdown()
        self._show_dropdown()
        self._configure_dropdown_button()

    def _update_dropdown(self):
        if self.dropdown_frame is None:
            return

        list_height, dropdown_height = self._calculate_dropdown_heights()
        if self.dropdown_container is not None:
            self.dropdown_container.configure(height=dropdown_height)
        if self.dropdown_frame is not None:
            self.dropdown_frame.configure(height=list_height)
        if self.dropdown_window is not None and self.dropdown_visible:
            self.dropdown_window.geometry(f"{int(self.winfo_width() * 8 / 9)}x{dropdown_height}+{self.winfo_rootx()}+{self.winfo_rooty() + self.winfo_height() - self.y_shift}")

        for widget in self.dropdown_frame.winfo_children():
            widget.destroy()

        if not self.filtered_values:
            empty_label = ctk.CTkLabel(self.dropdown_frame, text="Nessun risultato", text_color="gray", height=30)
            empty_label.pack(fill="x", padx=2, pady=1)
            self.dropdown_buttons = []
            if self.dropdown_add_button is not None:
                button_state = self.entry.cget("state")
            self.dropdown_add_button.configure(
                text=self.add_button_text,
                state=button_state
            )
            return

        self.dropdown_buttons = []
        for i, value in enumerate(self.filtered_values):
            btn = ctk.CTkButton(
                self.dropdown_frame,
                text=value,
                fg_color="transparent",
                text_color=("black", "white"),
                hover_color=("#F0F0F0", "#2A2A2A"),
                anchor="w",
                height=30,
                command=lambda v=value: self._on_dropdown_button_clicked(v)  # <- usa command
            )

            btn.pack(fill="x", padx=2, pady=1)

            self.dropdown_buttons.append(btn)

        self.current_selection_index = -1

        if self.dropdown_add_button is not None:
            button_state = self.entry.cget("state")
            self.dropdown_add_button.configure(
                text=self.add_button_text,
                state=button_state
            )

    def _calculate_dropdown_heights(self):
        visible_rows = min(max(len(self.filtered_values), 1), 8)
        list_height = visible_rows * 32 + 14
        add_button_height = 34 if self.show_add_button and self.add_button_command else 0
        total_height = list_height + add_button_height
        return list_height, total_height

    def _on_dropdown_button_clicked(self, value):
        # aggiorna l'entry PRIMA di nascondere per evitare race con focus/close
        self.entry.delete(0, "end")
        self.entry.insert(0, value)
        self.current_value = value
        if self.command:
            try:
                self.command(value)
            except Exception:
                pass
        # nascondi solo DOPO aver aggiornato
        self._hide_dropdown()

    def _on_add_button_clicked(self):
        if self._is_disabled():
            return
        self._hide_dropdown()
        if self.add_button_command:
            self.after(10, self.add_button_command)

    def _show_dropdown(self):
        if self._is_disabled():
            return
        if self.dropdown_visible:
            self._update_dropdown()
            self._update_dropdown_position()
            return

        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() - self.y_shift

        dropdown_width = int(self.winfo_width() *8/ 9)
        list_height, dropdown_height = self._calculate_dropdown_heights()

        # Crea una finestra Toplevel con larghezza personalizzata
        self.dropdown_window = Toplevel(self, bg="#545454", height=dropdown_height)
        self.dropdown_window.wm_overrideredirect(True)
        self.dropdown_window.wm_geometry(f"{dropdown_width}x{dropdown_height}+{x}+{y}")


        self.dropdown_window.configure(borderwidth=2)
        self.dropdown_window.attributes("-topmost", True)

        self.dropdown_container = ctk.CTkFrame(
            self.dropdown_window,
            fg_color="#3d3d3d"
        )
        self.dropdown_container.pack(fill="both", expand=True)
        self.dropdown_container.grid_columnconfigure(0, weight=1)
        self.dropdown_container.grid_rowconfigure(0, weight=1)
        self.dropdown_container.grid_propagate(False)
        self.dropdown_container.configure(width=dropdown_width, height=dropdown_height)

        self.dropdown_frame = ctk.CTkScrollableFrame(
            self.dropdown_container,
            width=dropdown_width,
            height=list_height,
            fg_color="#3d3d3d"
        )
        self.dropdown_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        if self.show_add_button and self.add_button_command:
            self.dropdown_add_button = ctk.CTkButton(
                self.dropdown_container,
                text=self.add_button_text,
                command=self._on_add_button_clicked,
                height=22
            )
            self.dropdown_container.grid_rowconfigure(1, weight=0)
            self.dropdown_add_button.grid(row=1, column=0, sticky="ew", padx=4, pady=(4, 4))
        else:
            self.dropdown_add_button = None

        self._update_dropdown()
        self._apply_state()

        self.dropdown_visible = True

        # Bind locali: focusout del dropdown e mouse wheel su dropdown
        self.dropdown_window.bind("<FocusOut>", lambda e: self.after(100, self._check_focus), add="+")
        self.dropdown_window.bind("<MouseWheel>", self._on_mousewheel, add="+")
        self.dropdown_window.bind("<Button-4>", self._on_mousewheel_linux, add="+")
        self.dropdown_window.bind("<Button-5>", self._on_mousewheel_linux, add="+")

        # Bindiamo la rotella su tutti i figli del dropdown (non globalmente)
        self._bind_mousewheel_to_children(self.dropdown_window)

        # Bind agli eventi parent (una tantum)
        self._bind_to_parent_events()

        # Inizia a tracciare la posizione
        self._start_tracking_movement()

    def _bind_to_parent_events(self):
        # Assicuriamoci di bindare gli eventi del parent solo una volta
        if self._parent_events_bound:
            return
        parent_window = self.winfo_toplevel()
        parent_window.bind("<Configure>", self._on_parent_configure, add="+")
        # Non bindiamo ButtonPress globali che causano conflitti
        self._parent_events_bound = True

    def _on_parent_configure(self, event):
        if self.dropdown_visible:
            # se la finestra si sposta/ridimensiona, chiudiamo il dropdown
            self._hide_dropdown()

    # --- binding mousewheel solo sui widget del dropdown (non globali) ---
    def _bind_mousewheel_to_children(self, widget):
        # pulisci lista precedente (se presente)
        self._mousewheel_bound_widgets = []

        def _bind_recursive(w):
            try:
                # bind mousewheel per Windows/Mac
                w.bind("<MouseWheel>", self._on_mousewheel, add="+")
                w.bind("<Button-4>", self._on_mousewheel_linux, add="+")
                w.bind("<Button-5>", self._on_mousewheel_linux, add="+")
                self._mousewheel_bound_widgets.append(w)
            except Exception:
                pass
            for child in w.winfo_children():
                _bind_recursive(child)

        _bind_recursive(widget)

    def _unbind_mousewheel_from_children(self):
        # rimuovi i binding che abbiamo aggiunto sui widget creati
        for w in self._mousewheel_bound_widgets:
            try:
                w.unbind("<MouseWheel>")
                w.unbind("<Button-4>")
                w.unbind("<Button-5>")
            except Exception:
                pass
        self._mousewheel_bound_widgets = []

    def _on_mousewheel(self, event):
        # scrolla il canvas del dropdown e interrompi la propagazione
        if self.dropdown_frame:
            try:
                scroll_amount = int(-25 * (event.delta / 120))
                self.dropdown_frame._parent_canvas.yview_scroll(scroll_amount, "units")
            except Exception:
                # fallback generico: prova spostare di 1 unità
                try:
                    self.dropdown_frame._parent_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                except Exception:
                    pass
        return "break"

    def _on_mousewheel_linux(self, event):
        if self.dropdown_frame:
            try:
                if event.num == 4:
                    self.dropdown_frame._parent_canvas.yview_scroll(-25, "units")
                elif event.num == 5:
                    self.dropdown_frame._parent_canvas.yview_scroll(25, "units")
            except Exception:
                pass
        return "break"

    def _start_tracking_movement(self):
        self._last_x = self.winfo_rootx()
        self._last_y = self.winfo_rooty()
        self._tracking_movement = True
        self._check_movement()

    def _check_movement(self):
        if not self._tracking_movement or not self.dropdown_visible:
            return
        current_x = self.winfo_rootx()
        current_y = self.winfo_rooty()
        if current_x != self._last_x or current_y != self._last_y:
            self._last_x = current_x
            self._last_y = current_y
            self._update_dropdown_position()
        self.after(50, self._check_movement)

    def _update_dropdown_position(self):
        if self.dropdown_window and self.dropdown_visible:
            x = self.winfo_rootx()
            y = self.winfo_rooty() + self.winfo_height() - self.y_shift
            dropdown_width = int(self.winfo_width() * 8 / 9)
            _, dropdown_height = self._calculate_dropdown_heights()
            self.dropdown_window.wm_geometry(f"{dropdown_width}x{dropdown_height}+{x}+{y}")

    def _hide_dropdown(self):
        if self.dropdown_visible:
            self._tracking_movement = False
            # rimuovi i binding mousewheel che abbiamo applicato
            try:
                self._unbind_mousewheel_from_children()
            except Exception:
                pass

            if self.dropdown_window:
                try:
                    self.dropdown_window.destroy()
                except Exception:
                    pass
                self.dropdown_window = None
                self.dropdown_container = None
                self.dropdown_frame = None
                self.dropdown_add_button = None
            self.dropdown_visible = False
            self.current_selection_index = -1
            self.dropdown_buttons = []

    def _get_dropdown_widgets(self):
        widgets = []
        if self.dropdown_window:
            widgets.append(self.dropdown_window)
            widgets.extend(self.dropdown_window.winfo_children())
            if self.dropdown_frame:
                widgets.extend(self.dropdown_frame.winfo_children())
        return widgets

    def get_value(self):
        return self.current_value

    def set_value(self, value, safe_mode=True):
        if safe_mode:
            if value in self.all_values:
                self.entry.delete(0, "end")
                self.entry.insert(0, value)
                self.current_value = value
        else:
            self.entry.delete(0, "end")
            self.entry.insert(0, value)
            self.current_value = value

    def clear_value(self):
        self.entry.delete(0, "end")
        self.current_value = ""

    def set_values(self, values, preserve_current=True):
        current = self.get_value()
        self.all_values = self._sort_values(values)
        self.filtered_values = self.all_values.copy()

        if preserve_current and current in self.all_values:
            self.set_value(current)
            return

        if self.all_values:
            self.set_value(self.all_values[0], safe_mode=False)
        else:
            self.clear_value()

        if self.dropdown_visible:
            self._update_dropdown()
            self._update_dropdown_position()

    def configure(self, require_redraw=False, **kwargs):
        state = kwargs.pop("state", None)
        text_color = kwargs.pop("text_color", None)
        if text_color is not None:
            self._text_color = text_color
        if state is not None:
            self.state = state
        super().configure(require_redraw=require_redraw, **kwargs)
        if state is not None or text_color is not None:
            self._apply_state()

    config = configure

    def cget(self, attribute_name):
        if attribute_name == "state":
            return self.state
        if attribute_name == "text_color":
            return self._text_color
        return super().cget(attribute_name)

    def destroy(self):
        # rimuovi binding e dropdown in modo sicuro
        try:
            self._hide_dropdown()
        except Exception:
            pass
        super().destroy()


class CustomTkMenuButton(tk.Menubutton):
    """
    Menubutton tkinter con stile dark e API semplificata:
    items = [
        ("Impostazioni backup", callback1),
        ("Carica un backup", callback2),
    ]
    """

    def __init__(self, parent, text, items=None, **kwargs):
        # ---- DEFAULT STYLING (centralizzato) ----
        defaults = {
            "relief": "raised",
            "bd": 0,
            "bg": "#595959",
            "fg": "white",
            "activebackground": "#1665b5",
            "activeforeground": "white",
            "padx": 8,
            "pady": 6,
            "anchor": "w",
            "font": ("Segoe UI", 10),
        }

        # permetti override puntuale
        cfg = {**defaults, **kwargs}

        super().__init__(
            parent,
            text=text,
            relief=cfg["relief"],
            bd=cfg["bd"],
            bg=cfg["bg"],
            fg=cfg["fg"],
            activebackground=cfg["activebackground"],
            activeforeground=cfg["activeforeground"],
            padx=cfg["padx"],
            pady=cfg["pady"],
            anchor=cfg["anchor"],
            font=cfg["font"],
        )

        # ---- MENU ----
        self.menu = tk.Menu(
            self,
            tearoff=0,
            bg=cfg["bg"],
            fg=cfg["fg"],
            activebackground=cfg["activebackground"],
            activeforeground=cfg["activeforeground"],
            bd=0,
            relief="flat",
            font=cfg["font"],
        )

        self.configure(menu=self.menu)

        if items:
            self.set_items(items)

        # ---- Hover effect (simile CTk) ----
        self._normal_bg = cfg["bg"]
        self._hover_bg = cfg.get("hover", "#1f1f1f")

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    # ---------- API PUBBLICA ----------

    def set_items(self, items):
        """
        items: iterable di tuple (label, command)
        """
        self.menu.delete(0, "end")

        for label, command in items:
            if not callable(command):
                raise ValueError(f"Command for menu item '{label}' is not callable")

            self.menu.add_command(label=label, command=command)

    def add_item(self, label, command):
        if not callable(command):
            raise ValueError("command must be callable")

        self.menu.add_command(label=label, command=command)

    # ---------- Hover handlers ----------

    def _on_enter(self, _):
        self.configure(bg=self._hover_bg, activebackground=self._hover_bg)

    def _on_leave(self, _):
        self.configure(bg=self._normal_bg, activebackground=self._normal_bg)








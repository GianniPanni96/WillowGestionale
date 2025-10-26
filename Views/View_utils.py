from enum import Enum
import customtkinter as ctk
import tkinter as tk
from PIL import Image
import os

from Model import DBExpensesColumns, DBSuppliersColumns, DBUsersColumns, DBAccountsColumns, DBSalariesColumns, DBRefundsColumns
from Model import DBProductionsColumns, DBPaymentsColumns, DBInvoicesColumns, DBClientsColumns, DBTransfersColumns

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

            # Calcola dimensioni del tooltip
            tooltip.update_idletasks()  # Forza il calcolo delle dimensioni

            # Offset personalizzabile (regola questo valore in base alle tue esigenze)
            vertical_offset = -170  # Sposta il tooltip 100px sopra il puntatore

            # Calcola posizione finale
            x = event.x_root + 15
            y = event.y_root + vertical_offset

            # Controllo per evitare che il tooltip esca dallo schermo in alto
            screen_height = widget.winfo_screenheight()
            if y < 0:
                # Se il tooltip andrebbe sopra lo schermo, mostralo sotto il puntatore
                y = event.y_root + 20

            # Controllo per evitare che il tooltip esca dallo schermo a destra
            tooltip_width = tooltip.winfo_width()
            screen_width = widget.winfo_screenwidth()
            if (x + tooltip_width) > screen_width:
                x = screen_width - tooltip_width - 10  # 10px di margine

            tooltip.wm_geometry(f"+{int(x)}+{int(y)}")

        def hide_tooltip(event):
            nonlocal tooltip
            if tooltip:
                tooltip.destroy()
                tooltip = None

        widget.bind("<Enter>", show_tooltip)
        widget.bind("<Leave>", hide_tooltip)

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
    def process_items_in_chunks(widget, items_list, add_card_callback, extract_args_callback, chunk_size=10, delay=100):
        """
        Processa una lista di elementi in chunk separati per non bloccare l'interfaccia

        Args:
            widget: Il widget CTk che contiene il metodo after()
            items_list: Lista generica di elementi da processare
            add_card_callback: Funzione callback per aggiungere una card
            extract_args_callback: Funzione che estrae gli argomenti da un elemento della lista
            chunk_size: Dimensione di ogni chunk (default: 30)
            delay: Delay tra i chunk in ms (default: 10)
        """
        if not items_list:
            return

        # Dividi la lista in chunk
        chunks = [
            items_list[i:i + chunk_size]
            for i in range(0, len(items_list), chunk_size)
        ]

        # Processa il primo chunk
        current_chunk_index = 0

        def process_next_chunk():
            nonlocal current_chunk_index

            if current_chunk_index >= len(chunks):
                return  # Tutti i chunk sono stati processati

            current_chunk = chunks[current_chunk_index]

            for item in current_chunk:
                # Estrai gli argomenti usando la callback fornita
                args = extract_args_callback(item)
                # Chiama la funzione di aggiunta card con gli argomenti estratti
                add_card_callback(*args)

            # Programma il prossimo chunk
            current_chunk_index += 1
            if current_chunk_index < len(chunks):
                widget.after(delay, process_next_chunk)

        # Avvia il processing
        process_next_chunk()

    @staticmethod
    def create_extractor_for_expenses(expense_controller, supplier_controller, user_controller, account_controller):
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
    def create_extractor_for_clients(client_controller):
        """
        Crea una funzione di estrazione parametri specifica per i clienti
        """

        def extract_client_args(client):
            client_id = client[DBClientsColumns.ID.value]
            name = client[DBClientsColumns.NAME.value]

            # Costruisci i dati aggregati per singolo cliente
            aggregate_data = client_controller.construct_client_map_aggregate_data(client_id)

            return (
                client_id,
                name,
                round(aggregate_data[client_controller.Aggregate_data.TOT_ENTRATE.value], 2),
                aggregate_data[client_controller.Aggregate_data.NUM_FATTURE.value],
                round(aggregate_data[client_controller.Aggregate_data.MEDIA_FATTURE.value], 2),
                round(aggregate_data[client_controller.Aggregate_data.TOT_CREDITI.value], 2),
                round(client_controller.calcola_tot_rimborsi_by_client(client_id)),
                round(aggregate_data[client_controller.Aggregate_data.PAGAM_ORARIO_MEDIO.value], 2),
                aggregate_data[client_controller.Aggregate_data.TOT_GIORNI_RIT.value],
                round(aggregate_data[client_controller.Aggregate_data.MEDIA_RITARDO.value], 2)
            )

        return extract_client_args

    @staticmethod
    def create_extractor_for_invoices(invoice_controller, client_controller, user_controller, production_controller):
        """
        Crea una funzione di estrazione parametri specifica per le fatture
        """

        def extract_invoice_args(invoice):
            invoice_id = invoice[DBInvoicesColumns.ID.value]
            invoice_name = invoice[DBInvoicesColumns.NUMERO_FATTURA.value]
            invoice_client_ID = invoice[DBInvoicesColumns.ID_CLIENTE.value]
            invoice_client_name = client_controller.retrieve_client_map_by_id(invoice_client_ID)[
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
    def create_extractor_for_payments(payment_controller, invoice_controller, client_controller, production_controller,
                                      account_controller):
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
            client = client_controller.retrieve_client_map_by_id(cliente_id)
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
    def create_extractor_for_productions(production_controller, client_controller):
        """
        Crea una funzione di estrazione parametri specifica per le produzioni
        """

        def extract_production_args(production):
            production_id = production[DBProductionsColumns.ID.value]
            production_name = production[DBProductionsColumns.NAME.value]
            client_id = production[DBProductionsColumns.CLIENT_ID.value]
            client_name = client_controller.retrieve_client_map_by_id(client_id)[DBClientsColumns.NAME.value]
            tipologia_produzione = production[DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value]
            tipologia_output = production[DBProductionsColumns.TIPOLOGIA_OUTPUT.value]
            produzione_stato = production[DBProductionsColumns.STATO.value]
            data_di_consegna = production[DBProductionsColumns.END_DATE.value]
            totale_preventivo = production[DBProductionsColumns.TOTALE_PREVENTIVO.value]
            durata_produzione = production[DBProductionsColumns.HOURS.value]
            prezzo_orario = production_controller.calculate_production_cost_per_hour(production_id)

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
    def create_extractor_for_refunds(refunds_controller, client_controller, account_controller):
        """
        Crea una funzione di estrazione parametri specifica per i rimborsi
        """

        def extract_refund_args(refund):
            refund_id = refund[DBRefundsColumns.ID.value]
            refund_name = refund[DBRefundsColumns.REFUND_NAME.value]
            amount = refund[DBRefundsColumns.REFUND_AMOUNT.value]
            refund_date = refund[DBRefundsColumns.REFUND_DATE.value]
            cliente_id = refund[DBRefundsColumns.CLIENT_ID.value]
            client = client_controller.retrieve_client_map_by_id(cliente_id)
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
    def create_extractor_for_salaries(salary_controller, user_controller, account_controller):
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
    def create_extractor_for_suppliers(supplier_controller):
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
            aggregate_data = supplier_controller.construct_supplier_map_aggregate_data(supplier_id)

            return (
                supplier_id,
                supplier_name,
                partita_iva,
                aggregate_data[supplier_controller.Aggregate_data.NUM_SPESE.value],
                round(aggregate_data[supplier_controller.Aggregate_data.MEDIA_SPESE.value], 2),
                round(aggregate_data[supplier_controller.Aggregate_data.TOT_SPESE.value], 2),
                note,
                contatto
            )

        return extract_supplier_args
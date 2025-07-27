from enum import Enum
import customtkinter as ctk
import tkinter as tk


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
                             wraplength=300,
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
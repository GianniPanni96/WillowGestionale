from tkinter import Toplevel

import customtkinter as ctk


class FilterableComboBox(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        values,
        placeholder="Seleziona...",
        autofill=False,
        command=None,
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
        self.current_value = ""
        self.parent = parent

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
        self._default_message_label_height = self.message_label.cget("height")
        self._set_message_label_text("")


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
        self._parent_configure_bind_id = None
        self._parent_click_bind_id = None

        self._apply_state()

    def _sort_values(self, values):
        return sorted(values, key=lambda value: str(value).casefold()) if values else []

    def _get_dropdown_anchor_geometry(self):
        anchor = self.interaction_frame
        return (
            anchor.winfo_rootx(),
            anchor.winfo_rooty() + anchor.winfo_height(),
            max(int(anchor.winfo_width() * 8 / 9), 1)
        )

    def _set_message_label_text(self, text, text_color="white"):
        message_text = text or ""
        if message_text:
            if not self.message_label.winfo_manager():
                self.message_label.pack(fill="x", expand=True)
            self.message_label.configure(
                text=message_text,
                text_color=text_color,
                height=self._default_message_label_height
            )
        else:
            self.message_label.configure(
                text="",
                text_color=text_color,
                height=0
            )
            if self.message_label.winfo_manager():
                self.message_label.pack_forget()

    def _is_disabled(self):
        return self.state == ctk.DISABLED

    def _apply_state(self):
        entry_text_color = self._disabled_text_color if self._is_disabled() else self._text_color
        self.entry.configure(state=self.state, text_color=entry_text_color)
        self.dropdown_button.configure(state=self.state)
        self._update_dropdown_footer_state()
        if self._is_disabled() and self.dropdown_visible:
            self._hide_dropdown()
            self._configure_dropdown_button()

    def _get_dropdown_footer_height(self):
        return 0

    def _create_dropdown_footer(self):
        self.dropdown_add_button = None

    def _update_dropdown_footer_state(self):
        if self.dropdown_add_button is not None:
            self.dropdown_add_button.configure(state=self.state)

    def _refresh_dropdown_footer(self):
        self._update_dropdown_footer_state()

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

    def _is_widget_inside_combo_or_dropdown(self, widget):
        current = widget
        while current is not None:
            if current == self or current == self.dropdown_window:
                return True
            current = getattr(current, "master", None)
        return False

    def _on_parent_mouse_click(self, event):
        if not self.dropdown_visible:
            return

        clicked_widget = event.widget
        if self._is_widget_inside_combo_or_dropdown(clicked_widget):
            return

        self._close_dropdown()

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
            self._set_message_label_text(
                "Selezione dell'utente assente: valore selezionato in automatico dalla lista",
                text_color=self.warning_color
            )
        else:
            self.entry.configure(border_color=self.default_border_color)
            self._set_message_label_text("")


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
            x, y, dropdown_width = self._get_dropdown_anchor_geometry()
            self.dropdown_window.geometry(f"{dropdown_width}x{dropdown_height}+{x}+{y}")

        for widget in self.dropdown_frame.winfo_children():
            widget.destroy()

        if not self.filtered_values:
            empty_label = ctk.CTkLabel(self.dropdown_frame, text="Nessun risultato", text_color="gray", height=30)
            empty_label.pack(fill="x", padx=2, pady=1)
            self.dropdown_buttons = []
            self._refresh_dropdown_footer()
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
        self._refresh_dropdown_footer()

    def _calculate_dropdown_heights(self):
        visible_rows = min(max(len(self.filtered_values), 1), 8)
        list_height = visible_rows * 32 + 14
        add_button_height = self._get_dropdown_footer_height()
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

    def _show_dropdown(self):
        if self._is_disabled():
            return
        if self.dropdown_visible:
            self._update_dropdown()
            self._update_dropdown_position()
            return

        x, y, dropdown_width = self._get_dropdown_anchor_geometry()
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

        self._create_dropdown_footer()

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
        self._parent_configure_bind_id = parent_window.bind("<Configure>", self._on_parent_configure, add="+")
        self._parent_click_bind_id = parent_window.bind("<ButtonPress-1>", self._on_parent_mouse_click, add="+")
        self._parent_events_bound = True

    def _unbind_parent_events(self):
        if not self._parent_events_bound:
            return

        parent_window = self.winfo_toplevel()
        if self._parent_configure_bind_id:
            try:
                parent_window.unbind("<Configure>", self._parent_configure_bind_id)
            except Exception:
                pass
        if self._parent_click_bind_id:
            try:
                parent_window.unbind("<ButtonPress-1>", self._parent_click_bind_id)
            except Exception:
                pass
        self._parent_configure_bind_id = None
        self._parent_click_bind_id = None
        self._parent_events_bound = False

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
            x, y, dropdown_width = self._get_dropdown_anchor_geometry()
            _, dropdown_height = self._calculate_dropdown_heights()
            self.dropdown_window.wm_geometry(f"{dropdown_width}x{dropdown_height}+{x}+{y}")

    def _hide_dropdown(self):
        if self.dropdown_visible:
            self._tracking_movement = False
            self._unbind_parent_events()
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

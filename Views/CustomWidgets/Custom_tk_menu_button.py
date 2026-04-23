import tkinter as tk


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

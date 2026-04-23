import customtkinter as ctk

from Views.CustomWidgets.Filterable_combo_box import FilterableComboBox


class CatalogFilterableComboBox(FilterableComboBox):
    def __init__(
        self,
        parent,
        values,
        placeholder="Seleziona...",
        autofill=False,
        command=None,
        add_button_text="",
        add_button_command=None,
        state=ctk.NORMAL,
        **kwargs
    ):
        self.add_button_text = add_button_text
        self.add_button_command = add_button_command
        super().__init__(
            parent,
            values,
            placeholder=placeholder,
            autofill=autofill,
            command=command,
            state=state,
            **kwargs
        )

    def _get_dropdown_footer_height(self):
        return 34 if self.add_button_command else 0

    def _create_dropdown_footer(self):
        if not self.add_button_command:
            self.dropdown_add_button = None
            return

        self.dropdown_add_button = ctk.CTkButton(
            self.dropdown_container,
            text=self.add_button_text,
            command=self._on_add_button_clicked,
            height=22
        )
        self.dropdown_container.grid_rowconfigure(1, weight=0)
        self.dropdown_add_button.grid(row=1, column=0, sticky="ew", padx=4, pady=(4, 4))

    def _update_dropdown_footer_state(self):
        if self.dropdown_add_button is not None:
            self.dropdown_add_button.configure(state=self.state)

    def _refresh_dropdown_footer(self):
        if self.dropdown_add_button is not None:
            self.dropdown_add_button.configure(
                text=self.add_button_text,
                state=self.state
            )

    def _on_add_button_clicked(self):
        if self._is_disabled():
            return
        self._hide_dropdown()
        if self.add_button_command:
            self.after(10, self.add_button_command)

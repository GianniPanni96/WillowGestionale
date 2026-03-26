import customtkinter as ctk

from datetime import datetime

from App_context import AppContext
from Model import DBExpensesColumns, DBSuppliersColumns

from QueryServices.Suppliers_query_service import SupplierQueryService
from Analyzers.Supplier_analyzer_service import SupplierAnalyzerService

from Controllerss.Supplier_controller import SupplierController
from Views.View_utils import ViewUtils


class SupplierDetailView(ctk.CTkFrame):
    def __init__(self, parent, app_context: AppContext, back_callback):
        super().__init__(parent)
        self.app_context: AppContext = app_context
        self.supplier_controller:SupplierController = app_context.supplier_controller
        self.supplier_query_service:SupplierQueryService = app_context.suppliers_query_service
        self.supplier_analyzer_service:SupplierAnalyzerService = app_context.suppliers_analyzer_service
        self.expense_controller = app_context.expense_controller
        self.db_model = app_context.db_model
        self.back_callback = back_callback
        self.event_bus = app_context.event_bus
        self.current_client_id = None
        self.analyzer = app_context.analyzer
        self.catalogo_elenchi = app_context.catalogo_elenchi

        self.configure(fg_color="transparent")

        self.head_frame = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.back_button = ctk.CTkButton(
            self.head_frame,
            text="Elenco Fornitori",
            command=self._cleanup_and_go_back
        )
        self.title_label = ctk.CTkLabel(self.head_frame, font=("Arial", 22, "bold"))

        self.user_info_widgets: dict[str, ctk.CTkEntry | ctk.CTkOptionMenu] = {}

        self.nome_fattura_string = "FATTURA ASSOCIATA"
        self.nome_produzione_string = "PRODUZIONE ASSOCIATA"
        self.nome_rimborso_string = "RIMBORSO ASSOCIATO"

        self.content_frame = ctk.CTkScrollableFrame(self)

        self.switch_modify = ctk.CTkSwitch(
            self.head_frame,
            text="Abilita la modifica",
            command=lambda: self.toggle_edit(self.content_frame)
        )

        self._setup_base_layout()

    def _setup_base_layout(self):
        """Inizializza la struttura base del layout"""
        self.head_frame.pack(fill="x", pady=5, padx=5)
        self.back_button.pack(anchor="w", side="left", pady=10, padx=10)
        self.title_label.pack(anchor="c", side="left", fill="x", expand=True, pady=10)
        self.switch_modify.pack(anchor="e", side="left", pady=10, padx=10)
        self.content_frame.pack(fill="both", expand=True, pady=20, padx=20)

    def create_detail_tab(self, supplier_id):
        """Ricrea la vista dettaglio per un fornitore specifico"""
        self.current_supplier_id = supplier_id

        self._clear_content()

        self.supplier = self.supplier_query_service.retrieve_supplier_map_by_id(supplier_id)

        self.title_label.configure(text=f"{self.supplier[DBSuppliersColumns.NAME.value]}")

        self._create_supplier_info_section(self.supplier)
        self.toggle_edit(self.content_frame)

        self.wrapper_frame = ctk.CTkFrame(self.content_frame, fg_color="#333333")
        self.wrapper_frame.pack(padx=25, pady=(90, 0), fill="both", expand=True)
        self._create_expenses_history()

    def _create_supplier_info_section(self, supplier_data):
        self.entry_fields = {
            DBSuppliersColumns.NAME.value: {
                "type": ctk.CTkEntry,
                "label": "Nome Fornitore",
                "section": "Dati Anagrafici"
            },
            DBSuppliersColumns.PARTITA_IVA.value: {
                "type": ctk.CTkEntry,
                "label": "Partita IVA",
                "section": "Dati Anagrafici"
            },
            DBSuppliersColumns.SEDE.value: {
                "type": ctk.CTkEntry,
                "label": "Sede",
                "section": "Dati Anagrafici"
            },
            DBSuppliersColumns.CONTATTO.value: {
                "type": ctk.CTkEntry,
                "label": "Contatto",
                "section": "Contatto"
            },
            DBSuppliersColumns.CATEGORIA.value: {
                "type": ctk.CTkOptionMenu,
                "label": "Categoria",
                "section": "Categoria",
                "values": [item[1] for item in self.catalogo_elenchi["clients_business_sectors"]]
            },
            DBSuppliersColumns.NOTE.value: {
                "type": ctk.CTkTextbox,
                "label": "Note",
                "section": "Note",
                "height": 100
            }
        }

        validation_rules = {
            DBSuppliersColumns.NAME.value: (
                lambda val: val.strip() != "",
                "Il nome del fornitore non puo essere vuoto"
            ),
            DBSuppliersColumns.PARTITA_IVA.value: (
                lambda val: val == "" or (len(val) == 11 and val.isdigit()),
                "Partita IVA non valida (11 cifre)"
            )
        }

        self.supplier_info_widgets = {}
        self.error_labels = {}
        sections = {}

        self.info_frame = ctk.CTkFrame(self.content_frame, border_width=2, border_color="#2659ab")
        self.info_frame.pack(fill="both", expand=True, pady=10, padx=25)

        self.info_frame.grid_columnconfigure(0, weight=1, uniform="col")
        self.info_frame.grid_columnconfigure(1, weight=1, uniform="col")

        sections_order = [
            "Dati Anagrafici",
            "Contatto",
            "Categoria",
            "Note"
        ]

        for i, section_name in enumerate(sections_order):
            frame = ctk.CTkFrame(self.info_frame)
            column = 0 if i % 2 == 0 else 1
            row = i // 2
            frame.grid(row=row, column=column, sticky="nsew", padx=15, pady=15)
            frame.grid_columnconfigure(1, weight=1)
            sections[section_name] = {
                "frame": frame,
                "row": 0
            }

            ctk.CTkLabel(frame, text=section_name, font=("Arial", 14, "bold")).grid(
                row=0, column=0, columnspan=2, sticky="w", padx=15, pady=5
            )
            sections[section_name]["row"] += 1

        for field, config in self.entry_fields.items():
            section = sections[config["section"]]
            frame = section["frame"]
            row = section["row"]

            lbl = ctk.CTkLabel(frame, text=config["label"] + ":")
            lbl.grid(row=row, column=0, sticky="w", padx=(15, 5), pady=(2, 5))

            value = str(supplier_data.get(field, ""))

            if config["type"] == ctk.CTkOptionMenu:
                widget = config["type"](frame, values=config.get("values", []))

                if field == DBSuppliersColumns.CATEGORIA.value:
                    current_value = next(
                        (desc for key, desc in self.catalogo_elenchi["clients_business_sectors"] if key == value),
                        value
                    )
                    widget.set(current_value)
                else:
                    widget.set(value if value else config.get("values", [""])[0])

            elif config["type"] == ctk.CTkTextbox:
                widget = config["type"](frame, height=config.get("height", 50))
                widget.insert("1.0", value)
            else:
                widget = config["type"](frame)
                widget.insert(0, value)

            widget.grid(
                row=row,
                column=1,
                sticky="ew",
                padx=(5, 15),
                pady=(2, 5),
                rowspan=2 if config["type"] == ctk.CTkTextbox else 1
            )
            self.supplier_info_widgets[field] = widget

            if field in validation_rules:
                validation_func, error_message = validation_rules[field]

                error_lbl = ctk.CTkLabel(frame, text="", text_color="#e8e5dc")
                error_lbl.grid(
                    row=row + (2 if config["type"] == ctk.CTkTextbox else 1),
                    column=1,
                    sticky="w",
                    padx=5,
                    pady=(0, 10)
                )
                self.error_labels[field] = error_lbl

                if config["type"] != ctk.CTkTextbox:
                    widget.bind(
                        "<FocusOut>",
                        lambda e, w=widget, vl=validation_func, el=error_lbl, em=error_message:
                        ViewUtils.validate_entry(w, vl, el, em)
                    )
                else:
                    widget.bind(
                        "<FocusOut>",
                        lambda e, w=widget, vl=validation_func, el=error_lbl, em=error_message:
                        ViewUtils.validate_textbox(w, vl, el, em)
                    )

            section["row"] += 3 if config["type"] == ctk.CTkTextbox else 2

        buttons_frame = ctk.CTkFrame(self.info_frame, fg_color="#2b2b2b")
        buttons_frame.grid(row=2, column=0, columnspan=2, pady=(5, 15), padx=20, sticky="WE")

        self.save_info_btn = ctk.CTkButton(buttons_frame, text="Salva Fornitore", command=self.save_supplier_mod)
        self.save_info_btn.pack(padx=(400, 10), pady=(20, 20), side="left")

        self.delete_btn = ctk.CTkButton(
            buttons_frame,
            text="Elimina Fornitore",
            fg_color="#8B0000",
            hover_color="#A52A2A",
            command=self.delete_supplier
        )
        self.delete_btn.pack(padx=10, pady=(20, 20), side="right", anchor="e")

    def toggle_edit(self, parent):
        """
        Abilita o disabilita la modifica dei widget nella finestra di modifica utente.
        """
        state = ctk.NORMAL if self.switch_modify.get() else ctk.DISABLED

        self.save_info_btn.configure(state=state)
        self.delete_btn.configure(state=state)

        for w in parent.winfo_children():
            if isinstance(w, (ctk.CTkEntry, ctk.CTkTextbox)):
                w.configure(state=state, text_color="#636363" if state == ctk.DISABLED else "#c2c2c2")
            elif isinstance(w, ctk.CTkOptionMenu):
                w.configure(state=state)
            elif isinstance(w, (ctk.CTkFrame, ctk.CTkScrollableFrame, ctk.CTkToplevel)):
                self.toggle_edit(w)

    def _create_expenses_history(self):
        """Crea la sezione storico delle spese """
        section_frame = ctk.CTkFrame(self.wrapper_frame, border_width=2, border_color="#2659ab")
        section_frame.pack(fill="both", side="left", expand=True, pady=0, padx=(0, 30))

        ctk.CTkLabel(section_frame, text="SPESE", font=("Arial", 14, "bold")).pack(
            anchor="w",
            pady=(10, 10),
            padx=10
        )

        global_infos = {
            "TOTALE SPESE (All Time)": {
                "value": self.supplier_analyzer_service.calcola_tot_spese_supplier(self.current_supplier_id, year=-1),
                "uom": "€"
            },
            f"TOTALE SPESE {datetime.now().year}": {
                "value": self.supplier_analyzer_service.calcola_tot_spese_supplier(self.current_supplier_id),
                "uom": "€"
            }
        }

        self.global_infos_invoices_widgets = ViewUtils.construct_global_infos_cards(section_frame, global_infos)

        ctk.CTkLabel(
            section_frame,
            text=f"- Elenco Spese {datetime.now().year} -",
            font=("Arial", 14, "italic"),
            text_color="gray",
            justify="right"
        ).pack(anchor="w", padx=10, pady=(10, 0))

        expenses_frame = ctk.CTkScrollableFrame(section_frame, height=300)
        expenses_frame.pack(fill="both", expand=True, padx=(10, 20), pady=(10, 20))

        expenses = self.supplier_query_service.retrieve_supplier_with_expenses_map_list(self.current_supplier_id)
        for expense in expenses:
            if expense[DBExpensesColumns.NAME.value] is not None:
                nome_spesa = expense[DBExpensesColumns.NAME.value]
                id_spesa = expense[DBExpensesColumns.ID.value]
                spesa_button = ctk.CTkButton(
                    expenses_frame,
                    text=f"{nome_spesa}",
                    command=lambda id=id_spesa: self.show_expense_detail(id)
                )
                spesa_button.pack(padx=10, pady=10, fill="x", expand=True)

    def show_expense_detail(self, expense_id):
        self.event_bus.publish(ViewUtils.EventBusKeys.SHOW_EXPENSE_DETAIL, expense_id)

    def save_supplier_mod(self):
        supplier_data = {
            DBSuppliersColumns.NAME.value: self.supplier_info_widgets[DBSuppliersColumns.NAME.value].get().strip(),
            DBSuppliersColumns.PARTITA_IVA.value: self.supplier_info_widgets[DBSuppliersColumns.PARTITA_IVA.value].get().strip(),
            DBSuppliersColumns.SEDE.value: self.supplier_info_widgets[DBSuppliersColumns.SEDE.value].get().strip(),
            DBSuppliersColumns.CONTATTO.value: self.supplier_info_widgets[DBSuppliersColumns.CONTATTO.value].get().strip(),
            DBSuppliersColumns.CATEGORIA.value: self.supplier_info_widgets[DBSuppliersColumns.CATEGORIA.value].get(),
            DBSuppliersColumns.NOTE.value: self.supplier_info_widgets[DBSuppliersColumns.NOTE.value].get("1.0", "end-1c").strip()
        }

        success, message = self.supplier_controller.update_supplier(self.current_supplier_id, supplier_data)

        if success:
            supplier_name = self.supplier_query_service.retrieve_supplier_map_by_id(
                self.current_supplier_id
            )[DBSuppliersColumns.NAME.value]
            print(f"Fornitore {supplier_name} salvato con successo")
            ViewUtils.show_confirm_popup_2(self.content_frame, "SALVATAGGIO COMPLETATO", message)
            self.switch_modify.deselect()
            self.toggle_edit(self.content_frame)
        else:
            print(f"{message}")
            ViewUtils.show_error_popup(self.content_frame, "ERRORE", message)

    def delete_supplier(self):
        confirmation = ViewUtils.ask_confirmation_popup(
            self.content_frame,
            "Stai per eliminare questo fornitore.\nDesideri continuare ?",
            "ELIMINAZIONE FORNITORE"
        )
        if confirmation:
            expenses = self.expense_controller.retrieve_expense_map_list_by_supplier(self.current_supplier_id)

            if len(expenses) == 0:
                success, message = self.supplier_controller.delete_supplier(self.current_supplier_id)
                if success:
                    print(message)
                    ViewUtils.show_confirm_popup_simple(self.content_frame, "CONFERMA ELIMINAZIONE", message)
                else:
                    print(message)
                    ViewUtils.show_error_popup(self.content_frame, "ERRORE", message)
            else:
                ViewUtils.show_error_popup(
                    self.info_frame,
                    message="Impossibile eliminare il fornitore.\n\n"
                    "Esiste un item collegato a questo fornitore.\n"
                    "Eliminare ogni riferimento a questo fornitore per poterlo eliminare dal database."
                )

    def _clear_content(self):
        """Distrugge tutti i widget dinamici"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def _cleanup_and_go_back(self):
        """Pulizia completa prima di tornare indietro"""
        self._clear_content()
        self.pack_forget()
        self.back_callback()

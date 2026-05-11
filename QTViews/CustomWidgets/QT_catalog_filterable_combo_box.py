"""
Combo box filtrabile in chiave Qt con bottone "Aggiungi…" integrato.

Equivalente di Views/CustomWidgets/Catalog_filterable_combo_box.py + del
flusso Views/Adders/Base_catalog_item_adder_view.py.

Estende QTFilterableComboBox aggiungendo:

- una voce sentinella "+ Aggiungi …" come ultima riga del dropdown,
  resa visivamente distinta (italico + colore accento);
- la callback che, al click sulla sentinella, apre la
  QTCatalogItemAdderDialog, persiste la nuova voce su catalogs.json
  e aggiorna sia il widget sia `app_context.catalogo_elenchi`;
- il factory `bound_to_section()` che cabla in un colpo solo la
  sezione di catalogs.json desiderata.

La sentinella non e' considerata un valore valido: la validazione
ereditata da QTFilterableComboBox la esclude da `_selectable_values()`,
quindi non puo' mai essere "selezionata" come reale.
"""

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QTimer
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from QTViews.CustomWidgets.QT_filterable_combo_box import QTFilterableComboBox
from Utils.Controller_utils import ControllerUtils

if TYPE_CHECKING:
    from App_context import AppContext


# Metadata per ogni sezione di catalogs.json. Aggiungere qui una entry
# per supportare un nuovo catalogo.
CATALOG_SECTIONS = {
    "clients_business_sectors": {
        "trigger_key": "ADD_SECTOR",
        "add_button_text": "Aggiungi un settore",
        "dialog_title": "Aggiungi un nuovo settore",
        "dialog_label": "Nome del settore:",
    },
    "production_types": {
        "trigger_key": "ADD_PROD_TYPE",
        "add_button_text": "Aggiungi una tipologia",
        "dialog_title": "Aggiungi una nuova tipologia di produzione",
        "dialog_label": "Nome della tipologia:",
    },
    "production_output_types": {
        "trigger_key": "ADD_PROD_OUT_TYPE",
        "add_button_text": "Aggiungi una tipologia di output",
        "dialog_title": "Aggiungi una nuova tipologia di output",
        "dialog_label": "Nome della tipologia di output:",
    },
    "expenses_category": {
        "trigger_key": "ADD_CATEGORY",
        "add_button_text": "Aggiungi una categoria",
        "dialog_title": "Aggiungi una nuova categoria di spesa",
        "dialog_label": "Nome della categoria:",
    },
}


class QTCatalogItemAdderDialog(QDialog):
    """
    Modale per aggiungere una voce ad una sezione di catalogs.json.

    Equivalente Qt di Views/Adders/Base_catalog_item_adder_view.py.
    """

    def __init__(
        self,
        app_context: "AppContext",
        section_name: str,
        title: str,
        label_text: str,
        parent=None,
    ):
        super().__init__(parent)
        self.app_context = app_context
        self.config_manager = app_context.config_manager
        self.section_name = section_name

        self.new_key: Optional[str] = None
        self.new_value: Optional[str] = None

        self.setWindowTitle(title)
        self.resize(380, 180)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        layout.addWidget(QLabel(label_text))

        self._value_edit = QLineEdit()
        self._value_edit.returnPressed.connect(self._save)
        layout.addWidget(self._value_edit)

        layout.addStretch(1)

        save_btn = QPushButton("Salva")
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

    def _save(self):
        new_value = self._value_edit.text().strip()
        if not new_value:
            QMessageBox.warning(self, "Errore", "Il valore non può essere vuoto")
            return

        new_key = ControllerUtils.normalize_string_for_key(new_value)
        try:
            self.config_manager.update_list_field(
                self.section_name, new_key, new_value, "update"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Errore", str(exc))
            return

        self.new_key = new_key
        self.new_value = new_value
        self.accept()


class QTCatalogFilterableComboBox(QTFilterableComboBox):
    """
    Combo filtrabile (eredita comportamento "must select") con sentinella
    "+ Aggiungi …" in coda al dropdown che apre il flusso di add.

    Uso diretto:
        combo = QTCatalogFilterableComboBox(values=[...],
                                            add_button_text="Aggiungi …",
                                            on_add_clicked=cb)

    Uso wired ad una sezione catalogs.json:
        combo = QTCatalogFilterableComboBox.bound_to_section(
            app_context, "expenses_category", parent=...
        )
    """

    SENTINEL_PREFIX = "➕ "

    def __init__(
        self,
        parent=None,
        values: Optional[list] = None,
        add_button_text: str = "",
        on_add_clicked=None,
        autofill: bool = False,
        placeholder: str = "Seleziona…",
    ):
        # Devono esistere prima di super().__init__() perche' il
        # costruttore base chiama _rebuild_items().
        self._add_button_text = add_button_text
        self._on_add_clicked = on_add_clicked

        super().__init__(parent=parent, values=values, autofill=autofill, placeholder=placeholder)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def bound_to_section(
        cls,
        app_context: "AppContext",
        section_name: str,
        parent=None,
        add_button_text: Optional[str] = None,
        autofill: bool = False,
    ) -> "QTCatalogFilterableComboBox":
        """
        Costruisce una combo che pesca i valori dalla sezione indicata di
        catalogo_elenchi e che, alla pressione di "Aggiungi…", apre la
        QTCatalogItemAdderDialog corretta. La combo si aggiorna
        automaticamente con il nuovo valore appena salvato.
        """
        meta = CATALOG_SECTIONS.get(section_name)
        if meta is None:
            raise ValueError(
                f"Sezione catalogo non riconosciuta: {section_name}. "
                f"Valori validi: {list(CATALOG_SECTIONS.keys())}"
            )

        values = cls._values_for_section(app_context, section_name, meta["trigger_key"])
        button_text = add_button_text or meta["add_button_text"]

        combo = cls(
            parent=parent,
            values=values,
            add_button_text=button_text,
            on_add_clicked=None,
            autofill=autofill,
        )

        def _on_add_clicked():
            dialog = QTCatalogItemAdderDialog(
                app_context=app_context,
                section_name=section_name,
                title=meta["dialog_title"],
                label_text=meta["dialog_label"],
                parent=combo,
            )
            if dialog.exec() != QDialog.Accepted:
                return
            if dialog.new_value is None:
                return

            cls._refresh_in_memory_catalog(
                app_context, section_name, meta["trigger_key"],
                dialog.new_key, dialog.new_value,
            )
            updated = cls._values_for_section(app_context, section_name, meta["trigger_key"])
            combo.set_values(updated)
            combo.set_value(dialog.new_value)

        combo._on_add_clicked = _on_add_clicked
        # Rebuild ora che on_add_clicked e' valorizzata: la sentinella
        # diventa cliccabile.
        combo.set_values(values)
        return combo

    # ------------------------------------------------------------------
    # Override degli hook della base
    # ------------------------------------------------------------------

    def _rebuild_items(self):
        super()._rebuild_items()
        if self._add_button_text and self._on_add_clicked is not None:
            self.blockSignals(True)
            self.addItem(self._sentinel_text())
            sentinel_idx = self.count() - 1
            item = self.model().item(sentinel_idx)
            if item is not None:
                font = item.font()
                font.setItalic(True)
                item.setFont(font)
                item.setForeground(QApplication.palette().color(QPalette.ColorRole.Highlight))
            self.blockSignals(False)

    def _selectable_values(self) -> list:
        # La sentinella non e' un valore valido per la validazione.
        return list(self._all_values)

    def _on_activated(self, index: int):
        if (
            0 <= index < self.count()
            and self.itemText(index) == self._sentinel_text()
        ):
            # Apre la dialog al prossimo giro dell'event loop, cosi' che
            # la combo possa chiudere il proprio popup prima.
            QTimer.singleShot(0, self._handle_add_click)
            return
        super()._on_activated(index)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _sentinel_text(self) -> str:
        return f"{self.SENTINEL_PREFIX}{self._add_button_text}"

    def _handle_add_click(self):
        # Resetta la selezione cosi' che la sentinella non resti come
        # valore "in attesa di commit".
        self.setCurrentIndex(-1)
        self.setEditText("")
        self._clear_warning()
        if self._on_add_clicked is not None:
            self._on_add_clicked()

    @staticmethod
    def _values_for_section(app_context, section_name, trigger_key) -> list:
        section = app_context.catalogo_elenchi.get(section_name, [])
        return [value for key, value in section if key != trigger_key]

    @staticmethod
    def _refresh_in_memory_catalog(app_context, section_name, trigger_key, new_key, new_value):
        section = app_context.catalogo_elenchi.get(section_name, [])
        if any(k == new_key for k, _ in section):
            return
        items = [(k, v) for k, v in section if k != trigger_key]
        trigger_pair = next(((k, v) for k, v in section if k == trigger_key), None)
        items.insert(0, (new_key, new_value))
        if trigger_pair is not None:
            items.append(trigger_pair)
        app_context.catalogo_elenchi[section_name] = items

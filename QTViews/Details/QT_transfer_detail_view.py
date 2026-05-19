"""
Vista dettaglio bonifico, versione Qt.

Replica il pattern delle altre detail view (refund/salary/payment):
- griglia 2x2 (Dati Generali / Dati Fiscali / Collegamenti / Note);
- switch "Abilita la modifica" che sblocca i campi editabili e i
  bottoni Salva / Elimina;
- "Torna al conto" come back: questa view e' raggiungibile solo
  cliccando una riga della tabella movimenti del dettaglio conto, e
  l'``on_back`` ricostruisce quella vista.
"""

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from Gestionale_Enums import DBAccountsColumns, DBTransfersColumns

if TYPE_CHECKING:
    from App_context import AppContext


class QTTransferDetailViewH(QWidget):
    """QWidget dettaglio bonifico."""

    SENDER_FIELD = "CONTO MITTENTE"
    RECEIVER_FIELD = "CONTO RICEVENTE"

    SECTIONS = ["Dati Generali", "Dati Fiscali", "Collegamenti", "Note"]

    def __init__(self, app_context: "AppContext", transfer_id, on_back, parent=None):
        super().__init__(parent)

        self.app_context = app_context
        self.transfer_controller = app_context.transfer_controller
        self.transfer_query_service = app_context.transfer_query_service
        self.accounts_query_service = app_context.account_query_service
        self.update_controller = getattr(app_context, "update_controller", None)

        self.current_transfer_id = transfer_id
        self.transfer: dict | None = None
        self.on_back = on_back

        self.transfer_widgets: dict = {}
        self.transfer_labels: dict = {}
        self.section_grids: dict = {}
        self.section_rows: dict = {}

        self._build_ui()
        self.load_transfer(transfer_id)

    # ------------------------------------------------------------------
    # UI base
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        head = QFrame()
        head.setObjectName("TransferDetailHead")
        head.setStyleSheet(
            "#TransferDetailHead { background-color: palette(window); border-radius: 6px; }"
        )
        head_layout = QHBoxLayout(head)
        head_layout.setContentsMargins(10, 6, 10, 6)

        self.back_button = QPushButton("Torna al conto")
        self.back_button.clicked.connect(self._cleanup_and_go_back)
        head_layout.addWidget(self.back_button)

        self.title_label = QLabel("")
        title_font = self.title_label.font()
        title_font.setPointSize(16)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignCenter)
        head_layout.addWidget(self.title_label, stretch=1)

        self.modify_switch = QCheckBox("Abilita la modifica")
        self.modify_switch.toggled.connect(self._toggle_edit)
        head_layout.addWidget(self.modify_switch)

        root.addWidget(head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        root.addWidget(self.scroll, stretch=1)

        self.content = QWidget()
        self.scroll.setWidget(self.content)
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        self.content_layout.setSpacing(15)

    def _build_info_section(self, transfer_data):
        self.info_frame = QFrame()
        self.info_frame.setObjectName("TransferInfoFrame")
        self.info_frame.setStyleSheet(
            "#TransferInfoFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
        )
        info_layout = QGridLayout(self.info_frame)
        info_layout.setContentsMargins(15, 15, 15, 15)
        info_layout.setHorizontalSpacing(20)
        info_layout.setVerticalSpacing(10)

        for i, name in enumerate(self.SECTIONS):
            section_frame = QFrame()
            section_frame.setObjectName("TransferInfoSectionFrame")
            section_frame.setStyleSheet(
                "#TransferInfoSectionFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
            )
            section_layout = QGridLayout(section_frame)
            section_layout.setContentsMargins(10, 10, 10, 10)
            section_layout.setHorizontalSpacing(8)
            section_layout.setVerticalSpacing(8)
            section_layout.setAlignment(Qt.AlignTop)

            section_title = QLabel(name)
            font = section_title.font()
            font.setBold(True)
            font.setPointSize(12)
            section_title.setFont(font)
            section_title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            section_layout.addWidget(section_title, 0, 0, 1, 2, alignment=Qt.AlignTop)

            row = i // 2
            col = i % 2
            info_layout.addWidget(section_frame, row, col)
            info_layout.setColumnStretch(col, 1)
            self.section_grids[name] = section_layout
            self.section_rows[name] = 1

        # --- Dati Generali ---
        self._add_field(
            "Dati Generali",
            DBTransfersColumns.DESCRIPTION.value,
            "Causale",
            self._make_line_edit(transfer_data.get(DBTransfersColumns.DESCRIPTION.value, "")),
        )

        # --- Dati Fiscali ---
        self._add_field(
            "Dati Fiscali",
            DBTransfersColumns.AMOUNT.value,
            "Importo (€)",
            self._make_line_edit(transfer_data.get(DBTransfersColumns.AMOUNT.value, "")),
        )

        # --- Collegamenti ---
        accounts = self.accounts_query_service.retrieve_accounts_map_list() or []
        account_names = [a[DBAccountsColumns.NAME.value] for a in accounts]

        sender_combo = QComboBox()
        sender_combo.addItems(account_names)
        sender_id = transfer_data.get(DBTransfersColumns.SENDER_ACCOUNT_ID.value)
        sender = self.accounts_query_service.retrieve_account_map_by_id(sender_id) if sender_id else None
        self._set_combo_text(sender_combo, sender[DBAccountsColumns.NAME.value] if sender else None)
        self._add_field("Collegamenti", self.SENDER_FIELD, "Conto Mittente", sender_combo)

        receiver_combo = QComboBox()
        receiver_combo.addItems(account_names)
        receiver_id = transfer_data.get(DBTransfersColumns.RECEIVER_ACCOUNT_ID.value)
        receiver = self.accounts_query_service.retrieve_account_map_by_id(receiver_id) if receiver_id else None
        self._set_combo_text(receiver_combo, receiver[DBAccountsColumns.NAME.value] if receiver else None)
        self._add_field("Collegamenti", self.RECEIVER_FIELD, "Conto Ricevente", receiver_combo)

        # --- Note: timestamp read-only ---
        created_lbl = QLabel(str(transfer_data.get(DBTransfersColumns.CREATED_AT.value, "") or ""))
        self._add_field("Note", DBTransfersColumns.CREATED_AT.value, "Data Creazione", created_lbl)

        updated_lbl = QLabel(str(transfer_data.get(DBTransfersColumns.UPDATED_AT.value, "") or ""))
        self._add_field("Note", DBTransfersColumns.UPDATED_AT.value, "Ultimo Aggiornamento", updated_lbl)

        for name, grid in self.section_grids.items():
            grid.setRowStretch(self.section_rows[name], 1)

        buttons_frame = QFrame()
        buttons_layout = QHBoxLayout(buttons_frame)
        buttons_layout.setContentsMargins(15, 15, 15, 15)

        self.save_btn = QPushButton("Salva Bonifico")
        self.save_btn.clicked.connect(self._save_transfer_mod)
        buttons_layout.addWidget(self.save_btn)

        buttons_layout.addStretch(1)

        self.delete_btn = QPushButton("Elimina Bonifico")
        self.delete_btn.setStyleSheet(
            "QPushButton { background-color: #8B0000; color: palette(highlighted-text); }"
            "QPushButton:hover { background-color: #A52A2A; }"
            "QPushButton:disabled { background-color: #4a2727; color: palette(mid); }"
        )
        self.delete_btn.clicked.connect(self._delete_transfer)
        buttons_layout.addWidget(self.delete_btn)

        info_layout.addWidget(buttons_frame, 2, 0, 1, 2)

        self.content_layout.addWidget(self.info_frame)

    def _add_field(self, section_name, key, label_text, widget):
        grid = self.section_grids[section_name]
        row = self.section_rows[section_name]
        label = QLabel(label_text + ":")
        grid.addWidget(label, row, 0, alignment=Qt.AlignLeft)
        grid.addWidget(widget, row, 1)
        self.transfer_widgets[key] = widget
        self.transfer_labels[key] = label
        self.section_rows[section_name] = row + 1

    def _make_line_edit(self, value):
        edit = QLineEdit()
        edit.setText(str(value) if value is not None else "")
        return edit

    # ------------------------------------------------------------------
    # Caricamento
    # ------------------------------------------------------------------

    def load_transfer(self, transfer_id):
        self.current_transfer_id = transfer_id
        self._clear_content()

        transfer = self.transfer_query_service.retrieve_transfer_map_by_id(transfer_id)
        if not transfer:
            self.title_label.setText("Bonifico non trovato")
            return

        self.transfer = transfer
        self.title_label.setText(
            str(transfer.get(DBTransfersColumns.DESCRIPTION.value, "") or "Bonifico")
        )

        self._build_info_section(transfer)
        self._toggle_edit(self.modify_switch.isChecked())

    def _clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.transfer_widgets.clear()
        self.transfer_labels.clear()
        self.section_grids.clear()
        self.section_rows.clear()
        self.modify_switch.blockSignals(True)
        self.modify_switch.setChecked(False)
        self.modify_switch.blockSignals(False)

    # ------------------------------------------------------------------
    # Toggle edit
    # ------------------------------------------------------------------

    def _toggle_edit(self, enabled):
        if not hasattr(self, "save_btn"):
            return

        self.save_btn.setEnabled(enabled)
        self.delete_btn.setEnabled(enabled)

        readonly_keys = {
            DBTransfersColumns.CREATED_AT.value,
            DBTransfersColumns.UPDATED_AT.value,
        }
        for key, widget in self.transfer_widgets.items():
            if key in readonly_keys:
                continue
            widget.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Salvataggio / eliminazione
    # ------------------------------------------------------------------

    def _save_transfer_mod(self):
        if self.transfer is None:
            return

        sender_name = self._combo_text(self.SENDER_FIELD)
        receiver_name = self._combo_text(self.RECEIVER_FIELD)
        sender = self.accounts_query_service.retrieve_account_map_by_name(sender_name)
        receiver = self.accounts_query_service.retrieve_account_map_by_name(receiver_name)

        if not sender or not receiver:
            QMessageBox.critical(self, "ERRORE", "Conto mittente o ricevente non valido.")
            return

        transfer_data = {
            DBTransfersColumns.DESCRIPTION.value: self.transfer_widgets[
                DBTransfersColumns.DESCRIPTION.value
            ].text().strip(),
            DBTransfersColumns.AMOUNT.value: self.transfer_widgets[
                DBTransfersColumns.AMOUNT.value
            ].text().strip(),
            DBTransfersColumns.SENDER_ACCOUNT_ID.value: sender[DBAccountsColumns.ID.value],
            DBTransfersColumns.RECEIVER_ACCOUNT_ID.value: receiver[DBAccountsColumns.ID.value],
        }

        success, message = self.transfer_controller.update_transfer(
            self.current_transfer_id, transfer_data
        )
        if not success:
            QMessageBox.critical(self, "ERRORE", message)
            return

        if self.update_controller is not None:
            try:
                self.update_controller.on_adding_transfer()
            except Exception:
                pass

        QMessageBox.information(self, "SALVATAGGIO COMPLETATO", message)
        self.modify_switch.setChecked(False)
        self.load_transfer(self.current_transfer_id)

    def _delete_transfer(self):
        confirm = QMessageBox.question(
            self,
            "ELIMINAZIONE BONIFICO",
            "Stai per eliminare questo bonifico.\nDesideri continuare?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        success, message = self.transfer_controller.delete_transfer(self.current_transfer_id)
        if not success:
            QMessageBox.critical(self, "ERRORE", message)
            return

        if self.update_controller is not None:
            try:
                self.update_controller.on_adding_transfer()
            except Exception:
                pass

        QMessageBox.information(self, "BONIFICO ELIMINATO", message)
        self._cleanup_and_go_back()

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _cleanup_and_go_back(self):
        if self.on_back is not None:
            self.on_back()

    def _combo_text(self, key):
        widget = self.transfer_widgets.get(key)
        if isinstance(widget, QComboBox):
            return widget.currentText().strip()
        if hasattr(widget, "text"):
            return widget.text().strip()
        return ""

    def _set_combo_text(self, combo, value):
        if value is None:
            return
        text = str(value)
        idx = combo.findText(text)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        elif combo.isEditable():
            combo.setEditText(text)

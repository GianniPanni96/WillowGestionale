"""
Versione QT del dettaglio di un rimborso.

Equivalente di Views/Details/Refund_detail_view.RefundDetailView,
portato sui widget Qt mantenendo la stessa logica di dominio:
- sezione informazioni in griglia 2x2 (Dati Generali / Dati Fiscali /
  Collegamenti / Note), con il cliente come QTFilterableComboBox e il
  conto come QComboBox;
- switch "Abilita la modifica" che sblocca i campi editabili e i
  bottoni Salva / Elimina;
- prima dell'eliminazione si conferma con l'utente.

Strutturalmente segue il pattern di QTPaymentDetailViewH /
QTProductionDetailViewH: head bar persistente (back + titolo +
switch), QScrollArea per il corpo, refresh totale via load_refund().
"""

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
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

from Gestionale_Enums import (
    DBAccountsColumns,
    DBClientsColumns,
    DBRefundsColumns,
)
from QTViews.CustomWidgets.QT_filterable_combo_box import QTFilterableComboBox
from QTViews.CustomWidgets.QT_warning_banner import WarningBanner
from WarningServices.Warning_types import WarningInfo, WarningSeverity

if TYPE_CHECKING:
    from App_context import AppContext


class QTRefundDetailViewH(QWidget):
    """
    QWidget dettaglio rimborso.
    """

    CLIENT_FIELD = "CLIENTE ASSOCIATO"
    ACCOUNT_FIELD = "CONTO"

    SECTIONS = ["Dati Generali", "Dati Fiscali", "Collegamenti", "Note"]

    def __init__(self, app_context: "AppContext", refund_id, on_back, parent=None):
        super().__init__(parent)

        self.app_context = app_context
        self.refund_controller = app_context.refund_controller
        self.refunds_query_service = app_context.refunds_query_service
        self.clients_query_service = app_context.clients_query_service
        self.accounts_query_service = app_context.account_query_service

        self.current_refund_id = refund_id
        self.refund = None
        self.on_back = on_back

        self.refund_widgets: dict = {}
        self.refund_labels: dict = {}
        self.section_grids: dict = {}
        self.section_rows: dict = {}

        self._build_ui()
        self.load_refund(refund_id)

    # ------------------------------------------------------------------
    # UI base
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        head = QFrame()
        head.setObjectName("RefundDetailHead")
        head.setStyleSheet(
            "#RefundDetailHead { background-color: palette(window); border-radius: 6px; }"
        )
        head_layout = QHBoxLayout(head)
        head_layout.setContentsMargins(10, 6, 10, 6)

        self.back_button = QPushButton("Elenco Rimborsi")
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

    def _build_info_section(self, refund_data):
        # Warning banner: visibile solo per i sev 1 (FK rotte).
        self.warning_banner = WarningBanner()
        self.content_layout.addWidget(self.warning_banner)
        self._current_warning_info = self._compute_current_warning(refund_data)
        if self._is_consistency_warning(self._current_warning_info):
            self.warning_banner.set_warning(self._current_warning_info)
        else:
            self.warning_banner.hide_warning()

        self.info_frame = QFrame()
        self.info_frame.setObjectName("RefundInfoFrame")
        self.info_frame.setStyleSheet(
            "#RefundInfoFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
        )
        info_layout = QGridLayout(self.info_frame)
        info_layout.setContentsMargins(15, 15, 15, 15)
        info_layout.setHorizontalSpacing(20)
        info_layout.setVerticalSpacing(10)

        # Griglia 2x2 come la legacy: Dati Generali / Dati Fiscali (riga
        # 0), Collegamenti / Note (riga 1).
        for i, name in enumerate(self.SECTIONS):
            section_frame = QFrame()
            section_frame.setObjectName("RefundInfoSectionFrame")
            section_frame.setStyleSheet(
                "#RefundInfoSectionFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
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
            DBRefundsColumns.REFUND_NAME.value,
            "Nome Rimborso",
            self._make_line_edit(refund_data.get(DBRefundsColumns.REFUND_NAME.value, "")),
        )
        self._add_field(
            "Dati Generali",
            DBRefundsColumns.REFUND_DATE.value,
            "Data Rimborso",
            self._make_date_edit(refund_data.get(DBRefundsColumns.REFUND_DATE.value)),
        )

        # --- Dati Fiscali ---
        self._add_field(
            "Dati Fiscali",
            DBRefundsColumns.REFUND_AMOUNT.value,
            "Importo Rimborsato (€)",
            self._make_line_edit(refund_data.get(DBRefundsColumns.REFUND_AMOUNT.value, ""), money=True),
        )

        # --- Collegamenti ---
        clients = self.clients_query_service.retrieve_clients_map_list()
        client_combo = QTFilterableComboBox(
            values=[c[DBClientsColumns.NAME.value] for c in clients],
            placeholder="Cerca cliente…",
            autofill=True,
        )
        client_id = refund_data.get(DBRefundsColumns.CLIENT_ID.value)
        client = self.clients_query_service.retrieve_client_map_by_id(client_id) if client_id else None
        client_combo.set_value(client[DBClientsColumns.NAME.value] if client else "")
        self._add_field("Collegamenti", self.CLIENT_FIELD, "Cliente", client_combo)

        accounts = self.accounts_query_service.retrieve_accounts_map_list()
        account_combo = QComboBox()
        account_combo.addItems([a[DBAccountsColumns.NAME.value] for a in accounts])
        account_id = refund_data.get(DBRefundsColumns.CONTO_ID.value)
        account = self.accounts_query_service.retrieve_account_map_by_id(account_id) if account_id else None
        self._set_combo_text(account_combo, account[DBAccountsColumns.NAME.value] if account else None)
        self._add_field("Collegamenti", self.ACCOUNT_FIELD, "Conto", account_combo)

        # --- Note: timestamp read-only ---
        created_lbl = QLabel(str(refund_data.get(DBRefundsColumns.CREATED_AT.value, "") or ""))
        self._add_field("Note", DBRefundsColumns.CREATED_AT.value, "Data Creazione", created_lbl)

        updated_lbl = QLabel(str(refund_data.get(DBRefundsColumns.UPDATED_AT.value, "") or ""))
        self._add_field("Note", DBRefundsColumns.UPDATED_AT.value, "Ultimo Aggiornamento", updated_lbl)

        for name, grid in self.section_grids.items():
            grid.setRowStretch(self.section_rows[name], 1)

        # Riga bottoni Salva / Elimina.
        buttons_frame = QFrame()
        buttons_layout = QHBoxLayout(buttons_frame)
        buttons_layout.setContentsMargins(15, 15, 15, 15)

        self.save_btn = QPushButton("Salva Rimborso")
        self.save_btn.clicked.connect(self._save_refund_mod)
        buttons_layout.addWidget(self.save_btn)

        buttons_layout.addStretch(1)

        self.delete_btn = QPushButton("Elimina Rimborso")
        self.delete_btn.setStyleSheet(
            "QPushButton { background-color: #8B0000; color: palette(highlighted-text); }"
            "QPushButton:hover { background-color: #A52A2A; }"
            "QPushButton:disabled { background-color: #4a2727; color: palette(mid); }"
        )
        self.delete_btn.clicked.connect(self._delete_refund)
        buttons_layout.addWidget(self.delete_btn)

        info_layout.addWidget(buttons_frame, 2, 0, 1, 2)

        self.content_layout.addWidget(self.info_frame)

    def _add_field(self, section_name, key, label_text, widget):
        grid = self.section_grids[section_name]
        row = self.section_rows[section_name]
        label = QLabel(label_text + ":")
        grid.addWidget(label, row, 0, alignment=Qt.AlignLeft)
        grid.addWidget(widget, row, 1)
        self.refund_widgets[key] = widget
        self.refund_labels[key] = label
        self.section_rows[section_name] = row + 1

    def _make_line_edit(self, value, money=False):
        edit = QLineEdit()
        if money and value not in (None, ""):
            try:
                value = f"{float(value):.2f}"
            except (TypeError, ValueError):
                pass
        edit.setText(str(value) if value is not None else "")
        return edit

    def _make_date_edit(self, value):
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("yyyy-MM-dd")
        if value:
            qd = QDate.fromString(str(value), "yyyy-MM-dd")
            if qd.isValid():
                date_edit.setDate(qd)
            else:
                date_edit.setDate(QDate.currentDate())
        else:
            date_edit.setDate(QDate.currentDate())
        return date_edit

    # ------------------------------------------------------------------
    # Caricamento dati di un rimborso specifico
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Warning di consistenza (sev 1)
    # ------------------------------------------------------------------

    def _compute_current_warning(self, refund):
        try:
            service = self.app_context.refund_warning_service
            warnings = service.collect_warnings_for_list([refund]) or {}
            return warnings.get(refund.get(DBRefundsColumns.REFUND_NAME.value))
        except Exception:
            return None

    @staticmethod
    def _is_consistency_warning(info) -> bool:
        return isinstance(info, WarningInfo) and info.severity == WarningSeverity.CONSISTENCY

    _BROKEN_FIELD_WIDGET_MAP_REFUND = {
        DBRefundsColumns.CLIENT_ID.value: "CLIENTE ASSOCIATO",
        DBRefundsColumns.CONTO_ID.value: "CONTO",
    }

    def _apply_broken_field_highlight(self):
        info = getattr(self, "_current_warning_info", None)
        if not self._is_consistency_warning(info) or not info.broken_field_key:
            return
        widget_key = self._BROKEN_FIELD_WIDGET_MAP_REFUND.get(
            info.broken_field_key, info.broken_field_key
        )
        widget = getattr(self, "refund_widgets", {}).get(widget_key)
        if widget is None:
            return
        widget.setStyleSheet(
            widget.styleSheet() + " border: 2px solid #d62929; border-radius: 4px;"
        )

    # ------------------------------------------------------------------
    # Caricamento
    # ------------------------------------------------------------------

    def load_refund(self, refund_id):
        self.current_refund_id = refund_id
        self._clear_content()

        refund = self.refunds_query_service.retrieve_refund_map_by_id(refund_id)
        if not refund:
            self.title_label.setText("Rimborso non trovato")
            return

        self.refund = refund
        self.title_label.setText(str(refund.get(DBRefundsColumns.REFUND_NAME.value, "")))

        self._build_info_section(refund)
        self._toggle_edit(self.modify_switch.isChecked())
        self._apply_broken_field_highlight()

    def _clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.refund_widgets.clear()
        self.refund_labels.clear()
        self.section_grids.clear()
        self.section_rows.clear()
        self.modify_switch.blockSignals(True)
        self.modify_switch.setChecked(False)
        self.modify_switch.blockSignals(False)

    # ------------------------------------------------------------------
    # Modifica abilitata/disabilitata
    # ------------------------------------------------------------------

    def _toggle_edit(self, enabled):
        if not hasattr(self, "save_btn"):
            return

        self.save_btn.setEnabled(enabled)
        self.delete_btn.setEnabled(enabled)

        readonly_keys = {
            DBRefundsColumns.CREATED_AT.value,
            DBRefundsColumns.UPDATED_AT.value,
        }
        for key, widget in self.refund_widgets.items():
            if key in readonly_keys:
                continue
            widget.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Salvataggio / eliminazione
    # ------------------------------------------------------------------

    def _save_refund_mod(self):
        account_name = self._combo_text(self.ACCOUNT_FIELD)
        account = self.accounts_query_service.retrieve_account_map_by_name(account_name)
        client_name = self._combo_text(self.CLIENT_FIELD)
        client = self.clients_query_service.retrieve_client_map_by_name(client_name)

        date_widget: QDateEdit = self.refund_widgets[DBRefundsColumns.REFUND_DATE.value]

        refund_data = {
            DBRefundsColumns.REFUND_NAME.value: self.refund_widgets[
                DBRefundsColumns.REFUND_NAME.value
            ].text().strip(),
            DBRefundsColumns.REFUND_DATE.value: date_widget.date().toString("yyyy-MM-dd"),
            DBRefundsColumns.REFUND_AMOUNT.value: self.refund_widgets[
                DBRefundsColumns.REFUND_AMOUNT.value
            ].text().strip(),
            DBRefundsColumns.CLIENT_ID.value: client[DBClientsColumns.ID.value] if client else None,
            DBRefundsColumns.CONTO_ID.value: account[DBAccountsColumns.ID.value] if account else None,
        }

        success, message = self.refund_controller.update_refund(self.current_refund_id, refund_data)
        if not success:
            QMessageBox.critical(self, "ERRORE", message)
            return

        QMessageBox.information(self, "SALVATAGGIO COMPLETATO", message)
        self.modify_switch.setChecked(False)
        self.load_refund(self.current_refund_id)

    def _delete_refund(self):
        confirm = QMessageBox.question(
            self,
            "ELIMINAZIONE RIMBORSO",
            "Stai per eliminare questo rimborso.\nDesideri continuare?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        success, message = self.refund_controller.delete_refund(self.current_refund_id)
        if not success:
            QMessageBox.critical(self, "ERRORE", message)
            return

        QMessageBox.information(self, "RIMBORSO ELIMINATO", message)
        self._cleanup_and_go_back()

    # ------------------------------------------------------------------
    # Helper grafici
    # ------------------------------------------------------------------

    def _cleanup_and_go_back(self):
        if self.on_back is not None:
            self.on_back()

    def _combo_text(self, key):
        widget = self.refund_widgets.get(key)
        if isinstance(widget, QTFilterableComboBox):
            return widget.value()
        if isinstance(widget, QComboBox):
            return widget.currentText().strip()
        if hasattr(widget, "text"):
            return widget.text().strip()
        return ""

    def _set_combo_text(self, combo, value):
        if value is None:
            return
        if isinstance(combo, QTFilterableComboBox):
            combo.set_value(value)
            return
        text = str(value)
        idx = combo.findText(text)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        elif combo.isEditable():
            combo.setEditText(text)

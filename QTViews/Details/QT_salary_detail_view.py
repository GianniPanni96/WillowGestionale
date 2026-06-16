"""
Versione QT del dettaglio di un salario.

Equivalente di Views/Details/Salary_detail_view.SalaryDetailView,
portato sui widget Qt mantenendo la stessa logica di dominio:
- sezione informazioni con sezioni "Dati Generali", "Collegamenti",
  "Note" (la legacy usa una griglia con 3 sezioni, non 4);
- utente e conto come QComboBox (nessuna entita' di filtro avanzato:
  numero di utenti basso);
- switch "Abilita la modifica" che sblocca i campi editabili e i
  bottoni Salva / Elimina;
- conferma utente prima dell'eliminazione.

Strutturalmente segue il pattern di QTRefundDetailViewH /
QTPaymentDetailViewH.
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
    DBSalariesColumns,
    DBUsersColumns,
)
from QTViews.CustomWidgets.QT_warning_banner import WarningBanner
from WarningServices.Warning_types import WarningInfo, WarningSeverity

if TYPE_CHECKING:
    from App_context import AppContext


class QTSalaryDetailViewH(QWidget):
    """
    QWidget dettaglio salario.
    """

    ACCOUNT_FIELD = "CONTO"
    USER_FIELD = "UTENTE"

    SECTIONS = ["Dati Generali", "Collegamenti", "Note"]

    def __init__(self, app_context: "AppContext", salary_id, on_back, parent=None):
        super().__init__(parent)

        self.app_context = app_context
        self.salary_controller = app_context.salary_controller
        self.salary_query_service = app_context.salary_query_service
        self.user_query_service = app_context.user_query_service
        self.accounts_query_service = app_context.account_query_service

        self.current_salary_id = salary_id
        self.salary = None
        self.on_back = on_back

        self.salary_widgets: dict = {}
        self.salary_labels: dict = {}
        self.section_grids: dict = {}
        self.section_rows: dict = {}

        self._build_ui()
        self.load_salary(salary_id)

    # ------------------------------------------------------------------
    # UI base
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        head = QFrame()
        head.setObjectName("SalaryDetailHead")
        head.setStyleSheet(
            "#SalaryDetailHead { background-color: palette(window); border-radius: 6px; }"
        )
        head_layout = QHBoxLayout(head)
        head_layout.setContentsMargins(10, 6, 10, 6)

        self.back_button = QPushButton("Elenco Stipendi")
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

    def _build_info_section(self, salary_data):
        # Warning banner: visibile solo per i sev 1 (FK rotte).
        self.warning_banner = WarningBanner()
        self.content_layout.addWidget(self.warning_banner)
        self._current_warning_info = self._compute_current_warning(salary_data)
        if self._is_consistency_warning(self._current_warning_info):
            self.warning_banner.set_warning(self._current_warning_info)
        else:
            self.warning_banner.hide_warning()

        self.info_frame = QFrame()
        self.info_frame.setObjectName("SalaryInfoFrame")
        self.info_frame.setStyleSheet(
            "#SalaryInfoFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
        )
        info_layout = QGridLayout(self.info_frame)
        info_layout.setContentsMargins(15, 15, 15, 15)
        info_layout.setHorizontalSpacing(20)
        info_layout.setVerticalSpacing(10)

        # Griglia: 3 sezioni in due righe (la legacy mette
        # Dati Generali + Collegamenti su riga 0 e Note su riga 1).
        for i, name in enumerate(self.SECTIONS):
            section_frame = QFrame()
            section_frame.setObjectName("SalaryInfoSectionFrame")
            section_frame.setStyleSheet(
                "#SalaryInfoSectionFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
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
            DBSalariesColumns.NAME.value,
            "Nome Stipendio",
            self._make_line_edit(salary_data.get(DBSalariesColumns.NAME.value, "")),
        )
        self._add_field(
            "Dati Generali",
            DBSalariesColumns.DATE.value,
            "Data Stipendio",
            self._make_date_edit(salary_data.get(DBSalariesColumns.DATE.value)),
        )
        self._add_field(
            "Dati Generali",
            DBSalariesColumns.AMOUNT.value,
            "Importo (€)",
            self._make_line_edit(salary_data.get(DBSalariesColumns.AMOUNT.value, ""), money=True),
        )

        # --- Collegamenti ---
        accounts = self.accounts_query_service.retrieve_accounts_map_list()
        account_combo = QComboBox()
        account_combo.addItems([a[DBAccountsColumns.NAME.value] for a in accounts])
        self._set_combo_text(account_combo, salary_data.get(self.ACCOUNT_FIELD, ""))
        self._add_field("Collegamenti", self.ACCOUNT_FIELD, "Conto", account_combo)

        users = self.user_query_service.retrieve_users_map_list()
        user_combo = QComboBox()
        user_combo.addItems([
            f"{u[DBUsersColumns.FIRST_NAME.value]} {u[DBUsersColumns.LAST_NAME.value]}"
            for u in users
        ])
        self._set_combo_text(user_combo, salary_data.get(self.USER_FIELD, ""))
        self._add_field("Collegamenti", self.USER_FIELD, "Utente", user_combo)

        # --- Note: timestamp read-only ---
        created_lbl = QLabel(str(salary_data.get(DBSalariesColumns.CREATED_AT.value, "") or ""))
        self._add_field("Note", DBSalariesColumns.CREATED_AT.value, "Data Creazione", created_lbl)

        updated_lbl = QLabel(str(salary_data.get(DBSalariesColumns.UPDATED_AT.value, "") or ""))
        self._add_field("Note", DBSalariesColumns.UPDATED_AT.value, "Ultimo Aggiornamento", updated_lbl)

        # Riga bottoni Salva / Elimina.
        buttons_frame = QFrame()
        buttons_layout = QHBoxLayout(buttons_frame)
        buttons_layout.setContentsMargins(15, 15, 15, 15)

        self.save_btn = QPushButton("Salva Stipendio")
        self.save_btn.clicked.connect(self._save_salary_mod)
        buttons_layout.addWidget(self.save_btn, alignment=Qt.AlignBottom)

        buttons_layout.addStretch(1)

        self.delete_btn = QPushButton("Elimina Stipendio")
        self.delete_btn.setStyleSheet(
            "QPushButton { background-color: #8B0000; color: palette(highlighted-text); }"
            "QPushButton:hover { background-color: #A52A2A; }"
            "QPushButton:disabled { background-color: #4a2727; color: palette(mid); }"
        )
        self.delete_btn.clicked.connect(self._delete_salary)
        buttons_layout.addWidget(self.delete_btn, alignment=Qt.AlignBottom)

        info_layout.addWidget(buttons_frame, 2, 0, 1, 2)

        self.content_layout.addWidget(self.info_frame)

    def _add_field(self, section_name, key, label_text, widget):
        grid = self.section_grids[section_name]
        row = self.section_rows[section_name]
        label = QLabel(label_text + ":")
        grid.addWidget(label, row, 0, alignment=Qt.AlignLeft)
        grid.addWidget(widget, row, 1)
        self.salary_widgets[key] = widget
        self.salary_labels[key] = label
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
    # Caricamento
    # ------------------------------------------------------------------

    def load_salary(self, salary_id):
        self.current_salary_id = salary_id
        self._clear_content()

        salary = self.salary_query_service.retrieve_salary_map_by_id(salary_id)
        if not salary:
            self.title_label.setText("Salario non trovato")
            return

        # Arricchiamo il dict con i nomi risolti, come la legacy.
        account = self.accounts_query_service.retrieve_account_map_by_id(
            salary.get(DBSalariesColumns.ACCOUNT_ID.value)
        )
        user = self.user_query_service.retrieve_user_map_by_id(
            salary.get(DBSalariesColumns.USER_ID.value)
        )
        salary[self.ACCOUNT_FIELD] = account[DBAccountsColumns.NAME.value] if account else ""
        salary[self.USER_FIELD] = (
            f"{user[DBUsersColumns.FIRST_NAME.value]} {user[DBUsersColumns.LAST_NAME.value]}"
            if user
            else ""
        )

        self.salary = salary
        self.title_label.setText(str(salary.get(DBSalariesColumns.NAME.value, "")))

        self._build_info_section(salary)
        self._toggle_edit(self.modify_switch.isChecked())
        self._apply_broken_field_highlight()

    # ------------------------------------------------------------------
    # Warning di consistenza (sev 1)
    # ------------------------------------------------------------------

    def _compute_current_warning(self, salary):
        try:
            service = self.app_context.salary_warning_service
            warnings = service.collect_warnings_for_list([salary]) or {}
            return warnings.get(salary.get(DBSalariesColumns.NAME.value))
        except Exception:
            return None

    @staticmethod
    def _is_consistency_warning(info) -> bool:
        return isinstance(info, WarningInfo) and info.severity == WarningSeverity.CONSISTENCY

    _BROKEN_FIELD_WIDGET_MAP_SALARY = {
        DBSalariesColumns.USER_ID.value: "UTENTE",
        DBSalariesColumns.ACCOUNT_ID.value: "CONTO",
    }

    def _apply_broken_field_highlight(self):
        info = getattr(self, "_current_warning_info", None)
        if not self._is_consistency_warning(info) or not info.broken_field_key:
            return
        widget_key = self._BROKEN_FIELD_WIDGET_MAP_SALARY.get(
            info.broken_field_key, info.broken_field_key
        )
        widget = getattr(self, "salary_widgets", {}).get(widget_key)
        if widget is None:
            return
        widget.setStyleSheet(
            widget.styleSheet() + " border: 2px solid #d62929; border-radius: 4px;"
        )

    def _clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.salary_widgets.clear()
        self.salary_labels.clear()
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
            DBSalariesColumns.CREATED_AT.value,
            DBSalariesColumns.UPDATED_AT.value,
        }
        for key, widget in self.salary_widgets.items():
            if key in readonly_keys:
                continue
            widget.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Salvataggio / eliminazione
    # ------------------------------------------------------------------

    def _save_salary_mod(self):
        account_name = self._combo_text(self.ACCOUNT_FIELD)
        account = self.accounts_query_service.retrieve_account_map_by_name(account_name)

        user_id = None
        user_name = self._combo_text(self.USER_FIELD)
        if user_name:
            parts = user_name.split(" ", 1)
            first_name = parts[0] if len(parts) > 0 else ""
            last_name = parts[1] if len(parts) > 1 else ""
            user = self.user_query_service.retrieve_user_map_by_fullname(first_name, last_name)
            user_id = user[DBUsersColumns.ID.value] if user else None

        date_widget: QDateEdit = self.salary_widgets[DBSalariesColumns.DATE.value]

        salary_data = {
            DBSalariesColumns.NAME.value: self.salary_widgets[DBSalariesColumns.NAME.value].text().strip(),
            DBSalariesColumns.DATE.value: date_widget.date().toString("yyyy-MM-dd"),
            DBSalariesColumns.AMOUNT.value: self.salary_widgets[DBSalariesColumns.AMOUNT.value].text().strip(),
            DBSalariesColumns.ACCOUNT_ID.value: account[DBAccountsColumns.ID.value] if account else None,
            DBSalariesColumns.USER_ID.value: user_id,
        }

        success, message = self.salary_controller.update_salary(self.current_salary_id, salary_data)
        if not success:
            QMessageBox.critical(self, "ERRORE", message)
            return

        QMessageBox.information(self, "SALVATAGGIO COMPLETATO", message)
        self.modify_switch.setChecked(False)
        self.load_salary(self.current_salary_id)

    def _delete_salary(self):
        confirm = QMessageBox.question(
            self,
            "ELIMINAZIONE STIPENDIO",
            "Stai per eliminare questo stipendio.\nDesideri continuare?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        success, message = self.salary_controller.delete_salary(self.current_salary_id)
        if not success:
            QMessageBox.critical(self, "ERRORE", message)
            return

        QMessageBox.information(self, "STIPENDIO ELIMINATO", message)
        self._cleanup_and_go_back()

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _cleanup_and_go_back(self):
        if self.on_back is not None:
            self.on_back()

    def _combo_text(self, key):
        widget = self.salary_widgets.get(key)
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

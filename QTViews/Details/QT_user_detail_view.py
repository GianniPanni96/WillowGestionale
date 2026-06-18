"""
Vista dettaglio utente, versione Qt.

Replica le sezioni della legacy ``Views/Details/User_detail_view.py``:
- info anagrafiche/fiscali editabili (Dati Anagrafici, Dati Fiscali, Foto,
  Status). I campi sensibili (``REDDITO_ESTERNO``,
  ``SPESE_DEDOTTE_ESTERNE``, acconti ``IRPEF/INPS`` dell'anno
  precedente, ``PASSWORD_LOGIN``) sono mostrati mascherati con un
  bottone "occhio" per la toggle visibility, e sono effettivamente
  modificabili solo se l'utente loggato sta visualizzando il proprio
  profilo (logica ``toggle_sensible_data`` della legacy);
- sezioni di collegamento agli altri domini (FATTURE WILLOW, SPESE
  ANTICIPATE, PAGAMENTI SALARIO, e per il regime ORDINARIO anche
  SPESE IN DEDUZIONE), con la rispettiva metrica aggregata e
  l'apertura del dettaglio dell'item via event_bus;
- sezione DATI FISCALI (aliquote + imponibili);
- sezione PREVISIONE TASSE per regime, con tooltip educativi che
  ricostruiscono il calcolo (ispirati alla legacy);
- sezione IVA TRIMESTRALE (solo regime ORDINARIO).

La barra dei bottoni Salva / Elimina e' inserita in fondo alla prima
sezione con i dati utente, dentro la scroll area.

Note di scope:
- la parte di login al provider di fatturazione elettronica (Aruba)
  resta omessa dalla UI; i campi ``PROVIDER_FATTURE``,
  ``USERNAME_PROVIDER``, ``PASSWORD_PROVIDER`` vengono preservati nel
  dict di update con i valori correnti del DB, cosi' il controller
  non li tratta come mancanti.
"""

import os
import re
from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
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
    DBExpensesColumns,
    DBInvoicesColumns,
    DBProductionsColumns,
    DBSalariesColumns,
    DBUsersColumns,
    RegimeFiscale,
    UserStatus,
)
from QTViews.CustomWidgets.QT_toggle_switch import QTToggleSwitch
from Utils.Controller_utils import ControllerUtils
from Utils.Validation_utils import ValidationUtils
from Utils.View_utils import ViewUtils

if TYPE_CHECKING:
    from App_context import AppContext


PHOTO_PREVIEW_SIZE = 160
DOMAIN_LINKS_LIST_HEIGHT = 380
TAX_WILLOW_HEADER_COLOR = "#2659ab"
TAX_DEFAULT_HEADER_COLOR = "gray"


# Campi "sensibili": mascherati con echo password + toggle visibility,
# editabili solo se l'utente loggato e' lo stesso del profilo aperto.
SENSITIVE_FIELDS = (
    DBUsersColumns.PASSWORD_LOGIN.value,
    DBUsersColumns.REDDITO_ESTERNO.value,
    DBUsersColumns.SPESE_DEDOTTE_ESTERNE.value,
    DBUsersColumns.LAST_YEAR_IRPEF_ACCONTO.value,
    DBUsersColumns.LAST_YEAR_INPS_ACCONTO.value,
)


def _fmt_eur(value) -> str:
    """Formattazione monetaria con separatore migliaia."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "0,00 €"
    s = f"{n:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    return f"{s} €"


def _localize_collective(text: str, name: str) -> str:
    """Sostituisce le occorrenze hard-coded del nome storico 'Willow'
    con il nome del collettivo configurato.

    Solo per stringhe user-facing (label, tooltip): le chiavi interne
    dei dict (es. ``"SALDO WILLOW"``, ``"WILLOW_IRPEF"``) NON devono
    passare da qui, restano stabili come identificatori.
    """
    if not text:
        return text
    return text.replace("WILLOW", name.upper()).replace("Willow", name)


class QTUserDetailViewH(QWidget):
    """QWidget dettaglio utente."""

    ACCOUNT_FIELD = "CONTO"

    # Sezioni anagrafiche/fiscali in grid 2x2.
    SECTIONS = ["Dati Anagrafici", "Dati Fiscali", "Foto", "Status"]

    def __init__(self, app_context: "AppContext", user_id, on_back, parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.user_controller = app_context.user_controller
        self.user_query_service = app_context.user_query_service
        self.user_analyzer_service = app_context.user_analyzer_service
        self.iva_analyzer_service = app_context.iva_analyzer_service
        self.accounts_query_service = app_context.account_query_service
        self.productions_query_service = app_context.productions_query_service
        self.event_bus = app_context.event_bus

        self.current_user_id = user_id
        self.user: dict | None = None
        self.on_back = on_back

        self._widgets: dict = {}
        self._labels: dict = {}
        self._eye_buttons: list[QPushButton] = []
        self._photo_path: str = ""
        self._section_grids: dict = {}
        self._section_rows: dict = {}
        self._login_password_is_present: bool = False

        # Nome del collettivo: usato per le label/tooltip che parlano del
        # gruppo (es. "FATTURE <nome>", "IRPEF <nome>", "Quota proporzionale
        # <nome>"). Fallback a "Willow" gia' gestito dal manager.
        self._collective_name = app_context.config_manager.app_settings_manager.get_collective_name()

        # Login state (aggiornato via event bus).
        parent_window = parent
        self._login_status: bool = getattr(parent_window, "login_status", False)
        self._logged_user_id: int = getattr(parent_window, "logged_user_id", -1)
        self._is_admin: bool = getattr(parent_window, "is_admin", False)

        try:
            self.event_bus.subscribe(
                ViewUtils.EventBusKeys.LOGIN_STATUS_CHANGED.value,
                self._on_login_changed,
            )
        except Exception:
            pass

        self._build_ui()
        self.load_user(user_id)

    # ------------------------------------------------------------------
    # UI base (head bar + scroll + action bar)
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # Head bar.
        head = QFrame()
        head.setObjectName("UserDetailHead")
        head.setStyleSheet(
            "#UserDetailHead { background-color: palette(window); border-radius: 6px; }"
        )
        head_layout = QHBoxLayout(head)
        head_layout.setContentsMargins(10, 6, 10, 6)

        self.back_button = QPushButton("Elenco Utenti")
        self.back_button.clicked.connect(self._cleanup_and_go_back)
        head_layout.addWidget(self.back_button)

        self.title_label = QLabel("")
        f = self.title_label.font()
        f.setPointSize(16)
        f.setBold(True)
        self.title_label.setFont(f)
        self.title_label.setAlignment(Qt.AlignCenter)
        head_layout.addWidget(self.title_label, stretch=1)

        self.modify_switch = QCheckBox("Abilita la modifica")
        self.modify_switch.toggled.connect(self._on_modify_toggled)
        head_layout.addWidget(self.modify_switch)

        root.addWidget(head)

        # Corpo scrollabile.
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        root.addWidget(self.scroll, stretch=1)

        self.content = QWidget()
        self.scroll.setWidget(self.content)
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        self.content_layout.setSpacing(15)

        # Action bar: Salva / Elimina. Viene inizializzata subito, ma
        # inserita in fondo alla prima sezione dati utente quando i dati
        # vengono caricati.
        self.action_bar = QFrame()
        self.action_bar.setObjectName("UserDetailActions")
        self.action_bar.setStyleSheet(
            "#UserDetailActions { background-color: palette(window); border-radius: 6px; }"
        )
        action_layout = QHBoxLayout(self.action_bar)
        action_layout.setContentsMargins(15, 8, 15, 8)

        self.save_btn = QPushButton("Salva Utente")
        self.save_btn.clicked.connect(self._save_user_mod)
        self.save_btn.setEnabled(False)
        action_layout.addWidget(self.save_btn)

        action_layout.addStretch(1)

        self.delete_btn = QPushButton("Elimina Utente")
        self.delete_btn.setStyleSheet(
            "QPushButton { background-color: #8B0000; color: palette(highlighted-text); }"
            "QPushButton:hover { background-color: #A52A2A; }"
            "QPushButton:disabled { background-color: #4a2727; color: palette(mid); }"
        )
        self.delete_btn.clicked.connect(self._delete_user)
        self.delete_btn.setEnabled(False)
        action_layout.addWidget(self.delete_btn)

    # ------------------------------------------------------------------
    # Info section (grid 2x2 anagrafica/fiscale/foto/status)
    # ------------------------------------------------------------------

    def _build_info_section(self, user_data: dict):
        self.info_frame = QFrame()
        self.info_frame.setObjectName("UserInfoFrame")
        self.info_frame.setStyleSheet(
            "#UserInfoFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
        )
        info_layout = QGridLayout(self.info_frame)
        info_layout.setContentsMargins(15, 15, 15, 15)
        info_layout.setHorizontalSpacing(20)
        info_layout.setVerticalSpacing(10)

        for i, name in enumerate(self.SECTIONS):
            section_frame = QFrame()
            section_frame.setObjectName("UserInfoSectionFrame")
            section_frame.setStyleSheet(
                "#UserInfoSectionFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
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
            self._section_grids[name] = section_layout
            self._section_rows[name] = 1

        regime_value = str(user_data.get(DBUsersColumns.REGIME_FISCALE.value, "") or "")

        # --- Dati Anagrafici ---
        self._add_field("Dati Anagrafici", DBUsersColumns.FIRST_NAME.value, "Nome",
                        self._make_line_edit(user_data.get(DBUsersColumns.FIRST_NAME.value, "")))
        self._add_field("Dati Anagrafici", DBUsersColumns.LAST_NAME.value, "Cognome",
                        self._make_line_edit(user_data.get(DBUsersColumns.LAST_NAME.value, "")))
        self._add_field("Dati Anagrafici", DBUsersColumns.EMAIL.value, "Email",
                        self._make_line_edit(user_data.get(DBUsersColumns.EMAIL.value, "")))
        self._add_field("Dati Anagrafici", DBUsersColumns.TELEFONO.value, "Telefono",
                        self._make_line_edit(user_data.get(DBUsersColumns.TELEFONO.value, "")))

        # Password di login: campo sempre vuoto (mostriamo solo il segnale
        # che esiste o no nel DB tramite ``_login_password_is_present``).
        # Se valorizzata in fase di save, il controller la fa hashare.
        stored_hash = str(user_data.get(DBUsersColumns.PASSWORD_LOGIN.value, "") or "")
        self._login_password_is_present = len(stored_hash) >= 128
        password_edit = self._make_line_edit("")
        password_edit.setEchoMode(QLineEdit.Password)
        wrapper = self._wrap_with_eye_toggle(password_edit)
        self._add_field("Dati Anagrafici", DBUsersColumns.PASSWORD_LOGIN.value,
                        "Nuova Login Password", wrapper)

        # --- Dati Fiscali ---
        self._add_field("Dati Fiscali", DBUsersColumns.PARTITA_IVA.value, "Partita IVA",
                        self._make_line_edit(user_data.get(DBUsersColumns.PARTITA_IVA.value, "")))
        self._add_field("Dati Fiscali", DBUsersColumns.CODICE_FISCALE.value, "Codice Fiscale",
                        self._make_line_edit(user_data.get(DBUsersColumns.CODICE_FISCALE.value, "")))

        regime_combo = QComboBox()
        regime_combo.addItems([item.value for item in RegimeFiscale])
        self._set_combo_text(regime_combo, user_data.get(DBUsersColumns.REGIME_FISCALE.value))
        self._add_field("Dati Fiscali", DBUsersColumns.REGIME_FISCALE.value, "Regime Fiscale", regime_combo)

        anno_combo = QComboBox()
        current_year = datetime.now().year
        anno_combo.addItems([str(y) for y in range(2000, current_year + 1)])
        self._set_combo_text(anno_combo, user_data.get(DBUsersColumns.ANNO_APERTURA_PIVA.value))
        self._add_field("Dati Fiscali", DBUsersColumns.ANNO_APERTURA_PIVA.value, "Anno apertura P. IVA", anno_combo)

        accounts = self.accounts_query_service.retrieve_accounts_map_list() or []
        account_combo = QComboBox()
        account_combo.addItems([a[DBAccountsColumns.NAME.value] for a in accounts])
        self._set_combo_text(account_combo, user_data.get(self.ACCOUNT_FIELD, ""))
        self._add_field("Dati Fiscali", self.ACCOUNT_FIELD, "Conto Corrente", account_combo)

        # Campi sensibili monetari (password-masked, eye toggle).
        self._add_sensitive_money_field(
            "Dati Fiscali",
            DBUsersColumns.REDDITO_ESTERNO.value,
            "Reddito Esterno",
            user_data.get(DBUsersColumns.REDDITO_ESTERNO.value, ""),
            tooltip=(
                "Ricavi/fatturato LORDO da attività svolte al di fuori del collettivo, "
                "al netto dell'IVA (l'IVA non è reddito).\n\n"
                "Inserisci l'imponibile dei compensi esterni, non il totale documento.\n"
                "• Forfettario: a questo importo viene applicato il coefficiente di "
                "redditività come al fatturato interno.\n"
                "• Ordinario: è un ricavo lordo, da cui si sottraggono le 'Spese Dedotte "
                "Esterne'."
            ),
        )
        # Spese dedotte esterne: solo regime ORDINARIO (la legacy salta
        # questo campo per il forfettario).
        if regime_value == RegimeFiscale.ORDINARIO.value:
            self._add_sensitive_money_field(
                "Dati Fiscali",
                DBUsersColumns.SPESE_DEDOTTE_ESTERNE.value,
                "Spese Dedotte Esterne",
                user_data.get(DBUsersColumns.SPESE_DEDOTTE_ESTERNE.value, ""),
                tooltip=(
                    "Spese deducibili (inerenti all'attività) sostenute al di fuori del "
                    "collettivo, al netto dell'IVA.\n\n"
                    "Vengono sottratte dai ricavi esterni per determinare il reddito netto "
                    "imponibile. Non includere spese già registrate come 'Spese in "
                    "deduzione' interne al collettivo."
                ),
            )
        self._add_sensitive_money_field(
            "Dati Fiscali",
            DBUsersColumns.LAST_YEAR_IRPEF_ACCONTO.value,
            f"Acconto IRPEF \n(versato durante il {datetime.today().year - 1})",
            user_data.get(DBUsersColumns.LAST_YEAR_IRPEF_ACCONTO.value, ""),
        )
        self._add_sensitive_money_field(
            "Dati Fiscali",
            DBUsersColumns.LAST_YEAR_INPS_ACCONTO.value,
            f"Acconto INPS \n(versato durante il {datetime.today().year - 1})",
            user_data.get(DBUsersColumns.LAST_YEAR_INPS_ACCONTO.value, ""),
        )

        # --- Foto ---
        self._build_photo_widgets(user_data)

        # --- Status ---
        status_combo = QComboBox()
        status_combo.addItems([s.value for s in UserStatus])
        self._set_combo_text(status_combo, user_data.get(DBUsersColumns.STATUS.value))
        self._add_field("Status", DBUsersColumns.STATUS.value, "Status", status_combo)

        # Note timestamp read-only (in coda alla colonna Status).
        created_lbl = QLabel(str(user_data.get(DBUsersColumns.CREATED_AT.value, "") or ""))
        self._add_field("Status", DBUsersColumns.CREATED_AT.value, "Data Creazione", created_lbl)
        updated_lbl = QLabel(str(user_data.get(DBUsersColumns.UPDATED_AT.value, "") or ""))
        self._add_field("Status", DBUsersColumns.UPDATED_AT.value, "Ultimo Aggiornamento", updated_lbl)

        info_layout.addWidget(self.action_bar, 2, 0, 1, 2)

        self.content_layout.addWidget(self.info_frame)

    # ------------------------------------------------------------------
    # Sensitive widgets + eye toggle
    # ------------------------------------------------------------------

    def _add_sensitive_money_field(self, section_name, key, label_text, value, tooltip: str = ""):
        if value not in (None, ""):
            try:
                value = f"{float(value):.2f}"
            except (TypeError, ValueError):
                pass
        edit = self._make_line_edit(str(value) if value not in (None, "") else "")
        edit.setEchoMode(QLineEdit.Password)
        wrapper = self._wrap_with_eye_toggle(edit)
        if tooltip:
            edit.setToolTip(tooltip)
            wrapper.setToolTip(tooltip)
        self._add_field(section_name, key, label_text, wrapper)
        if tooltip:
            label = self._labels.get(key)
            if label is not None:
                label.setToolTip(tooltip)

    def _wrap_with_eye_toggle(self, line_edit: QLineEdit) -> QWidget:
        """Wrappa un ``QLineEdit`` (in echo Password) con un bottone occhio
        per la toggle visibility, e ritorna il widget wrapper. Il
        ``QLineEdit`` viene memorizzato dentro al widget come
        ``wrapper.entry`` cosi' il caller puo' continuare a leggerne
        il valore."""
        wrapper = QWidget()
        wrapper.setProperty("entry", line_edit)
        hbox = QHBoxLayout(wrapper)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)
        hbox.addWidget(line_edit, stretch=1)

        eye_btn = QPushButton("👁")
        eye_btn.setFixedWidth(34)
        eye_btn.setCheckable(True)
        eye_btn.clicked.connect(lambda _checked, e=line_edit, b=eye_btn: self._toggle_eye(e, b))
        hbox.addWidget(eye_btn)
        self._eye_buttons.append(eye_btn)

        # Esponiamo entry + eye button come attributi: serve a
        # ``_apply_sensitive_visibility_policy`` per resettare in modo
        # coerente echo e label del pulsante quando si rientra nello
        # stato "campo oscurato".
        wrapper.entry = line_edit  # type: ignore[attr-defined]
        wrapper.eye_button = eye_btn  # type: ignore[attr-defined]
        return wrapper

    @staticmethod
    def _toggle_eye(line_edit: QLineEdit, button: QPushButton):
        if line_edit.echoMode() == QLineEdit.Password:
            line_edit.setEchoMode(QLineEdit.Normal)
            button.setText("🔒")
        else:
            line_edit.setEchoMode(QLineEdit.Password)
            button.setText("👁")

    # ------------------------------------------------------------------
    # Foto
    # ------------------------------------------------------------------

    def _build_photo_widgets(self, user_data: dict):
        wrapper = QWidget()
        v = QVBoxLayout(wrapper)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)

        self._photo_preview = QLabel("Nessuna immagine")
        self._photo_preview.setAlignment(Qt.AlignCenter)
        self._photo_preview.setFixedSize(PHOTO_PREVIEW_SIZE, PHOTO_PREVIEW_SIZE)
        self._photo_preview.setStyleSheet(
            "QLabel {"
            " background-color: palette(window);"
            " border: 1px dashed palette(mid);"
            " border-radius: 6px;"
            " color: palette(mid);"
            "}"
        )
        v.addWidget(self._photo_preview, alignment=Qt.AlignCenter)

        row = QHBoxLayout()
        self._photo_btn = QPushButton("Scegli Immagine…")
        self._photo_btn.clicked.connect(self._on_choose_photo)
        row.addWidget(self._photo_btn)
        self._photo_clear_btn = QPushButton("Rimuovi")
        self._photo_clear_btn.clicked.connect(self._on_clear_photo)
        row.addWidget(self._photo_clear_btn)
        v.addLayout(row)

        self._photo_name_lbl = QLabel("Nessuna immagine selezionata")
        self._photo_name_lbl.setStyleSheet("color: palette(mid);")
        v.addWidget(self._photo_name_lbl, alignment=Qt.AlignCenter)

        path = user_data.get(DBUsersColumns.PHOTO_PATH.value) or ""
        if path and os.path.exists(path):
            self._set_photo(path)
        else:
            self._photo_path = ""

        self._widgets["_photo_buttons_choose"] = self._photo_btn
        self._widgets["_photo_buttons_clear"] = self._photo_clear_btn

        grid = self._section_grids["Foto"]
        row_idx = self._section_rows["Foto"]
        grid.addWidget(wrapper, row_idx, 0, 1, 2)
        self._section_rows["Foto"] = row_idx + 1

    def _set_photo(self, path: str):
        self._photo_path = path
        self._photo_name_lbl.setText(os.path.basename(path))
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self._photo_preview.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self._photo_preview.setPixmap(scaled)
            self._photo_preview.setText("")
        else:
            self._photo_preview.clear()
            self._photo_preview.setText("Immagine non valida")

    def _on_choose_photo(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleziona un'immagine",
            "",
            "Immagini (*.png *.jpg *.jpeg *.gif *.bmp)",
        )
        if path:
            self._set_photo(path)

    def _on_clear_photo(self):
        self._photo_path = ""
        self._photo_preview.clear()
        self._photo_preview.setText("Nessuna immagine")
        self._photo_name_lbl.setText("Nessuna immagine selezionata")

    # ------------------------------------------------------------------
    # Sezioni STORICO (collegamenti ad altri item dei domini)
    # ------------------------------------------------------------------

    def _build_history_sections(self, regime_value: str):
        """Costruisce, in due righe orizzontali, le sezioni di storico:
        prima riga: FATTURE / SPESE ANTICIPATE / SALARI / (SPESE DEDUZIONE
        solo se regime ORDINARIO).
        """
        wrapper = QFrame()
        wrapper_layout = QHBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(15)

        wrapper_layout.addWidget(self._build_invoices_section(), stretch=1)
        wrapper_layout.addWidget(self._build_anticipated_expenses_section(), stretch=1)
        wrapper_layout.addWidget(self._build_salary_section(), stretch=1)
        if regime_value == RegimeFiscale.ORDINARIO.value:
            wrapper_layout.addWidget(self._build_deduz_expenses_section(), stretch=1)

        self.content_layout.addWidget(wrapper)

    def _build_invoices_section(self) -> QFrame:
        section = QFrame()
        section.setObjectName("UserSectionFrame")
        section.setStyleSheet(
            "#UserSectionFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
        )
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(15, 12, 15, 12)
        section_layout.setSpacing(8)

        # Header: titolo a sinistra, switch ancorato a destra con label
        # descrittiva subito prima dello switch.
        header_row = QHBoxLayout()
        title_lbl = QLabel(f"FATTURE {self._collective_name.upper()}")
        f = title_lbl.font()
        f.setBold(True)
        f.setPointSize(12)
        title_lbl.setFont(f)
        header_row.addWidget(title_lbl)
        header_row.addStretch(1)

        toggle_lbl = QLabel("Includi insoluti anno prec.")
        header_row.addWidget(toggle_lbl)
        self._invoices_toggle = QTToggleSwitch(
            on_change=self._on_invoices_toggle,
            initial=True,
        )
        header_row.addWidget(self._invoices_toggle)
        section_layout.addLayout(header_row)

        # Aggregate card con riferimento al label del valore per aggiornamenti.
        agg_card = self._make_aggregate_card(
            f"TOTALE FATTURATO {self._collective_name.upper()}",
            _fmt_eur(self.user_analyzer_service.calcola_tot_fatturato_utente(
                self.current_user_id, year=None, include_unpaid_invoices=True,
            )),
        )
        self._invoices_aggregate_value_lbl = agg_card.layout().itemAt(1).widget()
        section_layout.addWidget(agg_card)

        # Scroll area: la lista delle cards viene popolata tramite
        # _populate_invoices_list per poter essere ricostruita al toggle.
        list_scroll = QScrollArea()
        list_scroll.setWidgetResizable(True)
        list_scroll.setFixedHeight(280)
        list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        list_scroll.setWidget(inner)
        self._invoices_inner_layout = QVBoxLayout(inner)
        self._invoices_inner_layout.setContentsMargins(2, 2, 2, 2)
        self._invoices_inner_layout.setSpacing(6)

        self._populate_invoices_list(include_unpaid=True)

        section_layout.addWidget(list_scroll, stretch=1)
        return section

    def _populate_invoices_list(self, include_unpaid: bool):
        """Pulisce e ricostruisce la lista di button-cards fatture."""
        while self._invoices_inner_layout.count():
            item = self._invoices_inner_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        current_year = datetime.now().year
        warn_prev_year = (
            include_unpaid
            and self.app_context.warnings_visibility_manager.is_warning_enabled("fatture", "previous_year")
        )

        invoices = self.user_query_service.retrieve_user_with_invoices_map_list(
            self.current_user_id, year=None, include_unpaid_invoices=include_unpaid,
        ) or []

        for invoice in invoices:
            nome_fattura = invoice.get(DBInvoicesColumns.NUMERO_FATTURA.value)
            if not nome_fattura:
                continue
            id_fattura = invoice[DBInvoicesColumns.ID.value]
            id_produzione = invoice.get(DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value)
            produzione = (
                self.productions_query_service.retrieve_production_map_by_id(id_produzione)
                if id_produzione else None
            )
            nome_prod = produzione[DBProductionsColumns.NAME.value] if produzione else "Produzione non trovata"

            btn = QPushButton(f"{nome_fattura} — {nome_prod}")

            if warn_prev_year:
                data_str = invoice.get(DBInvoicesColumns.DATA_CREAZIONE.value)
                dt = ControllerUtils._parse_date(data_str) if data_str else None
                if dt and dt.year < current_year:
                    btn.setStyleSheet(
                        "text-align: left; padding: 6px;"
                        " border: 2px solid #FFC107; border-radius: 4px;"
                    )
                else:
                    btn.setStyleSheet("text-align: left; padding: 6px;")
            else:
                btn.setStyleSheet("text-align: left; padding: 6px;")

            btn.clicked.connect(lambda _=False, iid=id_fattura: self._show_invoice_detail(iid))
            self._invoices_inner_layout.addWidget(btn)

        self._invoices_inner_layout.addStretch(1)

    def _on_invoices_toggle(self, checked: bool):
        """Aggiorna aggregato e lista al cambio del toggle include_unpaid."""
        totale = self.user_analyzer_service.calcola_tot_fatturato_utente(
            self.current_user_id, year=None, include_unpaid_invoices=checked,
        )
        self._invoices_aggregate_value_lbl.setText(_fmt_eur(totale))
        self._populate_invoices_list(include_unpaid=checked)

    def _build_anticipated_expenses_section(self) -> QFrame:
        section = self._make_section_frame("SPESE ANTICIPATE")
        section.layout().addWidget(self._make_aggregate_card(
            "TOTALE SPESE ANTICIPATE",
            _fmt_eur(self.user_analyzer_service.calcola_tot_spese_utente_anticipate(self.current_user_id)),
        ))

        list_widget = QScrollArea()
        list_widget.setWidgetResizable(True)
        list_widget.setFixedHeight(280)
        inner = QWidget()
        list_widget.setWidget(inner)
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(2, 2, 2, 2)
        inner_layout.setSpacing(6)

        expenses = self.user_query_service.retrieve_user_with_anticipated_expenses_map_list(self.current_user_id) or []
        for expense in expenses:
            nome_spesa = expense.get(DBExpensesColumns.NAME.value)
            if not nome_spesa:
                continue
            id_spesa = expense[DBExpensesColumns.ID.value]
            btn = QPushButton(str(nome_spesa))
            btn.setStyleSheet("text-align: left; padding: 6px;")
            btn.clicked.connect(lambda _=False, eid=id_spesa: self._show_expense_detail(eid))
            inner_layout.addWidget(btn)
        inner_layout.addStretch(1)

        section.layout().addWidget(list_widget, stretch=1)
        return section

    def _build_salary_section(self) -> QFrame:
        section = self._make_section_frame("PAGAMENTI SALARIO")
        section.layout().addWidget(self._make_aggregate_card(
            "TOTALE SALARI",
            _fmt_eur(self.user_analyzer_service.calcola_tot_salari_utente(self.current_user_id)),
        ))

        list_widget = QScrollArea()
        list_widget.setWidgetResizable(True)
        list_widget.setFixedHeight(280)
        inner = QWidget()
        list_widget.setWidget(inner)
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(2, 2, 2, 2)
        inner_layout.setSpacing(6)

        salaries = self.user_query_service.retrieve_user_with_salaries_map_list(self.current_user_id) or []
        for salary in salaries:
            nome_salario = salary.get(DBSalariesColumns.NAME.value)
            if not nome_salario:
                continue
            id_salario = salary[DBSalariesColumns.ID.value]
            btn = QPushButton(str(nome_salario))
            btn.setStyleSheet("text-align: left; padding: 6px;")
            btn.clicked.connect(lambda _=False, sid=id_salario: self._show_salary_detail(sid))
            inner_layout.addWidget(btn)
        inner_layout.addStretch(1)

        section.layout().addWidget(list_widget, stretch=1)
        return section

    def _build_deduz_expenses_section(self) -> QFrame:
        section = self._make_section_frame("SPESE IN DEDUZIONE")
        section.layout().addWidget(self._make_aggregate_card(
            "TOTALE SPESE IN DEDUZIONE",
            _fmt_eur(self.user_analyzer_service.calcola_tot_spese_utente_dedotte(self.current_user_id)),
        ))

        list_widget = QScrollArea()
        list_widget.setWidgetResizable(True)
        list_widget.setFixedHeight(280)
        inner = QWidget()
        list_widget.setWidget(inner)
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(2, 2, 2, 2)
        inner_layout.setSpacing(6)

        expenses = self.user_query_service.retrieve_user_with_deducted_expenses_map_list(self.current_user_id) or []
        for expense in expenses:
            nome_spesa = expense.get(DBExpensesColumns.NAME.value)
            if not nome_spesa:
                continue
            id_spesa = expense[DBExpensesColumns.ID.value]
            btn = QPushButton(str(nome_spesa))
            btn.setStyleSheet("text-align: left; padding: 6px;")
            btn.clicked.connect(lambda _=False, eid=id_spesa: self._show_expense_detail(eid))
            inner_layout.addWidget(btn)
        inner_layout.addStretch(1)

        section.layout().addWidget(list_widget, stretch=1)
        return section

    # ------------------------------------------------------------------
    # Sezione DATI FISCALI (aliquote + imponibili)
    # ------------------------------------------------------------------

    def _build_fiscal_data_section(self):
        section = self._make_section_frame("DATI FISCALI")

        try:
            user_fiscal_data = self.user_analyzer_service.pick_fiscal_data_by_user_id(self.current_user_id) or {}
        except Exception:
            user_fiscal_data = {}
        aliquote = user_fiscal_data.get("aliquote", {}) or {}
        imponibili = user_fiscal_data.get("imponibili", {}) or {}

        two_col = QHBoxLayout()
        two_col.setSpacing(15)

        two_col.addWidget(self._build_kv_block("Aliquote", aliquote), stretch=1)
        two_col.addWidget(self._build_kv_block("Imponibili", imponibili), stretch=1)
        section.layout().addLayout(two_col)

        self.content_layout.addWidget(section)

    def _build_kv_block(self, title: str, data: dict) -> QFrame:
        frame = QFrame()
        frame.setObjectName("KvBlock")
        frame.setStyleSheet(
            "#KvBlock { background-color: palette(alternate-base); border-radius: 6px; }"
        )
        v = QVBoxLayout(frame)
        v.setContentsMargins(15, 10, 15, 10)
        v.setSpacing(6)

        title_lbl = QLabel(title)
        f = title_lbl.font()
        f.setBold(True)
        f.setPointSize(12)
        title_lbl.setFont(f)
        v.addWidget(title_lbl)

        if not data:
            empty = QLabel("Nessun dato disponibile")
            empty.setStyleSheet("color: palette(mid); font-style: italic;")
            v.addWidget(empty)
        else:
            for k, val in data.items():
                row = QHBoxLayout()
                row.setContentsMargins(0, 0, 0, 0)
                row.setSpacing(8)
                kk = QLabel(f"{k}:")
                kk.setStyleSheet("color: palette(text);")
                row.addWidget(kk, stretch=1)
                vv = QLabel(str(val))
                vv.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                vv.setStyleSheet("color: palette(text);")
                row.addWidget(vv)
                v.addLayout(row)
        v.addStretch(1)
        return frame

    # ------------------------------------------------------------------
    # Sezione PREVISIONE TASSE (per regime, con tooltip educativi)
    # ------------------------------------------------------------------

    def _build_taxes_section(self, regime_value: str):
        section = self._make_section_frame("PREVISIONE TASSE")

        try:
            if regime_value == RegimeFiscale.FORFETTARIO.value:
                tasse, versamenti, total = self.user_analyzer_service.calculate_previsione_tasse_forfettaria(self.current_user_id)
            else:
                tasse, versamenti, total = self.user_analyzer_service.calculate_previsione_tasse_ordinaria(self.current_user_id)
        except Exception:
            tasse, versamenti, total = {}, {}, {}

        # Card totali. Il key originale (es. "IRPEF WILLOW") rimane chiave
        # di lookup per i tooltip; la card visualizza la versione localizzata
        # col nome del collettivo.
        section.layout().addWidget(self._make_subtitle("Totali"))
        totali_row = QHBoxLayout()
        totali_row.setSpacing(10)
        for k, v in tasse.items():
            display_k = _localize_collective(k, self._collective_name)
            card = self._make_aggregate_card(display_k, _fmt_eur(v), header_color=self._tax_header_color(k))
            self._apply_tax_tooltip(card, k, total, regime_value, kind="totali")
            totali_row.addWidget(card, stretch=1)
        totali_row.addStretch(1)
        section.layout().addLayout(totali_row)

        # Card versamenti.
        section.layout().addWidget(self._make_subtitle("Versamenti"))
        versam_row = QHBoxLayout()
        versam_row.setSpacing(10)
        for k, v in versamenti.items():
            display_k = _localize_collective(k, self._collective_name)
            card = self._make_aggregate_card(display_k, _fmt_eur(v), header_color=self._tax_header_color(k))
            self._apply_tax_tooltip(card, k, total, regime_value, kind="versamenti")
            versam_row.addWidget(card, stretch=1)
        versam_row.addStretch(1)
        section.layout().addLayout(versam_row)

        self.content_layout.addWidget(section)

    def _apply_tax_tooltip(self, card_widget: QFrame, key: str, total: dict, regime_value: str, kind: str):
        """Imposta il tooltip educativo sulla card. La struttura del dict
        ``total`` cambia tra forfettario e ordinario; per i campi
        mancanti scriviamo "Informazioni non disponibili"."""
        text = ""
        try:
            if regime_value == RegimeFiscale.FORFETTARIO.value and kind == "totali":
                text = self._tooltip_forfettario_totali(key, total)
            elif regime_value == RegimeFiscale.FORFETTARIO.value and kind == "versamenti":
                text = self._tooltip_forfettario_versamenti(key, total)
            elif regime_value == RegimeFiscale.ORDINARIO.value and kind == "totali":
                text = self._tooltip_ordinario_totali(key, total)
            elif regime_value == RegimeFiscale.ORDINARIO.value and kind == "versamenti":
                text = self._tooltip_ordinario_versamenti(key, total)
        except Exception:
            text = ""
        if not text:
            text = "Informazioni non disponibili"
        else:
            text = _localize_collective(text, self._collective_name)
        card_widget.setToolTip(text)

    @staticmethod
    def _tooltip_forfettario_totali(key, total: dict) -> str:
        t = total or {}
        if key == "INPS":
            return (
                "Calcolo contributi INPS complessivi:\n\n"
                "1. Fatturato totale lordo = Fatturato Willow + Reddito esterno\n"
                f"   = {_fmt_eur(t.get('FATTURATO_WILLOW', 0))} + {_fmt_eur(t.get('REDDITO_ESTERNO', 0))}\n"
                "2. Reddito imponibile = Fatturato totale × Coefficiente di redditività\n"
                f"   = {_fmt_eur(t.get('REDDITO_TOT', 0))}\n"
                f"   (tetto al massimale INPS: {_fmt_eur(t.get('MASSIMALE_INPS', 0))})\n"
                "3. Contributi INPS = min(Reddito imponibile, Massimale) × Aliquota INPS\n"
                f"   = {_fmt_eur(t.get('INPS', 0))}"
            )
        if key == "IRPEF":
            return (
                "Calcolo imposta sostitutiva IRPEF:\n\n"
                f"1. Reddito imponibile = {_fmt_eur(t.get('REDDITO_TOT', 0))}\n"
                "2. Base imposta = Reddito imponibile − Contributi INPS (deducibili)\n"
                f"   = {_fmt_eur(t.get('REDDITO_TOT', 0))} − {_fmt_eur(t.get('INPS', 0))} = {_fmt_eur(t.get('BASE_IMPONIBILE_IRPEF', 0))}\n"
                f"3. Aliquota IRPEF applicata: {t.get('ALIQUOTA_IRPEF', 0) * 100:.2f}%\n"
                "4. Imposta = Base imposta × Aliquota IRPEF\n"
                f"   = {_fmt_eur(t.get('IRPEF', 0))}"
            )
        if key == "IRPEF WILLOW":
            return (
                "Quota IRPEF attribuibile a Willow:\n\n"
                f"1. Quota proporzionale Willow = {t.get('QUOTA_WILLOW', 0):.4f}\n"
                "2. IRPEF Willow = IRPEF totale × Quota proporzionale\n"
                f"   = {_fmt_eur(t.get('IRPEF WILLOW', 0))}"
            )
        if key == "INPS WILLOW":
            return (
                "Quota INPS attribuibile a Willow:\n\n"
                f"1. Fatturato Willow = {_fmt_eur(t.get('FATTURATO_WILLOW', 0))}\n"
                f"2. Reddito imponibile Willow = {_fmt_eur(t.get('REDDITO_WILLOW', 0))}\n"
                f"3. Quota proporzionale Willow = {t.get('QUOTA_WILLOW', 0):.4f}\n"
                "4. INPS Willow = INPS totale × Quota proporzionale\n"
                f"   = {_fmt_eur(t.get('INPS WILLOW', 0))}"
            )
        return ""

    @staticmethod
    def _tooltip_forfettario_versamenti(key, total: dict) -> str:
        t = total or {}
        norm = key.replace("\n", " ")
        if norm.startswith("SALDO TOTALE"):
            return (
                "Saldo tasse correnti:\n\n"
                f"1. Tasse totali (INPS + IRPEF) = {_fmt_eur(t.get('TOTALE_TASSE', 0))}\n"
                f"2. Acconto versato per l'anno precedente = {_fmt_eur(t.get('ACCONTO_ANNO_PRECEDENTE', 0))}\n"
                "3. Saldo = Tasse totali − Acconto anno precedente\n"
                f"   = {_fmt_eur(t.get('SALDO_CORRENTE', 0))}"
            )
        if norm.startswith("ACCONTO TOTALE"):
            return (
                "Acconto totale per l'anno successivo:\n\n"
                "1. Acconto IRPEF = IRPEF × (primo + secondo acconto)\n"
                f"   = {_fmt_eur((t.get('PRIMO_ACCONTO_IRPEF', 0) or 0) + (t.get('SECONDO_ACCONTO_IRPEF', 0) or 0))}\n"
                "2. Acconto INPS = INPS × % acconto\n"
                f"   = {_fmt_eur((t.get('PRIMO_ACCONTO_INPS', 0) or 0) + (t.get('SECONDO_ACCONTO_INPS', 0) or 0))}\n"
                "3. Totale acconto = Acconto IRPEF + Acconto INPS\n"
                f"   = {_fmt_eur(t.get('ACCONTO_TOTALE', 0))}"
            )
        if norm.startswith("SALDO WILLOW"):
            return (
                "Quota del saldo corrente attribuita a Willow:\n\n"
                f"1. Saldo totale = {_fmt_eur(t.get('SALDO_CORRENTE', 0))}\n"
                f"2. Quota proporzionale Willow = {t.get('QUOTA_WILLOW', 0):.4f}\n"
                "3. Saldo Willow = Saldo totale × Quota\n"
                f"   = {_fmt_eur(t.get('SALDO_WILLOW', 0))}"
            )
        if norm.startswith("ACCONTO WILLOW"):
            return (
                "Quota dell'acconto attribuita a Willow:\n\n"
                f"1. Acconto totale = {_fmt_eur(t.get('ACCONTO_TOTALE', 0))}\n"
                f"2. Quota proporzionale Willow = {t.get('QUOTA_WILLOW', 0):.4f}\n"
                "3. Acconto Willow = Acconto totale × Quota\n"
                f"   = {_fmt_eur(t.get('ACCONTO_WILLOW', 0))}"
            )
        return ""

    @staticmethod
    def _tooltip_ordinario_totali(key, total: dict) -> str:
        t = total or {}
        if key == "INPS":
            return (
                "Calcolo contributi INPS complessivi:\n\n"
                "1. Ricavi totali = Fatturato Willow + Reddito esterno\n"
                f"   = {_fmt_eur(t.get('RICAVI_TOTALI', 0))}\n"
                "2. Spese totali = Spese Willow + Spese esterne\n"
                f"   = {_fmt_eur(t.get('SPESE_TOTALI', 0))}\n"
                "3. Reddito netto imponibile = Ricavi − Spese\n"
                f"   = {_fmt_eur(t.get('REDDITO_NETTO', 0))}\n"
                f"   (tetto al massimale INPS: {_fmt_eur(t.get('MASSIMALE_INPS', 0))})\n"
                "4. Contributi INPS = min(Reddito netto, Massimale) × Aliquota INPS\n"
                f"   = {_fmt_eur(t.get('INPS', 0))}"
            )
        if key == "IRPEF NETTA":
            return (
                "Calcolo IRPEF netta dovuta:\n\n"
                "1. Base imponibile IRPEF = Reddito netto − INPS\n"
                f"   = {_fmt_eur(t.get('BASE_IRPEF', 0))}\n"
                "2. IRPEF lorda (calcolata a scaglioni)\n"
                f"   = {_fmt_eur(t.get('IRPEF_LORDA', 0))}\n"
                "3. Ritenuta d'acconto già versata\n"
                f"   = {_fmt_eur(t.get('RITENUTA', 0))}\n"
                "4. IRPEF netta = IRPEF lorda − Ritenuta\n"
                f"   = {_fmt_eur(t.get('IRPEF_NETTA', 0))}"
            )
        if key == "WILLOW INPS":
            return (
                "Quota INPS attribuibile a Willow (proporzionale):\n\n"
                f"1. Reddito netto Willow = {_fmt_eur(t.get('REDDITO_NETTO_WILLOW', 0))}\n"
                f"2. Quota = Reddito netto Willow / Reddito netto totale = {t.get('QUOTA_WILLOW_BASE', 0)}\n"
                "3. INPS Willow = INPS totale × Quota\n"
                f"   = {_fmt_eur(t.get('WILLOW_INPS', 0))}"
            )
        if key == "WILLOW IRPEF":
            return (
                "IRPEF netta attribuibile a Willow (proporzionale):\n\n"
                f"1. Quota = Reddito netto Willow / Reddito netto totale = {t.get('QUOTA_WILLOW_BASE', 0)}\n"
                "2. IRPEF lorda Willow = IRPEF lorda totale × Quota\n"
                f"   = {_fmt_eur(t.get('WILLOW_IRPEF_TOT', 0))}\n"
                "3. La ritenuta nasce dalle fatture interne → tutta a Willow\n"
                f"   = {_fmt_eur(t.get('WILLOW_RITENUTA', 0))}\n"
                "4. IRPEF netta Willow = max(0, IRPEF lorda Willow − Ritenuta)\n"
                f"   = {_fmt_eur(t.get('WILLOW_IRPEF_NETTA', 0))}"
            )
        return ""

    @staticmethod
    def _tooltip_ordinario_versamenti(key, total: dict) -> str:
        t = total or {}
        norm = key.replace("\n", " ")
        if norm.startswith("SALDO TOTALE"):
            return (
                "Saldo tasse correnti:\n\n"
                f"1. Tasse totali (INPS + IRPEF netta) = {_fmt_eur(t.get('TOTALE_TASSE', 0))}\n"
                f"2. Acconto anno precedente = {_fmt_eur(t.get('ACCONTO_ANNO_PRECEDENTE', 0))}\n"
                "3. Saldo = Tasse totali − Acconto anno precedente\n"
                f"   = {_fmt_eur(t.get('SALDO_TOTALE', 0))}"
            )
        if norm.startswith("ACCONTO TOTALE"):
            return (
                "Acconto totale per l'anno successivo:\n\n"
                "Acconto INPS + Acconto IRPEF\n"
                f"   = {_fmt_eur(t.get('ACCONTO_TOTALE', 0))}"
            )
        if norm.startswith("SALDO WILLOW"):
            return (
                "Quota del saldo corrente attribuita a Willow:\n\n"
                f"1. Saldo totale = {_fmt_eur(t.get('SALDO_TOTALE', 0))}\n"
                f"2. Proporzione Willow = {t.get('PROP_WILLOW', 0)}\n"
                f"3. Saldo Willow = {_fmt_eur(t.get('SALDO_WILLOW', 0))}"
            )
        if norm.startswith("ACCONTO WILLOW"):
            return (
                "Quota dell'acconto attribuita a Willow:\n\n"
                f"1. Acconto totale = {_fmt_eur(t.get('ACCONTO_TOTALE', 0))}\n"
                f"2. Proporzione Willow = {t.get('PROP_WILLOW', 0)}\n"
                f"3. Acconto Willow = {_fmt_eur(t.get('ACCONTO_WILLOW', 0))}"
            )
        return ""

    # ------------------------------------------------------------------
    # Sezione IVA TRIMESTRALE (solo regime ORDINARIO)
    # ------------------------------------------------------------------

    def _build_iva_section(self):
        section = self._make_section_frame("IVA TRIMESTRALE")

        # Header con 4 colonne.
        header = QFrame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        for col_text in ("TRIMESTRE", "CREDITO", "DEBITO", "DA PAGARE"):
            lbl = QLabel(col_text)
            lbl.setAlignment(Qt.AlignCenter)
            f = lbl.font()
            f.setBold(True)
            lbl.setFont(f)
            lbl.setStyleSheet(
                "background-color: palette(highlight);"
                " color: palette(highlighted-text);"
                " padding: 6px; border-radius: 4px;"
            )
            header_layout.addWidget(lbl, stretch=1)
        section.layout().addWidget(header)

        # Righe trimestrali.
        try:
            iva_data = self.iva_analyzer_service.calculate_trimestral_iva_by_user_id(self.current_user_id) or {}
        except Exception:
            iva_data = {}

        for quarter in ("Gen-Marz", "Apr-Giu", "Lug-Sett", "Ott-Dic"):
            data = iva_data.get(quarter, {"debito": 0.0, "credito": 0.0, "da_pagare": 0.0})
            row = QFrame()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)

            quarter_lbl = QLabel(quarter)
            quarter_lbl.setAlignment(Qt.AlignCenter)
            quarter_lbl.setStyleSheet("padding: 6px; background-color: palette(alternate-base); border-radius: 4px;")
            row_layout.addWidget(quarter_lbl, stretch=1)

            credito_lbl = QLabel(_fmt_eur(data.get("credito", 0)))
            credito_lbl.setAlignment(Qt.AlignCenter)
            credito_lbl.setStyleSheet("padding: 6px; background-color: palette(alternate-base); border-radius: 4px;")
            row_layout.addWidget(credito_lbl, stretch=1)

            debito_lbl = QLabel(_fmt_eur(data.get("debito", 0)))
            debito_lbl.setAlignment(Qt.AlignCenter)
            debito_lbl.setStyleSheet("padding: 6px; background-color: palette(alternate-base); border-radius: 4px;")
            row_layout.addWidget(debito_lbl, stretch=1)

            saldo = data.get("da_pagare", 0) or 0
            if saldo > 0:
                color = "#f52f2f"   # rosso: da pagare
            elif saldo < 0:
                color = "#2ca31c"   # verde: a credito
            else:
                color = "palette(alternate-base)"
            saldo_lbl = QLabel(_fmt_eur(saldo))
            saldo_lbl.setAlignment(Qt.AlignCenter)
            saldo_lbl.setStyleSheet(
                f"padding: 6px; background-color: {color}; color: palette(highlighted-text);"
                " border-radius: 4px;"
            )
            row_layout.addWidget(saldo_lbl, stretch=1)
            section.layout().addWidget(row)

        self.content_layout.addWidget(section)

    # ------------------------------------------------------------------
    # Helper grafici condivisi
    # ------------------------------------------------------------------

    def _make_section_frame(self, title: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("UserSectionFrame")
        frame.setStyleSheet(
            "#UserSectionFrame { border: 2px solid palette(highlight); border-radius: 6px; }"
        )
        v = QVBoxLayout(frame)
        v.setContentsMargins(15, 12, 15, 12)
        v.setSpacing(8)
        title_lbl = QLabel(title)
        f = title_lbl.font()
        f.setBold(True)
        f.setPointSize(12)
        title_lbl.setFont(f)
        v.addWidget(title_lbl)
        return frame

    def _make_subtitle(self, text: str) -> QLabel:
        lbl = QLabel(text)
        f = lbl.font()
        f.setBold(True)
        lbl.setFont(f)
        lbl.setStyleSheet("color: palette(text); margin-top: 6px;")
        return lbl

    @staticmethod
    def _tax_header_color(title: str) -> str:
        return TAX_WILLOW_HEADER_COLOR if "WILLOW" in title.upper() else TAX_DEFAULT_HEADER_COLOR

    def _make_aggregate_card(self, title: str, value: str, header_color: str | None = None) -> QFrame:
        card = QFrame()
        card.setObjectName("UserAggregateCard")
        card.setStyleSheet(
            "#UserAggregateCard { background-color: palette(alternate-base); border-radius: 6px; }"
            "#UserAggregateCard QLabel { color: palette(text); }"
        )
        box = QVBoxLayout(card)
        box.setContentsMargins(10, 6, 10, 6)
        title_lbl = QLabel(title)
        title_lbl.setAlignment(Qt.AlignCenter)
        header_background = header_color or "palette(highlight)"
        title_lbl.setStyleSheet(
            f"background-color: {header_background};"
            " color: palette(highlighted-text);"
            " padding: 3px; border-radius: 3px;"
        )
        value_lbl = QLabel(value)
        value_lbl.setAlignment(Qt.AlignCenter)
        vf = value_lbl.font()
        vf.setPointSize(11)
        value_lbl.setFont(vf)
        box.addWidget(title_lbl)
        box.addWidget(value_lbl)
        return card

    def _add_field(self, section_name, key, label_text, widget):
        grid = self._section_grids[section_name]
        row = self._section_rows[section_name]
        label = QLabel(label_text + ":")
        grid.addWidget(label, row, 0, alignment=Qt.AlignLeft)
        grid.addWidget(widget, row, 1)
        self._widgets[key] = widget
        self._labels[key] = label
        self._section_rows[section_name] = row + 1

    def _make_line_edit(self, value):
        edit = QLineEdit()
        edit.setText(str(value) if value is not None else "")
        return edit

    # ------------------------------------------------------------------
    # Caricamento utente
    # ------------------------------------------------------------------

    def load_user(self, user_id):
        self.current_user_id = user_id
        self._clear_content()

        user = self.user_query_service.retrieve_user_map_by_id(user_id)
        if not user:
            self.title_label.setText("Utente non trovato")
            return

        account = self.accounts_query_service.retrieve_account_map_by_id(
            user.get(DBUsersColumns.CONTO_CORRENTE_ID.value)
        )
        user[self.ACCOUNT_FIELD] = account[DBAccountsColumns.NAME.value] if account else ""

        self.user = user
        full_name = f"{user.get(DBUsersColumns.FIRST_NAME.value, '')} {user.get(DBUsersColumns.LAST_NAME.value, '')}".strip()
        self.title_label.setText(full_name or "Utente")

        regime_value = str(user.get(DBUsersColumns.REGIME_FISCALE.value, "") or "")

        # 1) Info section (anagrafica/fiscale/foto/status).
        self._build_info_section(user)

        # 2) Storico in riga: fatture / spese anticipate / salari / (deduzione).
        self._build_history_sections(regime_value)

        # 3) Dati fiscali.
        self._build_fiscal_data_section()

        # 4) Previsione tasse.
        self._build_taxes_section(regime_value)

        # 5) IVA trimestrale (solo ORDINARIO).
        if regime_value == RegimeFiscale.ORDINARIO.value:
            self._build_iva_section()

        # Spinge il contenuto verso l'alto.
        self.content_layout.addStretch(1)

        # Applica stato iniziale di edit/sensible-data.
        self._on_modify_toggled(self.modify_switch.isChecked())

    def _clear_content(self):
        if hasattr(self, "action_bar"):
            self.action_bar.setParent(None)
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._widgets.clear()
        self._labels.clear()
        self._eye_buttons.clear()
        self._section_grids.clear()
        self._section_rows.clear()
        self.modify_switch.blockSignals(True)
        self.modify_switch.setChecked(False)
        self.modify_switch.blockSignals(False)

    # ------------------------------------------------------------------
    # Toggle edit + dati sensibili (login-dependent)
    # ------------------------------------------------------------------

    def _on_modify_toggled(self, enabled: bool):
        if not hasattr(self, "save_btn"):
            return
        self.save_btn.setEnabled(enabled)
        # Eliminazione utente: azione amministrativa, abilitata solo per admin.
        can_delete = enabled and self._is_admin
        self.delete_btn.setEnabled(can_delete)
        if not self._is_admin:
            self.delete_btn.setToolTip(
                "Solo l'amministratore puo' eliminare un utente."
            )
        else:
            self.delete_btn.setToolTip("")

        readonly_keys = {
            DBUsersColumns.CREATED_AT.value,
            DBUsersColumns.UPDATED_AT.value,
        }
        for key, widget in self._widgets.items():
            if key in readonly_keys:
                continue
            widget.setEnabled(enabled)

        self._apply_sensitive_visibility_policy(enabled)

    def _apply_sensitive_visibility_policy(self, modify_enabled: bool):
        """Replica della legacy ``toggle_sensible_data`` con eccezione admin:
        - se l'utente loggato sta vedendo il proprio profilo, i campi
          sensibili seguono lo stato dello switch;
        - se chi sta guardando e' l'admin, puo' modificare SOLO il campo
          ``PASSWORD_LOGIN`` (force-reset password); gli altri sensibili
          (provider creds, dati finanziari) restano disabilitati: senza
          la chiave AES dell'utente non avrebbero senso comunque;
        - altrimenti i campi sensibili restano sempre disabled e
          mascherati con asterischi (anche se lo switch e' on).
        """
        is_own_profile = (
            self._login_status
            and self._logged_user_id == self.current_user_id
        )
        for key in SENSITIVE_FIELDS:
            wrapper = self._widgets.get(key)
            if wrapper is None:
                continue
            entry = getattr(wrapper, "entry", None) or wrapper
            if not isinstance(entry, QLineEdit):
                continue
            eye_btn = getattr(wrapper, "eye_button", None)
            if is_own_profile:
                entry.setEnabled(modify_enabled)
            elif self._is_admin and key == DBUsersColumns.PASSWORD_LOGIN.value:
                # Admin: solo force-reset password.
                entry.setEnabled(modify_enabled)
            else:
                entry.setEnabled(False)
                entry.setEchoMode(QLineEdit.Password)
                # Sincronizza il bottone occhio col reset dell'echo,
                # altrimenti resta visivamente "rivelato" (icona lucchetto)
                # mentre il campo e' mascherato.
                if eye_btn is not None:
                    eye_btn.setChecked(False)
                    eye_btn.setText("👁")

        # Bottoni occhio: utili solo se l'utente sta digitando un valore
        # nei campi sensibili (proprio profilo) — admin force-reset non
        # ha bisogno di rivelare il valore digitato.
        for btn in self._eye_buttons:
            btn.setEnabled(is_own_profile and modify_enabled)

    def _on_login_changed(self, data):
        """Handler dell'evento ``LOGIN_STATUS_CHANGED`` (event bus).

        Re-valuta tutta la UI dipendente dallo stato di login: campi
        sensibili (oscurati se non sei sul tuo profilo), bottone elimina
        (admin-only), tooltip. Chiama ``_on_modify_toggled`` che internamente
        invoca ``_apply_sensitive_visibility_policy`` — un unico punto
        di sincronizzazione.
        """
        if isinstance(data, dict):
            self._login_status = bool(data.get("login_status", False))
            self._logged_user_id = data.get("logged_user_id", -1)
            self._is_admin = bool(data.get("is_admin", False))
        if hasattr(self, "modify_switch"):
            self._on_modify_toggled(self.modify_switch.isChecked())

    # ------------------------------------------------------------------
    # Salvataggio / eliminazione
    # ------------------------------------------------------------------

    def _entry_value(self, key: str) -> str:
        widget = self._widgets.get(key)
        if widget is None:
            return ""
        entry = getattr(widget, "entry", None) or widget
        if isinstance(entry, QLineEdit):
            return entry.text().strip()
        if isinstance(entry, QComboBox):
            return entry.currentText().strip()
        return ""

    def _save_user_mod(self):
        if self.user is None:
            return

        account_name = self._entry_value(self.ACCOUNT_FIELD)
        account = self.accounts_query_service.retrieve_account_map_by_name(account_name)
        if not account:
            QMessageBox.critical(self, "ERRORE", "Conto corrente non valido.")
            return

        current = self.user_query_service.retrieve_user_map_by_id(self.current_user_id) or {}

        user_data = {
            DBUsersColumns.FIRST_NAME.value: self._entry_value(DBUsersColumns.FIRST_NAME.value),
            DBUsersColumns.LAST_NAME.value: self._entry_value(DBUsersColumns.LAST_NAME.value),
            DBUsersColumns.PARTITA_IVA.value: self._entry_value(DBUsersColumns.PARTITA_IVA.value),
            DBUsersColumns.CODICE_FISCALE.value: self._entry_value(DBUsersColumns.CODICE_FISCALE.value),
            DBUsersColumns.TELEFONO.value: self._entry_value(DBUsersColumns.TELEFONO.value),
            DBUsersColumns.EMAIL.value: self._entry_value(DBUsersColumns.EMAIL.value),
            DBUsersColumns.REGIME_FISCALE.value: self._entry_value(DBUsersColumns.REGIME_FISCALE.value),
            DBUsersColumns.ANNO_APERTURA_PIVA.value: self._entry_value(DBUsersColumns.ANNO_APERTURA_PIVA.value),
            DBUsersColumns.CONTO_CORRENTE_ID.value: account[DBAccountsColumns.ID.value],
            DBUsersColumns.PHOTO_PATH.value: self._photo_path or "",
            DBUsersColumns.STATUS.value: self._entry_value(DBUsersColumns.STATUS.value) or UserStatus.ATTIVO.value,
            DBUsersColumns.REDDITO_ESTERNO.value: self._entry_value(DBUsersColumns.REDDITO_ESTERNO.value) or "0",
            DBUsersColumns.LAST_YEAR_IRPEF_ACCONTO.value: self._entry_value(DBUsersColumns.LAST_YEAR_IRPEF_ACCONTO.value) or "0",
            DBUsersColumns.LAST_YEAR_INPS_ACCONTO.value: self._entry_value(DBUsersColumns.LAST_YEAR_INPS_ACCONTO.value) or "0",
            # Provider FE: preservato dal DB (non gestito a livello UI).
            DBUsersColumns.PROVIDER_FATTURE.value: current.get(DBUsersColumns.PROVIDER_FATTURE.value, ""),
            DBUsersColumns.USERNAME_PROVIDER.value: current.get(DBUsersColumns.USERNAME_PROVIDER.value, ""),
            DBUsersColumns.PASSWORD_PROVIDER.value: current.get(DBUsersColumns.PASSWORD_PROVIDER.value, ""),
        }

        # SPESE_DEDOTTE_ESTERNE: presente solo per ORDINARIO; per
        # FORFETTARIO settiamo 0 di default come fa la legacy.
        if user_data[DBUsersColumns.REGIME_FISCALE.value] == RegimeFiscale.ORDINARIO.value:
            user_data[DBUsersColumns.SPESE_DEDOTTE_ESTERNE.value] = (
                self._entry_value(DBUsersColumns.SPESE_DEDOTTE_ESTERNE.value) or "0"
            )
        else:
            user_data[DBUsersColumns.SPESE_DEDOTTE_ESTERNE.value] = 0

        # PASSWORD_LOGIN: inviata solo se l'utente ne ha digitata una
        # nuova (il controller la hashera').
        new_password = self._entry_value(DBUsersColumns.PASSWORD_LOGIN.value)
        if new_password:
            user_data[DBUsersColumns.PASSWORD_LOGIN.value] = new_password

        # Validazione locale minimale.
        if not user_data[DBUsersColumns.FIRST_NAME.value]:
            QMessageBox.critical(self, "ERRORE", "Il nome non può essere vuoto.")
            return
        if not user_data[DBUsersColumns.LAST_NAME.value]:
            QMessageBox.critical(self, "ERRORE", "Il cognome non può essere vuoto.")
            return
        if not ValidationUtils.validate_partita_iva(user_data[DBUsersColumns.PARTITA_IVA.value]):
            QMessageBox.critical(self, "ERRORE", "La partita IVA deve essere un numero di 11 cifre.")
            return
        email_val = user_data[DBUsersColumns.EMAIL.value]
        if email_val and not ValidationUtils.validate_email(email_val):
            QMessageBox.critical(self, "ERRORE", "Inserisci una e-mail valida.")
            return
        money_re = re.compile(r"^\d+(\.\d{1,2})?$")
        for money_key in (
            DBUsersColumns.REDDITO_ESTERNO.value,
            DBUsersColumns.LAST_YEAR_IRPEF_ACCONTO.value,
            DBUsersColumns.LAST_YEAR_INPS_ACCONTO.value,
        ):
            v = str(user_data.get(money_key, "0") or "0")
            if not money_re.fullmatch(v):
                QMessageBox.critical(
                    self,
                    "ERRORE",
                    "Importo non valido: usa una cifra monetaria con due decimali (es. 123.45).",
                )
                return

        success, message, info = self.user_controller.update_user(self.current_user_id, user_data)
        if not success:
            QMessageBox.critical(self, "ERRORE", message)
            return

        QMessageBox.information(self, "SALVATAGGIO COMPLETATO", message)

        # Se in questa save e' stata impostata o cambiata la password,
        # il controller ha generato un nuovo recovery code: mostralo ora
        # (l'utente lo trascrive offline).
        recovery_code = (info or {}).get("recovery_code")
        if recovery_code:
            from QTViews.LoginViews.QT_recovery_code_show_dialog import QTRecoveryCodeShowDialog
            QTRecoveryCodeShowDialog(recovery_code, parent=self).exec()

        self.modify_switch.setChecked(False)
        self.load_user(self.current_user_id)

    def _delete_user(self):
        confirm = QMessageBox.question(
            self,
            "ELIMINAZIONE UTENTE",
            "Stai per eliminare questo utente.\nDesideri continuare?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        success, message = self.user_controller.delete_user_by_ID(self.current_user_id)
        if not success:
            QMessageBox.critical(self, "ERRORE", message)
            return

        QMessageBox.information(self, "UTENTE ELIMINATO", message)
        self._cleanup_and_go_back()

    # ------------------------------------------------------------------
    # Navigation: detail di item collegati (event bus)
    # ------------------------------------------------------------------

    def _show_invoice_detail(self, invoice_id):
        self.event_bus.publish(ViewUtils.EventBusKeys.SHOW_INVOICE_DETAIL.value, invoice_id)

    def _show_expense_detail(self, expense_id):
        self.event_bus.publish(ViewUtils.EventBusKeys.SHOW_EXPENSE_DETAIL.value, expense_id)

    def _show_salary_detail(self, salary_id):
        self.event_bus.publish(ViewUtils.EventBusKeys.SHOW_SALARY_DETAIL.value, salary_id)

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _cleanup_and_go_back(self):
        try:
            self.event_bus.unsubscribe(
                ViewUtils.EventBusKeys.LOGIN_STATUS_CHANGED.value,
                self._on_login_changed,
            )
        except Exception:
            pass
        if self.on_back is not None:
            self.on_back()

    def _set_combo_text(self, combo: QComboBox, value):
        if value is None:
            return
        text = str(value)
        idx = combo.findText(text)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        elif combo.isEditable():
            combo.setEditText(text)

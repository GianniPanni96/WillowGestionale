import re
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from App_context import AppContext


_IRPEF_DESCRIPTIONS = {
    1: "Aliquota IRPEF per il primo scaglione di reddito",
    2: "Aliquota IRPEF per il secondo scaglione di reddito",
    3: "Aliquota IRPEF per il terzo scaglione di reddito",
    4: "Aliquota IRPEF per il quarto scaglione di reddito",
    5: "Aliquota IRPEF per il quinto scaglione di reddito",
    6: "Aliquota IRPEF per il sesto scaglione di reddito",
}


class QTFiscalSettingsDialog(QDialog):
    """
    Finestra "Modifica dati fiscali".

    Equivalente di MainWindow.open_fiscal_settings_window legacy.
    Tre tab: FORFETTARIA, ORDINARIA, IVA. Per la sezione ordinaria gli
    scaglioni IRPEF sono dinamici (add/remove) come nella legacy.
    """

    IVA_KEYS = [
        "no_iva",
        "aliquota_iva_ordinaria",
        "aliquota_iva_ridotta_1",
        "aliquota_iva_ridotta_2",
        "aliquota_iva_minima",
    ]

    FORF_ALIQUOTE_KEYS = [
        "aliquota_irpef_min",
        "aliquota_irpef_max",
        "anni_agevolazione",
        "aliquota_inps",
        "massimale_inps",
        "aliquota_rivalsa_inps",
    ]

    FORF_RATEIZZ_KEYS = [
        "percentuale_acconto_imposta_primo",
        "percentuale_acconto_imposta_secondo",
        "percentuale_acconto_inps_forfettario",
        "percentuale_rata_acconto_inps_forfettario",
    ]

    ORD_FIXED_KEYS = ["aliquota_inps", "massimale_inps", "aliquota_cassa_inps", "aliquota_ritenuta"]
    ORD_IMPONIBILI_KEYS = [
        "imponibile_iva",
        "imponibile_ritenuta_acconto",
        "imponibile_cassa_inps",
        "imponibile_inps",
        "imponibile_irpef",
    ]
    ORD_RATEIZZ_KEYS = [
        "percentuale_acconto_irpef_primo",
        "percentuale_acconto_irpef_secondo",
        "percentuale_acconto_inps",
        "percentuale_rata_acconto_inps",
    ]

    MAX_SCAGLIONI = 6

    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.config_manager = app_context.config_manager

        self.setWindowTitle("Dati Fiscali")
        self.resize(900, 950)
        self.setModal(True)

        self.iva_entries: dict = {}
        self.forfettaria_entries: dict = {}
        self.forfettaria_rateizzazione_entries: dict = {}
        self.ordinaria_entries: dict = {}
        self.ordinaria_imponibili_entries: dict = {}
        self.ordinaria_rateizzazione_entries: dict = {}
        self.ordinaria_irpef_entries: dict = {}
        self.scaglioni_containers: dict = {}

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(15, 15, 15, 15)
        root.setSpacing(12)

        title = QLabel("Modifica i dati fiscali in base alla legge vigente")
        title_font = title.font()
        title_font.setPointSize(16)
        title.setFont(title_font)
        root.addWidget(title)

        config = self.config_manager.load_config()
        fiscal = config.get("fiscal_settings", {})

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_forfettaria_tab(fiscal.get("partita_iva_forfettaria", {})), "FORFETTARIA")
        self.tabs.addTab(self._build_ordinaria_tab(fiscal.get("partita_iva_ordinaria", {})), "ORDINARIA")
        self.tabs.addTab(self._build_iva_tab(fiscal.get("iva", {})), "IVA")
        root.addWidget(self.tabs, stretch=1)

        save_btn = QPushButton("Salva Dati Fiscali")
        save_btn.clicked.connect(self._save_fiscal_settings)
        root.addWidget(save_btn)

    @staticmethod
    def _wrap_in_scroll(widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        return scroll

    @staticmethod
    def _add_label_entry(layout: QVBoxLayout, description, value):
        lbl = QLabel(description)
        f = lbl.font()
        f.setPointSize(11)
        lbl.setFont(f)
        layout.addWidget(lbl)

        try:
            val_str = f"{float(value):.2f}" if value is not None else ""
        except (TypeError, ValueError):
            val_str = str(value if value is not None else "")

        ent = QLineEdit(val_str)
        layout.addWidget(ent)
        return ent

    @staticmethod
    def _add_description(layout: QVBoxLayout, text):
        if not text:
            return
        lbl = QLabel(text)
        lbl.setStyleSheet("color: palette(mid); font-style: italic;")
        layout.addWidget(lbl)

    # ----- IVA -----
    def _build_iva_tab(self, iva_data) -> QScrollArea:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(35)

        group = QGroupBox("Aliquote IVA")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(8)

        for key in self.IVA_KEYS:
            data = iva_data.get(key, {}) if isinstance(iva_data.get(key), dict) else {}
            value = data.get("value", "")
            description = data.get("description", key.replace("_", " ").capitalize())
            ent = self._add_label_entry(group_layout, key.replace("_", " ").capitalize(), value)
            self._add_description(group_layout, description)
            self.iva_entries[key] = ent

        layout.addWidget(group)
        layout.addStretch(1)
        return self._wrap_in_scroll(container)

    # ----- FORFETTARIA -----
    def _build_forfettaria_tab(self, forf_data) -> QScrollArea:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(35)

        # Aliquote & Parametri.
        aliquote_group = QGroupBox("Aliquote & Parametri")
        aliquote_layout = QVBoxLayout(aliquote_group)
        aliquote_layout.setSpacing(10)
        for key in self.FORF_ALIQUOTE_KEYS:
            data = forf_data.get(key, {}) if isinstance(forf_data.get(key), dict) else {}
            value = data.get("value", "")
            description = data.get("description", key)
            ent = self._add_label_entry(aliquote_layout, description, value)
            self.forfettaria_entries[key] = ent
        layout.addWidget(aliquote_group)

        # Imponibile.
        imp_group = QGroupBox("Imponibile")
        imp_layout = QVBoxLayout(imp_group)
        data = forf_data.get("imponibile", {}) if isinstance(forf_data.get("imponibile"), dict) else {}
        value = data.get("value", "")
        description = data.get("description", "Imponibile")
        ent = self._add_label_entry(imp_layout, description, value)
        self.forfettaria_entries["imponibile"] = ent
        layout.addWidget(imp_group)

        # Rateizzazione.
        rate_group = QGroupBox("Rateizzazione Tasse")
        rate_layout = QVBoxLayout(rate_group)
        for key in self.FORF_RATEIZZ_KEYS:
            if key not in forf_data:
                continue
            data = forf_data.get(key, {}) if isinstance(forf_data.get(key), dict) else {}
            value = data.get("value", "")
            description = data.get("description", key)
            ent = self._add_label_entry(rate_layout, description, value)
            self.forfettaria_rateizzazione_entries[key] = ent
        layout.addWidget(rate_group)

        layout.addStretch(1)
        return self._wrap_in_scroll(container)

    # ----- ORDINARIA -----
    def _build_ordinaria_tab(self, ord_data) -> QScrollArea:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(35)

        # Aliquote (con scaglioni IRPEF dinamici).
        aliquote_group = QGroupBox("Aliquote")
        aliquote_layout = QVBoxLayout(aliquote_group)

        self.scaglioni_holder = QFrame()
        self.scaglioni_layout = QVBoxLayout(self.scaglioni_holder)
        self.scaglioni_layout.setContentsMargins(0, 0, 0, 0)
        self.scaglioni_layout.setSpacing(10)
        aliquote_layout.addWidget(self.scaglioni_holder)

        # Carica gli scaglioni esistenti.
        pattern = re.compile(r"^aliquota_irpef_(\d+)$")
        existing = []
        for key in ord_data.keys():
            match = pattern.match(key)
            if match:
                existing.append((int(match.group(1)), key))
        existing.sort(key=lambda x: x[0])
        for _, key in existing:
            data = ord_data.get(key, {}) if isinstance(ord_data.get(key), dict) else {}
            self._append_scaglione(
                key,
                data.get("description", key),
                data.get("value", ""),
                data.get("reddito_min", ""),
                data.get("reddito_max", ""),
            )
        self._refresh_delete_buttons()

        # Bottone aggiungi.
        self.add_scaglione_btn = QPushButton("Aggiungi Scaglione")
        self.add_scaglione_btn.clicked.connect(self._add_scaglione_irpef)
        aliquote_layout.addWidget(self.add_scaglione_btn)
        self._refresh_add_button()

        # Aliquote fisse.
        for key in self.ORD_FIXED_KEYS:
            if key not in ord_data:
                continue
            data = ord_data.get(key, {}) if isinstance(ord_data.get(key), dict) else {}
            value = data.get("value", "")
            description = data.get("description", key)
            ent = self._add_label_entry(aliquote_layout, description, value)
            self.ordinaria_entries[key] = ent
        layout.addWidget(aliquote_group)

        # Imponibili.
        imp_group = QGroupBox("Imponibili")
        imp_layout = QVBoxLayout(imp_group)
        for key in self.ORD_IMPONIBILI_KEYS:
            if key not in ord_data:
                continue
            data = ord_data.get(key, {}) if isinstance(ord_data.get(key), dict) else {}
            value = data.get("value", "")
            description = data.get("description", key)
            ent = self._add_label_entry(imp_layout, description, value)
            self.ordinaria_imponibili_entries[key] = ent
        layout.addWidget(imp_group)

        # Rateizzazione.
        rate_group = QGroupBox("Rateizzazione Tasse")
        rate_layout = QVBoxLayout(rate_group)
        for key in self.ORD_RATEIZZ_KEYS:
            if key not in ord_data:
                continue
            data = ord_data.get(key, {}) if isinstance(ord_data.get(key), dict) else {}
            value = data.get("value", "")
            description = data.get("description", key)
            ent = self._add_label_entry(rate_layout, description, value)
            self.ordinaria_rateizzazione_entries[key] = ent
        layout.addWidget(rate_group)

        layout.addStretch(1)
        return self._wrap_in_scroll(container)

    # ------------------------------------------------------------------
    # Scaglioni IRPEF dinamici
    # ------------------------------------------------------------------

    def _append_scaglione(self, key, description, value, reddito_min, reddito_max):
        container = QFrame()
        container.setFrameShape(QFrame.StyledPanel)
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(8, 6, 8, 6)
        c_layout.setSpacing(6)

        title_row = QHBoxLayout()
        lbl = QLabel(description)
        title_row.addWidget(lbl, stretch=1)
        delete_btn = QPushButton("Cancella")
        delete_btn.clicked.connect(lambda _, k=key: self._delete_scaglione_irpef(k))
        title_row.addWidget(delete_btn)
        c_layout.addLayout(title_row)

        entries_row = QHBoxLayout()
        entries_row.setSpacing(8)

        value_col = QVBoxLayout()
        value_col.addWidget(QLabel("Valore:"))
        val_str = f"{float(value):.2f}" if value is not None else ""
        value_ent = QLineEdit(val_str)
        value_col.addWidget(value_ent)
        entries_row.addLayout(value_col)

        min_col = QVBoxLayout()
        min_col.addWidget(QLabel("Reddito Minimo:"))
        min_val = f"{float(reddito_min):.2f}" if reddito_min is not None else ""
        min_ent = QLineEdit(min_val)
        min_col.addWidget(min_ent)
        entries_row.addLayout(min_col)

        max_col = QVBoxLayout()
        max_col.addWidget(QLabel("Reddito Massimo:"))
        max_val = f"{float(reddito_max):.2f}" if reddito_max is not None else ""
        max_ent = QLineEdit(max_val)
        max_col.addWidget(max_ent)
        entries_row.addLayout(max_col)

        c_layout.addLayout(entries_row)

        self.scaglioni_layout.addWidget(container)
        self.scaglioni_containers[key] = {
            "frame": container,
            "delete_button": delete_btn,
        }
        self.ordinaria_irpef_entries[key] = {
            "value": value_ent,
            "reddito_min": min_ent,
            "reddito_max": max_ent,
            "description": description,
        }

    def _add_scaglione_irpef(self):
        n = len(self.scaglioni_containers)
        if n >= self.MAX_SCAGLIONI:
            QMessageBox.warning(self, "ERRORE", "Raggiunto numero massimo di scaglioni inseribili")
            self.add_scaglione_btn.setEnabled(False)
            return
        idx = n + 1
        key = f"aliquota_irpef_{idx}"
        description = _IRPEF_DESCRIPTIONS.get(idx, key)
        self._append_scaglione(key, description, 0, 0, 0)
        self._refresh_delete_buttons()
        self._refresh_add_button()

    def _delete_scaglione_irpef(self, key):
        info = self.scaglioni_containers.pop(key, None)
        if info is None:
            return
        info["frame"].setParent(None)
        info["frame"].deleteLater()
        self.ordinaria_irpef_entries.pop(key, None)
        self._refresh_delete_buttons()
        self._refresh_add_button()

    def _refresh_delete_buttons(self):
        # Solo l'ultimo scaglione mostra il bottone "Cancella" (come nella legacy).
        keys = list(self.scaglioni_containers.keys())
        for i, key in enumerate(keys):
            info = self.scaglioni_containers[key]
            info["delete_button"].setVisible(i == len(keys) - 1)

    def _refresh_add_button(self):
        n = len(self.scaglioni_containers)
        self.add_scaglione_btn.setEnabled(n < self.MAX_SCAGLIONI)

    # ------------------------------------------------------------------
    # Salvataggio
    # ------------------------------------------------------------------

    def _save_fiscal_settings(self):
        fiscal_data = {}

        iva_data = {}
        for key in ["aliquota_iva_ordinaria", "aliquota_iva_ridotta_1",
                    "aliquota_iva_ridotta_2", "aliquota_iva_minima"]:
            if key in self.iva_entries:
                iva_data[key] = {"value": self.iva_entries[key].text()}
            else:
                iva_data[key] = {"value": ""}
        fiscal_data["iva"] = iva_data

        forf_data = {}
        for key in self.FORF_ALIQUOTE_KEYS + ["imponibile"]:
            if key in self.forfettaria_entries:
                forf_data[key] = {"value": self.forfettaria_entries[key].text()}
            else:
                forf_data[key] = {"value": ""}
        for key in self.FORF_RATEIZZ_KEYS:
            if key in self.forfettaria_rateizzazione_entries:
                forf_data[key] = {"value": self.forfettaria_rateizzazione_entries[key].text()}
        fiscal_data["partita_iva_forfettaria"] = forf_data

        ord_data = {}
        for key, widgets in self.ordinaria_irpef_entries.items():
            ord_data[key] = {
                "value": widgets["value"].text(),
                "reddito_min": widgets["reddito_min"].text(),
                "reddito_max": widgets["reddito_max"].text(),
                "description": widgets.get("description", ""),
            }
        for key, widget in self.ordinaria_entries.items():
            ord_data[key] = {"value": widget.text()}
        for key, widget in self.ordinaria_imponibili_entries.items():
            ord_data[key] = {"value": widget.text()}
        for key, widget in self.ordinaria_rateizzazione_entries.items():
            ord_data[key] = {"value": widget.text()}
        fiscal_data["partita_iva_ordinaria"] = ord_data

        try:
            self.config_manager.update_fiscal_settings(fiscal_data)
        except Exception as exc:
            QMessageBox.critical(self, "ERRORE", f"Impossibile aggiornare i dati fiscali: {exc}")
            return

        QMessageBox.information(self, "INFO", "Dati fiscali aggiornati con successo")
        self.accept()

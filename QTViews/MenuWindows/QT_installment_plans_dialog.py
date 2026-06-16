from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ConfigManagers.config_models import InstallmentPlan

if TYPE_CHECKING:
    from App_context import AppContext


# Default usati per il prefill se il piano non e' ancora presente nel JSON.
_DEFAULT_PLANS = {
    2: {"day_offsets": [60, 90], "amount_split": [50, 50]},
    3: {"day_offsets": [30, 60, 90], "amount_split": [34, 33, 33]},
}


class QTInstallmentPlansDialog(QDialog):
    """
    Finestra unica per configurare scadenze e rateizzazione delle fatture.

    - Rata singola: giorni di scadenza (limite di legge 30gg, estendibile per
      accordi col cliente);
    - Per ogni numero di rate (2 e 3): giorni di scadenza di ciascuna rata
      (offset dalla data di emissione) e ripartizione percentuale del netto.

    I valori multi-rata sono indipendenti dalla preferenza della rata singola.
    Tutto viene salvato in fiscal_rules.json.
    """

    PLANS = (2, 3)

    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.config_manager = app_context.config_manager

        self.setWindowTitle("Scadenze e rateizzazione")
        self.setModal(True)
        self.setMinimumWidth(560)

        # {num_rate: {"days": [QSpinBox], "split": [QDoubleSpinBox]}}
        self.plan_widgets: dict = {}

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Configurazione scadenze e rateizzazione")
        f = title.font()
        f.setPointSize(14)
        f.setBold(True)
        title.setFont(f)
        layout.addWidget(title)

        # --- Rata singola ---
        layout.addWidget(self._build_single_rate_group())

        info = QLabel(
            "Per le fatture rateizzate imposta, per ogni rata, i giorni di "
            "scadenza (dalla data di emissione) e la quota percentuale del netto "
            "a pagare. Le percentuali di ciascun piano dovrebbero sommare a 100%."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: palette(mid); font-style: italic;")
        layout.addWidget(info)

        current_plans = self.config_manager.get_installment_plans() or {}

        for num_rate in self.PLANS:
            stored = current_plans.get(str(num_rate), {}) or {}
            day_offsets = stored.get("day_offsets") or _DEFAULT_PLANS[num_rate]["day_offsets"]
            amount_split = stored.get("amount_split") or _DEFAULT_PLANS[num_rate]["amount_split"]
            # Normalizza la lunghezza al numero di rate.
            if len(day_offsets) != num_rate:
                day_offsets = _DEFAULT_PLANS[num_rate]["day_offsets"]
            if len(amount_split) != num_rate:
                amount_split = _DEFAULT_PLANS[num_rate]["amount_split"]

            layout.addWidget(self._build_plan_group(num_rate, day_offsets, amount_split))

        save_btn = QPushButton("Salva")
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

    def _build_single_rate_group(self) -> QGroupBox:
        group = QGroupBox("Pagamento in rata unica")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(8)

        info = QLabel(
            "Per legge (D.Lgs. 231/2002) il termine standard di pagamento è di "
            "<b>30 giorni</b> dalla data di emissione. È estendibile se esistono "
            "accordi differenti con il cliente. Questo valore è il default proposto "
            "alla creazione della fattura a rata singola (modificabile al volo)."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: palette(mid); font-style: italic;")
        group_layout.addWidget(info)

        row = QHBoxLayout()
        row.addWidget(QLabel("Giorni di scadenza:"))
        self.expiry_days_spin = QSpinBox()
        self.expiry_days_spin.setMinimum(1)
        self.expiry_days_spin.setMaximum(365)
        self.expiry_days_spin.setValue(int(self.config_manager.get_invoice_expiry_days()))
        row.addWidget(self.expiry_days_spin)
        row.addStretch(1)
        group_layout.addLayout(row)

        return group

    def _build_plan_group(self, num_rate, day_offsets, amount_split) -> QGroupBox:
        group = QGroupBox(f"Pagamento in {num_rate} rate")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(8)

        days_widgets = []
        split_widgets = []

        for i in range(num_rate):
            row = QHBoxLayout()
            row.addWidget(QLabel(f"Rata {i + 1}:"))

            row.addWidget(QLabel("giorni"))
            day_spin = QSpinBox()
            day_spin.setMinimum(1)
            day_spin.setMaximum(365)
            day_spin.setValue(int(day_offsets[i]))
            row.addWidget(day_spin)
            days_widgets.append(day_spin)

            row.addWidget(QLabel("quota %"))
            split_spin = QDoubleSpinBox()
            split_spin.setMinimum(0.0)
            split_spin.setMaximum(100.0)
            split_spin.setDecimals(2)
            split_spin.setValue(float(amount_split[i]))
            row.addWidget(split_spin)
            split_widgets.append(split_spin)

            row.addStretch(1)
            group_layout.addLayout(row)

        self.plan_widgets[num_rate] = {"days": days_widgets, "split": split_widgets}
        return group

    def _save(self):
        new_plans = {}
        for num_rate in self.PLANS:
            widgets = self.plan_widgets[num_rate]
            day_offsets = [w.value() for w in widgets["days"]]
            amount_split = [w.value() for w in widgets["split"]]

            total_split = sum(amount_split)
            if total_split <= 0:
                QMessageBox.critical(
                    self,
                    "ERRORE",
                    f"Le quote del piano a {num_rate} rate non sono valide "
                    "(la somma deve essere maggiore di zero).",
                )
                return
            if abs(total_split - 100.0) > 0.01:
                confirm = QMessageBox.question(
                    self,
                    "Quote non a 100%",
                    f"Le quote del piano a {num_rate} rate sommano a "
                    f"{round(total_split, 2)}% invece di 100%.\n"
                    "Verranno riscalate proporzionalmente. Continuare?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if confirm != QMessageBox.Yes:
                    return

            new_plans[str(num_rate)] = {
                "day_offsets": day_offsets,
                "amount_split": amount_split,
            }

        expiry_days = self.expiry_days_spin.value()

        try:
            self.config_manager.update_invoice_expiry_days(expiry_days)
            self.config_manager.update_installment_plans(new_plans)
        except Exception as exc:
            QMessageBox.critical(self, "ERRORE", f"Impossibile salvare le impostazioni: {exc}")
            return

        # Aggiorna l'oggetto fiscal_settings in memoria (condiviso per
        # riferimento dai servizi) per effetto immediato senza riavvio.
        fiscal_settings = getattr(self.app_context, "fiscal_settings", None)
        if fiscal_settings is not None:
            fiscal_settings.invoice_expiry_days = expiry_days
            for num_rate in self.PLANS:
                fiscal_settings.installment_plans[num_rate] = InstallmentPlan.from_dict(
                    num_rate, new_plans[str(num_rate)]
                )

        QMessageBox.information(self, "INFO", "Scadenze e rateizzazione aggiornate con successo.")
        self.accept()

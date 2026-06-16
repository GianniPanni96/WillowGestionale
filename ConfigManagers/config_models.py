import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from Gestionale_Enums import RecurringExpensesStatus
from ConfigManagers.historical_financial_data_manager import normalize_historical_file_data
from ConfigManagers.type_utils import coerce_to_float, coerce_to_int


def _coerce_config_float(value, default: float = 0.0) -> float:
    return coerce_to_float(value, default)


def _coerce_config_int(value, default: int = 0) -> int:
    return coerce_to_int(value, default)


@dataclass
class PartitaIVAForfettaria:
    aliquota_irpef_min: float
    aliquota_irpef_max: float
    anni_agevolazione: int
    aliquota_inps: float
    massimale_inps: float
    imponibile: float
    aliquota_rivalsa_inps: float
    percentuale_acconto_imposta_primo: float
    percentuale_acconto_imposta_secondo: float
    percentuale_acconto_inps_forfettario: float
    percentuale_rata_acconto_inps_forfettario: float

    @staticmethod
    def from_dict(data: dict):
        return PartitaIVAForfettaria(
            aliquota_irpef_min=_coerce_config_float(data.get("aliquota_irpef_min", {}).get("value"), 0.05),
            aliquota_irpef_max=_coerce_config_float(data.get("aliquota_irpef_max", {}).get("value"), 0.15),
            anni_agevolazione=_coerce_config_int(data.get("anni_agevolazione", {}).get("value"), 5),
            aliquota_inps=_coerce_config_float(data.get("aliquota_inps", {}).get("value"), 0.2607),
            massimale_inps=_coerce_config_float(data.get("massimale_inps", {}).get("value"), 120607.0),
            imponibile=_coerce_config_float(data.get("imponibile", {}).get("value"), 0.78),
            aliquota_rivalsa_inps=_coerce_config_float(data.get("aliquota_rivalsa_inps", {}).get("value"), 0.04),
            percentuale_acconto_imposta_primo=_coerce_config_float(
                data.get("percentuale_acconto_imposta_primo", {}).get("value"), 0.40
            ),
            percentuale_acconto_imposta_secondo=_coerce_config_float(
                data.get("percentuale_acconto_imposta_secondo", {}).get("value"), 0.60
            ),
            percentuale_acconto_inps_forfettario=_coerce_config_float(
                data.get("percentuale_acconto_inps_forfettario", {}).get("value"), 1.00
            ),
            percentuale_rata_acconto_inps_forfettario=_coerce_config_float(
                data.get("percentuale_rata_acconto_inps_forfettario", {}).get("value"), 0.50
            ),
        )


@dataclass
class ScaglioneIrpef:
    value: float
    reddito_min: float
    reddito_max: float
    description: str

    @staticmethod
    def from_dict(data: dict) -> "ScaglioneIrpef":
        reddito_max_raw = data.get("reddito_max")
        if isinstance(reddito_max_raw, str):
            if reddito_max_raw.strip().lower().replace("+", "") == "infinity":
                reddito_max_val = float("inf")
            else:
                try:
                    reddito_max_val = float(reddito_max_raw)
                except ValueError:
                    reddito_max_val = float("inf")
        elif reddito_max_raw is None:
            reddito_max_val = float("inf")
        else:
            reddito_max_val = reddito_max_raw

        return ScaglioneIrpef(
            value=_coerce_config_float(data.get("value"), 0.0),
            reddito_min=_coerce_config_float(data.get("reddito_min"), 0.0),
            reddito_max=reddito_max_val,
            description=data.get("description", ""),
        )


@dataclass
class PartitaIVAOrdinaria:
    scaglioni_irpef: List[ScaglioneIrpef] = field(default_factory=list)
    aliquota_inps: float = 0.0
    massimale_inps: float = 120607.0
    aliquota_cassa_inps: float = 0.0
    aliquota_ritenuta: float = 0.0
    imponibile_iva: float = 0.0
    imponibile_ritenuta_acconto: float = 0.0
    imponibile_cassa_inps: float = 0.0
    imponibile_inps: float = 0.0
    imponibile_irpef: float = 0.0
    percentuale_acconto_irpef_primo: float = 0.0
    percentuale_acconto_irpef_secondo: float = 0.0
    percentuale_acconto_inps: float = 0.0
    percentuale_rata_acconto_inps: float = 0.0

    @staticmethod
    def from_dict(data: dict) -> "PartitaIVAOrdinaria":
        scaglioni = []
        pattern = re.compile(r"aliquota_irpef_(\d+)$")
        for key, value in data.items():
            match = pattern.match(key)
            if match and isinstance(value, dict):
                scaglioni.append((int(match.group(1)), ScaglioneIrpef.from_dict(value)))
        scaglioni.sort(key=lambda item: item[0])

        return PartitaIVAOrdinaria(
            scaglioni_irpef=[scaglione for _, scaglione in scaglioni],
            aliquota_inps=_coerce_config_float(data.get("aliquota_inps", {}).get("value"), 0.2607),
            massimale_inps=_coerce_config_float(data.get("massimale_inps", {}).get("value"), 120607.0),
            aliquota_cassa_inps=_coerce_config_float(data.get("aliquota_cassa_inps", {}).get("value"), 0.04),
            aliquota_ritenuta=_coerce_config_float(data.get("aliquota_ritenuta", {}).get("value"), 0.2),
            imponibile_iva=_coerce_config_float(data.get("imponibile_iva", {}).get("value"), 1.0),
            imponibile_ritenuta_acconto=_coerce_config_float(
                data.get("imponibile_ritenuta_acconto", {}).get("value"), 1.0
            ),
            imponibile_cassa_inps=_coerce_config_float(data.get("imponibile_cassa_inps", {}).get("value"), 1.0),
            imponibile_inps=_coerce_config_float(data.get("imponibile_inps", {}).get("value"), 1.0),
            imponibile_irpef=_coerce_config_float(data.get("imponibile_irpef", {}).get("value"), 1.0),
            percentuale_acconto_irpef_primo=_coerce_config_float(
                data.get("percentuale_acconto_irpef_primo", {}).get("value"), 0.40
            ),
            percentuale_acconto_irpef_secondo=_coerce_config_float(
                data.get("percentuale_acconto_irpef_secondo", {}).get("value"), 0.60
            ),
            percentuale_acconto_inps=_coerce_config_float(
                data.get("percentuale_acconto_inps", {}).get("value"), 0.80
            ),
            percentuale_rata_acconto_inps=_coerce_config_float(
                data.get("percentuale_rata_acconto_inps", {}).get("value"), 0.50
            ),
        )


@dataclass
class AliquotaIva:
    no_iva: float = 0.0
    desc_no_iva: str = ""
    aliquota_iva_ordinaria: float = 0.0
    desc_iva_ordinaria: str = ""
    aliquota_iva_ridotta_1: float = 0.0
    desc_iva_ridotta_1: str = ""
    aliquota_iva_ridotta_2: float = 0.0
    desc_iva_ridotta_2: str = ""
    aliquota_iva_minima: float = 0.0
    desc_iva_minima: str = ""

    @staticmethod
    def from_dict(data: dict) -> "AliquotaIva":
        return AliquotaIva(
            no_iva=_coerce_config_float(data.get("no_iva", {}).get("value"), 0.0),
            aliquota_iva_ordinaria=_coerce_config_float(
                data.get("aliquota_iva_ordinaria", {}).get("value"), 0.0
            ),
            desc_iva_ordinaria=data.get("aliquota_iva_ordinaria", {}).get("description", ""),
            aliquota_iva_ridotta_1=_coerce_config_float(
                data.get("aliquota_iva_ridotta_1", {}).get("value"), 0.0
            ),
            desc_iva_ridotta_1=data.get("aliquota_iva_ridotta_1", {}).get("description", ""),
            aliquota_iva_ridotta_2=_coerce_config_float(
                data.get("aliquota_iva_ridotta_2", {}).get("value"), 0.0
            ),
            desc_iva_ridotta_2=data.get("aliquota_iva_ridotta_2", {}).get("description", ""),
            aliquota_iva_minima=_coerce_config_float(
                data.get("aliquota_iva_minima", {}).get("value"), 0.0
            ),
            desc_iva_minima=data.get("aliquota_iva_minima", {}).get("description", ""),
        )


@dataclass
class InstallmentPlan:
    """Piano di rateizzazione per un dato numero di rate.

    ``day_offsets`` sono i giorni (dalla data di emissione) di ciascuna rata;
    ``amount_split`` sono i pesi di ripartizione del netto (normalizzati a somma
    qualsiasi: vengono riscalati internamente). Entrambe le liste hanno
    lunghezza pari al numero di rate.
    """

    day_offsets: List[int]
    amount_split: List[float]

    @staticmethod
    def from_dict(num_rate: int, data: dict) -> "InstallmentPlan":
        data = data or {}
        raw_offsets = data.get("day_offsets") or []
        raw_split = data.get("amount_split") or []

        day_offsets = [_coerce_config_int(v, 0) for v in raw_offsets]
        amount_split = [_coerce_config_float(v, 0.0) for v in raw_split]

        # Fallback robusti se il piano e' incompleto/corrotto: offset 30/60/90…
        # e ripartizione equa.
        if len(day_offsets) != num_rate:
            day_offsets = [30 * (i + 1) for i in range(num_rate)]
        if len(amount_split) != num_rate or sum(amount_split) <= 0:
            amount_split = [1.0] * num_rate

        return InstallmentPlan(day_offsets=day_offsets, amount_split=amount_split)

    def fractions(self) -> List[float]:
        total = sum(self.amount_split)
        if total <= 0:
            n = len(self.amount_split) or 1
            return [1.0 / n] * n
        return [w / total for w in self.amount_split]

    def split_amount(self, netto: float) -> List[float]:
        """Ripartisce ``netto`` sulle rate; l'ultima assorbe l'arrotondamento."""
        fr = self.fractions()
        amounts = [round(netto * f, 2) for f in fr]
        if amounts:
            amounts[-1] = round(netto - sum(amounts[:-1]), 2)
        return amounts


@dataclass
class FiscalSettings:
    aliquota_iva: AliquotaIva
    partita_iva_forfettaria: PartitaIVAForfettaria
    partita_iva_ordinaria: PartitaIVAOrdinaria
    invoice_expiry_days: int = 30
    installment_plans: Dict[int, InstallmentPlan] = field(default_factory=dict)

    @staticmethod
    def from_dict(data: dict):
        fiscal_data = data or {}
        raw_plans = fiscal_data.get("installment_plans", {}) or {}
        installment_plans: Dict[int, InstallmentPlan] = {}
        for key, plan_data in raw_plans.items():
            try:
                num_rate = int(key)
            except (TypeError, ValueError):
                continue
            installment_plans[num_rate] = InstallmentPlan.from_dict(num_rate, plan_data)

        return FiscalSettings(
            aliquota_iva=AliquotaIva.from_dict(fiscal_data.get("iva", {})),
            partita_iva_forfettaria=PartitaIVAForfettaria.from_dict(
                fiscal_data.get("partita_iva_forfettaria", {})
            ),
            partita_iva_ordinaria=PartitaIVAOrdinaria.from_dict(
                fiscal_data.get("partita_iva_ordinaria", {})
            ),
            invoice_expiry_days=_coerce_config_int(fiscal_data.get("invoice_expiry_days"), 30),
            installment_plans=installment_plans,
        )

    # ------------------------------------------------------------------
    # Helper per scadenze e ripartizione importi
    # ------------------------------------------------------------------

    def _plan_for(self, num_rate: int) -> InstallmentPlan:
        plan = self.installment_plans.get(num_rate)
        if plan is None:
            plan = InstallmentPlan.from_dict(num_rate, {})
        return plan

    def day_offsets_for(self, num_rate: int, single_rate_days: int = None) -> List[int]:
        """Offset in giorni delle scadenze.

        Per la rata singola usa ``single_rate_days`` (override al volo) se fornito,
        altrimenti ``invoice_expiry_days``. Per le multi-rata usa il relativo
        ``InstallmentPlan`` (valori indipendenti dalla preferenza rata singola).
        """
        if num_rate <= 1:
            days = single_rate_days if single_rate_days else self.invoice_expiry_days
            return [int(days)]
        return list(self._plan_for(num_rate).day_offsets)

    def split_netto(self, netto: float, num_rate: int) -> List[float]:
        """Importi per rata (rata singola -> intero netto)."""
        if num_rate <= 1:
            return [round(netto, 2)]
        return self._plan_for(num_rate).split_amount(netto)

    def quota_for_rata(self, netto: float, num_rate: int, rata_index: int) -> float:
        """Quota della rata ``rata_index`` (1-based)."""
        amounts = self.split_netto(netto, num_rate)
        if 1 <= rata_index <= len(amounts):
            return amounts[rata_index - 1]
        return 0.0


@dataclass
class RecurringExpense:
    description: str
    amount: float
    descr_amount: str
    supplier: str
    descr_supplier: str
    deductible: bool
    descr_deductible: str
    deductor: Optional[int]
    descr_deductor: str
    category: str
    descr_category: str
    iva: float
    descr_iva: str
    account: str
    descr_account: str
    frequency: str
    descr_frequency: str
    status: bool
    descr_status: str

    @staticmethod
    def from_dict(data: dict):
        deductor_value = data.get("deductor", {}).get("value")
        try:
            deductor = int(deductor_value) if deductor_value is not None else None
        except (TypeError, ValueError):
            deductor = None

        deductible_value = str(data.get("deductible", {}).get("value", "No")).strip().lower()
        status_value = data.get("status", {}).get("value", RecurringExpensesStatus.SOSPESA.value)

        return RecurringExpense(
            description=data.get("description", ""),
            amount=_coerce_config_float(data.get("amount", {}).get("value"), 0.0),
            descr_amount=data.get("amount", {}).get("description", ""),
            supplier=data.get("supplier", {}).get("value", ""),
            descr_supplier=data.get("supplier", {}).get("description", ""),
            deductible=deductible_value in {"si", "yes", "true"},
            descr_deductible=data.get("deductible", {}).get("description", ""),
            deductor=deductor,
            descr_deductor=data.get("deductor", {}).get("description", ""),
            category=data.get("category", {}).get("value", ""),
            descr_category=data.get("category", {}).get("description", ""),
            iva=_coerce_config_float(data.get("iva", {}).get("value"), 0.0),
            descr_iva=data.get("iva", {}).get("description", ""),
            account=data.get("account", {}).get("value", ""),
            descr_account=data.get("account", {}).get("description", ""),
            frequency=data.get("frequency", {}).get("value", ""),
            descr_frequency=data.get("frequency", {}).get("description", ""),
            status=status_value == RecurringExpensesStatus.ATTIVA.value,
            descr_status=data.get("status", {}).get("description", ""),
        )


@dataclass
class HistoricalFinancialData:
    revenues: Dict[str, Dict[str, float]]
    deducted_expenses: Dict[str, float]

    @staticmethod
    def from_dict(data: dict) -> "HistoricalFinancialData":
        normalized = normalize_historical_file_data(data or {})
        return HistoricalFinancialData(
            revenues={
                year: {name: _coerce_config_float(amount, 0.0) for name, amount in names.items()}
                for year, names in normalized.get("revenues", {}).items()
            },
            deducted_expenses={
                year: _coerce_config_float(amount, 0.0)
                for year, amount in normalized.get("deducted_expenses", {}).items()
            },
        )

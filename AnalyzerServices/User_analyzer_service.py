from datetime import datetime

from Gestionale_Enums import DBExpensesColumns, DBInvoicesColumns, DBSalariesColumns, DBUsersColumns, RegimeFiscale
from QueryServices.Users_query_service import UserQueryService
from Utils.Controller_utils import ControllerUtils


class UserAnalyzerService:
    def __init__(self, user_query_service:UserQueryService, db_model, fiscal_settings):
        self.user_query_service:UserQueryService = user_query_service
        self.db_model = db_model
        self.fiscal_settings = fiscal_settings

    def calcola_tot_fatturato_utente(self, user_id, include_unpaid_invoices: bool = True, year: int = None):
        rows = self.user_query_service.retrieve_user_with_invoices_map_list(
            user_id,
            include_unpaid_invoices=include_unpaid_invoices,
            year=year,
        )
        fatturato = 0.0
        for row in rows:
            tot = row.get(DBInvoicesColumns.TOT_DOCUMENTO.value)
            if tot is None:
                continue
            fatturato += float(tot)
        return fatturato

    def calcola_tot_imponibile_utente(self, user_id, include_unpaid_invoices: bool = False, year: int = None):
        """Somma il solo imponibile (compensi) delle fatture, escludendo IVA,
        cassa/rivalsa INPS e rimborsi spese. E' la base corretta per IRPEF/INPS,
        a differenza di TOT_DOCUMENTO che e' il lordo documento IVA inclusa."""
        rows = self.user_query_service.retrieve_user_with_invoices_map_list(
            user_id,
            include_unpaid_invoices=include_unpaid_invoices,
            year=year,
        )
        imponibile = 0.0
        for row in rows:
            tot = row.get(DBInvoicesColumns.IMPONIBILE.value)
            if tot is None:
                continue
            imponibile += float(tot)
        return imponibile

    def calcola_tot_spese_utente_anticipate(self, user_id, year: int = None):
        rows = self.user_query_service.retrieve_user_with_anticipated_expenses_map_list(user_id, year=year)
        if not rows:
            return 0.0

        target_year = year if year is not None else datetime.now().year
        tot_spese = 0.0
        for row in rows:
            data_str = row.get(DBExpensesColumns.created_at.value)
            if not data_str:
                continue
            try:
                anno = datetime.strptime(data_str, '%Y-%m-%d %H:%M:%S').year
            except ValueError:
                continue
            if anno == target_year:
                tot_spese += float(row.get(DBExpensesColumns.TOT_AMOUNT.value) or 0.0)

        return tot_spese

    def calcola_tot_spese_utente_dedotte(self, user_id, year: int = None):
        rows = self.user_query_service.retrieve_user_with_deducted_expenses_map_list(user_id, year=year)
        if not rows:
            return 0.0

        target_year = year if year is not None else datetime.now().year
        tot_spese = 0.0
        for row in rows:
            data_str = row.get(DBExpensesColumns.created_at.value)
            if not data_str:
                continue
            try:
                anno = datetime.strptime(data_str, '%Y-%m-%d %H:%M:%S').year
            except ValueError:
                continue
            if anno == target_year:
                tot_spese += float(row.get(DBExpensesColumns.TOT_AMOUNT.value) or 0.0)

        return tot_spese

    def calcola_tot_salari_utente(self, user_id, year: int = None):
        rows = self.user_query_service.retrieve_user_with_salaries_map_list(user_id, year=year)
        if not rows:
            return 0.0

        target_year = year if year is not None else datetime.now().year
        tot_salary = 0.0
        for row in rows:
            data_str = row.get(DBSalariesColumns.CREATED_AT.value)
            if not data_str:
                continue
            try:
                anno = datetime.strptime(data_str, '%Y-%m-%d %H:%M:%S').year
            except ValueError as exc:
                print(f'formato data non valido: skip {exc}')
                continue
            if anno == target_year:
                tot_salary += float(row.get(DBSalariesColumns.AMOUNT.value) or 0.0)

        return tot_salary

    def calcola_tot_ritenuta_acconto_ordinaria(self, user_id, year: int = None):
        invoices = self.user_query_service.retrieve_user_with_invoices_map_list(
            user_id, year=year, include_unpaid_invoices=False,
        )
        invoices = ControllerUtils.clear_invoices_list_from_NDC_and_stornate(invoices)
        tot = 0.0
        for invoice in invoices:
            if invoice[DBInvoicesColumns.ID_CLIENTE.value]:
                tot += float(invoice[DBInvoicesColumns.RITENUTA.value])
        return tot

    def calcola_aliquota_tax_forfettaria(self, anno_apertura_piva):
        try:
            current_year = datetime.now().year
            anni_di_attivita = current_year - int(anno_apertura_piva)
            settings = self.fiscal_settings.partita_iva_forfettaria
            if anni_di_attivita < int(settings.anni_agevolazione):
                return settings.aliquota_irpef_min
            return settings.aliquota_irpef_max
        except (ValueError, AttributeError, TypeError):
            return None

    def retrieve_users_with_tot_fatturato(self, year: int = None) -> dict[str, dict[str, float]]:
        output_map = {
            RegimeFiscale.FORFETTARIO.value: {},
            RegimeFiscale.ORDINARIO.value: {},
        }

        for user in self.user_query_service.retrieve_users_map_list():
            regime = user[DBUsersColumns.REGIME_FISCALE.value]
            if regime in output_map:
                output_map[regime][user[DBUsersColumns.LAST_NAME.value]] = self.calcola_tot_fatturato_utente(
                    user[DBUsersColumns.ID.value],
                    year=year,
                )

        return output_map

    def retrieve_users_with_tot_spese(self, year: int = None) -> dict[str, float]:
        output_map: dict[str, float] = {}

        for user in self.user_query_service.retrieve_users_map_list():
            user_id = user[DBUsersColumns.ID.value]
            cognome = user[DBUsersColumns.LAST_NAME.value]
            output_map[cognome] = self.calcola_tot_spese_utente_dedotte(user_id, year=year)

        return output_map

    def pick_fiscal_data_by_user_id(self, user_id: int) -> dict[str, dict[str, str]]:
        user = self.user_query_service.retrieve_user_map_by_id(user_id)
        if not user:
            return {'aliquote': {}, 'imponibili': {}}

        regime = user.get(DBUsersColumns.REGIME_FISCALE.value)
        anno = user.get(DBUsersColumns.ANNO_APERTURA_PIVA.value)

        aliquote: dict[str, str] = {}
        imponibili: dict[str, str] = {}

        if regime == RegimeFiscale.FORFETTARIO.value:
            forfettaria = self.fiscal_settings.partita_iva_forfettaria
            aliquote['IRPEF forfettaria (%)'] = f"{self.calcola_aliquota_tax_forfettaria(anno)}"
            aliquote['INPS (%)'] = f"{forfettaria.aliquota_inps}"
            aliquote['Rivalsa INPS (%)'] = f"{forfettaria.aliquota_rivalsa_inps}"
            imponibili['Imponibile forfettario (%)'] = f"{forfettaria.imponibile}"
        else:
            ordinaria = self.fiscal_settings.partita_iva_ordinaria
            iva = self.fiscal_settings.aliquota_iva
            aliquote['INPS (%)'] = f"{ordinaria.aliquota_inps}"
            aliquote['Cassa INPS (%)'] = f"{ordinaria.aliquota_cassa_inps}"
            aliquote['Ritenuta (%)'] = f"{ordinaria.aliquota_ritenuta}"
            aliquote['IVA ordinaria (%)'] = f"{iva.aliquota_iva_ordinaria}"
            imponibili['Imponibile IVA (%)'] = f"{ordinaria.imponibile_iva}"
            imponibili['Imponibile ritenuta (%)'] = f"{ordinaria.imponibile_ritenuta_acconto}"
            imponibili['Imponibile cassa INPS (%)'] = f"{ordinaria.imponibile_cassa_inps}"
            imponibili['Imponibile INPS (%)'] = f"{ordinaria.imponibile_inps}"
            imponibili['Imponibile IRPEF (%)'] = f"{ordinaria.imponibile_irpef}"

        return {'aliquote': aliquote, 'imponibili': imponibili}

    def calculate_previsione_tasse_forfettaria(self, user_id, year:int = None):
        user = self.user_query_service.retrieve_user_map_by_id(user_id)
        reddito_esterno = 0.0
        fatturato_willow = 0.0
        if user:
            reddito_esterno = float(user[DBUsersColumns.REDDITO_ESTERNO.value])
            # Base = solo imponibile (compensi), per cassa: esclude IVA/rivalsa/
            # rimborsi e le fatture non incassate.
            fatturato_willow = self.calcola_tot_imponibile_utente(
                user_id, year=year, include_unpaid_invoices=False,
            )
            anno_apertura = int(user[DBUsersColumns.ANNO_APERTURA_PIVA.value])
        else:
            return

        # Recupero impostazioni fiscali
        forfettaria_settings = self.fiscal_settings.partita_iva_forfettaria
        perc_acc_imp_primo = float(forfettaria_settings.percentuale_acconto_imposta_primo)
        perc_acc_imp_secondo = float(forfettaria_settings.percentuale_acconto_imposta_secondo)
        perc_acc_inps = float(forfettaria_settings.percentuale_acconto_inps_forfettario)
        perc_rata_inps = float(forfettaria_settings.percentuale_rata_acconto_inps_forfettario)
        massimale_inps = float(forfettaria_settings.massimale_inps)

        # Recupero anticipo anno precedente
        acconto_anno_precedente_IRPEF = float(user.get(DBUsersColumns.LAST_YEAR_IRPEF_ACCONTO.value, 0.0))
        acconto_anno_precedente_INPS = float(user.get(DBUsersColumns.LAST_YEAR_INPS_ACCONTO.value, 0.0))
        acconto_anno_precedente = acconto_anno_precedente_IRPEF + acconto_anno_precedente_INPS

        # Calcolo valori base
        coefficiente_imponibile = float(forfettaria_settings.imponibile)
        aliquota_inps = float(forfettaria_settings.aliquota_inps)
        # La funzione si aspetta l'anno di apertura della P. IVA.
        aliquota_irpef = float(self.calcola_aliquota_tax_forfettaria(anno_apertura))

        # Calcolo reddito imponibile (il coefficiente si applica a fatturato
        # interno ed esterno, entrambi ricavi lordi del regime forfettario).
        reddito_willow = fatturato_willow * coefficiente_imponibile
        reddito_tot = (fatturato_willow + reddito_esterno) * coefficiente_imponibile

        # Calcolo contributi INPS (con tetto al massimale Gestione Separata)
        inps = min(reddito_tot, massimale_inps) * aliquota_inps

        # Calcolo imposta sostitutiva: i contributi INPS sono deducibili dalla base
        base_imponibile_irpef = max(0.0, reddito_tot - inps)
        irpef = base_imponibile_irpef * aliquota_irpef
        totale_tasse = inps + irpef

        # Calcolo saldo corrente (tasse totali - acconto anno precedente)
        saldo_corrente = max(0, totale_tasse - acconto_anno_precedente)

        # Calcolo quote Willow
        quota_willow = reddito_willow / reddito_tot if reddito_tot > 0 else 0
        irpef_w = irpef * quota_willow
        inps_w = inps * quota_willow
        tasse_willow = inps_w + irpef_w
        saldo_willow = saldo_corrente * quota_willow

        # Calcolo acconti per l'anno successivo
        # IRPEF
        primo_acconto_irpef = irpef * perc_acc_imp_primo
        secondo_acconto_irpef = irpef * perc_acc_imp_secondo

        # INPS
        acconto_inps_totale = inps * perc_acc_inps
        primo_acconto_inps = acconto_inps_totale * perc_rata_inps
        secondo_acconto_inps = acconto_inps_totale - primo_acconto_inps

        # Calcolo totale acconti
        acconto_totale = (primo_acconto_irpef + secondo_acconto_irpef +
                          primo_acconto_inps + secondo_acconto_inps)
        acconto_willow = acconto_totale * quota_willow

        # Calcolo totale per scadenza
        primo_acconto_totale = primo_acconto_irpef + primo_acconto_inps
        secondo_acconto_totale = secondo_acconto_irpef + secondo_acconto_inps

        # Ripartizione per Willow
        primo_acconto_willow = primo_acconto_totale * quota_willow
        secondo_acconto_willow = secondo_acconto_totale * quota_willow

        # Mappa versamenti (saldo e acconti)
        versamenti_map = {
            "SALDO TOTALE": round(saldo_corrente, 2),
            "ACCONTO TOTALE": round(acconto_totale, 2),
            "SALDO WILLOW": round(saldo_willow, 2),
            "ACCONTO WILLOW": round(acconto_willow, 2)
        }

        # Output map per tooltip e dettagli
        output_map = {
            # Informazioni di base
            "FATTURATO_WILLOW": round(fatturato_willow, 2),
            "REDDITO_ESTERNO": round(reddito_esterno, 2),
            "COEFFICIENTE_IMPONIBILE": coefficiente_imponibile,
            "ALIQUOTA_INPS": aliquota_inps,
            "ALIQUOTA_IRPEF": aliquota_irpef,
            "PERC_ACC_IMP_PRIMO": perc_acc_imp_primo,
            "PERC_ACC_IMP_SECONDO": perc_acc_imp_secondo,
            "PERC_ACC_INPS": perc_acc_inps,
            "PERC_RATA_INPS": perc_rata_inps,

            # Calcoli intermedi
            "REDDITO_WILLOW": round(reddito_willow, 2),
            "REDDITO_TOT": round(reddito_tot, 2),
            "BASE_IMPONIBILE_IRPEF": round(base_imponibile_irpef, 2),
            "MASSIMALE_INPS": round(massimale_inps, 2),
            "QUOTA_WILLOW": quota_willow,

            # Totali tasse
            "INPS": round(inps, 2),
            "IRPEF": round(irpef, 2),
            "TOTALE_TASSE": round(totale_tasse, 2),
            "INPS WILLOW": round(inps_w, 2),
            "IRPEF WILLOW": round(irpef_w, 2),
            "TASSE_WILLOW": round(tasse_willow, 2),

            # Anticipo anno precedente
            "ACCONTO_ANNO_PRECEDENTE": round(acconto_anno_precedente, 2),
            "ACCONTO_ANNO_PRECEDENTE_IRPEF": round(acconto_anno_precedente_IRPEF, 2),
            "ACCONTO_ANNO_PRECEDENTE_INPS": round(acconto_anno_precedente_INPS, 2),

            # Saldi
            "SALDO_CORRENTE": round(saldo_corrente, 2),
            "SALDO_WILLOW": round(saldo_willow, 2),

            # Acconti anno successivo
            "ACCONTO_TOTALE": round(acconto_totale, 2),
            "ACCONTO_WILLOW": round(acconto_willow, 2),
            "PRIMO_ACCONTO_TOTALE": round(primo_acconto_totale, 2),
            "SECONDO_ACCONTO_TOTALE": round(secondo_acconto_totale, 2),
            "PRIMO_ACCONTO_WILLOW": round(primo_acconto_willow, 2),
            "SECONDO_ACCONTO_WILLOW": round(secondo_acconto_willow, 2),
            "PRIMO_ACCONTO_IRPEF": round(primo_acconto_irpef, 2),
            "SECONDO_ACCONTO_IRPEF": round(secondo_acconto_irpef, 2),
            "PRIMO_ACCONTO_INPS": round(primo_acconto_inps, 2),
            "SECONDO_ACCONTO_INPS": round(secondo_acconto_inps, 2),
            "PRIMO_ACCONTO_IRPEF_WILLOW": round(primo_acconto_irpef * quota_willow, 2),
            "SECONDO_ACCONTO_IRPEF_WILLOW": round(secondo_acconto_irpef * quota_willow, 2),
            "PRIMO_ACCONTO_INPS_WILLOW": round(primo_acconto_inps * quota_willow, 2),
            "SECONDO_ACCONTO_INPS_WILLOW": round(secondo_acconto_inps * quota_willow, 2)
        }

        # Output principale
        return {
            "INPS": round(inps, 2),
            "IRPEF": round(irpef, 2),
            "IRPEF WILLOW": round(irpef_w, 2),
            "INPS WILLOW": round(inps_w, 2)
        }, versamenti_map, output_map

    def calculate_previsione_tasse_ordinaria(self, user_id, year:int = None):
        user = self.user_query_service.retrieve_user_map_by_id(user_id)
        if not user:
            return {}

        # Recupero dati utente
        reddito_esterno = float(user.get(DBUsersColumns.REDDITO_ESTERNO.value, 0.0))
        spese_esterne = float(user.get(DBUsersColumns.SPESE_DEDOTTE_ESTERNE.value, 0.0))
        # Base = solo imponibile (compensi), al netto di IVA/cassa/rimborsi e
        # delle fatture non incassate (principio di cassa).
        fatturato_willow = self.calcola_tot_imponibile_utente(user_id, year = year, include_unpaid_invoices = False)
        spese_willow = self.calcola_tot_spese_utente_dedotte(user_id, year = year)
        tot_ritenuta = self.calcola_tot_ritenuta_acconto_ordinaria(user_id, year = year)
        acconto_anno_precedente_IRPEF = float(user.get(DBUsersColumns.LAST_YEAR_IRPEF_ACCONTO.value, 0.0))
        acconto_anno_precedente_INPS = float(user.get(DBUsersColumns.LAST_YEAR_INPS_ACCONTO.value, 0.0))
        acconto_anno_precedente = acconto_anno_precedente_IRPEF + acconto_anno_precedente_INPS

        # Recupero impostazioni fiscali
        ordinaria_settings = self.fiscal_settings.partita_iva_ordinaria
        aliquota_inps = float(ordinaria_settings.aliquota_inps)
        massimale_inps = float(ordinaria_settings.massimale_inps)
        scaglioni = ordinaria_settings.scaglioni_irpef
        perc_acc_irpef_primo = float(ordinaria_settings.percentuale_acconto_irpef_primo)
        perc_acc_irpef_secondo = float(ordinaria_settings.percentuale_acconto_irpef_secondo)
        perc_acc_inps = float(ordinaria_settings.percentuale_acconto_inps)
        perc_rata_inps = float(ordinaria_settings.percentuale_rata_acconto_inps)

        # 1. Calcolo scenario completo
        ricavi_totali = fatturato_willow + reddito_esterno
        spese_totali = spese_willow + spese_esterne
        reddito_netto_completo = ricavi_totali - spese_totali
        # INPS Gestione Separata con tetto al massimale contributivo
        inps_completo = min(max(0.0, reddito_netto_completo), massimale_inps) * aliquota_inps
        base_irpef_completo = reddito_netto_completo - inps_completo
        irpef_lorda_completo = self._calcola_irpef(base_irpef_completo, scaglioni)
        irpef_netta_completo = irpef_lorda_completo - tot_ritenuta

        # 2. Ripartizione proporzionale della quota collettivo.
        # La quota e' il peso del reddito netto interno sul reddito netto totale;
        # IRPEF e INPS del collettivo sono la stessa frazione del totale, cosi'
        # che quota collettivo + quota propria == totale (quadratura garantita).
        reddito_netto_willow = fatturato_willow - spese_willow
        quota_willow_base = (reddito_netto_willow / reddito_netto_completo) if reddito_netto_completo > 0 else 0
        irpef_willow = irpef_lorda_completo * quota_willow_base
        inps_willow = inps_completo * quota_willow_base

        # 3. Calcolo tasse totali. La ritenuta nasce dalle fatture interne, quindi
        # e' interamente attribuita al collettivo.
        totale_tasse = inps_completo + max(0, irpef_netta_completo)
        tasse_willow = inps_willow + max(0, irpef_willow - tot_ritenuta)
        tasse_non_willow = totale_tasse - tasse_willow

        # 6. Calcolo versamenti (saldo e acconti)
        # Ripartizione proporzionale acconto precedente
        if totale_tasse > 0:
            prop_willow = tasse_willow / totale_tasse
            prop_non_willow = tasse_non_willow / totale_tasse
        else:
            prop_willow = prop_non_willow = 0.0

        # Calcolo saldo corrente
        saldo_corrente = max(0, totale_tasse - acconto_anno_precedente)
        saldo_willow = saldo_corrente * prop_willow
        saldo_non_willow = saldo_corrente * prop_non_willow

        # Calcolo nuovo acconto per l'anno successivo
        acconto_inps = inps_completo * perc_acc_inps
        acconto_irpef = max(0, irpef_netta_completo) * 1.0  # 100% per IRPEF

        # Ripartizione proporzionale acconto
        acconto_totale = acconto_inps + acconto_irpef
        acconto_willow = acconto_totale * prop_willow
        acconto_non_willow = acconto_totale * prop_non_willow

        # Rate acconto INPS
        rata_inps = acconto_inps * perc_rata_inps
        rata_inps_willow = rata_inps * prop_willow
        rata_inps_non_willow = rata_inps * prop_non_willow

        # Rate acconto IRPEF
        rata_irpef_primo = acconto_irpef * perc_acc_irpef_primo
        rata_irpef_secondo = acconto_irpef * perc_acc_irpef_secondo

        rata_irpef_primo_willow = rata_irpef_primo * prop_willow
        rata_irpef_primo_non_willow = rata_irpef_primo * prop_non_willow
        rata_irpef_secondo_willow = rata_irpef_secondo * prop_willow
        rata_irpef_secondo_non_willow = rata_irpef_secondo * prop_non_willow

        # Calcolo totale per scadenza (giugno e novembre)
        totale_giugno = saldo_corrente + rata_inps + rata_irpef_primo
        totale_giugno_willow = saldo_willow + rata_inps_willow + rata_irpef_primo_willow
        totale_giugno_non_willow = saldo_non_willow + rata_inps_non_willow + rata_irpef_primo_non_willow

        # A novembre cade anche la seconda rata dell'acconto INPS.
        totale_novembre = rata_irpef_secondo + rata_inps
        totale_novembre_willow = rata_irpef_secondo_willow + rata_inps_willow
        totale_novembre_non_willow = rata_irpef_secondo_non_willow + rata_inps_non_willow

        # 7. Mappa versamenti (saldo e acconti)
        versamenti_map = {
            "SALDO TOTALE": round(saldo_corrente, 2),
            "ACCONTO TOTALE": round(acconto_totale, 2),
            "SALDO WILLOW": round(saldo_willow, 2),
            "ACCONTO WILLOW": round(acconto_willow, 2)
        }

        # 8. Output map per tooltip e dettagli
        output_map = {
            # Valori complessivi
            "REDDITO_NETTO": round(reddito_netto_completo, 2),
            "INPS": round(inps_completo, 2),
            "BASE_IRPEF": round(base_irpef_completo, 2),
            "IRPEF_LORDA": round(irpef_lorda_completo, 2),
            "RITENUTA": round(tot_ritenuta, 2),
            "IRPEF_NETTA": round(irpef_netta_completo, 2),
            "TOTALE_TASSE": round(totale_tasse, 2),
            "ALIQUOTA_INPS": round(aliquota_inps, 4),
            "PERC_ACCONTO_INPS": round(perc_acc_inps, 4),
            "PERC_RATA_INPS": round(perc_rata_inps, 4),
            "PERC_ACCONTO_IRPEF_PRIMO": round(perc_acc_irpef_primo, 4),
            "PERC_ACCONTO_IRPEF_SECONDO": round(perc_acc_irpef_secondo, 4),
            "ACCONTO_ANNO_PRECEDENTE": round(acconto_anno_precedente, 2),
            "SALDO_CORRENTE": round(saldo_corrente, 2),
            "ACCONTO_ANNO_SUCCESSIVO": round(acconto_totale, 2),
            "RATA_IRPEF_PRIMO": round(rata_irpef_primo, 2),
            "RATA_IRPEF_SECONDO": round(rata_irpef_secondo, 2),
            "RATA_INPS": round(rata_inps, 2),
            "MASSIMALE_INPS": round(massimale_inps, 2),

            # Ripartizione per Willow (proporzionale)
            "WILLOW_IRPEF_TOT": round(irpef_willow, 2),
            "WILLOW_INPS": round(inps_willow, 2),
            "WILLOW_RITENUTA": round(tot_ritenuta, 2),
            "WILLOW_TASSE_TOT": round(tasse_willow, 2),
            "NON_WILLOW_TASSE_TOT": round(tasse_non_willow, 2),

            # Coefficienti
            "QUOTA_WILLOW_BASE": round(quota_willow_base, 4),
            "PROP_WILLOW": round(prop_willow, 4),
            "PROP_NON_WILLOW": round(prop_non_willow, 4),

            "REDDITO_ESTERNO": round(reddito_esterno, 2),
            "RICAVI_TOTALI": round(ricavi_totali, 2),
            "SPESE_ESTERNE": round(spese_esterne, 2),
            "SPESE_TOTALI": round(spese_totali, 2),
            "REDDITO_NETTO_WILLOW": round(reddito_netto_willow, 2),
            "WILLOW_IRPEF_NETTA": round(max(0, irpef_willow - tot_ritenuta), 2),
            "FATTURATO_WILLOW": round(fatturato_willow, 2),
            "SPESE_WILLOW": round(spese_willow, 2),

            # Saldi
            "SALDO_TOTALE": round(saldo_corrente, 2),
            "SALDO_WILLOW": round(saldo_willow, 2),
            "SALDO_NON_WILLOW": round(saldo_non_willow, 2),

            # Acconti totali
            "ACCONTO_TOTALE": round(acconto_totale, 2),
            "ACCONTO_WILLOW": round(acconto_willow, 2),
            "ACCONTO_NON_WILLOW": round(acconto_non_willow, 2),

            # Rate INPS
            "RATA_INPS_WILLOW": round(rata_inps_willow, 2),
            "RATA_INPS_NON_WILLOW": round(rata_inps_non_willow, 2),

            # Rate IRPEF
            "RATA_IRPEF_PRIMO_WILLOW": round(rata_irpef_primo_willow, 2),
            "RATA_IRPEF_PRIMO_NON_WILLOW": round(rata_irpef_primo_non_willow, 2),
            "RATA_IRPEF_SECONDO_WILLOW": round(rata_irpef_secondo_willow, 2),
            "RATA_IRPEF_SECONDO_NON_WILLOW": round(rata_irpef_secondo_non_willow, 2),

            # Totali per scadenza
            "TOTALE_GIUGNO": round(totale_giugno, 2),
            "TOTALE_GIUGNO_WILLOW": round(totale_giugno_willow, 2),
            "TOTALE_GIUGNO_NON_WILLOW": round(totale_giugno_non_willow, 2),
            "TOTALE_NOVEMBRE": round(totale_novembre, 2),
            "TOTALE_NOVEMBRE_WILLOW": round(totale_novembre_willow, 2),
            "TOTALE_NOVEMBRE_NON_WILLOW": round(totale_novembre_non_willow, 2),

            # Date di scadenza
            "SCADENZA_GIUGNO": "30/06",
            "SCADENZA_NOVEMBRE": "30/11"
        }

        # 9. Preparazione risultati
        return {
            "INPS": round(inps_completo, 2),
            "IRPEF NETTA": round(irpef_netta_completo, 2),
            "WILLOW INPS": round(inps_willow, 2),
            "WILLOW IRPEF": round(max(0, irpef_willow - tot_ritenuta), 2)
        }, versamenti_map, output_map

    def calculate_previsione_tasse_willow(self, year:int = None):
        list_of_users = self.user_query_service.retrieve_users_map_list()
        result_map = {}
        total_saldo_willow = 0.0
        total_acconto_willow = 0.0
        total_irpef_willow = 0.0
        total_inps_willow = 0.0

        for user in list_of_users:
            user_id = user[DBUsersColumns.ID.value]
            regime_fiscale = user[DBUsersColumns.REGIME_FISCALE.value]
            user_name = f"{user.get(DBUsersColumns.FIRST_NAME.value, '')} {user.get(DBUsersColumns.LAST_NAME.value, '')}"

            saldo_willow = 0.0
            acconto_willow = 0.0
            irpef_willow = 0.0
            inps_willow = 0.0

            try:
                if regime_fiscale == RegimeFiscale.ORDINARIO.value:
                    tasse_map, versamenti, _ = self.calculate_previsione_tasse_ordinaria(user_id, year = year)
                    saldo_willow = versamenti.get("SALDO WILLOW", 0.0)
                    acconto_willow = versamenti.get("ACCONTO WILLOW", 0.0)
                    irpef_willow = tasse_map.get("WILLOW IRPEF", 0.0)
                    inps_willow = tasse_map.get("WILLOW INPS", 0.0)

                elif regime_fiscale == RegimeFiscale.FORFETTARIO.value:
                    tasse_map, versamenti, _ = self.calculate_previsione_tasse_forfettaria(user_id, year = year)
                    saldo_willow = versamenti.get("SALDO WILLOW", 0.0)
                    acconto_willow = versamenti.get("ACCONTO WILLOW", 0.0)
                    irpef_willow = tasse_map.get("IRPEF WILLOW", 0.0)
                    inps_willow = tasse_map.get("INPS WILLOW", 0.0)

                # Aggiungi i valori dell'utente alla mappa
                result_map[user_name] = {
                    "SALDO WILLOW": saldo_willow,
                    "ACCONTO WILLOW": acconto_willow,
                    "IRPEF WILLOW": irpef_willow,
                    "INPS WILLOW": inps_willow
                }

                # Aggiorna i totali
                total_saldo_willow += saldo_willow
                total_acconto_willow += acconto_willow
                total_irpef_willow += irpef_willow
                total_inps_willow += inps_willow

            except Exception as e:
                print(f"Errore nel calcolo per l'utente {user_name} (ID: {user_id}): {str(e)}")
                result_map[user_name] = {
                    "SALDO WILLOW": 0.0,
                    "ACCONTO WILLOW": 0.0,
                    "IRPEF WILLOW": 0.0,
                    "INPS WILLOW": 0.0
                }

        # Aggiungi i totali alla mappa risultato
        result_map["TOTALE"] = {
            "SALDO WILLOW": total_saldo_willow,
            "ACCONTO WILLOW": total_acconto_willow,
            "IRPEF WILLOW": total_irpef_willow,
            "INPS WILLOW": total_inps_willow
        }

        return result_map

    def _calcola_irpef(self, imponibile, scaglioni):
        """Calcola l'IRPEF in base agli scaglioni di reddito"""
        if imponibile <= 0:
            return 0.0

        scaglioni_ordinati = sorted(scaglioni, key=lambda x: x.reddito_min)
        irpef = 0.0
        reddito_residuo = imponibile

        for scaglione in scaglioni_ordinati:
            if reddito_residuo <= 0:
                break

            # Calcola la parte di reddito nello scaglione
            if scaglione.reddito_max == float('inf'):
                parte_scaglione = reddito_residuo
            else:
                ammontare_scaglione = float(scaglione.reddito_max) - float(scaglione.reddito_min)
                parte_scaglione = min(reddito_residuo, ammontare_scaglione)

            # Applica l'aliquota marginale
            irpef += parte_scaglione * (float(scaglione.value))
            reddito_residuo -= parte_scaglione

        return irpef

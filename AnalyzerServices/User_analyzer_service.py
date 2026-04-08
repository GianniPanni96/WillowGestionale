from datetime import datetime

from Gestionale_Enums import DBExpensesColumns, DBInvoicesColumns, DBSalariesColumns, DBUsersColumns, RegimeFiscale
from QueryServices.Users_query_service import UserQueryService
from Utils.Controller_utils import ControllerUtils


class UserAnalyzerService:
    def __init__(self, user_query_service:UserQueryService, db_model, fiscal_settings):
        self.user_query_service:UserQueryService = user_query_service
        self.db_model = db_model
        self.fiscal_settings = fiscal_settings

    def calcola_reddito_tot_utente(self, user_id, year: int = None):
        invoices = self.db_model.fetch_invoices_by_user_id(user_id)
        user = self.user_query_service.retrieve_user_map_by_id(user_id)
        reddito_esterno = user[DBUsersColumns.REDDITO_ESTERNO.value] if user else 0
        reddito = reddito_esterno

        filter_invoices = True
        if year is not None:
            selected_year = year
            if year == -1:
                filter_invoices = False
        else:
            selected_year = datetime.now().year

        if filter_invoices:
            invoices = [
                invoice
                for invoice in invoices
                if datetime.strptime(invoice[DBInvoicesColumns.DATA_CREAZIONE.value], '%Y-%m-%d').year == selected_year
            ]

        for invoice in invoices:
            reddito += invoice[DBInvoicesColumns.TOT_DOCUMENTO.value]

        return reddito

    def calcola_tot_fatturato_utente(self, user_id, include_unpaid_invoices: bool = True, year: int = None):
        rows = self.user_query_service.retrieve_user_with_invoices_map_list(
            user_id,
            include_unpaid_invoices=include_unpaid_invoices,
            year=year,
        )
        if not rows:
            return 0.0

        target_year = year if year is not None else datetime.now().year
        fatturato = 0.0
        for row in rows:
            data_str = row.get(DBInvoicesColumns.DATA_CREAZIONE.value)
            if not data_str:
                continue
            try:
                anno = datetime.strptime(data_str, '%Y-%m-%d').year
            except ValueError:
                continue
            if anno == target_year:
                fatturato += float(row.get(DBInvoicesColumns.TOT_DOCUMENTO.value) or 0.0)

        return fatturato

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
        invoices = self.user_query_service.retrieve_user_with_invoices_map_list(user_id, year=year)
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

    def calcola_aliquota_tax_ordinaria(self, user_id):
        reddito = self.calcola_reddito_tot_utente(user_id)
        scaglioni = self.fiscal_settings.partita_iva_ordinaria.scaglioni_irpef

        for scaglione in scaglioni:
            if scaglione.reddito_min <= reddito <= scaglione.reddito_max:
                return scaglione.value

        if scaglioni:
            return scaglioni[-1].value
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


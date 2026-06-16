from datetime import datetime
import pandas as pd

from AnalyzerServices.User_analyzer_service import UserAnalyzerService
from Gestionale_Enums import *
from Model import DatabaseModel
from ConfigManagers import FiscalSettings, HistoricalFinancialData

from Controllerss.User_controller import UserController

from QueryServices.Invoices_query_service import InvoiceQueryService
from QueryServices.Users_query_service import UserQueryService
from Utils.Controller_utils import ControllerUtils


class InvoiceAnalyzerService:
    """
    Servizio applicativo che calcola gli aggregati economici delle fatture.

    Questa classe lavora sopra ``InvoiceQueryService`` e ``DatabaseModel``:
    non costruisce interfacce, ma espone metriche pronte per view e report,
    mantenendo fuori dalla UI la logica di analisi.
    """

    def __init__(self, user_controller:UserController, user_query_service:UserQueryService, user_analyzer_service:UserAnalyzerService, invoices_query_service: InvoiceQueryService,
                 database_model: DatabaseModel, fiscal_settings:FiscalSettings, historical_financial_data_settings:HistoricalFinancialData):
        """Memorizza i servizi necessari per query e calcoli aggregati."""
        self.user_controller:UserController = user_controller
        self.user_query_service:UserQueryService = user_query_service
        self.user_analyzer_service:UserAnalyzerService = user_analyzer_service
        self.fiscal_settings:FiscalSettings = fiscal_settings
        self.historical_financial_data_settings:HistoricalFinancialData = historical_financial_data_settings
        self.invoices_query_service: InvoiceQueryService = invoices_query_service
        self.db_model: DatabaseModel = database_model

    def check_linked_tot_expenses(self, invoice_id):
        """
        Controlla il totale delle spese associate a una fattura e verifica
        se copre l’importo dei rimborsi con una tolleranza di 5.
        Ritorna una tupla (check, linked_expenses_tot) dove:
          - check: True se esistono spese e linked_expenses_tot >= rimborsi
                   oppure |linked_expenses_tot - rimborsi| < 5; altrimenti False
          - linked_expenses_tot: somma degli importi delle spese associate
        """
        # Recupera tutte le spese collegate alla fattura
        expenses = self.invoices_query_service.retrieve_invoice_with_expenses_map_list(invoice_id)
        # Somma tutti gli importi
        total = 0.0
        for exp in expenses:
            try:
                total += float(exp[DBExpensesColumns.TOT_AMOUNT.value])
            except (KeyError, ValueError, TypeError):
                continue

        # Se non ci sono spese, esci subito
        if not expenses:
            return False, total

        # Ottieni l’importo dei rimborsi (prendo il primo record)
        try:
            rimborsi = float(expenses[0][DBInvoicesColumns.RIMBORSI.value])
        except (KeyError, ValueError, TypeError):
            rimborsi = 0.0

        # Verifica copertura con tolleranza ±5
        check = (total >= rimborsi) or (abs(total - rimborsi) < 5)
        return check, total

    def count_invoices(self, year: int = None, include_unpaid_invoices:bool = False):
        """
        Conta il numero di fatture che non siano state stornate, applicando il filtro per l'anno corrente se specificato.

        :param year: Anno di riferimento per il retrieving.
        :return: Numero di fatture (int)
        """
        # Recupera le fatture già filtrate
        invoices = self.invoices_query_service.retrieve_invoices_map_list(year=year, include_unpaid_invoices=include_unpaid_invoices)
        # Filtra ulteriormente per rimuovere NDC e stornate
        filtered_invoices = ControllerUtils.clear_invoices_list_from_NDC_and_stornate(invoices)
        return len(filtered_invoices)

    def calculate_TOT_DOCUMENTO_invoiced(self, year: int = None, include_unpaid_invoices:bool = False):
        """
        Calcola il totale fatturato, escludendo NDC e fatture stornate.

        :param year: Anno di riferimento per il retrieving.
        :return: Totale fatturato (float)
        """
        # Recupera le fatture già filtrate
        invoices = self.invoices_query_service.retrieve_invoices_map_list(year=year, include_unpaid_invoices=include_unpaid_invoices)
        # Filtra ulteriormente per rimuovere NDC e stornate
        filtered_invoices = ControllerUtils.clear_invoices_list_from_NDC_and_stornate(invoices)

        tot = 0.0
        for invoice in filtered_invoices:
            amount = invoice.get(DBInvoicesColumns.TOT_DOCUMENTO.value)
            if amount:
                tot += float(amount)
        return tot

    def calculate_IVA_invoiced(self, year: int = None, include_unpaid_invoices:bool = False):
        """
        Calcola il totale IVA fatturata, escludendo NDC e fatture stornate.

        :param year: Anno di riferimento per il retrieving.
        :return: Totale IVA (float)
        """
        # Recupera le fatture già filtrate
        invoices = self.invoices_query_service.retrieve_invoices_map_list(year=year, include_unpaid_invoices=include_unpaid_invoices)
        # Filtra ulteriormente per rimuovere NDC e stornate
        filtered_invoices = ControllerUtils.clear_invoices_list_from_NDC_and_stornate(invoices)

        iva_total = 0.0
        for invoice in filtered_invoices:
            iva = invoice.get(DBInvoicesColumns.IVA.value)
            if iva:
                iva_total += float(iva)
        return iva_total

    def calculate_RITENUTA_ACCONTO_invoiced(self, year: int = None, include_unpaid_invoices:bool = False):
        """
        Calcola il totale della ritenuta d'acconto fatturata.
        """
        # Recupera le fatture già filtrate
        invoices = self.invoices_query_service.retrieve_invoices_map_list(year=year, include_unpaid_invoices=include_unpaid_invoices)
        # Filtra ulteriormente per rimuovere NDC e stornate
        filtered_invoices = ControllerUtils.clear_invoices_list_from_NDC_and_stornate(invoices)

        ritenuta = 0.0
        for invoice in filtered_invoices:
            amount = invoice.get(DBInvoicesColumns.RITENUTA.value)
            if amount:
                ritenuta += float(amount)
        return ritenuta

    def calculate_FATT_LORDO_invoiced(self, year: int = None, include_unpaid_invoices:bool = False):
        """
        Calcola il fatturato lordo (totale documento - IVA).
        """
        tot_documento = self.calculate_TOT_DOCUMENTO_invoiced(year = year, include_unpaid_invoices = include_unpaid_invoices)
        iva = self.calculate_IVA_invoiced(year = year, include_unpaid_invoices = include_unpaid_invoices)
        return tot_documento - iva

    def calculate_FATT_NETTO_invoiced(self, year : int = None, include_unpaid_invoices:bool = False):
        """
        Calcola il fatturato netto (totale documento - IVA - ritenuta).
        """
        tot_documento = self.calculate_TOT_DOCUMENTO_invoiced(year=year, include_unpaid_invoices=include_unpaid_invoices)
        iva = self.calculate_IVA_invoiced(year=year, include_unpaid_invoices=include_unpaid_invoices)
        ritenuta = self.calculate_RITENUTA_ACCONTO_invoiced(year=year, include_unpaid_invoices=include_unpaid_invoices)
        return tot_documento - iva - ritenuta

    def calculate_CRED_LORDO_invoiced(self, year: int = None, include_unpaid_invoices:bool = False):
        """
        Calcola i crediti lordi basandosi sulle fatture non pagate.
        """
        # Utilizza la funzione comune di processing
        return self._process_crediti(year, netto=False, include_unpaid_invoices=include_unpaid_invoices)

    def calculate_CRED_NETTO_invoiced(self, year: int = None, include_unpaid_invoices:bool = False):
        """
        Calcola i crediti netti basandosi sulle fatture non pagate.
        """
        # Utilizza la funzione comune di processing
        return self._process_crediti(year, netto=True, include_unpaid_invoices=include_unpaid_invoices)

    def calculate_MEDIA_FATTURA_LORDO_invoiced(self, year: int = None, include_unpaid_invoices:bool = False):
        """
        Calcola la media del fatturato lordo per fattura.
        """
        fatt_lordo = self.calculate_FATT_LORDO_invoiced(year=year, include_unpaid_invoices=include_unpaid_invoices)
        numero_fatt = self.count_invoices(year=year, include_unpaid_invoices=include_unpaid_invoices)
        return fatt_lordo / numero_fatt if numero_fatt > 0 else -1

    def calculate_MEDIA_FATTURA_NETTO_invoiced(self, year: int = None, include_unpaid_invoices:bool = False):
        """
        Calcola la media del fatturato netto per fattura.
        """
        fatt_netto = self.calculate_FATT_NETTO_invoiced(year=year, include_unpaid_invoices=include_unpaid_invoices)
        numero_fatt = self.count_invoices(year=year, include_unpaid_invoices=include_unpaid_invoices)
        return fatt_netto / numero_fatt if numero_fatt > 0 else -1

    # Funzione helper comune per il calcolo dei crediti
    def _process_crediti(self, year: int, netto:bool=True, include_unpaid_invoices:bool = False):
        """
        Funzione comune per il calcolo dei crediti lordi o netti.
        """
        # Recupera le fatture con i pagamenti associati
        rows = self.db_model.fetch_invoices_with_payments()
        num_invoice_cols = len(DBInvoicesColumns)

        # Crea un set di ID fatture da includere (usando la nuova logica di filtraggio)
        included_ids = {inv[DBInvoicesColumns.ID.value] for inv in self.invoices_query_service.retrieve_invoices_map_list(year=year, include_unpaid_invoices=include_unpaid_invoices)}

        # Raggruppa per invoice_id
        grouped = {}
        for row in rows:
            invoice_id = row[0]
            if invoice_id not in included_ids:  # Filtra per le fatture da includere
                continue

            if invoice_id not in grouped:
                grouped[invoice_id] = {
                    "invoice_raw": row[0:num_invoice_cols],
                    "payments": []
                }
            payment_raw = row[num_invoice_cols:]
            if payment_raw and payment_raw[0] is not None:
                grouped[invoice_id]["payments"].append(payment_raw)

        # Converti in mappe e filtra
        all_invoice_maps = {}
        for inv_id, data in grouped.items():
            inv_map = ControllerUtils.row_to_map(data["invoice_raw"], DBInvoicesColumns)
            inv_map["payments"] = data["payments"]
            all_invoice_maps[inv_id] = inv_map

        filtered_invoices = ControllerUtils.clear_invoices_list_from_NDC_and_stornate(list(all_invoice_maps.values()))
        payment_cols = [col.value for col in DBPaymentsColumns]
        totale_credito = 0.0

        for invoice in filtered_invoices:
            try:
                num_rate = int(invoice[DBInvoicesColumns.NUMERO_RATE.value])
                tot_documento = float(invoice[DBInvoicesColumns.TOT_DOCUMENTO.value])
                iva = float(invoice[DBInvoicesColumns.IVA.value])
                ritenuta = float(invoice.get(DBInvoicesColumns.RITENUTA.value, 0))
            except (ValueError, TypeError):
                continue

            # Converti i pagamenti
            payments_maps = []
            for p in invoice.get("payments", []):
                if p and p[0] is not None:
                    payments_maps.append(dict(zip(payment_cols, p)))

            # Calcola il credito in base al tipo di fattura
            if num_rate == int(Rateizzazione.UNA.value):
                paid = any(int(pm.get(DBPaymentsColumns.LINKED_RATA.value, 0)) == 1 for pm in payments_maps)
                if not paid:
                    credito = tot_documento - iva - (ritenuta if netto else 0)
                    totale_credito += credito

            elif num_rate > 1:
                base_credito = tot_documento - iva - (ritenuta if netto else 0)
                quote = self.fiscal_settings.split_netto(base_credito, num_rate)
                for rata in range(1, num_rate + 1):
                    paid = any(int(pm.get(DBPaymentsColumns.LINKED_RATA.value, 0)) == rata for pm in payments_maps)
                    if not paid:
                        totale_credito += quote[rata - 1]

        return totale_credito

    # ancora da implementare perché manca la parte di produzioni
    def calculate_MEDIA_PAGAM_ORARIO_LORDO_invoiced(self, year: int = None):
        return 0

    def calculate_MEDIA_PAGAM_ORARIO_NETTO_invoiced(self, current_year=True):
        return 0

    def calcola_derivati_fattura_ordinaria(self,
                                            aliquota_cassa_inps,
                                            aliquota_ritenuta_acconto,
                                            aliquota_iva,
                                            imponibile_tax,
                                            imponibile_cassa_inps,
                                            imponibile_iva,
                                            tipologia_cliente,
                                            tot_servizi,
                                            tot_rimborsi):

        imponibile = tot_servizi * imponibile_tax
        cassa_inps = tot_servizi * imponibile_cassa_inps * aliquota_cassa_inps
        iva = imponibile * aliquota_iva * imponibile_iva
        tot_documento = imponibile + cassa_inps + iva + tot_rimborsi
        ritenuta = 0 if tipologia_cliente == TipologiaCliente.PRIVATO.value else imponibile * aliquota_ritenuta_acconto
        netto_a_pagare = tot_documento - ritenuta

        invoice_data = {
            DBInvoicesColumns.CASSA_INPS.value: cassa_inps,
            DBInvoicesColumns.IMPONIBILE.value: imponibile,
            DBInvoicesColumns.IVA.value: iva,
            DBInvoicesColumns.TOT_DOCUMENTO.value: tot_documento,
            DBInvoicesColumns.RITENUTA.value: ritenuta,
            DBInvoicesColumns.NETTO_A_PAGARE.value: netto_a_pagare
        }
        return invoice_data

    def calcola_derivati_fattura(self, regime_fiscale, tipologia_cliente, tot_servizi, tot_rimborsi, ext_rivalsa_inps):
        """
        Calcola i campi derivati della fattura sulla base del regime fiscale dell'utente e della tipologia di cliente.
        Usa i dati fiscali da self.fiscal_settings.
        """

        if regime_fiscale == RegimeFiscale.ORDINARIO.value:
            settings = self.fiscal_settings.partita_iva_ordinaria

            imponibile = tot_servizi * float(settings.imponibile_irpef)
            cassa_inps = tot_servizi * float(settings.imponibile_cassa_inps) * float(settings.aliquota_cassa_inps)
            iva = imponibile * float(self.fiscal_settings.aliquota_iva.aliquota_iva_ordinaria) * float(settings.imponibile_iva)
            tot_documento = imponibile + cassa_inps + iva + tot_rimborsi

            ritenuta = 0
            if tipologia_cliente != TipologiaCliente.PRIVATO.value:
                ritenuta = imponibile * float(settings.aliquota_ritenuta)

            netto_a_pagare = tot_documento - ritenuta
            rivalsa_inps = 0  # Non prevista nel regime ordinario

        elif regime_fiscale == RegimeFiscale.FORFETTARIO.value:
            settings = self.fiscal_settings.partita_iva_forfettaria

            imponibile = tot_servizi
            cassa_inps = 0
            iva = 0
            ritenuta = 0
            rivalsa_inps = tot_servizi * float(settings.aliquota_rivalsa_inps) if ext_rivalsa_inps != 0 else ext_rivalsa_inps
            tot_documento = imponibile + rivalsa_inps + tot_rimborsi
            netto_a_pagare = tot_documento

        else:
            raise ValueError(f"Regime fiscale non supportato: {regime_fiscale}")

        return {
            DBInvoicesColumns.CASSA_INPS.value: cassa_inps,
            DBInvoicesColumns.IMPONIBILE.value: imponibile,
            DBInvoicesColumns.IVA.value: iva,
            DBInvoicesColumns.TOT_DOCUMENTO.value: tot_documento,
            DBInvoicesColumns.RITENUTA.value: ritenuta,
            DBInvoicesColumns.NETTO_A_PAGARE.value: netto_a_pagare,
            DBInvoicesColumns.RIVALSA_INPS.value: rivalsa_inps
        }

    def calcola_totale_pagamenti_fattura(self, id_invoice):
        payments = self.invoices_query_service.retrieve_invoice_with_payments_map_list(id_invoice)
        tot = 0.0
        tot_1 = 0.0
        tot_2 = 0.0
        tot_3 = 0.0

        for payment in payments:
            if payment[DBPaymentsColumns.PAYMENT_NAME.value] is not None:
                tot = tot + float(payment[DBPaymentsColumns.PAYMENT_AMOUNT.value])
                if payment[DBPaymentsColumns.LINKED_RATA.value] == 1:
                    tot_1 = tot_1 + float(payment[DBPaymentsColumns.PAYMENT_AMOUNT.value])
                elif payment[DBPaymentsColumns.LINKED_RATA.value] == 2:
                    tot_2 = tot_2 + float(payment[DBPaymentsColumns.PAYMENT_AMOUNT.value])
                elif payment[DBPaymentsColumns.LINKED_RATA.value] == 3:
                    tot_3 = tot_3 + float(payment[DBPaymentsColumns.PAYMENT_AMOUNT.value])

        return [tot, tot_1, tot_2, tot_3]

    def calcola_totale_spese_produzione_fattura(self, id_invoice):
        expenses = self.invoices_query_service.retrieve_invoice_with_expenses_map_list(id_invoice)
        tot = 0.0

        for expense in expenses:
            if expense[DBExpensesColumns.NAME.value] is not None:
                tot = tot + float(expense[DBExpensesColumns.TOT_AMOUNT.value])

        return tot

    def select_best_invoicer(self, nuovo_importo: float) -> dict[str, float]:
        """
        Suggerisce quale partita IVA debba emettere una nuova fattura,
        con un bilanciamento migliore tra situazione corrente e obiettivi annuali,
        specialmente per la partita IVA ordinaria.
        """
        # 1. Recupero dati base
        user_list = self.user_query_service.retrieve_users_map_list()
        id_to_last_name = {user[DBUsersColumns.ID.value]: user[DBUsersColumns.LAST_NAME.value] for user in user_list}
        id_to_full_name = {
            user[DBUsersColumns.ID.value]: f"{user[DBUsersColumns.FIRST_NAME.value]} {user[DBUsersColumns.LAST_NAME.value]}"
            for user in user_list
        }
        name_to_id = {v: k for k, v in id_to_last_name.items()}

        # 2. Fatturati e spese correnti
        fatturati = self.user_analyzer_service.retrieve_users_with_tot_fatturato()
        spese = self.user_analyzer_service.retrieve_users_with_tot_spese()

        ordinari = fatturati.get(RegimeFiscale.ORDINARIO.value, {})
        if len(ordinari) != 1:
            raise ValueError("Richiesta esattamente 1 partita IVA ordinaria")

        nome_ordinaria = next(iter(ordinari))
        id_ordinaria = name_to_id[nome_ordinaria]

        # 3. Strutture dati
        piva_forfettarie = {
            name_to_id[nome]: {
                "fatturato": tot,
                "spese_deducibili": spese.get(nome, 0.0)
            }
            for nome, tot in fatturati.get(RegimeFiscale.FORFETTARIO.value, {}).items()
        }

        piva_ordinaria = {
            id_ordinaria: {
                "fatturato": ordinari[nome_ordinaria],
                "spese_deducibili": spese.get(nome_ordinaria, 0.0)
            }
        }

        # 4. Storico fatture e spese
        fatture = self.invoices_query_service.retrieve_invoices_map_list(-1)
        storico_fatture = [{
            "piva": f.get(DBInvoicesColumns.ID_UTENTE.value),
            "data": f.get(DBInvoicesColumns.DATA_CREAZIONE.value),
            "amount": f.get(DBInvoicesColumns.TOT_DOCUMENTO.value)
        } for f in fatture]

        spese_ordinaria_raw = self.user_query_service.retrieve_user_with_deducted_expenses_map_list(id_ordinaria)
        storico_spese_ordinaria = [{
            "data": s.get(DBExpensesColumns.DATE.value),
            "amount": s.get(DBExpensesColumns.TOT_AMOUNT.value)
        } for s in spese_ordinaria_raw]

        # 5. Dati storici annuali
        storico_annuale_fatturato = self.historical_financial_data_settings.revenues
        storico_annuale_spese_ordinaria = self.historical_financial_data_settings.deducted_expenses

        oggi = datetime.today()
        anno_corrente = oggi.year
        mese_corrente = oggi.month

        # 6. Calcolo valori correnti (situazione attuale)
        fatturati_correnti = {}
        for piva, data in {**piva_forfettarie, **piva_ordinaria}.items():
            storico_piva = [f for f in storico_fatture if f["piva"] == piva]
            df = pd.DataFrame(storico_piva)
            if not df.empty:
                df["data"] = pd.to_datetime(df["data"])
                df["anno"] = df["data"].dt.year
                fatturati_correnti[piva] = df[df["anno"] == anno_corrente]["amount"].sum()
            else:
                fatturati_correnti[piva] = 0

        # Spese YTD corrente per ordinaria
        df_spese = pd.DataFrame(storico_spese_ordinaria)
        if not df_spese.empty:
            df_spese["data"] = pd.to_datetime(df_spese["data"])
            df_spese["anno"] = df_spese["data"].dt.year
            spese_correnti_ordinaria = df_spese[df_spese["anno"] == anno_corrente]["amount"].sum()
        else:
            spese_correnti_ordinaria = 0

        # 7. Previsioni semplificate (solo per bilanciamento)
        previsioni = {}
        for piva, data in {**piva_forfettarie, **piva_ordinaria}.items():
            nome = self.user_query_service.id_to_full_name_str(piva)

            # Recupera dati storici se disponibili
            storico_annuale = 0
            count = 0
            for anno, valori in storico_annuale_fatturato.items():
                if int(anno) < anno_corrente and nome in valori:
                    storico_annuale += valori[nome]
                    count += 1

            media_storica = storico_annuale / count if count > 0 else 0
            fatturato_attuale = fatturati_correnti[piva]

            # Peso dinamico: più peso al corrente man mano che avanziamo nell'anno
            peso_corrente = min(0.9, max(0.5, mese_corrente / 12))
            peso_storico = 1 - peso_corrente

            # Previsione conservativa
            previsioni[piva] = (fatturato_attuale * peso_corrente) + (media_storica * peso_storico)

        # Previsione spese ordinaria
        storico_spese = 0
        count = 0
        for anno, valore in storico_annuale_spese_ordinaria.items():
            if int(anno) < anno_corrente:
                storico_spese += valore
                count += 1

        media_spese_storiche = storico_spese / count if count > 0 else 0
        peso_corrente_spese = min(0.9, max(0.5, mese_corrente / 12))
        spese_previste = (spese_correnti_ordinaria * peso_corrente_spese) + (
                    media_spese_storiche * (1 - peso_corrente_spese))

        # 8. Calcolo punteggi integrati
        TARGET_FORFETTARIO = 85000
        MARGINE_SICURO = 2000
        punteggi = {}

        # Soglia per bonus/malus
        SOGLIA_IMPORTO = 5000
        # Fattori aumentati per maggiore impatto
        MALUS_FACTOR_FORFETTARIE = 0.3
        BONUS_FACTOR_ORDINARIA = 0.25

        # Calcola il fatturato totale corrente di tutte le forfettarie
        totale_forfettarie_corrente = sum(fatturati_correnti[piva] for piva in piva_forfettarie)

        # Calcola il fatturato medio corrente delle forfettarie
        if piva_forfettarie:
            media_forfettarie_corrente = totale_forfettarie_corrente / len(piva_forfettarie)
        else:
            media_forfettarie_corrente = 0

        # Punteggi forfettarie
        for piva in piva_forfettarie:
            # Punteggio base basato su distanza dalla soglia
            distanza_soglia = max(0, TARGET_FORFETTARIO - previsioni[piva])

            # Considera l'impatto della nuova fattura
            impatto_nuova_fattura = min(nuovo_importo, distanza_soglia)

            # Differenziale rispetto alla media
            differenziale_media = media_forfettarie_corrente - fatturati_correnti[piva]

            punteggio = (
                                (distanza_soglia * 0.7) +
                                (impatto_nuova_fattura * 0.5) +
                                (max(0, differenziale_media) * 0.4)
                        ) / 1000

            # Applica malus più impattante se l'importo è grande
            if nuovo_importo > SOGLIA_IMPORTO:
                eccesso = nuovo_importo - SOGLIA_IMPORTO
                # Malus proporzionale alla distanza dalla soglia
                fattore_distanza = min(1, distanza_soglia / TARGET_FORFETTARIO)
                malus = eccesso * MALUS_FACTOR_FORFETTARIE * (1 + fattore_distanza) / 500
                punteggio = max(0, punteggio - malus)

            punteggi[piva] = max(0, punteggio)

        # Punteggio ordinaria - RIBILANCIATO
        current_revenue = fatturati_correnti[id_ordinaria]
        current_expenses = spese_correnti_ordinaria
        projected_revenue = previsioni[id_ordinaria]

        # 1. Base score basato sul deficit corrente
        deficit_corrente = max(0, current_expenses - current_revenue)
        base_score = deficit_corrente * 0.8  # 0.8 punti per euro di deficit

        # 2. Score per avvicinamento al margine di sicurezza
        gap_previsto = max(0, projected_revenue - spese_previste)
        avvicinamento_margine = min(nuovo_importo, max(0, MARGINE_SICURO - gap_previsto))
        margine_score = avvicinamento_margine * 0.6  # 0.6 punti per euro che avvicinano al margine

        # 3. Bonus per copertura immediata del deficit
        copertura_immediata = min(nuovo_importo, deficit_corrente)
        copertura_score = copertura_immediata * 1.2  # Bonus più alto per copertura diretta

        # 4. Fattore di urgenza (deficit corrente vs previsione)
        fattore_urgenza = 1 + (deficit_corrente / max(1, current_revenue))

        punteggio_ordinaria = (base_score + margine_score + copertura_score) * fattore_urgenza / 100

        # Applica bonus più impattante se l'importo è grande
        if nuovo_importo > SOGLIA_IMPORTO:
            eccesso = nuovo_importo - SOGLIA_IMPORTO
            # Bonus proporzionale all'urgenza
            bonus = eccesso * BONUS_FACTOR_ORDINARIA * fattore_urgenza / 50
            punteggio_ordinaria += bonus

        # Aggiusta il punteggio per evitare valori estremi
        punteggio_ordinaria = min(100, max(5, punteggio_ordinaria))  # Minimo 5 per essere sempre considerata
        punteggi[id_ordinaria] = punteggio_ordinaria

        # 9. Normalizzazione e ordinamento
        # Calcola il punteggio massimo per normalizzazione
        max_punteggio = max(punteggi.values()) if punteggi else 1

        punteggi_finali = {}
        for piva, score in punteggi.items():
            full_name = id_to_full_name[piva]
            # Normalizza tra 0 e 100 se c'è un punteggio positivo
            punteggi_finali[full_name] = round((score / max_punteggio) * 100, 2) if max_punteggio > 0 else 0

        return dict(sorted(punteggi_finali.items(), key=lambda x: x[1], reverse=True))

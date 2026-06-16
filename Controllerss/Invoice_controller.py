from datetime import datetime

from Model import DatabaseModel
from Gestionale_Enums import*
from QueryServices.Account_query_service import AccountQueryService
from QueryServices.Users_query_service import UserQueryService
from Utils.Validation_utils import ValidationUtils
from Utils.Controller_utils import ControllerUtils

from ConfigManagers import FiscalSettings

from QueryServices.Clients_query_service import ClientQueryService
from QueryServices.Productions_query_service import ProductionQueryService
from QueryServices.Invoices_query_service import InvoiceQueryService

from AnalyzerServices.Invoice_analyzer_service import InvoiceAnalyzerService

class InvoiceController:

    def __init__(self, db_model: DatabaseModel,
                 invoice_analyzer_service: InvoiceAnalyzerService,
                 clients_query_service:ClientQueryService,
                 invoices_query_service:InvoiceQueryService,
                 productions_query_service:ProductionQueryService,
                 user_query_service:UserQueryService,
                 fiscal_settings:FiscalSettings,
                 account_query_service:AccountQueryService):

        """Inizializza il controller con il modello del database"""
        self.clients_query_service:ClientQueryService = clients_query_service
        self.productions_query_service:ProductionQueryService = productions_query_service
        self.invoices_query_service:InvoiceQueryService = invoices_query_service
        self.fiscal_settings:FiscalSettings = fiscal_settings
        self.user_query_service:UserQueryService = user_query_service
        self.account_query_service:AccountQueryService = account_query_service
        self.invoice_analyzer_service: InvoiceAnalyzerService = invoice_analyzer_service
        self.db_model = db_model

    # Chiave transitoria (non colonna DB) usata dal creator per passare
    # l'override "al volo" dei giorni di scadenza della fattura a rata singola.
    OVERRIDE_EXPIRY_DAYS_KEY = "OVERRIDE_EXPIRY_DAYS"

    def _compute_scadenze_slots(self, creation_date, numero_rate_value, override_days=None):
        """Calcola le tre scadenze (slot DB) in base al numero di rate.

        - rata singola: usa l'override "al volo" se presente, altrimenti la
          preferenza ``invoice_expiry_days``; popola solo DATA_SCADENZA_1.
        - 2/3 rate: usa gli offset del piano di rateizzazione configurato;
          le scadenze non pertinenti restano None.
        """
        try:
            num_rate = int(numero_rate_value)
        except (TypeError, ValueError):
            num_rate = 1

        single_days = None
        if num_rate <= 1 and override_days not in (None, ""):
            try:
                single_days = int(override_days)
            except (TypeError, ValueError):
                single_days = None

        offsets = self.fiscal_settings.day_offsets_for(num_rate, single_rate_days=single_days)
        dates = ControllerUtils.calculate_expiration_dates(creation_date, offsets) or []

        slots = [None, None, None]
        for i, d in enumerate(dates[:3]):
            slots[i] = d
        return slots

    def save_invoice(self, invoice_data):
        """
        Gestisce il salvataggio di una fattura, con validazioni di primo livello.
        :param invoice_data: Dizionario contenente i dati della fattura
        :return: Tuple (success, message), dove success è True/False
        """

        # Campi obbligatori (solo quelli modellati tramite entry)
        required_fields = {"NOME CLIENTE", DBInvoicesColumns.NUMERO_FATTURA.value, DBInvoicesColumns.SERVIZI.value, DBInvoicesColumns.RIMBORSI.value}

        # Validazione dei campi obbligatori
        missing_fields = [field for field in required_fields if not invoice_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        # Validazione importi
        servizi = invoice_data.get(DBInvoicesColumns.SERVIZI.value)
        if not ValidationUtils.validate_amount(servizi):
            return False, "L'importo dei servizi non è valido"

        tot_non_ivato = invoice_data.get(DBInvoicesColumns.RIMBORSI.value)
        if not ValidationUtils.validate_amount(tot_non_ivato):
            return False, "L'importo di tot_non_ivato non è valido"

        #prendo i dati della produzione associata
        production_name = invoice_data.get("NOME PRODUZIONE") #definito nella view (è un po' una porcata)
        if production_name:
            production = self.productions_query_service.retrieve_production_map_by_name(production_name)
            if production:
                production_id = production[DBProductionsColumns.ID.value]
            else:
                return False, "Aggiungere una produzione prima di emettere questa fattura"

        #prendo i dati necessari dell'utente
        nome_utente = invoice_data.get("NOME UTENTE").split(" ")
        utente = self.user_query_service.retrieve_user_map_by_fullname(nome_utente[0], nome_utente[1])
        id_utente = utente[DBUsersColumns.ID.value]
        regime_fiscale = utente[DBUsersColumns.REGIME_FISCALE.value]


        #prendo i dati necessari del cliente
        nome_cliente = invoice_data.get("NOME CLIENTE")
        cliente_list = self.clients_query_service.retrieve_client_by_name(nome_cliente)
        cliente_map = self.clients_query_service.retrieve_client_map_by_id(cliente_list[0])
        id_cliente = cliente_map[DBClientsColumns.ID.value]
        tipologia_cliente = cliente_map[DBClientsColumns.TIPOLOGIA.value]

        #prendo i dati necessari al conto
        nome_conto = invoice_data.get("CONTO")
        conto = self.account_query_service.retrieve_account_map_by_name(nome_conto)
        if conto:
            conto_id = conto[DBAccountsColumns.ID.value]

        totale_servizi = invoice_data.get(DBInvoicesColumns.SERVIZI.value)
        totale_rimborsi = invoice_data.get(DBInvoicesColumns.RIMBORSI.value)

        #se la fattura è una nota di credito prendo l'ID della fattura a cui è collegata
        id_linked_invoice = None
        if invoice_data.get(DBInvoicesColumns.TIPO.value) == TipologiaFattura.NOTA_DI_CREDITO.value and invoice_data.get(DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value):
            id_linked_invoice = invoice_data.get(DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value)


        invoice_data_prepared = {}


        # Preparazione dei dati per il salvataggio
        if regime_fiscale == RegimeFiscale.ORDINARIO.value:

            #prendo le aliquote e gli imponibili per il calcolo degli importi derivati della fattura
            aliquota_cassa_inps = self.fiscal_settings.partita_iva_ordinaria.aliquota_cassa_inps
            aliquota_ritenuta_acconto = self.fiscal_settings.partita_iva_ordinaria.aliquota_ritenuta
            aliquota_iva = self.fiscal_settings.aliquota_iva.aliquota_iva_ordinaria
            imponibile_tax = self.fiscal_settings.partita_iva_ordinaria.imponibile_irpef
            imponibile_cassa_inps = self.fiscal_settings.partita_iva_ordinaria.imponibile_cassa_inps
            imponibile_iva = self.fiscal_settings.partita_iva_ordinaria.imponibile_iva

            #calcolo importi derivati
            importi_derivati_ordinaria = self.invoice_analyzer_service.calcola_derivati_fattura_ordinaria(
                float(aliquota_cassa_inps),
                float(aliquota_ritenuta_acconto),
                float(aliquota_iva),
                float(imponibile_tax),
                float(imponibile_cassa_inps),
                float(imponibile_iva),
                tipologia_cliente,
                float(totale_servizi),
                float(totale_rimborsi)
            )

            #riempio i dati da passare al model
            _scad1, _scad2, _scad3 = self._compute_scadenze_slots(
                invoice_data.get(DBInvoicesColumns.DATA_CREAZIONE.value),
                invoice_data.get(DBInvoicesColumns.NUMERO_RATE.value),
                override_days=invoice_data.get(self.OVERRIDE_EXPIRY_DAYS_KEY),
            )
            invoice_data_prepared = {
                DBInvoicesColumns.NUMERO_FATTURA.value : invoice_data.get(DBInvoicesColumns.NUMERO_FATTURA.value),  # view
                DBInvoicesColumns.DATA_CREAZIONE.value : invoice_data.get(DBInvoicesColumns.DATA_CREAZIONE.value),  # view
                DBInvoicesColumns.DATA_SCADENZA_1.value : _scad1,
                DBInvoicesColumns.DATA_SCADENZA_2.value : _scad2,
                DBInvoicesColumns.DATA_SCADENZA_3.value : _scad3,
                DBInvoicesColumns.ID_UTENTE.value : id_utente,  # controller(view)
                DBInvoicesColumns.ID_CLIENTE.value : id_cliente,  # controller(view)
                DBInvoicesColumns.ID_CONTO.value : conto_id,
                DBInvoicesColumns.NOTE.value : invoice_data.get(DBInvoicesColumns.NOTE.value),  # view
                DBInvoicesColumns.SERVIZI.value : totale_servizi,  # view (comprensivo di rivalsa)
                DBInvoicesColumns.CASSA_INPS.value : importi_derivati_ordinaria[DBInvoicesColumns.CASSA_INPS.value],  # controller -> servizi*coeff redditività*aliquota INPS
                DBInvoicesColumns.IMPONIBILE.value : importi_derivati_ordinaria[DBInvoicesColumns.IMPONIBILE.value],  # controller -> servizi*coeff redditività
                DBInvoicesColumns.IVA.value : importi_derivati_ordinaria[DBInvoicesColumns.IVA.value],  # controller = 0
                DBInvoicesColumns.RIMBORSI.value : totale_rimborsi,  # view
                DBInvoicesColumns.TOT_DOCUMENTO.value : importi_derivati_ordinaria[DBInvoicesColumns.TOT_DOCUMENTO.value],
                DBInvoicesColumns.RITENUTA.value : importi_derivati_ordinaria[DBInvoicesColumns.RITENUTA.value],  # controller = 0
                DBInvoicesColumns.RIVALSA_INPS.value: 0,
                DBInvoicesColumns.NETTO_A_PAGARE.value : importi_derivati_ordinaria[DBInvoicesColumns.NETTO_A_PAGARE.value],  # controller = 0
                DBInvoicesColumns.STATUS.value : "",  # eccezione manuale: STORNATA scritto solo via storna_invoice
                DBInvoicesColumns.METODO_PAGAMENTO.value : invoice_data.get(DBInvoicesColumns.METODO_PAGAMENTO.value),  # view
                DBInvoicesColumns.NUMERO_RATE.value : invoice_data.get(DBInvoicesColumns.NUMERO_RATE.value),  # view
                DBInvoicesColumns.TIPO.value : invoice_data.get(DBInvoicesColumns.TIPO.value),  # se è nota di credito #view
                DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value : invoice_data.get(DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value) if invoice_data.get(DBInvoicesColumns.TIPO.value) == TipologiaFattura.NOTA_DI_CREDITO.value else None,  # view (a comparsa)
                DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value : production_id
            }
        elif regime_fiscale == RegimeFiscale.FORFETTARIO.value:
            tot_lordo = float(totale_servizi) + float(invoice_data.get(DBInvoicesColumns.RIMBORSI.value)) + float(invoice_data.get(DBInvoicesColumns.RIVALSA_INPS.value))
            _scad1, _scad2, _scad3 = self._compute_scadenze_slots(
                invoice_data.get(DBInvoicesColumns.DATA_CREAZIONE.value),
                invoice_data.get(DBInvoicesColumns.NUMERO_RATE.value),
                override_days=invoice_data.get(self.OVERRIDE_EXPIRY_DAYS_KEY),
            )
            invoice_data_prepared = {
                DBInvoicesColumns.NUMERO_FATTURA.value: invoice_data.get(DBInvoicesColumns.NUMERO_FATTURA.value),  # view
                DBInvoicesColumns.DATA_CREAZIONE.value: invoice_data.get(DBInvoicesColumns.DATA_CREAZIONE.value),  # view
                DBInvoicesColumns.DATA_SCADENZA_1.value: _scad1,
                DBInvoicesColumns.DATA_SCADENZA_2.value: _scad2,
                DBInvoicesColumns.DATA_SCADENZA_3.value: _scad3,
                DBInvoicesColumns.ID_UTENTE.value: id_utente,  # controller(view)
                DBInvoicesColumns.ID_CLIENTE.value: id_cliente,  # controller(view)
                DBInvoicesColumns.ID_CONTO.value: conto_id,
                DBInvoicesColumns.NOTE.value: invoice_data.get(DBInvoicesColumns.NOTE.value),  # view
                DBInvoicesColumns.SERVIZI.value: totale_servizi,  # view (comprensivo di rivalsa)
                DBInvoicesColumns.CASSA_INPS.value: 0,
                DBInvoicesColumns.IMPONIBILE.value: totale_servizi,
                DBInvoicesColumns.IVA.value: 0,  # controller = 0
                DBInvoicesColumns.RIMBORSI.value: totale_rimborsi,  # view
                DBInvoicesColumns.RIVALSA_INPS.value : invoice_data.get(DBInvoicesColumns.RIVALSA_INPS.value),
                DBInvoicesColumns.TOT_DOCUMENTO.value: tot_lordo,
                DBInvoicesColumns.RITENUTA.value: 0,
                DBInvoicesColumns.NETTO_A_PAGARE.value: tot_lordo,
                DBInvoicesColumns.STATUS.value: "",  # eccezione manuale: STORNATA scritto solo via storna_invoice
                DBInvoicesColumns.METODO_PAGAMENTO.value: invoice_data.get(DBInvoicesColumns.METODO_PAGAMENTO.value),
                DBInvoicesColumns.NUMERO_RATE.value: invoice_data.get(DBInvoicesColumns.NUMERO_RATE.value),  # view
                DBInvoicesColumns.TIPO.value: invoice_data.get(DBInvoicesColumns.TIPO.value),  # se è nota di credito #view
                DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value: invoice_data.get(DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value) if invoice_data.get(DBInvoicesColumns.TIPO.value) == TipologiaFattura.NOTA_DI_CREDITO.value else None,  # view (a comparsa)
                DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value: production_id

            }

        # Salvataggio nel DB
        try:
            self.db_model.add_invoice(**invoice_data_prepared)
            # Lo stato EMESSA/SCADUTA/SALDATA/PAGATA/PARZIALMENTE_SALDATA/CRITICA
            # e' calcolato on-the-fly (Utils.Invoice_status_utils.compute_invoice_status),
            # quindi non serve aggiornare nulla nel DB. Resta scritto solo STORNATA
            # per la linked invoice in caso di nota di credito.
            if id_linked_invoice:
                self.db_model.modify_invoice_datum(id_linked_invoice, DBInvoicesColumns.STATUS.value, InvoiceSatus.STORNATA.value)
            return True, "Fattura salvata con successo!"
        except Exception as e:
            return False, f"Errore durante il salvataggio: {str(e)}"

    def update_invoice(self, invoice_id, invoice_data):

        invoice = self.invoices_query_service.retrieve_invoice_map_by_id(invoice_id)

        # Campi obbligatori (solo quelli modellati tramite entry)
        required_fields = {DBInvoicesColumns.SERVIZI.value, DBInvoicesColumns.RIMBORSI.value}

        # Validazione dei campi obbligatori
        missing_fields = [field for field in required_fields if not invoice_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        # Validazione importi
        servizi = invoice_data.get(DBInvoicesColumns.SERVIZI.value)
        if not ValidationUtils.validate_amount(servizi):
            return False, "L'importo dei servizi non è valido"

        tot_non_ivato = invoice_data.get(DBInvoicesColumns.RIMBORSI.value)
        if not ValidationUtils.validate_amount(tot_non_ivato):
            return False, "L'importo dei rimborsi non è valido"

        invoice_data_prepared = {}
        for col in DBInvoicesColumns:
            try:
                invoice_data_prepared[col.value] = float(invoice_data.get(col.value))
            except Exception as e:
                invoice_data_prepared[col.value] = invoice_data.get(col.value)


        #sistemazione dei dati prima di pushare verso db
        for key, data in invoice_data.items():
            if data is None:
                invoice_data_prepared.pop(key)
        invoice_data_prepared.pop(DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value) #da valutare se reintrodurla
        invoice_data_prepared.pop(DBInvoicesColumns.ID.value)
        invoice_data_prepared.pop(DBInvoicesColumns.CREATED_AT.value)
        invoice_data_prepared.pop(DBInvoicesColumns.TIPO.value)
        invoice_data_prepared.pop(DBInvoicesColumns.STATUS.value)
        invoice_data_prepared.pop(DBInvoicesColumns.ID_UTENTE.value)
        invoice_data_prepared.pop(DBInvoicesColumns.NUMERO_FATTURA.value)

        invoice_data_prepared[DBInvoicesColumns.CREATED_AT.value] = invoice[DBInvoicesColumns.CREATED_AT.value]

        invoice_data_prepared[DBInvoicesColumns.UPDATED_AT.value] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            # Invoca il metodo del model per aggiornare l'utente
            self.db_model.update_invoice(invoice_id, **invoice_data_prepared)
            return True, "Fattura aggiornata con successo!"

        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento della fattura: {str(e)}"

    def storna_invoice(self, invoice_id, invoice_data):
        # Campi obbligatori (solo quelli modellati tramite entry)
        required_fields = {DBInvoicesColumns.STATUS.value}

        # Validazione dei campi obbligatori
        missing_fields = [field for field in required_fields if not invoice_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        invoice_data_prepared = invoice_data
        invoice_data_prepared[DBInvoicesColumns.UPDATED_AT.value] = datetime.now().replace(microsecond=0)

        try:
            # Invoca il metodo del model per aggiornare l'utente
            self.db_model.update_invoice(invoice_id, **invoice_data_prepared)
            return True, "Fattura aggiornata con successo!"

        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento della fattura: {str(e)}"

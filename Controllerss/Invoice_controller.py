from datetime import datetime

from Model import DatabaseModel
from Gestionale_Enums import*
from Utils.Validation_utils import ValidationUtils
from Utils.Controller_utils import ControllerUtils

from Config import FiscalSettings

from Controllers import UserController, AccountController
from QueryServices.Clients_query_service import ClientQueryService
from QueryServices.Productions_query_service import ProductionQueryService
from QueryServices.Invoices_query_service import InvoiceQueryService

from Analyzers.Invoice_analyzer_service import InvoiceAnalyzerService

class InvoiceController:

    def __init__(self, db_model: DatabaseModel,
                 invoice_analyzer_service: InvoiceAnalyzerService,
                 clients_query_service:ClientQueryService,
                 invoices_query_service:InvoiceQueryService,
                 productions_query_service:ProductionQueryService,
                 user_controller:UserController,
                 fiscal_settings:FiscalSettings,
                 account_controller:AccountController):

        """Inizializza il controller con il modello del database"""
        self.clients_query_service:ClientQueryService = clients_query_service
        self.productions_query_service:ProductionQueryService = productions_query_service
        self.invoices_query_service:InvoiceQueryService = invoices_query_service
        self.fiscal_settings:FiscalSettings = fiscal_settings
        self.user_controller:UserController = user_controller
        self.account_controller:AccountController = account_controller
        self.invoice_analyzer_service: InvoiceAnalyzerService = invoice_analyzer_service
        self.db_model = db_model

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
        utente = self.user_controller.retrieve_user_map_by_fullname(nome_utente[0], nome_utente[1])
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
        conto = self.account_controller.retrieve_account_map_by_name(nome_conto)
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
            invoice_data_prepared = {
                DBInvoicesColumns.NUMERO_FATTURA.value : invoice_data.get(DBInvoicesColumns.NUMERO_FATTURA.value),  # view
                DBInvoicesColumns.DATA_CREAZIONE.value : invoice_data.get(DBInvoicesColumns.DATA_CREAZIONE.value),  # view
                DBInvoicesColumns.DATA_SCADENZA_1.value : ControllerUtils.calculate_three_expiration_dates(invoice_data.get(DBInvoicesColumns.DATA_CREAZIONE.value))[0],
                DBInvoicesColumns.DATA_SCADENZA_2.value : ControllerUtils.calculate_three_expiration_dates(invoice_data.get(DBInvoicesColumns.DATA_CREAZIONE.value))[1] if invoice_data.get(DBInvoicesColumns.NUMERO_RATE.value) == Rateizzazione.TRE.value else None,
                DBInvoicesColumns.DATA_SCADENZA_3.value : ControllerUtils.calculate_three_expiration_dates(invoice_data.get(DBInvoicesColumns.DATA_CREAZIONE.value))[2] if invoice_data.get(DBInvoicesColumns.NUMERO_RATE.value) == Rateizzazione.TRE.value else None,
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
                DBInvoicesColumns.STATUS.value : InvoiceRateizzSatus.EMESSA.value if invoice_data.get(DBInvoicesColumns.NUMERO_RATE.value) == Rateizzazione.TRE.value else InvoiceSatus.EMESSA.value, # controller -> default: emessa
                DBInvoicesColumns.METODO_PAGAMENTO.value : invoice_data.get(DBInvoicesColumns.METODO_PAGAMENTO.value),  # view
                DBInvoicesColumns.NUMERO_RATE.value : invoice_data.get(DBInvoicesColumns.NUMERO_RATE.value),  # view
                DBInvoicesColumns.TIPO.value : invoice_data.get(DBInvoicesColumns.TIPO.value),  # se è nota di credito #view
                DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value : invoice_data.get(DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value) if invoice_data.get(DBInvoicesColumns.TIPO.value) == TipologiaFattura.NOTA_DI_CREDITO.value else None,  # view (a comparsa)
                DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value : production_id
            }
        elif regime_fiscale == RegimeFiscale.FORFETTARIO.value:
            tot_lordo = float(totale_servizi) + float(invoice_data.get(DBInvoicesColumns.RIMBORSI.value)) + float(invoice_data.get(DBInvoicesColumns.RIVALSA_INPS.value))
            invoice_data_prepared = {
                DBInvoicesColumns.NUMERO_FATTURA.value: invoice_data.get(DBInvoicesColumns.NUMERO_FATTURA.value),  # view
                DBInvoicesColumns.DATA_CREAZIONE.value: invoice_data.get(DBInvoicesColumns.DATA_CREAZIONE.value),  # view
                DBInvoicesColumns.DATA_SCADENZA_1.value: ControllerUtils.calculate_three_expiration_dates(invoice_data.get(DBInvoicesColumns.DATA_CREAZIONE.value))[0],
                DBInvoicesColumns.DATA_SCADENZA_2.value: ControllerUtils.calculate_three_expiration_dates(invoice_data.get(DBInvoicesColumns.DATA_CREAZIONE.value))[1] if invoice_data.get(DBInvoicesColumns.NUMERO_RATE.value) == Rateizzazione.TRE.value else None,
                DBInvoicesColumns.DATA_SCADENZA_3.value: ControllerUtils.calculate_three_expiration_dates(invoice_data.get(DBInvoicesColumns.DATA_CREAZIONE.value))[2] if invoice_data.get(DBInvoicesColumns.NUMERO_RATE.value) == Rateizzazione.TRE.value else None,
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
                DBInvoicesColumns.STATUS.value: InvoiceRateizzSatus.EMESSA.value if invoice_data.get(DBInvoicesColumns.NUMERO_RATE.value) == Rateizzazione.TRE.value else InvoiceSatus.EMESSA.value,
                DBInvoicesColumns.METODO_PAGAMENTO.value: invoice_data.get(DBInvoicesColumns.METODO_PAGAMENTO.value),
                DBInvoicesColumns.NUMERO_RATE.value: invoice_data.get(DBInvoicesColumns.NUMERO_RATE.value),  # view
                DBInvoicesColumns.TIPO.value: invoice_data.get(DBInvoicesColumns.TIPO.value),  # se è nota di credito #view
                DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value: invoice_data.get(DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value) if invoice_data.get(DBInvoicesColumns.TIPO.value) == TipologiaFattura.NOTA_DI_CREDITO.value else None,  # view (a comparsa)
                DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value: production_id

            }

        # Salvataggio nel DB
        try:
            self.db_model.add_invoice(**invoice_data_prepared)
            self.update_stato_fatture() #aggiorno lo stato in funzione della data di oggi e dei pagamenti associati alla fattura
            if id_linked_invoice:
                self.db_model.modify_invoice_datum(id_linked_invoice, DBInvoicesColumns.STATUS.value, InvoiceSatus.STORNATA.value)
            #self.update_invoices_list()
            #self.update_aggregated_data()
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

    def update_stato_fatture(self, year: int = None):
        """
        Aggiorna lo stato di tutte le fatture nel database in base ai dati correnti,
        utilizzando il nuovo enum InvoiceRateizzSatus e sfruttando i dati dei pagamenti
        ottenuti dal join tra invoices e payments.

        Per fatture con 1 rata:
          - Se esiste un pagamento associato (con LINKED_RATA == 1) → PAGATA
          - Se non esiste pagamento e la scadenza (DATA_SCADENZA_1) è passata → SCADUTA
          - Altrimenti → EMESSA

        Per fatture con 3 rate:
          - Se tutte le 3 rate sono pagate → PAGATA
          - Se nessuna rata è pagata:
                * Se tutte le scadenze sono passate → SCADUTA
                * Se almeno una rata non pagata è scaduta (ma non tutte) → CRITICA
                * Altrimenti → EMESSA
          - Se alcune rate sono pagate (1 o 2):
                * Se almeno una rata ancora non pagata è scaduta → CRITICA
                * Altrimenti → PARZIALMENTE_SALDATA

        Viene stampato a console il feedback per ogni fattura e un riepilogo finale.
        """
        # Recupera i dati dal join tra invoices e payments
        rows = self.db_model.fetch_invoices_with_payments()
        oggi = datetime.today().date()
        num_invoice_cols = len(DBInvoicesColumns)

        # Estrai solo la parte fatture (senza pagamenti) per il filtraggio
        invoice_maps = [
            ValidationUtils._row_to_map(row[0:num_invoice_cols], DBInvoicesColumns)
            for row in rows
        ]

        # Applica il filtro utilizzando ControllerUtils
        filtered_invoice_maps = ControllerUtils.filter_invoices(
            invoice_maps,
            self.db_model,
            year=year
        )

        # Crea un set con gli ID delle fatture filtrate
        filtered_ids = {
            inv[DBInvoicesColumns.ID.value]
            for inv in filtered_invoice_maps
        }

        # Filtra le righe originali mantenendo solo quelle delle fatture filtrate
        filtered_rows = [row for row in rows if row[0] in filtered_ids]

        # Raggruppa i record per invoice_id
        grouped = {}
        for row in filtered_rows:
            invoice_id = row[0]
            if invoice_id not in grouped:
                grouped[invoice_id] = {
                    "invoice_raw": row[0:num_invoice_cols],
                    "payments": []
                }
            payment_raw = row[num_invoice_cols:]
            if payment_raw and payment_raw[0] is not None:
                grouped[invoice_id]["payments"].append(payment_raw)

        # Converte ogni gruppo in una mappa
        all_invoice_maps = {}
        for inv_id, data in grouped.items():
            inv_map = ValidationUtils._row_to_map(data["invoice_raw"], DBInvoicesColumns)
            inv_map["payments"] = data["payments"]
            all_invoice_maps[inv_id] = inv_map

        # Filtra ulteriormente rimuovendo note di credito e fatture stornate
        filtered_invoices = ControllerUtils.clear_invoices_list_from_NDC_and_stornate(
            list(all_invoice_maps.values())
        )

        updates = 0
        total = len(filtered_invoices)
        payment_cols = [col.value for col in DBPaymentsColumns]

        for invoice in filtered_invoices:
            invoice_id = invoice[DBInvoicesColumns.ID.value]
            stato_attuale = invoice[DBInvoicesColumns.STATUS.value]
            num_rate = int(invoice[DBInvoicesColumns.NUMERO_RATE.value])
            nuovo_stato = stato_attuale  # default

            # Salta note di credito (già gestito in clear_invoices_list... ma doppio check)
            if stato_attuale == InvoiceSatus.STORNATA.value:
                print(f"Fattura {invoice_id} non aggiornata poichè è nota di credito")
                continue

            # Converti i pagamenti in mappe
            payments = invoice.get("payments", [])
            payments_maps = []
            for p in payments:
                if p and p[0] is not None:
                    payments_maps.append(dict(zip(payment_cols, p)))

            # Logica di aggiornamento stato (invariata)
            if num_rate == int(Rateizzazione.UNA.value):
                paid = any(int(pm[DBPaymentsColumns.LINKED_RATA.value]) == 1 for pm in payments_maps)
                scadenza = ControllerUtils.parse_date(invoice[DBInvoicesColumns.DATA_SCADENZA_1.value])
                if paid:
                    nuovo_stato = InvoiceRateizzSatus.PAGATA.value
                else:
                    if scadenza is not None and oggi > scadenza:
                        nuovo_stato = InvoiceRateizzSatus.SCADUTA.value
                    else:
                        nuovo_stato = InvoiceRateizzSatus.EMESSA.value

            elif num_rate == int(Rateizzazione.TRE.value):
                pagamenti = []
                for rata in [1, 2, 3]:
                    payment = next((pm for pm in payments_maps if int(pm[DBPaymentsColumns.LINKED_RATA.value]) == rata),
                                   None)
                    pagamenti.append(
                        ControllerUtils.parse_date(payment[DBPaymentsColumns.PAYMENT_DATE.value]) if payment else None)

                scadenze = [
                    ControllerUtils.parse_date(invoice[DBInvoicesColumns.DATA_SCADENZA_1.value]),
                    ControllerUtils.parse_date(invoice[DBInvoicesColumns.DATA_SCADENZA_2.value]),
                    ControllerUtils.parse_date(invoice[DBInvoicesColumns.DATA_SCADENZA_3.value])
                ]

                count_paid = sum(1 for p in pagamenti if p is not None)
                count_overdue = sum(
                    1 for i in range(3) if pagamenti[i] is None and scadenze[i] is not None and oggi > scadenze[i]
                )

                if count_paid == 3:
                    nuovo_stato = InvoiceRateizzSatus.PAGATA.value
                elif count_paid == 0:
                    if all(s is not None and oggi > s for s in scadenze):
                        nuovo_stato = InvoiceRateizzSatus.SCADUTA.value
                    elif count_overdue > 0 and count_overdue < 3:
                        nuovo_stato = InvoiceRateizzSatus.CRITICA.value
                    else:
                        nuovo_stato = InvoiceRateizzSatus.EMESSA.value
                else:
                    if count_overdue > 0:
                        nuovo_stato = InvoiceRateizzSatus.CRITICA.value
                    else:
                        nuovo_stato = InvoiceRateizzSatus.PARZIALMENTE_SALDATA.value
            else:
                print(
                    f"Invoice id {invoice_id}: numero rate non riconosciuto (valore: {num_rate}). Nessuna azione effettuata.")
                continue

            # Aggiornamento se lo stato è cambiato
            if nuovo_stato != stato_attuale:
                self.db_model.modify_invoice_datum(invoice_id, DBInvoicesColumns.STATUS.value, nuovo_stato)
                print(f"Invoice id {invoice_id}: stato aggiornato da '{stato_attuale}' a '{nuovo_stato}'.")
                updates += 1
            else:
                print(f"Invoice id {invoice_id}: nessun cambiamento (stato corrente: '{stato_attuale}').")

        print(f"Aggiornamento completato: {updates} su {total} fatture aggiornate.")

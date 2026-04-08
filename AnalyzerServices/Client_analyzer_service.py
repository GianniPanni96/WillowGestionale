from datetime import datetime

from Gestionale_Enums import *
from Controllers import ControllerUtils

from Model import DatabaseModel
from QueryServices.Clients_query_service import ClientQueryService


class ClientAnalyzerService:
    """
    Servizio applicativo che calcola gli aggregati economici dei clienti.

    Questa classe lavora sopra ``ClientQueryService`` e ``DatabaseModel``:
    non costruisce interfacce, ma espone metriche pronte per view e report,
    mantenendo fuori dalla UI la logica di analisi.
    """

    def __init__(self, client_query_service: ClientQueryService, database_model: DatabaseModel):
        """Memorizza i servizi necessari per query e calcoli aggregati."""
        self.client_query_service: ClientQueryService = client_query_service
        self.db_model: DatabaseModel = database_model

    def calcola_tot_entrate_cliente(self, client_id, include_unpaid_invoices: bool = True, year: int = None):
        """
        Restituisce il totale fatturato del cliente nel periodo richiesto.

        Le fatture vengono recuperate tramite ``ClientQueryService`` e poi
        sommate escludendo note di credito e documenti stornati secondo la
        logica attuale del progetto.
        """
        client_with_invoices = self.client_query_service.retrieve_client_with_invoices_map_list(
            client_id,
            include_unpaid_invoices=include_unpaid_invoices,
            year=year
        )
        tot = 0.0
        for row in client_with_invoices:
            if (row[DBInvoicesColumns.TIPO.value] != TipologiaFattura.NOTA_DI_CREDITO.value or
                    row[DBInvoicesColumns.STATUS.value] != InvoiceSatus.STORNATA.value):
                if row[DBInvoicesColumns.TOT_DOCUMENTO.value] is not None:
                    tot += float(row[DBInvoicesColumns.TOT_DOCUMENTO.value])

        return tot

    def calcola_numero_fatture_cliente(self, client_id, include_unpaid_invoices: bool = True, year: int = None):
        """Conta quante fatture valide risultano associate al cliente."""
        client_with_invoices = self.client_query_service.retrieve_client_with_invoices_map_list(
            client_id,
            include_unpaid_invoices=include_unpaid_invoices,
            year=year
        )
        tot = 0
        for row in client_with_invoices:
            valid_row = row[DBInvoicesColumns.ID_CLIENTE.value] is not None
            if (row[DBInvoicesColumns.TIPO.value] != TipologiaFattura.NOTA_DI_CREDITO.value and valid_row or
                    row[DBInvoicesColumns.STATUS.value] != InvoiceSatus.STORNATA.value and valid_row):
                tot += 1

        return tot

    def calcola_media_fatture_cliente(self, client_id, include_unpaid_invoices: bool = True, year: int = None):
        """Calcola il valore medio delle fatture del cliente."""
        numero = self.calcola_numero_fatture_cliente(
            client_id,
            include_unpaid_invoices=include_unpaid_invoices,
            year=year
        )
        tot = self.calcola_tot_entrate_cliente(
            client_id,
            include_unpaid_invoices=include_unpaid_invoices,
            year=year
        )

        return tot / numero if numero > 0 else 0

    def calcola_totale_crediti_cliente(self, client_id, include_unpaid_invoices: bool = True, year: int = None):
        """Somma i crediti ancora aperti associati al cliente."""
        outstanding = self.db_model.fetch_outstanding_by_client(client_id)
        return sum(outstanding.values())

    def calcola_pagam_orario_medio_cliente(self, client_id, include_unpaid_invoices: bool = True, year: int = None):
        """
        Calcola il pagamento orario medio del cliente.

        Il rapporto e' dato da ``totale fatturato / totale ore prodotte`` sulle
        fatture che risultano collegate a produzioni.
        """
        invoices_with_prod = self.db_model.fetch_invoices_with_productions()
        all_columns = list(DBInvoicesColumns) + list(DBProductionsColumns)

        invoices_with_prod_maps = [ControllerUtils.row_to_map(row, all_columns) for row in invoices_with_prod]
        invoices_with_prod_maps = ControllerUtils.clear_invoices_list_from_NDC_and_stornate(
            invoices_with_prod_maps
        )

        filtered_maps = {}

        if invoices_with_prod_maps:
            filtered_maps = ControllerUtils.filter_invoices(
                invoices=invoices_with_prod_maps,
                db_model=self.db_model,
                year=year,
                include_unpaid_invoices=include_unpaid_invoices
            )

        tot_pagam = 0.0
        tot_orario = 0.0
        for invoice in filtered_maps:
            if invoice[DBInvoicesColumns.ID_CLIENTE.value] == client_id:
                # La logica esistente somma l'importo della fattura per ogni produzione
                # collegata. Il commento viene mantenuto per evidenziare il tradeoff.
                tot_pagam += float(invoice[DBInvoicesColumns.TOT_DOCUMENTO.value])
                tot_orario += float(invoice[DBProductionsColumns.HOURS.value])

        return tot_pagam / tot_orario if tot_orario > 0 else -1

    def calcola_ritardo_medio_cliente(
            self,
            client_id,
            include_unpaid_invoices: bool = True,
            year: int = None
    ):
        """
        Calcola il ritardo medio in giorni sulle rate del cliente.

        La funzione confronta, rata per rata, la data di scadenza della fattura
        con la data del pagamento collegato. Se la rata non e' ancora pagata e
        la scadenza e' superata, il ritardo viene calcolato rispetto ad oggi.
        """
        invoice_rows = self.db_model.fetch_invoices_by_client_id(client_id)
        invoices_maps = [
            ControllerUtils.row_to_map(row, DBInvoicesColumns)
            for row in invoice_rows
        ]
        invoices_maps = ControllerUtils.clear_invoices_list_from_NDC_and_stornate(
            invoices_maps
        )

        invoices_maps = ControllerUtils.filter_invoices(
            invoices_maps,
            self.db_model,
            year=year,
            include_unpaid_invoices=include_unpaid_invoices
        )

        if not invoices_maps:
            return 0

        payment_rows = self.db_model.fetch_payments_with_invoice_for_client(client_id)

        payments = []
        payments_dict = {}

        for row in payment_rows:
            payment_data = row[:len(DBPaymentsColumns)]
            payment_map = ControllerUtils.row_to_map(payment_data, DBPaymentsColumns)
            payments.append(payment_map)

        payments = ControllerUtils.filter_payments(
            payments,
            self.db_model,
            year=year,
            include_unpaid_invoice_payments=include_unpaid_invoices
        )

        # Riorganizza i pagamenti in una struttura piu' comoda:
        # {invoice_id: {numero_rata: payment_map}}.
        for row in payment_rows:
            payment_data = row[:len(DBPaymentsColumns)]
            payment_map = ControllerUtils.row_to_map(payment_data, DBPaymentsColumns)

            if payment_map not in payments:
                continue

            invoice_data = row[len(DBPaymentsColumns):len(DBPaymentsColumns) + len(DBInvoicesColumns)]
            invoice_map = ControllerUtils.row_to_map(invoice_data, DBInvoicesColumns)

            invoice_id = invoice_map[DBInvoicesColumns.ID.value]
            rata = payment_map[DBPaymentsColumns.LINKED_RATA.value]

            payments_dict.setdefault(invoice_id, {})[rata] = payment_map

        totale_ritardo = 0
        conteggio_rate_in_ritardo = 0
        oggi = datetime.today()
        date_format = "%Y-%m-%d"

        for invoice in invoices_maps:
            num_rate = invoice.get(DBInvoicesColumns.NUMERO_RATE.value) or 1
            invoice_id = invoice[DBInvoicesColumns.ID.value]

            for rata in range(1, num_rate + 1):
                due_date_str = invoice.get(
                    getattr(DBInvoicesColumns, f"DATA_SCADENZA_{rata}").value,
                    None
                )
                if not due_date_str:
                    continue

                try:
                    due_date = datetime.strptime(due_date_str, date_format)
                except ValueError:
                    continue

                payment = payments_dict.get(invoice_id, {}).get(rata)
                ritardo = 0
                in_ritardo = False

                if payment:
                    try:
                        payment_date = datetime.strptime(
                            payment[DBPaymentsColumns.PAYMENT_DATE.value],
                            date_format
                        )
                        if payment_date > due_date:
                            ritardo = (payment_date - due_date).days
                            in_ritardo = True
                    except ValueError:
                        pass
                else:
                    if oggi > due_date:
                        ritardo = (oggi - due_date).days
                        in_ritardo = True

                if in_ritardo:
                    totale_ritardo += ritardo
                    conteggio_rate_in_ritardo += 1

        return totale_ritardo / conteggio_rate_in_ritardo if conteggio_rate_in_ritardo else 0

    def calcola_totale_ritardi_cliente(
            self,
            client_id,
            include_unpaid_invoices: bool = True,
            year: int = None
    ):
        """
        Calcola il ritardo totale, in giorni, accumulato dal cliente.

        A differenza del metodo della media, qui ogni rata in ritardo contribuisce
        con il proprio numero di giorni al totale finale.
        """
        invoice_rows = self.db_model.fetch_invoices_by_client_id(client_id)
        invoices_maps = [
            ControllerUtils.row_to_map(row, DBInvoicesColumns)
            for row in invoice_rows
        ]
        invoices_maps = ControllerUtils.clear_invoices_list_from_NDC_and_stornate(
            invoices_maps
        )

        invoices_maps = ControllerUtils.filter_invoices(
            invoices_maps,
            self.db_model,
            year=year,
            include_unpaid_invoices=include_unpaid_invoices
        )

        if not invoices_maps:
            return 0

        payment_rows = self.db_model.fetch_payments_with_invoice_for_client(client_id)

        payments = []
        payments_dict = {}

        for row in payment_rows:
            payment_data = row[:len(DBPaymentsColumns)]
            payment_map = ControllerUtils.row_to_map(payment_data, DBPaymentsColumns)
            payments.append(payment_map)

        payments = ControllerUtils.filter_payments(
            payments,
            self.db_model,
            year=year,
            include_unpaid_invoice_payments=include_unpaid_invoices
        )

        for row in payment_rows:
            payment_data = row[:len(DBPaymentsColumns)]
            payment_map = ControllerUtils.row_to_map(payment_data, DBPaymentsColumns)

            if payment_map not in payments:
                continue

            invoice_data = row[len(DBPaymentsColumns):len(DBPaymentsColumns) + len(DBInvoicesColumns)]
            invoice_map = ControllerUtils.row_to_map(invoice_data, DBInvoicesColumns)

            invoice_id = invoice_map[DBInvoicesColumns.ID.value]
            rata = payment_map[DBPaymentsColumns.LINKED_RATA.value]

            payments_dict.setdefault(invoice_id, {})[rata] = payment_map

        oggi = datetime.today()
        date_format = "%Y-%m-%d"
        totale = 0

        for invoice in invoices_maps:
            num_rate = invoice.get(DBInvoicesColumns.NUMERO_RATE.value) or 1
            invoice_id = invoice[DBInvoicesColumns.ID.value]

            for rata in range(1, num_rate + 1):
                due_date_str = invoice.get(
                    getattr(DBInvoicesColumns, f"DATA_SCADENZA_{rata}").value,
                    None
                )
                if not due_date_str:
                    continue

                try:
                    due_date = datetime.strptime(due_date_str, date_format)
                except ValueError:
                    continue

                payment = payments_dict.get(invoice_id, {}).get(rata)

                if payment:
                    try:
                        payment_date = datetime.strptime(
                            payment[DBPaymentsColumns.PAYMENT_DATE.value],
                            date_format
                        )
                        if payment_date > due_date:
                            totale += (payment_date - due_date).days
                    except ValueError:
                        pass
                else:
                    if oggi > due_date:
                        totale += (oggi - due_date).days

        return totale

    def calcola_tot_rimborsi_by_client(
            self,
            client_id,
            year: int = None
    ):
        """Somma l'ammontare dei rimborsi emessi per il cliente nel periodo."""
        refunds = [
            ControllerUtils.row_to_map(row, DBRefundsColumns)
            for row in self.db_model.fetch_refunds_by_client_id(client_id)
        ]

        refunds = ControllerUtils.filter_refunds(refunds, year=year)

        return sum(float(r[DBRefundsColumns.REFUND_AMOUNT.value]) for r in refunds)

    def construct_client_map_aggregate_data(self, client_id, include_unpaid_invoices: bool = True, year: int = None):
        """
        Restituisce un dizionario unico con tutti gli aggregati esposti dalla service.

        Questo e' il punto di ingresso piu' comodo per le view che devono
        mostrare una card cliente con tutte le metriche principali.
        """
        client_aggregate_data = {
            ClientsAggregateData.TOT_ENTRATE.value: self.calcola_tot_entrate_cliente(
                client_id,
                include_unpaid_invoices=include_unpaid_invoices,
                year=year
            ),
            ClientsAggregateData.NUM_FATTURE.value: self.calcola_numero_fatture_cliente(
                client_id,
                include_unpaid_invoices=include_unpaid_invoices,
                year=year
            ),
            ClientsAggregateData.MEDIA_FATTURE.value: self.calcola_media_fatture_cliente(
                client_id,
                include_unpaid_invoices=include_unpaid_invoices,
                year=year
            ),
            ClientsAggregateData.TOT_CREDITI.value: self.calcola_totale_crediti_cliente(
                client_id,
                include_unpaid_invoices=include_unpaid_invoices,
                year=year
            ),
            ClientsAggregateData.TOT_RIMBORSI.value: self.calcola_tot_rimborsi_by_client(
                client_id,
                year=year
            ),
            ClientsAggregateData.PAGAM_ORARIO_MEDIO.value: self.calcola_pagam_orario_medio_cliente(
                client_id,
                include_unpaid_invoices=include_unpaid_invoices,
                year=year
            ),
            ClientsAggregateData.TOT_GIORNI_RIT.value: self.calcola_totale_ritardi_cliente(
                client_id,
                include_unpaid_invoices=include_unpaid_invoices,
                year=year
            ),
            ClientsAggregateData.MEDIA_RITARDO.value: self.calcola_ritardo_medio_cliente(
                client_id,
                include_unpaid_invoices=include_unpaid_invoices,
                year=year
            )
        }

        return client_aggregate_data

from enum import Enum


class TipologiaCliente(Enum):
    PRIVATO = "PRIVATO"
    AZIENDA = "AZIENDA"
    ENTE_PUBBLICO = "ENTE_PUBBLICO"
    ALTRO = "ALTRO"


class BusinessSector(Enum):
    AEROSPACE = "Aerospaziale e Difesa"
    AGRICULTURE = "Agricoltura e Allevamento"
    CREATIVE_AGENCY = "Agenzia Creativa"
    FOOD_AND_BEVERAGE = "Alimentare e Bevande"
    AUTOMOTIVE = "Automobilistico"
    CHEMICAL = "Chimico"
    RETAIL = "Commercio al Dettaglio"
    WHOLESALE = "Commercio all'Ingrosso"
    CONSULTING = "Consulenza e Servizi Professionali"
    CONSTRUCTION = "Costruzioni e Edilizia"
    ENERGY = "Energia e Risorse Naturali"
    PHARMACEUTICAL = "Farmaceutico"
    FINANCE = "Finanza e Assicurazioni"
    GOVERNMENT = "Governo e Settore Pubblico"
    REAL_ESTATE = "Immobiliare"
    EDUCATION = "Istruzione e Formazione"
    ENTERTAINMENT = "Intrattenimento e Media"
    MANUFACTURING = "Manifatturiero e Produzione"
    NON_PROFIT = "Organizzazioni Non Profit"
    RESEARCH_AND_DEVELOPMENT = "Ricerca e Sviluppo"
    HEALTHCARE = "Sanità e Servizi Medici"
    ENVIRONMENTAL_SERVICES = "Servizi Ambientali"
    SECURITY = "Sicurezza e Vigilanza"
    SPORTS = "Sport e Benessere"
    INFORMATION_TECHNOLOGY = "Tecnologia dell'Informazione (IT)"
    TELECOMMUNICATIONS = "Telecomunicazioni"
    TEXTILE = "Tessile e Abbigliamento"
    TOURISM = "Turismo e Ospitalità"
    TRANSPORTATION = "Trasporti e Logistica"


class RegimeFiscale(Enum):
    FORFETTARIO = "Forfettario"
    ORDINARIO = "Ordinario"


class UserStatus(Enum):
    ATTIVO = "attivo"
    DISATTIVO = "disattivo"


class InvoiceSatus(Enum): #stati per le fatture con una rata
    DA_EMETTERE = "DA EMETTERE" #questo valore non prenderlo in considerazione per ora
    EMESSA = "EMESSA"
    SALDATA = "SALDATA"
    SCADUTA = "SCADUTA"
    STORNATA = "STORNATA" #questo valore non prenderlo in considerazione per ora


class InvoiceRateizzSatus(Enum): #stati per le fatture con tre rate (le rate possibili sono solo 1 o 3)
    DA_EMETTERE = "DA EMETTERE" #questo valore non prenderlo in considerazione per ora
    EMESSA = "EMESSA" #nessuna rata scaduta e nessuna rata pagata
    PARZIALMENTE_SALDATA = "PARZIALMENTE SALDATA" #una o più rate pagate e nessuna rata scaduta
    CRITICA = "CRITICA" #una o più rate scadute
    SCADUTA = "SCADUTA" #tutte le rate sono scadute e nessuna è stata saldata
    PAGATA = "PAGATA" #tutte le rate pagate
    STORNATA = "STORNATA" #questo valore non prenderlo in considerazione per ora


class PaymentsMethods(Enum):
    BONIFICO = "BONIFICO"
    CONTANTI = "CONTANTI"
    ASSEGNO = "ASSEGNO"


class Rateizzazione(Enum):
    UNA = "1"
    TRE = "3"


class TipologiaFattura(Enum):
    FATTURA = "FATTURA"
    NOTA_DI_CREDITO = "NOTA DI CREDITO"


class TipologiaProduzione(Enum): #DA ESTENDERE CON FILE DI CONFIGURAZIONE MODIFICABILE DA UTENTE
    PRODUZIONE = "PRODUZIONE"
    POST_PRODUZIONE = "POST_PRODUZIONE"
    MISTA = "MISTA" #POST + PRODUZIONE
    CONSULENZA = "CONSULENZA"


class TipologiaOutput(Enum): #DA ESTENDERE CON FILE DI CONFIGURAZIONE MODIFICABILE DA UTENTE
    VIDEO_MUSICALE = "VIDEO_MUSICALE"
    ADV_SOCIAL = "ADV_SOCIAL"
    COMMERCIAL = "COMMERCIAL"
    INTEGRAZIONE_VFX = "INTEGRAZIONE_VFX"


class ProductionStatus(Enum):
    START_WAITING = "START_WAITING"
    DOC_WAITING = "DOC_WAITING"
    WORKING = "WORKING"
    REVISION = "REVISION"
    CLOSED = "CLOSED"


class ExpensesAggregateData(Enum):
    NUMERO_SPESE = "#SPESE"
    TOT_SPESE = "TOT. SPESE"


class RecurringExpensesFrequencies(Enum):
    SETTIMANALE = "SETTIMANALE"
    MENSILE = "MENSILE"
    BIMESTRALE = "BIMESTRALE"
    TRIMESTRALE = "TRIMESTRALE"
    QUADRIMESTRALE = "QUADRIMESTRALE"
    SEMESTRALE = "SEMESTRALE"
    ANNUALE = "ANNUALE"


class RecurringExpensesStatus(Enum):
    ATTIVA = "Attiva"
    SOSPESA = "Sospesa"


class InvoiceAggregatedData(Enum):
    NUMERO_FATTURE = "NUMERO_FATTURE"
    FATT_LORDO = "FATT_LORDO"
    FATT_NETTO = "FATT_NETTO"
    IVA_DEBITO = "IVA_DEBITO"
    CREDITI_LORDO = "CREDITI_LORDO"
    CREDITI_NETTO = "CREDITI_NETTO"
    MEDIA_FATTURA_LORDO = "MEDIA_FATTURA_LORDO"
    MEDIA_FATTURA_NETTO = "MEDIA_FATTURA_NETTO"
    MEDIA_PAGAM_ORARIO_LORDO = "MEDIA_PAGAM_ORARIO_LORDO"
    MEDIA_PAGAM_ORARIO_NETTO = "MDIA_PAGAM_ORARIO_NETTO"


class PaymentsAggregateData(Enum):
    NUMERO_PAGAMENTI = "#PAGAMENTI"
    TOT_PAGAMENTI = "TOT. PAGAMENTI"


class AccountsAggregateData(Enum):
    NUM_ACCOUNTS = "num_accounts"
    TOTAL_BALANCE = "total_balance"


class ProductionsAggregateData(Enum):
    NUMERO_PRODUZIONI = "#PRODUZIONI"
    NUMERO_PRODUZIONI_ATTIVE = "#PRODUZIONI\nATTIVE"
    NUMERO_PRODUZIONI_CHIUSE = "#PRODUZIONI\nCHIUSE"
    MEDIA_ORE_PRODUZIONE = "MEDIA ORE\nPER PRODUZIONE"
    MEDIA_PREZZO_ORARIO = "MEDIA PREZZO PER\nORA DI PRODUZIONE"


class SalariesAggregateData(Enum):
    NUMERO_SALARI = "#SALARI"
    TOT_SALARI = "TOT. SALARI"


class RefundsAggregateData(Enum):
    NUMERO_RIMBORSI = "#RIMBORSI"
    TOT_RIMBORSI = "TOT. RIMBORSI"


class SupplierAggregateData(Enum):
    TOT_SPESE = "tot_spese"
    NUM_SPESE = "num_spese"
    MEDIA_SPESE = "media_spese"


class ClientsAggregateData(Enum):
        TOT_ENTRATE = "tot_entrate"
        NUM_FATTURE = "num_fatture"
        MEDIA_FATTURE = "media_fatture"
        TOT_CREDITI = "tot_crediti"
        TOT_RIMBORSI = "tot_rimborsi"
        PAGAM_ORARIO_MEDIO = "pagam_orario_medio"
        TOT_GIORNI_RIT = "tot_giorni_ritardo"
        MEDIA_RITARDO = "media_ritardo"


#################################################
##############     DBCOLUMNS       ##############
#################################################

class DBUsersColumns(Enum):
    """ SE MODIFICHI QUESTO ENUM DEVI MODIFICARE ANCHE LO SCRIPT DI CREAZIONE DELLA TABELLA E LA FUNZIONE SAVE UTENTE DELLA VIEW"""
    ID = "id"
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    PARTITA_IVA = "partita_iva"
    CODICE_FISCALE = "codice_fiscale"
    TELEFONO = "telefono"
    EMAIL = "email"
    REGIME_FISCALE = "regime_fiscale"
    ANNO_APERTURA_PIVA = "anno_apertura_piva"
    REDDITO_ESTERNO = "reddito_esterno"
    SPESE_DEDOTTE_ESTERNE = "spese_dedotte_esterne" #totale iva inclusa delle spese non attribuibili a willow
    CONTO_CORRENTE_ID = "conto_corrente_id"
    PROVIDER_FATTURE = "provider_fatture"
    USERNAME_PROVIDER = "username_provider"
    PASSWORD_PROVIDER = "password_provider"
    PASSWORD_LOGIN = "password_login"
    STATUS = "status"
    LAST_YEAR_IRPEF_ACCONTO = "acconto_irpef"
    LAST_YEAR_INPS_ACCONTO = "acconto_inps"
    PHOTO_PATH = "photo_path"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    CRYPTO_SALT = "crypto_salt"      # salt random (hex) per la derivazione PBKDF2 della chiave per-utente
    CRYPTO_CHECK = "crypto_check"    # valore noto cifrato con la chiave per-utente: serve a validare lo sblocco
    RECOVERY_HASH = "recovery_hash"  # hash PBKDF2 del recovery code (mai in chiaro nel DB)

class DBClientsColumns(Enum):
    """ SE MODIFICHI QUESTO ENUM DEVI MODIFICARE ANCHE LO SCRIPT DI CREAZIONE DELLA TABELLA E LA FUNZIONE SAVE CLIENTE DELLA VIEW"""
    ID = "id"
    NAME = "name"
    PARTITA_IVA = "partita_iva"
    EMAIL = "email"
    SEDE_LEGALE = "sede_legale"
    SETTORE = "settore"
    TIPOLOGIA = "tipologia"
    REFERENTE = "referente"
    CONTATTO_REFERENTE = "contatto_referente"
    NOTE = "note"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"

class DBInvoicesColumns(Enum):
    """ SE MODIFICHI QUESTO ENUM DEVI MODIFICARE ANCHE LO SCRIPT DI CREAZIONE DELLA TABELLA E LA FUNZIONE SAVE INVOICE DELLA VIEW"""

    ID = "id" #db
    NUMERO_FATTURA = "numero_fattura"
    DATA_CREAZIONE = "creation_date"
    DATA_SCADENZA_1 = "expiration_date_1"
    DATA_SCADENZA_2 = "expiration_date_2"
    DATA_SCADENZA_3 = "expiration_date_3"
    ID_UTENTE = "invoicer_id"
    ID_CLIENTE = "client_id"
    ID_CONTO = "ID_CONTO"
    NOTE = "note"
    SERVIZI = "importo_servizi"
    CASSA_INPS = "cassa_inps"
    IMPONIBILE = "imponibile"
    IVA = "iva"
    RIMBORSI = "rimborsi"
    RIVALSA_INPS = "rivalsa_inps"
    TOT_DOCUMENTO = "tot_documento"
    RITENUTA = "ritenuta"
    NETTO_A_PAGARE = "netto_a_pagare"
    STATUS = "status"
    METODO_PAGAMENTO = "metodo_pagamento"
    NUMERO_RATE = "rate_totali"
    TIPO = "tipo"
    ID_FATTURA_ASSOCIATA = "id_fattura_associata"
    ID_PRODUZIONE_ASSOCIATA = "id_produzione_associata"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"

class DBPaymentsColumns(Enum):
    """ SE MODIFICHI QUESTO ENUM DEVI MODIFICARE ANCHE LO SCRIPT DI CREAZIONE DELLA TABELLA E LA FUNZIONE SAVE PAYMENT DELLA VIEW"""

    ID = "ID"
    PAYMENT_NAME = "PAYMENT_NAME" #NomeCliente_NomeProduzione_NomeFattura_1/2/3
    PAYMENT_AMOUNT = "PAYMENT_AMOUNT"
    PAYMENT_DATE = "PAYMENT_DATE"
    LINKED_RATA = "LINKED_RATA" # 1, 2, 3
    INVOICE_ID = "INVOICE_ID"
    CONTO_ID = "CONTO_ID"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"

class DBProductionsColumns(Enum):
    ID = "ID"
    NAME = "NAME"
    CLIENT_ID = "CLIENT_ID"
    HOURS = "HOURS"
    TIPOLOGIA_PRODUZIONE = "TIPOLOGIA_PRODUZIONE"
    TIPOLOGIA_OUTPUT = "TIPOLOGIA_OUTPUT"
    STATO = "STATO"
    END_DATE = "END_DATE"
    TOTALE_PREVENTIVO = "TOTALE_PREVENTIVO"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"

class DBAccountsColumns(Enum):
    ID = "ID"
    NAME = "NAME"
    INIT_BALANCE = "INIT_BALANCE"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"

class DBTransfersColumns(Enum):
    ID = "ID"
    DESCRIPTION = "CAUSALE"
    AMOUNT = "IMPORTO"
    SENDER_ACCOUNT_ID = "ID_CONTO_MITTENTE"
    RECEIVER_ACCOUNT_ID = "ID_CONTO_RICEVENTE"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"

class DBExpensesColumns(Enum):
    ID = "ID"
    NAME = "NOME"
    USER_ID_DEDUZIONE = "ID_UTENTE_DEDUZIONE"
    USER_ID_ANTICIPO = "ID_UTENTE_ANTICIPO"
    SUPPLIER_ID = "ID_FORNITORE"
    CATEGORY = "CATEGORIA"
    NET_AMOUNT = "IMPORTO_NETTO"
    IVA_AMOUNT = "IMPORTO_IVA"
    TOT_AMOUNT = "IMPORTO_LORDO"
    DATE = "DATA_PAGAMENTO"
    DEDUCIBILE = "DEDUCIBILE"
    ACCOUNT_ID = "ID_CONTO"
    LINKED_INVOICE_ID = "ID_FATTURA_COLLEGATA"
    RICORRENTE = "RICORRENTE"
    created_at = "created_at"
    updated_at = "updated_at"

class DBSuppliersColumns(Enum):
    ID = "ID"
    NAME = "NOME"
    PARTITA_IVA = "PARTITA_IVA"
    SEDE = "SEDE"
    CONTATTO = "CONTATTO_REFERENTE"
    CATEGORIA = "CATEGORIA"
    NOTE = "NOTE"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"

class DBSalariesColumns(Enum):
    ID = "ID"
    NAME = "NAME"
    AMOUNT = "TOTALE"
    DATE = "DATE"
    ACCOUNT_ID = "ID_CONTO"
    USER_ID = "ID_UTENTE"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"

class DBRefundsColumns(Enum):
    ID = "ID"
    REFUND_NAME = "REFUND_NAME"
    REFUND_AMOUNT = "REFUND_AMOUNT"
    REFUND_DATE = "REFUND_DATE"
    CLIENT_ID = "CLIENT_ID"
    CONTO_ID = "CONTO_ID"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"

class DBAdminColumns(Enum):
    """Tabella admin: singolo amministratore del sistema.
    Non cifra dati propri (non ha provider creds o campi sensibili),
    quindi NON ha crypto_salt/crypto_check: solo hash della password
    e hash del recovery code."""
    ID = "id"
    NAME = "name"
    PASSWORD_LOGIN = "password_login"
    RECOVERY_HASH = "recovery_hash"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


ADMIN_FIXED_NAME = "ADMIN"


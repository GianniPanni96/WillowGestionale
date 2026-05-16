import argparse
import os
import random
import sqlite3
import string
import sys
from datetime import date, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Gestionale_Enums import (
    BusinessSector,
    DBAccountsColumns,
    DBClientsColumns,
    DBExpensesColumns,
    DBInvoicesColumns,
    DBPaymentsColumns,
    DBProductionsColumns,
    DBRefundsColumns,
    DBSalariesColumns,
    DBSuppliersColumns,
    DBTransfersColumns,
    DBUsersColumns,
    InvoiceRateizzSatus,
    InvoiceSatus,
    PaymentsMethods,
    ProductionStatus,
    Rateizzazione,
    RegimeFiscale,
    TipologiaCliente,
    TipologiaFattura,
    TipologiaOutput,
    TipologiaProduzione,
    UserStatus,
)
from Model import db_path as runtime_db_path


TABLES = (
    "accounts",
    "clients",
    "suppliers",
    "users",
    "productions",
    "invoices",
    "payments",
    "expenses",
    "transfers",
    "salaries",
    "refunds",
)

NO_INVOICE_PROVIDER = "nessuno"


FIRST_NAMES = (
    "Luca",
    "Giulia",
    "Marco",
    "Sara",
    "Davide",
    "Elena",
    "Matteo",
    "Chiara",
    "Andrea",
    "Francesca",
)
LAST_NAMES = (
    "Rossi",
    "Bianchi",
    "Ferrari",
    "Romano",
    "Gallo",
    "Costa",
    "Fontana",
    "Moretti",
    "Conti",
    "Marino",
)
CLIENT_ROOTS = (
    "Nebula",
    "Pixel",
    "Aurora",
    "Vector",
    "Studio",
    "Forma",
    "Materia",
    "Lumen",
    "Orizzonte",
    "Sintesi",
)
SUPPLIER_ROOTS = (
    "Office",
    "Cloud",
    "Rental",
    "Hardware",
    "Travel",
    "Energia",
    "Media",
    "Servizi",
    "Logistica",
    "Lab",
)
PRODUCTION_NAMES = (
    "Spot prodotto",
    "Video evento",
    "Campagna social",
    "Tutorial corporate",
    "Rendering VFX",
    "Intervista brand",
    "Format web",
    "Demo app",
)
EXPENSE_NAMES = (
    "Licenze software",
    "Noleggio attrezzatura",
    "Materiale di consumo",
    "Trasferta produzione",
    "Hosting progetto",
    "Consulenza tecnica",
    "Utenze studio",
    "Campagna advertising",
)


def quote_identifier(identifier):
    return '"' + identifier.replace('"', '""') + '"'


def pick(seq):
    return random.choice(tuple(seq))


def money(min_value, max_value):
    return round(random.uniform(min_value, max_value), 2)


def iso_day(days_back=730, days_forward=60):
    delta = random.randint(-days_back, days_forward)
    return (date.today() + timedelta(days=delta)).isoformat()


def add_days(iso_date, days):
    return (date.fromisoformat(iso_date) + timedelta(days=days)).isoformat()


def digits(length):
    return "".join(random.choice(string.digits) for _ in range(length))


def fake_codice_fiscale(index, token):
    base = f"RSSLCU{80 + index:02d}A01H501"
    suffix = "".join(ch for ch in token.upper() if ch.isalnum())[-2:].rjust(2, "X")
    return (base + suffix)[:16]


def insert_row(cursor, table, data):
    columns = list(data.keys())
    quoted_columns = ", ".join(quote_identifier(column) for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    query = f"INSERT INTO {quote_identifier(table)} ({quoted_columns}) VALUES ({placeholders})"
    cursor.execute(query, tuple(data[column] for column in columns))
    return cursor.lastrowid


def require_tables(cursor):
    existing = {
        row[0]
        for row in cursor.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    missing = [table for table in TABLES if table not in existing]
    if missing:
        raise RuntimeError(
            "Il database non contiene tutte le tabelle richieste. Mancano: "
            + ", ".join(missing)
        )


def resolve_db_path(explicit_path):
    if explicit_path:
        return Path(explicit_path).expanduser().resolve()

    env_value = os.environ.get("GESTIONALE_DB_PATH")
    if env_value:
        env_path = Path(env_value).expanduser().resolve()
        if env_path.suffix.lower() == ".db":
            return env_path
        return env_path / "gestionale.db"

    return Path(runtime_db_path).expanduser().resolve()


def create_accounts(cursor, token, count):
    ids = []
    account_names = ("Banca principale", "Conto tasse", "Carta aziendale", "Cassa contanti")
    for index in range(max(2, count)):
        name = f"Seed {token} - {account_names[index % len(account_names)]} {index + 1}"
        ids.append(
            insert_row(
                cursor,
                "accounts",
                {
                    DBAccountsColumns.NAME.value: name,
                    DBAccountsColumns.INIT_BALANCE.value: money(500, 25000),
                },
            )
        )
    return ids


def create_clients(cursor, token, count):
    ids = []
    sectors = [item.value for item in BusinessSector]
    client_types = [item.value for item in TipologiaCliente]
    for index in range(count):
        root = CLIENT_ROOTS[index % len(CLIENT_ROOTS)]
        ids.append(
            insert_row(
                cursor,
                "clients",
                {
                    DBClientsColumns.NAME.value: f"{root} {token} SRL {index + 1}",
                    DBClientsColumns.PARTITA_IVA.value: digits(11),
                    DBClientsColumns.EMAIL.value: f"cliente{index + 1}.{token}@example.test",
                    DBClientsColumns.SEDE_LEGALE.value: f"Via Inventata {index + 1}, Milano",
                    DBClientsColumns.SETTORE.value: pick(sectors),
                    DBClientsColumns.TIPOLOGIA.value: pick(client_types),
                    DBClientsColumns.REFERENTE.value: f"{pick(FIRST_NAMES)} {pick(LAST_NAMES)}",
                    DBClientsColumns.CONTATTO_REFERENTE.value: f"+39 3{digits(9)}",
                    DBClientsColumns.NOTE.value: "Cliente dimostrativo generato automaticamente.",
                },
            )
        )
    return ids


def create_suppliers(cursor, token, count):
    ids = []
    categories = [item.value for item in BusinessSector]
    for index in range(count):
        root = SUPPLIER_ROOTS[index % len(SUPPLIER_ROOTS)]
        ids.append(
            insert_row(
                cursor,
                "suppliers",
                {
                    DBSuppliersColumns.NAME.value: f"{root} {token} Forniture {index + 1}",
                    DBSuppliersColumns.PARTITA_IVA.value: digits(11),
                    DBSuppliersColumns.SEDE.value: f"Corso Campione {index + 10}, Torino",
                    DBSuppliersColumns.CONTATTO.value: f"fornitore{index + 1}.{token}@example.test",
                    DBSuppliersColumns.CATEGORIA.value: pick(categories),
                    DBSuppliersColumns.NOTE.value: "Fornitore dimostrativo generato automaticamente.",
                },
            )
        )
    return ids


def create_users(cursor, token, count, account_ids):
    ids = []
    regimes = [RegimeFiscale.FORFETTARIO.value, RegimeFiscale.ORDINARIO.value]
    for index in range(count):
        first_name = FIRST_NAMES[index % len(FIRST_NAMES)]
        last_name = LAST_NAMES[(index * 3) % len(LAST_NAMES)]
        ids.append(
            insert_row(
                cursor,
                "users",
                {
                    DBUsersColumns.FIRST_NAME.value: first_name,
                    DBUsersColumns.LAST_NAME.value: last_name,
                    DBUsersColumns.PARTITA_IVA.value: digits(11),
                    DBUsersColumns.CODICE_FISCALE.value: fake_codice_fiscale(index, token),
                    DBUsersColumns.TELEFONO.value: f"+39 3{digits(9)}",
                    DBUsersColumns.EMAIL.value: f"{first_name.lower()}.{last_name.lower()}.{token}@example.test",
                    DBUsersColumns.REGIME_FISCALE.value: regimes[index % len(regimes)],
                    DBUsersColumns.ANNO_APERTURA_PIVA.value: random.randint(2015, date.today().year),
                    DBUsersColumns.REDDITO_ESTERNO.value: money(0, 12000),
                    DBUsersColumns.SPESE_DEDOTTE_ESTERNE.value: money(0, 2500),
                    DBUsersColumns.CONTO_CORRENTE_ID.value: pick(account_ids),
                    DBUsersColumns.PROVIDER_FATTURE.value: NO_INVOICE_PROVIDER,
                    DBUsersColumns.USERNAME_PROVIDER.value: None,
                    DBUsersColumns.PASSWORD_PROVIDER.value: None,
                    DBUsersColumns.PASSWORD_LOGIN.value: None,
                    DBUsersColumns.STATUS.value: UserStatus.ATTIVO.value,
                    DBUsersColumns.LAST_YEAR_IRPEF_ACCONTO.value: money(0, 1800),
                    DBUsersColumns.LAST_YEAR_INPS_ACCONTO.value: money(0, 2200),
                    DBUsersColumns.PHOTO_PATH.value: None,
                },
            )
        )
    return ids


def create_productions(cursor, token, count, client_ids):
    ids = []
    production_types = [item.value for item in TipologiaProduzione]
    output_types = [item.value for item in TipologiaOutput]
    statuses = [item.value for item in ProductionStatus]
    for index in range(count):
        ids.append(
            insert_row(
                cursor,
                "productions",
                {
                    DBProductionsColumns.NAME.value: f"Seed {token} - {pick(PRODUCTION_NAMES)} {index + 1}",
                    DBProductionsColumns.CLIENT_ID.value: pick(client_ids),
                    DBProductionsColumns.HOURS.value: round(random.uniform(8, 160), 1),
                    DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value: pick(production_types),
                    DBProductionsColumns.TIPOLOGIA_OUTPUT.value: pick(output_types),
                    DBProductionsColumns.STATO.value: pick(statuses),
                    DBProductionsColumns.END_DATE.value: iso_day(days_back=180, days_forward=120),
                    DBProductionsColumns.TOTALE_PREVENTIVO.value: money(900, 18000),
                },
            )
        )
    return ids


def invoice_amounts():
    services = money(600, 9000)
    refunds = money(0, 900)
    rivalsa = round(services * 0.04, 2)
    imponibile = round(services + rivalsa, 2)
    iva = round(imponibile * 0.22, 2)
    total = round(imponibile + iva + refunds, 2)
    withholding = round(services * 0.2, 2)
    net = round(total - withholding, 2)
    return services, refunds, rivalsa, imponibile, iva, total, withholding, net


def create_invoices(cursor, token, count, user_ids, client_ids, account_ids, production_ids):
    ids = []
    methods = [item.value for item in PaymentsMethods]
    for index in range(count):
        creation_date = iso_day(days_back=420, days_forward=20)
        rates = Rateizzazione.TRE.value if index % 3 == 0 else Rateizzazione.UNA.value
        status = InvoiceRateizzSatus.EMESSA.value if rates == Rateizzazione.TRE.value else InvoiceSatus.EMESSA.value
        services, refunds, rivalsa, imponibile, iva, total, withholding, net = invoice_amounts()
        ids.append(
            insert_row(
                cursor,
                "invoices",
                {
                    DBInvoicesColumns.NUMERO_FATTURA.value: f"SEED-{token}-{index + 1:04d}",
                    DBInvoicesColumns.DATA_CREAZIONE.value: creation_date,
                    DBInvoicesColumns.DATA_SCADENZA_1.value: add_days(creation_date, 30),
                    DBInvoicesColumns.DATA_SCADENZA_2.value: add_days(creation_date, 60) if rates == Rateizzazione.TRE.value else None,
                    DBInvoicesColumns.DATA_SCADENZA_3.value: add_days(creation_date, 90) if rates == Rateizzazione.TRE.value else None,
                    DBInvoicesColumns.ID_UTENTE.value: pick(user_ids),
                    DBInvoicesColumns.ID_CLIENTE.value: pick(client_ids),
                    DBInvoicesColumns.ID_CONTO.value: pick(account_ids),
                    DBInvoicesColumns.NOTE.value: "Fattura dimostrativa generata automaticamente.",
                    DBInvoicesColumns.SERVIZI.value: services,
                    DBInvoicesColumns.CASSA_INPS.value: round(services * 0.04, 2),
                    DBInvoicesColumns.IMPONIBILE.value: imponibile,
                    DBInvoicesColumns.IVA.value: iva,
                    DBInvoicesColumns.RIMBORSI.value: refunds,
                    DBInvoicesColumns.RIVALSA_INPS.value: rivalsa,
                    DBInvoicesColumns.TOT_DOCUMENTO.value: total,
                    DBInvoicesColumns.RITENUTA.value: withholding,
                    DBInvoicesColumns.NETTO_A_PAGARE.value: net,
                    DBInvoicesColumns.STATUS.value: status,
                    DBInvoicesColumns.METODO_PAGAMENTO.value: pick(methods),
                    DBInvoicesColumns.NUMERO_RATE.value: rates,
                    DBInvoicesColumns.TIPO.value: TipologiaFattura.FATTURA.value,
                    DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value: None,
                    DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value: pick(production_ids),
                },
            )
        )
    return ids


def create_payments(cursor, token, count, invoice_ids, account_ids):
    ids = []
    for index in range(count):
        invoice_id = pick(invoice_ids)
        linked_rata = random.choice((1, 2, 3))
        ids.append(
            insert_row(
                cursor,
                "payments",
                {
                    DBPaymentsColumns.PAYMENT_NAME.value: f"Pagamento seed {token} {index + 1} rata {linked_rata}",
                    DBPaymentsColumns.PAYMENT_AMOUNT.value: money(250, 4500),
                    DBPaymentsColumns.PAYMENT_DATE.value: iso_day(days_back=365, days_forward=0),
                    DBPaymentsColumns.LINKED_RATA.value: linked_rata,
                    DBPaymentsColumns.INVOICE_ID.value: invoice_id,
                    DBPaymentsColumns.CONTO_ID.value: pick(account_ids),
                },
            )
        )
    return ids


def create_expenses(cursor, token, count, user_ids, supplier_ids, account_ids, invoice_ids):
    ids = []
    categories = [item.value for item in BusinessSector]
    for index in range(count):
        gross = money(40, 3500)
        iva_rate = random.choice((0.0, 0.04, 0.10, 0.22))
        net = round(gross / (1 + iva_rate), 2)
        iva = round(gross - net, 2)
        deductible = random.choice(("Si", "No"))
        ids.append(
            insert_row(
                cursor,
                "expenses",
                {
                    DBExpensesColumns.NAME.value: f"Spesa seed {token} - {pick(EXPENSE_NAMES)} {index + 1}",
                    DBExpensesColumns.USER_ID_DEDUZIONE.value: pick(user_ids) if deductible == "Si" else None,
                    DBExpensesColumns.USER_ID_ANTICIPO.value: random.choice([None, pick(user_ids)]),
                    DBExpensesColumns.SUPPLIER_ID.value: pick(supplier_ids),
                    DBExpensesColumns.CATEGORY.value: pick(categories),
                    DBExpensesColumns.NET_AMOUNT.value: net,
                    DBExpensesColumns.IVA_AMOUNT.value: iva,
                    DBExpensesColumns.TOT_AMOUNT.value: gross,
                    DBExpensesColumns.DATE.value: iso_day(days_back=365, days_forward=0),
                    DBExpensesColumns.DEDUCIBILE.value: deductible,
                    DBExpensesColumns.ACCOUNT_ID.value: pick(account_ids),
                    DBExpensesColumns.LINKED_INVOICE_ID.value: random.choice([None, pick(invoice_ids)]),
                    DBExpensesColumns.RICORRENTE.value: random.choice((0, 1)),
                },
            )
        )
    return ids


def create_transfers(cursor, token, count, account_ids):
    ids = []
    for index in range(count):
        sender = pick(account_ids)
        receiver_candidates = [account_id for account_id in account_ids if account_id != sender]
        receiver = pick(receiver_candidates)
        ids.append(
            insert_row(
                cursor,
                "transfers",
                {
                    DBTransfersColumns.DESCRIPTION.value: f"Giroconto seed {token} {index + 1}",
                    DBTransfersColumns.AMOUNT.value: money(100, 5000),
                    DBTransfersColumns.SENDER_ACCOUNT_ID.value: sender,
                    DBTransfersColumns.RECEIVER_ACCOUNT_ID.value: receiver,
                },
            )
        )
    return ids


def create_salaries(cursor, token, count, user_ids, account_ids):
    ids = []
    for index in range(count):
        ids.append(
            insert_row(
                cursor,
                "salaries",
                {
                    DBSalariesColumns.NAME.value: f"Compenso seed {token} {index + 1}",
                    DBSalariesColumns.DATE.value: iso_day(days_back=365, days_forward=0),
                    DBSalariesColumns.AMOUNT.value: money(700, 6500),
                    DBSalariesColumns.ACCOUNT_ID.value: pick(account_ids),
                    DBSalariesColumns.USER_ID.value: pick(user_ids),
                },
            )
        )
    return ids


def create_refunds(cursor, token, count, client_ids, account_ids):
    ids = []
    for index in range(count):
        ids.append(
            insert_row(
                cursor,
                "refunds",
                {
                    DBRefundsColumns.REFUND_NAME.value: f"Rimborso seed {token} {index + 1}",
                    DBRefundsColumns.REFUND_AMOUNT.value: money(40, 1400),
                    DBRefundsColumns.REFUND_DATE.value: iso_day(days_back=365, days_forward=0),
                    DBRefundsColumns.CLIENT_ID.value: pick(client_ids),
                    DBRefundsColumns.CONTO_ID.value: pick(account_ids),
                },
            )
        )
    return ids


def populate(db_path, count, seed):
    if seed is not None:
        random.seed(seed)

    token = f"{date.today().strftime('%Y%m%d')}-{random.randint(100000, 999999)}"
    inserted = {}

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        require_tables(cursor)

        try:
            inserted["accounts"] = create_accounts(cursor, token, count)
            inserted["clients"] = create_clients(cursor, token, count)
            inserted["suppliers"] = create_suppliers(cursor, token, count)
            inserted["users"] = create_users(cursor, token, count, inserted["accounts"])
            inserted["productions"] = create_productions(cursor, token, count, inserted["clients"])
            inserted["invoices"] = create_invoices(
                cursor,
                token,
                count,
                inserted["users"],
                inserted["clients"],
                inserted["accounts"],
                inserted["productions"],
            )
            inserted["payments"] = create_payments(cursor, token, count, inserted["invoices"], inserted["accounts"])
            inserted["expenses"] = create_expenses(
                cursor,
                token,
                count,
                inserted["users"],
                inserted["suppliers"],
                inserted["accounts"],
                inserted["invoices"],
            )
            inserted["transfers"] = create_transfers(cursor, token, count, inserted["accounts"])
            inserted["salaries"] = create_salaries(cursor, token, count, inserted["users"], inserted["accounts"])
            inserted["refunds"] = create_refunds(cursor, token, count, inserted["clients"], inserted["accounts"])
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return token, {table: len(ids) for table, ids in inserted.items()}


def main():
    parser = argparse.ArgumentParser(
        description="Popola il database gestionale con dati casuali inventati rispettando le foreign key."
    )
    parser.add_argument(
        "--db-path",
        help="Percorso del file SQLite. Se omesso usa GESTIONALE_DB_PATH o il path runtime del progetto.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=8,
        help="Numero di record da creare per ogni tabella principale. Default: 8.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Seed opzionale per rendere riproducibile la generazione.",
    )
    args = parser.parse_args()

    if args.count < 1:
        raise ValueError("--count deve essere almeno 1.")

    db_file = resolve_db_path(args.db_path)
    if not db_file.exists():
        raise FileNotFoundError(f"Database non trovato: {db_file}")

    token, counts = populate(db_file, args.count, args.seed)
    print(f"Database popolato: {db_file}")
    print(f"Prefisso lotto: {token}")
    for table in TABLES:
        print(f"  {table}: {counts.get(table, 0)} record inseriti")


if __name__ == "__main__":
    main()

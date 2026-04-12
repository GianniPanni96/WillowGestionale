import sqlite3
from Model import db_path, DBInvoicesColumns, DBUsersColumns, DBClientsColumns, DBProductionsColumns, DBAccountsColumns

# Creazione della tabella `invoices` utilizzando l'enum
columns = [
    f"{DBInvoicesColumns.ID.value} INTEGER PRIMARY KEY AUTOINCREMENT",
    f"{DBInvoicesColumns.NUMERO_FATTURA.value} TEXT UNIQUE NOT NULL",
    f"{DBInvoicesColumns.DATA_CREAZIONE.value} DATE NOT NULL",
    f"{DBInvoicesColumns.DATA_SCADENZA_1.value} DATE NOT NULL",
    f"{DBInvoicesColumns.DATA_SCADENZA_2.value} DATE",
    f"{DBInvoicesColumns.DATA_SCADENZA_3.value} DATE",
    f"{DBInvoicesColumns.ID_UTENTE.value} INTEGER NOT NULL",
    f"{DBInvoicesColumns.ID_CLIENTE.value} INTEGER NOT NULL",
    f"{DBInvoicesColumns.ID_CONTO.value} INTEGER NOT NULL",
    f"{DBInvoicesColumns.NOTE.value} TEXT",
    f"{DBInvoicesColumns.SERVIZI.value} REAL NOT NULL",
    f"{DBInvoicesColumns.CASSA_INPS.value} REAL NOT NULL",
    f"{DBInvoicesColumns.IMPONIBILE.value} REAL NOT NULL",
    f"{DBInvoicesColumns.IVA.value} REAL NOT NULL",
    f"{DBInvoicesColumns.RIMBORSI.value} REAL NOT NULL",
    f"{DBInvoicesColumns.RIVALSA_INPS.value} REAL NOT NULL",
    f"{DBInvoicesColumns.TOT_DOCUMENTO.value} REAL NOT NULL",
    f"{DBInvoicesColumns.RITENUTA.value} REAL",
    f"{DBInvoicesColumns.NETTO_A_PAGARE.value} REAL NOT NULL",
    f"{DBInvoicesColumns.STATUS.value} TEXT NOT NULL DEFAULT 'non pagata'",
    f"{DBInvoicesColumns.METODO_PAGAMENTO.value} TEXT",
    f"{DBInvoicesColumns.NUMERO_RATE.value} INTEGER DEFAULT 1",
    f"{DBInvoicesColumns.TIPO.value} TEXT NOT NULL DEFAULT 'fattura'",  # Colonna TIPO con valore di default
    f"{DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value} INTEGER DEFAULT NULL",  # Colonna ID_FATTURA_ASSOCIATA
    f"{DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value} INTEGER DEFAULT NULL",  # Colonna ID_FATTURA_ASSOCIATA
    f"{DBInvoicesColumns.CREATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    f"{DBInvoicesColumns.UPDATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    f"FOREIGN KEY ({DBInvoicesColumns.ID_UTENTE.value}) REFERENCES users({DBUsersColumns.ID.value})",
    f"FOREIGN KEY ({DBInvoicesColumns.ID_CLIENTE.value}) REFERENCES clients({DBClientsColumns.ID.value})",
    f"FOREIGN KEY ({DBInvoicesColumns.ID_CONTO.value}) REFERENCES accounts({DBAccountsColumns.ID.value})",
    f"FOREIGN KEY ({DBInvoicesColumns.ID_FATTURA_ASSOCIATA.value}) REFERENCES invoices({DBInvoicesColumns.ID.value})",  # Chiave esterna per ID_FATTURA_ASSOCIATA
    f"FOREIGN KEY ({DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value}) REFERENCES productions({DBProductionsColumns.ID.value})"
    ]

create_table_query = f"CREATE TABLE invoices ({', '.join(columns)})"

# Connessione al database ed esecuzione della query
conn = sqlite3.connect(db_path)
print(f"Connesso al database: {db_path}")
c = conn.cursor()

c.execute(create_table_query)

# Commit e chiusura connessione
conn.commit()
conn.close()

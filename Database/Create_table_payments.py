from Model import db_path, DBPaymentsColumns, DBInvoicesColumns, DBProductionsColumns, DBAccountsColumns
import sqlite3


 #Creazione della tabella `invoices` utilizzando l'enum
columns = [
    f"{DBPaymentsColumns.ID.value} INTEGER PRIMARY KEY AUTOINCREMENT",
    f"{DBPaymentsColumns.PAYMENT_NAME.value} TEXT NOT NULL UNIQUE",
    f"{DBPaymentsColumns.PAYMENT_AMOUNT.value} REAL NOT NULL",
    f"{DBPaymentsColumns.PAYMENT_DATE.value} DATE NOT NULL",
    f"{DBPaymentsColumns.LINKED_RATA.value} INTEGER NOT NULL",
    f"{DBPaymentsColumns.INVOICE_ID.value} INTEGER NOT NULL",
    f"{DBPaymentsColumns.CONTO_ID.value} INTEGER NOT NULL",
    f"{DBPaymentsColumns.CREATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    f"{DBPaymentsColumns.UPDATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    f"FOREIGN KEY ({DBPaymentsColumns.INVOICE_ID.value}) REFERENCES invoices({DBInvoicesColumns.ID.value})"
    f"FOREIGN KEY ({DBPaymentsColumns.CONTO_ID.value}) REFERENCES accounts({DBAccountsColumns.ID.value})"
]

create_table_query = f"CREATE TABLE payments ({', '.join(columns)})"

# Connessione al database ed esecuzione della query
conn = sqlite3.connect(db_path)
print(f"Connesso al database: {db_path}")
c = conn.cursor()

c.execute(create_table_query)

# Commit e chiusura connessione
conn.commit()
conn.close()
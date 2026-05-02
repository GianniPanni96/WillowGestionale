from Model import db_path, DBAccountsColumns, DBRefundsColumns, DBClientsColumns
import sqlite3


 #Creazione della tabella `invoices` utilizzando l'enum
columns = [
    f"{DBRefundsColumns.ID.value} INTEGER PRIMARY KEY AUTOINCREMENT",
    f"{DBRefundsColumns.REFUND_NAME.value} TEXT NOT NULL UNIQUE",
    f"{DBRefundsColumns.REFUND_AMOUNT.value} REAL NOT NULL",
    f"{DBRefundsColumns.REFUND_DATE.value} DATE NOT NULL",
    f"{DBRefundsColumns.CLIENT_ID.value} INTEGER NOT NULL",
    f"{DBRefundsColumns.CONTO_ID.value} INTEGER NOT NULL",
    f"{DBRefundsColumns.CREATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    f"{DBRefundsColumns.UPDATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    f"FOREIGN KEY ({DBRefundsColumns.CLIENT_ID.value}) REFERENCES clients({DBClientsColumns.ID.value})"
    f"FOREIGN KEY ({DBRefundsColumns.CONTO_ID.value}) REFERENCES accounts({DBAccountsColumns.ID.value})"
]

create_table_query = f"CREATE TABLE refunds ({', '.join(columns)})"

# Connessione al database ed esecuzione della query
conn = sqlite3.connect(db_path)
print(f"Connesso al database: {db_path}")
c = conn.cursor()

c.execute(create_table_query)

# Commit e chiusura connessione
conn.commit()
conn.close()
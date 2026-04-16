import sqlite3
from Model import db_path, DBTransfersColumns, DBAccountsColumns

# Definizione delle colonne per la tabella accounts
columns = [
    f"{DBTransfersColumns.ID.value} INTEGER PRIMARY KEY AUTOINCREMENT",
    f"{DBTransfersColumns.DESCRIPTION.value} TEXT",
    f"{DBTransfersColumns.AMOUNT.value} REAL NOT NULL",
    f"{DBTransfersColumns.SENDER_ACCOUNT_ID.value} INTEGER NOT NULL",
    f"{DBTransfersColumns.RECEIVER_ACCOUNT_ID.value} INTEGER NOT NULL",
    f"{DBTransfersColumns.CREATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    f"{DBTransfersColumns.UPDATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    f"FOREIGN KEY ({DBTransfersColumns.SENDER_ACCOUNT_ID.value}) REFERENCES accounts({DBAccountsColumns.ID.value})"
    f"FOREIGN KEY ({DBTransfersColumns.RECEIVER_ACCOUNT_ID.value}) REFERENCES accounts({DBAccountsColumns.ID.value})"

]

create_table_query = f"CREATE TABLE transfers ({', '.join(columns)})"

# Connessione al database ed esecuzione della query
conn = sqlite3.connect(db_path)
print(f"Connesso al database: {db_path}")
c = conn.cursor()

c.execute(create_table_query)

# Commit e chiusura della connessione
conn.commit()
conn.close()
import sqlite3
from Model import db_path, DBAccountsColumns

# Definizione delle colonne per la tabella accounts
columns = [
    f"{DBAccountsColumns.ID.value} INTEGER PRIMARY KEY AUTOINCREMENT",
    f"{DBAccountsColumns.NAME.value} TEXT NOT NULL",
    f"{DBAccountsColumns.INIT_BALANCE.value} REAL NOT NULL",
    f"{DBAccountsColumns.CREATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    f"{DBAccountsColumns.UPDATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
]

create_table_query = f"CREATE TABLE accounts ({', '.join(columns)})"

# Connessione al database ed esecuzione della query
conn = sqlite3.connect(db_path)
print(f"Connesso al database: {db_path}")
c = conn.cursor()

c.execute(create_table_query)

# Commit e chiusura della connessione
conn.commit()
conn.close()

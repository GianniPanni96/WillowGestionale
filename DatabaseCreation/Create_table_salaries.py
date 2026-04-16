import sqlite3
from Model import db_path, DBUsersColumns, DBAccountsColumns, DBSalariesColumns

# Definizione delle colonne per la tabella accounts
columns = [
    f"{DBSalariesColumns.ID.value} INTEGER PRIMARY KEY AUTOINCREMENT",
    f"{DBSalariesColumns.NAME.value} TEXT NOT NULL UNIQUE",
    f"{DBSalariesColumns.DATE.value} DATE NOT NULL",
    f"{DBSalariesColumns.AMOUNT.value} REAL NOT NULL",
    f"{DBSalariesColumns.ACCOUNT_ID.value} INTEGER NOT NULL",
    f"{DBSalariesColumns.USER_ID.value} INTEGER NOT NULL",
    f"{DBSalariesColumns.CREATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    f"{DBSalariesColumns.UPDATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    f"FOREIGN KEY ({DBSalariesColumns.USER_ID.value}) REFERENCES users({DBUsersColumns.ID.value})"
    f"FOREIGN KEY ({DBSalariesColumns.ACCOUNT_ID.value}) REFERENCES accounts({DBAccountsColumns.ID.value})"

]

create_table_query = f"CREATE TABLE salaries ({', '.join(columns)})"

# Connessione al database ed esecuzione della query
conn = sqlite3.connect(db_path)
print(f"Connesso al database: {db_path}")
c = conn.cursor()

c.execute(create_table_query)

# Commit e chiusura della connessione
conn.commit()
conn.close()
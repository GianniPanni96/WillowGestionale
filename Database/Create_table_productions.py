from Model import db_path, DBClientsColumns, DBProductionsColumns
import sqlite3


 #Creazione della tabella `invoices` utilizzando l'enum
columns = [
    f"{DBProductionsColumns.ID.value} INTEGER PRIMARY KEY AUTOINCREMENT",
    f"{DBProductionsColumns.NAME.value} TEXT UNIQUE NOT NULL UNIQUE",
    f"{DBProductionsColumns.CLIENT_ID.value} INTEGER NOT NULL",
    f"{DBProductionsColumns.HOURS.value} REAL",
    f"{DBProductionsColumns.TIPOLOGIA_PRODUZIONE.value} TEXT NOT NULL",
    f"{DBProductionsColumns.TIPOLOGIA_OUTPUT.value} TEXT NOT NULL",
    f"{DBProductionsColumns.STATO.value} TEXT NOT NULL",
    f"{DBProductionsColumns.END_DATE.value} DATE",
    f"{DBProductionsColumns.TOTALE_PREVENTIVO.value} REAL",
    f"{DBProductionsColumns.CREATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    f"{DBProductionsColumns.UPDATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    f"FOREIGN KEY ({DBProductionsColumns.CLIENT_ID.value}) REFERENCES clients({DBClientsColumns.ID.value})"
    ]

create_table_query = f"CREATE TABLE productions ({', '.join(columns)})"

# Connessione al database ed esecuzione della query
conn = sqlite3.connect(db_path)
print(f"Connesso al database: {db_path}")
c = conn.cursor()

c.execute(create_table_query)

# Commit e chiusura connessione
conn.commit()
conn.close()
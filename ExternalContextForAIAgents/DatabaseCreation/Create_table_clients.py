import sqlite3
from Model import db_path, DBClientsColumns

# Creazione della tabella `clients` utilizzando l'enum
columns = [
    f"{DBClientsColumns.ID.value} INTEGER PRIMARY KEY AUTOINCREMENT",
    f"{DBClientsColumns.NAME.value} TEXT NOT NULL UNIQUE",
    f"{DBClientsColumns.PARTITA_IVA.value} TEXT NOT NULL UNIQUE",
    f"{DBClientsColumns.EMAIL.value} TEXT",
    f"{DBClientsColumns.SEDE_LEGALE.value} TEXT",
    f"{DBClientsColumns.SETTORE.value} TEXT",
    f"{DBClientsColumns.TIPOLOGIA.value} TEXT",
    f"{DBClientsColumns.REFERENTE.value} TEXT",
    f"{DBClientsColumns.CONTATTO_REFERENTE.value} TEXT",
    f"{DBClientsColumns.NOTE.value} TEXT",
    f"{DBClientsColumns.CREATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    f"{DBClientsColumns.UPDATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
]

create_table_query = f"CREATE TABLE clients ({', '.join(columns)})"

# Esecuzione della query
conn = sqlite3.connect(db_path)
print(f"Connesso al database: {db_path}")
c = conn.cursor()

c.execute(create_table_query)

# Commit e chiusura connessione
conn.commit()
conn.close()

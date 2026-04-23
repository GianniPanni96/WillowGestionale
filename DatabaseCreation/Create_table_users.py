from Model import db_path, DBUsersColumns
import sqlite3


# Creazione della tabella usando l'enum
columns = [
    f"{DBUsersColumns.ID.value} INTEGER PRIMARY KEY AUTOINCREMENT",
    f"{DBUsersColumns.FIRST_NAME.value} TEXT NOT NULL",
    f"{DBUsersColumns.LAST_NAME.value} TEXT NOT NULL",
    f"{DBUsersColumns.PARTITA_IVA.value} TEXT NOT NULL UNIQUE",
    f"{DBUsersColumns.CODICE_FISCALE.value} TEXT UNIQUE",
    f"{DBUsersColumns.TELEFONO.value} TEXT",
    f"{DBUsersColumns.EMAIL.value} TEXT",
    f"{DBUsersColumns.REGIME_FISCALE.value} TEXT NOT NULL",
    f"{DBUsersColumns.ANNO_APERTURA_PIVA.value} INTEGER NOT NULL",
    f"{DBUsersColumns.REDDITO_ESTERNO.value} REAL NOT NULL DEFAULT 0",
    f"{DBUsersColumns.SPESE_DEDOTTE_ESTERNE.value} REAL NOT NULL DEFAULT 0",
    f"{DBUsersColumns.CONTO_CORRENTE_ID.value} INTEGER",
    f"{DBUsersColumns.PROVIDER_FATTURE.value} TEXT NOT NULL",
    f"{DBUsersColumns.USERNAME_PROVIDER.value} TEXT",
    f"{DBUsersColumns.PASSWORD_PROVIDER.value} TEXT",
    f"{DBUsersColumns.PASSWORD_LOGIN.value} TEXT",
    f"{DBUsersColumns.STATUS.value} INTEGER NOT NULL DEFAULT active",
    f"{DBUsersColumns.LAST_YEAR_IRPEF_ACCONTO.value} REAL NOT NULL DEFAULT 0",
    f"{DBUsersColumns.LAST_YEAR_INPS_ACCONTO.value} REAL NOT NULL DEFAULT 0",
    f"{DBUsersColumns.PHOTO_PATH.value} TEXT",
    f"{DBUsersColumns.CREATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    f"{DBUsersColumns.UPDATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    f"FOREIGN KEY ({DBUsersColumns.CONTO_CORRENTE_ID.value}) REFERENCES accounts (id)"
]

create_table_query = f"CREATE TABLE users ({', '.join(columns)})"

# Esecuzione della query
conn = sqlite3.connect(db_path)
print(f"Connesso al database: {db_path}")
c = conn.cursor()

c.execute(create_table_query)

# Commit e chiusura connessione
conn.commit()
conn.close()

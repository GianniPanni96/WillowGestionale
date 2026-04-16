from Model import db_path, DBExpensesColumns, DBAccountsColumns, DBSuppliersColumns, DBUsersColumns
import sqlite3


#Creazione della tabella `invoices` utilizzando l'enum
columns = [
    f"{DBSuppliersColumns.ID.value} INTEGER PRIMARY KEY AUTOINCREMENT",
    f"{DBSuppliersColumns.NAME.value} TEXT NOT NULL UNIQUE",
    f"{DBSuppliersColumns.PARTITA_IVA.value} TEXT",
    f"{DBSuppliersColumns.SEDE.value} TEXT",
    f"{DBSuppliersColumns.CONTATTO.value} TEXT",
    f"{DBSuppliersColumns.CATEGORIA.value} TEXT NOT NULL",
    f"{DBSuppliersColumns.NOTE.value} TEXT",
    f"{DBExpensesColumns.created_at.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    f"{DBExpensesColumns.updated_at.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
]

create_table_query = f"CREATE TABLE suppliers ({', '.join(columns)})"

# Connessione al database ed esecuzione della query
conn = sqlite3.connect(db_path)
print(f"Connesso al database: {db_path}")
c = conn.cursor()

c.execute(create_table_query)

# Commit e chiusura connessione
conn.commit()
conn.close()

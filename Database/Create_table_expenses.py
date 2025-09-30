from Model import db_path, DBExpensesColumns, DBAccountsColumns, DBSuppliersColumns, DBUsersColumns, DBInvoicesColumns
import sqlite3


#Creazione della tabella `invoices` utilizzando l'enum
columns = [
    f"{DBExpensesColumns.ID.value} INTEGER PRIMARY KEY AUTOINCREMENT",
    f"{DBExpensesColumns.NAME.value} TEXT NOT NULL UNIQUE",
    f"{DBExpensesColumns.USER_ID_DEDUZIONE.value} INTEGER",
    f"{DBExpensesColumns.USER_ID_ANTICIPO.value} INTEGER",
    f"{DBExpensesColumns.SUPPLIER_ID.value} INTEGER NOT NULL",
    f"{DBExpensesColumns.CATEGORY.value} TEXT NOT NULL",
    f"{DBExpensesColumns.NET_AMOUNT.value} REAL NOT NULL",
    f"{DBExpensesColumns.IVA_AMOUNT.value} REAL NOT NULL",
    f"{DBExpensesColumns.TOT_AMOUNT.value} REAL NOT NULL",
    f"{DBExpensesColumns.DATE.value} TIMESTAMP NOT NULL",
    f"{DBExpensesColumns.DEDUCIBILE.value} TEXT NOT NULL",
    f"{DBExpensesColumns.ACCOUNT_ID.value} INTEGER NOT NULL",
    f"{DBExpensesColumns.LINKED_INVOICE_ID.value} INTEGER",
    f"{DBExpensesColumns.RICORRENTE.value} BOOL DEFAULT 0",
    f"{DBExpensesColumns.created_at.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    f"{DBExpensesColumns.updated_at.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    f"FOREIGN KEY ({DBExpensesColumns.USER_ID_DEDUZIONE.value}) REFERENCES users({DBUsersColumns.ID.value})"
    f"FOREIGN KEY ({DBExpensesColumns.USER_ID_ANTICIPO.value}) REFERENCES users({DBUsersColumns.ID.value})"
    f"FOREIGN KEY ({DBExpensesColumns.SUPPLIER_ID.value}) REFERENCES suppliers({DBSuppliersColumns.ID.value})"
    f"FOREIGN KEY ({DBExpensesColumns.ACCOUNT_ID.value}) REFERENCES accounts({DBAccountsColumns.ID.value})"
    f"FOREIGN KEY ({DBExpensesColumns.LINKED_INVOICE_ID.value}) REFERENCES invoices({DBInvoicesColumns.ID.value})"

]

create_table_query = f"CREATE TABLE expenses ({', '.join(columns)})"

# Connessione al database ed esecuzione della query
conn = sqlite3.connect(db_path)
print(f"Connesso al database: {db_path}")
c = conn.cursor()

c.execute(create_table_query)

# Commit e chiusura connessione
conn.commit()
conn.close()

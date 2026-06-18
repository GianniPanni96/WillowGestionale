from Gestionale_Enums import DBUsersColumns, DBAdminColumns
from Model import db_path
import sqlite3


# Tabella admin: singolo amministratore del sistema.
# Vincolo "uno solo" applicato a livello applicativo nell'AdminController.
columns = [
    f"{DBAdminColumns.ID.value} INTEGER PRIMARY KEY AUTOINCREMENT",
    f"{DBAdminColumns.NAME.value} TEXT NOT NULL DEFAULT 'ADMIN'",
    f"{DBAdminColumns.PASSWORD_LOGIN.value} TEXT NOT NULL",
    f"{DBAdminColumns.RECOVERY_HASH.value} TEXT NOT NULL",
    f"{DBAdminColumns.CREATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    f"{DBAdminColumns.UPDATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
]

create_table_query = f"CREATE TABLE admin ({', '.join(columns)})"

conn = sqlite3.connect(db_path)
print(f"Connesso al database: {db_path}")
c = conn.cursor()
c.execute(create_table_query)
conn.commit()
conn.close()

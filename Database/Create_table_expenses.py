from Model import db_path
import sqlite3


# Connessione al database
conn = sqlite3.connect(db_path)
print(f"Connesso al database: {db_path}")

# Esempio di utilizzo
c = conn.cursor()


# Tabella spese
c.execute('''
CREATE TABLE expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    type TEXT NOT NULL,
    amount REAL NOT NULL,
    date DATE NOT NULL,
    anticipata TEXT,
    destinatario TEXT,
    deducibile TEXT,
    ivabile TEXT,
    conto_corrente_id INTEGER,
    documento_allegato TEXT,
    anno_contabile INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conto_corrente_id) REFERENCES accounts (id)
)
''')

# Commit e chiusura connessione
conn.commit()
conn.close()
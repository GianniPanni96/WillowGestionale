import os

# Lista dei file degli script da eseguire
table_scripts = [
    "Create_table_users.py",
    "Create_table_clients.py",
    "Create_table_invoices.py",
    "Create_table_expenses.py",
    "Create_table_accounts.py",
    "Create_table_payments.py",
    "Create_table_productions.py",
    "Create_table_transfers.py",
    "Create_table_suppliers.py",
    "Create_table_salaries.py",
    "Create_table_refunders.py"

]

def execute_script(script_name):
    try:
        # Usa l'esecuzione di script come se li stessi lanciando singolarmente
        exec(open(script_name).read())
        print(f"Successfully executed: {script_name}")
    except Exception as e:
        print(f"Error executing {script_name}: {e}")

def main():
    for script in table_scripts:
        if os.path.exists(script):
            execute_script(script)
        else:
            print(f"Script not found: {script}")

if __name__ == "__main__":
    main()

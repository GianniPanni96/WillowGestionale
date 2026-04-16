from datetime import date, datetime, timedelta

from Controllerss.Account_controller import AccountController
from Controllerss.Supplier_controller import SupplierController
from Gestionale_Enums import*
from Model import DatabaseModel
from QueryServices.Account_query_service import AccountQueryService
from QueryServices.Expenses_query_service import ExpenseQueryService
from QueryServices.Invoices_query_service import InvoiceQueryService
from QueryServices.Suppliers_query_service import SupplierQueryService
from QueryServices.Users_query_service import UserQueryService
from Utils.Controller_utils import ControllerUtils
from Utils.Validation_utils import ValidationUtils


class ExpenseController:
    def __init__(
        self,
        db_model: DatabaseModel,
        user_query_service: UserQueryService,
        account_controller: AccountController,
        account_query_service: AccountQueryService,
        supplier_controller:SupplierController,
        supplier_query_service: SupplierQueryService,
        invoices_query_service: InvoiceQueryService,
        expenses_query_service: ExpenseQueryService,
        recurring_expenses_settings,
        catalogo_elenchi,
    ):
        self.db_model = db_model
        self.user_query_service:UserQueryService = user_query_service
        self.account_controller: AccountController = account_controller
        self.account_query_service:AccountQueryService = account_query_service
        self.supplier_controller = supplier_controller
        self.supplier_query_service:SupplierQueryService = supplier_query_service
        self.invoices_query_service:InvoiceQueryService = invoices_query_service
        self.expenses_query_service:ExpenseQueryService = expenses_query_service
        self.recurring_expenses_settings = recurring_expenses_settings
        self.catalogo_elenchi = catalogo_elenchi

        self.create_recurring_expenses()

    def save_expense(self, expense_data):
        required_fields = {DBExpensesColumns.NAME.value, DBExpensesColumns.TOT_AMOUNT.value}
        missing_fields = [field for field in required_fields if not expense_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        spesa_lorda = expense_data.get(DBExpensesColumns.TOT_AMOUNT.value)
        if not ValidationUtils.validate_amount(spesa_lorda):
            return False, "L'importo lordo non e valido"

        user_id_anticipo = None
        user_name = expense_data.get("QUALCUNO HA ANTICIPATO?")
        if user_name and len(user_name.split(" ")) >= 2:
            user_first = user_name.split(" ")[0]
            user_last = user_name.split(" ")[1]
            user = self.user_query_service.retrieve_user_map_by_fullname(user_first, user_last)
            user_id_anticipo = user[DBUsersColumns.ID.value]

        user_id_deduzione = None
        user_name = expense_data.get("DEDUZIONE A CARICO")
        if user_name is not None and len(user_name.split(" ")) >= 2:
            user_first = user_name.split(" ")[0]
            user_last = user_name.split(" ")[1]
            user = self.user_query_service.retrieve_user_map_by_fullname(user_first, user_last)
            user_id_deduzione = user[DBUsersColumns.ID.value]

        invoice_id = None
        invoice_name = expense_data.get("FATTURA ASSOCIATA")
        if invoice_name is not None:
            invoice = self.invoices_query_service.retrieve_invoice_map_by_name(invoice_name)
            if invoice:
                invoice_id = invoice[DBInvoicesColumns.ID.value]

        aliquota_iva = float(expense_data.get("ALIQUOTA IVA"))
        spesa_netta = float(spesa_lorda) / (1 + aliquota_iva)
        iva = float(spesa_lorda) - spesa_netta

        supplier_id = None
        supplier_name = expense_data.get("NOME FORNITORE")
        if supplier_name:
            supplier = self.supplier_query_service.retrieve_supplier_map_by_name(supplier_name)
            supplier_id = supplier[DBSuppliersColumns.ID.value]

        conto_id = None
        conto_name = expense_data.get("CONTO")
        if conto_name:
            conto = self.account_query_service.retrieve_account_map_by_name(conto_name)
            conto_id = conto[DBAccountsColumns.ID.value]

        nome_spesa = supplier_name + " - " + expense_data.get(DBExpensesColumns.NAME.value)

        expense_data_prepared = {
            DBExpensesColumns.NAME.value: nome_spesa,
            DBExpensesColumns.USER_ID_ANTICIPO.value: user_id_anticipo,
            DBExpensesColumns.USER_ID_DEDUZIONE.value: user_id_deduzione,
            DBExpensesColumns.SUPPLIER_ID.value: supplier_id,
            DBExpensesColumns.CATEGORY.value: expense_data.get(DBExpensesColumns.CATEGORY.value),
            DBExpensesColumns.NET_AMOUNT.value: spesa_netta,
            DBExpensesColumns.IVA_AMOUNT.value: iva,
            DBExpensesColumns.TOT_AMOUNT.value: float(spesa_lorda),
            DBExpensesColumns.DATE.value: expense_data.get(DBExpensesColumns.DATE.value),
            DBExpensesColumns.DEDUCIBILE.value: expense_data.get(DBExpensesColumns.DEDUCIBILE.value),
            DBExpensesColumns.ACCOUNT_ID.value: conto_id,
            DBExpensesColumns.LINKED_INVOICE_ID.value: invoice_id,
        }

        try:
            self.db_model.add_expense(**expense_data_prepared)
            self.update_aggregate_data()
            return True, "Spesa salvata con successo!"
        except Exception as e:
            return False, f"Errore durante il salvataggio: {str(e)}"

    def update_expense(self, expense_id, expense_data):
        try:
            if not expense_id or not isinstance(expense_id, int):
                return False, "ID rimborso non valido. Deve essere un intero positivo."

            required_fields = {
                DBExpensesColumns.NET_AMOUNT.value,
                DBExpensesColumns.TOT_AMOUNT.value,
                DBExpensesColumns.IVA_AMOUNT.value,
            }
            missing_fields = [field for field in required_fields if not expense_data.get(field)]
            if missing_fields:
                return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

            if DBExpensesColumns.NET_AMOUNT.value in expense_data:
                amount = expense_data[DBExpensesColumns.NET_AMOUNT.value]
                if amount and not ValidationUtils.validate_amount(amount):
                    return False, "L'importo netto inserito non e valido."

            if DBExpensesColumns.TOT_AMOUNT.value in expense_data:
                amount = expense_data[DBExpensesColumns.TOT_AMOUNT.value]
                if amount and not ValidationUtils.validate_amount(amount):
                    return False, "L'importo lordo inserito non e valido."

            if DBExpensesColumns.IVA_AMOUNT.value in expense_data:
                amount = expense_data[DBExpensesColumns.IVA_AMOUNT.value]
                if amount and not ValidationUtils.validate_amount(amount):
                    return False, "L'importo iva inserito non e valido."

            if expense_data[DBExpensesColumns.CATEGORY.value] != dict(self.catalogo_elenchi["expenses_category"]).get("PRODUCTION_EXPENSE"):
                expense_data.pop(DBExpensesColumns.LINKED_INVOICE_ID.value, None)

            if expense_data[DBExpensesColumns.DEDUCIBILE.value] == "No":
                expense_data.pop(DBExpensesColumns.USER_ID_DEDUZIONE.value, None)

            expense_data[DBExpensesColumns.updated_at.value] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            self.db_model.update_expense(expense_id, **expense_data)
            return True, "Spesa aggiornata con successo!"
        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Errore durante l'aggiornamento della spesa: {str(e)}"

    def delete_expense(self, expense_id):
        return self.db_model.remove_expense(expense_id)

    def update_aggregate_data(self):
        return

    def create_recurring_expenses(self):
        print("\nControllo emissione spese ricorrenti...")

        today: date = datetime.today().date()
        all_expenses = self.expenses_query_service.retrieve_expenses_map_list()

        def is_same_period(freq: str, ref: date, candidate: date) -> bool:
            f = RecurringExpensesFrequencies

            if freq == f.SETTIMANALE.value:
                start = ref - timedelta(days=7)
                return start <= candidate <= ref

            if freq == f.MENSILE.value:
                return ref.year == candidate.year and ref.month == candidate.month

            if freq == f.BIMESTRALE.value:
                return ref.year == candidate.year and (ref.month - 1) // 2 == (candidate.month - 1) // 2

            if freq == f.TRIMESTRALE.value:
                return ref.year == candidate.year and (ref.month - 1) // 3 == (candidate.month - 1) // 3

            if freq == f.QUADRIMESTRALE.value:
                return ref.year == candidate.year and (ref.month - 1) // 4 == (candidate.month - 1) // 4

            if freq == f.SEMESTRALE.value:
                return ref.year == candidate.year and (ref.month - 1) // 6 == (candidate.month - 1) // 6

            if freq == f.ANNUALE.value:
                return ref.year == candidate.year

            return ref.year == candidate.year

        for _, exp in self.recurring_expenses_settings.items():
            if not exp.status:
                print(f"Emissione di {exp.description} saltata: disattiva")
                continue

            suffix = today.strftime("%d-%m-%Y")
            nominal = f"{exp.description}_{suffix}"
            prefix_norm = ControllerUtils.normalize_string_for_key(exp.description)

            found = False
            matched_name = None
            matched_date = None

            for e in all_expenses:
                name = e[DBExpensesColumns.NAME.value]
                name_part, _, date_part = name.rpartition("_")

                if not date_part:
                    continue

                if ControllerUtils.normalize_string_for_key(name_part) != prefix_norm:
                    continue

                try:
                    dt = datetime.strptime(date_part, "%d-%m-%Y").date()
                except ValueError:
                    continue

                if is_same_period(exp.frequency, today, dt):
                    found = True
                    matched_name = name
                    matched_date = dt
                    break

            if found:
                print(
                    f"Emissione di {nominal} saltata: gia presente "
                    f"({matched_name}) per il periodo {matched_date}"
                )
                continue

            acct = self.account_query_service.retrieve_account_map_by_name(exp.account)
            acct_id = acct.get(DBAccountsColumns.ID.value) if acct else None

            gross = exp.amount
            iva_rate = exp.iva
            netto = round(gross / (1 + iva_rate), 2)
            iva_amt = round(gross - netto, 2)
            deductor_id = exp.deductor if exp.deductible else None

            new_exp = {
                DBExpensesColumns.NAME.value: nominal,
                DBExpensesColumns.SUPPLIER_ID.value: self.supplier_query_service.retrieve_supplier_map_by_name(
                    exp.supplier
                )[DBSuppliersColumns.ID.value],
                DBExpensesColumns.CATEGORY.value: exp.category,
                DBExpensesColumns.NET_AMOUNT.value: netto,
                DBExpensesColumns.IVA_AMOUNT.value: iva_amt,
                DBExpensesColumns.TOT_AMOUNT.value: gross,
                DBExpensesColumns.USER_ID_DEDUZIONE.value: deductor_id,
                DBExpensesColumns.DATE.value: today.isoformat(),
                DBExpensesColumns.DEDUCIBILE.value: "Si" if exp.deductible else "No",
                DBExpensesColumns.ACCOUNT_ID.value: acct_id,
                DBExpensesColumns.RICORRENTE.value: 1,
            }

            try:
                self.db_model.add_expense(**new_exp)
                print(f"Spesa ricorrente creata: {nominal}")
            except Exception as e:
                print(f"Errore creando spesa '{nominal}': {e}")

    def add_DB_voices_for_recurring_expenses(self):
        default_sector_key = self.catalogo_elenchi["clients_business_sectors"][0][0]

        for expense in self.recurring_expenses_settings.values():
            supplier_name = expense.supplier
            account_name = expense.account

            supp_map = self.supplier_query_service.retrieve_supplier_map_by_name(supplier_name)
            if supp_map is None:
                esito, to_print = self.supplier_controller.save_supplier(
                    supplier_data={
                        DBSuppliersColumns.NAME.value: supplier_name,
                        DBSuppliersColumns.CATEGORIA.value: default_sector_key,
                    }
                )
                print(to_print)
            else:
                print(f"Fornitore '{supplier_name}' gia presente. SKIPPING")

            acc_map = self.account_query_service.retrieve_account_map_by_name(account_name)
            if acc_map is None:
                esito, to_print = self.account_controller.save_account(
                    account_data={
                        DBAccountsColumns.NAME.value: account_name,
                        DBAccountsColumns.INIT_BALANCE.value: 0,
                    }
                )
                print(to_print)
            else:
                print(f"Conto '{account_name}' gia presente. SKIPPING")

from Fatturazione_elettronica_API import FatturazioneElettronicaProvider
from Gestionale_Enums import DBUsersColumns, RegimeFiscale, UserStatus
from Model import DatabaseModel
from QueryServices.Users_query_service import UserQueryService
from AnalyzerServices.User_analyzer_service import UserAnalyzerService
from OtherServices.User_auth_service import UserAuthService
from OtherServices.User_crypto_service import UserCryptoService
from Utils.Controller_utils import ControllerUtils
from Utils.Validation_utils import ValidationUtils


class UserController:
    def __init__(
        self,
        db_model: DatabaseModel,
        fiscal_settings,
        user_query_service: UserQueryService,
        user_analyzer_service: UserAnalyzerService,
        user_crypto_service: UserCryptoService,
        user_auth_service: UserAuthService,
    ):
        self.db_model = db_model
        self.fiscal_settings = fiscal_settings
        self.user_query_service = user_query_service
        self.user_analyzer_service = user_analyzer_service
        self.user_crypto_service = user_crypto_service
        self.user_auth_service = user_auth_service

        self.required_fields = {
            DBUsersColumns.FIRST_NAME.value,
            DBUsersColumns.LAST_NAME.value,
            DBUsersColumns.PARTITA_IVA.value,
            DBUsersColumns.REGIME_FISCALE.value,
            DBUsersColumns.ANNO_APERTURA_PIVA.value,
            DBUsersColumns.PROVIDER_FATTURE.value,
        }

    def _build_required_fields(self, provider_value):
        required_fields = set(self.required_fields)
        if provider_value != FatturazioneElettronicaProvider.NESSUNO.value:
            required_fields.add(DBUsersColumns.USERNAME_PROVIDER.value)
            required_fields.add(DBUsersColumns.PASSWORD_PROVIDER.value)
        return required_fields

    def save_user(self, user_data):
        required_fields = self._build_required_fields(user_data.get(DBUsersColumns.PROVIDER_FATTURE.value))
        missing_fields = [field for field in required_fields if not user_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        if not ValidationUtils.validate_partita_iva(user_data[DBUsersColumns.PARTITA_IVA.value]):
            return False, 'La partita IVA non e valida. Deve contenere esattamente 11 cifre.'

        email = user_data.get(DBUsersColumns.EMAIL.value)
        if email and not ValidationUtils.validate_email(email):
            return False, "L'indirizzo email non e valido."

        if user_data.get(DBUsersColumns.PROVIDER_FATTURE.value) != FatturazioneElettronicaProvider.NESSUNO.value:
            try:
                username_provider = user_data.get(DBUsersColumns.USERNAME_PROVIDER.value)
                password_provider = user_data.get(DBUsersColumns.PASSWORD_PROVIDER.value)
                user_data[DBUsersColumns.USERNAME_PROVIDER.value] = (
                    self.user_crypto_service.encrypt_string(username_provider) if username_provider else None
                )
                user_data[DBUsersColumns.PASSWORD_PROVIDER.value] = (
                    self.user_crypto_service.encrypt_string(password_provider) if password_provider else None
                )
            except Exception as exc:
                print(f'Errore durante la cifratura dei dati di accesso: {exc}')
                user_data[DBUsersColumns.USERNAME_PROVIDER.value] = None
                user_data[DBUsersColumns.PASSWORD_PROVIDER.value] = None

        user_data_filtered = {
            column.value: user_data.get(column.value)
            for column in DBUsersColumns
            if column.value in user_data
        }
        user_data_filtered = {key: value for key, value in user_data_filtered.items() if value is not None}

        try:
            self.db_model.add_user(**user_data_filtered)
            return True, 'Utente salvato con successo!'
        except Exception as exc:
            return False, f'Errore durante il salvataggio: {str(exc)}'

    def delete_user_by_ID(self, user_id):
        try:
            self.db_model.delete_row('users', DBUsersColumns.ID.value, user_id)
            print(f'Utente {user_id} rimmosso con successo')
            return True, f'Utente {user_id} rimmosso con successo'
        except Exception as exc:
            return False, f"Errore durante l'eliminazione dell'utente: {str(exc)}"

    def update_user(self, user_id, user_data):
        if not user_id or not isinstance(user_id, int):
            return False, 'ID utente non valido. Deve essere un intero positivo.'

        valid_columns = {column.value for column in DBUsersColumns}
        update_fields = {key: value for key, value in user_data.items() if key in valid_columns}
        if not update_fields:
            return False, "Nessun campo valido fornito per l'aggiornamento."

        required_fields = self._build_required_fields(update_fields.get(DBUsersColumns.PROVIDER_FATTURE.value))
        missing_fields = [field for field in required_fields if not update_fields.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}."

        if DBUsersColumns.PARTITA_IVA.value in update_fields:
            if not ValidationUtils.validate_partita_iva(update_fields[DBUsersColumns.PARTITA_IVA.value]):
                return False, 'La partita IVA non e valida. Deve contenere esattamente 11 cifre.'

        if DBUsersColumns.EMAIL.value in update_fields:
            email = update_fields[DBUsersColumns.EMAIL.value]
            if email and not ValidationUtils.validate_email(email):
                return False, "L'indirizzo email non e valido."

        if DBUsersColumns.PASSWORD_LOGIN.value in update_fields:
            login_password = update_fields[DBUsersColumns.PASSWORD_LOGIN.value]
            if login_password:
                is_valid, _ = ValidationUtils.validate_password_strength(login_password)
            else:
                is_valid = True
            if login_password and not is_valid:
                return False, 'Password non valida, digitare almeno 8 caratteri'

        if DBUsersColumns.PASSWORD_LOGIN.value in update_fields:
            password_value = update_fields[DBUsersColumns.PASSWORD_LOGIN.value]
            if password_value and password_value.strip():
                try:
                    update_fields[DBUsersColumns.PASSWORD_LOGIN.value] = ControllerUtils.hash_password(password_value)
                except Exception as exc:
                    print(f"Errore durante l'hashing della password di login: {exc}")
                    return False, 'Errore durante la creazione della password di login.'
            else:
                update_fields.pop(DBUsersColumns.PASSWORD_LOGIN.value)

        if update_fields.get(DBUsersColumns.PROVIDER_FATTURE.value) != FatturazioneElettronicaProvider.NESSUNO.value:
            try:
                if DBUsersColumns.USERNAME_PROVIDER.value in update_fields:
                    update_fields[DBUsersColumns.USERNAME_PROVIDER.value] = self.user_crypto_service.encrypt_string(
                        update_fields[DBUsersColumns.USERNAME_PROVIDER.value]
                    )
                if DBUsersColumns.PASSWORD_PROVIDER.value in update_fields:
                    update_fields[DBUsersColumns.PASSWORD_PROVIDER.value] = self.user_crypto_service.encrypt_string(
                        update_fields[DBUsersColumns.PASSWORD_PROVIDER.value]
                    )
            except Exception as exc:
                print(f'Errore durante la cifratura dei dati di accesso: {exc}')
                return False, 'Errore durante la cifratura dei dati di accesso.'
        else:
            update_fields.pop(DBUsersColumns.USERNAME_PROVIDER.value, None)
            update_fields.pop(DBUsersColumns.PASSWORD_PROVIDER.value, None)

        try:
            self.db_model.update_user(user_id, **update_fields)
            return True, 'Utente aggiornato con successo!'
        except ValueError as exc:
            return False, str(exc)
        except Exception as exc:
            return False, f"Errore durante l'aggiornamento dell'utente: {str(exc)}"

    def print_utente(self, user):
        return self.user_query_service.print_utente(user)

    def print_utenti(self):
        return self.user_query_service.print_utenti()


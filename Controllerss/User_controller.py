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

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    def save_user(self, user_data):
        """Returns (success, message, info_dict) — info_dict contiene
        ``recovery_code`` quando la save ha generato uno nuovo (i.e. la
        password e' stata impostata in questa stessa call)."""
        required_fields = self._build_required_fields(user_data.get(DBUsersColumns.PROVIDER_FATTURE.value))
        missing_fields = [field for field in required_fields if not user_data.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}.", None

        if not ValidationUtils.validate_partita_iva(user_data[DBUsersColumns.PARTITA_IVA.value]):
            return False, 'La partita IVA non e valida. Deve contenere esattamente 11 cifre.', None

        email = user_data.get(DBUsersColumns.EMAIL.value)
        if email and not ValidationUtils.validate_email(email):
            return False, "L'indirizzo email non e valido.", None

        # Setup crypto per il nuovo utente: la password genera salt +
        # crypto_check + recovery code, e una chiave temporanea con cui
        # cifrare eventuali provider credentials passati nella save.
        plain_password = user_data.pop("_plain_password", None)
        recovery_code = None
        if plain_password:
            is_valid, _ = ValidationUtils.validate_password_strength(plain_password)
            if not is_valid:
                return False, 'Password non valida, digitare almeno 8 caratteri.', None
            salt = UserCryptoService.generate_salt()
            recovery_code = ControllerUtils.generate_recovery_code()
            user_data[DBUsersColumns.PASSWORD_LOGIN.value] = ControllerUtils.hash_password(plain_password)
            user_data[DBUsersColumns.CRYPTO_SALT.value] = salt
            user_data[DBUsersColumns.CRYPTO_CHECK.value] = (
                self.user_crypto_service.build_crypto_check(plain_password, salt)
            )
            user_data[DBUsersColumns.RECOVERY_HASH.value] = (
                ControllerUtils.hash_recovery_code(recovery_code)
            )

        # Provider credentials: cifrate con la chiave del nuovo utente
        # (derivata al volo dalla password); se manca la password si
        # rifiutano per coerenza.
        if user_data.get(DBUsersColumns.PROVIDER_FATTURE.value) != FatturazioneElettronicaProvider.NESSUNO.value:
            username_provider = user_data.get(DBUsersColumns.USERNAME_PROVIDER.value)
            password_provider = user_data.get(DBUsersColumns.PASSWORD_PROVIDER.value)
            if (username_provider or password_provider) and not plain_password:
                return False, (
                    "Per salvare le credenziali del provider e' necessario impostare anche "
                    "la password di login dell'utente (le credenziali vengono cifrate con "
                    "una chiave derivata da quella password)."
                ), None
            if plain_password and (username_provider or password_provider):
                temp_key_holder = UserCryptoService()
                temp_key_holder.unlock(0, plain_password, user_data[DBUsersColumns.CRYPTO_SALT.value])
                if username_provider:
                    user_data[DBUsersColumns.USERNAME_PROVIDER.value] = temp_key_holder.encrypt_string(username_provider)
                if password_provider:
                    user_data[DBUsersColumns.PASSWORD_PROVIDER.value] = temp_key_holder.encrypt_string(password_provider)
                temp_key_holder.lock()

        user_data_filtered = {
            column.value: user_data.get(column.value)
            for column in DBUsersColumns
            if column.value in user_data
        }
        user_data_filtered = {key: value for key, value in user_data_filtered.items() if value is not None}

        try:
            self.db_model.add_user(**user_data_filtered)
            info = {"recovery_code": recovery_code} if recovery_code else None
            return True, 'Utente salvato con successo!', info
        except Exception as exc:
            return False, f'Errore durante il salvataggio: {str(exc)}', None

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------

    def delete_user_by_ID(self, user_id):
        # Gating: l'eliminazione di un utente e' un'azione amministrativa.
        if not self.user_auth_service.is_admin:
            return False, "Solo l'amministratore puo' eliminare un utente."
        try:
            self.db_model.delete_row('users', DBUsersColumns.ID.value, user_id)
            print(f'Utente {user_id} rimmosso con successo')
            return True, f'Utente {user_id} rimmosso con successo'
        except Exception as exc:
            return False, f"Errore durante l'eliminazione dell'utente: {str(exc)}"

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------

    def update_user(self, user_id, user_data):
        """Returns (success, message, info_dict). ``info_dict`` contiene
        ``recovery_code`` se in questa call e' stata cambiata la password
        (e quindi e' stato generato un nuovo recovery code)."""
        if not user_id or not isinstance(user_id, int):
            return False, 'ID utente non valido. Deve essere un intero positivo.', None

        valid_columns = {column.value for column in DBUsersColumns}
        update_fields = {key: value for key, value in user_data.items() if key in valid_columns}
        if not update_fields:
            return False, "Nessun campo valido fornito per l'aggiornamento.", None

        required_fields = self._build_required_fields(update_fields.get(DBUsersColumns.PROVIDER_FATTURE.value))
        missing_fields = [field for field in required_fields if not update_fields.get(field)]
        if missing_fields:
            return False, f"I campi obbligatori mancanti sono: {', '.join(missing_fields)}.", None

        if DBUsersColumns.PARTITA_IVA.value in update_fields:
            if not ValidationUtils.validate_partita_iva(update_fields[DBUsersColumns.PARTITA_IVA.value]):
                return False, 'La partita IVA non e valida. Deve contenere esattamente 11 cifre.', None

        if DBUsersColumns.EMAIL.value in update_fields:
            email = update_fields[DBUsersColumns.EMAIL.value]
            if email and not ValidationUtils.validate_email(email):
                return False, "L'indirizzo email non e valido.", None

        # ------------ Password change / set ----------------------------
        new_plain_password = update_fields.get(DBUsersColumns.PASSWORD_LOGIN.value)
        recovery_code = None
        if new_plain_password and new_plain_password.strip():
            # Gating: se la password e' impostata per un utente diverso
            # da quello attualmente loggato come crypto session owner,
            # e' un force-reset di un'altrui password -> solo admin.
            active_user_id = self.user_crypto_service.active_user_id
            is_self_password = active_user_id == user_id
            if not is_self_password and not self.user_auth_service.is_admin:
                return False, (
                    "Solo l'amministratore puo' resettare la password di un altro utente."
                ), None
            is_valid, _ = ValidationUtils.validate_password_strength(new_plain_password)
            if not is_valid:
                return False, 'Password non valida, digitare almeno 8 caratteri.', None
            try:
                update_fields[DBUsersColumns.PASSWORD_LOGIN.value] = ControllerUtils.hash_password(new_plain_password)
            except Exception as exc:
                print(f"Errore durante l'hashing della password di login: {exc}")
                return False, 'Errore durante la creazione della password di login.', None

            # Rotate crypto: nuovo salt, nuovo check, nuovo recovery code.
            # I provider esistenti diventano ineggibili (sono cifrati
            # con la vecchia chiave dell'utente, sconosciuta a chi
            # resetta la password). Vengono svuotati esplicitamente.
            new_salt = UserCryptoService.generate_salt()
            recovery_code = ControllerUtils.generate_recovery_code()
            update_fields[DBUsersColumns.CRYPTO_SALT.value] = new_salt
            update_fields[DBUsersColumns.CRYPTO_CHECK.value] = (
                self.user_crypto_service.build_crypto_check(new_plain_password, new_salt)
            )
            update_fields[DBUsersColumns.RECOVERY_HASH.value] = (
                ControllerUtils.hash_recovery_code(recovery_code)
            )
            update_fields[DBUsersColumns.USERNAME_PROVIDER.value] = ""
            update_fields[DBUsersColumns.PASSWORD_PROVIDER.value] = ""

            # Se l'utente che sta resettando e' lo stesso target,
            # aggiorniamo la sessione in memoria con la nuova chiave.
            if self.user_crypto_service.active_user_id == user_id:
                self.user_crypto_service.unlock(user_id, new_plain_password, new_salt)
        else:
            update_fields.pop(DBUsersColumns.PASSWORD_LOGIN.value, None)

        # ------------ Provider credentials -----------------------------
        is_setting_provider = (
            update_fields.get(DBUsersColumns.PROVIDER_FATTURE.value)
            not in (None, FatturazioneElettronicaProvider.NESSUNO.value)
        )
        if is_setting_provider:
            owns_session = self.user_crypto_service.active_user_id == user_id
            if not owns_session:
                return False, (
                    "Solo l'utente proprietario puo' modificare le credenziali del provider "
                    "(la cifratura usa la sua chiave personale). Effettua il login con quell'utente."
                ), None
            try:
                if DBUsersColumns.USERNAME_PROVIDER.value in update_fields and update_fields[DBUsersColumns.USERNAME_PROVIDER.value]:
                    update_fields[DBUsersColumns.USERNAME_PROVIDER.value] = self.user_crypto_service.encrypt_string(
                        update_fields[DBUsersColumns.USERNAME_PROVIDER.value]
                    )
                if DBUsersColumns.PASSWORD_PROVIDER.value in update_fields and update_fields[DBUsersColumns.PASSWORD_PROVIDER.value]:
                    update_fields[DBUsersColumns.PASSWORD_PROVIDER.value] = self.user_crypto_service.encrypt_string(
                        update_fields[DBUsersColumns.PASSWORD_PROVIDER.value]
                    )
            except Exception as exc:
                print(f'Errore durante la cifratura dei dati di accesso: {exc}')
                return False, 'Errore durante la cifratura dei dati di accesso.', None
        else:
            update_fields.pop(DBUsersColumns.USERNAME_PROVIDER.value, None)
            update_fields.pop(DBUsersColumns.PASSWORD_PROVIDER.value, None)

        try:
            self.db_model.update_user(user_id, **update_fields)
            info = {"recovery_code": recovery_code} if recovery_code else None
            return True, 'Utente aggiornato con successo!', info
        except ValueError as exc:
            return False, str(exc), None
        except Exception as exc:
            return False, f"Errore durante l'aggiornamento dell'utente: {str(exc)}", None

    # ------------------------------------------------------------------
    # RECOVERY
    # ------------------------------------------------------------------

    def reset_password_via_recovery(self, username: str, recovery_code: str, new_password: str):
        """Verifica il recovery code dell'utente e, se corretto, imposta
        una nuova password (rotation completa: nuovo salt, nuovo check,
        nuovo recovery code; provider credentials svuotati come per
        qualsiasi cambio password). Returns (success, message, info)
        con ``info["recovery_code"]`` = nuovo code da consegnare.
        """
        user = self.user_query_service.retrieve_user_map_by_extended_name(username)
        if not user:
            return False, "Utente non trovato.", None
        stored = user.get(DBUsersColumns.RECOVERY_HASH.value)
        if not stored:
            return False, (
                "Questo utente non ha un recovery code impostato. "
                "Imposta una password dal dettaglio utente quando un altro "
                "utente sara' loggato."
            ), None
        if not ControllerUtils.verify_recovery_code(recovery_code, stored):
            return False, "Recovery code errato.", None

        user_id = int(user[DBUsersColumns.ID.value])
        # Usa update_user per la logica di rotation: gli passiamo solo i
        # campi minimi richiesti per evitare validazioni inutili.
        ok, msg, info = self.update_user(user_id, {
            DBUsersColumns.PASSWORD_LOGIN.value: new_password,
            # Re-include i campi required per evitare validation errors.
            DBUsersColumns.FIRST_NAME.value: user[DBUsersColumns.FIRST_NAME.value],
            DBUsersColumns.LAST_NAME.value: user[DBUsersColumns.LAST_NAME.value],
            DBUsersColumns.PARTITA_IVA.value: user[DBUsersColumns.PARTITA_IVA.value],
            DBUsersColumns.REGIME_FISCALE.value: user[DBUsersColumns.REGIME_FISCALE.value],
            DBUsersColumns.ANNO_APERTURA_PIVA.value: user[DBUsersColumns.ANNO_APERTURA_PIVA.value],
            DBUsersColumns.PROVIDER_FATTURE.value: FatturazioneElettronicaProvider.NESSUNO.value,
        })
        if not ok:
            return False, f"Reset fallito: {msg}", None
        return True, "Password reimpostata con successo.", info

    # ------------------------------------------------------------------
    # Debug
    # ------------------------------------------------------------------

    def print_utente(self, user):
        return self.user_query_service.print_utente(user)

    def print_utenti(self):
        return self.user_query_service.print_utenti()

"""
Servizio di autenticazione utenti.

Combina la verifica della password (hash PBKDF2 in ``users.password_login``)
con lo sblocco della crypto session per l'utente che si logga. La
crypto session viene resa attiva su ``UserCryptoService`` e da quel
momento l'app puo' cifrare/decifrare i campi sensibili dell'utente.

Migrazione legacy
-----------------
Se l'utente non ha ancora ``crypto_salt`` valorizzato (installazione
pre-update), il primo login esegue una migrazione transparente:
  - genera un nuovo salt
  - deriva la chiave dalla password
  - decifra ``username_provider`` / ``password_provider`` con la
    vecchia master key e li ricifra con la chiave per-utente
  - scrive salt, crypto_check e i campi ricifrati nel DB
"""

from __future__ import annotations

from Gestionale_Enums import DBUsersColumns
from Model import DatabaseModel
from OtherServices.User_crypto_service import UserCryptoService
from QueryServices.Users_query_service import UserQueryService
from Utils.Controller_utils import ControllerUtils


_LEGACY_HEX_FIELDS = (
    DBUsersColumns.USERNAME_PROVIDER.value,
    DBUsersColumns.PASSWORD_PROVIDER.value,
)


def _looks_legacy_cipher(value) -> bool:
    """Heuristica: i cipher prodotti dal vecchio servizio sono hex string
    di lunghezza pari e maggiore di 32 (16 byte IV + almeno un blocco)."""
    if not isinstance(value, str) or len(value) < 32 or len(value) % 2:
        return False
    try:
        bytes.fromhex(value)
        return True
    except ValueError:
        return False


class UserAuthService:
    def __init__(
        self,
        user_query_service: UserQueryService,
        db_model: DatabaseModel,
        user_crypto_service: UserCryptoService,
    ):
        self.user_query_service = user_query_service
        self.db_model = db_model
        self.user_crypto_service = user_crypto_service

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def check_password_for_login(self, username: str, password: str):
        """Verifica la password e, se ok, sblocca la crypto session.

        Returns:
            (success: bool, message: str, user_id: int)
        """
        user = self.user_query_service.retrieve_user_map_by_extended_name(username)
        if not user:
            return False, "Utente selezionato non trovato", -1

        db_hash = user.get(DBUsersColumns.PASSWORD_LOGIN.value)
        if not db_hash:
            return False, (
                "L'utente selezionato non ha impostato una password per il login.\n"
                "Imposta una password dal dettaglio dell'utente."
            ), -1

        if not ControllerUtils.verify_password(password, db_hash):
            return False, "Password errata!", -1

        user_id = int(user[DBUsersColumns.ID.value])
        try:
            self._activate_crypto_session(user, password)
        except Exception as exc:
            # Loggin OK ma sblocco crypto fallito: meglio non far proseguire,
            # altrimenti l'app andrebbe in stato incoerente.
            print(f"Errore durante lo sblocco della crypto session: {exc}")
            self.user_crypto_service.lock()
            return False, (
                "Impossibile sbloccare i dati cifrati. "
                "Contatta l'amministratore."
            ), -1

        return True, "Login Effettuato", user_id

    def logout(self) -> None:
        self.user_crypto_service.lock()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _activate_crypto_session(self, user: dict, password: str) -> None:
        user_id = int(user[DBUsersColumns.ID.value])
        salt = user.get(DBUsersColumns.CRYPTO_SALT.value)
        check = user.get(DBUsersColumns.CRYPTO_CHECK.value)

        if salt and check:
            if not self.user_crypto_service.verify_check(password, salt, check):
                raise RuntimeError("crypto_check non valido per la password fornita")
            self.user_crypto_service.unlock(user_id, password, salt)
            return

        # Caso legacy: salt mancante. Generiamo salt + sblocchiamo + migriamo.
        new_salt = self.user_crypto_service.generate_salt()
        self.user_crypto_service.unlock(user_id, password, new_salt)
        new_check = self.user_crypto_service.build_crypto_check(password, new_salt)

        updates = {
            DBUsersColumns.CRYPTO_SALT.value: new_salt,
            DBUsersColumns.CRYPTO_CHECK.value: new_check,
        }
        for field in _LEGACY_HEX_FIELDS:
            legacy_value = user.get(field)
            if not _looks_legacy_cipher(legacy_value):
                continue
            migrated = self.user_crypto_service.migrate_legacy_string(legacy_value)
            if migrated is not None:
                updates[field] = migrated

        try:
            self.db_model.update_user(user_id, **updates)
        except Exception as exc:
            # Lo sblocco e' gia' attivo in memoria, ma la persistenza
            # del salt e' fallita: al prossimo login si rifarebbe la
            # migrazione. Logghiamo ma non rompiamo la sessione.
            print(f"Attenzione: persistenza migrazione crypto fallita: {exc}")

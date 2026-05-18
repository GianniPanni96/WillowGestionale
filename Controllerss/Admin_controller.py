"""Controller per il singolo admin di sistema.

L'admin e' separato dagli utenti: non cifra dati propri, ha solo
``password_login`` (hash PBKDF2) e ``recovery_hash`` (hash PBKDF2 del
recovery code). E' previsto un unico admin: ``save_admin`` rifiuta la
creazione se ne esiste gia' uno.
"""

from __future__ import annotations

from Gestionale_Enums import ADMIN_FIXED_NAME, DBAdminColumns
from Model import DatabaseModel
from QueryServices.Admin_query_service import AdminQueryService
from Utils.Controller_utils import ControllerUtils
from Utils.Validation_utils import ValidationUtils


class AdminController:
    def __init__(
        self,
        db_model: DatabaseModel,
        admin_query_service: AdminQueryService,
    ):
        self.db_model = db_model
        self.admin_query_service = admin_query_service

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    def save_admin(self, plain_password: str):
        """Crea il singolo admin di sistema. Rifiuta se ne esiste gia' uno.
        Returns (success, message, info_dict). ``info_dict["recovery_code"]``
        contiene il recovery code in chiaro (da mostrare una volta sola).
        """
        if not plain_password:
            return False, "La password e' obbligatoria.", None
        is_valid, _ = ValidationUtils.validate_password_strength(plain_password)
        if not is_valid:
            return False, "Password non valida, digitare almeno 8 caratteri.", None
        if self.admin_query_service.admin_exists():
            return False, "Esiste gia' un amministratore di sistema.", None

        recovery_code = ControllerUtils.generate_recovery_code()
        fields = {
            DBAdminColumns.NAME.value: ADMIN_FIXED_NAME,
            DBAdminColumns.PASSWORD_LOGIN.value: ControllerUtils.hash_password(plain_password),
            DBAdminColumns.RECOVERY_HASH.value: ControllerUtils.hash_recovery_code(recovery_code),
        }
        try:
            self.db_model.add_admin(**fields)
            return True, "Amministratore creato con successo.", {"recovery_code": recovery_code}
        except Exception as exc:
            return False, f"Errore durante la creazione dell'admin: {str(exc)}", None

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------

    def update_admin_password(self, new_plain_password: str):
        """Cambia la password dell'admin (richiede che l'admin sia gia'
        autenticato, gating gestito a livello di UI/auth service).
        Rigenera anche il recovery code.
        """
        if not new_plain_password:
            return False, "La nuova password e' obbligatoria.", None
        is_valid, _ = ValidationUtils.validate_password_strength(new_plain_password)
        if not is_valid:
            return False, "Password non valida, digitare almeno 8 caratteri.", None
        admin = self.admin_query_service.retrieve_admin_map()
        if not admin:
            return False, "Nessun amministratore presente.", None

        recovery_code = ControllerUtils.generate_recovery_code()
        try:
            self.db_model.update_admin(
                int(admin[DBAdminColumns.ID.value]),
                **{
                    DBAdminColumns.PASSWORD_LOGIN.value: ControllerUtils.hash_password(new_plain_password),
                    DBAdminColumns.RECOVERY_HASH.value: ControllerUtils.hash_recovery_code(recovery_code),
                },
            )
            return True, "Password admin aggiornata.", {"recovery_code": recovery_code}
        except Exception as exc:
            return False, f"Errore durante l'aggiornamento admin: {str(exc)}", None

    # ------------------------------------------------------------------
    # RECOVERY
    # ------------------------------------------------------------------

    def reset_password_via_recovery(self, recovery_code: str, new_password: str):
        """Verifica il recovery code dell'admin e, se corretto, imposta
        una nuova password. Returns (success, message, info_dict) con
        ``info_dict["recovery_code"]`` = nuovo code da consegnare.
        """
        admin = self.admin_query_service.retrieve_admin_map()
        if not admin:
            return False, "Nessun amministratore presente.", None
        stored = admin.get(DBAdminColumns.RECOVERY_HASH.value)
        if not stored:
            return False, "Recovery code non disponibile per l'admin.", None
        if not ControllerUtils.verify_recovery_code(recovery_code, stored):
            return False, "Recovery code errato.", None
        return self.update_admin_password(new_password)

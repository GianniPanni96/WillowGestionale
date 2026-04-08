from Gestionale_Enums import DBUsersColumns
from Utils.Controller_utils import ControllerUtils


class UserAuthService:
    def __init__(self, user_query_service):
        self.user_query_service = user_query_service

    def check_password_for_login(self, username, password):
        user = self.user_query_service.retrieve_user_map_by_extended_name(username)
        if user:
            db_hash = user.get(DBUsersColumns.PASSWORD_LOGIN.value)
            if db_hash == '' or db_hash is None:
                return False, (
                    "L'utente selezionato non ha impostato una password per il login\n"
                    "Impostare uno nuova password dal dettaglio dell'utente"
                ), -1
        else:
            print('Utente selezionato non trovato')
            return False, 'Utente selezionato non trovato', -1

        if ControllerUtils.verify_password(password, db_hash):
            print('Login Effettuato')
            return True, 'Login Effettuato', int(user.get(DBUsersColumns.ID.value))

        print('Password errata!')
        return False, 'Password errata!', -1

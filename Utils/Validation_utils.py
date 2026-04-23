import re

class ValidationUtils:
    @staticmethod
    def validate_partita_iva(partita_iva):
        """Valida la partita IVA: deve contenere esattamente 11 cifre"""
        return bool(re.fullmatch(r"\d{11}", partita_iva))

    @staticmethod
    def validate_email(email):
        """Valida un indirizzo email"""
        return bool(re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email))

    @staticmethod
    def validate_phone_number(phone_number):
        """Valida che il numero di telefono sia composto solo da cifre e abbia una lunghezza accettabile."""
        return isinstance(phone_number, str) and phone_number.isdigit() and 8 <= len(phone_number) <= 15

    @staticmethod
    def validate_amount(amount):
        """
        Valida che l'importo sia una stringa che rappresenta un numero non negativo,
        con opzionalmente una parte decimale (al massimo due cifre decimali).

        Esempi di formati accettati:
          - "100"
          - "100.5"
          - "100.50"

        Ritorna True se l'input è valido, altrimenti False.
        """
        if not isinstance(amount, str):
            return False

        # Regex: una o più cifre, opzionalmente seguite da un punto e 1 o 2 cifre
        pattern = r"^-?\d+(\.\d{1,2})?$"
        return re.fullmatch(pattern, amount) is not None

    @staticmethod
    def validate_integers(int):
        """
        Valida che l'intero sia effettivamente una stringa che può essere trasformata in un intero
        """
        if not int.isdigit():
            return False
        else:
            return True

    @staticmethod
    def _row_to_map(row, database_columns):
        """Converte una singola riga in un dizionario."""
        if row is None:
            return None
        keys = [column.value for column in database_columns]
        return dict(zip(keys, row))

    @staticmethod
    def validate_password_strength(password: str) -> tuple[bool, str]:
        """
        Verifica che la password soddisfi i criteri di sicurezza.

        Args:
            password (str): La password da validare

        Returns:
            tuple[bool, str]: (True, "") se valida, (False, messaggio di errore) altrimenti
        """
        # Verifica lunghezza minima
        if len(password) < 8:
            return False, "La password deve essere lunga almeno 8 caratteri"

        # Puoi aggiungere altri criteri qui in futuro
        # Esempio:
        # if not any(c.isupper() for c in password):
        #     return False, "La password deve contenere almeno una lettera maiuscola"
        # if not any(c.islower() for c in password):
        #     return False, "La password deve contenere almeno una lettera minuscola"
        # if not any(c.isdigit() for c in password):
        #     return False, "La password deve contenere almeno un numero"

        return True, ""
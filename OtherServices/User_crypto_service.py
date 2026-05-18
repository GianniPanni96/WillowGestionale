"""
Servizio di crittografia per-utente.

Modello
-------
La chiave AES-256 con cui vengono cifrati i dati sensibili di un utente
e' **derivata dalla password di login di quell'utente** tramite PBKDF2.
Il salt e' generato la prima volta ed e' memorizzato in
``users.crypto_salt``. Non esiste alcuna "master key" hardcoded
applicabile a tutti gli utenti.

Stato
-----
Il servizio e' stateful: contiene la chiave dell'utente attualmente
loggato (``_active_key``) e l'``id`` del relativo utente
(``_active_user_id``). All'avvio dell'app la chiave non e' impostata
(la UI deve mostrare la dialog di login prima di permettere qualsiasi
operazione che richieda cifratura/decifratura).

Flusso tipico:
    crypto_service.unlock(user_id, password, salt)
    ...                                # app in uso
    crypto_service.lock()              # logout / shutdown

Migrazione legacy
-----------------
Le installazioni esistenti hanno ``username_provider`` /
``password_provider`` cifrati con la vecchia master key derivata dal
seed costante ``'Neomisia'``. Per non rompere quelle installazioni, il
servizio embedda un ``_LegacyDecryptor`` usato unicamente per
decifrare quei campi durante la migrazione (vedi
``migrate_legacy_string``). I dati ricifrati con la chiave per-utente
sostituiscono i vecchi nel DB. Una volta che ogni utente ha eseguito
il primo login post-update, la classe legacy non viene piu' invocata
e potra' essere rimossa in una release futura.
"""

from __future__ import annotations

import hashlib
import secrets

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad


# Parametri PBKDF2.
_KDF_ITERATIONS = 600_000
_KDF_HASH = "sha256"
_KEY_BYTES = 32                     # AES-256
_SALT_BYTES = 16

# Valore noto cifrato con la chiave per-utente per verificare lo
# sblocco senza decifrare dati reali.
_CHECK_PLAINTEXT = "willow-crypto-check-v1"


class CryptoSessionError(RuntimeError):
    """Sollevata quando si tenta di cifrare/decifrare senza una sessione attiva."""


class _LegacyDecryptor:
    """Decifra esclusivamente i campi cifrati con la vecchia master key."""

    _LEGACY_SEED = "Neomisia"

    def __init__(self):
        self._key = hashlib.sha256(self._LEGACY_SEED.encode()).digest()

    def decrypt(self, encrypted_hex: str) -> str | None:
        try:
            data = bytes.fromhex(encrypted_hex)
            iv, body = data[:16], data[16:]
            cipher = AES.new(self._key, AES.MODE_CBC, iv)
            return unpad(cipher.decrypt(body), AES.block_size).decode("utf-8")
        except Exception as exc:
            print(f"[legacy] decrypt fallito: {exc}")
            return None


class UserCryptoService:
    """Servizio di cifratura per-utente, con sessione attiva post-login."""

    def __init__(self):
        self._active_key: bytes | None = None
        self._active_user_id: int | None = None
        self._legacy = _LegacyDecryptor()

    # ------------------------------------------------------------------
    # Sessione
    # ------------------------------------------------------------------

    @property
    def is_unlocked(self) -> bool:
        return self._active_key is not None

    @property
    def active_user_id(self) -> int | None:
        return self._active_user_id

    def unlock(self, user_id: int, password: str, salt_hex: str) -> None:
        """Deriva la chiave dell'utente e la rende attiva nella sessione."""
        salt = bytes.fromhex(salt_hex)
        self._active_key = self._derive_key(password, salt)
        self._active_user_id = user_id

    def unlock_with_key_hex(self, user_id: int, key_hex: str) -> None:
        """Ripristina una sessione gia' sbloccata da una chiave salvata
        (usato dalla session persistence: la chiave era stata derivata
        in un login precedente)."""
        self._active_key = bytes.fromhex(key_hex)
        self._active_user_id = user_id

    @property
    def active_key_hex(self) -> str | None:
        """Esporta la chiave AES attiva come hex (per la persistenza
        della sessione). Ritorna None se nessuna sessione e' attiva."""
        if self._active_key is None:
            return None
        return self._active_key.hex()

    def lock(self) -> None:
        """Cancella chiave + user id dalla memoria del processo."""
        self._active_key = None
        self._active_user_id = None

    # ------------------------------------------------------------------
    # Bootstrap di un nuovo utente
    # ------------------------------------------------------------------

    @staticmethod
    def generate_salt() -> str:
        return secrets.token_bytes(_SALT_BYTES).hex()

    def build_crypto_check(self, password: str, salt_hex: str) -> str:
        """Cifra un valore noto con la chiave derivata, da memorizzare
        come ``users.crypto_check``. Sblocchi futuri saranno validati
        tentando di decifrarlo e confrontandolo con ``_CHECK_PLAINTEXT``.
        """
        key = self._derive_key(password, bytes.fromhex(salt_hex))
        return self._encrypt_with_key(_CHECK_PLAINTEXT, key)

    def verify_check(self, password: str, salt_hex: str, check_cipher: str) -> bool:
        try:
            key = self._derive_key(password, bytes.fromhex(salt_hex))
            return self._decrypt_with_key(check_cipher, key) == _CHECK_PLAINTEXT
        except Exception:
            return False

    # ------------------------------------------------------------------
    # API di cifratura (richiedono sessione attiva)
    # ------------------------------------------------------------------

    def encrypt_string(self, plain_text: str) -> str | None:
        if not self.is_unlocked:
            raise CryptoSessionError(
                "Crypto session non attiva: chiamare unlock() prima di cifrare."
            )
        try:
            return self._encrypt_with_key(plain_text, self._active_key)  # type: ignore[arg-type]
        except Exception as exc:
            print(f"Errore durante la crittografia: {exc}")
            return None

    def decrypt_string(self, encrypted_text: str) -> str | None:
        if not self.is_unlocked:
            raise CryptoSessionError(
                "Crypto session non attiva: chiamare unlock() prima di decifrare."
            )
        try:
            return self._decrypt_with_key(encrypted_text, self._active_key)  # type: ignore[arg-type]
        except Exception as exc:
            print(f"Errore durante la decrittografia: {exc}")
            return None

    # ------------------------------------------------------------------
    # Migrazione legacy (one-shot al primo login post-update)
    # ------------------------------------------------------------------

    def migrate_legacy_string(self, legacy_cipher: str) -> str | None:
        """Decifra ``legacy_cipher`` con la vecchia master key e ricifra
        con la chiave per-utente corrente. Ritorna il nuovo cipher hex
        oppure None se la stringa non era cifrata col vecchio schema
        (in tal caso il chiamante puo' lasciarla invariata).
        """
        if not self.is_unlocked:
            raise CryptoSessionError("Crypto session non attiva per la migrazione.")
        plain = self._legacy.decrypt(legacy_cipher)
        if plain is None:
            return None
        return self.encrypt_string(plain)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _derive_key(password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac(
            _KDF_HASH,
            password.encode("utf-8"),
            salt,
            _KDF_ITERATIONS,
            dklen=_KEY_BYTES,
        )

    @staticmethod
    def _encrypt_with_key(plain_text: str, key: bytes) -> str:
        iv = get_random_bytes(16)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        body = cipher.encrypt(pad(plain_text.encode(), AES.block_size))
        return f"{iv.hex()}{body.hex()}"

    @staticmethod
    def _decrypt_with_key(encrypted_text: str, key: bytes) -> str:
        data = bytes.fromhex(encrypted_text)
        iv, body = data[:16], data[16:]
        cipher = AES.new(key, AES.MODE_CBC, iv)
        return unpad(cipher.decrypt(body), AES.block_size).decode("utf-8")

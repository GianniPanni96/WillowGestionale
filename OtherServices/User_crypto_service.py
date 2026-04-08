import hashlib

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad


class UserCryptoService:
    def __init__(self, secret_seed: str = 'Neomisia'):
        self.secret_key = hashlib.sha256(secret_seed.encode()).digest()

    def encrypt_string(self, plain_text: str) -> str | None:
        try:
            iv = get_random_bytes(16)
            cipher = AES.new(self.secret_key, AES.MODE_CBC, iv)
            encrypted_data = cipher.encrypt(pad(plain_text.encode(), AES.block_size))
            return f'{iv.hex()}{encrypted_data.hex()}'
        except Exception as exc:
            print(f'Errore durante la crittografia: {exc}')
            return None

    def decrypt_string(self, encrypted_text: str) -> str | None:
        try:
            encrypted_bytes = bytes.fromhex(encrypted_text)
            iv = encrypted_bytes[:16]
            encrypted_data = encrypted_bytes[16:]
            cipher = AES.new(self.secret_key, AES.MODE_CBC, iv)
            plain_data = unpad(cipher.decrypt(encrypted_data), AES.block_size)
            return plain_data.decode('utf-8')
        except Exception as exc:
            print(f'Errore durante la decrittografia: {exc}')
            return None

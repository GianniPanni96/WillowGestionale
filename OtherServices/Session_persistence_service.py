"""Persistenza della sessione di login tra chiusure dell'app.

Salva su disco (in ``storage_root/session.bin``) un piccolo blob che
contiene:
  - tipo di sessione (utente / admin)
  - user_id (oppure -1 per l'admin)
  - timestamp di scadenza
  - chiave AES per-utente (hex) per ripristinare la crypto session

Sicurezza
---------
Su Windows il blob viene protetto con ``DPAPI`` (CurrentUser scope):
solo lo stesso utente Windows sulla stessa macchina puo' decifrare il
file. Se la DPAPI non e' disponibile la persistenza viene
silenziosamente disabilitata (nessun file creato, ``load_session()``
ritorna sempre None) — preferiamo non scrivere su disco un blob in
chiaro che contiene la chiave AES.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import os
from datetime import datetime, timedelta
from pathlib import Path


KIND_USER = "user"
KIND_ADMIN = "admin"


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _is_windows() -> bool:
    return os.name == "nt"


def _dpapi_protect(plain: bytes) -> bytes | None:
    if not _is_windows():
        return None
    try:
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        in_blob = _DataBlob(len(plain), ctypes.cast(ctypes.c_char_p(plain), ctypes.POINTER(ctypes.c_char)))
        out_blob = _DataBlob()
        ok = crypt32.CryptProtectData(
            ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
        )
        if not ok:
            return None
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            kernel32.LocalFree(out_blob.pbData)
    except Exception as exc:
        print(f"[session] DPAPI protect failed: {exc}")
        return None


def _dpapi_unprotect(cipher: bytes) -> bytes | None:
    if not _is_windows():
        return None
    try:
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        in_blob = _DataBlob(len(cipher), ctypes.cast(ctypes.c_char_p(cipher), ctypes.POINTER(ctypes.c_char)))
        out_blob = _DataBlob()
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
        )
        if not ok:
            return None
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            kernel32.LocalFree(out_blob.pbData)
    except Exception as exc:
        print(f"[session] DPAPI unprotect failed: {exc}")
        return None


class SessionPersistenceService:
    def __init__(self, session_file_path: Path):
        self.session_file_path = Path(session_file_path)

    def is_supported(self) -> bool:
        """La persistenza richiede DPAPI (Windows)."""
        return _is_windows()

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def save_user_session(self, user_id: int, crypto_key_hex: str, minutes: int) -> bool:
        payload = {
            "kind": KIND_USER,
            "user_id": int(user_id),
            "crypto_key_hex": crypto_key_hex,
            "expires_at": (datetime.now() + timedelta(minutes=minutes)).isoformat(),
        }
        return self._write(payload)

    def save_admin_session(self, minutes: int) -> bool:
        payload = {
            "kind": KIND_ADMIN,
            "user_id": -1,
            "expires_at": (datetime.now() + timedelta(minutes=minutes)).isoformat(),
        }
        return self._write(payload)

    def load_session(self) -> dict | None:
        """Ritorna il payload se la sessione e' valida e non scaduta,
        altrimenti None (e in tal caso cancella il file)."""
        if not self.session_file_path.exists():
            return None
        try:
            with open(self.session_file_path, "rb") as fh:
                cipher = fh.read()
        except OSError:
            return None

        plain = _dpapi_unprotect(cipher)
        if plain is None:
            self.clear_session()
            return None

        try:
            payload = json.loads(plain.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self.clear_session()
            return None

        expires_at_str = payload.get("expires_at", "")
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
        except (ValueError, TypeError):
            self.clear_session()
            return None

        if datetime.now() >= expires_at:
            self.clear_session()
            return None

        return payload

    def clear_session(self) -> None:
        try:
            if self.session_file_path.exists():
                self.session_file_path.unlink()
        except OSError as exc:
            print(f"[session] cancellazione fallita: {exc}")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _write(self, payload: dict) -> bool:
        if not self.is_supported():
            print("[session] persistenza non supportata su questa piattaforma")
            return False
        try:
            plain = json.dumps(payload).encode("utf-8")
        except (TypeError, ValueError) as exc:
            print(f"[session] serializzazione fallita: {exc}")
            return False

        cipher = _dpapi_protect(plain)
        if cipher is None:
            return False

        try:
            self.session_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.session_file_path, "wb") as fh:
                fh.write(cipher)
            return True
        except OSError as exc:
            print(f"[session] scrittura fallita: {exc}")
            return False

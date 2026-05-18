"""Audit log delle azioni dell'amministratore di sistema.

Formato: JSONL (un record JSON per riga) — append-only. Vive accanto
ai file di configurazione, in ``storage_root``. Una riga di esempio:

    {"timestamp": "2026-05-18T01:23:45.123456", "event": "admin_login_success"}

Il logger e' best-effort: se la scrittura fallisce viene stampato un
warning ma non si interrompe il flusso di login/logout (l'audit non
deve impedire all'utente di accedere al sistema).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class AdminAuditLog:
    EVENT_LOGIN_SUCCESS = "admin_login_success"
    EVENT_LOGIN_FAILURE = "admin_login_failure"
    EVENT_LOGOUT = "admin_logout"

    def __init__(self, log_file_path: Path):
        self.log_file_path = Path(log_file_path)

    # ------------------------------------------------------------------
    # API pubblica
    # ------------------------------------------------------------------

    def log_login_success(self) -> None:
        self._append(self.EVENT_LOGIN_SUCCESS)

    def log_login_failure(self, reason: str | None = None) -> None:
        extra = {"reason": reason} if reason else None
        self._append(self.EVENT_LOGIN_FAILURE, extra=extra)

    def log_logout(self) -> None:
        self._append(self.EVENT_LOGOUT)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _append(self, event: str, extra: dict | None = None) -> None:
        record = {
            "timestamp": datetime.now().isoformat(timespec="microseconds"),
            "event": event,
        }
        if extra:
            record.update(extra)
        try:
            self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_file_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            # Best-effort: l'audit non deve mai bloccare il flusso.
            print(f"[AdminAuditLog] scrittura fallita: {exc}")

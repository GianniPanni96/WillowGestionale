"""Servizio di lettura per il singolo admin di sistema."""

from __future__ import annotations

from Gestionale_Enums import DBAdminColumns
from Model import DatabaseModel
from Utils.Controller_utils import ControllerUtils


class AdminQueryService:
    def __init__(self, db_model: DatabaseModel):
        self.db_model = db_model

    def admin_exists(self) -> bool:
        return self.db_model.count_admin() > 0

    def retrieve_admin_map(self) -> dict | None:
        row = self.db_model.fetch_admin()
        if not row:
            return None
        return ControllerUtils.row_to_map(row, DBAdminColumns)

    def get_password_hash(self) -> str | None:
        admin = self.retrieve_admin_map()
        if not admin:
            return None
        return admin.get(DBAdminColumns.PASSWORD_LOGIN.value)

    def get_recovery_hash(self) -> str | None:
        admin = self.retrieve_admin_map()
        if not admin:
            return None
        return admin.get(DBAdminColumns.RECOVERY_HASH.value)

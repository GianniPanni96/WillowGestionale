"""Finestra di visualizzazione del log accessi amministratore.

Legge ``admin_audit.jsonl``, ordina i record dal piu' recente al meno
recente, e li raggruppa per mese calendario con intestazioni visive.
"""

from __future__ import annotations

import json
from datetime import datetime
from itertools import groupby
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from App_context import AppContext


_MONTH_NAMES_IT = [
    "", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]

_EVENT_LABELS = {
    "admin_login_success": "Login riuscito",
    "admin_login_failure": "Tentativo di login fallito",
    "admin_logout": "Logout",
}

_FAILURE_REASONS = {
    "wrong_password": "password errata",
    "no_admin_in_db": "nessun admin nel database",
    "admin_password_not_set": "password non impostata",
    "admin_service_not_configured": "servizio admin non configurato",
}


def _load_records(log_path: Path) -> list[dict]:
    if not log_path.exists():
        return []
    records = []
    try:
        with open(log_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass
    records.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return records


def _month_key(record: dict) -> tuple[int, int]:
    ts = record.get("timestamp", "")
    try:
        dt = datetime.fromisoformat(ts)
        return (dt.year, dt.month)
    except (ValueError, TypeError):
        return (0, 0)


def _format_timestamp(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%d/%m/%Y  %H:%M:%S")
    except (ValueError, TypeError):
        return ts


def _format_timestamp_parts(ts: str) -> tuple[str, str]:
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%d/%m/%Y"), dt.strftime("%H:%M:%S")
    except (ValueError, TypeError):
        return ts, ""


def _event_text(record: dict) -> str:
    event = record.get("event", "")
    label = _EVENT_LABELS.get(event, event)
    if event == "admin_login_failure":
        reason_code = record.get("reason", "")
        reason_label = _FAILURE_REASONS.get(reason_code, reason_code)
        if reason_label:
            label = f"{label}  ({reason_label})"
    return label


class QTAdminAuditLogDialog(QDialog):
    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.setWindowTitle("Log Accessi Amministratore")
        self.resize(560, 620)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        log_path = self.app_context.admin_audit_log.log_file_path
        records = _load_records(log_path)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        outer.addWidget(scroll, stretch=1)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(4)
        scroll.setWidget(content)

        if not records:
            empty = QLabel("Nessun accesso registrato.")
            empty.setAlignment(Qt.AlignCenter)
            content_layout.addWidget(empty)
            content_layout.addStretch(1)
        else:
            for (year, month), group in groupby(records, key=_month_key):
                content_layout.addWidget(self._make_month_header(year, month))
                for record in group:
                    content_layout.addWidget(self._make_entry_row(record))
                content_layout.addSpacing(8)
            content_layout.addStretch(1)

        close_btn = QPushButton("Chiudi")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        outer.addWidget(close_btn, alignment=Qt.AlignRight)

    def _make_month_header(self, year: int, month: int) -> QWidget:
        if year == 0:
            label_text = "Data sconosciuta"
        else:
            month_name = _MONTH_NAMES_IT[month] if 1 <= month <= 12 else str(month)
            label_text = f"{month_name} {year}"

        label = QLabel(label_text)
        font = QFont()
        font.setBold(True)
        font.setPointSize(11)
        label.setFont(font)
        label.setStyleSheet(
            "background-color: palette(mid);"
            "color: palette(window-text);"
            "padding: 4px 8px;"
            "border-radius: 4px;"
        )
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return label

    def _make_entry_row(self, record: dict) -> QWidget:
        date_text, time_text = _format_timestamp_parts(record.get("timestamp", ""))
        event_text = _event_text(record)

        event_name = record.get("event", "")
        if event_name == "admin_login_success":
            dot_color = "#4caf50"
        elif event_name == "admin_login_failure":
            dot_color = "#f44336"
        else:
            dot_color = "#9e9e9e"

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 6, 8, 6)
        row_layout.setSpacing(12)

        ts_widget = QWidget()
        ts_layout = QVBoxLayout(ts_widget)
        ts_layout.setContentsMargins(0, 0, 0, 0)
        ts_layout.setSpacing(0)
        date_label = QLabel(date_text)
        date_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        time_label = QLabel(time_text)
        time_label.setStyleSheet("color: palette(dark); font-size: 12px;")
        ts_layout.addWidget(date_label)
        ts_layout.addWidget(time_label)
        ts_widget.setFixedWidth(110)

        event_label = QLabel(f"● {event_text}")
        event_label.setStyleSheet(f"color: {dot_color}; font-weight: bold; font-size: 13px;")
        event_label.setWordWrap(True)

        row_layout.addWidget(ts_widget)
        row_layout.addWidget(event_label, stretch=1)

        row.setStyleSheet(
            "QWidget { border-bottom: 1px solid palette(mid); }"
        )
        return row

"""Utility condivise lato view, neutre rispetto al framework UI.

Contiene solo cio' che e' usato dalla UI Qt (``QTViews/``):

* ``ViewUtils.EventBusKeys``: chiavi degli eventi pubblicati sull'event bus
  dell'app (es. richieste di apertura tab di dettaglio, login/logout).
* ``ViewUtils.split_string_by_length``: helper per spezzare etichette
  troppo lunghe inserendo un newline vicino alla meta'.

Nessuna dipendenza da tkinter/customtkinter: il modulo deve restare
importabile prima di PySide6 senza side effect.
"""

from enum import Enum


class ViewUtils:

    class EventBusKeys(Enum):
        SHOW_INVOICE_DETAIL = "SHOW_INVOICE_DETAIL"
        SHOW_SALARY_DETAIL = "SHOW_SALARY_DETAIL"
        SHOW_PRODUCTION_DETAIL = "SHOW_PRODUCTION_DETAIL"
        SHOW_REFUND_DETAIL = "SHOW_REFUND_DETAIL"
        SHOW_EXPENSE_DETAIL = "SHOW_EXPENSE_DETAIL"
        SHOW_PAYMENT_DETAIL = "SHOW_PAYMENT_DETAIL"
        LOGIN_STATUS_CHANGED = "LOGIN_STATUS_CHANGED"
        SHOW_ACCOUNT_TAB = "SHOW_ACCOUNT_TAB"

    @staticmethod
    def split_string_by_length(text: str, max_length: int) -> str:
        """Inserisce un newline vicino alla meta' di ``text`` (solo tra parole) se eccede ``max_length``."""
        if len(text) <= max_length:
            return text

        words = text.split()
        current_length = 0
        split_index = -1

        for i, word in enumerate(words):
            current_length += len(word) + 1
            if current_length >= max_length // 2:
                split_index = i
                break

        if split_index == -1 or split_index == len(words) - 1:
            return text

        return " ".join(words[:split_index + 1]) + "\n" + " ".join(words[split_index + 1:])

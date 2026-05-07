from datetime import datetime

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QRect
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QStyledItemDelegate

from Gestionale_Enums import (
    InvoiceRateizzSatus,
    InvoiceSatus,
    Rateizzazione,
)
from Model import (
    DBClientsColumns,
    DBInvoicesColumns,
    DBPaymentsColumns,
    DBProductionsColumns,
    DBUsersColumns,
)
from Utils.Controller_utils import ControllerUtils


# Coerenti con InvoicesViewH.InvoicesStatusColors del lato customtkinter.
COLOR_CRITICAL = "#f52f2f"
COLOR_WARNING = "#e39e27"
COLOR_GOOD = "#2ca31c"
COLOR_STORNATA = "#2444d4"
COLOR_NOT_EXISTING = "#424242"
COLOR_NORMAL = None


def _invert_date_string(date_str):
    if not date_str or "-" not in date_str:
        return date_str or ""
    parts = date_str.split("-")
    if len(parts) != 3:
        return date_str
    return f"{parts[2]}-{parts[1]}-{parts[0]}"


def _status_color(status_value, num_rate):
    try:
        is_rateizzata = int(num_rate) == int(Rateizzazione.TRE.value)
    except (TypeError, ValueError):
        is_rateizzata = False

    if is_rateizzata:
        if status_value == InvoiceRateizzSatus.PAGATA.value:
            return COLOR_GOOD
        if status_value == InvoiceRateizzSatus.CRITICA.value:
            return COLOR_WARNING
        if status_value == InvoiceRateizzSatus.SCADUTA.value:
            return COLOR_CRITICAL
        if status_value == InvoiceSatus.STORNATA.value:
            return COLOR_STORNATA
        return COLOR_NORMAL

    if status_value in (InvoiceSatus.SALDATA.value, InvoiceRateizzSatus.PAGATA.value):
        return COLOR_GOOD
    if status_value == InvoiceSatus.SCADUTA.value:
        return COLOR_CRITICAL
    if status_value == InvoiceSatus.STORNATA.value:
        return COLOR_STORNATA
    return COLOR_NORMAL


def _rate_colors(invoice_with_payments):
    if not invoice_with_payments:
        return [COLOR_NOT_EXISTING, COLOR_NOT_EXISTING, COLOR_NOT_EXISTING]

    fattura = invoice_with_payments[0]
    today = datetime.today().date()

    scadenze = (
        fattura[DBInvoicesColumns.DATA_SCADENZA_1.value],
        fattura[DBInvoicesColumns.DATA_SCADENZA_2.value],
        fattura[DBInvoicesColumns.DATA_SCADENZA_3.value],
    )

    try:
        netto = float(fattura[DBInvoicesColumns.NETTO_A_PAGARE.value])
        num_rate = int(fattura[DBInvoicesColumns.NUMERO_RATE.value])
        importo_per_rata = netto / num_rate
    except (TypeError, ValueError, ZeroDivisionError):
        return [COLOR_NOT_EXISTING, COLOR_NOT_EXISTING, COLOR_NOT_EXISTING]

    pagamenti = {1: 0.0, 2: 0.0, 3: 0.0}
    for payment in invoice_with_payments:
        try:
            r = int(payment[DBPaymentsColumns.LINKED_RATA.value])
            a = float(payment[DBPaymentsColumns.PAYMENT_AMOUNT.value])
        except (TypeError, ValueError, KeyError):
            continue
        if r in pagamenti:
            pagamenti[r] += a

    def color_for(due_date_str, payment_sum):
        if payment_sum > 0:
            if payment_sum >= importo_per_rata or (importo_per_rata - payment_sum) < 5:
                return COLOR_GOOD
            return COLOR_WARNING
        due_date = ControllerUtils.parse_date(due_date_str)
        if due_date is None:
            return COLOR_NOT_EXISTING
        if today > due_date:
            return COLOR_CRITICAL
        if today == due_date:
            return COLOR_WARNING
        return COLOR_NORMAL

    colors = [color_for(scadenze[0], pagamenti[1])]
    if scadenze[1] is not None and scadenze[2] is not None:
        colors.append(color_for(scadenze[1], pagamenti[2]))
        colors.append(color_for(scadenze[2], pagamenti[3]))
    else:
        colors.append(COLOR_NOT_EXISTING)
        colors.append(COLOR_NOT_EXISTING)
    return colors


class InvoicesTableModel(QAbstractTableModel):
    """
    Modello dati delle fatture per QTableView.

    Tutti i valori per ogni riga sono pre-calcolati una sola volta.
    La QTableView non istanzia widget per riga: chiede al modello solo le
    celle visibili sullo schermo, riciclando le stesse strutture di rendering.
    """

    HEADERS = [
        "NOME",
        "CLIENTE",
        "UTENTE",
        "PRODUZIONE",
        "DATA EMISSIONE",
        "STATO",
        "RATE",
        "NETTO A PAGARE",
        "TIPOLOGIA",
    ]

    COL_NOME = 0
    COL_CLIENTE = 1
    COL_UTENTE = 2
    COL_PRODUZIONE = 3
    COL_DATA = 4
    COL_STATO = 5
    COL_RATE = 6
    COL_NETTO = 7
    COL_TIPO = 8

    ROLE_RATE_COLORS = Qt.UserRole + 1
    ROLE_INVOICE_ID = Qt.UserRole + 2

    def __init__(self, rows, parent=None):
        super().__init__(parent)
        self._rows = rows

    @classmethod
    def build_rows(
        cls,
        invoices,
        clients_query_service,
        user_query_service,
        productions_query_service,
        invoices_query_service,
    ):
        rows = []
        for inv in invoices:
            invoice_id = inv[DBInvoicesColumns.ID.value]
            client_id = inv[DBInvoicesColumns.ID_CLIENTE.value]
            user_id = inv[DBInvoicesColumns.ID_UTENTE.value]
            prod_id = inv[DBInvoicesColumns.ID_PRODUZIONE_ASSOCIATA.value]

            client = clients_query_service.retrieve_client_map_by_id(client_id) or {}
            client_name = client.get(DBClientsColumns.NAME.value, "") or ""

            if user_id:
                user = user_query_service.retrieve_user_map_by_id(user_id) or {}
                first = user.get(DBUsersColumns.FIRST_NAME.value, "") or ""
                last = user.get(DBUsersColumns.LAST_NAME.value, "") or ""
                user_name = f"{first} {last}".strip()
            else:
                user_name = ""

            production = productions_query_service.retrieve_production_map_by_id(prod_id)
            prod_name = (
                production[DBProductionsColumns.NAME.value]
                if production
                else "Produzione non trovata"
            )

            inv_with_payments = invoices_query_service.retrieve_invoice_with_payments_map_list(
                invoice_id
            )

            try:
                netto_float = float(inv[DBInvoicesColumns.NETTO_A_PAGARE.value] or 0)
            except (TypeError, ValueError):
                netto_float = 0.0

            creation_date = inv[DBInvoicesColumns.DATA_CREAZIONE.value] or ""
            num_rate = inv[DBInvoicesColumns.NUMERO_RATE.value]
            status_value = inv[DBInvoicesColumns.STATUS.value] or ""

            rows.append(
                {
                    "id": invoice_id,
                    "name": inv[DBInvoicesColumns.NUMERO_FATTURA.value] or "",
                    "client": client_name,
                    "user": user_name,
                    "production": prod_name,
                    "creation_date": creation_date,
                    "creation_date_display": _invert_date_string(creation_date),
                    "status": status_value,
                    "status_color": _status_color(status_value, num_rate),
                    "rate_colors": _rate_colors(inv_with_payments),
                    "netto": netto_float,
                    "tipo": inv[DBInvoicesColumns.TIPO.value] or "",
                }
            )
        return rows

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == self.COL_NOME:
                return row["name"]
            if col == self.COL_CLIENTE:
                return row["client"]
            if col == self.COL_UTENTE:
                return row["user"]
            if col == self.COL_PRODUZIONE:
                return row["production"]
            if col == self.COL_DATA:
                return row["creation_date_display"]
            if col == self.COL_STATO:
                return row["status"]
            if col == self.COL_RATE:
                return ""
            if col == self.COL_NETTO:
                return f"{round(row['netto'], 2)} €"
            if col == self.COL_TIPO:
                return row["tipo"]

        if role == Qt.UserRole:
            if col == self.COL_DATA:
                return row["creation_date"]
            if col == self.COL_NETTO:
                return row["netto"]
            return self.data(index, Qt.DisplayRole)

        if role == Qt.ForegroundRole and col == self.COL_STATO:
            color = row["status_color"]
            if color:
                return QBrush(QColor(color))

        if role == self.ROLE_RATE_COLORS and col == self.COL_RATE:
            return row["rate_colors"]

        if role == self.ROLE_INVOICE_ID:
            return row["id"]

        if role == Qt.TextAlignmentRole:
            if col in (self.COL_DATA, self.COL_NETTO, self.COL_RATE, self.COL_STATO):
                return int(Qt.AlignCenter)
            return int(Qt.AlignVCenter | Qt.AlignLeft)

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.HEADERS[section]
        return None

    def find_row_by_invoice_id(self, invoice_id):
        for i, row in enumerate(self._rows):
            if row["id"] == invoice_id:
                return i
        return -1


class RateDelegate(QStyledItemDelegate):
    """Disegna i numeri 1, 2, 3 con il colore di stato della rispettiva rata."""

    def paint(self, painter, option, index):
        super().paint(painter, option, index)

        colors = index.data(InvoicesTableModel.ROLE_RATE_COLORS) or []
        rect = option.rect
        n = 3
        cell_w = rect.width() / n

        painter.save()
        for i in range(n):
            color_hex = colors[i] if i < len(colors) else None
            if color_hex:
                painter.setPen(QColor(color_hex))
            else:
                painter.setPen(option.palette.text().color())
            sub = QRect(
                int(rect.x() + i * cell_w),
                rect.y(),
                int(cell_w),
                rect.height(),
            )
            painter.drawText(sub, int(Qt.AlignCenter), str(i + 1))
        painter.restore()

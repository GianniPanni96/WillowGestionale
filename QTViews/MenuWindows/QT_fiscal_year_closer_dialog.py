from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

if TYPE_CHECKING:
    from App_context import AppContext


class QTFiscalYearCloserDialog(QDialog):
    """
    Finestra "Chiusura anno contabile".

    Equivalente di MainWindow.open_fiscal_year_closer_window legacy.
    Mostra le informazioni sull'operazione e, se confermato, esegue tutte
    le operazioni di chiusura via BookCloser, riportando un report.
    Esegue anche il check sul mese in cui può essere lanciata la chiusura.
    """

    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.book_closer = app_context.book_closer

        self.setWindowTitle("Chiusura anno contabile")
        self.resize(720, 720)
        self.setModal(True)

        self.current_exercise_year = self._determine_current_exercise_year()

        self._build_ui()

    @staticmethod
    def _determine_current_exercise_year() -> int:
        now = datetime.now()
        if now.month == 12:
            return now.year
        if now.month in (1, 2):
            return now.year - 1
        return now.year

    @staticmethod
    def is_closer_available_now() -> bool:
        """La chiusura è abilitata solo da dicembre a febbraio (come legacy)."""
        m = datetime.today().month
        return not (3 <= m <= 11)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(15, 15, 15, 15)
        root.setSpacing(15)

        title = QLabel(
            f"Stai per eseguire la chiusura dell'anno fiscale {self.current_exercise_year}."
        )
        f = title.font()
        f.setPointSize(16)
        f.setBold(True)
        title.setFont(f)
        root.addWidget(title)

        description_1 = QLabel(
            "Quest'operazione comporta:\n\n"
            "- esportazione dei dati aggregati annuali su file .csv\n"
            "- esportazione dei dati aggregati mensili su file .csv\n"
            "- salvataggio e aggiornamento del saldo dei conti al 31/12\n"
            "- esportazione dell'elenco dei movimenti bancari su file .csv\n"
        )
        root.addWidget(description_1)

        description_2 = QLabel(
            "A PARTIRE DAL 01/12 ed indipendentemente dall'avvenuta chiusura contabile dell'anno:\n\n"
            "- non sarà più possibile modificare i campi di oggetti relativi all'anno contabile passato\n"
            "- l'interfaccia mostrerà solo i dati relativi al nuovo esercizio contabile\n"
            "- il database in backend rimarrà sempre lo stesso, contenente tutti i campi inseriti, di tutti gli anni\n"
            "- sarà possibile visualizzare i vecchi esercizi via time machine (sola lettura)\n"
            "- i dati esportati saranno usati per il plotting nella tab apposita\n"
            "- NON SPOSTARE I FILE DEI DATI ESPORTATI DALLA LORO CARTELLA\n"
        )
        root.addWidget(description_2)

        prompt = QLabel("Desideri continuare?")
        f2 = prompt.font()
        f2.setBold(True)
        f2.setPointSize(13)
        prompt.setFont(f2)
        root.addWidget(prompt)

        root.addStretch(1)

        buttons = QHBoxLayout()
        cancel_btn = QPushButton("Non ora")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        buttons.addStretch(1)
        confirm_btn = QPushButton("Avanti")
        confirm_btn.clicked.connect(self._close_fiscal_year)
        buttons.addWidget(confirm_btn)
        root.addLayout(buttons)

    def _close_fiscal_year(self):
        self.book_closer.set_current_exercise_year(self.current_exercise_year)

        operations = [
            ("Esportazione movimenti bancari", self.book_closer.export_accounts_movements),
            ("Aggiornamento dati finanziari storici", self.book_closer.update_historical_financial_data),
            ("Esportazione dati annuali aggregati", self.book_closer.export_annual_data),
            ("Esportazione dati mensili aggregati", self.book_closer.export_monthly_data),
            ("Esportazione dati IVA aggregati", self.book_closer.export_trimestral_iva_data),
            ("Esportazione dati TASSE aggregati", self.book_closer.export_tax_data),
            ("Importazione saldi bancari iniziali", self.book_closer.import_initial_balances),
        ]

        results = []
        for description, op in operations:
            try:
                result = op()
                if description == "Esportazione movimenti bancari" and result is None:
                    results.append((description, False, "Restituito None"))
                else:
                    results.append((description, True, "Successo"))
            except Exception as exc:
                results.append((description, False, str(exc)))

        success_count = sum(1 for _, success, _ in results if success)
        total = len(results)
        details = "\n".join(
            f"✓ {desc}" if success else f"✗ {desc}: {msg}"
            for desc, success, msg in results
        )

        title = f"Chiusura esercizio {'completata' if success_count == total else 'parziale'} ({success_count}/{total})"
        body = f"Operazioni completate:\n\n{details}"

        if success_count == total:
            QMessageBox.information(self, title, body)
        else:
            QMessageBox.warning(self, title, body)

        # Log su console (coerente con la legacy).
        print("\n" + "=" * 60)
        print("RIEPILOGO CHIUSURA ESERCIZIO")
        print("=" * 60)
        for desc, success, msg in results:
            status = "✓ SUCCESSO" if success else "✗ FALLITO"
            print(f"{status}: {desc}")
            if not success and msg:
                print(f"  Motivo: {msg}")
        print("=" * 60)
        print(f"Operazioni completate con successo: {success_count}/{total}")

        self.accept()

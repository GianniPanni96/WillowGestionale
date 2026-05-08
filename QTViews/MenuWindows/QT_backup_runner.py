from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox, QWidget

if TYPE_CHECKING:
    from App_context import AppContext


class QTBackupRunner:
    """
    Esegue i backup manuali (DB e libri contabili) mostrando i popup di
    conferma/errore in stile Qt. Estratto dalla MainWindow legacy
    (`execute_db_backup` / `execute_books_backup`).
    """

    def __init__(self, app_context: "AppContext", parent: QWidget = None):
        self.app_context = app_context
        self.parent = parent
        self.backup_scheduler = app_context.backup_scheduler

    def run_db_backup(self):
        try:
            self.backup_scheduler.backup_gestionale_db()
        except Exception as exc:
            print(f"Errore durante l'esecuzione manuale del backup: {exc}")
            QMessageBox.critical(
                self.parent,
                "Errore",
                f"Errore durante l'esecuzione del backup manuale: {exc}",
            )
            return
        print("Esecuzione manuale del backup riuscita")
        QMessageBox.information(self.parent, "Backup", "Backup eseguito con successo.")

    def run_books_backup(self):
        success, message = self.backup_scheduler.backup_gestionale_books()
        if success:
            print("Esecuzione manuale del backup riuscita")
            QMessageBox.information(self.parent, "Backup", "Backup eseguito con successo.")
        else:
            print(f"Errore durante l'esecuzione manuale del backup: {message}")
            QMessageBox.critical(
                self.parent,
                "Errore",
                f"Errore durante l'esecuzione del backup manuale: {message}",
            )

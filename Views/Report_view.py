import customtkinter as ctk
from datetime import datetime

from App_context import AppContext
from Views.Annual_report_charts_view import AnnualReportChartsView
from Views.Monthly_report_view import MonthlyReportView


class ReportView(ctk.CTkFrame):
    def __init__(self, app_context: AppContext, tabview):
        super().__init__(tabview.tab(f"Report {datetime.now().strftime('%Y')}"))

        self.app_context = app_context
        self.tabview = tabview
        self.tab = tabview.tab(f"Report {datetime.now().strftime('%Y')}")

        self._after_ids = set()
        self._orig_after = self.after
        self.after = self._track_after
        self._is_cleaned_up = False

        self.subview_instances = {}
        self.current_subtab = None
        self.subview_factory = {
            "Dati Mensili": lambda parent: MonthlyReportView(self.app_context, parent),
            "Analisi Annuale": lambda parent: AnnualReportChartsView(self.app_context, parent),
        }

        self.main_container = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.main_container.pack(fill="both", expand=True)

        self.report_tabview = ctk.CTkTabview(self.main_container, fg_color="#2b2b2b")
        self.report_tabview.pack(fill="both", expand=True, padx=5, pady=(14, 5))
        self.report_tabview.add("Dati Mensili")
        self.report_tabview.add("Analisi Annuale")
        self.report_tabview._segmented_button.configure(font=ctk.CTkFont("Arial", 14, "bold"))

        self.current_subtab = self.report_tabview.get()
        self._load_subtab(self.current_subtab)
        self._monitor_subtab_change()

    def _load_subtab(self, tab_name: str):
        if tab_name in self.subview_instances:
            return

        tab_frame = self.report_tabview.tab(tab_name)
        for widget in tab_frame.winfo_children():
            widget.destroy()

        instance = self.subview_factory[tab_name](tab_frame)
        instance.pack(fill="both", expand=True)
        self.subview_instances[tab_name] = instance

    def _destroy_subtab(self, tab_name: str):
        instance = self.subview_instances.pop(tab_name, None)
        if instance is None:
            return

        try:
            if hasattr(instance, "cleanup"):
                instance.cleanup()
            instance.destroy()
        except Exception as exc:
            print(f"Errore nel distruggere la sottoview '{tab_name}': {exc}")

    def _switch_subtab(self, new_tab: str):
        previous_tab = self.current_subtab
        self.current_subtab = new_tab

        if previous_tab and previous_tab != new_tab:
            self._destroy_subtab(previous_tab)

        self._load_subtab(new_tab)

    def _monitor_subtab_change(self):
        if self._is_cleaned_up:
            return

        try:
            selected_tab = self.report_tabview.get()
            if selected_tab != self.current_subtab:
                self._switch_subtab(selected_tab)
        finally:
            if not self._is_cleaned_up:
                self.after(250, self._monitor_subtab_change)

    def cleanup(self):
        try:
            self._is_cleaned_up = True

            for after_id in self._after_ids:
                try:
                    self.after_cancel(after_id)
                except Exception:
                    pass
            self._after_ids.clear()

            for tab_name in list(self.subview_instances.keys()):
                self._destroy_subtab(tab_name)

            if hasattr(self, "main_container") and self.main_container.winfo_exists():
                for widget in self.main_container.winfo_children():
                    widget.destroy()
        except Exception as exc:
            print(f"Errore durante il cleanup di {self.__class__.__name__}: {exc}")

    def _track_after(self, ms, func, *args):
        after_id = self._orig_after(ms, func, *args)
        self._after_ids.add(after_id)
        return after_id

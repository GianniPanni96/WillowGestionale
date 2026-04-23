from typing import List

import customtkinter as ctk
import tkinter as tk
from enum import Enum
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.pyplot as plt
from datetime import datetime
import mplcursors

from App_context import AppContext
from Model import DatabaseModel


# ── Palette fissa: ogni anno ottiene sempre lo stesso colore ──────────────────
_YEAR_PALETTE = [
    '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
    '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
    '#F0A500', '#E17055', '#00B894', '#6C5CE7', '#FD79A8',
]

def _year_color(year: int) -> str:
    """Colore deterministico e stabile per un anno, indipendente dal range selezionato."""
    # Usiamo il modulo della palette rispetto a (anno - anno_base)
    # così anni vicini hanno colori distinti ma l'anno X ha sempre lo stesso colore.
    idx = (year - 2000) % len(_YEAR_PALETTE)
    return _YEAR_PALETTE[idx]


class AnnualData(Enum):
    """Enumerativo per i dati annuali"""
    TOTALE_FATTURATO = "Fatturato"
    SPESE = "Spese"
    MEDIA_FATTURE = "Media Fatture"
    MEDIA_ORE_PRODUZIONE = "Media h produzione"
    MEDIA_PREZZO_ORARIO = "Media prezzo orario"
    IRPEF = "Irpef"
    INPS = "Inps"

    @classmethod
    def get_display_names(cls):
        return [item.value for item in cls]

    @classmethod
    def from_display_name(cls, display_name):
        for item in cls:
            if item.value == display_name:
                return item
        raise ValueError(f"Valore non trovato: {display_name}")


class MonthlyData(Enum):
    """Enumerativo per i dati mensili"""
    FATTURATO = "Fatturato"
    SPESE = "Spese"
    ENTRATE = "Entrate"
    USCITE = "Uscite"
    SALARIO_MEDIO = "Salario Medio"

    @classmethod
    def get_display_names(cls):
        return [item.value for item in cls]

    @classmethod
    def from_display_name(cls, display_name):
        for item in cls:
            if item.value == display_name:
                return item
        raise ValueError(f"Valore non trovato: {display_name}")


class PlotView(ctk.CTkFrame):
    def __init__(self, app_context: AppContext, tabview):
        super().__init__(tabview.tab("Plots"))

        self.app_context: AppContext = app_context
        self.db_model: DatabaseModel = app_context.db_model
        self.tabview = tabview
        self.tab = tabview.tab("Plots")
        self.books_retriever = app_context.books_retriever

        # Container principale
        self.main_container = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.main_container.pack(fill='both', expand=True)

        # Sistema per tracciare gli after()
        self._after_ids = set()
        self._orig_after = self.after
        self.after = self._track_after

        self.annuale_mensile_switch_var = tk.BooleanVar(value=False)  # false è mensile

        # Variabili per il range di anni
        self.start_year_var = tk.StringVar()
        self.end_year_var = tk.StringVar()
        self.available_years = []

        # Cache per i dati
        self.current_year_monthly_data = None
        self.salary_data_cache = {}

        # Riferimento al cursore mplcursors attivo (per pulizia tra plot)
        self._active_cursor = None

        self._create_plot_tab()
        self._init_canvas()
        self._load_available_years()
        self._update_year_range_options()
        self._toggle_visualized_data_menu()

    # ─────────────────────────────────────────────────────────────────────────
    # Setup / inizializzazione
    # ─────────────────────────────────────────────────────────────────────────

    def _load_available_years(self):
        try:
            years_from_data = self.app_context.books_retriever.get_years_available()
            current_year = datetime.now().year
            if current_year not in years_from_data:
                years_from_data.append(current_year)
            self.available_years = sorted(years_from_data)
        except Exception as e:
            print(f"Errore nel caricamento degli anni disponibili: {e}")
            self.available_years = [datetime.now().year]

    def _create_plot_tab(self):
        ctk.CTkLabel(self.main_container,
                     text="Visualizza i grafici dell'andamento con granularità mensile o annuale",
                     font=("Arial", 16),
                     text_color="#e8f4f8").pack(pady=(25, 0))

        self.switch_frame = ctk.CTkFrame(self.main_container, fg_color="#2b2b2b")
        self.switch_frame.pack(fill="x", pady=(10, 0), expand=True)

        ctk.CTkLabel(self.switch_frame, text="Mensili   ", font=("Arial", 16)).pack(
            pady=(10, 0), padx=(20, 0), anchor="w", side=ctk.LEFT)
        self.annuale_mensile_switch = ctk.CTkSwitch(
            self.switch_frame, text="  Annuali", font=("Arial", 16),
            command=self._switch_mensile_annuale,
            width=200, switch_width=60, height=48, switch_height=20,
            variable=self.annuale_mensile_switch_var)
        self.annuale_mensile_switch.pack(pady=(10, 0), anchor="w", side="left")

        ctk.CTkLabel(self.switch_frame, text="Seleziona un dato\nda visualizzare: ",
                     justify="right").pack(side="left", padx=(50, 10), pady=(10, 0))

        self.visualized_data_option_menu = ctk.CTkOptionMenu(
            self.switch_frame,
            values=MonthlyData.get_display_names(),
            command=lambda v: self._plot_selected_value(v))
        self.visualized_data_option_menu.pack(side="left", pady=(10, 0))

        # Frame range anni
        self.year_range_frame = ctk.CTkFrame(self.switch_frame, fg_color="#2b2b2b")
        self.year_range_frame.pack(side="left", padx=(20, 0), pady=(10, 0))

        ctk.CTkLabel(self.year_range_frame, text="Range anni:").pack(side="left", padx=(70, 5))

        self.start_year_menu = ctk.CTkOptionMenu(
            self.year_range_frame, values=[],
            variable=self.start_year_var,
            command=lambda _: self._on_year_range_changed())
        self.start_year_menu.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(self.year_range_frame, text="-").pack(side="left")

        self.end_year_menu = ctk.CTkOptionMenu(
            self.year_range_frame, values=[],
            variable=self.end_year_var,
            command=lambda _: self._on_year_range_changed())
        self.end_year_menu.pack(side="left", padx=(10, 0))

        # Frame canvas
        self.canvas_frame = ctk.CTkFrame(self.main_container, fg_color="#2b2b2b")
        self.canvas_frame.pack(fill='both', expand=True, padx=20, pady=20)

    def _switch_mensile_annuale(self):
        self._toggle_visualized_data_menu()

    def _update_year_range_options(self):
        if not self.available_years:
            self._load_available_years()
        year_strings = [str(y) for y in self.available_years]
        self.start_year_menu.configure(values=year_strings)
        self.end_year_menu.configure(values=year_strings)
        if self.available_years:
            self.start_year_var.set(str(self.available_years[0]))
            self.end_year_var.set(str(self.available_years[-1]))

    def _on_year_range_changed(self):
        self._clear_data_cache()
        if self.start_year_var.get() and self.end_year_var.get():
            self._plot_selected_value(self.visualized_data_option_menu.get())

    # ─────────────────────────────────────────────────────────────────────────
    # Canvas & toolbar  (PUNTO 1: navigazione integrata matplotlib)
    # ─────────────────────────────────────────────────────────────────────────

    def _init_canvas(self):
        """Inizializza il canvas con toolbar di navigazione integrata."""
        self.plot_bridge_frame = tk.Frame(self.canvas_frame)
        self.plot_bridge_frame.pack(fill='both', expand=True)

        self.fig, self.ax = plt.subplots(figsize=(8, 14), facecolor='#2b2b2b')

        # Tema scuro statico
        self.fig.patch.set_facecolor('#2b2b2b')
        self.ax.set_facecolor('#2b2b2b')
        self.ax.tick_params(colors='#e8f4f8')
        self.ax.xaxis.label.set_color('#e8f4f8')
        self.ax.yaxis.label.set_color('#e8f4f8')
        self.ax.title.set_color('#e8f4f8')
        for spine in self.ax.spines.values():
            spine.set_color('white')
        self.ax.spines['top'].set_color('#2b2b2b')
        self.ax.spines['right'].set_color('#2b2b2b')

        self.graph_canvas = FigureCanvasTkAgg(self.fig, self.plot_bridge_frame)
        self.graph_canvas.draw()
        self.graph_canvas.get_tk_widget().pack(fill='both', expand=True)

        # ── Toolbar nativa matplotlib (zoom, pan, salva, home) ────────────────
        self.toolbar = NavigationToolbar2Tk(self.graph_canvas, self.plot_bridge_frame)
        self.toolbar.update()
        # Adatta l'aspetto al tema scuro
        try:
            self.toolbar.config(background='#3a3a3a')
            for child in self.toolbar.winfo_children():
                try:
                    child.config(background='#3a3a3a', foreground='#e8f4f8')
                except Exception:
                    pass
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────────
    # Plot principale
    # ─────────────────────────────────────────────────────────────────────────

    def _plot_selected_value(self, selected_value):
        if not self.available_years:
            self._load_available_years()
            self._update_year_range_options()

        is_annual = self.annuale_mensile_switch_var.get()

        if is_annual:
            data_enum = AnnualData.from_display_name(selected_value)
            mode = "Annuali"
        else:
            data_enum = MonthlyData.from_display_name(selected_value)
            mode = "Mensili"

        # Rimuovi il cursore precedente prima di ridisegnare (PUNTO 2)
        if self._active_cursor is not None:
            try:
                self._active_cursor.remove()
            except Exception:
                pass
            self._active_cursor = None

        self.ax.clear()

        # Ri-applica stile dopo clear()
        self.ax.set_facecolor('#2b2b2b')
        self.ax.tick_params(colors='#e8f4f8')
        self.ax.set_title(f'{selected_value} - {mode}', color='#e8f4f8', fontsize=14)

        if is_annual:
            self.ax.set_xlabel('Anno', color='#e8f4f8')
            self._plot_annual_data(data_enum)
        else:
            self.ax.set_xlabel('Mese', color='#e8f4f8')
            try:
                start_year = int(self.start_year_var.get())
                end_year = int(self.end_year_var.get())
            except (ValueError, AttributeError):
                start_year = self.available_years[0] if self.available_years else datetime.now().year
                end_year = self.available_years[-1] if self.available_years else datetime.now().year
            self._plot_monthly_data_multiyear(data_enum, start_year, end_year)

        self.ax.set_ylabel(selected_value, color='#e8f4f8')

        for spine in self.ax.spines.values():
            spine.set_color('#e8f4f8')

        self.ax.grid(True, alpha=0.3, color='gray', linestyle='--')

        if not is_annual and len(self.ax.lines) > 0:
            self.ax.legend(loc='upper left', facecolor='#2b2b2b',
                           edgecolor='white', labelcolor='white')

        self.graph_canvas.draw()

    # ─────────────────────────────────────────────────────────────────────────
    # Plot annuale  (PUNTO 4: larghezza fissa + ordinamento per anno)
    # ─────────────────────────────────────────────────────────────────────────

    def _plot_annual_data(self, data_enum):
        try:
            annual_df = self.app_context.books_retriever.get_annual_dataframe()

            if annual_df.empty:
                self.ax.text(0.5, 0.5, 'Nessun dato annuale disponibile',
                             ha='center', va='center', transform=self.ax.transAxes,
                             color='white', fontsize=12)
                return

            # Filtra per range anni
            if self.start_year_var.get() and self.end_year_var.get():
                try:
                    s = int(self.start_year_var.get())
                    e = int(self.end_year_var.get())
                    if s > e:
                        s, e = e, s
                    annual_df = annual_df[(annual_df['anno'] >= s) & (annual_df['anno'] <= e)]
                except Exception:
                    pass

            column_mapping = {
                AnnualData.TOTALE_FATTURATO: 'totale_fatturato',
                AnnualData.SPESE: 'totale_spese',
                AnnualData.MEDIA_FATTURE: 'media_fatture',
                AnnualData.MEDIA_ORE_PRODUZIONE: 'media_ore_per_produzione',
                AnnualData.MEDIA_PREZZO_ORARIO: 'media_prezzo_orario_produzione',
                AnnualData.IRPEF: 'irpef_willow',
                AnnualData.INPS: 'inps_willow',
            }
            column_name = column_mapping.get(data_enum)

            if column_name is None or column_name not in annual_df.columns:
                self.ax.text(0.5, 0.5, f'Dato non disponibile: {data_enum.value}',
                             ha='center', va='center', transform=self.ax.transAxes,
                             color='white', fontsize=12)
                return

            # ── Ordinamento crescente per anno (sinistra→destra) ─────────────
            annual_df = annual_df.sort_values('anno')
            years = annual_df['anno'].tolist()
            values = annual_df[column_name].tolist()

            # ── Larghezza colonne semi-fissa, posizioni numeriche ──────────────────
            n_bars = len(years)
            x_range = (n_bars - 1) if n_bars > 1 else 1
            BAR_WIDTH = min(0.1, (x_range / n_bars) * 0.8)        # larghezza fissa in unità asse X
            x_pos = list(range(len(years)))

            # colore per anno, coerente con il grafico mensile
            bar_colors = [_year_color(year) for year in years]
            bars = self.ax.bar(x_pos, values,
                               width=BAR_WIDTH,
                               color=bar_colors, alpha=0.8)

            # Etichette valori sopra le barre
            for bar, value in zip(bars, values):
                height = bar.get_height()
                self.ax.text(
                    bar.get_x() + bar.get_width() / 2., height,
                    f'{value:.0f}' if isinstance(value, (int, float)) else str(value),
                    ha='center',
                    va='bottom' if value >= 0 else 'top',
                    color='white', fontsize=10)

            # Etichette asse X = anni reali
            self.ax.set_xticks(x_pos)
            self.ax.set_xticklabels([str(y) for y in years], rotation=0)

            # Margini laterali minimi per non schiacciare le barre
            self.ax.set_xlim(-0.6, len(years) - 0.4)

            # ── PUNTO 2: tooltip sui valori delle barre ───────────────────────
            #cursor = mplcursors.cursor(bars, hover=True)

#            #@cursor.connect("add")
            #def _on_bar(sel):
            #    year_label = years[int(round(sel.target[0]))] if 0 <= int(round(sel.target[0])) < len(years) else ""
            #    sel.annotation.set_text(f"{year_label}\n{sel.target[1]:,.2f}")
            #    sel.annotation.get_bbox_patch().set(fc="#2b2b2b", alpha=0.9, ec="white")
            #    sel.annotation.set_color("white")

#            #self._active_cursor = cursor

        except Exception as e:
            self.ax.text(0.5, 0.5, f'Errore: {str(e)}',
                         ha='center', va='center', transform=self.ax.transAxes,
                         color='red', fontsize=10)

    # ─────────────────────────────────────────────────────────────────────────
    # Plot mensile multi-anno  (PUNTO 3: colore stabile per anno)
    # ─────────────────────────────────────────────────────────────────────────

    def _plot_monthly_data_multiyear(self, data_enum, start_year, end_year):
        """Plotta dati mensili come linee spezzate per più anni + curva media."""
        try:
            if start_year > end_year:
                start_year, end_year = end_year, start_year

            months = ['Gen', 'Feb', 'Mar', 'Apr', 'Mag', 'Giu',
                      'Lug', 'Ago', 'Set', 'Ott', 'Nov', 'Dic']
            x_pos = list(range(len(months)))

            scatter_targets = []  # scatter invisibili usati come target per i tooltip

            for year in range(start_year, end_year + 1):
                color = _year_color(year)
                values = self._get_monthly_data_for_year(year, data_enum)
                if not values:
                    continue

                # Linea visibile
                self.ax.plot(x_pos, values, marker='o', linewidth=2,
                             color=color, markersize=6, label=str(year))

                # Scatter invisibile sui nodi reali: è il solo target del tooltip
                sc = self.ax.scatter(x_pos, values,
                                     alpha=0,  # invisibile
                                     s=200,  # area di cattura generosa
                                     zorder=5,
                                     label='_nolegend_')
                scatter_targets.append((sc, str(year)))

            if not scatter_targets:
                self.ax.text(0.5, 0.5, 'Nessun dato disponibile per il range selezionato',
                             ha='center', va='center', transform=self.ax.transAxes,
                             color='white', fontsize=12)
                return

            # ── Curva media su tutti gli anni del CSV ─────────────────────────────
            avg_values = self._get_monthly_averages(data_enum)
            if any(v != 0.0 for v in avg_values):
                self.ax.plot(x_pos, avg_values,
                             color='#888888', linewidth=1.5,
                             linestyle='--', marker='',
                             label=f'Media storica - {datetime.now().year} escluso', zorder=3)

            self.ax.set_xticks(x_pos)
            self.ax.set_xticklabels(months)

            # ── Tooltip: solo sui nodi reali tramite gli scatter ──────────────────
            all_scatter = [sc for sc, _ in scatter_targets]
            # Mappa scatter → etichetta anno per il callback
            scatter_year_map = {id(sc): yr for sc, yr in scatter_targets}

            cursor = mplcursors.cursor(all_scatter, hover=True)

            @cursor.connect("add")
            def _on_node(sel):
                x_idx = int(round(float(sel.target[0])))
                month_label = months[x_idx] if 0 <= x_idx < len(months) else ""
                year_label = scatter_year_map.get(id(sel.artist), "")
                sel.annotation.set_text(
                    f"{year_label} – {month_label}\n{sel.target[1]:,.2f}")
                sel.annotation.get_bbox_patch().set(fc="#2b2b2b", alpha=0.9, ec="white")
                sel.annotation.set_color("white")

            self._active_cursor = cursor

        except Exception as e:
            self.ax.text(0.5, 0.5, f'Errore: {str(e)}',
                         ha='center', va='center', transform=self.ax.transAxes,
                         color='red', fontsize=10)

    # ─────────────────────────────────────────────────────────────────────────
    # Recupero dati mensili
    # ─────────────────────────────────────────────────────────────────────────

    def _get_monthly_data_for_year(self, year, data_enum):
        try:
            if year == datetime.now().year:
                return self._get_current_year_monthly_data(data_enum)
            else:
                return self._get_csv_monthly_data_for_year(year, data_enum)
        except Exception as e:
            print(f"Errore nel recupero dati per l'anno {year}: {e}")
            return None

    def _get_monthly_averages(self, data_enum: MonthlyData) -> List[float]:
        """
        Thin wrapper: mappa l'enum al nome colonna CSV e delega il calcolo
        a BooksRetriever, mantenendo la logica di retrieval fuori dalla View.
        """
        column_mapping = {
            MonthlyData.FATTURATO: 'fatturato',
            MonthlyData.SPESE: 'spese',
            MonthlyData.ENTRATE: 'entrate',
            MonthlyData.USCITE: 'uscite',
            MonthlyData.SALARIO_MEDIO: 'salario_medio_utente',
        }
        column_name = column_mapping.get(data_enum)
        if not column_name:
            return [0.0] * 12
        return self.app_context.books_retriever.get_monthly_averages(column_name)

    def _get_current_year_monthly_data(self, data_enum):
        try:
            if self.current_year_monthly_data is None:
                self.current_year_monthly_data = (
                    self.app_context.monthly_report_analyzer_service.retrieve_monthly_data())

            data_mapping = {
                MonthlyData.FATTURATO: 'fatturato',
                MonthlyData.SPESE: 'spese',
                MonthlyData.ENTRATE: 'incomes',
                MonthlyData.USCITE: 'outcomes',
                MonthlyData.SALARIO_MEDIO: 'salario_medio',
            }
            data_key = data_mapping.get(data_enum)
            if not data_key:
                return None

            if data_enum == MonthlyData.SALARIO_MEDIO:
                return self._get_current_year_salaries()

            values = []
            for month in range(1, 13):
                month_data = self.current_year_monthly_data.get(month, {})
                if 'values' in month_data and data_key in month_data['values']:
                    values.append(month_data['values'][data_key])
                else:
                    values.append(0.0)
            return values
        except Exception as e:
            print(f"Errore nel recupero dati anno corrente: {e}")
            return None

    def _get_current_year_salaries(self):
        try:
            if not self.salary_data_cache:
                for month in range(1, 13):
                    salary = self.app_context.salary_analyzer_service.calculate_mean_salary_by_month(month)
                    self.salary_data_cache[month] = salary if salary is not None else 0.0
            return [self.salary_data_cache.get(month, 0.0) for month in range(1, 13)]
        except Exception as e:
            print(f"Errore nel recupero salari: {e}")
            return [0.0] * 12

    def _get_csv_monthly_data_for_year(self, year, data_enum):
        try:
            monthly_df = self.app_context.books_retriever.get_monthly_dataframe()
            if monthly_df.empty:
                return None
            year_data = monthly_df[monthly_df['anno'] == year]
            if year_data.empty:
                return None
            year_data = year_data.sort_values('mese')
            column_mapping = {
                MonthlyData.FATTURATO: 'fatturato',
                MonthlyData.SPESE: 'spese',
                MonthlyData.ENTRATE: 'entrate',
                MonthlyData.USCITE: 'uscite',
                MonthlyData.SALARIO_MEDIO: 'salario_medio_utente',
            }
            column_name = column_mapping.get(data_enum)
            if not column_name or column_name not in year_data.columns:
                return None
            return year_data[column_name].tolist()
        except Exception as e:
            print(f"Errore nel recupero dati CSV per l'anno {year}: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # Utility
    # ─────────────────────────────────────────────────────────────────────────

    def _toggle_visualized_data_menu(self):
        if not self.annuale_mensile_switch_var.get():
            self.visualized_data_option_menu.configure(values=MonthlyData.get_display_names())
            default_value = MonthlyData.get_display_names()[0]
        else:
            self.visualized_data_option_menu.configure(values=AnnualData.get_display_names())
            default_value = AnnualData.get_display_names()[0]
        self.visualized_data_option_menu.set(default_value)
        self._plot_selected_value(default_value)

    def _clear_data_cache(self):
        self.current_year_monthly_data = None
        self.salary_data_cache = {}

    def cleanup(self):
        try:
            print(f"Cleanup di {self.__class__.__name__}")

            if hasattr(self, '_after_ids'):
                for after_id in self._after_ids:
                    try:
                        self.after_cancel(after_id)
                    except Exception:
                        pass
                self._after_ids.clear()

            # Rimuovi cursore attivo
            if self._active_cursor is not None:
                try:
                    self._active_cursor.remove()
                except Exception:
                    pass
                self._active_cursor = None

            # Chiudi figura matplotlib
            if hasattr(self, 'fig'):
                try:
                    plt.close(self.fig)
                except Exception:
                    pass

            card_lists = [
                'payment_card_list', 'invoice_card_list', 'client_card_list',
                'supplier_card_list', 'production_card_list', 'expenses_card_list',
                'salaries_card_list', 'refund_card_list', 'account_card_list',
            ]
            for card_attr in card_lists:
                if hasattr(self, card_attr):
                    card_dict = getattr(self, card_attr)
                    for card_name, card in card_dict.items():
                        try:
                            card.destroy()
                        except Exception:
                            pass
                    card_dict.clear()

            data_attrs = [
                'cards_warnings', 'global_infos', 'amount_aggregate_labels',
                'payment_card_labels_status', 'invoice_card_labels_status',
                'production_card_labels_status',
            ]
            for attr in data_attrs:
                if hasattr(self, attr):
                    getattr(self, attr).clear()

            container_attrs = [
                'main_container', 'detail_container', 'payments_cards_frame',
                'invoices_cards_frame', 'clients_cards_frame', 'suppliers_cards_frame',
                'productions_cards_frame', 'expenses_cards_frame', 'refunds_cards_frame',
                'accounts_cards_frame', 'salaries_cards_frame',
            ]
            for attr in container_attrs:
                if hasattr(self, attr):
                    container = getattr(self, attr)
                    try:
                        if container.winfo_exists():
                            for widget in container.winfo_children():
                                try:
                                    widget.destroy()
                                except Exception:
                                    pass
                    except Exception:
                        pass

            if hasattr(self, 'db_model'):
                self.db_model = None

        except Exception as e:
            print(f"Errore durante il cleanup di {self.__class__.__name__}: {e}")

    def _track_after(self, ms, func, *args):
        after_id = self._orig_after(ms, func, *args)
        self._after_ids.add(after_id)
        return after_id
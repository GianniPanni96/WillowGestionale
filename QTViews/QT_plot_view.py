"""
View "Plots", versione Qt.

Replica ``Views/Plot_view.py`` (legacy CustomTkinter):
- header con uno switch ``Mensili / Annuali`` per scegliere la
  granularita';
- combo box "Seleziona un dato da visualizzare" il cui elenco cambia
  in base allo switch (vedi ``MonthlyData`` / ``AnnualData``);
- range anni (combo "da" e "a") per il plot mensile multi-anno;
- area del grafico ``matplotlib`` con toolbar di navigazione integrata
  (zoom/pan/save/home) tramite backend Qt;
- per il plot mensile multi-anno: una linea per ogni anno con colore
  stabile e tooltip per nodo via ``mplcursors``, piu' una curva grigia
  con la media storica (escluso l'anno corrente);
- per il plot annuale: barre a larghezza fissa, etichette numeriche
  sopra ogni barra, x-tick = anni reali.

Il colore di ogni anno e' deterministico (``_year_color``) cosi' che
``2024`` abbia sempre la stessa tonalita' indipendentemente dal range
selezionato.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List

import matplotlib.pyplot as plt
import mplcursors
from matplotlib.backends.backend_qtagg import (
    FigureCanvasQTAgg,
    NavigationToolbar2QT,
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from App_context import AppContext


# Palette fissa: ogni anno ottiene sempre lo stesso colore.
_YEAR_PALETTE = [
    "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
    "#DDA0DD", "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E9",
    "#F0A500", "#E17055", "#00B894", "#6C5CE7", "#FD79A8",
]


def _year_color(year: int) -> str:
    """Colore deterministico per un anno, indipendente dal range."""
    idx = (year - 2000) % len(_YEAR_PALETTE)
    return _YEAR_PALETTE[idx]


BG_DARK = "#2b2b2b"
FG_LIGHT = "#e8f4f8"
GRID_COLOR = "gray"
AVG_LINE_COLOR = "#888888"


class AnnualData(Enum):
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


class QTPlotViewH(QWidget):
    """View Plots: switch mensile/annuale + selettore dato + range anni +
    canvas matplotlib con toolbar."""

    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.db_model = app_context.db_model
        self.books_retriever = app_context.books_retriever

        self.available_years: list[int] = []
        # Cache dei dati (invalidata al cambio range anni).
        self.current_year_monthly_data = None
        self.salary_data_cache: dict[int, float] = {}

        # Cursore mplcursors attivo (rimosso prima di ogni replot).
        self._active_cursor = None

        # Stato logico (sostituisce le ``tk.BooleanVar`` / ``tk.StringVar``).
        self._is_annual: bool = False
        self._start_year: int | None = None
        self._end_year: int | None = None

        # Flag per sopprimere chained signal handlers durante un refresh
        # programmatico delle combo (es. ricostruzione del menu dati al
        # toggle dello switch).
        self._suppress_signals: bool = False

        self._build_ui()
        self._init_canvas()
        self._load_available_years()
        self._update_year_range_options()
        self._toggle_visualized_data_menu()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        title = QLabel(
            "Visualizza i grafici dell'andamento con granularità mensile o annuale"
        )
        tf = title.font()
        tf.setPointSize(13)
        title.setFont(tf)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color: {FG_LIGHT}; padding-top: 16px;")
        root.addWidget(title)

        # Riga controlli.
        controls = QFrame()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(20, 10, 20, 4)
        controls_layout.setSpacing(8)

        # Switch Mensili / Annuali. QCheckBox come switch: checked=Annuale.
        controls_layout.addWidget(QLabel("Mensili"))
        self.mode_switch = QCheckBox("Annuali")
        self.mode_switch.toggled.connect(self._on_mode_switch_toggled)
        controls_layout.addWidget(self.mode_switch)
        controls_layout.addSpacing(40)

        # Selettore dato visualizzato.
        controls_layout.addWidget(QLabel("Seleziona un dato\nda visualizzare:"))
        self.visualized_data_combo = QComboBox()
        self.visualized_data_combo.currentTextChanged.connect(self._on_data_combo_changed)
        controls_layout.addWidget(self.visualized_data_combo)
        controls_layout.addSpacing(20)

        # Range anni.
        controls_layout.addWidget(QLabel("Range anni:"))
        self.start_year_combo = QComboBox()
        self.start_year_combo.currentTextChanged.connect(self._on_year_range_changed)
        controls_layout.addWidget(self.start_year_combo)
        controls_layout.addWidget(QLabel("-"))
        self.end_year_combo = QComboBox()
        self.end_year_combo.currentTextChanged.connect(self._on_year_range_changed)
        controls_layout.addWidget(self.end_year_combo)
        controls_layout.addStretch(1)

        root.addWidget(controls)

        # Canvas area (matplotlib + toolbar): tema scuro coerente con
        # tutto il resto della view.
        self.canvas_frame = QFrame()
        self.canvas_frame.setStyleSheet(f"background-color: {BG_DARK};")
        canvas_layout = QVBoxLayout(self.canvas_frame)
        canvas_layout.setContentsMargins(20, 10, 20, 20)
        canvas_layout.setSpacing(4)
        self._canvas_layout = canvas_layout
        root.addWidget(self.canvas_frame, stretch=1)

    # ------------------------------------------------------------------
    # Canvas matplotlib + toolbar
    # ------------------------------------------------------------------

    def _init_canvas(self):
        self.fig, self.ax = plt.subplots(figsize=(8, 6), facecolor=BG_DARK)
        self._apply_dark_axes_style()

        self.graph_canvas = FigureCanvasQTAgg(self.fig)
        self.graph_canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Toolbar di navigazione integrata.
        self.toolbar = NavigationToolbar2QT(self.graph_canvas, self.canvas_frame)
        self.toolbar.setStyleSheet(
            "QToolBar { background-color: #3a3a3a; color: #e8f4f8; }"
            "QToolButton { color: #e8f4f8; }"
            "QLabel { color: #e8f4f8; }"
        )

        self._canvas_layout.addWidget(self.toolbar)
        self._canvas_layout.addWidget(self.graph_canvas, stretch=1)

    def _apply_dark_axes_style(self):
        self.fig.patch.set_facecolor(BG_DARK)
        self.ax.set_facecolor(BG_DARK)
        self.ax.tick_params(colors=FG_LIGHT)
        self.ax.xaxis.label.set_color(FG_LIGHT)
        self.ax.yaxis.label.set_color(FG_LIGHT)
        self.ax.title.set_color(FG_LIGHT)
        for spine in self.ax.spines.values():
            spine.set_color(FG_LIGHT)
        self.ax.spines["top"].set_color(BG_DARK)
        self.ax.spines["right"].set_color(BG_DARK)

    # ------------------------------------------------------------------
    # Setup / inizializzazione anni
    # ------------------------------------------------------------------

    def _load_available_years(self):
        try:
            years_from_data = self.books_retriever.get_years_available() or []
            current_year = datetime.now().year
            if current_year not in years_from_data:
                years_from_data.append(current_year)
            self.available_years = sorted(set(years_from_data))
        except Exception as exc:
            print(f"Errore nel caricamento degli anni disponibili: {exc}")
            self.available_years = [datetime.now().year]

    def _update_year_range_options(self):
        if not self.available_years:
            self._load_available_years()
        year_strings = [str(y) for y in self.available_years]

        self._suppress_signals = True
        try:
            self.start_year_combo.clear()
            self.end_year_combo.clear()
            self.start_year_combo.addItems(year_strings)
            self.end_year_combo.addItems(year_strings)
            if self.available_years:
                self.start_year_combo.setCurrentText(str(self.available_years[0]))
                self.end_year_combo.setCurrentText(str(self.available_years[-1]))
                self._start_year = self.available_years[0]
                self._end_year = self.available_years[-1]
        finally:
            self._suppress_signals = False

    # ------------------------------------------------------------------
    # Eventi UI
    # ------------------------------------------------------------------

    def _on_mode_switch_toggled(self, checked: bool):
        self._is_annual = checked
        self._toggle_visualized_data_menu()

    def _on_data_combo_changed(self, value: str):
        if self._suppress_signals or not value:
            return
        self._plot_selected_value(value)

    def _on_year_range_changed(self, _value: str):
        if self._suppress_signals:
            return
        try:
            self._start_year = int(self.start_year_combo.currentText())
            self._end_year = int(self.end_year_combo.currentText())
        except (ValueError, TypeError):
            return
        self._clear_data_cache()
        current = self.visualized_data_combo.currentText()
        if current:
            self._plot_selected_value(current)

    def _toggle_visualized_data_menu(self):
        # Ricostruisce la lista dei dati visualizzabili in base alla
        # granularita' selezionata, poi forza un replot con il primo
        # valore della lista.
        if self._is_annual:
            options = AnnualData.get_display_names()
        else:
            options = MonthlyData.get_display_names()

        self._suppress_signals = True
        try:
            self.visualized_data_combo.clear()
            self.visualized_data_combo.addItems(options)
            self.visualized_data_combo.setCurrentText(options[0])
        finally:
            self._suppress_signals = False
        self._plot_selected_value(options[0])

    # ------------------------------------------------------------------
    # Plot principale
    # ------------------------------------------------------------------

    def _plot_selected_value(self, selected_value: str):
        if not selected_value:
            return
        if not self.available_years:
            self._load_available_years()
            self._update_year_range_options()

        is_annual = self._is_annual

        try:
            if is_annual:
                data_enum = AnnualData.from_display_name(selected_value)
                mode = "Annuali"
            else:
                data_enum = MonthlyData.from_display_name(selected_value)
                mode = "Mensili"
        except ValueError:
            return

        # Rimuovi cursore precedente per evitare leak di annotation.
        if self._active_cursor is not None:
            try:
                self._active_cursor.remove()
            except Exception:
                pass
            self._active_cursor = None

        self.ax.clear()
        self._apply_dark_axes_style()
        self.ax.set_title(f"{selected_value} - {mode}", color=FG_LIGHT, fontsize=14)

        if is_annual:
            self.ax.set_xlabel("Anno", color=FG_LIGHT)
            self._plot_annual_data(data_enum)
        else:
            self.ax.set_xlabel("Mese", color=FG_LIGHT)
            try:
                start_year = int(self.start_year_combo.currentText())
                end_year = int(self.end_year_combo.currentText())
            except (ValueError, TypeError):
                start_year = self.available_years[0] if self.available_years else datetime.now().year
                end_year = self.available_years[-1] if self.available_years else datetime.now().year
            self._plot_monthly_data_multiyear(data_enum, start_year, end_year)

        self.ax.set_ylabel(selected_value, color=FG_LIGHT)
        self.ax.grid(True, alpha=0.3, color=GRID_COLOR, linestyle="--")

        if not is_annual and len(self.ax.lines) > 0:
            self.ax.legend(
                loc="upper left",
                facecolor=BG_DARK,
                edgecolor="white",
                labelcolor="white",
            )

        self.graph_canvas.draw()

    # ------------------------------------------------------------------
    # Plot annuale
    # ------------------------------------------------------------------

    def _plot_annual_data(self, data_enum: AnnualData):
        try:
            annual_df = self.books_retriever.get_annual_dataframe()
            if annual_df.empty:
                self._draw_centered_message("Nessun dato annuale disponibile")
                return

            # Filtra per range anni se valido.
            if self._start_year and self._end_year:
                s, e = self._start_year, self._end_year
                if s > e:
                    s, e = e, s
                annual_df = annual_df[(annual_df["anno"] >= s) & (annual_df["anno"] <= e)]

            column_mapping = {
                AnnualData.TOTALE_FATTURATO: "totale_fatturato",
                AnnualData.SPESE: "totale_spese",
                AnnualData.MEDIA_FATTURE: "media_fatture",
                AnnualData.MEDIA_ORE_PRODUZIONE: "media_ore_per_produzione",
                AnnualData.MEDIA_PREZZO_ORARIO: "media_prezzo_orario_produzione",
                AnnualData.IRPEF: "irpef_willow",
                AnnualData.INPS: "inps_willow",
            }
            column_name = column_mapping.get(data_enum)
            if column_name is None or column_name not in annual_df.columns:
                self._draw_centered_message(f"Dato non disponibile: {data_enum.value}")
                return

            annual_df = annual_df.sort_values("anno")
            years = annual_df["anno"].tolist()
            values = annual_df[column_name].tolist()

            n_bars = len(years)
            x_range = (n_bars - 1) if n_bars > 1 else 1
            bar_width = min(0.1, (x_range / n_bars) * 0.8) if n_bars > 0 else 0.5
            x_pos = list(range(n_bars))
            bar_colors = [_year_color(y) for y in years]

            bars = self.ax.bar(x_pos, values, width=bar_width, color=bar_colors, alpha=0.8)
            for bar, value in zip(bars, values):
                height = bar.get_height()
                self.ax.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    height,
                    f"{value:.0f}" if isinstance(value, (int, float)) else str(value),
                    ha="center",
                    va="bottom" if value >= 0 else "top",
                    color="white",
                    fontsize=10,
                )

            self.ax.set_xticks(x_pos)
            self.ax.set_xticklabels([str(y) for y in years], rotation=0)
            self.ax.set_xlim(-0.6, n_bars - 0.4)
        except Exception as exc:
            self._draw_centered_message(f"Errore: {exc}", color="red")

    # ------------------------------------------------------------------
    # Plot mensile multi-anno
    # ------------------------------------------------------------------

    def _plot_monthly_data_multiyear(self, data_enum: MonthlyData, start_year: int, end_year: int):
        try:
            if start_year > end_year:
                start_year, end_year = end_year, start_year

            months = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu",
                      "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]
            x_pos = list(range(len(months)))

            scatter_targets: list[tuple] = []

            for year in range(start_year, end_year + 1):
                color = _year_color(year)
                values = self._get_monthly_data_for_year(year, data_enum)
                if not values:
                    continue

                self.ax.plot(x_pos, values, marker="o", linewidth=2,
                             color=color, markersize=6, label=str(year))

                # Scatter invisibile come target del tooltip.
                sc = self.ax.scatter(
                    x_pos,
                    values,
                    alpha=0,
                    s=200,
                    zorder=5,
                    label="_nolegend_",
                )
                scatter_targets.append((sc, str(year)))

            if not scatter_targets:
                self._draw_centered_message("Nessun dato disponibile per il range selezionato")
                return

            avg_values = self._get_monthly_averages(data_enum)
            if any(v != 0.0 for v in avg_values):
                self.ax.plot(
                    x_pos,
                    avg_values,
                    color=AVG_LINE_COLOR,
                    linewidth=1.5,
                    linestyle="--",
                    marker="",
                    label=f"Media storica - {datetime.now().year} escluso",
                    zorder=3,
                )

            self.ax.set_xticks(x_pos)
            self.ax.set_xticklabels(months)

            # Tooltip via mplcursors sui nodi reali (scatter invisibili).
            all_scatter = [sc for sc, _ in scatter_targets]
            scatter_year_map = {id(sc): yr for sc, yr in scatter_targets}

            cursor = mplcursors.cursor(all_scatter, hover=True)

            @cursor.connect("add")
            def _on_node(sel):
                x_idx = int(round(float(sel.target[0])))
                month_label = months[x_idx] if 0 <= x_idx < len(months) else ""
                year_label = scatter_year_map.get(id(sel.artist), "")
                sel.annotation.set_text(
                    f"{year_label} – {month_label}\n{sel.target[1]:,.2f}"
                )
                sel.annotation.get_bbox_patch().set(fc=BG_DARK, alpha=0.9, ec="white")
                sel.annotation.set_color("white")

            self._active_cursor = cursor
        except Exception as exc:
            self._draw_centered_message(f"Errore: {exc}", color="red")

    # ------------------------------------------------------------------
    # Recupero dati mensili
    # ------------------------------------------------------------------

    def _get_monthly_data_for_year(self, year: int, data_enum: MonthlyData):
        try:
            if year == datetime.now().year:
                return self._get_current_year_monthly_data(data_enum)
            return self._get_csv_monthly_data_for_year(year, data_enum)
        except Exception as exc:
            print(f"Errore nel recupero dati per l'anno {year}: {exc}")
            return None

    def _get_monthly_averages(self, data_enum: MonthlyData) -> List[float]:
        column_mapping = {
            MonthlyData.FATTURATO: "fatturato",
            MonthlyData.SPESE: "spese",
            MonthlyData.ENTRATE: "entrate",
            MonthlyData.USCITE: "uscite",
            MonthlyData.SALARIO_MEDIO: "salario_medio_utente",
        }
        column_name = column_mapping.get(data_enum)
        if not column_name:
            return [0.0] * 12
        try:
            return self.books_retriever.get_monthly_averages(column_name)
        except Exception as exc:
            print(f"Errore nel calcolo medie storiche: {exc}")
            return [0.0] * 12

    def _get_current_year_monthly_data(self, data_enum: MonthlyData):
        try:
            if self.current_year_monthly_data is None:
                self.current_year_monthly_data = (
                    self.app_context.monthly_report_analyzer_service.retrieve_monthly_data()
                )

            data_mapping = {
                MonthlyData.FATTURATO: "fatturato",
                MonthlyData.SPESE: "spese",
                MonthlyData.ENTRATE: "incomes",
                MonthlyData.USCITE: "outcomes",
                MonthlyData.SALARIO_MEDIO: "salario_medio",
            }
            data_key = data_mapping.get(data_enum)
            if not data_key:
                return None

            if data_enum == MonthlyData.SALARIO_MEDIO:
                return self._get_current_year_salaries()

            values = []
            for month in range(1, 13):
                month_data = self.current_year_monthly_data.get(month, {}) or {}
                month_values = month_data.get("values", {}) or {}
                values.append(month_values.get(data_key, 0.0))
            return values
        except Exception as exc:
            print(f"Errore nel recupero dati anno corrente: {exc}")
            return None

    def _get_current_year_salaries(self):
        try:
            if not self.salary_data_cache:
                for month in range(1, 13):
                    salary = self.app_context.salary_analyzer_service.calculate_mean_salary_by_month(month)
                    self.salary_data_cache[month] = salary if salary is not None else 0.0
            return [self.salary_data_cache.get(month, 0.0) for month in range(1, 13)]
        except Exception as exc:
            print(f"Errore nel recupero salari: {exc}")
            return [0.0] * 12

    def _get_csv_monthly_data_for_year(self, year: int, data_enum: MonthlyData):
        try:
            monthly_df = self.books_retriever.get_monthly_dataframe()
            if monthly_df.empty:
                return None
            year_data = monthly_df[monthly_df["anno"] == year]
            if year_data.empty:
                return None
            year_data = year_data.sort_values("mese")
            column_mapping = {
                MonthlyData.FATTURATO: "fatturato",
                MonthlyData.SPESE: "spese",
                MonthlyData.ENTRATE: "entrate",
                MonthlyData.USCITE: "uscite",
                MonthlyData.SALARIO_MEDIO: "salario_medio_utente",
            }
            column_name = column_mapping.get(data_enum)
            if not column_name or column_name not in year_data.columns:
                return None
            return year_data[column_name].tolist()
        except Exception as exc:
            print(f"Errore nel recupero dati CSV per l'anno {year}: {exc}")
            return None

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _draw_centered_message(self, text: str, color: str = "white"):
        self.ax.text(
            0.5,
            0.5,
            text,
            ha="center",
            va="center",
            transform=self.ax.transAxes,
            color=color,
            fontsize=12,
        )

    def _clear_data_cache(self):
        self.current_year_monthly_data = None
        self.salary_data_cache = {}

    # ------------------------------------------------------------------
    # API esterna
    # ------------------------------------------------------------------

    def refresh(self):
        """Ricarica anni disponibili, invalida cache e ridisegna."""
        self._clear_data_cache()
        self._load_available_years()
        self._update_year_range_options()
        current = self.visualized_data_combo.currentText()
        if current:
            self._plot_selected_value(current)

    def cleanup(self):
        if self._active_cursor is not None:
            try:
                self._active_cursor.remove()
            except Exception:
                pass
            self._active_cursor = None
        try:
            plt.close(self.fig)
        except Exception:
            pass

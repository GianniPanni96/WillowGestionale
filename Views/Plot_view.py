import customtkinter as ctk
import tkinter as tk
from enum import Enum
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from datetime import datetime

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
        """Restituisce una lista di nomi visualizzabili"""
        return [item.value for item in cls]

    @classmethod
    def from_display_name(cls, display_name):
        """Ottiene l'enum dal nome visualizzato"""
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
        """Restituisce una lista di nomi visualizzabili"""
        return [item.value for item in cls]

    @classmethod
    def from_display_name(cls, display_name):
        """Ottiene l'enum dal nome visualizzato"""
        for item in cls:
            if item.value == display_name:
                return item
        raise ValueError(f"Valore non trovato: {display_name}")


class PlotView (ctk.CTkFrame):
    def __init__(self, app_context , tabview):
        super().__init__(tabview.tab("Plots"))

        self.app_context = app_context
        self.db_model = app_context.db_model
        self.update_controller = app_context.update_controller
        self.tabview = tabview
        self.tab = tabview.tab("Plots")
        self.analyzer = app_context.analyzer
        self.event_bus = app_context.event_bus
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
        self.salary_data_cache = {}  # cache per i salari medi mensili

        self._create_plot_tab()
        self._init_canvas()
        self._load_available_years()  # Carica gli anni disponibili
        self._update_year_range_options()  # AGGIUNGI QUESTA RIGA per popolare i menu
        self._toggle_visualized_data_menu()

    def _load_available_years(self):
        """Carica gli anni disponibili dai dati"""
        try:
            # Ottieni anni dal BooksRetriever
            books_retriever = self.app_context.books_retriever
            years_from_data = books_retriever.get_years_available()

            # Aggiungi l'anno corrente se non presente
            current_year = datetime.now().year
            if current_year not in years_from_data:
                years_from_data.append(current_year)

            # Ordina gli anni
            self.available_years = sorted(years_from_data)

        except Exception as e:
            print(f"Errore nel caricamento degli anni disponibili: {e}")
            current_year = datetime.now().year
            self.available_years = [current_year]

    def _create_plot_tab(self):
        ctk.CTkLabel(self.main_container,
                     text="Visualizza i grafici dell'andamento con granularità mensile o annuale",
                     font=("Arial", 16),
                     text_color="#e8f4f8").pack(pady=(25, 0))

        self.switch_frame = ctk.CTkFrame(self.main_container, fg_color="#2b2b2b")
        self.switch_frame.pack(fill="x", pady=(10, 0), expand=True)
        ctk.CTkLabel(self.switch_frame, text="Mensili   ", font=("Arial", 16)).pack(pady=(10,0), padx=(20, 0), anchor="w", side=ctk.LEFT)
        self.annuale_mensile_switch = ctk.CTkSwitch(self.switch_frame,
                                                text="  Annuali", font=("Arial", 16),
                                                command=self._switch_mensile_annuale,
                                                width=200, switch_width=60,
                                                height=48, switch_height=20,
                                                variable=self.annuale_mensile_switch_var)
        self.annuale_mensile_switch.pack(pady=(10,0), anchor="w", side="left")

        ctk.CTkLabel(self.switch_frame, text="Seleziona un dato\nda visualizzare: ", justify="right").pack(side="left", padx=(50, 10), pady=(10,0))

        self.visualized_data_option_menu = ctk.CTkOptionMenu(self.switch_frame,
                                                             values=MonthlyData.get_display_names(),
                                                             command=lambda selected_value: self._plot_selected_value(
                                                                 selected_value))
        self.visualized_data_option_menu.pack(side="left", pady=(10, 0))

        # Frame per la selezione del range di anni
        self.year_range_frame = ctk.CTkFrame(self.switch_frame, fg_color="#2b2b2b")
        self.year_range_frame.pack(side="left", padx=(20, 0), pady=(10, 0))

        ctk.CTkLabel(self.year_range_frame, text="Range anni:").pack(side="left", padx=(70, 5))

        # Dropdown per anno inizio
        self.start_year_menu = ctk.CTkOptionMenu(
            self.year_range_frame,
            values=[],
            variable=self.start_year_var,
            command=lambda _: self._on_year_range_changed()
        )
        self.start_year_menu.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(self.year_range_frame, text="-").pack(side="left")

        # Dropdown per anno fine
        self.end_year_menu = ctk.CTkOptionMenu(
            self.year_range_frame,
            values=[],
            variable=self.end_year_var,
            command=lambda _: self._on_year_range_changed()
        )
        self.end_year_menu.pack(side="left", padx=(10, 0))

        # Frame per contenere il canvas
        self.canvas_frame = ctk.CTkFrame(self.main_container, fg_color="#2b2b2b")
        self.canvas_frame.pack(fill='both', expand=True, padx=20, pady=20)

    def _switch_mensile_annuale(self):
        """Gestisce il cambio tra visualizzazione mensile e annuale"""
        # Aggiorna il menu dei valori disponibili
        self._toggle_visualized_data_menu()

    def _update_year_range_options(self):
        """Aggiorna le opzioni del range di anni"""
        if not self.available_years:
            self._load_available_years()

        # Converti anni in stringhe per i menu
        year_strings = [str(year) for year in self.available_years]

        # Aggiorna i menu
        self.start_year_menu.configure(values=year_strings)
        self.end_year_menu.configure(values=year_strings)

        # Imposta valori di default
        if self.available_years:
            self.start_year_var.set(str(self.available_years[0]))
            self.end_year_var.set(str(self.available_years[-1]))

        # Aggiungi questa chiamata nel costruttore dopo _load_available_years()

    def _on_year_range_changed(self):
        """Chiamato quando cambia il range di anni selezionato"""
        # Pulisci la cache
        self._clear_data_cache()

        if self.start_year_var.get() and self.end_year_var.get():
            self._plot_selected_value(self.visualized_data_option_menu.get())

    def _init_canvas(self):
        """Inizializza il canvas con le caratteristiche statiche"""
        # Crea bridge frame tkinter per Matplotlib
        self.plot_bridge_frame = tk.Frame(self.canvas_frame)
        self.plot_bridge_frame.pack(fill='both', expand=True)

        # Crea figura e assi con caratteristiche statiche
        self.fig, self.ax = plt.subplots(figsize=(8, 14), facecolor='#2b2b2b')

        # Configurazione statica del tema scuro
        self.fig.patch.set_facecolor('#2b2b2b')
        self.ax.set_facecolor('#2b2b2b')

        # Configura colori assi e bordi (statici)
        self.ax.tick_params(colors='#e8f4f8')
        self.ax.xaxis.label.set_color('#e8f4f8')
        self.ax.yaxis.label.set_color('#e8f4f8')
        self.ax.title.set_color('#e8f4f8')

        # Configura bordi
        self.ax.spines['bottom'].set_color('white')
        self.ax.spines['top'].set_color('#2b2b2b')
        self.ax.spines['left'].set_color('white')
        self.ax.spines['right'].set_color('#2b2b2b')

        # Crea il canvas Matplotlib
        self.graph_canvas = FigureCanvasTkAgg(self.fig, self.plot_bridge_frame)
        self.graph_canvas.draw()
        self.graph_canvas.get_tk_widget().pack(fill='both', expand=True)

    def _plot_selected_value(self, selected_value):
        """Aggiorna solo i campi dinamici del canvas in base al valore selezionato"""
        # Assicurati che gli anni siano caricati
        if not self.available_years:
            self._load_available_years()
            self._update_year_range_options()

        # Determina se siamo in modalità annuale o mensile
        is_annual = self.annuale_mensile_switch_var.get()

        # Determina l'enum corretto in base al valore e modalità
        if is_annual:
            data_enum = AnnualData.from_display_name(selected_value)
            mode = "Annuali"
        else:
            data_enum = MonthlyData.from_display_name(selected_value)
            mode = "Mensili"

        # Pulisci l'asse mantenendo le proprietà statiche
        self.ax.clear()

        # RI-applica le proprietà statiche dopo clear()
        self.ax.set_facecolor('#2b2b2b')
        self.ax.tick_params(colors='#e8f4f8')

        # Imposta titolo e label dinamici
        self.ax.set_title(f'{selected_value} - {mode}', color='#e8f4f8', fontsize=14)

        # Configura label degli assi in base al tipo di dato
        if is_annual:
            self.ax.set_xlabel('Anno', color='#e8f4f8')
            self._plot_annual_data(data_enum)
        else:
            self.ax.set_xlabel('Mese', color='#e8f4f8')
            # Ottieni gli anni selezionati
            try:
                start_year = int(self.start_year_var.get())
                end_year = int(self.end_year_var.get())
            except (ValueError, AttributeError):
                # Fallback agli anni disponibili
                start_year = self.available_years[0] if self.available_years else datetime.now().year
                end_year = self.available_years[-1] if self.available_years else datetime.now().year

            self._plot_monthly_data_multiyear(data_enum, start_year, end_year)

        self.ax.set_ylabel(selected_value, color='#e8f4f8')

        # RI-applica colore bordi
        for spine in self.ax.spines.values():
            spine.set_color('#e8f4f8')

        # Aggiungi griglia
        self.ax.grid(True, alpha=0.3, color='gray', linestyle='--')

        # Aggiungi legenda se ci sono più serie
        if not is_annual and len(self.ax.lines) > 0:
            self.ax.legend(loc='upper left', facecolor='#2b2b2b', edgecolor='white', labelcolor='white')

        # Aggiorna il canvas
        self.graph_canvas.draw()

    def _plot_annual_data(self, data_enum):
        """Plotta i dati annuali ottenuti da BooksRetriever"""
        try:
            # Ottieni il books_retriever
            books_retriever = self.app_context.books_retriever

            # Ottieni i dati annuali
            annual_df = books_retriever.get_annual_dataframe()

            if annual_df.empty:
                self.ax.text(0.5, 0.5, 'Nessun dato annuale disponibile',
                             ha='center', va='center', transform=self.ax.transAxes,
                             color='white', fontsize=12)
                return

            # Filtra per range di anni se specificato
            if self.start_year_var.get() and self.end_year_var.get():
                try:
                    start_year = int(self.start_year_var.get())
                    end_year = int(self.end_year_var.get())
                    if start_year > end_year:
                        start_year, end_year = end_year, start_year

                    annual_df = annual_df[(annual_df['anno'] >= start_year) &
                                          (annual_df['anno'] <= end_year)]
                except:
                    pass  # Se c'è un errore, usa tutti gli anni

            # Mappatura tra enum AnnualData e colonne del DataFrame
            column_mapping = {
                AnnualData.TOTALE_FATTURATO: 'totale_fatturato',
                AnnualData.SPESE: 'totale_spese',
                AnnualData.MEDIA_FATTURE: 'media_fatture',
                AnnualData.MEDIA_ORE_PRODUZIONE: 'media_ore_per_produzione',
                AnnualData.MEDIA_PREZZO_ORARIO: 'media_prezzo_orario_produzione',
                AnnualData.IRPEF: 'irpef_willow',
                AnnualData.INPS: 'inps_willow'
            }

            column_name = column_mapping.get(data_enum)

            if column_name is None:
                self.ax.text(0.5, 0.5, f'Dato non disponibile: {data_enum.value}',
                             ha='center', va='center', transform=self.ax.transAxes,
                             color='white', fontsize=12)
                return

            if column_name not in annual_df.columns:
                self.ax.text(0.5, 0.5, f'Colonna non trovata: {column_name}',
                             ha='center', va='center', transform=self.ax.transAxes,
                             color='white', fontsize=12)
                return

            # Prepara i dati per il plot
            years = annual_df['anno'].tolist()
            values = annual_df[column_name].tolist()

            # Plot come barre per dati annuali
            bars = self.ax.bar(years, values, color='#4e8cff', alpha=0.7, width=0.6)

            # Aggiungi etichette ai valori
            for bar, value in zip(bars, values):
                height = bar.get_height()
                self.ax.text(bar.get_x() + bar.get_width() / 2., height,
                             f'{value:.0f}' if isinstance(value, (int, float)) else str(value),
                             ha='center', va='bottom' if value >= 0 else 'top',
                             color='white', fontsize=10)

            # Formatta l'asse X per gli anni
            self.ax.set_xticks(years)
            self.ax.set_xticklabels(years, rotation=0)

        except Exception as e:
            self.ax.text(0.5, 0.5, f'Errore: {str(e)}',
                         ha='center', va='center', transform=self.ax.transAxes,
                         color='red', fontsize=10)

    def _plot_monthly_data_multiyear(self, data_enum, start_year, end_year):
        """Plotta dati mensili come linee spezzate per più anni"""
        try:
            # Assicurati che start_year <= end_year
            if start_year > end_year:
                start_year, end_year = end_year, start_year

            # Colori per le diverse linee (puoi personalizzare questa palette)
            colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
                      '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9']

            # Mesi per l'asse X
            months = ['Gen', 'Feb', 'Mar', 'Apr', 'Mag', 'Giu',
                      'Lug', 'Ago', 'Set', 'Ott', 'Nov', 'Dic']

            lines = []  # Per tenere traccia delle linee per la legenda
            labels = []  # Per le etichette della legenda

            # Per ogni anno nel range
            for idx, year in enumerate(range(start_year, end_year + 1)):
                if idx >= len(colors):  # Se abbiamo più anni che colori, ricicliamo
                    color = colors[idx % len(colors)]
                else:
                    color = colors[idx]

                # Ottieni i dati per questo anno e questo tipo di dato
                values = self._get_monthly_data_for_year(year, data_enum)

                if values:
                    # Crea la linea spezzata
                    line, = self.ax.plot(months, values, marker='o', linewidth=2,
                                         color=color, markersize=6, label=str(year))
                    lines.append(line)
                    labels.append(str(year))

            if not lines:
                self.ax.text(0.5, 0.5, 'Nessun dato disponibile per il range selezionato',
                             ha='center', va='center', transform=self.ax.transAxes,
                             color='white', fontsize=12)
                return

            # Configura l'asse X
            self.ax.set_xticks(range(len(months)))
            self.ax.set_xticklabels(months)

        except Exception as e:
            self.ax.text(0.5, 0.5, f'Errore: {str(e)}',
                         ha='center', va='center', transform=self.ax.transAxes,
                         color='red', fontsize=10)

    def _get_monthly_data_for_year(self, year, data_enum):
        """Ottiene i dati mensili per un anno specifico"""
        try:
            current_year = datetime.now().year

            if year == current_year:
                # Usa i dati in tempo reale per l'anno corrente
                return self._get_current_year_monthly_data(data_enum)
            else:
                # Usa i dati dal CSV per anni precedenti
                return self._get_csv_monthly_data_for_year(year, data_enum)

        except Exception as e:
            print(f"Errore nel recupero dati per l'anno {year}: {e}")
            return None

    def _get_current_year_monthly_data(self, data_enum):
        """Ottiene i dati mensili per l'anno corrente"""
        try:
            # Carica i dati correnti se non già caricati
            if self.current_year_monthly_data is None:
                self.current_year_monthly_data = self.app_context.analyzer.retrieve_monthly_data()

            # Mappatura tra enum e chiavi dei dati
            data_mapping = {
                MonthlyData.FATTURATO: 'fatturato',
                MonthlyData.SPESE: 'spese',
                MonthlyData.ENTRATE: 'incomes',
                MonthlyData.USCITE: 'outcomes',
                MonthlyData.SALARIO_MEDIO: 'salario_medio'
            }

            data_key = data_mapping.get(data_enum)
            if not data_key:
                return None

            # Per il salario medio, usa il controller specifico
            if data_enum == MonthlyData.SALARIO_MEDIO:
                return self._get_current_year_salaries()

            # Per gli altri dati, usa i dati dell'analyzer
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
        """Ottiene i salari medi per l'anno corrente"""
        try:
            # Usa la cache se disponibile
            if not self.salary_data_cache:
                for month in range(1, 13):
                    salary = self.app_context.salary_controller.calculate_mean_salary_by_month(month)
                    self.salary_data_cache[month] = salary if salary is not None else 0.0

            # Ritorna i valori in ordine di mese
            return [self.salary_data_cache.get(month, 0.0) for month in range(1, 13)]

        except Exception as e:
            print(f"Errore nel recupero salari: {e}")
            return [0.0] * 12

    def _get_csv_monthly_data_for_year(self, year, data_enum):
        """Ottiene i dati mensili da CSV per un anno specifico"""
        try:
            books_retriever = self.app_context.books_retriever
            monthly_df = books_retriever.get_monthly_dataframe()

            if monthly_df.empty:
                return None

            # Filtra per anno
            year_data = monthly_df[monthly_df['anno'] == year]

            if year_data.empty:
                return None

            # Ordina per mese
            year_data = year_data.sort_values('mese')

            # Mappatura tra enum e colonne CSV
            column_mapping = {
                MonthlyData.FATTURATO: 'fatturato',
                MonthlyData.SPESE: 'spese',
                MonthlyData.ENTRATE: 'entrate',
                MonthlyData.USCITE: 'uscite',
                MonthlyData.SALARIO_MEDIO: 'salario_medio_utente'
            }

            column_name = column_mapping.get(data_enum)
            if not column_name or column_name not in year_data.columns:
                return None

            # Ritorna i valori
            return year_data[column_name].tolist()

        except Exception as e:
            print(f"Errore nel recupero dati CSV per l'anno {year}: {e}")
            return None

    def _toggle_visualized_data_menu(self):
        """Aggiorna i valori del menu a tendina in base alla modalità selezionata"""
        if not self.annuale_mensile_switch_var.get():  # Modalità mensile (False)
            # Imposta i valori mensili
            self.visualized_data_option_menu.configure(values=MonthlyData.get_display_names())
            # Seleziona il primo valore della lista mensile
            default_value = MonthlyData.get_display_names()[0]
            self.visualized_data_option_menu.set(default_value)
            # Aggiorna il grafico con il valore predefinito
            self._plot_selected_value(default_value)
        else:  # Modalità annuale (True)
            # Imposta i valori annuali
            self.visualized_data_option_menu.configure(values=AnnualData.get_display_names())
            # Seleziona il primo valore della lista annuale
            default_value = AnnualData.get_display_names()[0]
            self.visualized_data_option_menu.set(default_value)
            # Aggiorna il grafico con il valore predefinito
            self._plot_selected_value(default_value)

    def _clear_data_cache(self):
        """Pulisce la cache dei dati"""
        self.current_year_monthly_data = None
        self.salary_data_cache = {}

    def cleanup(self):
        """Pulizia completa per liberare memoria - DA AGGIUNGERE IN OGNI VIEW"""
        try:
            print(f"Cleanup di {self.__class__.__name__}")

            # 1. Cancella tutti gli after scheduled
            if hasattr(self, '_after_ids'):
                for after_id in self._after_ids:
                    try:
                        self.after_cancel(after_id)
                    except:
                        pass
                self._after_ids.clear()

            # 2. Distruggi tutte le card e widget dinamici
            card_lists = [
                'payment_card_list', 'invoice_card_list', 'client_card_list',
                'supplier_card_list', 'production_card_list', 'expenses_card_list',
                'salaries_card_list', 'refund_card_list', 'account_card_list'
            ]

            for card_attr in card_lists:
                if hasattr(self, card_attr):
                    card_dict = getattr(self, card_attr)
                    for card_name, card in card_dict.items():
                        try:
                            card.destroy()
                        except:
                            pass
                    card_dict.clear()

            # 3. Pulisci dizionari e liste
            data_attrs = [
                'cards_warnings', 'global_infos', 'amount_aggregate_labels',
                'payment_card_labels_status', 'invoice_card_labels_status',
                'production_card_labels_status'
            ]

            for attr in data_attrs:
                if hasattr(self, attr):
                    getattr(self, attr).clear()

            # 4. Distruggi i container principali se esistono
            container_attrs = [
                'main_container', 'detail_container', 'payments_cards_frame',
                'invoices_cards_frame', 'clients_cards_frame', 'suppliers_cards_frame',
                'productions_cards_frame', 'expenses_cards_frame', 'refunds_cards_frame',
                'accounts_cards_frame', 'salaries_cards_frame'
            ]

            for attr in container_attrs:
                if hasattr(self, attr):
                    container = getattr(self, attr)
                    try:
                        # Distruggi solo se il container esiste ancora
                        if container.winfo_exists():
                            for widget in container.winfo_children():
                                try:
                                    widget.destroy()
                                except:
                                    pass
                    except:
                        pass

            # 5. Pulisci i riferimenti ai controller (opzionale)
            if hasattr(self, 'db_model'):
                self.db_model = None

        except Exception as e:
            print(f"Errore durante il cleanup di {self.__class__.__name__}: {e}")

    def _track_after(self, ms, func, *args):
        """Versione tracciata di after()"""
        after_id = self._orig_after(ms, func, *args)
        self._after_ids.add(after_id)
        return after_id
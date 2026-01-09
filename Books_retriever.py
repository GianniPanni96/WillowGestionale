import os
import csv
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any


class BooksRetriever:
    def __init__(self, environment_db_variable: str):
        """
        Inizializza il BooksRetriever per recuperare dati dai libri contabili.

        Args:
            environment_db_variable: Percorso base della directory dei dati
        """
        self.environment_db_variable = environment_db_variable

        # Definisce i percorsi dei file
        self.books_dir = os.path.join(self.environment_db_variable, "Books")
        self.annual_data_file_path = os.path.join(self.books_dir, "annual_aggregated_data.csv")
        self.monthly_data_file_path = os.path.join(self.books_dir, "monthly_aggregated_data.csv")
        self.iva_data_file_path = os.path.join(self.books_dir, "iva_aggregated_data.csv")
        self.taxes_data_file_path = os.path.join(self.books_dir, "taxes_aggregated_data.csv")

        # Cache per i dati caricati
        self._annual_data = None
        self._monthly_data = None
        self._annual_df = None
        self._monthly_df = None
        self._iva_data = None
        self._iva_df = None
        self._taxes_data = None
        self._taxes_df = None

    def load_annual_data(self) -> List[Dict[str, Any]]:
        """
        Carica i dati annuali dal file CSV.

        Returns:
            Lista di dizionari con i dati annuali
        """
        if not os.path.exists(self.annual_data_file_path):
            print(f"File dati annuali non trovato: {self.annual_data_file_path}")
            return []

        try:
            data = []
            with open(self.annual_data_file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    # Converte i valori numerici
                    converted_row = {}
                    for key, value in row.items():
                        if key == 'anno':
                            converted_row[key] = int(value) if value else 0
                        elif value and value.replace('.', '', 1).isdigit():
                            try:
                                converted_row[key] = float(value)
                            except ValueError:
                                converted_row[key] = value
                        else:
                            converted_row[key] = value
                    data.append(converted_row)

            self._annual_data = data
            return data

        except Exception as e:
            print(f"Errore nel caricamento dei dati annuali: {e}")
            return []

    def load_monthly_data(self) -> List[Dict[str, Any]]:
        """
        Carica i dati mensili dal file CSV.

        Returns:
            Lista di dizionari con i dati mensili
        """
        if not os.path.exists(self.monthly_data_file_path):
            print(f"File dati mensili non trovato: {self.monthly_data_file_path}")
            return []

        try:
            data = []
            with open(self.monthly_data_file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    # Converte i valori numerici
                    converted_row = {}
                    for key, value in row.items():
                        if key in ['anno', 'mese']:
                            converted_row[key] = int(value) if value else 0
                        elif value and value.replace('.', '', 1).isdigit():
                            try:
                                converted_row[key] = float(value)
                            except ValueError:
                                converted_row[key] = value
                        else:
                            converted_row[key] = value
                    data.append(converted_row)

            self._monthly_data = data
            return data

        except Exception as e:
            print(f"Errore nel caricamento dei dati mensili: {e}")
            return []

    def load_iva_data(self) -> List[Dict[str, Any]]:
        """
        Carica i dati IVA trimestrali dal file CSV.

        Returns:
            Lista di dizionari con i dati IVA trimestrali
        """
        if not os.path.exists(self.iva_data_file_path):
            print(f"File dati IVA non trovato: {self.iva_data_file_path}")
            return []

        try:
            data = []
            with open(self.iva_data_file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    converted_row = {}
                    for key, value in row.items():
                        if key in ['anno', 'trimestre']:
                            converted_row[key] = int(value) if value else 0
                        elif value and value.replace('.', '', 1).isdigit():
                            try:
                                converted_row[key] = float(value)
                            except ValueError:
                                converted_row[key] = value
                        else:
                            converted_row[key] = value
                    data.append(converted_row)

            self._iva_data = data
            return data

        except Exception as e:
            print(f"Errore nel caricamento dei dati IVA: {e}")
            return []

    def load_taxes_data(self) -> List[Dict[str, Any]]:
        """
        Carica i dati delle tasse dal file CSV.

        Returns:
            Lista di dizionari con i dati delle tasse
        """
        if not os.path.exists(self.taxes_data_file_path):
            print(f"File dati tasse non trovato: {self.taxes_data_file_path}")
            return []

        try:
            data = []
            with open(self.taxes_data_file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    converted_row = {}
                    for key, value in row.items():
                        if key in ['anno', 'user_id']:
                            converted_row[key] = int(value) if value else None
                        elif key == 'is_totale':
                            converted_row[key] = value.lower() == 'true'
                        elif value and value.replace('.', '', 1).isdigit():
                            try:
                                converted_row[key] = float(value)
                            except ValueError:
                                converted_row[key] = value
                        else:
                            converted_row[key] = value
                    data.append(converted_row)

            self._taxes_data = data
            return data

        except Exception as e:
            print(f"Errore nel caricamento dei dati tasse: {e}")
            return []

    def get_annual_dataframe(self) -> pd.DataFrame:
        """
        Restituisce i dati annuali come DataFrame pandas.

        Returns:
            DataFrame con i dati annuali
        """
        if self._annual_df is None:
            if self._annual_data is None:
                self.load_annual_data()

            if self._annual_data:
                self._annual_df = pd.DataFrame(self._annual_data)
                # Ordina per anno
                if 'anno' in self._annual_df.columns:
                    self._annual_df = self._annual_df.sort_values('anno')
            else:
                self._annual_df = pd.DataFrame()

        return self._annual_df

    def get_monthly_dataframe(self) -> pd.DataFrame:
        """
        Restituisce i dati mensili come DataFrame pandas.

        Returns:
            DataFrame con i dati mensili
        """
        if self._monthly_df is None:
            if self._monthly_data is None:
                self.load_monthly_data()

            if self._monthly_data:
                self._monthly_df = pd.DataFrame(self._monthly_data)
                # Ordina per anno e mese
                if 'anno' in self._monthly_df.columns and 'mese' in self._monthly_df.columns:
                    self._monthly_df = self._monthly_df.sort_values(['anno', 'mese'])
            else:
                self._monthly_df = pd.DataFrame()

        return self._monthly_df

    def get_iva_dataframe(self) -> pd.DataFrame:
        """
        Restituisce i dati IVA trimestrali come DataFrame pandas.

        Returns:
            DataFrame con i dati IVA
        """
        if self._iva_df is None:
            if self._iva_data is None:
                self.load_iva_data()

            if self._iva_data:
                self._iva_df = pd.DataFrame(self._iva_data)
                if {'anno', 'utente', 'trimestre'}.issubset(self._iva_df.columns):
                    self._iva_df = self._iva_df.sort_values(
                        ['anno', 'utente', 'trimestre']
                    )
            else:
                self._iva_df = pd.DataFrame()

        return self._iva_df

    def get_taxes_dataframe(self) -> pd.DataFrame:
        """
        Restituisce i dati delle tasse come DataFrame pandas.

        Returns:
            DataFrame con i dati delle tasse
        """
        if self._taxes_df is None:
            if self._taxes_data is None:
                self.load_taxes_data()

            if self._taxes_data:
                self._taxes_df = pd.DataFrame(self._taxes_data)

                sort_cols = [c for c in ['anno', 'utente'] if c in self._taxes_df.columns]
                if sort_cols:
                    self._taxes_df = self._taxes_df.sort_values(sort_cols)
            else:
                self._taxes_df = pd.DataFrame()

        return self._taxes_df

    def get_years_available(self) -> List[int]:
        """
        Restituisce la lista degli anni disponibili nei dati.

        Returns:
            Lista di anni (ordinati)
        """
        df = self.get_annual_dataframe()
        if df.empty or 'anno' not in df.columns:
            return []

        years = sorted(df['anno'].unique().tolist())
        return years

    def get_iva_data_for_year(self, year: int) -> List[Dict[str, Any]]:
        """
        Restituisce i dati IVA trimestrali per un anno specifico.

        Args:
            year: Anno di riferimento

        Returns:
            Lista di dizionari IVA per l'anno
        """
        if self._iva_data is None:
            self.load_iva_data()

        return [row for row in self._iva_data if row.get('anno') == year]

    def get_iva_data_for_year_user(self, year: int, user_name: str) -> List[Dict[str, Any]]:
        """
        Restituisce i dati IVA trimestrali per anno e utente.

        Args:
            year: Anno
            user_name: Nome utente (es. "Mario Rossi")

        Returns:
            Lista di trimestri IVA
        """
        data = self.get_iva_data_for_year(year)
        return [row for row in data if row.get('utente') == user_name]

    def get_iva_summary_for_year(self, year: int) -> Dict[str, Any]:
        """
        Restituisce un riepilogo IVA annuale aggregato per utente.

        Args:
            year: Anno

        Returns:
            Dict {utente: {debito, credito, da_pagare}}
        """
        iva_data = self.get_iva_data_for_year(year)
        summary = {}

        for row in iva_data:
            user = row.get('utente')
            if not user:
                continue

            if user not in summary:
                summary[user] = {
                    'iva_debito': 0.0,
                    'iva_credito': 0.0,
                    'iva_da_pagare': 0.0
                }

            summary[user]['iva_debito'] += row.get('iva_debito', 0.0)
            summary[user]['iva_credito'] += row.get('iva_credito', 0.0)
            summary[user]['iva_da_pagare'] += row.get('iva_da_pagare', 0.0)

        return summary

    def get_annual_data_for_year(self, year: int) -> Optional[Dict[str, Any]]:
        """
        Restituisce i dati annuali per un anno specifico.

        Args:
            year: Anno da cercare

        Returns:
            Dizionario con i dati annuali per l'anno specificato, None se non trovato
        """
        if self._annual_data is None:
            self.load_annual_data()

        for data in self._annual_data:
            if data.get('anno') == year:
                return data

        return None

    def get_monthly_data_for_year(self, year: int) -> List[Dict[str, Any]]:
        """
        Restituisce i dati mensili per un anno specifico.

        Args:
            year: Anno da filtrare

        Returns:
            Lista di dizionari con i dati mensili per l'anno specificato
        """
        if self._monthly_data is None:
            self.load_monthly_data()

        monthly_data = []
        for data in self._monthly_data:
            if data.get('anno') == year:
                monthly_data.append(data)

        # Ordina per mese
        monthly_data.sort(key=lambda x: x.get('mese', 0))
        return monthly_data

    def get_taxes_data_for_year(self, year: int) -> List[Dict[str, Any]]:
        """
        Restituisce i dati delle tasse per un anno specifico.

        Args:
            year: Anno di riferimento

        Returns:
            Lista di dizionari con i dati delle tasse
        """
        if self._taxes_data is None:
            self.load_taxes_data()

        return [row for row in self._taxes_data if row.get('anno') == year]

    def get_taxes_data_for_year_user(self, year: int, user_name: str) -> Optional[Dict[str, Any]]:
        """
        Restituisce i dati delle tasse per anno e utente.

        Args:
            year: Anno
            user_name: Nome utente ("Nome Cognome")

        Returns:
            Dizionario con i dati fiscali o None
        """
        data = self.get_taxes_data_for_year(year)
        for row in data:
            # MODIFICA: usa nome_utente invece di utente
            if row.get('nome_utente') == user_name and row.get('nome_utente') != 'TOTALE':
                return row
        return None

    def get_taxes_totals_for_year(self, year: int) -> Optional[Dict[str, Any]]:
        """
        Restituisce i totali fiscali aggregati per un anno.

        Args:
            year: Anno

        Returns:
            Dizionario con i totali o None
        """
        data = self.get_taxes_data_for_year(year)
        for row in data:
            # MODIFICA: controlla se nome_utente è 'TOTALE'
            if row.get('nome_utente') == 'TOTALE':
                return row
        return None

    def get_taxes_summary_for_year(self, year: int) -> Dict[str, Any]:
        """
        Restituisce un riepilogo fiscale per anno, separando utenti e totale.

        Returns:
            {
                "users": { user_name: {...} },
                "totale": {...}
            }
        """
        data = self.get_taxes_data_for_year(year)

        summary = {
            "users": {},
            "totale": None
        }

        for row in data:
            if row.get('nome_utente') == 'TOTALE':  # MODIFICA: usa nome_utente
                summary['totale'] = row
            else:
                user_name = row.get('nome_utente')  # MODIFICA: usa nome_utente
                if user_name:
                    summary['users'][user_name] = row

        return summary

    def get_monthly_data_for_year_month(self, year: int, month: int) -> Optional[Dict[str, Any]]:
        """
        Restituisce i dati mensili per un anno e mese specifici.

        Args:
            year: Anno
            month: Mese (1-12)

        Returns:
            Dizionario con i dati mensili, None se non trovato
        """
        monthly_data = self.get_monthly_data_for_year(year)

        for data in monthly_data:
            if data.get('mese') == month:
                return data

        return None

    def get_financial_indicators(self, year: int = None) -> Dict[str, Any]:
        """
        Restituisce indicatori finanziari aggregati.

        Args:
            year: Anno specifico (se None, usa tutti gli anni)

        Returns:
            Dizionario con indicatori finanziari
        """
        annual_df = self.get_annual_dataframe()

        if annual_df.empty:
            return {}

        # Filtra per anno se specificato
        if year:
            df = annual_df[annual_df['anno'] == year]
            if df.empty:
                return {}
        else:
            df = annual_df

        indicators = {
            'years_available': self.get_years_available(),
            'latest_year': int(df['anno'].max()) if not df.empty else None,
            'total_years': len(df),
            'total_revenue': float(df['totale_fatturato'].sum()) if 'totale_fatturato' in df.columns else 0,
            'total_expenses': float(df['totale_spese'].sum()) if 'totale_spese' in df.columns else 0,
            'avg_invoice_amount': float(df['media_fatture'].mean()) if 'media_fatture' in df.columns else 0,
            'avg_production_hours': float(
                df['media_ore_per_produzione'].mean()) if 'media_ore_per_produzione' in df.columns else 0,
            'avg_hourly_rate': float(
                df['media_prezzo_orario_produzione'].mean()) if 'media_prezzo_orario_produzione' in df.columns else 0,
        }

        # Calcola indicatori aggiuntivi
        if indicators['total_revenue'] > 0:
            indicators['profit_margin'] = ((indicators['total_revenue'] - indicators['total_expenses']) /
                                           indicators['total_revenue']) * 100
        else:
            indicators['profit_margin'] = 0

        return indicators

    def get_monthly_trends(self, year: int = None) -> Dict[str, Any]:
        """
        Restituisce trend mensili per visualizzazione.

        Args:
            year: Anno specifico (se None, usa l'anno più recente)

        Returns:
            Dizionario con dati per trend mensili
        """
        if year is None:
            years = self.get_years_available()
            if not years:
                return {}
            year = years[-1]  # Usa l'anno più recente

        monthly_data = self.get_monthly_data_for_year(year)
        if not monthly_data:
            return {}

        # Estrae dati per grafici
        trends = {
            'year': year,
            'months': [],
            'revenue': [],
            'expenses': [],
            'incomes': [],
            'outcomes': [],
            'balance': [],
            'avg_salary': [],
            'operating_margin': [],
            'net_balance': []
        }

        months_ita = ['Gen', 'Feb', 'Mar', 'Apr', 'Mag', 'Giu',
                      'Lug', 'Ago', 'Set', 'Ott', 'Nov', 'Dic']

        for data in monthly_data:
            month_num = data.get('mese', 0)
            if 1 <= month_num <= 12:
                trends['months'].append(months_ita[month_num - 1])
                trends['revenue'].append(data.get('fatturato', 0))
                trends['expenses'].append(data.get('spese', 0))
                trends['incomes'].append(data.get('entrate', 0))
                trends['outcomes'].append(data.get('uscite', 0))
                trends['balance'].append(data.get('bilancio_mensile', 0))
                trends['avg_salary'].append(data.get('salario_medio_utente', 0))
                trends['operating_margin'].append(data.get('margine_operativo_percentuale', 0))
                trends['net_balance'].append(data.get('saldo_netto', 0))

        return trends

    def get_iva_trimestral_trends(self, year: int, user_name: str = None) -> Dict[str, Any]:
        """
        Restituisce i trend IVA trimestrali per visualizzazione.

        Args:
            year: Anno
            user_name: (opzionale) filtro per utente

        Returns:
            Dizionario pronto per grafici
        """
        data = self.get_iva_data_for_year(year)
        if user_name:
            data = [d for d in data if d.get('utente') == user_name]

        if not data:
            return {}

        trends = {
            'year': year,
            'trimesters': [],
            'iva_debito': [],
            'iva_credito': [],
            'iva_da_pagare': []
        }

        data.sort(key=lambda x: x.get('trimestre', 0))

        for row in data:
            trends['trimesters'].append(row.get('nome_trimestre'))
            trends['iva_debito'].append(row.get('iva_debito', 0))
            trends['iva_credito'].append(row.get('iva_credito', 0))
            trends['iva_da_pagare'].append(row.get('iva_da_pagare', 0))

        return trends

    def get_comparison_data(self, years: List[int] = None) -> Dict[str, Any]:
        """
        Restituisce dati comparativi tra anni diversi.

        Args:
            years: Lista di anni da confrontare (se None, confronta tutti gli anni disponibili)

        Returns:
            Dizionario con dati comparativi
        """
        annual_df = self.get_annual_dataframe()

        if annual_df.empty:
            return {}

        if years:
            df = annual_df[annual_df['anno'].isin(years)]
        else:
            df = annual_df

        if df.empty:
            return {}

        comparison = {
            'years': df['anno'].tolist(),
            'revenue': df['totale_fatturato'].tolist() if 'totale_fatturato' in df.columns else [],
            'expenses': df['totale_spese'].tolist() if 'totale_spese' in df.columns else [],
            'profit': [],
            'avg_invoice': df['media_fatture'].tolist() if 'media_fatture' in df.columns else [],
            'irpef': df['irpef_willow'].tolist() if 'irpef_willow' in df.columns else [],
            'inps': df['inps_willow'].tolist() if 'inps_willow' in df.columns else []
        }

        # Calcola il profitto per ogni anno
        for rev, exp in zip(comparison['revenue'], comparison['expenses']):
            comparison['profit'].append(rev - exp)

        return comparison

    def get_account_balances_over_time(self) -> Dict[str, Any]:
        """
        Restituisce l'andamento dei saldi dei conti nel tempo.

        Returns:
            Dizionario con saldi dei conti per ogni anno
        """
        annual_df = self.get_annual_dataframe()

        if annual_df.empty:
            return {}

        # Trova tutte le colonne che iniziano con 'saldo_'
        account_columns = [col for col in annual_df.columns if col.startswith('saldo_')]

        if not account_columns:
            return {}

        # Estrae i dati
        balances = {
            'years': annual_df['anno'].tolist(),
            'accounts': {}
        }

        for account_col in account_columns:
            account_name = account_col.replace('saldo_', '').replace('_', ' ')
            balances['accounts'][account_name] = annual_df[account_col].tolist()

        return balances

    def get_summary_for_view(self) -> Dict[str, Any]:
        """
        Restituisce un riepilogo completo per la View.

        Returns:
            Dizionario con tutti i dati necessari per la visualizzazione
        """
        summary = {
            'annual_data': self.get_annual_dataframe().to_dict(
                'records') if not self.get_annual_dataframe().empty else [],
            'monthly_data': self.get_monthly_dataframe().to_dict(
                'records') if not self.get_monthly_dataframe().empty else [],
            'iva_data': self.get_iva_dataframe().to_dict(
                'records') if not self.get_iva_dataframe().empty else [],
            'taxes_data': self.get_taxes_dataframe().to_dict(
                'records') if not self.get_taxes_dataframe().empty else [],
            'financial_indicators': self.get_financial_indicators(),
            'available_years': self.get_years_available(),
            'latest_year_trends': self.get_monthly_trends(),
            'comparison_data': self.get_comparison_data(),
            'account_balances': self.get_account_balances_over_time()
        }

        # Aggiungi l'anno corrente se disponibile
        if summary['available_years']:
            latest_year = summary['available_years'][-1]
            summary['latest_year_data'] = self.get_annual_data_for_year(latest_year)
            summary['iva_latest_year'] = self.get_iva_summary_for_year(latest_year)
            summary['taxes_latest_year'] = self.get_taxes_summary_for_year(latest_year)


        return summary
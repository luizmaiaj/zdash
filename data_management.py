from dataclasses import dataclass, field
import os
import pickle
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd
import logging
from odoo import fetch_and_process_data

@dataclass
class DataManager:
    DATA_FILE: str = 'odoo_data.pkl'
    LAST_UPDATE_FILE: str = 'last_update.json'
    JOB_COSTS_FILE: str = 'job_costs.json'
    FINANCIALS_FILE: str = 'financials_data.json'
    LAST_CALCULATION_FILE: str = 'last_financials_calculation.json'

    df_portfolio: pd.DataFrame = field(default_factory=pd.DataFrame)
    df_employees: pd.DataFrame = field(default_factory=pd.DataFrame)
    df_sales: pd.DataFrame = field(default_factory=pd.DataFrame)
    df_timesheet: pd.DataFrame = field(default_factory=pd.DataFrame)
    df_tasks: pd.DataFrame = field(default_factory=pd.DataFrame)
    job_costs: Dict = field(default_factory=dict)
    financials_data: Dict = field(default_factory=dict)
    last_update: Optional[datetime] = None
    data_loaded: bool = field(default_factory=bool)

    def __post_init__(self):
        self.data_loaded = False
        self.load_all_data()

    def load_all_data(self, force: bool = False):
        if self.data_loaded and not force:
            logging.warning('Data already loaded')
            return
        
        logging.info('Loading data with force = %s', force)
        data, self.last_update = self.load_or_fetch_data(force)
        self.df_portfolio, self.df_employees, self.df_sales, self.df_timesheet, self.df_tasks = data
        self.job_costs = self.load_job_costs()
        self.financials_data = self.load_financials_data()

        self.process_job_titles() # check for any new job titles

        self.data_loaded = True

        self.print_data_summary()

    def process_job_titles(self):
        if 'job_title' in self.df_employees.columns:
            unique_job_titles = self.df_employees['job_title'].unique()
        elif 'job_id' in self.df_employees.columns:
            unique_job_titles = self.df_employees['job_id'].apply(
                lambda x: x[1] if isinstance(x, (list, tuple)) and len(x) > 1 else x
            ).unique()
        else:
            logging.warning("No job title or job id column found in employees data")
            return

        for title in unique_job_titles:
            if title and title not in self.job_costs:
                self.job_costs[title] = {'cost': '', 'revenue': ''}
        
        logging.info(f"Processed job titles. Total unique titles: {len(unique_job_titles)}")
    
    def print_data_summary(self):
        logging.info("\n--- Data Summary ---")
        logging.info(f"Portfolio: {len(self.df_portfolio)} projects")
        logging.info(f"Employees: {len(self.df_employees)} employees")
        logging.info(f"Sales: {len(self.df_sales)} records")
        logging.info(f"Timesheet: {len(self.df_timesheet)} entries")
        logging.info(f"Tasks: {len(self.df_tasks)} tasks")
        logging.info(f"Job Costs: {len(self.job_costs)} job titles")
        logging.info(f"Financials: {len(self.financials_data)} project financials")
        logging.info(f"Last Update: {self.last_update}")
        logging.info("--- End of Summary ---\n")

    @staticmethod
    def serialize_dataframes(data: List[pd.DataFrame]) -> List[Dict]:
        return [df.to_dict(orient='records') if not df.empty else {} for df in data]

    @staticmethod
    def deserialize_dataframes(data: List[Dict]) -> List[pd.DataFrame]:
        return [pd.DataFrame(df_data) if df_data else pd.DataFrame() for df_data in data]

    def get_last_update_time(self) -> Optional[datetime]:
        if os.path.exists(self.LAST_UPDATE_FILE):
            with open(self.LAST_UPDATE_FILE, 'r') as f:
                last_update = json.load(f)
            return datetime.fromisoformat(last_update['time'])
        return None

    def set_last_update_time(self, time: datetime):
        with open(self.LAST_UPDATE_FILE, 'w') as f:
            json.dump({'time': time.isoformat()}, f)

    def load_cached_data(self) -> Optional[List[pd.DataFrame]]:
        if os.path.exists(self.DATA_FILE):
            with open(self.DATA_FILE, 'rb') as f:
                data = pickle.load(f)
            return self.deserialize_dataframes(data)
        return None

    def save_cached_data(self, data: List[pd.DataFrame]):
        with open(self.DATA_FILE, 'wb') as f:
            pickle.dump(self.serialize_dataframes(data), f)

    @staticmethod
    def merge_new_data(old_data: List[pd.DataFrame], new_data: List[pd.DataFrame]) -> List[pd.DataFrame]:
        merged_data = []
        for old_df, new_df in zip(old_data, new_data):
            for df in [old_df, new_df]:
                for col in df.columns:
                    if df[col].dtype == 'object':
                        df[col] = df[col].apply(lambda x: str(x) if isinstance(x, list) else x)
            
            all_columns = list(set(old_df.columns) | set(new_df.columns))
            old_df = old_df.reindex(columns=all_columns)
            new_df = new_df.reindex(columns=all_columns)
            
            old_df = old_df.dropna(axis=1, how='all')
            new_df = new_df.dropna(axis=1, how='all')
            
            if 'id' in old_df.columns and 'id' in new_df.columns:
                merged_df = pd.concat([old_df, new_df], ignore_index=True).drop_duplicates(subset='id', keep='last')
            else:
                merged_df = pd.concat([old_df, new_df], ignore_index=True).drop_duplicates()
            merged_data.append(merged_df)
        return merged_data

    def load_job_costs(self) -> Dict:
        if os.path.exists(self.JOB_COSTS_FILE):
            with open(self.JOB_COSTS_FILE, 'r') as f:
                return json.load(f)
        return {}

    def save_job_costs(self):
        with open(self.JOB_COSTS_FILE, 'w') as f:
            json.dump(self.job_costs, f)

    def load_or_fetch_data(self, force: bool = False) -> tuple:
        cached_data = self.load_cached_data()
        last_update = self.get_last_update_time()
        current_time = datetime.now()

        if cached_data is None or last_update is None:
            logging.info("No cached data found. Fetching all data...")
            new_data = fetch_and_process_data()
            if new_data and all(df is not None for df in new_data):
                self.save_cached_data(new_data)
                self.set_last_update_time(current_time)
                return new_data, current_time
            else:
                logging.error("Failed to fetch data.")
                return [pd.DataFrame() for _ in range(5)], current_time

        logging.info(f"Loading cached data from {last_update}")
        
        if force or (current_time - last_update) > timedelta(days=1):
            logging.info("Cached data is old or force refresh requested. Fetching update...")
            new_data = fetch_and_process_data(last_update - timedelta(hours=3))
            if new_data and all(df is not None for df in new_data):
                merged_data = self.merge_new_data(cached_data, new_data)
                self.save_cached_data(merged_data)
                self.set_last_update_time(current_time)
                return merged_data, current_time
            else:
                logging.error("Failed to fetch update. Using cached data.")
        
        return cached_data, last_update

    def save_financials_data(self, new_financials_data={}):

        if new_financials_data:
            self.financials_data = new_financials_data

        with open(self.FINANCIALS_FILE, 'w') as f:
            json.dump(self.financials_data, f, cls=DateTimeEncoder)

    def load_financials_data(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Dict:
        logging.info(f"Loading financial data. Start date: {start_date}, End date: {end_date}")
        if os.path.exists(self.FINANCIALS_FILE):
            with open(self.FINANCIALS_FILE, 'r') as f:
                data = json.load(f)
            logging.info(f"Loaded data for {len(data)} projects from file")

            filtered_data = {}
            for project, project_data in data.items():
                logging.debug(f"Processing project: {project}")
                filtered_daily_data = []
                for daily_data in project_data['daily_data']:
                    date = pd.to_datetime(daily_data['date'])
                    if (start_date is None or date >= start_date) and (end_date is None or date <= end_date):
                        filtered_daily_data.append(daily_data)
                
                logging.debug(f"Project {project}: {len(filtered_daily_data)} days of data after date filtering")
                
                if filtered_daily_data:
                    total_hours = sum(day['unit_amount'] for day in filtered_daily_data)
                    # Calculate the fraction of total hours that fall within the date range
                    hours_fraction = total_hours / project_data['total_hours'] if project_data['total_hours'] > 0 else 0
                    # Calculate the prorated revenue based on the fraction of hours
                    prorated_revenue = project_data['total_revenue'] * hours_fraction

                    filtered_data[project] = {
                        'total_revenue': prorated_revenue,
                        'total_hours': total_hours,
                        'daily_data': filtered_daily_data
                    }
                    logging.debug(f"Project {project} calculated revenue: {prorated_revenue}")

            # If no data falls within the specified range, return all available data
            if not filtered_data:
                logging.warning("No data found within specified date range. Returning all available data.")
                return data

            total_revenue = sum(project_data['total_revenue'] for project_data in filtered_data.values())
            total_hours = sum(project_data['total_hours'] for project_data in filtered_data.values())
            logging.info(f"Total revenue across all projects: {total_revenue}")
            logging.info(f"Total hours across all projects: {total_hours}")

            return filtered_data
        else:
            logging.warning(f"Financial data file {self.FINANCIALS_FILE} not found")
            return {}

    def get_last_calculation_time(self) -> Optional[datetime]:
        if os.path.exists(self.LAST_CALCULATION_FILE):
            with open(self.LAST_CALCULATION_FILE, 'r') as f:
                return datetime.fromisoformat(json.load(f)['time'])
        return None

    def set_last_calculation_time(self, time: datetime):
        with open(self.LAST_CALCULATION_FILE, 'w') as f:
            json.dump({'time': time.isoformat()}, f)

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat()
        return super().default(obj)

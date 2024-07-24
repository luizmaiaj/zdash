# In data_management.py

import os
import pickle
import json
from datetime import datetime, timedelta
import pandas as pd
from odoo import fetch_and_process_data

DATA_FILE = 'odoo_data.pkl'
LAST_UPDATE_FILE = 'last_update.json'

def serialize_dataframes(data):
    return [df.to_dict(orient='records') if not df.empty else {} for df in data]

def deserialize_dataframes(data):
    return [pd.DataFrame(df_data) if df_data else pd.DataFrame() for df_data in data]

def get_last_update_time():
    if os.path.exists(LAST_UPDATE_FILE):
        with open(LAST_UPDATE_FILE, 'r') as f:
            last_update = json.load(f)
        return datetime.fromisoformat(last_update['time'])
    return None

def set_last_update_time(time):
    with open(LAST_UPDATE_FILE, 'w') as f:
        json.dump({'time': time.isoformat()}, f)

def load_cached_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'rb') as f:
            data = pickle.load(f)
        return deserialize_dataframes(data)
    return None

def save_cached_data(data):
    with open(DATA_FILE, 'wb') as f:
        pickle.dump(serialize_dataframes(data), f)

def merge_new_data(old_data, new_data):
    merged_data = []
    for old_df, new_df in zip(old_data, new_data):
        # Convert list columns to strings to make them hashable
        for col in old_df.columns:
            if old_df[col].dtype == 'object':
                old_df[col] = old_df[col].apply(lambda x: str(x) if isinstance(x, list) else x)
        for col in new_df.columns:
            if new_df[col].dtype == 'object':
                new_df[col] = new_df[col].apply(lambda x: str(x) if isinstance(x, list) else x)
        
        # Ensure both DataFrames have the same columns
        all_columns = list(set(old_df.columns) | set(new_df.columns))
        old_df = old_df.reindex(columns=all_columns)
        new_df = new_df.reindex(columns=all_columns)
        
        # Remove empty or all-NA columns before concatenation
        old_df = old_df.dropna(axis=1, how='all')
        new_df = new_df.dropna(axis=1, how='all')
        
        if 'id' in old_df.columns and 'id' in new_df.columns:
            merged_df = pd.concat([old_df, new_df], ignore_index=True).drop_duplicates(subset='id', keep='last')
        else:
            merged_df = pd.concat([old_df, new_df], ignore_index=True).drop_duplicates()
        merged_data.append(merged_df)
    return merged_data

def load_or_fetch_data(force=False):
    cached_data = load_cached_data()
    last_update = get_last_update_time()
    current_time = datetime.now()

    if cached_data is None or last_update is None:
        print("No cached data found. Fetching all data...")
        new_data = fetch_and_process_data()
        if new_data and all(df is not None for df in new_data):
            save_cached_data(new_data)
            set_last_update_time(current_time)
            return new_data, current_time
        else:
            print("Error: Failed to fetch data.")
            return [pd.DataFrame() for _ in range(6)], current_time

    print(f"Loading cached data from {last_update}")
    
    # Check if data is older than 1 day or if force refresh is requested
    if force or (current_time - last_update) > timedelta(days=1):
        print("Cached data is old or force refresh requested. Fetching update...")
        # Fetch data from last update minus 3 hours to ensure overlap
        new_data = fetch_and_process_data(last_update - timedelta(hours=3))
        if new_data and all(df is not None for df in new_data):
            merged_data = merge_new_data(cached_data, new_data)
            save_cached_data(merged_data)
            set_last_update_time(current_time)
            return merged_data, current_time
        else:
            print("Error: Failed to fetch update. Using cached data.")
    
    return cached_data, last_update

def refresh_data(force=False):
    return load_or_fetch_data(force)

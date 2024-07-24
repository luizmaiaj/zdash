import os
import pickle
import json
from datetime import datetime, timedelta
from odoo import fetch_and_process_data
import pandas as pd

DATA_FILE = 'odoo_data.pkl'
LAST_UPDATE_FILE = 'last_update.json'

def serialize_dataframes(data):
    return [df.to_dict(orient='records') for df in data]

def deserialize_dataframes(data):
    return [pd.DataFrame(df_data) for df_data in data]

def get_last_update_time():
    if os.path.exists(LAST_UPDATE_FILE):
        with open(LAST_UPDATE_FILE, 'r') as f:
            last_update = json.load(f)
        return datetime.fromisoformat(last_update['time'])
    return None

def set_last_update_time(time):
    with open(LAST_UPDATE_FILE, 'w') as f:
        json.dump({'time': time.isoformat()}, f)

def load_or_fetch_data():
    last_update = get_last_update_time()
    current_time = datetime.now()

    if last_update is None or (current_time - last_update) > timedelta(hours=1) or not os.path.exists(DATA_FILE):
        print("Fetching new data from Odoo...")
        new_data = fetch_and_process_data()
        
        if new_data and all(df is not None for df in new_data):
            with open(DATA_FILE, 'wb') as f:
                pickle.dump(serialize_dataframes(new_data), f)
            set_last_update_time(current_time)
            return new_data, current_time
        else:
            print("Error: Failed to fetch valid data from Odoo.")
            if os.path.exists(DATA_FILE):
                print("Loading last saved data...")
                with open(DATA_FILE, 'rb') as f:
                    data = pickle.load(f)
                return deserialize_dataframes(data), last_update
            else:
                print("No saved data available. Initializing with empty DataFrames.")
                return [pd.DataFrame() for _ in range(6)], current_time
    else:
        print("Loading data from cache...")
        with open(DATA_FILE, 'rb') as f:
            data = pickle.load(f)
        return deserialize_dataframes(data), last_update

def update_existing_data(existing_data, new_data):
    """
    Update existing data with new data, handling potential new records and updates.
    """
    updated_data = []
    for existing_df, new_df in zip(existing_data, new_data):
        if existing_df is not None and new_df is not None:
            if 'id' in existing_df.columns and 'id' in new_df.columns:
                # Merge based on 'id' column if it exists
                merged_df = pd.concat([existing_df, new_df]).drop_duplicates(subset='id', keep='last')
            else:
                # If no 'id' column, just append new data
                merged_df = pd.concat([existing_df, new_df]).drop_duplicates()
            updated_data.append(merged_df)
        elif new_df is not None:
            # If existing_df is None, use the new_df
            updated_data.append(new_df)
        else:
            # If both are None or only existing_df exists, append existing_df (or None)
            updated_data.append(existing_df)
    return updated_data

def refresh_data():
    print("Forcing data refresh...")
    new_data = fetch_and_process_data()
    if new_data and all(df is not None for df in new_data):
        with open(DATA_FILE, 'wb') as f:
            pickle.dump(serialize_dataframes(new_data), f)
        current_time = datetime.now()
        set_last_update_time(current_time)
        return new_data, current_time
    else:
        print("Error: Failed to fetch valid data during refresh. Loading last saved data...")
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'rb') as f:
                data = pickle.load(f)
            last_update = get_last_update_time()
            return deserialize_dataframes(data), last_update
        else:
            print("No saved data available. Initializing with empty DataFrames.")
            empty_data = [pd.DataFrame() for _ in range(6)]
            current_time = datetime.now()
            return empty_data, current_time

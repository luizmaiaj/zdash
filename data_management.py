import os
import pandas as pd
import pickle
import json
from datetime import datetime, timedelta
from odoo import fetch_and_process_data
import pandas as pd

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
            return load_cached_data(last_update)
    else:
        print("Loading data from cache...")
        return load_cached_data(last_update)

def load_cached_data(last_update):
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'rb') as f:
            data = pickle.load(f)
        deserialized_data = deserialize_dataframes(data)
        
        # Validate the deserialized data
        if all(isinstance(df, pd.DataFrame) for df in deserialized_data):
            print("Successfully loaded data from cache.")
            return deserialized_data, last_update
        else:
            print("Error: Invalid data format in cache.")
    
    print("No valid cached data available. Initializing with empty DataFrames.")
    return [pd.DataFrame() for _ in range(6)], datetime.now()

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

# Update the refresh_data function similarly
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
        print("Error: Failed to fetch valid data during refresh.")
        return load_cached_data(get_last_update_time())

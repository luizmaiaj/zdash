import os
import pickle
import json
from datetime import datetime, timedelta
from odoo import fetch_and_process_data
import pandas as pd

DATA_FILE = 'odoo_data.pkl'
LAST_UPDATE_FILE = 'last_update.json'

def serialize_dataframes(data):
    """
    Serialize pandas DataFrames to JSON-compatible format.
    """
    return [df.to_dict(orient='records') for df in data]

def deserialize_dataframes(data):
    """
    Deserialize JSON data back to pandas DataFrames.
    """
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

    if last_update is None or (current_time - last_update) > timedelta(hours=1):
        # Fetch new data if no previous update or if it's been more than an hour
        new_data = fetch_and_process_data(last_update)
        
        if os.path.exists(DATA_FILE):
            # Load existing data and update with new data
            with open(DATA_FILE, 'rb') as f:
                existing_data = pickle.load(f)
            
            if existing_data and all(isinstance(df, pd.DataFrame) for df in existing_data):
                updated_data = update_existing_data(existing_data, new_data)
            else:
                updated_data = new_data
        else:
            updated_data = new_data

        # Save updated data
        with open(DATA_FILE, 'wb') as f:
            pickle.dump(serialize_dataframes(updated_data), f)
        
        set_last_update_time(current_time)
        return updated_data, current_time
    else:
        # Load existing data if it's recent enough
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
    """
    Force a refresh of all data.
    """
    new_data = fetch_and_process_data()  # Changed this line
    with open(DATA_FILE, 'wb') as f:
        pickle.dump(serialize_dataframes(new_data), f)
    set_last_update_time(datetime.now())
    return new_data, datetime.now()

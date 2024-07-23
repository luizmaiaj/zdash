import os
import pickle
import json
from datetime import datetime
from odoo import fetch_and_process_data
import pandas as pd

DATA_FILE = 'odoo_data.pkl'

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

def load_or_fetch_data():
    """
    Load data from file if it exists, otherwise fetch from Odoo and save to file.
    """
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'rb') as f:
            data = pickle.load(f)
        last_updated = datetime.fromtimestamp(os.path.getmtime(DATA_FILE))
        return deserialize_dataframes(data), last_updated
    else:
        return refresh_data()

def refresh_data():
    """
    Fetch fresh data from Odoo and save to file.
    """
    data = fetch_and_process_data()
    serialized_data = serialize_dataframes(data)
    with open(DATA_FILE, 'wb') as f:
        pickle.dump(serialized_data, f)
    last_updated = datetime.now()
    return data, last_updated

def get_last_update_time():
    """
    Get the last update time of the data file.
    """
    if os.path.exists(DATA_FILE):
        return datetime.fromtimestamp(os.path.getmtime(DATA_FILE))
    return None

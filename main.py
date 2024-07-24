import dash
from dash import dcc, html
from datetime import datetime, timedelta
import pandas as pd
from callbacks import register_callbacks
from llm_integration import check_ollama_status, extract_model_names
from data_management import load_or_fetch_data, get_last_update_time

# Load or fetch data
data, last_updated = load_or_fetch_data()
df_projects, df_employees, df_sales, df_financials, df_timesheet, df_tasks = data

if df_projects is None:
    print("Error: Unable to fetch data from Odoo. Please check your connection and try again.")
    exit(1)

# Print column names for debugging
print("df_projects columns:", df_projects.columns)

# Get available models
ollama_running, available_models = check_ollama_status()
if ollama_running:
    model_options = [{'label': model, 'value': model} for model in extract_model_names(available_models)]
else:
    model_options = []

# Initialize Dash app
app = dash.Dash(__name__)

# Function to safely get unique values from a DataFrame column
def safe_unique_values(df, column_name):
    if column_name in df.columns:
        return [{'label': i, 'value': i} for i in sorted(df[column_name].unique()) if pd.notna(i)]
    else:
        print(f"Warning: '{column_name}' column not found in DataFrame")
        return []

# Layout
app.layout = html.Div([
    html.Div([
        html.H1("Odoo Interactive Dashboard", style={'display': 'inline-block'}),
        html.Div([
            html.Button('Refresh Data', id='refresh-data', n_clicks=0),
            html.Span(id='last-update-time', style={'margin-left': '10px'})
        ], style={'float': 'right', 'margin-top': '20px'})
    ]),
    
    # Date range selector
    dcc.DatePickerRange(
        id='date-range',
        start_date=datetime.now().date() - timedelta(days=30),
        end_date=datetime.now().date()
    ),
    
    # Project filter
    dcc.Dropdown(
        id='project-filter',
        options=safe_unique_values(df_projects, 'name'),
        multi=True,
        placeholder="Select projects"
    ),
    
    # Employee filter
    dcc.Dropdown(
        id='employee-filter',
        options=safe_unique_values(df_employees, 'name'),
        multi=True,
        placeholder="Select employees"
    ),
    
    # Tabs for different dashboards
    dcc.Tabs([
        dcc.Tab(label='Global KPI', children=[
            html.Div([
                dcc.Graph(id='global-map'),
                dcc.Graph(id='global-kpi-chart')
            ])
        ]),
        dcc.Tab(label='Financials', children=[
            html.Div([
                dcc.Graph(id='financials-chart')
            ])
        ]),
        dcc.Tab(label='Projects', children=[
            html.Div([
                html.Div([
                    dcc.Graph(id='projects-hours-chart'),
                    dcc.Input(id='projects-hours-height', type='number', placeholder='Min height (px)', value=400)
                ]),
                html.Div([
                    dcc.Graph(id='projects-tasks-chart')
                ])
            ])
        ]),
        dcc.Tab(label='Project', value='project-tab', children=[
            html.Div([
                dcc.Dropdown(
                    id='project-selector',
                    options=safe_unique_values(df_projects, 'name'),
                    placeholder="Select a project"
                ),
                dcc.Graph(id='project-tasks-employees-chart')
            ])
        ]),
        dcc.Tab(label='Employees', children=[
            html.Div([
                html.H3(id='total-hours'),
                html.Div([
                    dcc.Graph(id='employee-hours-chart'),
                    dcc.Input(id='employee-chart-height', type='number', placeholder='Min height (px)', value=400)
                ])
            ])
        ]),
        dcc.Tab(label='Sales', children=[
            html.Div([
                dcc.Graph(id='sales-chart'),
                dcc.Input(id='sales-task-filter', type='text', placeholder='Enter task keywords (comma-separated)'),
                html.Button('Apply Filter', id='apply-sales-filter')
            ])
        ]),
        dcc.Tab(label='Reporting', children=[
            html.Div([
                html.H3("Data Quality Report"),
                html.Div(id='data-quality-report'),
                html.Div([
                    dcc.Dropdown(
                        id='model-selection',
                        options=model_options,
                        value=model_options[0]['value'] if model_options else None,
                        placeholder="Select a model",
                        style={'width': '300px', 'margin-bottom': '10px'}
                    ),
                    html.Button('Generate LLM Report', id='generate-llm-report', n_clicks=0),
                ]),
                html.Div(id='llm-report-output'),
                html.Div(id='long-tasks-list')
            ])
        ]),
    ], id='tabs'),

    # Store for holding the current data
    dcc.Store(id='data-store')
])

# Register callbacks
register_callbacks(app, df_projects, df_employees, df_sales, df_financials, df_timesheet, df_tasks)

if __name__ == '__main__':
    app.run_server(debug=True)

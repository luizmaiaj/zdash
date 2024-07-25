from datetime import datetime, timedelta
import ast

import dash
from dash import dcc, html, dash_table
import pandas as pd
from callbacks.callbacks import register_callbacks
from llm_integration import check_ollama_status, extract_model_names
from data_management import load_or_fetch_data, load_job_costs
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

# Load or fetch data
data, last_updated = load_or_fetch_data()
df_portfolio, df_employees, df_sales, df_financials, df_timesheet, df_tasks = data

job_costs = load_job_costs()

# Function to safely get DataFrame columns and process job_id
def safe_get_columns(df, columns):
    result = df[[col for col in columns if col in df.columns]].copy()
    if 'job_id' in result.columns:
        result['job_id_original'] = result['job_id']
        result['job_id'] = result['job_id_original'].apply(
            lambda x: ast.literal_eval(str(x))[0] if isinstance(x, (list, str)) and str(x).startswith('[') else x
        )
        result['job_title'] = result['job_id_original'].apply(
            lambda x: ast.literal_eval(str(x))[1] if isinstance(x, (list, str)) and str(x).startswith('[') else ''
        )
        result.drop('job_id_original', axis=1, inplace=True)
    return result

# Process df_employees to extract job titles
df_employees_processed = safe_get_columns(df_employees, ['name', 'job_id', 'job_title'])
unique_job_titles = df_employees_processed['job_title'].unique()

# Update job_costs with new job titles if they don't exist
for title in unique_job_titles:
    if title and title not in job_costs:
        job_costs[title] = {'cost': '', 'revenue': ''}

if df_portfolio is None:
    print("Error: Unable to fetch data from Odoo. Please check your connection and try again.")
    exit(1)

# Print column names for debugging
print("df_portfolio columns:", df_portfolio.columns)

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
        options=safe_unique_values(df_portfolio, 'name'),
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
        dcc.Tab(label='Portfolio', children=[
            html.Div([
                html.Div([
                    dcc.Graph(id='portfolio-hours-chart'),
                    dcc.Input(id='portfolio-hours-height', type='number', placeholder='Min height (px)', value=400)
                ]),
                html.Div([
                    dcc.Graph(id='portfolio-tasks-chart')
                ])
            ])
        ]),
        dcc.Tab(label='Project', value='project-tab', children=[
            html.Div([
                dcc.Dropdown(
                    id='project-selector',
                    options=safe_unique_values(df_portfolio, 'name'),
                    placeholder="Select a project"
                ),
                dcc.RadioItems(
                    id='man-hours-toggle',
                    options=[
                        {'label': 'Man Hours', 'value': True},
                        {'label': 'Man Days', 'value': False}
                    ],
                    value=True,
                    inline=True
                ),
                html.Div(id='project-total-revenue', style={'font-weight': 'bold', 'margin-top': '10px'}),
                dcc.Graph(id='project-timeline-chart'),
                dcc.Graph(id='project-revenue-chart'),
                dcc.Graph(id='project-tasks-employees-chart')
            ])
        ]),
        dcc.Tab(label='Employees', children=[
            html.Div([
                html.H3(id='total-hours'),
                html.Div([
                    dcc.Graph(id='employee-hours-chart'),
                    dcc.Input(id='employee-chart-height', type='number', placeholder='Min height (px)', value=600)
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
        dcc.Tab(label='Settings', value='Settings', children=[
            html.Div([
                html.H3("Job Titles and Costs"),
                html.Button('Save Cost and Revenue', id='save-cost-revenue', n_clicks=0),
                html.Button('Add Job Title', id='add-job-title', n_clicks=0),
                html.Div([
                    dash_table.DataTable(
                        id='job-costs-table',
                        columns=[
                            {'name': 'Job Title', 'id': 'job_title'},
                            {'name': 'Cost (USD/day)', 'id': 'cost'},
                            {'name': 'Revenue (USD/day)', 'id': 'revenue'}
                        ],
                        data=[{'job_title': jt, 'cost': data.get('cost', ''), 'revenue': data.get('revenue', '')} 
                              for jt, data in job_costs.items() if jt],
                        style_table={'height': '300px', 'overflowY': 'auto'},
                        style_header={
                            'backgroundColor': 'rgb(230, 230, 230)',
                            'fontWeight': 'bold'
                        },
                        editable=True,
                        row_deletable=True,
                        style_cell={
                            'textAlign': 'left'
                        },
                        style_cell_conditional=[
                            {
                                'if': {'column_id': 'job_title'},
                                'textAlign': 'left'
                            }
                        ]
                    ),
                ]),
                html.Div(id='job-costs-save-status'),
                html.H3("Employees and Job Titles"),
                html.Div([
                    dash_table.DataTable(
                        id='employees-job-titles-table',
                        columns=[
                            {'name': 'Employee Name', 'id': 'name'},
                            {'name': 'Job ID', 'id': 'job_id'},
                            {'name': 'Job Title', 'id': 'job_title'}
                        ],
                        data=df_employees_processed.to_dict('records'),
                        style_table={'height': '300px', 'overflowY': 'auto'},
                        style_cell={'textAlign': 'left'},
                        style_header={
                            'backgroundColor': 'rgb(230, 230, 230)',
                            'fontWeight': 'bold'
                        },
                        style_data_conditional=[
                            {
                                'if': {'row_index': 'odd'},
                                'backgroundColor': 'rgb(248, 248, 248)'
                            }
                        ]
                    )
                ])
            ])
        ])
    ], id='tabs'),

    # Store for holding the current data
    dcc.Store(id='data-store')
])

# Register callbacks
register_callbacks(app, df_portfolio, df_employees, df_sales, df_financials, df_timesheet, df_tasks, job_costs)

if __name__ == '__main__':
    app.run_server(debug=True)

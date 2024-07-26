from datetime import datetime, timedelta
import ast

import logging

import dash
from dash import dcc, html, dash_table
import pandas as pd
from dotenv import find_dotenv, load_dotenv

from callbacks.callbacks import register_callbacks
from llm_integration import check_ollama_status, extract_model_names
from data_management import DataManager

load_dotenv(find_dotenv())

# Configure logging
logging.basicConfig(level=logging.WARNING,
                    format='%(asctime)s - %(funcName)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

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

# Function to safely get unique values from a DataFrame column
def safe_unique_values(df, column_name):
    if column_name in df.columns:
        return [{'label': i, 'value': i} for i in sorted(df[column_name].unique()) if pd.notna(i)]
    else:
        logging.warning(f"Column not found in DataFrame '{column_name}' ")
        return []

def create_app():
    # Initialize DataManager
    data_manager = DataManager()

    if data_manager.df_portfolio is None or data_manager.df_portfolio.empty:
        logging.error("Unable to fetch data from Odoo. Please check your connection and try again.")
        return None

    # Process df_employees to extract job titles
    df_employees_processed = safe_get_columns(data_manager.df_employees, ['name', 'job_id', 'job_title'])

    # Get available models
    ollama_running, available_models = check_ollama_status()
    if ollama_running:
        model_options = [{'label': model, 'value': model} for model in extract_model_names(available_models)]
    else:
        model_options = []

    # Initialize Dash app
    app = dash.Dash(__name__)

    # Layout
    app.layout = html.Div([
        html.Div([
            html.H1("Oodash", style={'display': 'inline-block'}),
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
            options=safe_unique_values(data_manager.df_portfolio, 'name'),
            multi=True,
            placeholder="Select projects"
        ),

        # Employee filter
        dcc.Dropdown(
            id='employee-filter',
            options=safe_unique_values(data_manager.df_employees, 'name'),
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
                    html.Button('Calculate Financials', id='calculate-button', n_clicks=0),
                    dcc.Loading(
                        id="loading-financials",
                        type="circle",
                        children=[
                            dcc.Graph(id='financials-chart'),
                            html.Div(id='total-revenue-display'),
                            dcc.Graph(id='all-projects-hours-chart'),
                            dcc.Graph(id='all-projects-revenue-chart'),
                            html.Div(id='calculation-progress')
                        ]
                    )
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
                        options=safe_unique_values(data_manager.df_portfolio, 'name'),
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
                    dcc.Loading(
                        id="loading-project-data",
                        type="circle",
                        children=[
                            dcc.Graph(id='project-timeline-chart'),
                            html.Div([
                                html.Div(id='project-total-revenue', style={'font-weight': 'bold', 'display': 'inline-block', 'margin-right': '20px'}),
                                html.Div(id='project-period-revenue', style={'font-weight': 'bold', 'display': 'inline-block'})
                            ], style={'margin-top': '10px', 'margin-bottom': '10px'}),
                            dcc.Graph(id='project-revenue-chart'),
                            dcc.Graph(id='project-tasks-employees-chart')
                        ]
                    )
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
                                for jt, data in data_manager.job_costs.items() if jt],
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
            ]),
            dcc.Tab(label='Pivot Table', children=[
                html.Div([
                    html.Div([
                        dcc.Dropdown(
                            id='pivot-dataframe-selector',
                            options=[
                                {'label': 'Portfolio', 'value': 'df_portfolio'},
                                {'label': 'Employees', 'value': 'df_employees'},
                                {'label': 'Sales', 'value': 'df_sales'},
                                {'label': 'Timesheet', 'value': 'df_timesheet'},
                                {'label': 'Tasks', 'value': 'df_tasks'}
                            ],
                            value='df_timesheet',
                            placeholder="Select a dataframe"
                        ),
                        dcc.Dropdown(id='pivot-index-selector', multi=True, placeholder="Select index (rows)"),
                        dcc.Dropdown(id='pivot-columns-selector', multi=True, placeholder="Select columns"),
                        dcc.Dropdown(id='pivot-values-selector', multi=True, placeholder="Select values"),
                        dcc.Dropdown(
                            id='pivot-aggfunc-selector',
                            options=[
                                {'label': 'Sum', 'value': 'sum'},
                                {'label': 'Mean', 'value': 'mean'},
                                {'label': 'Count', 'value': 'count'},
                                {'label': 'Min', 'value': 'min'},
                                {'label': 'Max', 'value': 'max'}
                            ],
                            value='sum',
                            placeholder="Select aggregation function"
                        ),
                        dcc.Dropdown(
                            id='pivot-chart-type-selector',
                            options=[
                                {'label': 'Bar', 'value': 'bar'},
                                {'label': 'Line', 'value': 'line'},
                                {'label': 'Scatter', 'value': 'scatter'}
                            ],
                            value='bar',
                            placeholder="Select chart type"
                        ),
                    ], style={'width': '25%', 'display': 'inline-block', 'vertical-align': 'top'}),
                    html.Div([
                        dcc.Graph(id='pivot-chart'),
                        html.Div(id='pivot-table-container')
                    ], style={'width': '75%', 'display': 'inline-block'})
                ])
            ]),
        ], id='tabs'),

        # Store for holding the current data
        dcc.Store(id='data-store')
    ])

    # Register callbacks after all data is loaded
    register_callbacks(app, data_manager)
    logging.debug("Callbacks registered")

    return app

if __name__ == '__main__':
    app = create_app()
    if app:
        logging.info("Starting Dash server")
        app.run_server(debug=True)
    else:
        logging.error("Failed to create app")

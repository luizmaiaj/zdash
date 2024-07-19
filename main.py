import dash
from dash import dcc, html
from datetime import datetime, timedelta
import pandas as pd
from odoo import fetch_and_process_data
from callbacks import register_callbacks

# Fetch and process data
df_projects, df_employees, df_sales, df_financials, df_timesheet, df_tasks = fetch_and_process_data()

if df_projects is None:
    print("Error: Unable to fetch data from Odoo. Please check your connection and try again.")
    exit(1)

# Initialize Dash app
app = dash.Dash(__name__)

# Layout
app.layout = html.Div([
    html.H1("Odoo Interactive Dashboard"),
    
    # Date range selector
    dcc.DatePickerRange(
        id='date-range',
        start_date=datetime.now().date() - timedelta(days=30),
        end_date=datetime.now().date()
    ),
    
    # Project filter
    dcc.Dropdown(
        id='project-filter',
        options=[{'label': i, 'value': i} for i in df_projects['name'].unique() if pd.notna(i)],
        multi=True,
        placeholder="Select projects"
    ),
    
    # Employee filter
    dcc.Dropdown(
        id='employee-filter',
        options=[{'label': i, 'value': i} for i in df_employees['name'].unique() if pd.notna(i)],
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
                html.Div(id='data-quality-report')
            ])
        ]),
    ])
])

# Register callbacks
register_callbacks(app, df_projects, df_employees, df_sales, df_financials, df_timesheet, df_tasks)

if __name__ == '__main__':
    app.run_server(debug=True)

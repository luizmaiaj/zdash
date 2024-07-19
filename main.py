import os
import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
import plotly.express as px
import pandas as pd
import xmlrpc.client
from datetime import datetime, timedelta
import plotly.graph_objs as go

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(raise_error_if_not_found=True))

# Odoo API connection
url = os.getenv('ODOO_URL')
db = os.getenv('ODOO_DB')
username = os.getenv('ODOO_USERNAME')
api_key = os.getenv('ODOO_API_KEY')

common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
uid = common.authenticate(db, username, api_key, {})
models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

# Function to fetch data from Odoo
def fetch_odoo_data(model, fields, domain=[], limit=None):
    return models.execute_kw(db, uid, api_key, model, 'search_read', [domain, fields], {'limit': limit})

# Fetch necessary data
projects = fetch_odoo_data('project.project', ['name', 'partner_id', 'user_id', 'date_start', 'date'])
employees = fetch_odoo_data('hr.employee', ['name', 'department_id', 'job_id'])
sales = fetch_odoo_data('sale.order', ['name', 'partner_id', 'amount_total', 'date_order'])
financials = fetch_odoo_data('account.move', ['name', 'type', 'amount_total', 'date'])

# Convert to pandas DataFrames
df_projects = pd.DataFrame(projects)
df_employees = pd.DataFrame(employees)
df_sales = pd.DataFrame(sales)
df_financials = pd.DataFrame(financials)

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
        options=[{'label': i, 'value': i} for i in df_projects['name'].unique()],
        multi=True,
        placeholder="Select projects"
    ),
    
    # Employee filter
    dcc.Dropdown(
        id='employee-filter',
        options=[{'label': i, 'value': i} for i in df_employees['name'].unique()],
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
                dcc.Graph(id='projects-chart')
            ])
        ]),
        dcc.Tab(label='Sales', children=[
            html.Div([
                dcc.Graph(id='sales-chart')
            ])
        ]),
        # Add more tabs for other dashboards...
    ])
])

# Callback for Global KPI
@app.callback(
    [Output('global-map', 'figure'),
     Output('global-kpi-chart', 'figure')],
    [Input('date-range', 'start_date'),
     Input('date-range', 'end_date'),
     Input('project-filter', 'value'),
     Input('employee-filter', 'value')]
)
def update_global_kpi(start_date, end_date, selected_projects, selected_employees):
    # Filter data based on inputs
    filtered_projects = df_projects[
        (df_projects['date_start'] >= start_date) &
        (df_projects['date_start'] <= end_date)
    ]
    if selected_projects:
        filtered_projects = filtered_projects[filtered_projects['name'].isin(selected_projects)]
    
    # Create world map with project locations
    fig_map = px.scatter_geo(filtered_projects, 
                             locations='partner_id', 
                             color='name',
                             hover_name='name', 
                             projection='natural earth')
    
    # Create KPI chart (example: project count by month)
    project_counts = filtered_projects.groupby(pd.to_datetime(filtered_projects['date_start']).dt.to_period('M')).size().reset_index(name='count')
    fig_kpi = px.bar(project_counts, x='date_start', y='count', title='Projects by Month')
    
    return fig_map, fig_kpi

# Callback for Financials dashboard
@app.callback(
    Output('financials-chart', 'figure'),
    [Input('date-range', 'start_date'),
     Input('date-range', 'end_date')]
)
def update_financials(start_date, end_date):
    filtered_financials = df_financials[
        (df_financials['date'] >= start_date) &
        (df_financials['date'] <= end_date)
    ]
    
    fig = px.line(filtered_financials.groupby('date')['amount_total'].sum().reset_index(), 
                  x='date', y='amount_total', title='Daily Financial Summary')
    return fig

# Add more callbacks for other dashboards...

if __name__ == '__main__':
    app.run_server(debug=True)
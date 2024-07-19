import os
from dotenv import find_dotenv, load_dotenv
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.express as px
import plotly.graph_objs as go
import pandas as pd
import xmlrpc.client
from datetime import datetime, timedelta

# Load environment variables
load_dotenv(find_dotenv())

# Odoo API connection
url = os.getenv('ODOO_URL')
db = os.getenv('ODOO_DB')
username = os.getenv('ODOO_USERNAME')
api_key = os.getenv('ODOO_API_KEY')

# Create XML-RPC client with allow_none=True
common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common', allow_none=True)
uid = common.authenticate(db, username, api_key, {})
models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object', allow_none=True)

# Function to fetch data from Odoo
def fetch_odoo_data(model, fields, domain=[], limit=None):
    try:
        result = models.execute_kw(db, uid, api_key, model, 'search_read', [domain, fields], {'limit': limit})
        cleaned_result = [{k: v for k, v in record.items() if v is not None} for record in result]
        return cleaned_result
    except Exception as err:
        print(f"Error fetching data from Odoo: {err}")
        return []

# Fetch necessary data
projects = fetch_odoo_data('project.project', ['name', 'partner_id', 'user_id', 'date_start', 'date'])
employees = fetch_odoo_data('hr.employee', ['name', 'department_id', 'job_id'])
sales = fetch_odoo_data('sale.order', ['name', 'partner_id', 'amount_total', 'date_order'])
financials = fetch_odoo_data('account.move', ['name', 'move_type', 'amount_total', 'date'])
timesheet_entries = fetch_odoo_data('account.analytic.line', ['employee_id', 'project_id', 'unit_amount', 'date'])
tasks = fetch_odoo_data('project.task', ['project_id', 'stage_id', 'create_date', 'date_end'])

# Convert to pandas DataFrames with data validation
def validate_dataframe(df, required_columns):
    for col in required_columns:
        if col not in df.columns:
            df[col] = None
    return df

df_projects = validate_dataframe(pd.DataFrame(projects), ['name', 'partner_id', 'user_id', 'date_start', 'date'])
df_employees = validate_dataframe(pd.DataFrame(employees), ['name', 'department_id', 'job_id'])
df_sales = validate_dataframe(pd.DataFrame(sales), ['name', 'partner_id', 'amount_total', 'date_order'])
df_financials = validate_dataframe(pd.DataFrame(financials), ['name', 'move_type', 'amount_total', 'date'])
df_timesheet = validate_dataframe(pd.DataFrame(timesheet_entries), ['employee_id', 'project_id', 'unit_amount', 'date'])
df_tasks = validate_dataframe(pd.DataFrame(tasks), ['project_id', 'stage_id', 'create_date', 'date_end'])

# Convert date columns to datetime
date_columns = {
    'df_projects': ['date_start', 'date'],
    'df_sales': ['date_order'],
    'df_financials': ['date'],
    'df_timesheet': ['date'],
    'df_tasks': ['create_date', 'date_end']
}

for df_name, columns in date_columns.items():
    df = locals()[df_name]
    for col in columns:
        df[col] = pd.to_datetime(df[col], errors='coerce')

# Function to extract ID from list
def extract_id(x):
    if isinstance(x, list) and len(x) > 0:
        return x[0]
    return x

# Apply extract_id function to project_id columns
df_timesheet['project_id'] = df_timesheet['project_id'].apply(extract_id)
df_tasks['project_id'] = df_tasks['project_id'].apply(extract_id)

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
                dcc.Graph(id='projects-hours-chart'),
                dcc.Graph(id='projects-tasks-chart')
            ])
        ]),
        dcc.Tab(label='Employees', children=[
            html.Div([
                dcc.Graph(id='employee-hours-chart')
            ])
        ]),
        dcc.Tab(label='Sales', children=[
            html.Div([
                dcc.Graph(id='sales-chart')
            ])
        ]),
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
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)
    
    filtered_projects = df_projects[
        (df_projects['date_start'] >= start_date) &
        (df_projects['date_start'] <= end_date)
    ]
    if selected_projects:
        filtered_projects = filtered_projects[filtered_projects['name'].isin(selected_projects)]
    
    if filtered_projects.empty:
        return px.scatter_geo(), px.bar()
    
    fig_map = px.scatter_geo(filtered_projects, 
                             locations='partner_id', 
                             color='name',
                             hover_name='name', 
                             projection='natural earth')
    
    project_counts = filtered_projects.groupby(filtered_projects['date_start'].dt.to_period('M')).size().reset_index(name='count')
    project_counts['date_start'] = project_counts['date_start'].astype(str)
    
    fig_kpi = px.bar(project_counts, x='date_start', y='count', title='Projects by Month')
    
    return fig_map, fig_kpi

# Callback for Financials dashboard
@app.callback(
    Output('financials-chart', 'figure'),
    [Input('date-range', 'start_date'),
     Input('date-range', 'end_date')]
)
def update_financials(start_date, end_date):
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)
    
    filtered_financials = df_financials[
        (df_financials['date'] >= start_date) &
        (df_financials['date'] <= end_date)
    ]
    
    if filtered_financials.empty:
        return px.line()
    
    fig = px.line(filtered_financials.groupby('date')['amount_total'].sum().reset_index(), 
                  x='date', y='amount_total', title='Daily Financial Summary')
    return fig

# Callback for Projects dashboard
@app.callback(
    [Output('projects-hours-chart', 'figure'),
     Output('projects-tasks-chart', 'figure')],
    [Input('date-range', 'start_date'),
     Input('date-range', 'end_date'),
     Input('project-filter', 'value')]
)
def update_projects(start_date, end_date, selected_projects):
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)
    
    filtered_timesheet = df_timesheet[
        (df_timesheet['date'] >= start_date) &
        (df_timesheet['date'] <= end_date)
    ]
    
    filtered_tasks = df_tasks[
        (df_tasks['create_date'] >= start_date) &
        (df_tasks['create_date'] <= end_date)
    ]
    
    if selected_projects:
        filtered_timesheet = filtered_timesheet[filtered_timesheet['project_id'].isin(selected_projects)]
        filtered_tasks = filtered_tasks[filtered_tasks['project_id'].isin(selected_projects)]
    
    # Hours spent per project
    hours_per_project = filtered_timesheet.groupby('project_id')['unit_amount'].sum().reset_index()
    fig_hours = px.bar(hours_per_project, x='project_id', y='unit_amount', title='Hours Spent per Project')
    
    # Tasks opened and closed
    tasks_opened = filtered_tasks.groupby('project_id').size().reset_index(name='opened')
    tasks_closed = filtered_tasks[filtered_tasks['date_end'].notna()].groupby('project_id').size().reset_index(name='closed')
    tasks_stats = pd.merge(tasks_opened, tasks_closed, on='project_id', how='outer').fillna(0)
    
    fig_tasks = go.Figure()
    fig_tasks.add_trace(go.Bar(x=tasks_stats['project_id'], y=tasks_stats['opened'], name='Opened Tasks'))
    fig_tasks.add_trace(go.Bar(x=tasks_stats['project_id'], y=tasks_stats['closed'], name='Closed Tasks'))
    fig_tasks.update_layout(barmode='group', title='Tasks Opened and Closed per Project')
    
    return fig_hours, fig_tasks

# Callback for Employees dashboard
@app.callback(
    Output('employee-hours-chart', 'figure'),
    [Input('date-range', 'start_date'),
     Input('date-range', 'end_date'),
     Input('project-filter', 'value'),
     Input('employee-filter', 'value')]
)
def update_employee_hours(start_date, end_date, selected_projects, selected_employees):
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)
    
    filtered_timesheet = df_timesheet[
        (df_timesheet['date'] >= start_date) &
        (df_timesheet['date'] <= end_date)
    ]
    
    if selected_projects:
        filtered_timesheet = filtered_timesheet[filtered_timesheet['project_id'].isin(selected_projects)]
    
    if selected_employees:
        filtered_timesheet = filtered_timesheet[filtered_timesheet['employee_id'].isin(selected_employees)]
    
    employee_hours = filtered_timesheet.groupby(['employee_id', 'project_id'])['unit_amount'].sum().reset_index()
    
    fig = px.bar(employee_hours, x='employee_id', y='unit_amount', color='project_id', 
                 title='Employee Hours per Project', labels={'unit_amount': 'Hours'})
    fig.update_layout(barmode='stack')
    
    return fig

if __name__ == '__main__':
    app.run_server(debug=True)
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import pandas as pd
from datetime import datetime, timedelta
from odoo import fetch_and_process_data

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
                dcc.Graph(id='projects-hours-chart'),
                dcc.Graph(id='projects-tasks-chart')
            ])
        ]),
        dcc.Tab(label='Employees', children=[
            html.Div([
                html.H3(id='total-hours'),
                dcc.Graph(id='employee-hours-chart')
            ])
        ]),
        dcc.Tab(label='Sales', children=[
            html.Div([
                dcc.Graph(id='sales-chart')
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
        return go.Figure(), go.Figure()
    
    fig_map = go.Figure(go.Scattergeo(
        locations=filtered_projects['partner_id'],
        text=filtered_projects['name'],
        mode='markers',
        marker=dict(color=filtered_projects['name'], size=10)
    ))
    fig_map.update_layout(title='Project Locations')
    
    project_counts = filtered_projects.groupby(filtered_projects['date_start'].dt.to_period('M')).size().reset_index(name='count')
    project_counts['date_start'] = project_counts['date_start'].astype(str)
    
    fig_kpi = go.Figure(go.Bar(x=project_counts['date_start'], y=project_counts['count']))
    fig_kpi.update_layout(title='Projects by Month')
    
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
        return go.Figure()
    
    daily_financials = filtered_financials.groupby('date')['amount_total'].sum().reset_index()
    fig = go.Figure(go.Scatter(x=daily_financials['date'], y=daily_financials['amount_total'], mode='lines'))
    fig.update_layout(title='Daily Financial Summary')
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
        filtered_timesheet = filtered_timesheet[filtered_timesheet['project_name'].isin(selected_projects)]
        filtered_tasks = filtered_tasks[filtered_tasks['project_name'].isin(selected_projects)]
    
    # Hours spent per project
    hours_per_project = filtered_timesheet.groupby('project_name')['unit_amount'].sum().reset_index()
    hours_per_project = hours_per_project[hours_per_project['unit_amount'] > 0]  # Remove projects with no hours
    hours_per_project = hours_per_project.sort_values('unit_amount', ascending=False)
    hours_per_project['unit_amount'] = hours_per_project['unit_amount'].round().astype(int)  # Round to integers
    
    fig_hours = go.Figure(go.Bar(x=hours_per_project['project_name'], y=hours_per_project['unit_amount']))
    fig_hours.update_layout(title='Hours Spent per Project', xaxis_title='Project', yaxis_title='Hours')
    
    # Tasks opened and closed
    tasks_opened = filtered_tasks.groupby('project_name').size().reset_index(name='opened')
    tasks_closed = filtered_tasks[filtered_tasks['date_end'].notna()].groupby('project_name').size().reset_index(name='closed')
    tasks_stats = pd.merge(tasks_opened, tasks_closed, on='project_name', how='outer').fillna(0)
    
    fig_tasks = go.Figure()
    fig_tasks.add_trace(go.Bar(x=tasks_stats['project_name'], y=tasks_stats['opened'], name='Opened'))
    fig_tasks.add_trace(go.Bar(x=tasks_stats['project_name'], y=tasks_stats['closed'], name='Closed'))
    fig_tasks.update_layout(barmode='stack', title='Tasks Opened and Closed per Project', xaxis_title='Project', yaxis_title='Number of Tasks')
    
    return fig_hours, fig_tasks

# Callback for Employees dashboard
@app.callback(
    [Output('employee-hours-chart', 'figure'),
     Output('total-hours', 'children')],
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
        filtered_timesheet = filtered_timesheet[filtered_timesheet['project_name'].isin(selected_projects)]
    
    if selected_employees:
        filtered_timesheet = filtered_timesheet[filtered_timesheet['employee_name'].isin(selected_employees)]
    
    employee_hours = filtered_timesheet.groupby(['employee_name', 'project_name'])['unit_amount'].sum().reset_index()
    employee_hours['unit_amount'] = employee_hours['unit_amount'].round().astype(int)  # Round to integers
    
    total_hours = employee_hours['unit_amount'].sum()
    
    fig = go.Figure()
    for project in employee_hours['project_name'].unique():
        project_data = employee_hours[employee_hours['project_name'] == project]
        fig.add_trace(go.Bar(x=project_data['employee_name'], y=project_data['unit_amount'], name=project))
    
    fig.update_layout(barmode='stack', title='Employee Hours per Project', xaxis_title='Employee', yaxis_title='Hours')
    
    return fig, f"Total Hours Worked: {total_hours}"

# Callback for Sales dashboard
@app.callback(
    Output('sales-chart', 'figure'),
    [Input('date-range', 'start_date'),
     Input('date-range', 'end_date')]
)
def update_sales(start_date, end_date):
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)
    
    filtered_sales = df_sales[
        (df_sales['date_order'] >= start_date) &
        (df_sales['date_order'] <= end_date)
    ]
    
    if filtered_sales.empty:
        return go.Figure()
    
    daily_sales = filtered_sales.groupby('date_order')['amount_total'].sum().reset_index()
    fig = go.Figure(go.Scatter(x=daily_sales['date_order'], y=daily_sales['amount_total'], mode='lines'))
    fig.update_layout(title='Daily Sales')
    return fig

# Callback for Reporting dashboard
@app.callback(
    Output('data-quality-report', 'children'),
    [Input('date-range', 'start_date'),
     Input('date-range', 'end_date')]
)
def update_data_quality_report(start_date, end_date):
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)
    
    report = []
    
    # Check for projects with no hours logged
    projects_without_hours = set(df_projects['name']) - set(df_timesheet['project_name'])
    if projects_without_hours:
        report.append(html.P(f"Projects with no hours logged: {', '.join(projects_without_hours)}"))
    
    # Check for employees with no hours logged
    employees_without_hours = set(df_employees['name']) - set(df_timesheet['employee_name'])
    if employees_without_hours:
        report.append(html.P(f"Employees with no hours logged: {', '.join(employees_without_hours)}"))
    
    # Check for inconsistent project status (closed projects with open tasks)
    closed_projects = df_projects[df_projects['active'] == False]['name']
    open_tasks = df_tasks[df_tasks['date_end'].isna()]['project_name']
    inconsistent_projects = set(closed_projects) & set(open_tasks)
    if inconsistent_projects:
        report.append(html.P(f"Closed projects with open tasks: {', '.join(inconsistent_projects)}"))
    
    # Suggestions for improvement
    report.append(html.H4("Suggestions for improvement:"))
    report.append(html.Ul([
        html.Li("Add a burndown chart for each project to track progress"),
        html.Li("Include a resource allocation view to optimize employee workload"),
        html.Li("Implement a customer satisfaction metric for completed projects"),
        html.Li("Add a risk assessment indicator for ongoing projects"),
        html.Li("Include a profitability analysis comparing estimated vs. actual hours")
    ]))
    
    return report

if __name__ == '__main__':
    app.run_server(debug=True)

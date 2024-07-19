import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.express as px
import plotly.graph_objs as go
import pandas as pd
from datetime import datetime, timedelta
from odoo import fetch_and_process_data

# Fetch and process data
df_projects, df_employees, df_sales, df_financials, df_timesheet, df_tasks = fetch_and_process_data()

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
        filtered_timesheet = filtered_timesheet[filtered_timesheet['project_name'].isin(selected_projects)]
        filtered_tasks = filtered_tasks[filtered_tasks['project_name'].isin(selected_projects)]
    
    # Hours spent per project
    hours_per_project = filtered_timesheet.groupby('project_name')['unit_amount'].sum().reset_index()
    hours_per_project = hours_per_project[hours_per_project['unit_amount'] > 0]  # Remove projects with no hours
    hours_per_project = hours_per_project.sort_values('unit_amount', ascending=False)
    hours_per_project['unit_amount'] = hours_per_project['unit_amount'].round().astype(int)  # Round to integers
    
    fig_hours = px.bar(hours_per_project, x='project_name', y='unit_amount', 
                       title='Hours Spent per Project',
                       labels={'unit_amount': 'Hours', 'project_name': 'Project'})
    fig_hours.update_layout(xaxis={'categoryorder':'total descending'})
    
    # Tasks opened and closed
    tasks_opened = filtered_tasks.groupby('project_name').size().reset_index(name='opened')
    tasks_closed = filtered_tasks[filtered_tasks['date_end'].notna()].groupby('project_name').size().reset_index(name='closed')
    tasks_stats = pd.merge(tasks_opened, tasks_closed, on='project_name', how='outer').fillna(0)
    
    fig_tasks = px.bar(tasks_stats, x='project_name', y=['opened', 'closed'], 
                       title='Tasks Opened and Closed per Project',
                       labels={'value': 'Number of Tasks', 'project_name': 'Project'},
                       barmode='stack')
    fig_tasks.update_layout(xaxis={'categoryorder':'total descending'})
    
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
    
    fig = px.bar(employee_hours, x='employee_name', y='unit_amount', color='project_name', 
                 title='Employee Hours per Project', labels={'unit_amount': 'Hours', 'employee_name': 'Employee'})
    fig.update_layout(barmode='stack')
    
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
        return px.line()
    
    daily_sales = filtered_sales.groupby('date_order')['amount_total'].sum().reset_index()
    fig = px.line(daily_sales, x='date_order', y='amount_total', title='Daily Sales')
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
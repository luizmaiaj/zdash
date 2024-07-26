from dash.dependencies import Input, Output, State
from dash import html, dash_table
import dash
import pandas as pd
import ast

from data_management import DataManager

def register_reporting_calback(app, data_manager: DataManager):
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
        if 'name' in data_manager.df_portfolio.columns and 'project_name' in data_manager.df_timesheet.columns:
            projects_without_hours = set(data_manager.df_portfolio['name']) - set(data_manager.df_timesheet['project_name'])
        else:
            projects_without_hours = set()
        
        # Check for employees with no hours logged
        if 'name' in data_manager.df_employees.columns and 'employee_name' in data_manager.df_timesheet.columns:
            employees_without_hours = set(data_manager.df_employees['name']) - set(data_manager.df_timesheet['employee_name'])
        else:
            employees_without_hours = set()
        
        # Create side-by-side scrollable lists
        report.append(html.Div([
            html.Div([
                html.H4("Projects with no hours logged:"),
                html.Div([
                    html.Ul([html.Li(project) for project in projects_without_hours], style={'column-count': 2})
                ], style={'height': '400px', 'overflow': 'auto', 'border': '1px solid #ddd', 'padding': '10px'})
            ], style={'width': '48%', 'display': 'inline-block', 'vertical-align': 'top'}),
            
            html.Div([
                html.H4("Employees with no hours logged:"),
                html.Div([
                    html.Ul([html.Li(employee) for employee in employees_without_hours], style={'column-count': 2})
                ], style={'height': '400px', 'overflow': 'auto', 'border': '1px solid #ddd', 'padding': '10px'})
            ], style={'width': '48%', 'display': 'inline-block', 'vertical-align': 'top', 'margin-left': '4%'})
        ]))
        
        # Check for inconsistent project status (closed projects with open tasks)
        if 'active' in data_manager.df_portfolio.columns and 'name' in data_manager.df_portfolio.columns and 'date_end' in data_manager.df_tasks.columns and 'project_name' in data_manager.df_tasks.columns:
            closed_projects = data_manager.df_portfolio[data_manager.df_portfolio['active'] == False]['name']
            open_tasks = data_manager.df_tasks[data_manager.df_tasks['date_end'].isna()]['project_name']
            inconsistent_projects = set(closed_projects) & set(open_tasks)
            if inconsistent_projects:
                report.append(html.P(f"Closed projects with open tasks: {', '.join(inconsistent_projects)}"))
        
        return report
    
    @app.callback(
        Output('long-tasks-list', 'children'),
        [Input('date-range', 'start_date'),
        Input('date-range', 'end_date')]
    )
    def update_long_tasks_list(start_date, end_date):
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)

        # Filter timesheet data based on date range
        filtered_timesheet = data_manager.df_timesheet[
            (data_manager.df_timesheet['date'] >= start_date) &
            (data_manager.df_timesheet['date'] <= end_date)
        ].copy()

        # Filter timesheets longer than 8 hours
        long_timesheets = filtered_timesheet[filtered_timesheet['unit_amount'] > 8]

        # Sort by hours descending
        long_timesheets = long_timesheets.sort_values('unit_amount', ascending=False)

        # Merge with tasks to get task names
        long_timesheets['task_id'] = long_timesheets['task_id'].astype(str)
        data_manager.df_tasks['id'] = data_manager.df_tasks['id'].astype(str)
        merged_data = pd.merge(long_timesheets, data_manager.df_tasks[['id', 'name']], left_on='task_id', right_on='id', how='left')

        # Function to safely extract task name
        def extract_task_name(task_id):
            try:
                return ast.literal_eval(task_id)[1] if isinstance(task_id, str) and task_id.startswith('[') else task_id
            except:
                return task_id

        # Prepare the data for the table
        table_data = merged_data[['employee_name', 'project_name', 'task_id', 'name', 'date', 'unit_amount']].rename(columns={
            'name': 'task_name',
            'date': 'created_on',
            'unit_amount': 'duration'
        })

        # Extract task name from task_id if necessary
        table_data['task_name'] = table_data['task_name'].fillna(table_data['task_id'].apply(extract_task_name))
        table_data['task_id'] = table_data['task_id'].apply(lambda x: ast.literal_eval(x)[0] if isinstance(x, str) and x.startswith('[') else x)

        # Round duration to 2 decimal places
        table_data['duration'] = table_data['duration'].round(2)

        if table_data.empty:
            return html.Div("No timesheets longer than 8 hours found in the selected date range.")

        # Create the sortable table
        return html.Div([
            html.H4("Timesheets Longer Than 8 Hours:"),
            dash_table.DataTable(
                id='long-timesheets-table',
                columns=[
                    {"name": "Employee Name", "id": "employee_name"},
                    {"name": "Project Name", "id": "project_name"},
                    {"name": "Task Id", "id": "task_id"},
                    {"name": "Task Name", "id": "task_name"},
                    {"name": "Created On", "id": "created_on"},
                    {"name": "Duration (Hours)", "id": "duration"}
                ],
                data=table_data.to_dict('records'),
                sort_action='native',
                sort_mode='multi',
                style_table={'height': '400px', 'overflowY': 'auto'},
                style_cell={'textAlign': 'left', 'padding': '10px'},
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

    @app.callback(
        [Output('job-costs-table', 'data'),
         Output('employees-job-titles-table', 'data')],
        [Input('employee-filter', 'value'),
         Input('tabs', 'value')],
        [State('job-costs-table', 'data'),
         State('employees-job-titles-table', 'data')]
    )
    def update_settings_tables(selected_employees, current_tab, job_costs_data, employees_data):
        if current_tab != 'Settings':
            return dash.no_update, dash.no_update

        # Filter employees data
        filtered_employees = employees_data
        if selected_employees:
            filtered_employees = [emp for emp in employees_data if emp['name'] in selected_employees]

        # Get unique job titles from filtered employees
        unique_job_titles = set(emp['job_title'] for emp in filtered_employees if emp['job_title'])

        # Filter job costs data
        filtered_job_costs = [cost for cost in job_costs_data if cost['job_title'] in unique_job_titles]

        return filtered_job_costs, filtered_employees

import pandas as pd
from dash import html, dash_table
import ast
import logging

from data_management import DataManager

logger = logging.getLogger(__name__)

class DataQualityReporter:
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager

    def generate_data_quality_report(self, start_date, end_date):
        logger.info(f"Generating data quality report from {start_date} to {end_date}")
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        
        report = []
        
        # Check for projects with no hours logged
        projects_without_hours = self._get_projects_without_hours()
        
        # Check for employees with no hours logged
        employees_without_hours = self._get_employees_without_hours()
        
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
        inconsistent_projects = self._get_inconsistent_projects()
        if inconsistent_projects:
            report.append(html.P(f"Closed projects with open tasks: {', '.join(inconsistent_projects)}"))
        
        return report

    def generate_long_tasks_list(self, start_date, end_date):
        logger.info(f"Generating long tasks list from {start_date} to {end_date}")
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)

        # Filter timesheet data based on date range
        filtered_timesheet = self.data_manager.df_timesheet[
            (self.data_manager.df_timesheet['date'] >= start_date) &
            (self.data_manager.df_timesheet['date'] <= end_date)
        ].copy()

        # Filter timesheets longer than 8 hours
        long_timesheets = filtered_timesheet[filtered_timesheet['unit_amount'] > 8]

        # Sort by hours descending
        long_timesheets = long_timesheets.sort_values('unit_amount', ascending=False)

        # Merge with tasks to get task names
        long_timesheets['task_id'] = long_timesheets['task_id'].astype(str)
        self.data_manager.df_tasks['id'] = self.data_manager.df_tasks['id'].astype(str)
        merged_data = pd.merge(long_timesheets, self.data_manager.df_tasks[['id', 'name']], left_on='task_id', right_on='id', how='left')

        # Prepare the data for the table
        table_data = merged_data[['employee_name', 'project_name', 'task_id', 'name', 'date', 'unit_amount']].rename(columns={
            'name': 'task_name',
            'date': 'created_on',
            'unit_amount': 'duration'
        })

        # Extract task name from task_id if necessary
        table_data['task_name'] = table_data['task_name'].fillna(table_data['task_id'].apply(self._extract_task_name))
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

    def _get_projects_without_hours(self):
        if 'name' in self.data_manager.df_portfolio.columns and 'project_name' in self.data_manager.df_timesheet.columns:
            return set(self.data_manager.df_portfolio['name']) - set(self.data_manager.df_timesheet['project_name'])
        return set()

    def _get_employees_without_hours(self):
        if 'name' in self.data_manager.df_employees.columns and 'employee_name' in self.data_manager.df_timesheet.columns:
            return set(self.data_manager.df_employees['name']) - set(self.data_manager.df_timesheet['employee_name'])
        return set()

    def _get_inconsistent_projects(self):
        if all(col in self.data_manager.df_portfolio.columns for col in ['active', 'name']) and \
           all(col in self.data_manager.df_tasks.columns for col in ['date_end', 'project_name']):
            closed_projects = self.data_manager.df_portfolio[self.data_manager.df_portfolio['active'] == False]['name']
            open_tasks = self.data_manager.df_tasks[self.data_manager.df_tasks['date_end'].isna()]['project_name']
            return set(closed_projects) & set(open_tasks)
        return set()

    @staticmethod
    def _extract_task_name(task_id):
        try:
            return ast.literal_eval(task_id)[1] if isinstance(task_id, str) and task_id.startswith('[') else task_id
        except:
            return task_id

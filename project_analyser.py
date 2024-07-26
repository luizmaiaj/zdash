import pandas as pd
import plotly.graph_objs as go
import logging
import ast

from data_management import DataManager

logger = logging.getLogger(__name__)

class ProjectAnalyser:
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager

    def analyse_project(self, selected_project, start_date, end_date, selected_employees, use_man_hours):
        logger.info(f"Analyzing project: {selected_project}")
        if not selected_project:
            return go.Figure(), go.Figure(), go.Figure(), "", ""

        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)

        project_timesheet = self.data_manager.df_timesheet[self.data_manager.df_timesheet['project_name'] == selected_project].copy()

        if project_timesheet.empty:
            logger.warning(f"No timesheet data found for project: {selected_project}")
            return go.Figure(), go.Figure(), go.Figure(), "", ""

        total_project_revenue = self.calculate_project_revenue(project_timesheet)

        period_timesheet = project_timesheet[
            (project_timesheet['date'] >= start_date) &
            (project_timesheet['date'] <= end_date)
        ]

        if selected_employees:
            period_timesheet = period_timesheet[period_timesheet['employee_name'].isin(selected_employees)]

        period_revenue = self.calculate_project_revenue(period_timesheet)
        logger.info(f"Period revenue calculated: {period_revenue}")

        timeline_fig = self.create_timeline_chart(period_timesheet, self.data_manager.df_tasks, selected_project, use_man_hours)
        revenue_fig = self.create_revenue_chart(period_timesheet, self.data_manager.df_employees, self.data_manager.df_tasks, self.data_manager.job_costs, selected_project)
        tasks_employees_fig = self.create_tasks_employees_chart(period_timesheet, self.data_manager.df_tasks, selected_project)

        total_revenue_msg = f"Total Project Revenue: ${total_project_revenue:,.2f}"
        period_revenue_msg = f"Revenue for Selected Period"
        if selected_employees:
            period_revenue_msg += f" and Employees"
        period_revenue_msg += f": ${period_revenue:,.2f}"

        return timeline_fig, revenue_fig, tasks_employees_fig, total_revenue_msg, period_revenue_msg

    def calculate_project_revenue(self, timesheet_data):
        revenue = 0
        for _, row in timesheet_data.iterrows():
            employee_data = self.data_manager.df_employees[self.data_manager.df_employees['name'] == row['employee_name']]
            if employee_data.empty:
                logger.warning(f"Employee {row['employee_name']} not found in employees data")
                continue
            
            employee = employee_data.iloc[0]
            job_title = self.extract_job_title(employee)
            job_cost_data = self.data_manager.job_costs.get(job_title, {})
            
            try:
                daily_revenue = float(job_cost_data.get('revenue') or 0)
            except (ValueError, AttributeError):
                logger.warning(f"Invalid revenue data for job title: {job_title}")
                daily_revenue = 0
            
            entry_revenue = (row['unit_amount'] / 8) * daily_revenue  # Convert hours to days
            revenue += entry_revenue
        return revenue

    def create_timeline_chart(self, timesheet_data, tasks_data, project_name, use_man_hours):
        daily_effort = timesheet_data.copy()
        
        if not isinstance(tasks_data, pd.DataFrame):
            logger.warning("tasks_data is not a DataFrame. Skipping task name merge.")
            daily_effort['task_name'] = daily_effort['task_id']
        else:
            daily_effort['task_id_str'] = daily_effort['task_id'].apply(lambda x: str(x) if isinstance(x, list) else x)
            tasks_data['id_str'] = tasks_data['id'].astype(str)
            daily_effort = pd.merge(daily_effort, tasks_data[['id_str', 'name']], 
                                    left_on='task_id_str', right_on='id_str', 
                                    how='left', suffixes=('', '_task'))
            
            if 'name' in daily_effort.columns:
                daily_effort['task_name'] = daily_effort['name'].fillna(daily_effort['task_id_str'])
            else:
                logger.warning("'name' column not found after merge. Using 'task_id_str' as task name.")
                daily_effort['task_name'] = daily_effort['task_id_str']
        
        daily_effort = daily_effort.groupby(['date', 'employee_name', 'task_name'])['unit_amount'].sum().reset_index()
        daily_effort = daily_effort.sort_values(['date', 'employee_name'])
        
        fig = go.Figure()
        
        for employee in daily_effort['employee_name'].unique():
            employee_data = daily_effort[daily_effort['employee_name'] == employee]
            
            y_values = employee_data['unit_amount']
            if not use_man_hours:
                y_values = y_values / 8  # Convert to man days
            
            fig.add_trace(go.Bar(
                x=employee_data['date'],
                y=y_values,
                name=employee,
                hovertemplate='Date: %{x}<br>' +
                              'Employee: ' + employee + '<br>' +
                              'Task: %{customdata[0]}<br>' +
                              ('Hours: %{y:.2f}' if use_man_hours else 'Days: %{y:.2f}') +
                              '<extra></extra>',
                customdata=employee_data[['task_name']]
            ))
        
        title = f'Daily Effort for {project_name}'
        self.adjust_layout_for_legend(fig, title)
        
        fig.update_layout(
            barmode='stack',
            xaxis_title='Date',
            yaxis_title='Man Hours' if use_man_hours else 'Man Days'
        )
        
        return fig

    def create_revenue_chart(self, timesheet_data, employees_data, tasks_data, job_costs, project_name):
        daily_revenue = timesheet_data.copy()
        daily_revenue['revenue'] = daily_revenue.apply(
            lambda row: self.calculate_entry_revenue(row, employees_data, job_costs), axis=1
        )

        daily_revenue['task_id_str'] = daily_revenue['task_id'].apply(lambda x: str(x) if isinstance(x, list) else x)

        if not isinstance(tasks_data, pd.DataFrame):
            logger.warning("tasks_data is not a DataFrame. Skipping task name merge.")
            daily_revenue['task_name'] = daily_revenue['task_id_str']
        else:
            tasks_data['id_str'] = tasks_data['id'].astype(str)
            daily_revenue = pd.merge(daily_revenue, tasks_data[['id_str', 'name']], 
                                     left_on='task_id_str', right_on='id_str', 
                                     how='left', suffixes=('', '_task'))
            
            if 'name' in daily_revenue.columns:
                daily_revenue['task_name'] = daily_revenue['name'].fillna(daily_revenue['task_id_str'])
            else:
                logger.warning("'name' column not found after merge. Using 'task_id_str' as task name.")
                daily_revenue['task_name'] = daily_revenue['task_id_str']
        
        daily_revenue = daily_revenue.groupby(['date', 'employee_name', 'task_name'])[['revenue', 'unit_amount']].sum().reset_index()
        daily_revenue = daily_revenue.sort_values(['date', 'employee_name'])
        
        fig = go.Figure()
        
        for employee in daily_revenue['employee_name'].unique():
            employee_data = daily_revenue[daily_revenue['employee_name'] == employee]
            
            fig.add_trace(go.Bar(
                x=employee_data['date'],
                y=employee_data['revenue'],
                name=employee,
                hovertemplate='Date: %{x}<br>' +
                              'Employee: ' + employee + '<br>' +
                              'Task: %{customdata[0]}<br>' +
                              'Revenue: $%{y:.2f}<br>' +
                              'Hours: %{customdata[1]:.2f}' +
                              '<extra></extra>',
                customdata=employee_data[['task_name', 'unit_amount']]
            ))
        
        title = f'Daily Acquired Revenue for {project_name}'
        self.adjust_layout_for_legend(fig, title)
        
        fig.update_layout(
            barmode='stack',
            xaxis_title='Date',
            yaxis_title='Revenue (USD)'
        )
        
        return fig

    def create_tasks_employees_chart(self, timesheet_data, tasks_data, project_name):
        timesheet_copy = timesheet_data.copy()
        timesheet_copy['task_id_str'] = timesheet_copy['task_id'].apply(lambda x: str(x) if isinstance(x, list) else x)

        if not isinstance(tasks_data, pd.DataFrame):
            logger.warning("tasks_data is not a DataFrame. Using task_id as task name.")
            timesheet_copy['task_name'] = timesheet_copy['task_id_str']
        else:
            tasks_data['id_str'] = tasks_data['id'].astype(str)
            merged_data = pd.merge(timesheet_copy, tasks_data[['id_str', 'name']], 
                                   left_on='task_id_str', right_on='id_str', 
                                   how='left', suffixes=('', '_task'))
            
            merged_data['task_name'] = merged_data['name'].fillna(merged_data['task_id_str'])

        task_employee_hours = merged_data.groupby(['task_name', 'employee_name'])['unit_amount'].sum().unstack(fill_value=0)

        task_employee_hours['total'] = task_employee_hours.sum(axis=1)
        task_employee_hours = task_employee_hours.sort_values('total', ascending=False).drop('total', axis=1)

        fig = go.Figure()

        for employee in task_employee_hours.columns:
            fig.add_trace(go.Bar(
                name=employee,
                x=task_employee_hours.index,
                y=task_employee_hours[employee],
                text=task_employee_hours[employee].round().astype(int),
                textposition='auto',
                hovertemplate='<b>%{x}</b><br>' +
                              f'<b>{employee}</b>: ' +
                              '%{text} hours<extra></extra>'
            ))

        title = f'Tasks and Employee Hours for {project_name}'
        self.adjust_layout_for_legend(fig, title)
        
        fig.update_layout(
            barmode='stack',
            xaxis_title='Tasks',
            yaxis_title='Hours',
            xaxis=dict(
                tickangle=45,
                tickmode='array',
                tickvals=list(range(len(task_employee_hours.index))),
                ticktext=task_employee_hours.index,
                range=[-0.5, 24.5]  # Show only 25 tasks initially
            ),
            yaxis=dict(
                fixedrange=True  # Prevent y-axis zooming
            )
        )

        return fig

    def calculate_entry_revenue(self, row, employees_data, job_costs):
        employee_data = employees_data[employees_data['name'] == row['employee_name']]
        if employee_data.empty:
            logger.warning(f"Employee {row['employee_name']} not found in employees data")
            return 0
        
        employee = employee_data.iloc[0]
        job_title = self.extract_job_title(employee)
        daily_revenue = float(job_costs.get(job_title, {}).get('revenue') or 0)
        return (row['unit_amount'] / 8) * daily_revenue  # Convert hours to days

    @staticmethod
    def extract_job_title(employee):
        if 'job_id' in employee and isinstance(employee['job_id'], str):
            try:
                job_id_list = ast.literal_eval(employee['job_id'])
                return job_id_list[1] if len(job_id_list) > 1 else 'Unknown'
            except (ValueError, SyntaxError, IndexError) as e:
                logger.error(f"Job title not found: {e}")
                return 'Unknown'
        elif 'job_title' in employee:
            return employee['job_title']
        else:
            logger.warning(f"Job title not found: {employee}")
            return 'Unknown'

    @staticmethod
    def calculate_legend_height(fig):
        """Calculate the approximate height of the legend."""
        num_items = len(fig.data)
        item_height = 20 / 4  # Estimated height of each legend item in pixels
        padding = 20  # Extra padding
        return num_items * item_height + padding

    def adjust_layout_for_legend(self, fig, title):
        """Adjust the layout to accommodate the legend and ensure the title is visible."""
        legend_height = self.calculate_legend_height(fig)
        
        fig.update_layout(
            title={
                'text': title,
                'y': 0.95,  # Place the title closer to the top
                'x': 0.5,
                'xanchor': 'center',
                'yanchor': 'top'
            },
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1,
                xanchor="left",
                x=0
            ),
            margin=dict(t=legend_height + 40),  # Reduced top margin
            height=500 + legend_height  # Adjusted overall height
        )

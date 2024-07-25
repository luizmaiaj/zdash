from dash.dependencies import Input, Output
import plotly.graph_objs as go
import pandas as pd

def register_project_callback(app, df_timesheet, df_tasks):
    @app.callback(
        Output('project-tasks-employees-chart', 'figure'),
        [Input('project-selector', 'value'),
        Input('date-range', 'start_date'),
        Input('date-range', 'end_date'),
        Input('employee-filter', 'value')]
    )
    def update_project_tasks_employees_chart(selected_project, start_date, end_date, selected_employees):
        if not selected_project:
            return go.Figure()

        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)

        # Filter data based on date range
        project_timesheet = df_timesheet[
            (df_timesheet['project_name'] == selected_project) &
            (df_timesheet['date'] >= start_date) &
            (df_timesheet['date'] <= end_date)
        ].copy()

        if project_timesheet.empty:
            return go.Figure()

        # Filter by selected employees if any
        if selected_employees:
            project_timesheet = project_timesheet[project_timesheet['employee_name'].isin(selected_employees)]

        # Convert 'task_id' to string
        project_timesheet['task_id_str'] = project_timesheet['task_id'].astype(str)
        df_tasks['id_str'] = df_tasks['id'].astype(str)

        # Merge timesheet data with tasks to get task names
        merged_data = pd.merge(project_timesheet, df_tasks[['id_str', 'name']], 
                            left_on='task_id_str', right_on='id_str', how='left')

        merged_data['task_name'] = merged_data['name'].fillna(merged_data['task_id_str']).fillna('Unknown Task')

        # Group by task and employee, summing the hours
        task_employee_hours = merged_data.groupby(['task_name', 'employee_name'])['unit_amount'].sum().unstack(fill_value=0)

        # Sort tasks by total hours in descending order
        task_employee_hours['total'] = task_employee_hours.sum(axis=1)
        task_employee_hours = task_employee_hours.sort_values('total', ascending=False).drop('total', axis=1)

        # Create the stacked bar chart
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

        fig.update_layout(
            barmode='stack',
            title=f'Tasks and Employee Hours for {selected_project}',
            xaxis_title='Tasks',
            yaxis_title='Hours',
            legend_title='Employees',
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02
            ),
            height=600,
            margin=dict(r=200, b=100, t=50),
            xaxis=dict(
                tickangle=45,
                tickmode='array',
                tickvals=list(range(len(task_employee_hours.index))),
                ticktext=task_employee_hours.index
            )
        )

        return fig

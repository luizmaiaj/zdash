from dash.dependencies import Input, Output
import plotly.graph_objs as go
import pandas as pd

def register_project_callback(app, df_timesheet, df_tasks):
    @app.callback(
        [Output('project-timeline-chart', 'figure'),
         Output('project-tasks-employees-chart', 'figure')],
        [Input('project-selector', 'value'),
         Input('date-range', 'start_date'),
         Input('date-range', 'end_date'),
         Input('employee-filter', 'value'),
         Input('man-hours-toggle', 'value')]
    )
    def update_project_charts(selected_project, start_date, end_date, selected_employees, use_man_hours):
        if not selected_project:
            return go.Figure(), go.Figure()

        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)

        # Filter data based on date range and project
        project_timesheet = df_timesheet[
            (df_timesheet['project_name'] == selected_project) &
            (df_timesheet['date'] >= start_date) &
            (df_timesheet['date'] <= end_date)
        ].copy()

        if project_timesheet.empty:
            return go.Figure(), go.Figure()

        # Filter by selected employees if any
        if selected_employees:
            project_timesheet = project_timesheet[project_timesheet['employee_name'].isin(selected_employees)]

        # Timeline Chart
        daily_hours = project_timesheet.groupby('date')['unit_amount'].sum().reset_index()
        
        if use_man_hours:
            y_values = daily_hours['unit_amount']
            y_title = 'Man Hours'
        else:
            y_values = daily_hours['unit_amount'] / 8  # Convert to man days
            y_title = 'Man Days'

        timeline_fig = go.Figure(go.Bar(
            x=daily_hours['date'],
            y=y_values,
            name='Daily Effort',
            hovertemplate='Date: %{x}<br>' + y_title + ': %{y:.2f}<extra></extra>'
        ))

        timeline_fig.update_layout(
            title=f'Daily Effort for {selected_project}',
            xaxis_title='Date',
            yaxis_title=y_title,
            height=400
        )

        # Existing Tasks and Employees Chart
        merged_data = pd.merge(project_timesheet, df_tasks[['id', 'name']], 
                               left_on='task_id', right_on='id', how='left')

        merged_data['task_name'] = merged_data['name'].fillna(merged_data['task_id']).fillna('Unknown Task')

        task_employee_hours = merged_data.groupby(['task_name', 'employee_name'])['unit_amount'].sum().unstack(fill_value=0)

        task_employee_hours['total'] = task_employee_hours.sum(axis=1)
        task_employee_hours = task_employee_hours.sort_values('total', ascending=False).drop('total', axis=1)

        tasks_employees_fig = go.Figure()

        for employee in task_employee_hours.columns:
            tasks_employees_fig.add_trace(go.Bar(
                name=employee,
                x=task_employee_hours.index,
                y=task_employee_hours[employee],
                text=task_employee_hours[employee].round().astype(int),
                textposition='auto',
                hovertemplate='<b>%{x}</b><br>' +
                              f'<b>{employee}</b>: ' +
                              '%{text} hours<extra></extra>'
            ))

        tasks_employees_fig.update_layout(
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

        return timeline_fig, tasks_employees_fig
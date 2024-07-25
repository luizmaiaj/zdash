import ast
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import pandas as pd

def register_project_callback(app, df_timesheet, df_tasks, df_employees, job_costs):
    @app.callback(
        [Output('project-timeline-chart', 'figure'),
         Output('project-revenue-chart', 'figure'),
         Output('project-tasks-employees-chart', 'figure'),
         Output('project-total-revenue', 'children'),
         Output('project-period-revenue', 'children')],
        [Input('project-selector', 'value'),
         Input('date-range', 'start_date'),
         Input('date-range', 'end_date'),
         Input('employee-filter', 'value'),
         Input('man-hours-toggle', 'value')]
    )
    def update_project_charts(selected_project, start_date, end_date, selected_employees, use_man_hours):
        if not selected_project:
            return go.Figure(), go.Figure(), go.Figure(), "", ""

        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)

        # Filter data based on project
        project_timesheet = df_timesheet[df_timesheet['project_name'] == selected_project].copy()

        if project_timesheet.empty:
            return go.Figure(), go.Figure(), go.Figure(), "", ""

        # Calculate total project revenue (not considering date range)
        total_project_revenue = calculate_project_revenue(project_timesheet, df_employees, job_costs)

        # Filter data based on date range
        period_timesheet = project_timesheet[
            (project_timesheet['date'] >= start_date) &
            (project_timesheet['date'] <= end_date)
        ]

        # Filter by selected employees if any
        if selected_employees:
            period_timesheet = period_timesheet[period_timesheet['employee_name'].isin(selected_employees)]

        # Calculate revenue for the selected period (and selected employees if any)
        period_revenue = calculate_project_revenue(period_timesheet, df_employees, job_costs)

        # Timeline Chart (Man Hours/Days)
        timeline_fig = create_timeline_chart(period_timesheet, selected_project, use_man_hours)

        # Revenue Chart
        revenue_fig = create_revenue_chart(period_timesheet, df_employees, job_costs, selected_project)

        # Tasks and Employees Chart
        tasks_employees_fig = create_tasks_employees_chart(period_timesheet, df_tasks, selected_project)

        # Prepare revenue messages
        total_revenue_msg = f"Total Project Revenue: ${total_project_revenue:,.2f}"
        period_revenue_msg = f"Revenue for Selected Period"
        if selected_employees:
            period_revenue_msg += f" and Employees"
        period_revenue_msg += f": ${period_revenue:,.2f}"

        return (
            timeline_fig, 
            revenue_fig, 
            tasks_employees_fig, 
            total_revenue_msg,
            period_revenue_msg
        )

def calculate_project_revenue(timesheet_data, employees_data, job_costs):
    revenue = 0
    for _, row in timesheet_data.iterrows():
        employee = employees_data[employees_data['name'] == row['employee_name']].iloc[0]
        
        # Extract job title from job_id string
        if 'job_id' in employee and isinstance(employee['job_id'], str):
            try:
                job_id_list = ast.literal_eval(employee['job_id'])
                job_title = job_id_list[1] if len(job_id_list) > 1 else 'Unknown'
            except (ValueError, SyntaxError, IndexError):
                job_title = 'Unknown'
        elif 'job_title' in employee:
            job_title = employee['job_title']
        else:
            print(f"no job title found: {employee}")
            continue
        
        # Safely convert revenue to float, defaulting to 0 if empty or invalid
        try:
            daily_revenue = float(job_costs.get(job_title, {}).get('revenue') or 0)
        except ValueError:
            daily_revenue = 0
        
        revenue += (row['unit_amount'] / 8) * daily_revenue  # Convert hours to days
    return revenue

def create_timeline_chart(timesheet_data, project_name, use_man_hours):
    daily_hours = timesheet_data.groupby('date')['unit_amount'].sum().reset_index()
    
    if use_man_hours:
        y_values = daily_hours['unit_amount']
        y_title = 'Man Hours'
    else:
        y_values = daily_hours['unit_amount'] / 8  # Convert to man days
        y_title = 'Man Days'

    fig = go.Figure(go.Bar(
        x=daily_hours['date'],
        y=y_values,
        name='Daily Effort',
        hovertemplate='Date: %{x}<br>' + y_title + ': %{y:.2f}<extra></extra>'
    ))

    fig.update_layout(
        title=f'Daily Effort for {project_name}',
        xaxis_title='Date',
        yaxis_title=y_title,
        height=400
    )

    return fig

def create_revenue_chart(timesheet_data, employees_data, job_costs, project_name):
    daily_revenue = timesheet_data.groupby('date').apply(
        lambda x: calculate_project_revenue(x, employees_data, job_costs)
    ).reset_index(name='revenue')

    fig = go.Figure(go.Bar(
        x=daily_revenue['date'],
        y=daily_revenue['revenue'],
        name='Daily Revenue',
        hovertemplate='Date: %{x}<br>Revenue: $%{y:,.2f}<extra></extra>'
    ))

    fig.update_layout(
        title=f'Daily Acquired Revenue for {project_name}',
        xaxis_title='Date',
        yaxis_title='Revenue (USD)',
        height=400
    )

    return fig

def create_tasks_employees_chart(timesheet_data, tasks_data, project_name):
    merged_data = pd.merge(timesheet_data, tasks_data[['id', 'name']], 
                           left_on='task_id', right_on='id', how='left')

    merged_data['task_name'] = merged_data['name'].fillna(merged_data['task_id']).fillna('Unknown Task')

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

    # Calculate the height required for 25 tasks (assuming 30px per task)
    chart_height = min(25 * 30 + 200, 1000)  # 200px for margins and legend, max height of 1000px

    fig.update_layout(
        barmode='stack',
        title=f'Tasks and Employee Hours for {project_name}',
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
        height=chart_height,
        margin=dict(r=200, b=100, t=50, l=100),
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

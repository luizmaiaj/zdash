from dash.dependencies import Input, Output, State
import dash
from dash import html, dcc
import plotly.graph_objs as go
import pandas as pd

from data_management import deserialize_dataframes
from callbacks.project import calculate_project_revenue

def register_financials_callbacks(app, df_projects, df_employees, df_financials, df_timesheet, df_tasks, job_costs):
    @app.callback(
        [Output('financials-chart', 'figure'),
         Output('total-revenue-display', 'children'),
         Output('all-projects-hours-chart', 'figure'),
         Output('all-projects-revenue-chart', 'figure'),
         Output('calculation-progress', 'children'),
         Output('calculate-button', 'disabled')],
        [Input('date-range', 'start_date'),
         Input('date-range', 'end_date'),
         Input('calculate-button', 'n_clicks')],
        [State('data-store', 'data')]
    )
    def update_financials(start_date, end_date, n_clicks, serialized_data):
        ctx = dash.callback_context
        if not ctx.triggered:
            return [go.Figure()] * 3 + ["", False]

        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)

        if 'date' not in df_financials.columns:
            date_columns = [col for col in df_financials.columns if 'date' in col.lower()]
            if date_columns:
                date_column = date_columns[0]
            else:
                return [go.Figure()] * 3 + ["No date column found in financial data", False]
        else:
            date_column = 'date'

        filtered_financials = df_financials[
            (df_financials[date_column] >= start_date) &
            (df_financials[date_column] <= end_date)
        ]

        if filtered_financials.empty:
            return [go.Figure()] * 3 + ["No data available for the selected date range", False]

        daily_financials = filtered_financials.groupby(date_column)['amount_total'].sum().reset_index()
        fig_financials = go.Figure(go.Scatter(x=daily_financials[date_column], y=daily_financials['amount_total'], mode='lines'))
        fig_financials.update_layout(title='Daily Financial Summary', xaxis_title='Date', yaxis_title='Amount')

        if ctx.triggered_id == 'calculate-button':
            total_revenue, fig_hours, fig_revenue = calculate_all_projects_financials(df_projects, df_employees, df_timesheet, df_tasks, start_date, end_date, job_costs)
            return (
                fig_financials,
                f"Total Acquired Revenue: ${total_revenue:,.2f}",
                fig_hours,
                fig_revenue,
                "",
                False
            )
        else:
            return (
                fig_financials,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                "",
                False
            )

    @app.callback(
        [Output('calculation-progress', 'children'),
         Output('calculate-button', 'disabled', allow_duplicate=True)],
        [Input('calculate-button', 'n_clicks')],
        [State('data-store', 'data')],
        prevent_initial_call=True
    )
    def start_calculation(n_clicks, serialized_data):
        if n_clicks is None or n_clicks == 0:
            return "", False

        data = deserialize_dataframes(serialized_data)
        df_projects = data[0]
        total_projects = len(df_projects)

        return f"Calculation in progress: 0/{total_projects} projects", True

def calculate_all_projects_financials(df_projects, df_employees, df_timesheet, df_tasks, start_date, end_date, job_costs):
    total_revenue = 0
    all_hours = []
    all_revenue = []
    total_projects = len(df_projects)

    for idx, project in df_projects.iterrows():
        project_timesheet = df_timesheet[
            (df_timesheet['project_name'] == project['name']) &
            (df_timesheet['date'] >= start_date) &
            (df_timesheet['date'] <= end_date)
        ]

        project_revenue = calculate_project_revenue(project_timesheet, df_employees, job_costs)
        total_revenue += project_revenue

        daily_hours = project_timesheet.groupby('date')['unit_amount'].sum().reset_index()
        all_hours.append(daily_hours)

        daily_revenue = project_timesheet.groupby('date').apply(
            lambda x: calculate_project_revenue(x, df_employees, job_costs)
        ).reset_index(name='revenue')
        all_revenue.append(daily_revenue)

        # Update progress
        progress = (idx + 1) / total_projects * 100
        dash.callback_context.response.set_header('X-Progress', f"{progress:.0f}")

    # Combine all project data
    combined_hours = pd.concat(all_hours).groupby('date')['unit_amount'].sum().reset_index()
    combined_revenue = pd.concat(all_revenue).groupby('date')['revenue'].sum().reset_index()

    # Create hours chart
    fig_hours = go.Figure(go.Bar(x=combined_hours['date'], y=combined_hours['unit_amount']))
    fig_hours.update_layout(title='Total Hours for All Projects', xaxis_title='Date', yaxis_title='Hours')

    # Create revenue chart
    fig_revenue = go.Figure(go.Bar(x=combined_revenue['date'], y=combined_revenue['revenue']))
    fig_revenue.update_layout(title='Total Acquired Revenue for All Projects', xaxis_title='Date', yaxis_title='Revenue')

    return total_revenue, fig_hours, fig_revenue

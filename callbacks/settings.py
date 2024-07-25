from dash.dependencies import Input, Output, State
from dash import html
import dash
from data_management import save_job_costs

import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def register_settings_callbacks(app, df_employees):
    @app.callback(
        Output('job-costs-save-status', 'children'),
        Input('save-cost-revenue', 'n_clicks'),
        State('job-costs-table', 'data')
    )
    def save_job_costs_callback(n_clicks, table_data):
        if n_clicks is None or n_clicks == 0:
            return ""

        try:
            job_costs = {item['job_title']: {'cost': item['cost'], 'revenue': item['revenue']} for item in table_data if item['job_title']}
            save_job_costs(job_costs)
            return html.Div("Job costs saved successfully", style={'color': 'green'})
        except Exception as e:
            return html.Div(f"Error saving job costs: {str(e)}", style={'color': 'red'})

    @app.callback(
        Output('job-costs-table', 'data', allow_duplicate=True),
        Input('add-job-title', 'n_clicks'),
        State('job-costs-table', 'data'),
        prevent_initial_call=True
    )
    def add_job_title(n_clicks, current_data):
        if n_clicks is None or n_clicks == 0:
            return dash.no_update
        
        new_row = {'job_title': '', 'cost': '', 'revenue': ''}
        return current_data + [new_row]

    @app.callback(
        Output('job-costs-table', 'data', allow_duplicate=True),
        [Input('date-range', 'start_date'),
        Input('date-range', 'end_date'),
        Input('project-filter', 'value'),
        Input('employee-filter', 'value'),
        Input('tabs', 'value')],
        [State('job-costs-table', 'data')],
        prevent_initial_call=True
    )
    def update_job_costs_table(start_date, end_date, selected_projects, selected_employees, current_tab, current_data):
        if current_tab != 'Settings':
            return dash.no_update

        # Get all job titles from current data
        all_job_titles = set(item['job_title'] for item in current_data if item['job_title'])

        # Get job titles from employees
        employee_job_titles = set()
        if 'job_title' in df_employees.columns:
            employee_job_titles = set(df_employees['job_title'].dropna().unique())
        elif 'job_id' in df_employees.columns:
            employee_job_titles = set(df_employees['job_id'].dropna().apply(lambda x: x[1] if isinstance(x, (list, tuple)) and len(x) > 1 else x).unique())

        # Combine all job titles
        unique_job_titles = all_job_titles.union(employee_job_titles)
        logger.debug(f"Combined unique job titles: {unique_job_titles}")

        # If there are no job titles, return the current data
        if not unique_job_titles:
            logger.warning("No job titles found. Returning current data.")
            return current_data

        # Filter job costs data, but keep all entries if no matching job titles
        filtered_job_costs = [cost for cost in current_data if cost['job_title'] in unique_job_titles] or current_data

        logger.debug(f"Filtered job costs: {filtered_job_costs}")

        return filtered_job_costs

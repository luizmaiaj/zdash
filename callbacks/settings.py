import logging
from dash.dependencies import Input, Output, State
from dash import html
import dash
from data_management import DataManager

def register_settings_callbacks(app, data_manager: DataManager):
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
            data_manager.save_job_costs(job_costs)
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
        [Input('tabs', 'value')],
        [State('job-costs-table', 'data')],
        prevent_initial_call=True
    )
    def update_job_costs_table(current_tab, current_data):
        if current_tab != 'Settings':
            return dash.no_update

        # Get all job titles from current data
        all_job_titles = set(item['job_title'] for item in current_data if item['job_title'])

        # Get job titles from employees
        employee_job_titles = set()
        if 'job_title' in data_manager.df_employees.columns:
            employee_job_titles = set(data_manager.df_employees['job_title'].dropna().unique())
        elif 'job_id' in data_manager.df_employees.columns:
            employee_job_titles = set(data_manager.df_employees['job_id'].dropna().apply(lambda x: x[1] if isinstance(x, (list, tuple)) and len(x) > 1 else x).unique())

        # Combine all job titles
        unique_job_titles = all_job_titles.union(employee_job_titles)
        logging.debug(f"Combined unique job titles: {unique_job_titles}")

        # If there are no job titles, return the current data
        if not unique_job_titles:
            logging.warning("No job titles found. Returning current data.")
            return current_data

        # Filter job costs data, but keep all entries if no matching job titles
        filtered_job_costs = [cost for cost in current_data if cost['job_title'] in unique_job_titles] or current_data

        logging.debug(f"Filtered job costs: {filtered_job_costs}")

        return filtered_job_costs

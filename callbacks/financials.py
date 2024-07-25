from dash.dependencies import Input, Output
import logging
from dash import dcc
import plotly.graph_objs as go
import pandas as pd
import dash
from datetime import datetime
import json
import os

from data_management import get_last_update_time

logger = logging.getLogger(__name__)

FINANCIALS_FILE = 'financials_data.json'
LAST_CALCULATION_FILE = 'last_financials_calculation.json'

def load_financials_data():
    if os.path.exists(FINANCIALS_FILE):
        with open(FINANCIALS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_financials_data(data):
    with open(FINANCIALS_FILE, 'w') as f:
        json.dump(data, f)

def get_last_calculation_time():
    if os.path.exists(LAST_CALCULATION_FILE):
        with open(LAST_CALCULATION_FILE, 'r') as f:
            return datetime.fromisoformat(json.load(f)['time'])
    return None

def set_last_calculation_time(time):
    with open(LAST_CALCULATION_FILE, 'w') as f:
        json.dump({'time': time.isoformat()}, f)

def register_financials_callbacks(app, df_portfolio, df_employees, df_financials, df_timesheet, df_tasks, job_costs):
    @app.callback(
        [Output('financials-chart', 'figure'),
         Output('total-revenue-display', 'children'),
         Output('all-projects-hours-chart', 'figure'),
         Output('all-projects-revenue-chart', 'figure'),
         Output('calculation-progress', 'children'),
         Output('calculate-button', 'disabled')],
        [Input('date-range', 'start_date'),
         Input('date-range', 'end_date'),
         Input('calculate-button', 'n_clicks')]
    )
    def update_financials(start_date, end_date, n_clicks):
        logger.debug("Entering update_financials callback")
        ctx = dash.callback_context
        if not ctx.triggered:
            empty_fig = go.Figure()
            return [
                empty_fig,
                "No data calculated yet",
                empty_fig,
                empty_fig,
                "No data calculated yet",
                False
            ]

        try:
            financials_data = load_financials_data()
            last_calculation = get_last_calculation_time()
            last_update = get_last_update_time()

            if ctx.triggered[0]['prop_id'] == 'calculate-button.n_clicks':
                if last_calculation is None or last_update > last_calculation:
                    financials_data = calculate_all_financials(df_portfolio, df_employees, df_timesheet, df_tasks, job_costs)
                    save_financials_data(financials_data)
                    set_last_calculation_time(datetime.now())
                else:
                    new_data = calculate_incremental_financials(df_portfolio, df_employees, df_timesheet, df_tasks, job_costs, last_calculation)
                    financials_data.update(new_data)
                    save_financials_data(financials_data)
                    set_last_calculation_time(datetime.now())

            if not financials_data:
                empty_fig = go.Figure()
                return [
                    empty_fig,
                    "No data available. Please calculate.",
                    empty_fig,
                    empty_fig,
                    "No data available. Please calculate.",
                    False
                ]

            start_date = pd.to_datetime(start_date)
            end_date = pd.to_datetime(end_date)

            filtered_data = {k: v for k, v in financials_data.items() if start_date <= pd.to_datetime(k) <= end_date}

            fig_financials = create_financials_chart(filtered_data)
            fig_hours = create_hours_chart(filtered_data)
            fig_revenue = create_revenue_chart(filtered_data)

            total_revenue = sum(day_data['revenue'] for day_data in filtered_data.values())

            return [
                fig_financials,
                f"Total Revenue: ${total_revenue:,.2f}",
                fig_hours,
                fig_revenue,
                "Calculation complete",
                False
            ]
        except Exception as e:
            logger.error(f"Error in update_financials: {str(e)}")
            empty_fig = go.Figure()
            return [
                empty_fig,
                f"Error: {str(e)}",
                empty_fig,
                empty_fig,
                f"Error occurred: {str(e)}",
                False
            ]

def calculate_all_financials(df_projects, df_employees, df_timesheet, df_tasks, job_costs):
    logger.debug("Calculating all financials")
    logger.debug(f"Timesheet columns: {df_timesheet.columns}")
    logger.debug(f"Timesheet shape: {df_timesheet.shape}")
    logger.debug(f"Timesheet sample:\n{df_timesheet.head()}")
    logger.debug(f"Employees columns: {df_employees.columns}")
    logger.debug(f"Employees sample:\n{df_employees.head()}")
    
    financials_data = {}
    
    # Find the correct date column
    date_column = next((col for col in df_timesheet.columns if 'date' in col.lower()), None)
    if not date_column:
        raise ValueError("No date column found in timesheet data")

    # Find a column to link timesheet entries to employees
    employee_link_column = next((col for col in df_timesheet.columns if 'employee' in col.lower() or 'user' in col.lower()), None)
    if not employee_link_column:
        raise ValueError("No column found to link timesheet entries to employees")

    for _, project in df_projects.iterrows():
        project_timesheet = df_timesheet[df_timesheet['project_name'] == project['name']]
        for _, entry in project_timesheet.iterrows():
            date = entry[date_column].date().isoformat()
            if date not in financials_data:
                financials_data[date] = {'hours': 0, 'revenue': 0}
            
            # Find the corresponding employee
            employee_id = entry[employee_link_column]
            employee = df_employees[df_employees['id'] == employee_id].iloc[0] if not df_employees[df_employees['id'] == employee_id].empty else None
            
            if employee is not None:
                job_title = employee.get('job_title', 'Unknown')
                hourly_rate = float(job_costs.get(job_title, {}).get('revenue', 0)) / 8  # Assuming 8-hour workday
                
                hours = entry['unit_amount'] if 'unit_amount' in entry else 0
                revenue = hours * hourly_rate
                
                financials_data[date]['hours'] += hours
                financials_data[date]['revenue'] += revenue
            else:
                logger.warning(f"No matching employee found for ID: {employee_id}")
    
    return financials_data

def calculate_incremental_financials(df_projects, df_employees, df_timesheet, df_tasks, job_costs, last_calculation):
    logger.debug("Calculating incremental financials")
    new_data = {}
    for _, project in df_projects.iterrows():
        project_timesheet = df_timesheet[(df_timesheet['project_name'] == project['name']) & 
                                         (df_timesheet['date'] > last_calculation)]
        for _, entry in project_timesheet.iterrows():
            date = entry['date'].date().isoformat()
            if date not in new_data:
                new_data[date] = {'hours': 0, 'revenue': 0}
            
            employee = df_employees[df_employees['name'] == entry['employee_name']].iloc[0]
            job_title = employee['job_title']
            hourly_rate = float(job_costs.get(job_title, {}).get('revenue', 0)) / 8  # Assuming 8-hour workday
            
            hours = entry['unit_amount']
            revenue = hours * hourly_rate
            
            new_data[date]['hours'] += hours
            new_data[date]['revenue'] += revenue
    
    return new_data

def create_financials_chart(data):
    dates = list(data.keys())
    revenues = [day_data['revenue'] for day_data in data.values()]
    
    fig = go.Figure(data=[go.Scatter(x=dates, y=revenues, mode='lines')])
    fig.update_layout(title='Daily Financial Summary', xaxis_title='Date', yaxis_title='Revenue')
    return fig

def create_hours_chart(data):
    dates = list(data.keys())
    hours = [day_data['hours'] for day_data in data.values()]
    
    fig = go.Figure(data=[go.Bar(x=dates, y=hours)])
    fig.update_layout(title='Total Hours for All Projects', xaxis_title='Date', yaxis_title='Hours')
    return fig

def create_revenue_chart(data):
    dates = list(data.keys())
    revenues = [day_data['revenue'] for day_data in data.values()]
    
    fig = go.Figure(data=[go.Bar(x=dates, y=revenues)])
    fig.update_layout(title='Total Acquired Revenue for All Projects', xaxis_title='Date', yaxis_title='Revenue')
    return fig

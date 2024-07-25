from dash.dependencies import Input, Output, State
import logging
import plotly.graph_objs as go
import pandas as pd
import dash
from datetime import datetime
import json
import os

from data_management import deserialize_dataframes
from callbacks.project import calculate_project_revenue

logger = logging.getLogger(__name__)

FINANCIALS_FILE = 'financials_data.json'
LAST_CALCULATION_FILE = 'last_financials_calculation.json'

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat()
        return super().default(obj)

def save_financials_data(data):
    with open(FINANCIALS_FILE, 'w') as f:
        json.dump(data, f, cls=DateTimeEncoder)

def load_financials_data():
    if os.path.exists(FINANCIALS_FILE):
        with open(FINANCIALS_FILE, 'r') as f:
            data = json.load(f)
        # Convert ISO format strings back to datetime objects
        for project in data.values():
            for daily_data in project['daily_data']:
                daily_data['date'] = pd.to_datetime(daily_data['date'])
        return data
    return {}

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
         Input('calculate-button', 'n_clicks')],
        [State('data-store', 'data')]  # Add this line to get the current data from the store
    )
    def update_financials(start_date, end_date, n_clicks, data_store):
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
            start_date = pd.to_datetime(start_date)
            end_date = pd.to_datetime(end_date)
            
            # Deserialize the data from the store
            df_portfolio, df_employees, df_sales, df_financials, df_timesheet, df_tasks = deserialize_dataframes(data_store)
            
            logger.debug(f"Data types: portfolio={type(df_portfolio)}, employees={type(df_employees)}, timesheet={type(df_timesheet)}, tasks={type(df_tasks)}")
            logger.debug(f"DataFrame shapes: portfolio={df_portfolio.shape}, employees={df_employees.shape}, timesheet={df_timesheet.shape}, tasks={df_tasks.shape}")
            logger.debug(f"Timesheet columns: {df_timesheet.columns}")
            
            financials_data = calculate_all_financials(df_portfolio, df_employees, df_timesheet, df_tasks, job_costs, start_date, end_date)
            save_financials_data(financials_data)
            set_last_calculation_time(datetime.now())

            if not financials_data:
                empty_fig = go.Figure()
                return [
                    empty_fig,
                    "No data available. Please check your date range.",
                    empty_fig,
                    empty_fig,
                    "No data available. Please check your date range.",
                    False
                ]

            fig_financials = create_financials_chart(financials_data, df_employees, job_costs)
            fig_hours = create_hours_chart(financials_data)
            fig_revenue = create_revenue_chart(financials_data)

            total_revenue = sum(project_data['total_revenue'] for project_data in financials_data.values())

            return [
                fig_financials,
                f"Total Revenue: ${total_revenue:,.2f}",
                fig_hours,
                fig_revenue,
                "Calculation complete",
                False
            ]
        except Exception as e:
            logger.error(f"Error in update_financials: {str(e)}", exc_info=True)
            empty_fig = go.Figure()
            return [
                empty_fig,
                f"Error: {str(e)}",
                empty_fig,
                empty_fig,
                f"Error occurred: {str(e)}",
                False
            ]

def calculate_all_financials(df_portfolio, df_employees, df_timesheet, df_tasks, job_costs, start_date, end_date):
    logger.debug("Calculating all financials")
    
    financials_data = {}
    
    # Ensure we have a date column in df_timesheet
    date_column = next((col for col in df_timesheet.columns if 'date' in col.lower()), None)
    if not date_column:
        logger.error("No date column found in timesheet data")
        return financials_data
    
    logger.debug(f"Using '{date_column}' as the date column")
    
    # Convert date column to datetime
    try:
        df_timesheet[date_column] = pd.to_datetime(df_timesheet[date_column], errors='coerce')
        df_timesheet = df_timesheet.dropna(subset=[date_column])  # Remove rows with invalid dates
    except Exception as e:
        logger.error(f"Error converting date column to datetime: {str(e)}")
        return financials_data
    
    for _, project in df_portfolio.iterrows():
        project_name = project['name']
        project_timesheet = df_timesheet[
            (df_timesheet['project_name'] == project_name) &
            (df_timesheet[date_column] >= start_date) &
            (df_timesheet[date_column] <= end_date)
        ]
        
        if project_timesheet.empty:
            continue
        
        project_revenue = calculate_project_revenue(project_timesheet, df_employees, job_costs)
        project_hours = project_timesheet['unit_amount'].sum()
        
        daily_data = project_timesheet.groupby(date_column).agg({
            'unit_amount': 'sum',
            'employee_name': lambda x: list(set(x)),
            'task_id': lambda x: list(set(x))
        }).reset_index()
        
        project_financials = {
            'total_revenue': project_revenue,
            'total_hours': project_hours,
            'daily_data': daily_data.to_dict('records')
        }
        
        financials_data[project_name] = project_financials
    
    return financials_data

def create_financials_chart(financials_data, df_employees, job_costs):
    fig = go.Figure()
    
    for project, data in financials_data.items():
        daily_data = pd.DataFrame(data['daily_data'])
        if daily_data.empty:
            logger.warning(f"No daily data for project: {project}")
            continue
        
        date_column = daily_data.columns[0]  # Assume the first column is the date column
        
        try:
            daily_revenue = []
            for _, row in daily_data.iterrows():
                project_timesheet = pd.DataFrame({
                    date_column: [row[date_column]],
                    'unit_amount': [row['unit_amount']],
                    'employee_name': [row['employee_name'][0] if isinstance(row['employee_name'], list) else row['employee_name']]
                })
                revenue = calculate_project_revenue(project_timesheet, df_employees, job_costs)
                daily_revenue.append(revenue)
            
            daily_data['revenue'] = daily_revenue
            
            fig.add_trace(go.Scatter(
                x=daily_data[date_column],
                y=daily_data['revenue'],
                name=project,
                mode='lines+markers'
            ))
        except Exception as e:
            logger.error(f"Error processing data for project {project}: {str(e)}")
            continue
    
    fig.update_layout(
        title='Daily Revenue by Project',
        xaxis_title='Date',
        yaxis_title='Revenue',
        hovermode='x unified'
    )
    
    return fig

def create_hours_chart(financials_data):
    fig = go.Figure()
    
    for project, data in financials_data.items():
        daily_data = pd.DataFrame(data['daily_data'])
        if daily_data.empty:
            continue
        
        date_column = daily_data.columns[0]  # Assume the first column is the date column
        
        fig.add_trace(go.Bar(
            x=daily_data[date_column],
            y=daily_data['unit_amount'],
            name=project
        ))
    
    fig.update_layout(
        title='Daily Hours by Project',
        xaxis_title='Date',
        yaxis_title='Hours',
        barmode='stack'
    )
    
    return fig

def create_revenue_chart(financials_data):
    fig = go.Figure()
    
    projects = list(financials_data.keys())
    revenues = [data['total_revenue'] for data in financials_data.values()]
    
    fig.add_trace(go.Bar(
        x=projects,
        y=revenues,
        text=revenues,
        textposition='auto'
    ))
    
    fig.update_layout(
        title='Total Revenue by Project',
        xaxis_title='Project',
        yaxis_title='Revenue',
        yaxis_tickformat='$,.0f'
    )
    
    return fig

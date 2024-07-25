from dash.dependencies import Input, Output
import logging
import plotly.graph_objs as go
import pandas as pd
import dash
from datetime import datetime
import json
import os

from callbacks.project import calculate_project_revenue

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
            start_date = pd.to_datetime(start_date)
            end_date = pd.to_datetime(end_date)
            
            financials_data = calculate_all_financials(df_portfolio, df_employees, df_timesheet, job_costs, start_date, end_date)
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

def calculate_all_financials(df_portfolio, df_employees, df_timesheet, job_costs, start_date, end_date):
    logger.debug("Calculating all financials")
    
    financials_data = {}
    
    for _, project in df_portfolio.iterrows():
        project_name = project['name']
        project_timesheet = df_timesheet[
            (df_timesheet['project_name'] == project_name) &
            (df_timesheet['date'] >= start_date) &
            (df_timesheet['date'] <= end_date)
        ]
        
        if project_timesheet.empty:
            continue
        
        project_revenue = calculate_project_revenue(project_timesheet, df_employees, job_costs)
        project_hours = project_timesheet['unit_amount'].sum()
        
        daily_data = project_timesheet.groupby('date').agg({
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
        daily_revenue = daily_data.apply(lambda row: calculate_project_revenue(
            pd.DataFrame({'date': [row['date']], 'unit_amount': [row['unit_amount']], 'employee_name': row['employee_name']}),
            df_employees, job_costs
        ), axis=1)
        
        fig.add_trace(go.Scatter(
            x=daily_data['date'],
            y=daily_revenue,
            name=project,
            mode='lines+markers'
        ))
    
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
        
        fig.add_trace(go.Bar(
            x=daily_data['date'],
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

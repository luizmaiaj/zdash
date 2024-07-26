from dash.dependencies import Input, Output, State
import logging
import plotly.graph_objs as go
import pandas as pd
import dash
from datetime import datetime

from data_management import DataManager
from callbacks.project import calculate_project_revenue

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def register_financials_callbacks(app, data_manager: DataManager):
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
        ctx = dash.callback_context
        if not ctx.triggered and not data_manager.financials_data:
            empty_fig = go.Figure()
            return [empty_fig, "No data calculated yet", empty_fig, empty_fig, "No data calculated yet", False]
        try:
            start_date = pd.to_datetime(start_date)
            end_date = pd.to_datetime(end_date)

            # Load existing financial data if available
            financials_data = data_manager.load_financials_data(start_date, end_date)

            if not financials_data or 'calculate-button' in ctx.triggered[0]['prop_id']:
                # Calculate new financial data
                financials_data = calculate_all_financials(data_manager, start_date, end_date)
                data_manager.save_financials_data(financials_data)
                data_manager.set_last_calculation_time(datetime.now())

            if not financials_data:
                empty_fig = go.Figure()
                return empty_fig, "No data available", empty_fig, empty_fig, "No data available. Please check your date range."

            logger.info("Creating charts")
            fig_financials = create_financials_chart(financials_data, data_manager)
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

def calculate_all_financials(data_manager: DataManager, start_date, end_date):
    logger.debug("Calculating all financials")
    
    financials_data = {}
    
    # Ensure we have a date column in df_timesheet
    date_column = next((col for col in data_manager.df_timesheet.columns if 'date' in col.lower()), None)
    if not date_column:
        logger.error("No date column found in timesheet data")
        return financials_data
    
    logger.debug(f"Using '{date_column}' as the date column")
    
    # Convert date column to datetime
    try:
        data_manager.df_timesheet[date_column] = pd.to_datetime(data_manager.df_timesheet[date_column], errors='coerce')
        data_manager.df_timesheet = data_manager.df_timesheet.dropna(subset=[date_column])  # Remove rows with invalid dates
    except Exception as e:
        logger.error(f"Error converting date column to datetime: {str(e)}")
        return financials_data
    
    for _, project in data_manager.df_portfolio.iterrows():
        project_name = project['name']
        project_timesheet = data_manager.df_timesheet[
            (data_manager.df_timesheet['project_name'] == project_name) &
            (data_manager.df_timesheet[date_column] >= start_date) &
            (data_manager.df_timesheet[date_column] <= end_date)
        ].copy()  # Create an explicit copy
        
        if project_timesheet.empty:
            continue
        
        project_revenue = calculate_project_revenue(project_timesheet, data_manager.df_employees, data_manager.job_costs)
        project_hours = project_timesheet['unit_amount'].sum()
        
        # Convert task_id to string to ensure it's hashable
        project_timesheet['task_id_str'] = project_timesheet['task_id'].astype(str)
        
        daily_data = project_timesheet.groupby(date_column).agg({
            'unit_amount': 'sum',
            'employee_name': lambda x: x.unique().tolist(),
            'task_id_str': lambda x: x.unique().tolist()
        }).reset_index()
        
        # Rename task_id_str back to task_id in the result
        daily_data = daily_data.rename(columns={'task_id_str': 'task_id'})
        
        project_financials = {
            'total_revenue': project_revenue,
            'total_hours': project_hours,
            'daily_data': daily_data.to_dict('records')
        }
        
        financials_data[project_name] = project_financials
    
    return financials_data

def create_financials_chart(financials_data, data_manager):
    fig = go.Figure()
    
    # Create a DataFrame to hold all daily revenue data
    all_daily_data = []
    
    for project, data in financials_data.items():
        daily_data = pd.DataFrame(data['daily_data'])
        if daily_data.empty:
            logger.warning(f"No daily data for project: {project}")
            continue
        
        # Calculate daily revenue if not present
        if 'revenue' not in daily_data.columns:
            daily_data['revenue'] = daily_data.apply(
                lambda row: calculate_project_revenue(
                    data_manager.df_timesheet[
                        (data_manager.df_timesheet['project_name'] == project) &
                        (data_manager.df_timesheet['date'] == row['date'])
                    ],
                    data_manager.df_employees,
                    data_manager.job_costs
                ),
                axis=1
            )
        
        daily_data['project'] = project
        all_daily_data.append(daily_data)
    
    if not all_daily_data:
        return fig
    
    # Concatenate all daily data
    all_daily_data = pd.concat(all_daily_data)
    
    # Pivot the data to create a stacked bar chart
    pivoted_data = all_daily_data.pivot(index='date', columns='project', values='revenue').fillna(0)

   # Create stacked bar chart
    for project in pivoted_data.columns:
        fig.add_trace(go.Bar(
            x=pivoted_data.index,
            y=pivoted_data[project],
            name=project,
            hoverinfo='none',  # This disables the default hover
            hovertemplate=None  # This ensures our custom hovertemplate is used
        ))
    
    fig.update_layout(
        title='Daily Revenue by Project',
        xaxis_title='Date',
        yaxis_title='Revenue',
        barmode='stack',
        hovermode='closest',
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Rockwell"
        )
    )

    # Add custom hover text
    fig.update_traces(
        hovertemplate='<b>%{fullData.name}</b>Revenue: $%{y:,.2f}<extra></extra>'
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
        yaxis_tickformat='$,.0f',
        barmode='stack'
    )
    
    return fig

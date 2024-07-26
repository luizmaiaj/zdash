from dash.dependencies import Input, Output, State
import logging
import plotly.graph_objs as go
import pandas as pd
import dash
from datetime import datetime

from data_management import DataManager
from financial_calculator import FinancialCalculator

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def register_financials_callbacks(app, data_manager: DataManager):
    financial_calculator = FinancialCalculator(data_manager)

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

            financials_data = data_manager.load_financials_data(start_date, end_date)

            if not financials_data or 'calculate-button' in ctx.triggered[0]['prop_id']:
                financials_data = financial_calculator.calculate_all_financials(start_date, end_date)
                data_manager.save_financials_data(financials_data)
                data_manager.set_last_calculation_time(datetime.now())

            if not financials_data:
                empty_fig = go.Figure()
                return empty_fig, "No data available", empty_fig, empty_fig, "No data available. Please check your date range."

            fig_financials = financial_calculator.create_financials_chart(financials_data)
            fig_hours = financial_calculator.create_hours_chart(financials_data)
            fig_revenue = financial_calculator.create_revenue_chart(financials_data)

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

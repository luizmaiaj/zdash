from dash.dependencies import Input, Output
import plotly.graph_objs as go
import pandas as pd

def register_financials_callbacks(app, df_financials):
    @app.callback(
        Output('financials-chart', 'figure'),
        [Input('date-range', 'start_date'),
         Input('date-range', 'end_date')]
    )
    def update_financials(start_date, end_date):
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        
        print("Financials columns:", df_financials.columns)

        date_column = 'date'
        if date_column not in df_financials.columns:
            date_columns = [col for col in df_financials.columns if 'date' in col.lower()]
            if date_columns:
                date_column = date_columns[0]
            else:
                return go.Figure()
        
        filtered_financials = df_financials[
            (df_financials[date_column] >= start_date) &
            (df_financials[date_column] <= end_date)
        ]
        
        if filtered_financials.empty:
            return go.Figure()
        
        daily_financials = filtered_financials.groupby(date_column)['amount_total'].sum().reset_index()
        fig = go.Figure(go.Scatter(x=daily_financials[date_column], y=daily_financials['amount_total'], mode='lines'))
        fig.update_layout(title='Daily Financial Summary')
        return fig

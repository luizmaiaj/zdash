import logging
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
import pandas as pd
from dash import dash_table
from data_management import DataManager

def register_pivot_table_callbacks(app, data_manager: DataManager):
    @app.callback(
        [Output('pivot-index-selector', 'options'),
         Output('pivot-columns-selector', 'options'),
         Output('pivot-values-selector', 'options')],
        [Input('pivot-dataframe-selector', 'value')]
    )
    def update_pivot_selectors(selected_df):
        if not selected_df:
            return [], [], []
        
        df = getattr(data_manager, selected_df)
        options = [{'label': col, 'value': col} for col in df.columns]
        return options, options, options

    @app.callback(
        [Output('pivot-chart', 'figure'),
         Output('pivot-table-container', 'children')],
        [Input('pivot-index-selector', 'value'),
         Input('pivot-columns-selector', 'value'),
         Input('pivot-values-selector', 'value'),
         Input('pivot-aggfunc-selector', 'value'),
         Input('pivot-chart-type-selector', 'value'),
         Input('pivot-dataframe-selector', 'value')]
    )
    def update_pivot_table(index, columns, values, aggfunc, chart_type, selected_df):
        if not all([index, columns, values, aggfunc, selected_df]):
            return go.Figure(), "Please select all required fields"

        df = getattr(data_manager, selected_df)

        try:
            pivot_table = pd.pivot_table(df, values=values, index=index, columns=columns, aggfunc=aggfunc)
        except Exception as e:
            return go.Figure(), f"Error creating pivot table: {str(e)}"

        fig = go.Figure()

        if chart_type == 'bar':
            for col in pivot_table.columns:
                fig.add_trace(go.Bar(x=pivot_table.index, y=pivot_table[col], name=str(col)))
        elif chart_type == 'line':
            for col in pivot_table.columns:
                fig.add_trace(go.Scatter(x=pivot_table.index, y=pivot_table[col], mode='lines+markers', name=str(col)))
        elif chart_type == 'scatter':
            for col in pivot_table.columns:
                fig.add_trace(go.Scatter(x=pivot_table.index, y=pivot_table[col], mode='markers', name=str(col)))

        fig.update_layout(title='Pivot Table Chart', xaxis_title=index[0] if isinstance(index, list) else index,
                          yaxis_title=values[0] if isinstance(values, list) else values)

        table = dash_table.DataTable(
            columns=[{"name": str(i), "id": str(i)} for i in pivot_table.columns],
            data=pivot_table.reset_index().to_dict('records'),
            style_table={'height': '300px', 'overflowY': 'auto'}
        )

        return fig, table

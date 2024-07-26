from dash import html
from dash.dependencies import Input, Output, State
from llm_integration import generate_llm_report
from data_management import DataManager

import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def register_llm_callback(app, data_manager: DataManager):

    @app.callback(
        Output('llm-report-output', 'children'),
        [Input('generate-llm-report', 'n_clicks')],
        [State('model-selection', 'value'),
         State('data-store', 'data')],
        prevent_initial_call=True
    )
    def update_llm_report(n_clicks, selected_model, serialized_data):
        if n_clicks > 0 and selected_model and serialized_data:
            data = data_manager.deserialize_dataframes(serialized_data)
            df_projects, df_employees, df_sales, df_financials, df_timesheet, df_tasks = data
            report = generate_llm_report(df_projects, df_employees, df_sales, df_financials, df_timesheet, df_tasks, selected_model)
            if report.startswith("Error:"):
                return html.Div([
                    html.H4("Error Generating LLM Report"),
                    html.P(report, style={'color': 'red'})
                ])
            else:
                return html.Div([
                    html.H4(f"LLM Generated Report (Model: {selected_model})"),
                    html.Pre(report, style={'white-space': 'pre-wrap', 'word-break': 'break-word'})
                ])
        return ""
